"""mg — the Phase 2 CLI. Backend/10 Phase 2.

    mg predict --label "forearm sweep" -q impedance --low 45 --high 50 -u kOhm
    mg measure <artifact-id> --value 47.2
    mg show <artifact-id>
    mg claim "47 kOhm at 50 kHz means hydrated"
    mg status

Deliberately ugly. The point of Phase 2 is to find out whether anyone will
type a prediction before they build — not to look good doing it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .artifact import (ArtifactError, Session, calibration, measure, predict,
                       show)
from .crypto import encrypt
from .events import EventType
from .extract import FakeLLM, HTTPLLM, ingest_text
from .graph import stats
from .ids import uuid7
from .proposals import decide, ingest, pending_review
from .analyzer import analyze
from .adapters import from_env
from .agents import run_turn
from .coldstart import seed_project
from .costlog import default as costlog
from .curation import export, promote_concepts, structuring_nudge
from .evaluation import cost_per_accepted
from .frontier import frontier, tensions
from .retrieve import explain, path, query

BAR = "─" * 58


def _labels(s) -> dict[str, str]:
    """Labels live in the encrypted half, so retrieval has to be handed them
    explicitly — the graph itself never holds user text (Backend/02 §0)."""
    from .crypto import decrypt
    out: dict[str, str] = {}
    for e in s.ledger.read():
        if e.content is None:
            continue
        p = decrypt(s.keys, s.user, e.content)
        out.update(p.get("labels", {}))
        for nd in e.structural.get("nodes", []):
            if "label" in p:
                out.setdefault(nd["id"], p["label"])
    return out


def _claim(s: Session, text: str, cid: str | None = None) -> str:
    """Claim text is user content, so it rides in the encrypted half."""
    cid = cid or uuid7()
    s.ledger.append(s.user, EventType.ACCEPTED,
                    {"nodes": [{"id": cid, "type": "Claim"}]},
                    content=encrypt(s.keys, s.user, {"label": text}))
    return cid


def _fmt_show(d: dict) -> str:
    p, m = d["predicted"], d["measured"]
    out = [BAR, f"  {d['label'] or d['id']}", f"  {d['id']}", ""]
    if p:
        out.append(f"  PREDICT   {p['quantity']}  {p['low']}–{p['high']} {p['unit']}"
                   f"   🔒 locked")
    else:
        out.append("  PREDICT   — nothing locked yet")
    if m is not None:
        verdict = {"matched": "✓ MATCHED", "diverged": "✗ DIVERGED",
                   "inconclusive": "? INCONCLUSIVE"}.get(d["agreement"],
                                                         d["agreement"])
        v = m.get("value") if isinstance(m, dict) else m
        out.append(f"  MEASURE   {'—' if v is None else v} "
                   f"{p['unit'] if p else ''}".rstrip())
        out.append(f"  RESULT    {verdict}")
    else:
        out.append("  MEASURE   — not run")
    if d["supports"]:
        out.append(f"  supports  {', '.join(d['supports'])}")
    out.append(BAR)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mg")
    ap.add_argument("--user", default="local")
    ap.add_argument("--root", default="users")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("predict", help="lock a prediction (immutable)")
    p.add_argument("--label", required=True)
    p.add_argument("-q", "--quantity", required=True)
    p.add_argument("--low", type=float, required=True)
    p.add_argument("--high", type=float, required=True)
    p.add_argument("-u", "--unit", required=True)
    p.add_argument("--supports", nargs="*", default=[])
    p.add_argument("--method")
    p.add_argument("--id")

    m = sub.add_parser("measure", help="record what actually happened")
    m.add_argument("artifact_id")
    m.add_argument("--value", type=float)
    m.add_argument("--unit")
    m.add_argument("--raw")

    sh = sub.add_parser("show", help="show one artifact")
    sh.add_argument("artifact_id")

    c = sub.add_parser("claim", help="create a claim to measure against")
    c.add_argument("text")
    c.add_argument("--id")

    ing = sub.add_parser("ingest", help="ingest files into the graph")
    ing.add_argument("paths", nargs="+")
    ing.add_argument("--endpoint", help="OpenAI-compatible base URL (Tier 1a)")
    ing.add_argument("--model", default="")
    ing.add_argument("--api-key", default="")

    rv = sub.add_parser("review", help="the AMBIGUOUS queue — a thinking prompt")
    rv.add_argument("--accept", nargs="*", metavar="ID")
    rv.add_argument("--reject", nargs="*", metavar="ID")
    rv.add_argument("--all", action="store_true", help="accept everything listed")

    q = sub.add_parser("query", help="ask the graph")
    q.add_argument("text")
    q.add_argument("--lens", choices=["debug", "writeup", "learn"])
    q.add_argument("-k", type=int)

    ex = sub.add_parser("explain", help="why do I believe this?")
    ex.add_argument("node_id")

    pa = sub.add_parser("path", help="shortest justified path between two nodes")
    pa.add_argument("a"); pa.add_argument("b")

    an = sub.add_parser("analyze", help="nightly jobs — off the request path")
    an.add_argument("--json", action="store_true")

    nx_ = sub.add_parser("next", help="what to do next — gaps and tensions, one ranking")
    nx_.add_argument("--focus", nargs="*", default=[])
    nx_.add_argument("-n", type=int, default=3)

    tn = sub.add_parser("tensions", help="the Disagreement Engine")
    tn.add_argument("--focus", nargs="*", default=[])

    st = sub.add_parser("start", help="cold start — one sentence to a graph")
    st.add_argument("question")
    st.add_argument("--transcript", help="path to a transcript (a PRIOR, not knowledge)")

    ak = sub.add_parser("ask", help="ask the graph — the full turn protocol")
    ak.add_argument("question")
    ak.add_argument("--endpoint"); ak.add_argument("--api-key")
    ak.add_argument("--budget", type=float)
    ak.add_argument("-k", type=int, default=25)

    sub.add_parser("nudge", help="offer to structure drifting notes")
    sub.add_parser("promote", help="extracted -> global on a 2nd project")
    ex2 = sub.add_parser("export", help="the graph, as data you own")
    ex2.add_argument("-o", "--out")
    sub.add_parser("cost", help="what this has actually cost")
    eb = sub.add_parser("embed", help="backfill embeddings (needs an endpoint)")
    eb.add_argument("--endpoint"); eb.add_argument("--api-key")

    sub.add_parser("status", help="graph + calibration summary")

    a = ap.parse_args(argv)
    s = Session.open(a.user, a.root)
    try:
        if a.cmd == "predict":
            aid = predict(s, label=a.label, quantity=a.quantity, low=a.low,
                          high=a.high, unit=a.unit, supports=a.supports,
                          method=a.method, artifact_id=a.id)
            print(f"🔒 locked  {aid}")
            print(f"   {a.quantity}  {a.low}–{a.high} {a.unit}")
            print("   go build it, then:  mg measure "
                  f"{aid} --value <n>")
        elif a.cmd == "measure":
            r = measure(s, a.artifact_id, value=a.value, unit=a.unit,
                        raw_ref=a.raw)
            print(_fmt_show(show(s, a.artifact_id)))
            cal = calibration(s)
            if cal["hit_rate"] is not None:
                print(f"  calibration: {cal['matched']} of {cal['resolved']} "
                      f"predictions correct so far")
        elif a.cmd == "show":
            print(_fmt_show(show(s, a.artifact_id)))
        elif a.cmd == "claim":
            print(_claim(s, a.text, a.id))
        elif a.cmd == "ingest":
            llm = (HTTPLLM(a.endpoint, a.model, a.api_key) if a.endpoint
                   else FakeLLM())
            if not a.endpoint:
                print("⚠️  no --endpoint: text falls back to the stub extractor."
                      "\n    Code and CSV are parsed for real (0 tokens).\n")
            for path in a.paths:
                pth = Path(path)
                rep = ingest(s, ingest_text(pth.name, pth.read_text(), llm))
                d = rep.as_dict()
                mark = "· duplicate, skipped" if rep.duplicate else ""
                print(f"  {pth.name:<28} {d['lane']:<8} "
                      f"+{d['accepted']['nodes']}n/{d['accepted']['edges']}e  "
                      f"review {d['review']}  quarantine {d['quarantined']}  "
                      f"same_as {d['same_as']} {mark}")
        elif a.cmd == "review":
            if a.accept or a.all:
                ids = a.accept or [e["id"] for e in pending_review(s)]
                print(f"accepted {decide(s, ids, accept=True)}")
            elif a.reject:
                print(f"rejected {decide(s, a.reject, accept=False)}")
            else:
                pend = pending_review(s)
                if not pend:
                    print("queue empty — nothing needs your judgement")
                for e in pend:
                    print(f"  {e['id']}  {e['relation']:<12} "
                          f"{e['confidence']:<9} {e['score']}")
                print(f"\n  {len(pend)} item(s). "
                      f"Budget 20-30 decisions a session, not hundreds.")
        elif a.cmd == "query":
            g = s.state()
            res = query(g, a.text, _labels(s), lens=a.lens, k=a.k)
            if not res:
                print("nothing matched — the graph would rather say nothing "
                      "than something plausible")
            for r in res:
                lbl = _labels(s).get(r.id, r.id)
                print(f"  {r.score:>7.3f}  {lbl[:44]:<44} {r.hops}h  "
                      f"{' -> '.join(r.path[:4])}")
            if res:
                print(f"\n  {len(res)} of a hard cap. The limit is human, "
                      f"not technical.")
        elif a.cmd == "explain":
            e = explain(s.state(), a.node_id)
            if not e:
                print("no such node"); return 1
            lb = _labels(s)
            print(BAR)
            print(f"  {lb.get(a.node_id, a.node_id)}")
            print(f"  {e['type']}/{e['kind']}  {e['support'].upper()}  "
                  f"{e['strength']}  corroboration {e['corroboration']}")
            if e["single_method"]:
                print("  ◑ all corroboration came from ONE method")
            for k, arrow in (("supported_by", "←"), ("contradicted_by", "⚡"),
                             ("retracted_support", "✗")):
                for src in e[k]:
                    print(f"  {arrow} {lb.get(src, src)}")
            print(BAR)
        elif a.cmd == "path":
            p = path(s.state(), a.a, a.b)
            lb = _labels(s)
            print(" -> ".join(lb.get(x, x) for x in p) if p else "no path")
        elif a.cmd == "analyze":
            sc = analyze(s.state())
            if a.json:
                print(json.dumps(sc.as_dict(), indent=2)); return 0
            lb = _labels(s)
            print(f"  communities   {len(sc.communities)}")
            print(f"  predictions   {len(sc.predictions)} (Adamic-Adar)")
            print(f"  contradictions{len(sc.contradictions):>3}")
            print(f"  stale         {len(sc.stale)}")
            if sc.crossovers:
                print("\n  ⭐ crossovers — never shown without the reason:")
            for c in sc.crossovers:
                print(f"    {c['score']}  {lb.get(c['src'], c['src'])[:22]} <-> "
                      f"{lb.get(c['dst'], c['dst'])[:22]}")
                for w in c["why"]:
                    print(f"        · {w}")
            for x in sc.contradictions[:5]:
                if x.get("kind") == "CONFLICT":
                    print(f"\n  ⚡ CONTESTED  {lb.get(x['node'], x['node'])[:40]}")
                    print(f"        for {len(x['for'])} · against {len(x['against'])}"
                          f" · ratio {x['contest_ratio']}")
        elif a.cmd == "next":
            lb = _labels(s)
            acts = frontier(s.state(), focus=set(a.focus), limit=a.n)
            if not acts:
                print("nothing ready — ingest something or record a measurement")
            for act in acts:
                head = lb.get(act.id, act.id)[:44]
                print(f"  ◆ {head}")
                print(f"    {act.kind.lower()} · {act.why}")
        elif a.cmd == "tensions":
            lb = _labels(s)
            ts = tensions(s.state(), focus=set(a.focus))
            if not ts:
                print("nothing disagrees yet")
            for t in ts:
                print(f"  {t.level}  {t.kind:<11} "
                      f"{lb.get(t.a, t.a)[:24]} ⚡ {lb.get(t.b, t.b)[:24]}")
                print(f"       {t.framing}")
        elif a.cmd == "start":
            tx = Path(a.transcript).read_text() if a.transcript else ""
            cs = seed_project(s, a.question, transcript=tx)
            if cs.vague:
                print("⚠️  no measurable success criterion in that question.")
                print("    How will you know it worked? Seeded anyway, "
                      "but the graph will be generic.\n")
            if not cs.matched:
                print("⚠️  nothing matched the embedded-systems skeleton — "
                      "question decomposition only.\n")
            d = cs.as_dict()
            print(f"  root question   1")
            print(f"  sub-questions   {d['subquestions']}")
            print(f"  concepts        {d['concepts']}"
                  f"{f' (+{d[chr(39)+chr(39)]})' if False else ''}"
                  f"{f'  [{cs.capped} more beyond the 25-node cap]' if cs.capped else ''}")
            if cs.exposures:
                print(f"  exposure marks  {len(cs.exposures)}  "
                      f"(a prior — never knowledge)")
            print("\n  nothing is validated yet. That is correct.")
            print("  next:  mg next")
        elif a.cmd == "ask":
            agent, embedder, _ = from_env(a.endpoint, a.api_key)
            if agent is None:
                print("✗ no endpoint. Set MG_ENDPOINT and MG_API_KEY, or pass"
                      " --endpoint/--api-key.\n"
                      "  Everything else works without one; the turn protocol"
                      " does not.", file=sys.stderr)
                return 1
            g, lb = s.state(), _labels(s)
            vecs = s.vectors().all() if embedder else None
            hits = query(g, a.question, lb, k=a.k, embedder=embedder,
                         vectors=vecs)
            t = run_turn(g, a.question, [r.id for r in hits], agent, labels=lb,
                         budget_usd=a.budget,
                         on_token=lambda txt: print(f"\n{txt}\n"))
            if t.degraded:
                print("⚠️  degraded — budget breached, cheaper path taken")
            for c in t.critique:
                print(f"  ⚡ {c.get('relation', 'note')}: "
                      f"{c.get('citation_state', '')}")
            for r in t.rejected:
                print(f"  ✗ rejected: {r.reason}")
            print(f"\n  roles {' -> '.join(t.role_calls)}"
                  f"{' (escalated)' if t.escalated else ''}")
            print(f"  {cost_per_accepted(t.cost_rows, t.accepted_count)}")
        elif a.cmd == "nudge":
            n = structuring_nudge(s.state())
            if not n.triggered:
                print(f"no nudge — note ratio {n.ratio}")
            else:
                print(f"⚠️  {n.reason}")
                print(f"    {len(n.outstanding)} could be structured. "
                      f"This is an offer, not a requirement.")
        elif a.cmd == "promote":
            p_ = promote_concepts(s)
            print(f"promoted {len(p_)} concept(s) to global")
        elif a.cmd == "export":
            blob = export(s.state(), _labels(s))
            if a.out:
                Path(a.out).write_text(blob); print(f"wrote {a.out}")
            else:
                print(blob)
        elif a.cmd == "cost":
            rows = (s.costs or costlog()).rows()
            if not rows:
                print("no operations recorded yet")
            agg: dict = {}
            for op, wall, cpu, _tags in rows:
                d = agg.setdefault(op, {"n": 0, "wall_ms": 0})
                d["n"] += 1; d["wall_ms"] += wall
            for op, d in sorted(agg.items()):
                print(f"  {op:<12} {d['n']:>4} calls  {d['wall_ms']:>6} ms"
                      f"  ({d['wall_ms'] / max(1, d['n']):.1f} ms avg)")
        elif a.cmd == "embed":
            _, embedder, _ = from_env(a.endpoint, a.api_key)
            if embedder is None:
                print("✗ no endpoint configured", file=sys.stderr); return 1
            vs = s.vectors()
            n = vs.backfill(_labels(s), embedder)
            vs.close()
            print(f"embedded {n} node(s)")
        elif a.cmd == "status":
            print(json.dumps({**stats(s.state()), "calibration": calibration(s)},
                             indent=2))
    except ArtifactError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

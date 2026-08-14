/**
 * Phase 5 — Ask. `Frontend/01 §4.0`, the turn protocol made visible.
 *
 * ⭐ The answer is not the whole reply. A turn produces prose, proposals the
 * gate accepted, a critique, and proposals it REJECTED with reasons — and the
 * rejections are the most legible evidence that capability binding does
 * anything at all. A pane that renders only the prose is a chat window with
 * extra steps.
 *
 * ⚠️ Retrieval hits and the turn are two different things and are labelled as
 * such. The hits are deterministic and free; the answer costs money and calls
 * models. Blending them into one "results" list is how a student stops being
 * able to tell what the system knows from what a model said.
 */
import { useTurn } from "../lib/hooks";
import type { Turn } from "../lib/api";
import { ApiError } from "../lib/api";
import "./AnswerPane.css";

function Cost({ c }: { c: Turn["cost"] }) {
  const tiers = Object.entries(c.by_tier ?? {}).filter(([, v]) => v > 0);
  return (
    <div className="ans-cost">
      <span>${c.usd?.toFixed(4) ?? "0.0000"}</span>
      {/* ⭐ per ACCEPTED, not per turn — the number that says whether the
          graph is earning its keep (`Backend/09` Q2). */}
      {c.usd_per_accepted != null && <span>${c.usd_per_accepted.toFixed(4)} / accepted</span>}
      {tiers.map(([t, v]) => <span key={t} className="tier">{t} ${v.toFixed(4)}</span>)}
    </div>
  );
}

export function AnswerPane({ question }: { question: string }) {
  const turn = useTurn();
  const t = turn.data;

  return (
    <div className="ans">
      <div className="ans-bar">
        <button
          className="ans-go"
          disabled={!question.trim() || turn.isPending}
          onClick={() => turn.mutate(question)}
        >
          {turn.isPending ? "Thinking…" : "Ask the graph"}
        </button>
        {/* ⚠️ Says what it will do before it does it. A button that silently
            spends money on a model is not the same button as one that runs a
            free traversal, and the student must be able to tell. */}
        <small>runs the turn protocol — models, and money</small>
      </div>

      {turn.isError && <TurnError error={turn.error} />}

      {t && (
        <>
          {t.degraded && (
            <p className="ans-flag warn">
              ⚠ Degraded — the budget was reached, so a cheaper path was taken.
              This answer is not what a full turn would have produced.
            </p>
          )}
          <p className="ans-prose">{t.answer || <em>The model returned no prose.</em>}</p>

          <div className="ans-meta">
            <span>{t.role_calls.join(" → ")}</span>
            {t.escalated && <span className="esc">escalated</span>}
            <Cost c={t.cost} />
          </div>

          {t.proposals.length > 0 && (
            <section className="ans-sec">
              <h4>Proposed — pending your review</h4>
              <ul>
                {t.proposals.map((p, i) => (
                  <li key={String(p.id ?? i)}>
                    <code>{String(p.subject ?? "?")}</code>
                    <span className="rel">{String(p.relation ?? "relates_to")}</span>
                    <code>{String(p.object ?? "?")}</code>
                    <span className="conf">{String(p.confidence ?? "")}</span>
                  </li>
                ))}
              </ul>
              {/* ⚠️ Nothing here is in the graph yet. Saying so matters: the
                  turn returns proposals, it never writes them. */}
              <small>Not in your graph. They enter through Review, or not at all.</small>
            </section>
          )}

          {t.critique.length > 0 && (
            <section className="ans-sec">
              <h4>The Critic disagreed</h4>
              <ul>
                {t.critique.map((c, i) => (
                  <li key={i}>
                    <span className="rel">{String(c.relation ?? "note")}</span>
                    <span className="conf">{String(c.citation_state ?? "")}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {t.rejected.length > 0 && (
            <section className="ans-sec rejected">
              {/* ⭐ Shown, always. A turn that discarded four proposals and
                  says nothing looks exactly like one that found four. */}
              <h4>Discarded by the gate — {t.rejected.length}</h4>
              <ul>
                {t.rejected.map((r, i) => <li key={i}><span className="why">{r.reason}</span></li>)}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}

/** The 503 is a first-class state here, not an error banner. */
function TurnError({ error }: { error: unknown }) {
  const e = error instanceof ApiError ? error : null;
  if (e?.status === 503) {
    return (
      <div className="ans-flag unconfigured">
        <b>No model endpoint configured.</b>
        <span>{e.message}</span>
        {/* ⚠️ Say what still works. This is the ONLY surface that needs a
            model — telling the student the product is down would be false. */}
        <small>
          Everything else — the frontier, retrieval, explain, predict/measure,
          the log — is deterministic and unaffected.
        </small>
      </div>
    );
  }
  if (e?.isRefusal) {
    return (
      <div className="ans-flag refused">
        <b>Not permitted with this token.</b>
        <span>{e.message}</span>
      </div>
    );
  }
  return <div className="ans-flag warn">{String(e?.message ?? error)}</div>;
}

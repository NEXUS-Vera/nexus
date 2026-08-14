/**
 * Phase 7 — Share. `Frontend/01 §4.6`.
 *
 * One page, three sections: what this is · what was proven · how it got there.
 * Three rules, all of which are easier to break than to keep:
 *
 * ⭐ Failures stay visible. The diverged prediction, the retraction, the dead
 *    end. That is what demonstrates competence, and it is exactly what a
 *    polished write-up destroys.
 * ⭐ The calibration curve is the headline — "this student's predictions got
 *    measurably better" is a claim no transcript can make. Rendered as
 *    predicted intervals against measured values, not a single score.
 * ⚠️ The hash makes it verifiable. Without it this is a claim about a record
 *    rather than a record, and anyone can make a claim.
 *
 * No editing, no review queue, no frontier. Sharing is a different job from
 * working, and a share page with an Accept button is a working surface that
 * happens to be public.
 */
import { useMemo, useState } from "react";

import { useCalibration, useLog, useStats } from "../lib/hooks";
import type { Artifact } from "../lib/api";
import { ApiError } from "../lib/api";
import { ErrorState, LoadingState } from "./SurfaceStates";
import { copyText, download, shareMarkdown } from "../lib/exportShare";
import "./ShareView.css";

/** predicted [low, high] vs measured, on one shared scale per row. */
function AgreementRow({ a }: { a: Artifact }) {
  const p = a.predicted, m = a.measured;
  const bar = useMemo(() => {
    if (!p || m?.value == null) return null;
    const lo = Math.min(p.low, m.value), hi = Math.max(p.high, m.value);
    const pad = (hi - lo) * 0.25 || 1;
    const min = lo - pad, span = hi + pad - min;
    return {
      left: ((p.low - min) / span) * 100,
      width: ((p.high - p.low) / span) * 100,
      mark: ((m.value - min) / span) * 100,
    };
  }, [p, m]);

  return (
    <tr className={a.agreement === "diverged" ? "diverged" : undefined}>
      <td className="sh-label">{a.label ?? a.id}</td>
      {/* data-label feeds the phone layout, where the header row is gone */}
      <td className="sh-num" data-label="predicted">{p ? `${p.low}–${p.high} ${p.unit}` : "—"}</td>
      <td className="sh-num" data-label="measured">{m?.value != null ? `${m.value} ${m.unit}` : "not run"}</td>
      <td className="sh-bar">
        {bar && (
          <div className="sh-track" aria-hidden>
            <span className="sh-range" style={{ left: `${bar.left}%`, width: `${bar.width}%` }} />
            <span className="sh-mark" style={{ left: `${bar.mark}%` }} />
          </div>
        )}
      </td>
      <td className={"sh-verdict " + a.agreement}>
        {a.agreement === "matched" ? "✓ matched"
          : a.agreement === "diverged" ? "✗ diverged"
          : a.agreement === "inconclusive" ? "inconclusive" : "not run"}
      </td>
    </tr>
  );
}

/** F9 — one page, three depths. */
type Depth = "summary" | "standard" | "full";
const DEPTHS: Array<{ id: Depth; label: string; hint: string }> = [
  { id: "summary", label: "Summary", hint: "the answer and the numbers" },
  { id: "standard", label: "Standard", hint: "adds how it got there" },
  { id: "full", label: "Full", hint: "every entry, every withdrawal" },
];

export function ShareView({ question }: { question?: string }) {
  const log = useLog();
  const cal = useCalibration();
  const stats = useStats();

  /* ⭐ F9 resolved: ONE canonical page with collapsible depth, not
     per-audience variants. A professor wants rigour, an investor wants
     trajectory, a teammate wants blockers — and per-audience versions mean the
     student CURATES, which is both the organisational tax we removed and an
     invitation to polish away the failures that make this artifact worth
     anything.

     Depth is the READER's control: everyone is handed the same record and
     expands what they care about.

     ⚠️ The author tunes EMPHASIS, never CONTENT. Title and opening depth are
     theirs. Failures are not removable at any depth — a Share page you can
     quietly clean up is a press release, and the entire claim of this page is
     that it is not one. */
  const [depth, setDepth] = useState<Depth>("standard");
  const [title, setTitle] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);

  if (log.isLoading) return <LoadingState><div className="sh-skel" /></LoadingState>;
  if (log.error) {
    const e = log.error as ApiError;
    return (
      <ErrorState
        error={e.isRefusal
          ? "This link's role cannot read the timeline, so there is nothing to publish."
          : `The shared record did not load — ${e.message}`}
        stillWorks="Nothing about the project itself has changed."
        onRetry={e.isRefusal ? undefined : () => location.reload()}
      />
    );
  }

  const arts = log.data?.artifacts ?? [];
  const resolved = arts.filter((a) => a.agreement === "matched" || a.agreement === "diverged");
  const head = log.data?.head;

  const entries = log.data?.entries ?? [];
  /* ⚠️ At Summary depth the timeline collapses to withdrawals and dead ends —
     the parts a reader would otherwise never scroll to. Shortening the page
     must never mean shortening the honesty, or "Summary" becomes the version
     people share when they have something to hide. */
  const shown = depth === "full" ? entries
    : depth === "standard" ? entries.slice(-12)
    : entries.filter((e) => e.retracted || e.type === "dead_end");

  return (
    <article className="share">
      <div className="sh-controls" role="group" aria-label="reading depth">
        <div className="sh-depth">
          {DEPTHS.map((d) => (
            <button key={d.id} className={depth === d.id ? "on" : ""} title={d.hint}
              aria-pressed={depth === d.id} onClick={() => setDepth(d.id)}>
              {d.label}
            </button>
          ))}
        </div>
        <div className="sh-acts">
          {/* ⚠️ Export carries the failures and the hash too. A Share page you
              can clean up on the way OUT is a press release with extra steps. */}
          <button className="sh-edit" onClick={() => {
            const md = shareMarkdown({
              title: title || question || "This project",
              log: log.data!, calibration: cal.data, stats: stats.data ?? null });
            download(`${(title || question || "nexus-share").slice(0, 48)
              .replace(/[^\w -]/g, "").trim().replace(/\s+/g, "-").toLowerCase()}.md`, md);
          }}>Markdown</button>
          {/* the browser's own engine makes a better PDF than a 300 kB library */}
          <button className="sh-edit" onClick={() => window.print()}>PDF</button>
          <button className="sh-edit" onClick={async () => {
            const md = shareMarkdown({
              title: title || question || "This project",
              log: log.data!, calibration: cal.data, stats: stats.data ?? null });
            setCopied(await copyText(md));
            setTimeout(() => setCopied(false), 1600);
          }}>{copied ? "Copied" : "Copy"}</button>
          <button className="sh-edit" onClick={() => setEditing((e) => !e)}>
            {editing ? "Done" : "Adjust"}
          </button>
        </div>
      </div>

      {editing && (
        <div className="sh-editor">
          <label>
            <span>Title shown to readers</span>
            <input value={title ?? question ?? ""} placeholder={question ?? "This project"}
              onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label>
            <span>Opens at</span>
            <select value={depth} onChange={(e) => setDepth(e.target.value as Depth)}>
              {DEPTHS.map((d) => (
                <option key={d.id} value={d.id}>{d.label} — {d.hint}</option>
              ))}
            </select>
          </label>
          {/* ⚠️ Stated plainly rather than enforced silently. A student who
              expects to hide the diverged run should learn it here, with the
              reason, not by hunting for a toggle that does not exist. */}
          <p className="sh-editor-note">
            Withdrawals and diverged results cannot be hidden at any depth. They
            are what makes this page evidence rather than a claim — and at
            Summary depth they are the <em>only</em> history shown.
          </p>
        </div>
      )}

      <section className="sh-sec">
        <h2 className="sh-h">What this is</h2>
        <p className="sh-q">{title || question || "This project"}</p>
        <div className="sh-chips">
          {stats.data && <><span className="chip">{stats.data.established} established</span>
            <span className="chip">{stats.data.contested} contested</span>
            <span className="chip">{stats.data.nodes} nodes</span></>}
        </div>
      </section>

      <section className="sh-sec">
        <h2 className="sh-h">What was proven</h2>
        {resolved.length === 0 ? (
          /* ⚠️ Not an empty illustration. Say what would fill it — a share
             page with no measurements is honest, and pretending otherwise is
             the failure this whole surface exists to avoid. */
          <p className="sh-none">No prediction has been measured yet. This page will stay
            thin until one is — which is the accurate thing for it to say.</p>
        ) : (
          <table className="sh-table">
            <thead>
              <tr><th>Artifact</th><th>Predicted</th><th>Measured</th><th></th><th>Verdict</th></tr>
            </thead>
            <tbody>{arts.map((a) => <AgreementRow key={a.id} a={a} />)}</tbody>
          </table>
        )}
        {cal.data && cal.data.resolved > 0 && (
          <p className="sh-cal">
            <b>{cal.data.matched}</b> of <b>{cal.data.resolved}</b> resolved predictions matched
            {cal.data.hit_rate != null && <> — hit rate <b>{Math.round(cal.data.hit_rate * 100)}%</b></>}
            {cal.data.inconclusive > 0 && <> · {cal.data.inconclusive} inconclusive</>}
          </p>
        )}
      </section>

      <section className="sh-sec">
        <h2 className="sh-h">How it got there</h2>
        {depth === "summary" && shown.length > 0 && (
          <p className="sh-depth-note">
            Showing only what was withdrawn or abandoned — switch to Standard or
            Full for the rest.
          </p>
        )}
        {shown.length === 0 && <p className="sh-none">Nothing recorded yet.</p>}
        <ol className="sh-time">
          {shown.map((e) => (
            <li key={e.seq} className={e.retracted ? "gone" : undefined}>
              <span className="sh-t">{(e.ts || "").slice(0, 10)}</span>
              <span className="sh-e">
                {e.labels.length ? e.labels.join(" · ") : `${e.ids.length} item(s)`}
              </span>
              {e.retracted && <span className="sh-tag">withdrawn</span>}
              {e.type === "dead_end" && <span className="sh-tag">dead end</span>}
            </li>
          ))}
        </ol>
      </section>

      {head && (
        <footer className="sh-foot">
          {/* ⭐ The verifiability line. It is deliberately the last thing on
              the page and deliberately not a badge — a green tick invites
              trust in the tick; the hash invites replay. */}
          <span className={head.verified ? "ok" : "bad"}>
            {head.verified
              ? "Ledger chain verifies. Every entry above was written when it says it was."
              : "⚠ This chain does not verify. Treat the order above as unproven."}
          </span>
          <code className="sh-hash">{head.hash}</code>
          <span className="sh-seq">head seq {head.seq}</span>
        </footer>
      )}
    </article>
  );
}

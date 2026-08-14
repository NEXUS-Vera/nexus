/**
 * Phase 7 — Log. `Frontend/01 §4.5`.
 *
 * ⭐ "A document that grows. NOT a feed." The distinction is load-bearing:
 * a feed is read newest-first and never finished, a document is read
 * oldest-first and becomes the write-up. So this renders in ascending `seq`,
 * has no infinite scroll, and never says "new since you were last here" —
 * that is a feed's sentence.
 *
 * ⚠️ Retractions render as entries, struck but present. Removing them would
 * make this a write-up, and a write-up is exactly the artifact that destroys
 * the evidence of competence the ledger exists to hold.
 */
import { useMemo } from "react";

import { useLog } from "../lib/hooks";
import type { LogEntry } from "../lib/api";
import { ApiError } from "../lib/api";
import { EmptyState, ErrorState, LoadingState } from "./SurfaceStates";
import "./LogView.css";

const VERB: Record<string, string> = {
  validated: "measured",
  retracted: "withdrew",
  dead_end: "stopped",
};

/** Grouped by day, because a project is remembered in days, not in seq. */
function byDay(entries: LogEntry[]) {
  const out: Array<{ day: string; items: LogEntry[] }> = [];
  for (const e of entries) {
    const day = (e.ts || "").slice(0, 10);
    const last = out[out.length - 1];
    if (last && last.day === day) last.items.push(e);
    else out.push({ day, items: [e] });
  }
  return out;
}

function fmtDay(d: string) {
  if (!d) return "undated";
  const dt = new Date(d + "T00:00:00Z");
  return isNaN(+dt) ? d
    : dt.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function LogView({ onPredict }: { onPredict?: () => void } = {}) {
  const { data, isLoading, error } = useLog();
  const days = useMemo(() => byDay(data?.entries ?? []), [data]);

  if (isLoading) return <LoadingState><div className="log-skel" /></LoadingState>;
  if (error) {
    const e = error as ApiError;
    return (
      <ErrorState
        error={e.isRefusal
          ? "This role cannot read the timeline, so the log is closed to it."
          : `The log did not load — ${e.message}`}
        stillWorks="The frontier, the graph and your predictions are unaffected."
        /* ⚠️ no retry on a refusal — see ErrorState. */
        onRetry={e.isRefusal ? undefined : () => location.reload()}
      />
    );
  }
  if (!days.length) {
    return (
      <EmptyState
        message="Nothing measured yet. The log fills when you validate a prediction — it is the document this project becomes, including what you withdraw."
        actionText="Make a prediction"
        onAction={onPredict ?? (() => {})}
      />
    );
  }

  return (
    <article className="log">
      {days.map(({ day, items }) => (
        <section key={day} className="log-day">
          <h3 className="log-date">{fmtDay(day)}</h3>
          {items.map((e) => (
            <p key={e.seq} className={"log-entry" + (e.retracted ? " gone" : "")}>
              <span className="log-verb">{VERB[e.type] ?? e.type}</span>
              {/* ⭐ Labels are absent, not blank, when the token cannot read
                  content — so say which, rather than rendering an empty row
                  that reads as a bug. */}
              {e.labels.length
                ? <span className="log-what">{e.labels.join(" · ")}</span>
                : <span className="log-opaque">{e.ids.length} item{e.ids.length === 1 ? "" : "s"} — labels not readable by this role</span>}
              <span className="log-seq">#{e.seq}</span>
            </p>
          ))}
        </section>
      ))}
      {data && (
        <footer className="log-foot">
          {/* ⚠️ The chain state is shown even here, not only on Share. A
              document whose own integrity is unverified should say so to the
              person who wrote it first. */}
          <span className={data.head.verified ? "ok" : "bad"}>
            {data.head.verified ? "chain verified" : "⚠ chain does not verify"}
          </span>
          <code>{data.head.hash.slice(0, 12)}… · seq {data.head.seq}</code>
        </footer>
      )}
    </article>
  );
}

/**
 * F2 — the overview is a **state dashboard**, not a minimap. Settled by Aryav
 * 2026-08-13: *"it needs to be a dashboard that provides optimal info for the
 * everyday summary needs of a user."*
 *
 * ⭐ Why not a minimap: a shrunken hairball is still a hairball. And only we
 * can build this one — it needs epistemic state (established / contested /
 * unfooted / calibration) that no competitor records.
 *
 * ⚠️ The discipline this screen needs is SUBTRACTION. A dashboard's failure
 * mode is not missing a number, it is showing twelve — at which point the
 * student reads none of them. Four rows, and each has to answer a question
 * somebody actually asks in the morning:
 *
 *     how solid is what I have?     the established bar
 *     what needs me?                contested + unfooted + reachable
 *     am I getting better?          the calibration strip
 *     how am I habitually wrong?    the bias line  ⭐ nothing else can say this
 */
import { useCalibration, useStats } from "../lib/hooks";
import type { Bias } from "../lib/api";
import "./Dashboard.css";

function Bar({ value, total, tone }: { value: number; total: number; tone: string }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="db-bar" role="img" aria-label={`${pct}%`}>
      <i style={{ width: `${pct}%`, background: `var(--${tone})` }} />
    </div>
  );
}

/**
 * ⭐ The calibration strip: the last ten resolved predictions as dots.
 * A number ("70%") is a score; a sequence is a TREND, and the whole claim of
 * this product is that judgement improves. The shape is the message.
 */
function Strip({ matched, resolved }: { matched: number; resolved: number }) {
  const n = Math.min(10, resolved);
  const hits = resolved > 0 ? Math.round((matched / resolved) * n) : 0;
  return (
    <div className="db-strip" aria-label={`${matched} of ${resolved} matched`}>
      {Array.from({ length: n }, (_, i) => (
        <span key={i} className={i < hits ? "hit" : "miss"} />
      ))}
      {n === 0 && <em>no resolved predictions yet</em>}
    </div>
  );
}

export function Dashboard({ bias = [], onOpen }: {
  bias?: Bias[]; onOpen?: (what: "contested" | "gaps" | "log") => void;
}) {
  const stats = useStats();
  const cal = useCalibration();
  const s = stats.data;

  // ⚠️ Loading shows the SHAPE, not a spinner. A spinner over a region that
  // already has content reads as broken rather than busy (`F07 §1`).
  if (!s) return <div className="db db-skel" aria-busy="true" />;

  const needsYou = s.contested + (s.dead_ends ?? 0);
  const leading = bias.find((b) => b.direction !== "calibrated");

  return (
    <section className="db">
      <div className="db-row">
        <div className="db-k">Established</div>
        <div className="db-v"><b>{s.established}</b> of {s.nodes}</div>
        <Bar value={s.established} total={s.nodes} tone="support" />
      </div>

      <div className="db-row">
        <div className="db-k">Needs you</div>
        <div className="db-v">
          {/* ⚠️ Counted, never listed. This is a pull surface — the only thing
              allowed to interrupt is a P0 tension. */}
          <button className="db-link" onClick={() => onOpen?.("contested")}>
            <b>{s.contested}</b> contested
          </button>
          {s.single_method > 0 && <span> · {s.single_method} single-method</span>}
        </div>
        <Bar value={needsYou} total={Math.max(s.nodes, 1)} tone="contradict" />
      </div>

      <div className="db-row">
        <div className="db-k">Calibration</div>
        <div className="db-v">
          {cal.data
            ? <><b>{cal.data.matched}</b> of {cal.data.resolved} matched
                {cal.data.hit_rate != null && <> · {Math.round(cal.data.hit_rate * 100)}%</>}</>
            : "—"}
        </div>
        <Strip matched={cal.data?.matched ?? 0} resolved={cal.data?.resolved ?? 0} />
      </div>

      {/* ⭐ The row nothing else in the world can render. It needs predictions
          locked BEFORE the measurement, grouped by quantity — the student's own
          error signature. A supervisor learns this about you in a term. */}
      {leading && (
        <div className="db-row db-bias">
          <div className="db-k">Your pattern</div>
          <div className="db-v">
            <b>{leading.quantity}</b> runs {leading.direction}
            <small> — {leading.n} resolved, {leading.matched} held</small>
          </div>
          <p className="db-advice">{leading.advice}</p>
        </div>
      )}
    </section>
  );
}

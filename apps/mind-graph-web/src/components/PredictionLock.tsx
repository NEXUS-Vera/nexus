/**
 * The Artifact loop's one interaction. `F07 §2.3`, re-orchestrated for **F8**.
 *
 * F8 is the moat's UX risk: this is the most form-like thing in a product
 * built to remove friction, and it appears at the exact moment a student is
 * impatient to go and build. If it feels like paperwork it does not get
 * filled in — and calibration is the whole differentiator.
 *
 * The fix was never "make the form prettier". It was the ORDER:
 *
 * ⭐ 1. The range is the only gate. Three fields, one line, done. `because`
 *       and `method` moved AFTER the lock — they are worth having and worth
 *       nothing if they stop the lock from happening.
 * ⭐ 2. The lock is a moment, not a save. Fields become text, timestamped.
 *       A greyed-out input invites you to look for the edit button; text says
 *       the decision is made.
 * ⭐ 3. The payout is immediate. Calibration used to be invisible for weeks —
 *       so the student paid the cost now and got the reward never. Showing
 *       "your last 6: 4 matched — this is #7" at lock time makes it a streak
 *       you are already in the middle of.
 * ⚠️ 4. `because` never blocks. It is the highest-value free text in the
 *       product and the fastest thing to abandon under friction.
 */
import { useState } from "react";
import "./PredictionLock.css";

export interface LockedPrediction {
  min: number; max: number; unit: string; because: string; method: string;
}

const UNITS = ["kΩ", "Ω", "MΩ", "ms", "µs", "%", "mA", "V", "dB", "Hz"];

export function PredictionLock({ onLock, defaultMethod }: {
  onLock: (d: LockedPrediction) => Promise<void>;
  defaultMethod?: string;
}) {
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const [unit, setUnit] = useState(UNITS[0]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);


  const ready = min !== "" && max !== "" && !Number.isNaN(+min) && !Number.isNaN(+max);
  const inverted = ready && +min > +max;

  const lock = async () => {
    if (!ready || inverted) return;
    setBusy(true); setErr(null);
    const d = { min: +min, max: +max, unit, because: "", method: defaultMethod ?? "" };
    try {
      await onLock(d);
    } catch (e) {
      // ⚠️ Failing to lock must not look like locking. The whole value of the
      // timestamp is that it is real.
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  /* ⚠️ No post-lock branch here. ArtifactLoop owns everything after the lock
     (the sealed line, the payout, the optional detail, the measure step) — two
     components both rendering "after the lock" is how the payout ended up
     unreachable the first time this shipped. */
  return (
    <div className="plock">
      {/* ⭐ ONE line. Everything that is not the range has been moved out of
          the way of the commitment. */}
      <div className="plock-row">
        <span className="plock-key">I expect</span>
        <input className="num" inputMode="decimal" value={min} placeholder="45"
          onChange={(e) => setMin(e.target.value)} aria-label="low end" />
        <span className="dash">–</span>
        <input className="num" inputMode="decimal" value={max} placeholder="50"
          onChange={(e) => setMax(e.target.value)} aria-label="high end"
          onKeyDown={(e) => { if (e.key === "Enter") lock(); }} />
        <select value={unit} onChange={(e) => setUnit(e.target.value)} aria-label="unit">
          {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
        </select>
        <button className="plock-go" onClick={lock} disabled={!ready || inverted || busy}>
          {busy ? "Locking…" : "🔒 Lock"}
        </button>
      </div>

      {inverted && <p className="plock-warn">Low end is above the high end — swap them.</p>}
      {err && <p className="plock-warn">Not locked: {err}</p>}

      <p className="plock-hint">
        A range is enough. You can add why and how after — the point is that the
        number is written down <em>before</em> you build.
      </p>
    </div>
  );
}

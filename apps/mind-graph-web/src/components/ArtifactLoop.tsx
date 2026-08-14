/**
 * The Artifact loop — predict, build, measure, verdict. Frontend/01 §4.3.
 *
 * ⭐ This is the moat and it is deliberately built before anything with a graph
 * in it, because F8 is the biggest unknown in the product: will a student type
 * a prediction *before* they build? Nothing here needs a graph, a model, or a
 * key — so the answer costs one afternoon rather than one phase.
 *
 * ⚠️ Two rules the code enforces rather than documents:
 *   1. A locked prediction is immutable. The API refuses a second one.
 *   2. The verdict is DERIVED from the locked range. Nobody may supply it —
 *      an editable prediction makes the calibration record self-flattering,
 *      which is the one thing this loop exists to prevent.
 */
import { useState } from 'react';

import { api, ApiError } from '../lib/api';
import { PredictionLock } from './PredictionLock';
import './ArtifactLoop.css';

type Phase = 'predict' | 'built' | 'done';

interface Locked {
  id: string;
  label: string;
  low: number;
  high: number;
  unit: string;
  at: string;
}

export function ArtifactLoop({ onRecorded, calibration }: {
  onRecorded?: () => void;
  /** ⭐ F8's payout: shown AT the moment of locking, not weeks later. */
  calibration?: { matched: number; resolved: number };
}) {
  const [phase, setPhase] = useState<Phase>('predict');
  const [locked, setLocked] = useState<Locked | null>(null);
  const [measured, setMeasured] = useState('');
  const [verdict, setVerdict] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [because, setBecause] = useState('');
  const [detailSaved, setDetailSaved] = useState(false);

  const lock = async (d: { min: number; max: number; unit: string; because: string; method: string }) => {
    setError(null);
    // ⚠️ Guarded here as well as server-side. A backwards range is a typo, and
    // the honest moment to say so is before it is immutable.
    if (d.min > d.max) { setError(`${d.min} is above ${d.max} — check the range.`); throw new Error('range'); }
    try {
      const res = (await api.predict({
        label: d.because || 'Untitled run',
        quantity: 'measurement',
        low: d.min, high: d.max, unit: d.unit, method: d.method,
      })) as Record<string, unknown>;
      setLocked({
        id: String(res.id ?? ''),
        label: d.because || 'Untitled run',
        low: d.min, high: d.max, unit: d.unit,
        at: new Date().toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }),
      });
      setPhase('built');
    } catch (e) {
      setError(e instanceof ApiError && e.isRefusal
        ? 'Only the signed-in human may lock a prediction — no agent bundle can.'
        : String(e));
      throw e;
    }
  };

  const measure = async () => {
    if (!locked) return;
    setError(null);
    try {
      const res = (await api.validate({
        artifact_id: locked.id,
        value: measured === '' ? null : parseFloat(measured),
      })) as Record<string, unknown>;
      setVerdict(String(res.agreement ?? 'inconclusive'));
      setPhase('done');
      onRecorded?.();
    } catch (e) {
      setError(String(e));
    }
  };

  if (phase === 'predict') {
    return (
      <div className="artifact">
        {error && <p className="artifact-err">{error}</p>}
        <PredictionLock onLock={lock} />
      </div>
    );
  }

  return (
    <div className="artifact">
      <div className="artifact-locked">
        {/* ⭐ Text, not a disabled input. A greyed-out field invites a hunt for
            the edit button; text says the decision is made. */}
        <div className="row"><span className="k">Predict</span>
          <span className="v">{locked!.low} – {locked!.high} {locked!.unit}
            <em> 🔒 locked {locked!.at}</em></span></div>
      </div>

      {/* ⭐ F8's payout, at the moment the cost is paid. Calibration used to be
          invisible for weeks, so the student gave something up now and got
          nothing back until much later. A streak you are already inside is a
          reason to finish the next one. */}
      {calibration && calibration.resolved > 0 && (
        <p className="artifact-streak">
          Your last {calibration.resolved}: <b>{calibration.matched} matched</b>.
          {" "}This is #{calibration.resolved + 1}.
        </p>
      )}

      {/* ⚠️ Optional, and AFTER the commitment. `because` is the highest-value
          free text in the product and the fastest thing to abandon under
          friction — so it must never stand between the student and the lock. */}
      {phase === 'built' && !detailSaved && (
        <div className="artifact-detail">
          <label>
            <span>because <em>optional</em></span>
            <textarea rows={2} value={because} onChange={(e) => setBecause(e.target.value)}
              placeholder="2 cm spacing, dry electrodes" />
          </label>
          <div className="artifact-detail-a">
            <button className="ghost" onClick={() => setDetailSaved(true)}>Skip</button>
            <button onClick={() => setDetailSaved(true)} disabled={!because.trim()}>Save</button>
          </div>
        </div>
      )}
      {detailSaved && because && (
        <div className="artifact-locked">
          <div className="row"><span className="k">Because</span>
            <span className="v sm">{because}</span></div>
        </div>
      )}

      {phase === 'built' ? (
        <div className="artifact-measure">
          <label>
            What happened?
            <input autoFocus value={measured} onChange={(e) => setMeasured(e.target.value)}
              placeholder="47.2" inputMode="decimal" />
            <span className="unit">{locked!.unit}</span>
          </label>
          <button className="pri" onClick={measure}>Record the result</button>
          {/* Inconclusive is a real outcome, not a failure to answer. */}
          <button className="ghost" onClick={() => { setMeasured(''); measure(); }}>
            Couldn't measure it
          </button>
        </div>
      ) : (
        <div className={`artifact-verdict v-${verdict}`}>
          <strong>
            {verdict === 'matched' ? '✓ MATCHED' : verdict === 'diverged' ? '✗ DIVERGED' : '? INCONCLUSIVE'}
          </strong>
          <span>
            {verdict === 'matched' ? 'Your predicted range contained the result.'
              : verdict === 'diverged' ? 'Outside your range — that is the interesting one.'
              : 'Recorded as inconclusive, which is still a result.'}
          </span>
        </div>
      )}
      {error && <p className="artifact-err">{error}</p>}
    </div>
  );
}

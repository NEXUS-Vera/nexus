/**
 * The first sixty seconds. Frontend/01 §8.
 *
 * ⭐ The graph is never empty, because it starts as a structured question. An
 * empty graph is worse than no graph — it makes the product look broken at
 * exactly the moment a student decides whether to continue.
 */
import { useState } from 'react';

import { api, ApiError } from '../lib/api';
import './Onboarding.css';

/** ⭐ "How will you know it worked?" is the single most useful question anyone
 *  can ask an undergraduate, and it fixes the cold start as a side effect: a
 *  vague question produces a generic decomposition and a useless graph. */
const MEASURABLE = /(\d|measure|accuracy|within|percent|%|hz|khz|mhz|ohm|volt|amp|second|ms|error|threshold|detect|track|compare|distinguish)/i;

interface Seeded {
  subquestions: number;
  concepts: number;
  skeleton_matched: boolean;
  vague: boolean;
}

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState(1);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [seeded, setSeeded] = useState<Seeded | null>(null);
  const [error, setError] = useState<string | null>(null);

  const vague = q.trim().length > 0 && !MEASURABLE.test(q);

  const seed = async () => {
    setBusy(true); setError(null);
    try {
      const res = (await api.start(q)) as unknown as Seeded;
      setSeeded(res);
      setStep(3);
    } catch (e) {
      setError(e instanceof ApiError && e.isRefusal
        ? 'Only the signed-in human can start a project — that is not an agent decision.'
        : 'No backend. Start scripts/serve_demo.py, or continue without seeding.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="onb">
      <div className="onb-card">
        <div className="onb-step">New project · step {step} of 3</div>
        <h2>
          {step === 1 ? 'What are you trying to find out?'
            : step === 2 ? 'How will you know it worked?'
            : 'Your graph, a few seconds later'}
        </h2>

        {step < 3 ? (
          <>
            <input autoFocus className="onb-in" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Can skin impedance track hydration to within 10%?"
              onKeyDown={(e) => { if (e.key === 'Enter' && q.trim()) { if (step === 1) setStep(2); else void seed(); } }} />
            {step === 2 && vague && (
              <div className="onb-warn">
                <b>No measurable success criterion in that question.</b> Add one —
                “to within 10%”, “within 2 seconds”, “better than the datasheet”.
                Without it the decomposition is generic, and so is the graph.
              </div>
            )}
            {step === 2 && !vague && q.trim() && (
              <div className="onb-warn ok">
                <b>Measurable.</b> That number is what makes every prediction below testable.
              </div>
            )}
          </>
        ) : (
          <>
            <div className="onb-seed">
              <div><b>1</b><span>+ {seeded?.subquestions ?? 0} sub-questions</span></div>
              <div><b>{seeded?.concepts ?? 0}</b><span>concepts from the skeleton</span></div>
              <div><b>0</b><span>validated — that is correct</span></div>
            </div>
            {/* ⭐ The first screen shows what you do NOT know. Nothing is
                validated at t=0, and saying so plainly beats an empty progress
                bar — it sets the expectation that this is about what is left. */}
            <p className="onb-note">
              Nothing is proven yet. The first screen shows what you <b>don't</b> know —
              that is what the frontier is for.
            </p>
            {seeded && !seeded.skeleton_matched && (
              <p className="onb-note warn">
                ⚠️ Nothing matched the embedded-systems skeleton, so you get question
                decomposition only. That is a gap in our coverage, not in your project.
              </p>
            )}
          </>
        )}

        {error && <p className="onb-err">{error}</p>}

        <div className="onb-foot">
          <span className="hint">
            {step === 2 ? 'This is a nudge, never a gate — you can continue anyway.'
              : step === 3 ? 'Aim the first session at the cheapest verifiable thing nearby.'
              : 'One sentence. The graph is never empty.'}
          </span>
          {step > 1 && step < 3 && <button onClick={() => setStep(1)}>Back</button>}
          <button className="pri" disabled={busy || (step < 3 && !q.trim())}
            onClick={() => step === 1 ? setStep(2) : step === 2 ? seed() : onComplete()}>
            {busy ? 'Seeding…' : step === 3 ? 'Open the workbench'
              : step === 2 && vague ? 'Continue anyway' : 'Continue'}
          </button>
        </div>
      </div>
    </div>
  );
}

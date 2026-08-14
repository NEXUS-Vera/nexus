/**
 * The review queue. Frontend/01 §4.4, Frontend/07 §2.4.
 *
 * ⭐ It holds ONLY `AMBIGUOUS` — the cases the system genuinely cannot settle.
 * Everything the extractor was confident about is already in the graph,
 * flagged and one-click reversible. That is what turns this from an integrity
 * gate into a thinking prompt.
 *
 * ⚠️ Trained reviewer pods manage 2,000–12,000 items a day. Ours is one unpaid
 * undergraduate with a project due, so the budget is 20–30 decisions a session
 * — which makes aggressive, well-calibrated auto-accept a requirement rather
 * than an optimisation.
 */
import { useState } from 'react';

import { useDecide, useReview } from '../lib/hooks';
import { EmptyState, LoadingState } from './SurfaceStates';
import './ReviewQueue.css';

export function ReviewQueue() {
  const { data, isLoading } = useReview();
  const decide = useDecide();
  const [i, setI] = useState(0);

  const pending = data?.pending ?? [];
  const item = pending[i] as Record<string, string> | undefined;

  if (isLoading) return <LoadingState>Loading the queue…</LoadingState>;
  if (!item) {
    return (
      <EmptyState
        message="Nothing needs your judgement. Everything confident is already in the graph, reversibly."
        actionText="Ingest a source"
        onAction={() => {}}
      />
    );
  }

  const act = (accept: boolean) => {
    decide.mutate({ ids: [item.id], accept });
    setI((n) => Math.min(n, pending.length - 2));
  };

  return (
    <div className="rq" onKeyDown={(e) => {
      // Keyboard-driven: a queue you have to mouse through does not get cleared.
      if (e.key.toLowerCase() === 'a') act(true);
      if (e.key.toLowerCase() === 'r') act(false);
      if (e.key === ' ') { e.preventDefault(); setI((n) => (n + 1) % pending.length); }
    }} tabIndex={0}>
      {/* Counter, not a progress bar — finite and finishable, not a chore. */}
      <div className="rq-count">{i + 1} of {pending.length}</div>

      <div className="rq-edge">
        <code>{item.src}</code>
        <span className="rel">{item.relation}</span>
        <code>{item.dst}</code>
      </div>

      <div className="rq-conf">
        <span className={`rq-tier t-${String(item.confidence).toLowerCase()}`}>{item.confidence}</span>
        <span className="rq-score">{item.score}</span>
      </div>

      {/* ⭐ Mandatory. The queue holds only what nobody but the student can
          settle, so every card must say what the system could not decide —
          without this line it is a rubber stamp, and a rubber stamp gets
          clicked through. */}
      <p className="rq-why">
        {String(item.confidence) === 'AMBIGUOUS'
          ? 'The passage does not say which direction, so this could be read either way.'
          : 'This asserts a contradiction — cheap to check, expensive to get wrong.'}
      </p>

      <div className="rq-actions">
        <button className="pri" onClick={() => act(true)}>[A]ccept</button>
        <button onClick={() => act(false)}>[R]eject</button>
        <button className="ghost" onClick={() => setI((n) => (n + 1) % pending.length)}>[␣]skip</button>
      </div>
      <p className="rq-budget">Budget 20–30 decisions a session, not hundreds.</p>
    </div>
  );
}

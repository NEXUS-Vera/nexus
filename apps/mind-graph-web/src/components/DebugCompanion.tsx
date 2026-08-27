/**
 * The debug companion — F11 / F08_Debug_Companion_Design.md.
 *
 * ⭐ Every other surface assumes a planning posture. This one assumes the
 * opposite moment: week 3, 1am, mid-debug. `recall` and `impact` were both
 * already computed by `_companion` and silently discarded everywhere else —
 * this is the first surface that actually renders them.
 *
 * ⚠️ `bias` and `transfer` are deliberately left out. `bias` already has a
 * home on Dashboard; `transfer` is a different-project "did you know," which
 * cuts against "the one thing in front of you."
 */
import { useState } from "react";

import { ApiError } from "../lib/api";
import { useCompanion } from "../lib/hooks";
import { useUI } from "../lib/store";
import { EmptyState, ErrorState, LoadingState } from "./SurfaceStates";
import "./DebugCompanion.css";

export function DebugCompanion({ onClose }: { onClose: () => void }) {
  const ui = useUI();
  const [text, setText] = useState("");
  const [query, setQuery] = useState<string | undefined>(undefined);
  const companion = useCompanion({ id: ui.selected ?? undefined, q: query });

  const submit = () => { if (text.trim()) setQuery(text.trim()); };
  const pick = (id: string) => ui.set({ selected: id });
  // ⭐ Resets on close so reopening doesn't silently re-run a stale query
  // against whatever's newly selected.
  const close = () => { setText(""); setQuery(undefined); onClose(); };

  const impact = companion.data?.impact;
  const recall = companion.data?.recall;
  const isRefusal = companion.error instanceof ApiError && companion.error.isRefusal;

  return (
    <div className="debug-companion">
      <header className="dc-head">
        <h3>Debug companion</h3>
        <button className="dc-close" onClick={close} aria-label="Close">×</button>
      </header>

      <div className="dc-query">
        <input
          className="dc-input"
          placeholder="what are you stuck on?"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
        />
        <button className="dc-submit" onClick={submit} disabled={!text.trim()}>Ask</button>
      </div>

      {companion.isLoading && <LoadingState>Checking…</LoadingState>}

      {/* ⚠️ A 403 is not a transient failure — offering Retry against a
          capability the token will never have is a worse lie than the
          message alone. Same distinction ErrorState's own doc comment
          and App.tsx's Refusal already make. */}
      {companion.isError && isRefusal && (
        <ErrorState error={(companion.error as ApiError).message}
          stillWorks="Capabilities are checked server-side." />
      )}
      {companion.isError && !isRefusal && (
        <ErrorState
          error={companion.error instanceof ApiError ? companion.error.message : "Needs a connection."}
          onRetry={() => companion.refetch()} />
      )}

      {!companion.isLoading && !companion.isError && !ui.selected && !query && (
        <EmptyState message="Select something, or describe what you're stuck on."
          actionText="Dismiss" onAction={close} />
      )}

      {!companion.isLoading && !companion.isError && impact && (
        <section className="dc-block">
          <h4>what's riding on this</h4>
          {impact.direct.length === 0 ? (
            <p className="dc-empty">Nothing else depends on this yet.</p>
          ) : (
            <ul className="dc-list">
              {impact.direct.map((id) => (
                <li key={id}><button onClick={() => pick(id)}>{id}</button></li>
              ))}
            </ul>
          )}
          {impact.load_bearing && (
            <p className="dc-warn">⚠ {impact.unsupported_after.length} thing(s) would lose their footing.</p>
          )}
        </section>
      )}

      {query && !companion.isLoading && !companion.isError && (
        <section className="dc-block">
          <h4>you've hit this shape of problem before</h4>
          {recall && recall.length > 0 ? (
            <ul className="dc-list">
              {recall.map((r) => (
                <li key={r.id} className={`dc-recall dc-recall--${r.kind}`}>
                  <button onClick={() => pick(r.id)}>
                    <span className="dc-recall-label">{r.label}</span>
                    <span className="dc-recall-kind">
                      {r.kind === "dead_end" ? "dead end" : "unsupported"}
                    </span>
                    {r.reason && <span className="dc-recall-reason">{r.reason}</span>}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="dc-empty">Nothing matched.</p>
          )}
        </section>
      )}
    </div>
  );
}

import './SurfaceStates.css';

interface BaseStateProps {
  children?: React.ReactNode;
}

export function EmptyState({ message, actionText, onAction }: { message: string, actionText: string, onAction: () => void }) {
  return (
    <div className="surface-state state-empty">
      <p>{message}</p>
      <button onClick={onAction}>{actionText}</button>
    </div>
  );
}

export function LoadingState({ children }: BaseStateProps) {
  return (
    <div className="surface-state state-loading">
      <div className="skeleton-overlay"></div>
      {children}
    </div>
  );
}

export function PartialState({ children, missingCount }: { children: React.ReactNode, missingCount?: number }) {
  return (
    <div className="surface-state state-partial">
      {children}
      <div className="partial-badge">
        Partial result {missingCount ? `(${missingCount} missing)` : ''}
      </div>
    </div>
  );
}

/**
 * `F07 §1`: say what failed, what still works, and what to do.
 *
 * ⚠️ `onRetry` is optional, and that is the important part. A capability
 * refusal is not a transient failure — offering "Retry" against a 403 sends
 * the reader in a loop against a rule that will never change, which is a
 * worse lie than saying nothing.
 */
export function ErrorState({ error, onRetry, stillWorks }: {
  error: string; onRetry?: () => void; stillWorks?: string;
}) {
  return (
    <div className="surface-state state-error">
      <p className="error-message">{error}</p>
      {stillWorks && <p className="error-still">{stillWorks}</p>}
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function StaleState({ children, age, onRefresh }: { children: React.ReactNode, age: string, onRefresh: () => void }) {
  return (
    <div className="surface-state state-stale">
      {children}
      <div className="stale-banner">
        <span>Computed {age} ago</span>
        <button onClick={onRefresh}>Refresh</button>
      </div>
    </div>
  );
}

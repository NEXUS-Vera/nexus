import { Component, type ErrorInfo, type ReactNode } from 'react';
import { themeColors } from '../../lib/theme';

type Props = {
  isDark: boolean;
  children: ReactNode;
  onRetry?: () => void;
};

type State = {
  error: Error | null;
};

/**
 * Keeps the project shell (rail / Vera) mounted when Architecture rendering fails.
 * Logs the error; does not silently swallow programmer/schema failures.
 */
export class ArchitectureErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error('Architecture workspace render failed', error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children;
    const t = themeColors(this.props.isDark);
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          background: t.bg,
        }}
        data-testid="architecture-error-boundary"
        role="alert"
      >
        <div
          style={{
            maxWidth: 480,
            padding: 20,
            borderRadius: 8,
            border: `1px solid ${t.border}`,
            background: t.surface,
          }}
        >
          <h3 style={{ margin: 0, color: t.text }}>Architecture workspace failed to render</h3>
          <p style={{ margin: '8px 0 0', fontSize: 13, color: t.textSec }}>
            {this.state.error.message || 'An unexpected rendering error occurred.'}
          </p>
          <p style={{ margin: '8px 0 0', fontSize: 12, color: t.textMuted }}>
            The project rail and Vera sidecar remain available. Retry after regenerating layered
            architecture or switching views.
          </p>
          <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
            <button
              type="button"
              data-testid="architecture-error-retry"
              style={{
                fontSize: 12,
                padding: '6px 12px',
                borderRadius: 6,
                border: `1px solid ${t.border}`,
                background: t.cobalt,
                color: '#fff',
                cursor: 'pointer',
              }}
              onClick={() => {
                this.setState({ error: null });
                this.props.onRetry?.();
              }}
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }
}

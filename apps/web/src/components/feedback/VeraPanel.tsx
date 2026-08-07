import type { FormEvent } from 'react';
import type { OpenQuestion, ProjectHistory } from '@nexus/contracts';
import { themeColors } from '../../lib/theme';

export type VeraContextChip = {
  label: string;
  kind?: string;
};

export type VeraThreadItem = {
  id: string;
  role: 'user' | 'vera';
  text: string;
  timestamp?: string;
};

type VeraPanelProps = {
  message: string;
  onMessageChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  submitting: boolean;
  veraMessage: string;
  error: string | null;
  openQuestions: OpenQuestion[];
  isDark: boolean;
  /** Sidecar layout: fill height with sticky composer. */
  compact?: boolean;
  contextChips?: VeraContextChip[];
  thread?: VeraThreadItem[];
  history?: ProjectHistory | null;
};

function buildThreadFromHistory(
  history: ProjectHistory | null | undefined,
  veraMessage: string,
): VeraThreadItem[] {
  const items: VeraThreadItem[] = [];
  for (const turn of history?.turns ?? []) {
    items.push({
      id: `turn-${turn.turnId}`,
      role: 'user',
      text: turn.rawUserMessage,
      timestamp: turn.timestamp,
    });
  }
  for (const response of history?.veraResponses ?? []) {
    items.push({
      id: `vera-${response.turnId}-${response.timestamp}`,
      role: 'vera',
      text: response.userFacingMessage,
      timestamp: response.timestamp,
    });
  }
  items.sort((a, b) => String(a.timestamp ?? '').localeCompare(String(b.timestamp ?? '')));
  if (
    veraMessage &&
    !items.some((item) => item.role === 'vera' && item.text === veraMessage)
  ) {
    items.push({
      id: 'vera-current',
      role: 'vera',
      text: veraMessage,
    });
  }
  return items;
}

export function VeraPanel({
  message,
  onMessageChange,
  onSubmit,
  submitting,
  veraMessage,
  error,
  openQuestions,
  isDark,
  compact = false,
  contextChips = [],
  thread,
  history = null,
}: VeraPanelProps) {
  const t = themeColors(isDark);
  const threadItems = thread ?? buildThreadFromHistory(history, veraMessage);

  return (
    <section
      aria-label="Vera conversation"
      data-testid="vera-panel"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: compact ? '100%' : undefined,
        minHeight: 0,
        background: t.surface,
        flex: compact ? 1 : undefined,
        overflow: 'hidden',
        ...(compact
          ? {}
          : {
              borderTop: `1px solid ${t.border}`,
              padding: '10px 16px 12px',
              flexShrink: 0,
            }),
      }}
    >
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: 'auto',
          padding: compact ? '12px 14px' : 0,
          display: 'grid',
          gap: 10,
          alignContent: 'start',
          marginBottom: compact ? 0 : 10,
          maxHeight: compact ? undefined : 160,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: 13, color: t.text }}>Vera</h2>
          <span aria-live="polite" style={{ fontSize: 12, color: t.textMuted }}>
            {submitting ? 'Updating project…' : ''}
          </span>
        </div>

        {contextChips.length ? (
          <div
            data-testid="vera-context-chips"
            style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}
          >
            {contextChips.map((chip) => (
              <span
                key={`${chip.kind ?? 'ctx'}-${chip.label}`}
                style={{
                  border: `1px solid ${t.border}`,
                  background: t.surface2,
                  borderRadius: 999,
                  padding: '3px 8px',
                  fontSize: 11,
                  color: t.textSec,
                }}
              >
                {chip.label}
              </span>
            ))}
          </div>
        ) : null}

        <div data-testid="vera-thread" style={{ display: 'grid', gap: 8 }}>
          {threadItems.length ? (
            threadItems.map((item) => (
              <div
                key={item.id}
                style={{
                  border: `1px solid ${t.border}`,
                  borderRadius: 8,
                  padding: 8,
                  background: item.role === 'user' ? t.bg : t.surface2,
                }}
              >
                <div style={{ fontSize: 10, color: t.textMuted, marginBottom: 4 }}>
                  {item.role === 'user' ? 'You' : 'Vera'}
                </div>
                <p style={{ margin: 0, fontSize: 12, color: t.text, lineHeight: 1.45 }}>
                  {item.text}
                </p>
              </div>
            ))
          ) : (
            <div
              data-testid="vera-message"
              style={{
                border: `1px solid ${t.border}`,
                borderRadius: 8,
                padding: 10,
                background: t.bg,
              }}
            >
              <p style={{ margin: 0, fontSize: 13, color: t.textSec, lineHeight: 1.45 }}>
                {veraMessage || 'Ask Vera about the active artifact or selection.'}
              </p>
            </div>
          )}
        </div>

        {openQuestions.length ? (
          <div
            data-testid="vera-open-questions"
            style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}
          >
            {openQuestions.map((question) => (
              <button
                key={question.questionId}
                type="button"
                className="chip"
                disabled={submitting}
                onClick={() => onMessageChange(question.question)}
                style={{
                  border: `1px solid ${t.border}`,
                  background: t.surface2,
                  borderRadius: 999,
                  padding: '3px 8px',
                  fontSize: 11,
                  cursor: 'pointer',
                  color: t.textSec,
                }}
              >
                Use question
              </button>
            ))}
          </div>
        ) : null}

        {error ? (
          <div
            id="vera-turn-error"
            role="alert"
            data-testid="vera-error"
            style={{
              border: '1px solid #F0B4B4',
              background: isDark ? '#3a1f1f' : '#FFF5F5',
              borderRadius: 8,
              padding: 10,
              color: '#D14343',
              fontSize: 12,
            }}
          >
            {error}
          </div>
        ) : null}
      </div>

      <form
        onSubmit={onSubmit}
        style={{
          display: 'grid',
          gap: 8,
          padding: compact ? '10px 14px 14px' : 0,
          borderTop: compact ? `1px solid ${t.border}` : undefined,
          background: t.surface,
          flexShrink: 0,
          position: compact ? 'sticky' : undefined,
          bottom: compact ? 0 : undefined,
        }}
      >
        <label htmlFor="vera-turn" style={{ fontSize: 12, color: t.textMuted }}>
          Continue the conversation
        </label>
        <textarea
          id="vera-turn"
          rows={compact ? 3 : 2}
          value={message}
          disabled={submitting}
          onChange={(event) => onMessageChange(event.target.value)}
          placeholder="It should run for at least six months on battery power."
          aria-invalid={Boolean(error)}
          aria-describedby={error ? 'vera-turn-error' : undefined}
          style={{
            width: '100%',
            resize: 'vertical',
            maxHeight: 160,
            padding: 10,
            borderRadius: 8,
            border: `1px solid ${error ? '#D14343' : t.border}`,
            background: t.bg,
            color: t.text,
            font: 'inherit',
          }}
        />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button
            type="submit"
            disabled={submitting || !message.trim()}
            style={{
              border: 'none',
              borderRadius: 8,
              padding: '8px 14px',
              background: t.cobalt,
              color: '#fff',
              fontWeight: 600,
              fontSize: 13,
              cursor: submitting || !message.trim() ? 'not-allowed' : 'pointer',
              opacity: submitting || !message.trim() ? 0.6 : 1,
            }}
          >
            {submitting ? 'Updating…' : 'Send to Vera'}
          </button>
        </div>
      </form>
    </section>
  );
}

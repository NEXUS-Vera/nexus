import type { FormEvent } from 'react';
import type { OpenQuestion } from '@nexus/contracts';
import { themeColors } from '../../lib/theme';

type VeraPanelProps = {
  message: string;
  onMessageChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  submitting: boolean;
  veraMessage: string;
  error: string | null;
  openQuestions: OpenQuestion[];
  isDark: boolean;
};

export function VeraPanel({
  message,
  onMessageChange,
  onSubmit,
  submitting,
  veraMessage,
  error,
  openQuestions,
  isDark,
}: VeraPanelProps) {
  const t = themeColors(isDark);
  return (
    <section
      aria-label="Vera conversation"
      style={{
        borderTop: `1px solid ${t.border}`,
        background: t.surface,
        padding: '10px 16px 12px',
        flexShrink: 0,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 13, color: t.text }}>Vera</h2>
        <span aria-live="polite" style={{ fontSize: 12, color: t.textMuted }}>
          {submitting ? 'Updating project…' : ''}
        </span>
      </div>
      <p style={{ margin: '0 0 10px', fontSize: 13, color: t.textSec }}>{veraMessage}</p>
      {openQuestions.length ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
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
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 8 }}>
        <label htmlFor="vera-turn" style={{ fontSize: 12, color: t.textMuted }}>
          Continue the conversation
        </label>
        <textarea
          id="vera-turn"
          rows={2}
          value={message}
          disabled={submitting}
          onChange={(event) => onMessageChange(event.target.value)}
          placeholder="It should run for at least six months on battery power."
          aria-invalid={Boolean(error)}
          aria-describedby={error ? 'vera-turn-error' : undefined}
          style={{
            width: '100%',
            resize: 'vertical',
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
          {error ? (
            <p id="vera-turn-error" role="alert" style={{ margin: 0, color: '#D14343', fontSize: 12 }}>
              {error}
            </p>
          ) : null}
        </div>
      </form>
    </section>
  );
}

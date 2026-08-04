import { themeColors } from '../../lib/theme';

type PlaceholderWorkspaceProps = {
  title: string;
  body: string;
  prerequisites: string[];
  nextActionTitle?: string;
  isDark: boolean;
  shellHint?: string;
};

export function PlaceholderWorkspace({
  title,
  body,
  prerequisites,
  nextActionTitle,
  isDark,
  shellHint,
}: PlaceholderWorkspaceProps) {
  const t = themeColors(isDark);
  return (
    <div
      style={{
        flex: 1,
        overflow: 'auto',
        padding: 24,
        background: t.bg,
      }}
      data-testid="artifact-placeholder"
    >
      <div
        style={{
          maxWidth: 640,
          margin: '40px auto',
          padding: 24,
          borderRadius: 8,
          border: `1px dashed ${t.border}`,
          background: t.surface,
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.08em',
            color: t.textMuted,
            textTransform: 'uppercase',
          }}
        >
          Placeholder workspace
        </p>
        <h2 style={{ margin: '8px 0 0', fontSize: 18, color: t.text }}>{title}</h2>
        <p style={{ margin: '10px 0 0', fontSize: 13, color: t.textSec, lineHeight: 1.5 }}>{body}</p>
        {prerequisites.length ? (
          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Prerequisites</h3>
            <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: t.text, fontSize: 13 }}>
              {prerequisites.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {nextActionTitle ? (
          <p style={{ margin: '16px 0 0', fontSize: 13, color: t.cobalt }}>
            Current next action: {nextActionTitle}
          </p>
        ) : null}
        {shellHint ? (
          <p style={{ margin: '16px 0 0', fontSize: 12, color: t.textMuted }}>{shellHint}</p>
        ) : null}
      </div>
    </div>
  );
}

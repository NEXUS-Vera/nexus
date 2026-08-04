import type { ReactNode } from 'react';
import type { Artifact } from '@nexus/contracts';
import { themeColors } from '../../lib/theme';
import type { InspectorSelection } from '../../lib/inspector-selection';

type Props = {
  artifact: Extract<Artifact, { artifactType: 'project-brief' }>;
  isDark: boolean;
  onSelectItem: (selection: InspectorSelection) => void;
};

export function ProjectBriefWorkspace({ artifact, isDark, onSelectItem }: Props) {
  const t = themeColors(isDark);
  const content = artifact.content;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }} data-testid="workspace-project-brief">
      <div style={{ flex: 1, overflow: 'auto', padding: 16, background: t.bg, display: 'grid', gap: 12 }}>
        {[
          { id: 'goal', label: 'Goal', value: content.goal },
          { id: 'problem', label: 'Problem statement', value: content.problemStatement },
          { id: 'context', label: 'Intended context', value: content.intendedContext },
          { id: 'stage', label: 'Project stage', value: content.projectStage },
        ].map((field) => (
          <button
            key={field.id}
            type="button"
            onClick={() =>
              onSelectItem({ kind: 'project-brief-item', id: field.id, label: field.label })
            }
            style={{
              textAlign: 'left',
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: 14,
              background: t.surface,
              cursor: 'pointer',
            }}
          >
            <div style={{ fontSize: 11, color: t.textMuted, marginBottom: 4 }}>{field.label}</div>
            <div style={{ fontSize: 13, color: t.text }}>{field.value}</div>
          </button>
        ))}

        <Section title="Scope" isDark={isDark}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {content.scope.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Section>
        <Section title="Out of scope" isDark={isDark}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {content.outOfScope.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Section>
        <Section title="Success criteria" isDark={isDark}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {content.successCriteria.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Section>
        <Section title="Assumptions" isDark={isDark}>
          <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 8 }}>
            {content.assumptions.map((item) => (
              <li key={item.assumptionId}>
                <button
                  type="button"
                  onClick={() =>
                    onSelectItem({
                      kind: 'project-brief-item',
                      id: item.assumptionId,
                      label: 'Assumption',
                    })
                  }
                  style={{
                    border: 'none',
                    background: 'transparent',
                    padding: 0,
                    cursor: 'pointer',
                    color: t.text,
                    textAlign: 'left',
                    fontSize: 13,
                  }}
                >
                  {item.statement}{' '}
                  <span style={{ color: t.textMuted }}>
                    ({item.confirmationStatus}, {item.sourceType})
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Section>
        <Section title="Unknowns" isDark={isDark}>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {content.unknowns.map((item) => (
              <li key={item.questionId}>
                <button
                  type="button"
                  onClick={() => onSelectItem({ kind: 'open-question', id: item.questionId })}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    padding: 0,
                    cursor: 'pointer',
                    color: t.cobalt,
                    fontSize: 13,
                  }}
                >
                  {item.displayId ?? item.questionId}
                </button>
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
  isDark,
}: {
  title: string;
  children: ReactNode;
  isDark: boolean;
}) {
  const t = themeColors(isDark);
  return (
    <section
      style={{
        border: `1px solid ${t.border}`,
        borderRadius: 8,
        padding: 14,
        background: t.surface,
        color: t.text,
        fontSize: 13,
      }}
    >
      <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>{title}</h3>
      {children}
    </section>
  );
}

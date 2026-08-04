import type { Artifact } from '@nexus/contracts';
import { WorkspaceHeader } from '../../components/layout/WorkspaceHeader';
import { StatusBadge } from '../../components/statuses/StatusBadge';
import { themeColors } from '../../lib/theme';

type Props = {
  artifact: Extract<Artifact, { artifactType: 'next-action' }>;
  changeIndicator?: string;
  isDark: boolean;
};

export function NextActionWorkspace({ artifact, changeIndicator, isDark }: Props) {
  const t = themeColors(isDark);
  const content = artifact.content;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }} data-testid="workspace-next-action">
      <WorkspaceHeader
        title="Next Action"
        subtitle="Global recommended action for this project"
        version={artifact.artifactVersion}
        lifecycleStatus={artifact.lifecycleStatus}
        evidenceStatus={artifact.evidenceStatus}
        approvalStatus={artifact.approvalStatus}
        changeIndicator={changeIndicator}
        isDark={isDark}
      />
      <div style={{ flex: 1, overflow: 'auto', padding: 20, background: t.bg }}>
        <article
          style={{
            maxWidth: 720,
            margin: '0 auto',
            padding: 20,
            borderRadius: 8,
            border: `1px solid ${t.border}`,
            borderLeft: `4px solid ${t.cobalt}`,
            background: t.surface,
            display: 'grid',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <h3 style={{ margin: 0, color: t.text }}>{content.title}</h3>
            <StatusBadge status={content.priority} />
          </div>
          <p style={{ margin: 0, color: t.text, fontSize: 14 }}>{content.description}</p>
          <p style={{ margin: 0, color: t.textSec, fontSize: 13 }}>
            <strong>Rationale:</strong> {content.rationale}
          </p>
          <p style={{ margin: 0, color: t.textMuted, fontSize: 12 }}>
            Owner: {content.owner} · Priority: {content.priority}
          </p>
          <p style={{ margin: 0, fontSize: 13, color: t.text }}>
            Prerequisites: {content.prerequisites.length}. Blockers: {content.blocks.length}. Source
            questions: {content.sourceQuestionIds.length}. Source issues:{' '}
            {content.sourceIssueIds.length}.
          </p>
          <p style={{ margin: 0, fontSize: 13, color: t.text }}>
            <strong>Completion:</strong> {content.completionCondition.completionCriteria}
          </p>
        </article>
      </div>
    </div>
  );
}

import type { ReactNode } from 'react';
import type { Artifact, OpenQuestion, ProjectCurrentState, ValidationIssue } from '@nexus/contracts';
import { selectArtifactByType } from '../../artifacts';
import type { ArtifactRouteKey } from '../../artifacts/types';
import type { InspectorSelection } from '../../lib/inspector-selection';
import { themeColors } from '../../lib/theme';
import { EvidenceBadge } from '../statuses/EvidenceBadge';
import { StatusBadge } from '../statuses/StatusBadge';

type ContextInspectorProps = {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  isDark: boolean;
  activeArtifact: ArtifactRouteKey;
  selection: InspectorSelection;
  state: ProjectCurrentState;
  changedArtifactTypes: string[];
  regeneratedArtifactTypes: string[];
  onFocusVera: () => void;
};

function findRequirement(artifacts: Artifact[], id: string) {
  const set = selectArtifactByType(artifacts, 'requirement-set');
  return set?.content.requirements.find((r) => r.requirementId === id || r.displayId === id);
}

function findNode(artifacts: Artifact[], id: string) {
  const arch = selectArtifactByType(artifacts, 'functional-architecture');
  return arch?.content.nodes.find((n) => n.nodeId === id);
}

function findQuestion(questions: OpenQuestion[] | undefined, id: string) {
  return questions?.find((q) => q.questionId === id);
}

function findIssue(issues: ValidationIssue[] | undefined, id: string) {
  return issues?.find((i) => i.issueId === id);
}

export function ContextInspector({
  collapsed,
  onCollapsedChange,
  isDark,
  activeArtifact,
  selection,
  state,
  changedArtifactTypes,
  regeneratedArtifactTypes,
  onFocusVera,
}: ContextInspectorProps) {
  const t = themeColors(isDark);

  if (collapsed) {
    return (
      <aside
        aria-label="Context inspector"
        style={{
          height: '100%',
          borderLeft: `1px solid ${t.border}`,
          background: t.surface,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingTop: 8,
        }}
      >
        <button
          type="button"
          aria-label="Expand context inspector"
          onClick={() => onCollapsedChange(false)}
          style={{
            width: 36,
            height: 36,
            borderRadius: 8,
            border: `1px solid ${t.border}`,
            background: 'transparent',
            cursor: 'pointer',
            color: t.textSec,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <span aria-hidden>‹</span>
        </button>
      </aside>
    );
  }

  let title = 'No selection';
  let body: ReactNode = (
    <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
      Select a requirement, architecture node, open question, or revision to inspect it here.
    </p>
  );

  if (selection.kind === 'requirement') {
    const req = findRequirement(state.artifacts, selection.id);
    if (req) {
      title = req.displayId;
      body = (
        <div style={{ display: 'grid', gap: 10 }}>
          <p style={{ margin: 0, fontSize: 13, color: t.text }}>{req.statement}</p>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <StatusBadge status={req.confirmationStatus} />
            <span style={{ fontSize: 11, color: t.textMuted }}>{req.category}</span>
            <span style={{ fontSize: 11, color: t.textMuted }}>{req.priority}</span>
            <span style={{ fontSize: 11, color: t.textMuted }}>confidence {req.confidence}</span>
          </div>
          <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
            Verification: {req.verificationMethod}
          </p>
          {req.targetQuantity ? (
            <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
              Target: {req.targetQuantity.value} {req.targetQuantity.unit}
            </p>
          ) : null}
          {req.acceptanceCriteria?.length ? (
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
              {req.acceptanceCriteria.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          ) : null}
        </div>
      );
    }
  } else if (selection.kind === 'architecture-node') {
    const node = findNode(state.artifacts, selection.id);
    if (node) {
      title = node.name;
      body = (
        <div style={{ display: 'grid', gap: 10 }}>
          <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>{node.functionalType}</p>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: t.text }}>
            {node.responsibilities.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
            Satisfies: {node.satisfiesRequirementIds.join(', ')}
          </p>
        </div>
      );
    }
  } else if (selection.kind === 'open-question') {
    const q = findQuestion(state.openQuestions, selection.id);
    if (q) {
      title = q.questionId;
      body = (
        <div style={{ display: 'grid', gap: 8 }}>
          <p style={{ margin: 0, fontSize: 13, color: t.text }}>{q.question}</p>
          <StatusBadge status={q.status} />
          <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>Reason: {q.reason}</p>
        </div>
      );
    }
  } else if (selection.kind === 'validation-issue') {
    const issue = findIssue(state.validationIssues, selection.id);
    if (issue) {
      title = issue.issueId;
      body = (
        <div style={{ display: 'grid', gap: 8 }}>
          <p style={{ margin: 0, fontSize: 13, color: t.text }}>{issue.message}</p>
          <StatusBadge status={issue.severity} />
          <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
            {issue.code}
            {issue.blocking ? ' · blocking' : ''}
          </p>
        </div>
      );
    }
  } else if (selection.kind === 'next-action') {
    const next = selectArtifactByType(state.artifacts, 'next-action');
    if (next) {
      title = next.content.title;
      body = (
        <div style={{ display: 'grid', gap: 8 }}>
          <p style={{ margin: 0, fontSize: 13, color: t.text }}>{next.content.description}</p>
          <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>{next.content.rationale}</p>
          <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
            Owner {next.content.owner} · Priority {next.content.priority}
          </p>
          <p style={{ margin: 0, fontSize: 12, color: t.text }}>
            Completion: {next.content.completionCondition.completionCriteria}
          </p>
        </div>
      );
    }
  } else if (selection.kind === 'artifact-revision') {
    title = `${selection.artifactType} v${selection.version}`;
    body = (
      <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
        Historical revision (read-only). Open History for turn context.
      </p>
    );
  } else if (selection.kind === 'project-brief-item') {
    title = selection.label ?? selection.id;
    body = (
      <p style={{ margin: 0, fontSize: 13, color: t.text }}>
        Selected from Project Brief. Request changes through Vera rather than editing inline.
      </p>
    );
  }

  const activeLive = state.artifacts.find((a) => {
    if (activeArtifact === 'project-brief') return a.artifactType === 'project-brief';
    if (activeArtifact === 'requirement-set') return a.artifactType === 'requirement-set';
    if (activeArtifact === 'functional-architecture') {
      return a.artifactType === 'functional-architecture';
    }
    return false;
  });

  return (
    <aside
      aria-label="Context inspector"
      data-testid="context-inspector"
      style={{
        height: '100%',
        borderLeft: `1px solid ${t.border}`,
        background: t.surface,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          borderBottom: `1px solid ${t.border}`,
        }}
      >
        <strong style={{ fontSize: 13, color: t.text }}>Context</strong>
        <button
          type="button"
          aria-label="Collapse context inspector"
          onClick={() => onCollapsedChange(true)}
          style={{
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            color: t.textMuted,
          }}
        >
          ›
        </button>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 12, display: 'grid', gap: 16, alignContent: 'start' }}>
        <section>
          <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>Inspect</h3>
          <h4 style={{ margin: '0 0 8px', fontSize: 14, color: t.text }}>{title}</h4>
          {body}
        </section>

        <section>
          <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>Evidence</h3>
          {activeLive ? (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <EvidenceBadge status={activeLive.evidenceStatus} />
              <StatusBadge status={activeLive.lifecycleStatus} />
              <StatusBadge status={activeLive.approvalStatus} />
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
              No live evidence for this placeholder artifact.
            </p>
          )}
        </section>

        <section>
          <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>Changes</h3>
          {changedArtifactTypes.length || regeneratedArtifactTypes.length ? (
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
              {changedArtifactTypes.map((type) => (
                <li key={`c-${type}`}>Changed: {type}</li>
              ))}
              {regeneratedArtifactTypes.map((type) => (
                <li key={`r-${type}`}>Regenerated: {type}</li>
              ))}
            </ul>
          ) : (
            <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
              No turn impact markers yet. Submit a Vera update to see changed artifacts.
            </p>
          )}
        </section>

        <section>
          <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>Actions</h3>
          <button
            type="button"
            onClick={onFocusVera}
            style={{
              width: '100%',
              padding: '8px 10px',
              borderRadius: 6,
              border: `1px solid ${t.border}`,
              background: t.cobaltTint,
              color: t.cobalt,
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Request change via Vera
          </button>
        </section>
      </div>
    </aside>
  );
}

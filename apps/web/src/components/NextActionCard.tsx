import type { Artifact } from '@nexus/contracts';
import { StatusDimensions } from './StatusDimensions';

type Props = {
  artifact: Extract<Artifact, { artifactType: 'next-action' }>;
};

export function NextActionCard({ artifact }: Props) {
  const content = artifact.content;
  return (
    <section className="artifact-card next-action-card" aria-labelledby="next-action-heading">
      <header>
        <h2 id="next-action-heading">Next Action</h2>
        <StatusDimensions
          lifecycleStatus={artifact.lifecycleStatus}
          evidenceStatus={artifact.evidenceStatus}
          approvalStatus={artifact.approvalStatus}
        />
      </header>
      <h3>{content.title}</h3>
      <p>{content.description}</p>
      <p>
        <strong>Rationale:</strong> {content.rationale}
      </p>
      <p className="muted">
        Owner: {content.owner} · Priority: {content.priority}
      </p>
      <p>
        Prerequisites: {content.prerequisites.length}. Blockers: {content.blocks.length}.
        Linked questions: {content.sourceQuestionIds.length}. Linked issues:{' '}
        {content.sourceIssueIds.length}.
      </p>
      <p className="completion">
        <strong>Completion:</strong> {content.completionCondition.completionCriteria}
      </p>
    </section>
  );
}

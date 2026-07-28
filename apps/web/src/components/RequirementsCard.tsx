import type { Artifact } from '@nexus/contracts';
import { StatusDimensions } from './StatusDimensions';

type Props = {
  artifact: Extract<Artifact, { artifactType: 'requirement-set' }>;
};

export function RequirementsCard({ artifact }: Props) {
  const { requirements, requirementSummary } = artifact.content;
  const byStatus = requirements.reduce<Record<string, number>>((acc, req) => {
    acc[req.confirmationStatus] = (acc[req.confirmationStatus] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <section className="artifact-card" aria-labelledby="requirements-heading">
      <header>
        <h2 id="requirements-heading">Requirements</h2>
        <StatusDimensions
          lifecycleStatus={artifact.lifecycleStatus}
          evidenceStatus={artifact.evidenceStatus}
          approvalStatus={artifact.approvalStatus}
        />
      </header>
      <p>
        Total: {requirements.length}. Summary: {requirementSummary}. Confirmed:{' '}
        {byStatus.confirmed ?? 0}. Proposed: {byStatus.proposed ?? 0}. Needs
        confirmation: {byStatus['needs-confirmation'] ?? 0}.
      </p>
      <ul className="requirement-list">
        {requirements.map((req) => (
          <li
            key={req.requirementId}
            className={`requirement-item status-${req.confirmationStatus}`}
          >
            <div className="requirement-meta">
              <span className="display-id">{req.displayId}</span>
              <span className="badge">{req.confirmationStatus}</span>
              <span className="muted">{req.sourceType}</span>
            </div>
            <p>{req.statement}</p>
            <p className="muted">
              {req.category} · {req.priority} · confidence {req.confidence} ·{' '}
              {req.verificationMethod}
            </p>
            {'targetQuantity' in req && req.targetQuantity != null ? (
              <p className="muted">
                Target: {String(req.targetQuantity.value)} {req.targetQuantity.unit}
              </p>
            ) : null}
            {'openQuestionReferences' in req &&
            Array.isArray(req.openQuestionReferences) &&
            req.openQuestionReferences.length > 0 ? (
              <p className="muted">
                Linked questions:{' '}
                {req.openQuestionReferences.map((q) => q.displayId).join(', ')}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

import type { Artifact } from '@nexus/contracts';
import { StatusDimensions } from './StatusDimensions';

type Props = {
  artifact: Extract<Artifact, { artifactType: 'project-brief' }>;
};

export function ProjectBriefCard({ artifact }: Props) {
  const content = artifact.content;
  return (
    <section className="artifact-card" aria-labelledby="brief-heading">
      <header>
        <h2 id="brief-heading">Project Brief</h2>
        <StatusDimensions
          lifecycleStatus={artifact.lifecycleStatus}
          evidenceStatus={artifact.evidenceStatus}
          approvalStatus={artifact.approvalStatus}
        />
      </header>
      <p>
        <strong>Goal:</strong> {content.goal}
      </p>
      <p>
        <strong>Problem:</strong> {content.problemStatement}
      </p>
      <p>
        <strong>Context:</strong> {content.intendedContext}
      </p>
      <p>
        <strong>Stage:</strong> {content.projectStage}
      </p>
      <div>
        <h3>Scope</h3>
        <ul>
          {content.scope.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div>
        <h3>Out of scope</h3>
        <ul>
          {content.outOfScope.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div>
        <h3>Success criteria</h3>
        <ul>
          {content.successCriteria.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div>
        <h3>Assumptions</h3>
        <ul>
          {content.assumptions.map((item) => (
            <li key={item.assumptionId}>
              {item.statement}{' '}
              <span className="muted">
                ({item.confirmationStatus}, {item.sourceType})
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3>Unknowns</h3>
        <ul>
          {content.unknowns.map((item) => (
            <li key={item.questionId}>{item.displayId}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

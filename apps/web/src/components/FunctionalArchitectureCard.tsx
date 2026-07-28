import type { Artifact } from '@nexus/contracts';
import { StatusDimensions } from './StatusDimensions';

type Props = {
  artifact: Extract<Artifact, { artifactType: 'functional-architecture' }>;
};

export function FunctionalArchitectureCard({ artifact }: Props) {
  const content = artifact.content;
  return (
    <section className="artifact-card" aria-labelledby="architecture-heading">
      <header>
        <h2 id="architecture-heading">Functional Architecture</h2>
        <StatusDimensions
          lifecycleStatus={artifact.lifecycleStatus}
          evidenceStatus={artifact.evidenceStatus}
          approvalStatus={artifact.approvalStatus}
        />
      </header>
      <p>
        <strong>Maturity:</strong> {content.architectureMaturity}
      </p>
      <p>
        <strong>System boundary:</strong> {content.systemBoundary}
      </p>
      <div className="arch-nodes" role="list">
        {content.nodes.map((node) => (
          <article key={node.nodeId} className="arch-node" role="listitem">
            <h3>{node.name}</h3>
            <ul>
              {node.responsibilities.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
      <div>
        <h3>Flows</h3>
        <ul>
          {content.edges.map((edge) => {
            const from = content.nodes.find((n) => n.nodeId === edge.fromNodeId)?.name ?? edge.fromNodeId;
            const to = content.nodes.find((n) => n.nodeId === edge.toNodeId)?.name ?? edge.toNodeId;
            return (
              <li key={edge.edgeId}>
                {from} → {to} ({edge.flowType}: {edge.description})
              </li>
            );
          })}
        </ul>
      </div>
      <p>
        Requirement coverage:{' '}
        {content.requirementCoverage.coveredRequirementIds.length} covered.
      </p>
      {content.unresolvedDecisions.length ? (
        <div>
          <h3>Unresolved decisions</h3>
          <ul>
            {content.unresolvedDecisions.map((item) => (
              <li key={item.questionId ?? item.displayId}>
                {item.displayId}: {item.questionId}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

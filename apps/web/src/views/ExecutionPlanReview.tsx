import { useState } from 'react';
import type { ExecutionPlanArtifact } from '../api/client';
import { themeColors } from '../lib/theme';

type Props = {
  content: ExecutionPlanArtifact['content'];
  isDark: boolean;
  disabled?: boolean;
  onAccept: () => void;
  onReject: (reason?: string) => void;
};

/** Presentation only: the caller owns revision decisions and API calls. */
export function ExecutionPlanReview({ content, isDark, onAccept, onReject, disabled = false }: Props) {
  const [reason, setReason] = useState('');
  const t = themeColors(isDark);
  const { plan, configuration } = content;
  const steps = plan?.steps ?? [];
  const requirements = plan?.requirements ?? [];
  const objectives = plan?.verificationObjectives ?? [];
  const card = { border: `1px solid ${t.border}`, borderRadius: 8, padding: 12, marginBottom: 16, background: t.surface };

  return (
    <section aria-label="Execution plan review" style={{ padding: 16, color: t.text, background: t.bg, overflow: 'auto' }}>
      <h2>Execution plan review</h2>
      <section aria-labelledby="execution-plan-steps" style={card}>
        <h3 id="execution-plan-steps">Steps</h3>
        {steps.length ? (
          <ol>
            {steps.map((step) => (
              <li key={step.stepId}>
                <strong>{step.title}</strong> · {step.stepId}
                <div>Depends on: {step.dependsOn.join(', ') || 'None'}</div>
                <div>Workspaces: {step.workspaceKeys.join(', ') || 'None'}</div>
                <div>Objectives: {step.objectiveIds.join(', ') || 'None'}</div>
                {step.requiresApproval ? <div>Requires approval</div> : null}
              </li>
            ))}
          </ol>
        ) : <p>No steps available.</p>}
      </section>
      <section aria-labelledby="execution-plan-requirements" style={{ ...card, overflowX: 'auto' }}>
        <h3 id="execution-plan-requirements">Requirements</h3>
        {requirements.length ? (
          <table>
            <thead><tr><th scope="col">Requirement</th><th scope="col">Source artifact</th><th scope="col">Verification objectives</th></tr></thead>
            <tbody>
              {requirements.map((requirement) => (
                <tr key={`${requirement.artifactId}-${requirement.entityId}`}>
                  <th scope="row">{requirement.entityId}</th>
                  <td>{requirement.artifactId}</td>
                  <td>{objectives.some((objective) => objective.requirementId === requirement.entityId) ? objectives.filter((objective) => objective.requirementId === requirement.entityId).map((objective) => (
                    <div key={objective.objectiveId}>{objective.objectiveId} · {objective.method} · {objective.workspaceKey}: {objective.acceptanceCriteria.join('; ')}</div>
                  )) : 'No verification objectives.'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p>No requirements available.</p>}
      </section>
      <section aria-labelledby="execution-plan-pinout" style={card}>
        <h3 id="execution-plan-pinout">Pinout</h3>
        {configuration ? (
          <>
            <p>Components: {(configuration.components ?? []).map((component) => `${component.componentRoleId}: ${component.candidateId}`).join(', ')}</p>
            {configuration.i2c ? <p>{configuration.i2c.connectionId} · SDA: GPIO {configuration.i2c.sdaPin} · SCL: GPIO {configuration.i2c.sclPin}</p> : <p>No I²C pinout available.</p>}
            <p>Build: {configuration.buildProfileId} · Analysis: {configuration.analysisProfileId}</p>
          </>
        ) : <p>No pinout available.</p>}
      </section>
      <label htmlFor="plan-rejection-reason">Rejection reason (optional)</label>
      <textarea id="plan-rejection-reason" value={reason} disabled={disabled} onChange={(event) => setReason(event.target.value)} />
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" disabled={disabled} onClick={() => onAccept()}>Accept plan</button>
        <button type="button" disabled={disabled} onClick={() => reason.trim() ? onReject(reason.trim()) : onReject()}>Reject plan</button>
      </div>
    </section>
  );
}

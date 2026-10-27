import { useEffect, useRef, useState } from 'react';
import {
  ApiClientError, acceptArtifactRevision, rejectArtifactRevision, getExecutionPlan,
  proposeExecutionPlan, type ExecutionPlanArtifact, type ExecutionPlanProposal,
} from '../../api/client';
import { ExecutionPlanReview } from '../../views/ExecutionPlanReview';
import type { WorkspaceRenderProps } from '../renderers/registry';

export function ExecutionPlanWorkspace({ projectId, state, isDark, onCommandResult }: WorkspaceRenderProps) {
  const [artifact, setArtifact] = useState<Pick<ExecutionPlanArtifact, 'artifactVersion' | 'content'>>();
  const [error, setError] = useState<string>();
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<string>();
  const pending = useRef<ExecutionPlanProposal>();
  const submitting = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setArtifact(undefined);
    setMissing(false);
    setError(undefined);
    setOutcome(undefined);
    pending.current = undefined;
    getExecutionPlan(projectId).then((plan) => {
      if (!cancelled) setArtifact(plan);
    }).catch((err: unknown) => {
      if (!cancelled) {
        if (err instanceof ApiClientError && err.status === 404) setMissing(true);
        else setError(err instanceof Error ? err.message : 'Failed to load execution plan.');
      }
    });
    return () => { cancelled = true; };
  }, [projectId, state.project.currentStateVersion]);

  async function createPlan() {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError(undefined);
    setOutcome(undefined);
    try {
      const components = state.artifacts.find((a) => a.artifactType === 'component-plan');
      const electrical = state.artifacts.find((a) => a.artifactType === 'electrical-architecture');
      const connection = electrical?.content.connections.find((c) => c.interfaceType === 'i2c');
      const nodes = electrical?.content.nodes.filter((n) =>
        n.nodeId === connection?.fromNodeId || n.nodeId === connection?.toNodeId);
      const candidates = components?.content.candidates.filter((c) =>
        nodes?.some((n) => n.componentCandidateId === c.candidateId));
      if (!connection || candidates?.length !== 2) {
        throw new Error('The project needs two component candidates connected by I2C before creating an execution plan.');
      }
      const pin = (key: string, fallback: 21 | 22) => {
        const value = candidates.flatMap((c) => c.specifications).find((s) => s.specKey === key)?.value;
        if (value === undefined) return fallback;
        if (value === 21 || value === 22 || value === 25 || value === 26 || value === 27 || value === 32 || value === 33) return value;
        throw new Error(`Unsupported project pin for ${key}.`);
      };
      const proposal = await proposeExecutionPlan(projectId, {
        baseProjectStateVersion: state.project.currentStateVersion,
        basePlanVersion: 0,
        requestedBy: { schemaVersion: '1.0.0', actorType: 'user', actorId: 'user_local' },
        configuration: {
          components: [
            { componentRoleId: candidates[0].componentRoleId, candidateId: candidates[0].candidateId },
            { componentRoleId: candidates[1].componentRoleId, candidateId: candidates[1].candidateId },
          ],
          i2c: { connectionId: connection.connectionId, sdaPin: pin('gpio-sda', 21), sclPin: pin('gpio-scl', 22) },
          buildProfileId: 'platformio-arduino-esp32-v1', analysisProfileId: 'python-analysis-v1',
        },
      });
      if (!proposal.commandResult.proposalId) throw new Error(proposal.commandResult.error?.message ?? 'Plan proposal failed.');
      pending.current = proposal;
      setArtifact({ artifactVersion: 0, content: proposal.content });
      setMissing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create execution plan.');
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  async function decide(accept: boolean, reason?: string) {
    if (!artifact || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError(undefined);
    try {
      const requestedBy = { schemaVersion: '1.0.0' as const, actorType: 'user' as const, actorId: 'user_local' };
      const proposal = pending.current ?? await proposeExecutionPlan(projectId, {
        baseProjectStateVersion: state.project.currentStateVersion,
        basePlanVersion: artifact.artifactVersion,
        configuration: artifact.content.configuration,
        plan: artifact.content.plan,
        requestedBy,
      });
      if (!proposal.commandResult.proposalId) {
        throw new Error(proposal.commandResult.error?.message ?? 'Plan proposal failed.');
      }
      pending.current = proposal;
      const workspace = proposal.workspace;
      const result = await (accept ? acceptArtifactRevision : rejectArtifactRevision)(projectId, {
        schemaVersion: '1.0.0', commandId: `cmd_${crypto.randomUUID().replace(/-/g, '').slice(0, 24)}`, requestedAt: new Date().toISOString(), requestedBy,
        artifactId: workspace.artifactId, workspaceId: workspace.workspaceId,
        baseArtifactVersion: workspace.baseArtifactVersion,
        baseProjectStateVersion: workspace.baseProjectStateVersion,
        proposalId: proposal.commandResult.proposalId, reason,
      });
      if (result.status !== 'completed' && result.status !== 'completed-with-warnings') {
        throw new Error(result.error?.message ?? `Plan decision ${result.status}. Reload the project and review again.`);
      }
      pending.current = undefined;
      setOutcome(accept ? 'Plan accepted.' : 'Plan rejected.');
      if (!accept && artifact.artifactVersion === 0) { setArtifact(undefined); setMissing(true); }
      onCommandResult?.(result);
    } catch (err) {
      setError(`${err instanceof Error ? err.message : 'Plan decision failed.'} Reload the project if the plan basis has changed.`);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  return (
    <>
    {error ? <p role="alert">{error}</p> : null}
    <p>Unchanged workspace scaffolds are reconciled on approval. If a file conflicts, open
      Firmware or Analysis from the workflow rail, copy its contents to a safe location,
      delete the named file, then return here and accept the plan again.</p>
    {outcome ? <p role="status">{outcome}</p> : null}
    {missing ? <button type="button" disabled={busy} onClick={() => { void createPlan(); }}>Create Execution Plan</button> : null}
    {artifact ? <ExecutionPlanReview key={`${projectId}-${artifact.artifactVersion}`} content={artifact.content} isDark={isDark}
      disabled={busy || Boolean(outcome)} onAccept={() => { void decide(true); }} onReject={(reason) => { void decide(false, reason); }} />
      : !error && !missing ? <p role="status">Loading execution plan…</p> : null}
    </>
  );
}

import { useEffect, useRef, useState } from 'react';
import {
  acceptArtifactRevision, rejectArtifactRevision, getExecutionPlan,
  proposeExecutionPlan, type ExecutionPlanArtifact, type ExecutionPlanProposal,
} from '../../api/client';
import { ExecutionPlanReview } from '../../views/ExecutionPlanReview';
import type { WorkspaceRenderProps } from '../renderers/registry';

export function ExecutionPlanWorkspace({ projectId, state, isDark, onCommandResult }: WorkspaceRenderProps) {
  const [artifact, setArtifact] = useState<ExecutionPlanArtifact>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<string>();
  const pending = useRef<ExecutionPlanProposal>();
  const submitting = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setArtifact(undefined);
    setError(undefined);
    setOutcome(undefined);
    pending.current = undefined;
    getExecutionPlan(projectId).then((plan) => {
      if (!cancelled) setArtifact(plan);
    }).catch((err: unknown) => {
      if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load execution plan.');
    });
    return () => { cancelled = true; };
  }, [projectId, state.project.currentStateVersion]);

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
    {outcome ? <p role="status">{outcome}</p> : null}
    {artifact ? <ExecutionPlanReview key={`${projectId}-${artifact.artifactVersion}`} content={artifact.content} isDark={isDark}
      disabled={busy || Boolean(outcome)} onAccept={() => { void decide(true); }} onReject={(reason) => { void decide(false, reason); }} />
      : !error ? <p role="status">Loading execution plan…</p> : null}
    </>
  );
}

import { useCallback, useEffect, useMemo, useState } from 'react';
import type {
  Artifact,
  ArtifactCommand,
  ArtifactCommandResult,
  CompatibilityCheck,
  ComponentCandidate,
  ComponentPlanContent,
  ComponentRole,
  SelectionConstraint,
  SelectionDecision,
  WorkspaceDescriptor,
} from '@nexus/contracts';
import {
  ApiClientError,
  createWorkspace,
  getWorkspace,
  submitArtifactCommand,
} from '../../api/client';
import { themeColors } from '../../lib/theme';
import { EvidenceBadge } from '../../components/statuses/EvidenceBadge';
import { StatusBadge } from '../../components/statuses/StatusBadge';

type Props = {
  projectId: string;
  artifact?: Extract<Artifact, { artifactType: 'component-plan' }>;
  isDark: boolean;
  selectedRoleId?: string | null;
  onSelectRole?: (roleId: string) => void;
  onSubmitTurn?: (message: string) => Promise<boolean>;
  turnBusy?: boolean;
  onCommandResult?: (result: ArtifactCommandResult) => void;
};

function newCommandId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return `cmd_${crypto.randomUUID().replace(/-/g, '').slice(0, 24)}`;
  }
  return `cmd_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

function userActor() {
  return {
    schemaVersion: '1.0.0' as const,
    actorId: 'user_local',
    actorType: 'user' as const,
  };
}

function formatSpecValue(
  value: ComponentCandidate['specifications'][number]['value'],
): string {
  if (typeof value === 'object' && value !== null && 'kind' in value) {
    return 'unknown';
  }
  return String(value);
}

function unresolvedChecks(checks: CompatibilityCheck[]): CompatibilityCheck[] {
  return checks.filter((check) =>
    ['not-checked', 'unknown', 'fail', 'warning', 'conditional'].includes(check.status),
  );
}

function constraintsForRole(
  constraints: SelectionConstraint[],
  roleId: string,
): SelectionConstraint[] {
  return constraints.filter((c) => c.componentRoleId === roleId);
}

function decisionForRole(
  decisions: SelectionDecision[],
  roleId: string,
): SelectionDecision | undefined {
  return decisions.find((d) => d.componentRoleId === roleId);
}

export function ComponentPlanWorkspace({
  projectId,
  artifact,
  isDark,
  selectedRoleId = null,
  onSelectRole,
  onSubmitTurn,
  turnBusy = false,
  onCommandResult,
}: Props) {
  const t = themeColors(isDark);
  const content = artifact?.content;
  const roles = content?.componentRoles ?? [];
  const candidates = content?.candidates ?? [];
  const decisions = content?.selectionDecisions ?? [];
  const checks = content?.compatibilityChecks ?? [];
  const constraints = content?.selectionConstraints ?? [];
  const coverage = content?.coverageSummary;

  const [workspace, setWorkspace] = useState<WorkspaceDescriptor | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [commandBusy, setCommandBusy] = useState(false);
  const [commandMessage, setCommandMessage] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [lastAction, setLastAction] = useState<string | null>(null);

  const selectedRole: ComponentRole | undefined = useMemo(() => {
    if (!roles.length) return undefined;
    return roles.find((r) => r.componentRoleId === selectedRoleId) ?? roles[0];
  }, [roles, selectedRoleId]);

  const roleCandidates = useMemo(
    () =>
      selectedRole
        ? candidates.filter((c) => c.componentRoleId === selectedRole.componentRoleId)
        : [],
    [candidates, selectedRole],
  );

  const roleDecision = selectedRole
    ? decisionForRole(decisions, selectedRole.componentRoleId)
    : undefined;
  const preferredCandidate = roleDecision
    ? roleCandidates.find((c) => c.candidateId === roleDecision.selectedCandidateId)
    : roleCandidates.find((c) => c.candidateState === 'preferred' || c.candidateState === 'selected');

  const roleConstraints = selectedRole
    ? constraintsForRole(constraints, selectedRole.componentRoleId)
    : [];
  const roleChecks = selectedRole
    ? checks.filter((c) => c.componentRoleId === selectedRole.componentRoleId)
    : [];
  const unresolved = unresolvedChecks(checks);
  const selectedCount = decisions.filter((d) => d.selectionState === 'approved').length;
  const blockingIssues = content?.validationSummary.blockingIssueCount ?? 0;
  const busy = commandBusy || actionBusy || turnBusy;

  const refreshWorkspace = useCallback(async () => {
    setWorkspaceError(null);
    try {
      const next = await getWorkspace(projectId, 'component-plan');
      setWorkspace(next);
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setWorkspace(null);
        return;
      }
      setWorkspaceError(
        err instanceof ApiClientError ? err.message : 'Failed to load component-plan workspace',
      );
    }
  }, [projectId]);

  useEffect(() => {
    void refreshWorkspace();
  }, [refreshWorkspace]);

  useEffect(() => {
    if (selectedRole && onSelectRole && selectedRole.componentRoleId !== selectedRoleId) {
      onSelectRole(selectedRole.componentRoleId);
    }
  }, [onSelectRole, selectedRole, selectedRoleId]);

  async function ensureWorkspace(): Promise<WorkspaceDescriptor | null> {
    if (workspace) return workspace;
    try {
      const created = await createWorkspace(projectId, 'component-plan');
      setWorkspace(created);
      return created;
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setCommandMessage('Workspace API is not available yet.');
        return null;
      }
      setCommandMessage(
        err instanceof ApiClientError ? err.message : 'Failed to create workspace',
      );
      return null;
    }
  }

  async function runCommand(
    build: (ws: WorkspaceDescriptor) => ArtifactCommand,
  ): Promise<void> {
    if (!artifact) {
      setCommandMessage('No component-plan artifact is available to command yet.');
      return;
    }
    if (busy) return;
    setCommandBusy(true);
    setCommandMessage(null);
    try {
      const ws = await ensureWorkspace();
      if (!ws) return;
      const result = await submitArtifactCommand(projectId, build(ws));
      onCommandResult?.(result);
      setCommandMessage(`Command ${result.commandId}: ${result.status}`);
      await refreshWorkspace();
    } catch (err) {
      if (err instanceof ApiClientError && (err.status === 404 || err.status === 501)) {
        setCommandMessage('Artifact command API is not available yet.');
      } else {
        setCommandMessage(
          err instanceof ApiClientError ? err.message : 'Command failed',
        );
      }
    } finally {
      setCommandBusy(false);
    }
  }

  async function runSelectionAction(
    kind: 'approve' | 'reject' | 'alternatives',
    message: string,
  ): Promise<void> {
    if (!onSubmitTurn || busy) return;
    setActionBusy(true);
    setActionMessage(null);
    setLastAction(kind);
    try {
      const ok = await onSubmitTurn(message);
      if (ok) {
        setActionMessage(`Submitted: ${message}`);
      } else {
        // Retain role selection and button context on failure.
        setActionMessage('Submission failed. Your selection context was kept.');
      }
    } finally {
      setActionBusy(false);
    }
  }

  if (!content) {
    return (
      <div
        style={{ flex: 1, overflow: 'auto', padding: 16, background: t.bg }}
        data-testid="workspace-component-plan"
      >
        <EmptyState
          isDark={isDark}
          title="Component plan not available"
          body="No component-plan artifact is in the current project state yet. Roles and candidates will appear here once Vera produces a plan."
        />
      </div>
    );
  }

  return (
    <div
      style={{ flex: 1, overflow: 'auto', padding: 16, background: t.bg, display: 'grid', gap: 14 }}
      data-testid="workspace-component-plan"
    >
      <section
        style={{
          border: `1px solid ${t.border}`,
          borderRadius: 8,
          padding: 14,
          background: t.surface,
          display: 'grid',
          gap: 10,
        }}
        data-testid="component-plan-summary"
      >
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <strong style={{ fontSize: 13, color: t.text }}>Summary</strong>
          <StatusBadge status={content.maturity} />
          <StatusBadge status={content.validationSummary.status} />
          <EvidenceBadge status={artifact?.evidenceStatus ?? 'unverified'} />
        </div>
        <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>{content.summary}</p>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
            gap: 8,
          }}
        >
          <Metric label="Roles" value={String(roles.length)} isDark={isDark} />
          <Metric label="Candidates" value={String(candidates.length)} isDark={isDark} />
          <Metric label="Selected" value={String(selectedCount)} isDark={isDark} />
          <Metric label="Blockers" value={String(blockingIssues)} isDark={isDark} />
          <Metric
            label="Unresolved checks"
            value={String(unresolved.length)}
            isDark={isDark}
          />
          <Metric
            label="Awaiting approval"
            value={String(coverage?.rolesAwaitingApproval ?? 0)}
            isDark={isDark}
          />
        </div>
      </section>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(220px, 0.7fr) minmax(0, 1.3fr)',
          gap: 14,
          alignItems: 'start',
        }}
      >
        <section
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 8,
            padding: 14,
            background: t.surface,
            display: 'grid',
            gap: 8,
          }}
          data-testid="component-plan-role-list"
        >
          <h3 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Roles</h3>
          {roles.length === 0 ? (
            <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
              No component roles defined yet.
            </p>
          ) : (
            roles.map((role) => {
              const active = selectedRole?.componentRoleId === role.componentRoleId;
              const roleCands = candidates.filter((c) => c.componentRoleId === role.componentRoleId);
              const roleCons = constraintsForRole(constraints, role.componentRoleId);
              return (
                <button
                  key={role.componentRoleId}
                  type="button"
                  data-testid={`component-role-${role.componentRoleId}`}
                  data-role-category={role.category}
                  onClick={() => onSelectRole?.(role.componentRoleId)}
                  style={{
                    textAlign: 'left',
                    border: `1px solid ${active ? t.cobalt : t.border}`,
                    background: active ? t.cobaltSelected : t.bg,
                    borderRadius: 8,
                    padding: 10,
                    cursor: 'pointer',
                    display: 'grid',
                    gap: 6,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <strong style={{ fontSize: 13, color: t.text }}>{role.name}</strong>
                    <StatusBadge status={role.status} />
                  </div>
                  <div style={{ fontSize: 11, color: t.textMuted }}>
                    {role.displayId} · {role.category} · {roleCands.length} candidates
                  </div>
                  <div style={{ fontSize: 11, color: t.textSec }}>
                    Arch: {role.architectureNodeIds.length || 'none'} · Reqs:{' '}
                    {role.requirementIds.length || 'none'} · Constraints: {roleCons.length}
                  </div>
                </button>
              );
            })
          )}
        </section>

        <div style={{ display: 'grid', gap: 14 }}>
          <section
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: 14,
              background: t.surface,
              display: 'grid',
              gap: 10,
            }}
            data-testid="component-plan-candidate-compare"
          >
            <h3 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
              Candidate comparison
              {selectedRole ? ` · ${selectedRole.name}` : ''}
            </h3>
            {!selectedRole ? (
              <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
                Select a role to compare candidates.
              </p>
            ) : roleCandidates.length === 0 ? (
              <p style={{ margin: 0, fontSize: 13, color: t.textSec }} data-testid="component-plan-candidates-empty">
                No candidates proposed for this role yet. Request alternatives through Vera when ready.
              </p>
            ) : (
              <div style={{ display: 'grid', gap: 10 }}>
                {roleCandidates.map((candidate) => (
                  <CandidateCard
                    key={candidate.candidateId}
                    candidate={candidate}
                    checks={roleChecks.filter((c) => c.candidateId === candidate.candidateId)}
                    isPreferred={preferredCandidate?.candidateId === candidate.candidateId}
                    isDark={isDark}
                  />
                ))}
              </div>
            )}
          </section>

          <section
            style={{
              border: `1px solid ${t.border}`,
              borderRadius: 8,
              padding: 14,
              background: t.surface,
              display: 'grid',
              gap: 10,
            }}
            data-testid="component-plan-selection-panel"
          >
            <h3 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Selection</h3>
            {!selectedRole ? (
              <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
                Select a role to review preferred selection and approval actions.
              </p>
            ) : (
              <>
                {!roleDecision && !preferredCandidate ? (
                  <p style={{ margin: 0, fontSize: 13, color: t.textSec }} data-testid="component-plan-selection-empty">
                    No preferred selection yet for {selectedRole.name}.
                  </p>
                ) : (
                  <>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      <strong style={{ fontSize: 13, color: t.text }}>
                        Preferred: {preferredCandidate?.displayName ?? roleDecision?.selectedCandidateId}
                      </strong>
                      {roleDecision ? <StatusBadge status={roleDecision.selectionState} /> : null}
                    </div>
                    {roleDecision?.rationale ? (
                      <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>{roleDecision.rationale}</p>
                    ) : null}
                    {roleDecision?.tradeoffs?.length ? (
                      <div>
                        <h4 style={{ margin: '0 0 4px', fontSize: 11, color: t.textMuted }}>Tradeoffs</h4>
                        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                          {roleDecision.tradeoffs.map((item) => (
                            <li key={item}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {roleConstraints.length ? (
                      <div>
                        <h4 style={{ margin: '0 0 4px', fontSize: 11, color: t.textMuted }}>
                          Constraints ({roleConstraints.length})
                        </h4>
                        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                          {roleConstraints.slice(0, 4).map((c) => (
                            <li key={c.constraintId}>
                              {c.constraintType} · {c.importance} · {c.confirmationStatus}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </>
                )}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <ActionButton
                    label="Approve preferred"
                    testId="component-plan-approve"
                    disabled={busy || !preferredCandidate}
                    isDark={isDark}
                    onClick={() =>
                      void runSelectionAction(
                        'approve',
                        `Approve the preferred selection for role ${selectedRole.name}`,
                      )
                    }
                  />
                  <ActionButton
                    label="Reject candidate"
                    testId="component-plan-reject"
                    disabled={busy || !preferredCandidate}
                    isDark={isDark}
                    onClick={() =>
                      void runSelectionAction(
                        'reject',
                        `Reject the preferred candidate for role ${selectedRole.name}`,
                      )
                    }
                  />
                  <ActionButton
                    label="Request alternatives"
                    testId="component-plan-request-alternatives"
                    disabled={busy}
                    isDark={isDark}
                    onClick={() =>
                      void runSelectionAction(
                        'alternatives',
                        `Show me another option for ${selectedRole.name}`,
                      )
                    }
                  />
                </div>
                {actionMessage ? (
                  <p role="status" style={{ margin: 0, fontSize: 12, color: t.text }}>
                    {actionMessage}
                    {lastAction ? ` (${lastAction})` : ''}
                  </p>
                ) : null}
              </>
            )}
          </section>
        </div>
      </div>

      <section
        style={{
          border: `1px solid ${t.border}`,
          borderRadius: 8,
          padding: 14,
          background: t.surface,
        }}
        data-testid="component-plan-compatibility"
      >
        <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>
          Compatibility checks
        </h3>
        {roleChecks.length === 0 && unresolved.length === 0 ? (
          <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
            No compatibility checks recorded yet.
          </p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: t.text }}>
            {(selectedRole ? roleChecks : unresolved).slice(0, 8).map((check) => (
              <li key={check.compatibilityCheckId}>
                {check.checkType}: {check.status} ({check.severity}) — {check.reason}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section
        style={{
          border: `1px solid ${t.border}`,
          borderRadius: 8,
          padding: 14,
          background: t.surface,
          display: 'grid',
          gap: 10,
        }}
        data-testid="component-plan-workspace-commands"
      >
        <h3 style={{ margin: 0, fontSize: 12, color: t.textMuted }}>Workspace commands</h3>
        <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
          {workspace
            ? `Workspace ${workspace.workspaceId} · ${workspace.status}`
            : 'No workspace bound yet (API may still be landing).'}
        </p>
        {workspaceError ? (
          <p role="status" style={{ margin: 0, fontSize: 12, color: t.text }}>
            {workspaceError}
          </p>
        ) : null}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionButton
            label="Create / refresh workspace"
            disabled={busy}
            isDark={isDark}
            onClick={() => void ensureWorkspace().then(() => refreshWorkspace())}
          />
          <ActionButton
            label="Create snapshot"
            disabled={busy || !artifact}
            isDark={isDark}
            onClick={() =>
              void runCommand((ws) => ({
                schemaVersion: '1.0.0',
                commandId: newCommandId(),
                commandType: 'workspace.create-snapshot',
                projectId,
                artifactId: artifact!.artifactId,
                workspaceId: ws.workspaceId,
                baseArtifactVersion: artifact!.artifactVersion,
                baseProjectStateVersion: ws.baseProjectStateVersion,
                requestedAt: new Date().toISOString(),
                requestedBy: userActor(),
                input: { reason: 'Manual snapshot from component-plan workspace' },
              }))
            }
          />
          <ActionButton
            label="Propose revision"
            disabled={busy || !artifact || !workspace?.currentSnapshotId}
            isDark={isDark}
            onClick={() =>
              void runCommand((ws) => ({
                schemaVersion: '1.0.0',
                commandId: newCommandId(),
                commandType: 'artifact.propose-revision',
                projectId,
                artifactId: artifact!.artifactId,
                workspaceId: ws.workspaceId,
                baseArtifactVersion: artifact!.artifactVersion,
                baseProjectStateVersion: ws.baseProjectStateVersion,
                requestedAt: new Date().toISOString(),
                requestedBy: userActor(),
                input: {
                  snapshotId: ws.currentSnapshotId!,
                  consequenceLevel: 'medium',
                  summary: 'Propose component-plan revision from comparison workspace',
                },
              }))
            }
          />
        </div>
        {commandMessage ? (
          <p role="status" style={{ margin: 0, fontSize: 12, color: t.text }}>
            {commandMessage}
          </p>
        ) : null}
      </section>
    </div>
  );
}

function CandidateCard({
  candidate,
  checks,
  isPreferred,
  isDark,
}: {
  candidate: ComponentCandidate;
  checks: CompatibilityCheck[];
  isPreferred: boolean;
  isDark: boolean;
}) {
  const t = themeColors(isDark);
  return (
    <article
      data-testid={`component-candidate-${candidate.candidateId}`}
      style={{
        border: `1px solid ${isPreferred ? t.cobalt : t.border}`,
        borderRadius: 8,
        padding: 12,
        background: isPreferred ? t.cobaltTint : t.bg,
        display: 'grid',
        gap: 8,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div>
          <strong style={{ fontSize: 13, color: t.text }}>{candidate.displayName}</strong>
          <div style={{ fontSize: 11, color: t.textMuted }}>
            {candidate.manufacturer} · {candidate.partNumber}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <StatusBadge status={candidate.candidateState} />
          <EvidenceBadge status={candidate.evidenceStatus} />
          {isPreferred ? <StatusBadge status="preferred" /> : null}
        </div>
      </div>
      {candidate.specifications.length ? (
        <div style={{ fontSize: 12, color: t.textSec }}>
          Specs:{' '}
          {candidate.specifications
            .slice(0, 4)
            .map((spec) => {
              const unit = spec.unit ? ` ${spec.unit}` : '';
              return `${spec.specKey}=${formatSpecValue(spec.value)}${unit}`;
            })
            .join(' · ')}
        </div>
      ) : null}
      {candidate.advantages.length ? (
        <div style={{ fontSize: 12, color: t.text }}>
          Advantages: {candidate.advantages.join('; ')}
        </div>
      ) : null}
      {candidate.limitations.length ? (
        <div style={{ fontSize: 12, color: t.textSec }}>
          Limitations: {candidate.limitations.join('; ')}
        </div>
      ) : null}
      <div style={{ fontSize: 11, color: t.textMuted }}>
        Compatibility: {checks.length ? checks.map((c) => `${c.checkType}:${c.status}`).join(', ') : 'none'}
        {' · '}
        Evidence refs: {candidate.evidenceReferences.length}
        {' · '}
        Confidence: {candidate.confidence}
      </div>
    </article>
  );
}

function Metric({
  label,
  value,
  isDark,
}: {
  label: string;
  value: string;
  isDark: boolean;
}) {
  const t = themeColors(isDark);
  return (
    <div style={{ border: `1px solid ${t.border}`, borderRadius: 6, padding: 8, background: t.bg }}>
      <div style={{ fontSize: 11, color: t.textMuted }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color: t.text }}>{value}</div>
    </div>
  );
}

function EmptyState({
  isDark,
  title,
  body,
}: {
  isDark: boolean;
  title: string;
  body: string;
}) {
  const t = themeColors(isDark);
  return (
    <div
      style={{
        border: `1px dashed ${t.border}`,
        borderRadius: 8,
        padding: 24,
        background: t.surface,
        maxWidth: 560,
      }}
      data-testid="component-plan-empty"
    >
      <h3 style={{ margin: 0, fontSize: 15, color: t.text }}>{title}</h3>
      <p style={{ margin: '8px 0 0', fontSize: 13, color: t.textSec }}>{body}</p>
    </div>
  );
}

function ActionButton({
  label,
  disabled,
  isDark,
  onClick,
  testId,
}: {
  label: string;
  disabled?: boolean;
  isDark: boolean;
  onClick: () => void;
  testId?: string;
}) {
  const t = themeColors(isDark);
  return (
    <button
      type="button"
      disabled={disabled}
      data-testid={testId}
      onClick={onClick}
      style={{
        padding: '6px 10px',
        borderRadius: 6,
        border: `1px solid ${t.border}`,
        background: disabled ? t.bg : t.cobaltTint,
        color: disabled ? t.textMuted : t.cobalt,
        fontSize: 12,
        fontWeight: 600,
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      {label}
    </button>
  );
}

/** Exported for unit tests that need content helpers without mounting API. */
export function summarizePlanContent(content: ComponentPlanContent) {
  return {
    roleCount: content.componentRoles.length,
    candidateCount: content.candidates.length,
    selectedCount: content.selectionDecisions.filter((d) => d.selectionState === 'approved')
      .length,
    unresolvedCheckCount: unresolvedChecks(content.compatibilityChecks).length,
  };
}

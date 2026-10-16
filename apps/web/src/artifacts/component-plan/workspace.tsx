import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react';
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

type InspectorTab = 'decision' | 'specifications' | 'evidence' | 'alternatives' | 'linked-work';

type Props = {
  projectId: string;
  artifact?: Extract<Artifact, { artifactType: 'component-plan' }>;
  isDark: boolean;
  selectedRoleId?: string | null;
  onSelectRole?: (roleId: string) => void;
  onSubmitTurn?: (message: string) => Promise<boolean>;
  turnBusy?: boolean;
  onCommandResult?: (result: ArtifactCommandResult) => void;
  onRequestAlternatives?: (roleId: string, suggestedPrompt: string) => void;
  onAskVera?: () => void;
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

function preferredForRole(
  candidates: ComponentCandidate[],
  decisions: SelectionDecision[],
  roleId: string,
): ComponentCandidate | undefined {
  const roleCandidates = candidates.filter((c) => c.componentRoleId === roleId);
  const decision = decisionForRole(decisions, roleId);
  if (decision) {
    return roleCandidates.find((c) => c.candidateId === decision.selectedCandidateId);
  }
  return roleCandidates.find(
    (c) => c.candidateState === 'preferred' || c.candidateState === 'selected',
  );
}

function compatibilitySummary(
  checks: CompatibilityCheck[],
  roleId: string,
  candidateId?: string,
): string {
  const roleChecks = checks.filter(
    (c) =>
      c.componentRoleId === roleId &&
      (candidateId == null || c.candidateId === candidateId),
  );
  if (!roleChecks.length) return 'No checks';
  const unresolved = unresolvedChecks(roleChecks);
  if (!unresolved.length) {
    const passes = roleChecks.filter((c) => c.status === 'pass').length;
    return `${passes}/${roleChecks.length} pass`;
  }
  return `${unresolved.length} unresolved`;
}

function evidenceSummary(
  candidates: ComponentCandidate[],
  preferred: ComponentCandidate | undefined,
  planStatus: Artifact['evidenceStatus'] | undefined,
): string {
  if (preferred) return preferred.evidenceStatus;
  if (candidates.length) {
    return candidates[0]?.evidenceStatus ?? planStatus ?? 'unverified';
  }
  return planStatus ?? 'unverified';
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
  onRequestAlternatives,
  onAskVera,
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
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('decision');

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
  const preferredCandidate = selectedRole
    ? preferredForRole(candidates, decisions, selectedRole.componentRoleId)
    : undefined;

  const roleConstraints = selectedRole
    ? constraintsForRole(constraints, selectedRole.componentRoleId)
    : [];
  const roleChecks = selectedRole
    ? checks.filter((c) => c.componentRoleId === selectedRole.componentRoleId)
    : [];
  const unresolved = unresolvedChecks(checks);
  const preferredCount = roles.filter(
    (role) => preferredForRole(candidates, decisions, role.componentRoleId) != null,
  ).length;
  const approvedCount = decisions.filter((d) => d.selectionState === 'approved').length;
  const blockedCount = coverage?.rolesWithBlockedSelection ?? 0;
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
    kind: 'approve' | 'reject',
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
        setActionMessage('Submission failed. Your selection context was kept.');
      }
    } finally {
      setActionBusy(false);
    }
  }

  function requestAlternativesForRole(role: ComponentRole): void {
    const prompt = `Show me alternatives for the ${role.name} role.`;
    if (onRequestAlternatives) {
      onRequestAlternatives(role.componentRoleId, prompt);
      setLastAction('alternatives');
      setActionMessage('Opened Vera with an alternatives prompt (not submitted).');
      return;
    }
    onAskVera?.();
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

  const alternativeCandidates = preferredCandidate
    ? roleCandidates.filter((c) => c.candidateId !== preferredCandidate.candidateId)
    : roleCandidates;

  return (
    <div
      style={{
        flex: 1,
        overflow: 'hidden',
        padding: 16,
        background: t.bg,
        display: 'grid',
        gridTemplateRows: 'auto minmax(0, 1fr) auto',
        gap: 14,
      }}
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
            gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
            gap: 8,
          }}
        >
          <Metric label="Roles" value={String(roles.length)} isDark={isDark} />
          <Metric label="Candidates" value={String(candidates.length)} isDark={isDark} />
          <Metric label="Preferred" value={String(preferredCount)} isDark={isDark} />
          <Metric label="Approved" value={String(approvedCount)} isDark={isDark} />
          <Metric label="Blocked" value={String(blockedCount)} isDark={isDark} />
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
          gridTemplateColumns: 'minmax(0, 1.2fr) minmax(280px, 0.9fr)',
          gap: 14,
          minHeight: 0,
          alignItems: 'stretch',
        }}
      >
        <section
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 8,
            padding: 0,
            background: t.surface,
            overflow: 'auto',
            minHeight: 0,
          }}
          data-testid="component-plan-role-list"
        >
          <div
            style={{
              padding: '10px 12px',
              borderBottom: `1px solid ${t.border}`,
              fontSize: 12,
              color: t.textMuted,
              fontWeight: 600,
            }}
          >
            System components
          </div>
          {roles.length === 0 ? (
            <p style={{ margin: 12, fontSize: 13, color: t.textSec }}>
              No component roles defined yet.
            </p>
          ) : (
            <table
              data-testid="component-plan-role-table"
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 12,
              }}
            >
              <thead>
                <tr style={{ color: t.textMuted, textAlign: 'left' }}>
                  <th style={thStyle}>Role</th>
                  <th style={thStyle}>Preferred part</th>
                  <th style={thStyle}>Decision</th>
                  <th style={thStyle}>Compatibility</th>
                  <th style={thStyle}>Evidence</th>
                  <th style={thStyle}>Approval</th>
                </tr>
              </thead>
              <tbody>
                {roles.map((role) => {
                  const active = selectedRole?.componentRoleId === role.componentRoleId;
                  const preferred = preferredForRole(candidates, decisions, role.componentRoleId);
                  const decision = decisionForRole(decisions, role.componentRoleId);
                  const approval =
                    decision?.selectionState ??
                    (preferred ? preferred.candidateState : 'not-started');
                  return (
                    <tr
                      key={role.componentRoleId}
                      data-testid={`component-role-${role.componentRoleId}`}
                      data-role-category={role.category}
                      onClick={() => onSelectRole?.(role.componentRoleId)}
                      style={{
                        cursor: 'pointer',
                        background: active ? t.cobaltSelected : 'transparent',
                        borderTop: `1px solid ${t.border}`,
                      }}
                    >
                      <td style={tdStyle}>
                        <strong style={{ color: t.text }}>{role.name}</strong>
                        <div style={{ color: t.textMuted, marginTop: 2 }}>
                          {role.displayId} · {role.category}
                        </div>
                      </td>
                      <td style={{ ...tdStyle, color: t.text }}>
                        {preferred?.displayName ?? 'No candidate proposed'}
                      </td>
                      <td style={tdStyle}>
                        <StatusBadge status={decision?.selectionState ?? role.status} />
                      </td>
                      <td style={{ ...tdStyle, color: t.textSec }}>
                        {compatibilitySummary(checks, role.componentRoleId, preferred?.candidateId)}
                      </td>
                      <td style={tdStyle}>
                        <EvidenceBadge
                          status={evidenceSummary(
                            candidates.filter((c) => c.componentRoleId === role.componentRoleId),
                            preferred,
                            artifact?.evidenceStatus,
                          )}
                        />
                      </td>
                      <td style={tdStyle}>
                        <StatusBadge status={approval} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>

        <section
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 8,
            background: t.surface,
            display: 'flex',
            flexDirection: 'column',
            minHeight: 0,
            overflow: 'hidden',
          }}
          data-testid="component-plan-inspector"
        >
          <div
            style={{
              display: 'flex',
              gap: 4,
              flexWrap: 'wrap',
              padding: '8px 10px',
              borderBottom: `1px solid ${t.border}`,
            }}
            role="tablist"
            aria-label="Component role inspector"
          >
            {(
              [
                ['decision', 'Decision'],
                ['specifications', 'Specifications'],
                ['evidence', 'Evidence'],
                ['alternatives', 'Alternatives'],
                ['linked-work', 'Linked Work'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={inspectorTab === id}
                data-testid={`component-plan-inspector-tab-${id}`}
                onClick={() => setInspectorTab(id)}
                style={{
                  border: `1px solid ${inspectorTab === id ? t.cobalt : t.border}`,
                  background: inspectorTab === id ? t.cobaltTint : 'transparent',
                  color: inspectorTab === id ? t.cobalt : t.textSec,
                  borderRadius: 6,
                  padding: '4px 8px',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {label}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflow: 'auto', padding: 12, display: 'grid', gap: 12 }}>
            {!selectedRole ? (
              <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
                Select a role to inspect decisions, specs, and evidence.
              </p>
            ) : null}

            {selectedRole && inspectorTab === 'decision' ? (
              <div data-testid="component-plan-selection-panel" style={{ display: 'grid', gap: 10 }}>
                {!roleDecision && !preferredCandidate ? (
                  <p
                    style={{ margin: 0, fontSize: 13, color: t.textSec }}
                    data-testid="component-plan-selection-empty"
                  >
                    No preferred selection yet for {selectedRole.name}.
                  </p>
                ) : (
                  <>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      <strong style={{ fontSize: 13, color: t.text }}>
                        Preferred:{' '}
                        {preferredCandidate?.displayName ?? roleDecision?.selectedCandidateId}
                      </strong>
                      {roleDecision ? <StatusBadge status={roleDecision.selectionState} /> : null}
                    </div>
                    {roleDecision?.rationale ? (
                      <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
                        {roleDecision.rationale}
                      </p>
                    ) : (
                      <p style={{ margin: 0, fontSize: 12, color: t.textMuted }}>
                        Rationale unknown.
                      </p>
                    )}
                    {roleDecision?.tradeoffs?.length ? (
                      <div>
                        <h4 style={{ margin: '0 0 4px', fontSize: 11, color: t.textMuted }}>
                          Tradeoffs
                        </h4>
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
                    onClick={() => requestAlternativesForRole(selectedRole)}
                  />
                </div>
                {actionMessage ? (
                  <p role="status" style={{ margin: 0, fontSize: 12, color: t.text }}>
                    {actionMessage}
                    {lastAction ? ` (${lastAction})` : ''}
                  </p>
                ) : null}
              </div>
            ) : null}

            {selectedRole && inspectorTab === 'specifications' ? (
              <div data-testid="component-plan-specs" style={{ display: 'grid', gap: 8 }}>
                {!preferredCandidate ? (
                  <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
                    No preferred candidate specs available.
                  </p>
                ) : preferredCandidate.specifications.length === 0 ? (
                  <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
                    Specifications unknown for {preferredCandidate.displayName}.
                  </p>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                    {preferredCandidate.specifications.map((spec) => {
                      const unit = spec.unit ? ` ${spec.unit}` : '';
                      return (
                        <li key={`${spec.specKey}-${formatSpecValue(spec.value)}`}>
                          {spec.specKey}: {formatSpecValue(spec.value)}
                          {unit}
                          {spec.operator ? ` (${spec.operator})` : ''}
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            ) : null}

            {selectedRole && inspectorTab === 'evidence' ? (
              <div data-testid="component-plan-evidence" style={{ display: 'grid', gap: 8 }}>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <EvidenceBadge
                    status={
                      preferredCandidate?.evidenceStatus ??
                      artifact?.evidenceStatus ??
                      'unverified'
                    }
                  />
                  <span style={{ fontSize: 12, color: t.textMuted }}>
                    Plan evidence: {artifact?.evidenceStatus ?? 'unverified'}
                  </span>
                </div>
                {preferredCandidate?.evidenceReferences.length ? (
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                    {preferredCandidate.evidenceReferences.map((ref) => (
                      <li key={ref.evidenceId}>
                        {ref.sourceType} · {ref.evidenceStrength}
                        {ref.supportedClaim ? `: ${ref.supportedClaim}` : ''}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>
                    No evidence references on the preferred candidate yet. Status is not verified
                    beyond the badge above.
                  </p>
                )}
                {roleChecks.length ? (
                  <div>
                    <h4 style={{ margin: '0 0 4px', fontSize: 11, color: t.textMuted }}>
                      Compatibility
                    </h4>
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                      {roleChecks.slice(0, 8).map((check) => (
                        <li key={check.compatibilityCheckId}>
                          {check.checkType}: {check.status} ({check.severity}) — {check.reason}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            {selectedRole && inspectorTab === 'alternatives' ? (
              <div
                data-testid="component-plan-candidate-compare"
                style={{ display: 'grid', gap: 10 }}
              >
                {roleCandidates.length === 0 ? (
                  <p
                    style={{ margin: 0, fontSize: 13, color: t.textSec }}
                    data-testid="component-plan-candidates-empty"
                  >
                    No candidates proposed for this role yet. Request alternatives through Vera when
                    ready.
                  </p>
                ) : alternativeCandidates.length === 0 && preferredCandidate ? (
                  <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
                    Only the preferred candidate is listed for this role.
                  </p>
                ) : (
                  (alternativeCandidates.length ? alternativeCandidates : roleCandidates).map(
                    (candidate) => (
                      <CandidateCard
                        key={candidate.candidateId}
                        candidate={candidate}
                        checks={roleChecks.filter((c) => c.candidateId === candidate.candidateId)}
                        isPreferred={preferredCandidate?.candidateId === candidate.candidateId}
                        isDark={isDark}
                      />
                    ),
                  )
                )}
              </div>
            ) : null}

            {selectedRole && inspectorTab === 'linked-work' ? (
              <div data-testid="component-plan-linked-work" style={{ display: 'grid', gap: 10 }}>
                <div>
                  <h4 style={{ margin: '0 0 4px', fontSize: 11, color: t.textMuted }}>
                    Requirement IDs
                  </h4>
                  {selectedRole.requirementIds.length ? (
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                      {selectedRole.requirementIds.map((id) => (
                        <li key={id}>{id}</li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>None mapped.</p>
                  )}
                </div>
                <div>
                  <h4 style={{ margin: '0 0 4px', fontSize: 11, color: t.textMuted }}>
                    Architecture node IDs
                  </h4>
                  {selectedRole.architectureNodeIds.length ? (
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                      {selectedRole.architectureNodeIds.map((id) => (
                        <li key={id}>{id}</li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>None mapped.</p>
                  )}
                </div>
                <div>
                  <h4 style={{ margin: '0 0 4px', fontSize: 11, color: t.textMuted }}>
                    Open questions
                  </h4>
                  {(selectedRole.openQuestionIds?.length
                    ? selectedRole.openQuestionIds
                    : content.openQuestions.map((q) => q.questionId)
                  ).length ? (
                    <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: t.text }}>
                      {(selectedRole.openQuestionIds?.length
                        ? selectedRole.openQuestionIds.map((id) => {
                            const q = content.openQuestions.find((item) => item.questionId === id);
                            return q?.summary ?? id;
                          })
                        : content.openQuestions.map((q) => q.summary ?? q.questionId)
                      ).map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ margin: 0, fontSize: 12, color: t.textSec }}>No open questions.</p>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </section>
      </div>

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

const thStyle: CSSProperties = {
  padding: '8px 10px',
  fontWeight: 600,
  fontSize: 11,
  position: 'sticky',
  top: 0,
  background: 'inherit',
};

const tdStyle: CSSProperties = {
  padding: '10px',
  verticalAlign: 'top',
};

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
        Compatibility:{' '}
        {checks.length ? checks.map((c) => `${c.checkType}:${c.status}`).join(', ') : 'none'}
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

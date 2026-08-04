import { useCallback, useEffect, useState } from 'react';
import type {
  Artifact,
  ArtifactCommand,
  ArtifactCommandResult,
  ComponentPlanContent,
  WorkspaceDescriptor,
} from '@nexus/contracts';
import {
  ApiClientError,
  createWorkspace,
  getWorkspace,
  submitArtifactCommand,
} from '../../api/client';
import { themeColors } from '../../lib/theme';
import { StatusBadge } from '../../components/statuses/StatusBadge';

type Props = {
  projectId: string;
  artifact?: Extract<Artifact, { artifactType: 'component-plan' }>;
  isDark: boolean;
  onCommandResult?: (result: ArtifactCommandResult) => void;
};

const EMPTY_CONTENT: ComponentPlanContent = {
  approvalStatus: 'not-required',
  candidateCount: 0,
  constraintSummary: 'No component-plan constraints loaded yet.',
  selectionState: 'draft',
  unresolvedCompatibilityChecks: [],
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

export function ComponentPlanWorkspace({ projectId, artifact, isDark, onCommandResult }: Props) {
  const t = themeColors(isDark);
  const content = artifact?.content ?? EMPTY_CONTENT;
  const [workspace, setWorkspace] = useState<WorkspaceDescriptor | null>(null);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [commandBusy, setCommandBusy] = useState(false);
  const [commandMessage, setCommandMessage] = useState<string | null>(null);

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

  const candidates: Array<{ id: string; name: string; notes: string }> = [];

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
        }}
      >
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <strong style={{ fontSize: 13, color: t.text }}>Selection</strong>
          <StatusBadge status={content.selectionState} />
          <StatusBadge status={content.approvalStatus} />
          <span style={{ fontSize: 12, color: t.textMuted }}>
            Candidates: {content.candidateCount}
          </span>
        </div>
        <p style={{ margin: '10px 0 0', fontSize: 13, color: t.textSec }}>
          {content.constraintSummary}
        </p>
      </section>

      <section
        style={{
          border: `1px solid ${t.border}`,
          borderRadius: 8,
          padding: 14,
          background: t.surface,
        }}
      >
        <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>Candidate comparison</h3>
        {candidates.length === 0 ? (
          <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
            No candidates loaded. Comparison rows will appear when retrieval and plan generation
            produce component options.
          </p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, color: t.text }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: '6px 4px' }}>Candidate</th>
                <th style={{ textAlign: 'left', padding: '6px 4px' }}>Notes</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((row) => (
                <tr key={row.id}>
                  <td style={{ padding: '6px 4px', borderTop: `1px solid ${t.border}` }}>
                    {row.name}
                  </td>
                  <td style={{ padding: '6px 4px', borderTop: `1px solid ${t.border}` }}>
                    {row.notes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section
        style={{
          border: `1px solid ${t.border}`,
          borderRadius: 8,
          padding: 14,
          background: t.surface,
        }}
      >
        <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>
          Unresolved compatibility checks
        </h3>
        {content.unresolvedCompatibilityChecks.length ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: t.text }}>
            {content.unresolvedCompatibilityChecks.map((check) => (
              <li key={check}>{check}</li>
            ))}
          </ul>
        ) : (
          <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>No unresolved checks recorded.</p>
        )}
      </section>

      <section
        style={{
          border: `1px dashed ${t.border}`,
          borderRadius: 8,
          padding: 14,
          background: t.surface,
        }}
        data-testid="component-plan-retrieval-notice"
      >
        <h3 style={{ margin: '0 0 8px', fontSize: 12, color: t.textMuted }}>Retrieval</h3>
        <p style={{ margin: 0, fontSize: 13, color: t.textSec }}>
          Datasheet and supplier retrieval is unavailable in this proof workspace. Candidate evidence
          will attach here when retrieval providers are connected.
        </p>
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
          <CommandButton
            label="Create / refresh workspace"
            disabled={commandBusy}
            isDark={isDark}
            onClick={() => void ensureWorkspace().then(() => refreshWorkspace())}
          />
          <CommandButton
            label="Create snapshot"
            disabled={commandBusy || !artifact}
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
                input: { reason: 'Manual snapshot from component-plan proof workspace' },
              }))
            }
          />
          <CommandButton
            label="Propose revision"
            disabled={commandBusy || !artifact || !workspace?.currentSnapshotId}
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
                  summary: 'Propose component-plan revision from proof workspace',
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

function CommandButton({
  label,
  disabled,
  isDark,
  onClick,
}: {
  label: string;
  disabled?: boolean;
  isDark: boolean;
  onClick: () => void;
}) {
  const t = themeColors(isDark);
  return (
    <button
      type="button"
      disabled={disabled}
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

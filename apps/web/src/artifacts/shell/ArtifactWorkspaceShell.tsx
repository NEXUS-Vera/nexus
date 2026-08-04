import type { ReactNode } from 'react';
import { WorkspaceHeader } from '../../components/layout/WorkspaceHeader';
import { StatusBadge } from '../../components/statuses/StatusBadge';
import { themeColors } from '../../lib/theme';

export type ArtifactWorkspaceShellProps = {
  title: string;
  subtitle?: string;
  version?: number;
  lifecycleStatus?: string;
  evidenceStatus?: string;
  approvalStatus?: string;
  changeIndicator?: string;
  workspaceStatus?: string | null;
  proposalStatus?: string | null;
  executionStatus?: string | null;
  conflictMessage?: string | null;
  isDark: boolean;
  loading?: boolean;
  error?: string | null;
  actions?: ReactNode;
  children: ReactNode;
  testId?: string;
};

export function ArtifactWorkspaceShell({
  title,
  subtitle,
  version,
  lifecycleStatus,
  evidenceStatus,
  approvalStatus,
  changeIndicator,
  workspaceStatus,
  proposalStatus,
  executionStatus,
  conflictMessage,
  isDark,
  loading = false,
  error = null,
  actions,
  children,
  testId,
}: ArtifactWorkspaceShellProps) {
  const t = themeColors(isDark);
  const showStateStrip =
    Boolean(workspaceStatus) ||
    Boolean(proposalStatus) ||
    Boolean(executionStatus) ||
    Boolean(conflictMessage);

  return (
    <div
      style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
      data-testid={testId}
    >
      <WorkspaceHeader
        title={title}
        subtitle={subtitle}
        version={version}
        lifecycleStatus={lifecycleStatus}
        evidenceStatus={evidenceStatus}
        approvalStatus={approvalStatus}
        changeIndicator={changeIndicator}
        isDark={isDark}
        actions={actions}
      />

      {showStateStrip ? (
        <div
          data-testid="workspace-state-strip"
          style={{
            display: 'flex',
            gap: 8,
            flexWrap: 'wrap',
            alignItems: 'center',
            padding: '8px 16px',
            borderBottom: `1px solid ${t.border}`,
            background: t.surface,
            fontSize: 12,
            color: t.textSec,
          }}
        >
          {workspaceStatus ? (
            <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              Workspace <StatusBadge status={workspaceStatus} />
            </span>
          ) : null}
          {proposalStatus ? (
            <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              Proposal <StatusBadge status={proposalStatus} />
            </span>
          ) : null}
          {executionStatus ? (
            <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              Execution <StatusBadge status={executionStatus} />
            </span>
          ) : null}
          {conflictMessage ? (
            <span role="status" style={{ color: t.text, fontWeight: 600 }}>
              Conflict: {conflictMessage}
            </span>
          ) : null}
        </div>
      ) : null}

      {loading ? (
        <div
          style={{ flex: 1, display: 'grid', placeItems: 'center', background: t.bg, color: t.textSec }}
          aria-live="polite"
        >
          Loading workspace…
        </div>
      ) : null}

      {!loading && error ? (
        <div
          role="alert"
          style={{
            margin: 16,
            padding: 12,
            borderRadius: 8,
            border: `1px solid ${t.border}`,
            background: t.surface,
            color: t.text,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      ) : null}

      {!loading ? (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {children}
        </div>
      ) : null}
    </div>
  );
}

import type { ReactNode } from 'react';
import { themeColors } from '../../lib/theme';
import { EvidenceBadge } from '../statuses/EvidenceBadge';
import { StatusBadge } from '../statuses/StatusBadge';

type WorkspaceHeaderProps = {
  title: string;
  subtitle?: string;
  version?: number;
  lifecycleStatus?: string;
  evidenceStatus?: string;
  approvalStatus?: string;
  changeIndicator?: string;
  isDark: boolean;
  actions?: ReactNode;
};

export function WorkspaceHeader({
  title,
  subtitle,
  version,
  lifecycleStatus,
  evidenceStatus,
  approvalStatus,
  changeIndicator,
  isDark,
  actions,
}: WorkspaceHeaderProps) {
  const t = themeColors(isDark);
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 12,
        padding: '14px 16px',
        borderBottom: `1px solid ${t.border}`,
        background: t.surface,
        flexShrink: 0,
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: t.text }}>{title}</h2>
          {version != null ? (
            <span style={{ fontSize: 12, color: t.textMuted }} data-testid="artifact-revision-badge">
              {title} · v{version}
            </span>
          ) : null}
          {lifecycleStatus ? <StatusBadge status={lifecycleStatus} /> : null}
          {evidenceStatus ? <EvidenceBadge status={evidenceStatus} /> : null}
          {approvalStatus ? <StatusBadge status={approvalStatus} /> : null}
          {changeIndicator ? <StatusBadge status={changeIndicator} /> : null}
        </div>
        {subtitle ? (
          <p style={{ margin: '6px 0 0', fontSize: 12, color: t.textSec }}>{subtitle}</p>
        ) : null}
      </div>
      {actions}
    </header>
  );
}

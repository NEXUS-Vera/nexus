import {
  AlertOctagon,
  CheckCircle2,
  FlaskConical,
  GitBranch,
  HelpCircle,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import type { ElementType } from 'react';

type EvidenceBadgeProps = {
  /** Canonical contract evidenceStatus values. */
  status: string;
  showLabel?: boolean;
};

const STATE_MAP: Record<
  string,
  { icon: ElementType; color: string; bg: string; label: string; tooltip: string }
> = {
  grounded: {
    icon: CheckCircle2,
    color: '#159A7A',
    bg: 'rgba(21,154,122,0.1)',
    label: 'Grounded',
    tooltip: 'Supported by direct or strong evidence',
  },
  'partially-grounded': {
    icon: HelpCircle,
    color: '#D58A12',
    bg: 'rgba(213,138,18,0.1)',
    label: 'Partially grounded',
    tooltip: 'Some supporting evidence exists',
  },
  inferred: {
    icon: GitBranch,
    color: '#64748B',
    bg: 'rgba(100,116,139,0.1)',
    label: 'Inferred',
    tooltip: 'Derived by agent inference',
  },
  calculated: {
    icon: FlaskConical,
    color: '#168AAD',
    bg: 'rgba(22,138,173,0.1)',
    label: 'Calculated',
    tooltip: 'Derived from deterministic calculation',
  },
  tested: {
    icon: ShieldCheck,
    color: '#168AAD',
    bg: 'rgba(22,138,173,0.1)',
    label: 'Tested',
    tooltip: 'Covered by test evidence',
  },
  unverified: {
    icon: HelpCircle,
    color: '#8A94A3',
    bg: 'rgba(138,148,163,0.1)',
    label: 'Unverified',
    tooltip: 'Not yet grounded in evidence',
  },
  conflicted: {
    icon: AlertOctagon,
    color: '#D14343',
    bg: 'rgba(209,67,67,0.1)',
    label: 'Conflicted',
    tooltip: 'Contradicting evidence found',
  },
  stale: {
    icon: RefreshCw,
    color: '#858B98',
    bg: 'rgba(133,139,152,0.1)',
    label: 'Stale',
    tooltip: 'Evidence may be outdated',
  },
};

export function EvidenceBadge({ status, showLabel = true }: EvidenceBadgeProps) {
  const config = STATE_MAP[status] || {
    icon: HelpCircle,
    color: '#8A94A3',
    bg: 'rgba(138,148,163,0.1)',
    label: status,
    tooltip: 'Evidence status',
  };
  const Icon = config.icon;

  return (
    <span
      title={config.tooltip}
      aria-label={`Evidence: ${config.label}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: showLabel ? 4 : 0,
        padding: showLabel ? '2px 7px' : '2px 4px',
        borderRadius: 4,
        backgroundColor: config.bg,
        color: config.color,
        fontSize: 11,
        fontWeight: 500,
        whiteSpace: 'nowrap',
        border: `1px solid ${config.color}22`,
        lineHeight: 1.4,
      }}
    >
      <Icon size={11} strokeWidth={2} aria-hidden />
      {showLabel ? config.label : null}
    </span>
  );
}

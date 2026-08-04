import {
  AlertCircle,
  AlertTriangle,
  Ban,
  CheckCircle2,
  Circle,
  Pencil,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import type { ElementType } from 'react';

type StatusBadgeProps = {
  status: string;
  size?: 'sm' | 'md';
};

const STATUS_MAP: Record<
  string,
  { icon: ElementType; color: string; bg: string; label: string }
> = {
  drafted: { icon: Pencil, color: '#8A94A3', bg: 'rgba(138,148,163,0.1)', label: 'Drafted' },
  ready: { icon: CheckCircle2, color: '#159A7A', bg: 'rgba(21,154,122,0.1)', label: 'Ready' },
  affected: { icon: AlertTriangle, color: '#DC6B20', bg: 'rgba(220,107,32,0.1)', label: 'Affected' },
  stale: { icon: RefreshCw, color: '#858B98', bg: 'rgba(133,139,152,0.1)', label: 'Stale' },
  blocked: { icon: Ban, color: '#D14343', bg: 'rgba(209,67,67,0.1)', label: 'Blocked' },
  superseded: { icon: RefreshCw, color: '#858B98', bg: 'rgba(133,139,152,0.1)', label: 'Superseded' },
  archived: { icon: Circle, color: '#8A94A3', bg: 'rgba(138,148,163,0.1)', label: 'Archived' },
  unavailable: { icon: Circle, color: '#8A94A3', bg: 'rgba(138,148,163,0.1)', label: 'Unavailable' },
  confirmed: { icon: CheckCircle2, color: '#159A7A', bg: 'rgba(21,154,122,0.1)', label: 'Confirmed' },
  proposed: { icon: Circle, color: '#3563E9', bg: 'rgba(53,99,233,0.1)', label: 'Proposed' },
  'needs-confirmation': {
    icon: AlertCircle,
    color: '#D58A12',
    bg: 'rgba(213,138,18,0.1)',
    label: 'Needs confirmation',
  },
  rejected: { icon: XCircle, color: '#D14343', bg: 'rgba(209,67,67,0.1)', label: 'Rejected' },
  Updated: { icon: RefreshCw, color: '#3563E9', bg: 'rgba(53,99,233,0.1)', label: 'Updated' },
  Regenerated: { icon: RefreshCw, color: '#159A7A', bg: 'rgba(21,154,122,0.1)', label: 'Regenerated' },
  Unchanged: { icon: Circle, color: '#8A94A3', bg: 'rgba(138,148,163,0.1)', label: 'Unchanged' },
  Affected: { icon: AlertTriangle, color: '#DC6B20', bg: 'rgba(220,107,32,0.1)', label: 'Affected' },
  Stale: { icon: RefreshCw, color: '#858B98', bg: 'rgba(133,139,152,0.1)', label: 'Stale' },
  Current: { icon: CheckCircle2, color: '#159A7A', bg: 'rgba(21,154,122,0.1)', label: 'Current' },
};

export function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const key = status.toLowerCase().replace(/\s+/g, '-');
  const config =
    STATUS_MAP[status] ||
    STATUS_MAP[key] || {
      icon: Circle,
      color: '#8A94A3',
      bg: 'rgba(138,148,163,0.1)',
      label: status,
    };
  const Icon = config.icon;
  const iconSize = size === 'sm' ? 11 : 13;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: size === 'sm' ? '2px 7px' : '3px 8px',
        borderRadius: 4,
        backgroundColor: config.bg,
        color: config.color,
        fontSize: size === 'sm' ? 11 : 12,
        fontWeight: 500,
        whiteSpace: 'nowrap',
        border: `1px solid ${config.color}22`,
        lineHeight: 1.4,
      }}
    >
      <Icon size={iconSize} strokeWidth={2} aria-hidden />
      <span>{config.label}</span>
    </span>
  );
}

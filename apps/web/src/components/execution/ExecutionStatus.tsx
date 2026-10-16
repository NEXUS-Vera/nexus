import type { ExecutionRun } from '@nexus/contracts';

const LABELS: Record<ExecutionRun['status'], string> = {
  queued: 'Queued',
  starting: 'Starting',
  running: 'Running',
  completed: 'Completed',
  'completed-with-warnings': 'Completed with warnings',
  failed: 'Failed',
  cancelled: 'Cancelled',
  'timed-out': 'Timed out',
  stale: 'Stale',
};

export function ExecutionStatus({ status }: { status: ExecutionRun['status'] }) {
  return (
    <span data-testid="execution-status" data-status={status}>
      {LABELS[status] ?? status}
    </span>
  );
}

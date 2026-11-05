import { USER_ACTOR } from '../../api/actor';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { useState } from 'react';
import * as api from '../../api/client';
import { RunLogModal } from './run-log-modal';
vi.mock('../../api/client', () => ({ getExecution: vi.fn(), getExecutionLogs: vi.fn(), startRepair: vi.fn(), advanceRepair: vi.fn() }));
const state = { repairId: 'repair_1', revision: 1, status: 'inspect', attempts: [{ runIds: ['run_1'] }] } as api.RepairState;
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getExecution).mockResolvedValue({ executionRun: { status: 'failed', capability: 'embedded-build' } as never });
  vi.mocked(api.getExecutionLogs).mockResolvedValue({ chunks: [{ sequence: 1, stream: 'stderr', content: 'compile failed\nAPI_KEY=private-value\nAuthorization: Bearer hidden-value' } as never], logTruncated: true });
  vi.mocked(api.startRepair).mockResolvedValue(state);
  vi.mocked(api.advanceRepair).mockResolvedValue({ ...state, status: 'review' });
});
function Harness() {
  const [repair, setRepair] = useState<api.RepairState>();
  return <RunLogModal projectId="p" runId="run_1" onClose={vi.fn()} repair={repair} setRepair={setRepair} />;
}
it('loads logs safely and repairs only on explicit clicks, preserving revision guards', async () => {
  render(<Harness />);
  expect(await screen.findByText(/compile failed/)).toBeInTheDocument();
  expect(screen.getByText('Log truncated')).toBeInTheDocument();
  expect(document.body.textContent).not.toContain('private-value');
  expect(document.body.textContent).not.toContain('hidden-value');
  expect(screen.queryByRole('combobox', { name: 'Repair target' })).not.toBeInTheDocument();
  expect(api.startRepair).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: /Diagnose/ }));
  await screen.findByText(/Repair: review/);
  expect(api.startRepair).toHaveBeenCalledWith('p', { executionRunId: 'run_1', target: 'firmware', maxAttempts: 3, requireReal: true, requestedBy: USER_ACTOR });
  expect(api.advanceRepair).toHaveBeenCalledWith('p', 'repair_1', 1, false, USER_ACTOR);
});
it('disables repair after three attempts and closes with Escape', async () => {
  const close = vi.fn();
  render(<RunLogModal projectId="p" runId="r" onClose={close} repair={{ ...state, attempts: [state.attempts[0], state.attempts[0], state.attempts[0]] }} setRepair={vi.fn()} />);
  await screen.findByText(/compile failed/);
  expect(screen.getByRole('button', { name: /Attempt 3 of 3/ })).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  expect(close).toHaveBeenCalledOnce();
});
it('shows a safe load failure', async () => {
  vi.mocked(api.getExecution).mockRejectedValue(new Error('internal-diagnostic-sentinel'));
  render(<Harness />);
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Unable to load run logs.'));
  expect(document.body.textContent).not.toContain('internal-diagnostic-sentinel');
});
it('does not restart the loop when an advance fails', async () => {
  vi.mocked(api.advanceRepair).mockRejectedValue(new Error('raw-upstream-detail'));
  render(<Harness />);
  await screen.findByText(/compile failed/);
  fireEvent.click(screen.getByRole('button', { name: /Diagnose/ }));
  await screen.findByText(/Repair request failed/);
  fireEvent.click(screen.getByRole('button', { name: /Diagnose/ }));
  await waitFor(() => expect(api.advanceRepair).toHaveBeenCalledTimes(2));
  expect(api.startRepair).toHaveBeenCalledOnce();
  expect(document.body.textContent).not.toContain('raw-upstream-detail');
});

it('offers explicit workspace review for a pending firmware repair', async () => {
  const review = vi.fn();
  render(<RunLogModal projectId="p" runId="r" onClose={vi.fn()} setRepair={vi.fn()}
    repair={{ ...state, status: 'review', target: 'firmware', proposalId: 'pending' }} onReviewPatch={review} />);
  await screen.findByText(/compile failed/);
  expect(review).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Review repair patch in Workspace' }));
  expect(review).toHaveBeenCalledWith('pending');
  expect(api.advanceRepair).not.toHaveBeenCalled();
});
it('defaults failed analysis repairs to firmware', async () => {
  vi.mocked(api.getExecution).mockResolvedValue({ executionRun: { status: 'failed', capability: 'python-kernel' } as never });
  render(<Harness />);
  const target = await screen.findByRole('combobox', { name: 'Repair target' });
  expect(target).toHaveValue('firmware');
  expect(screen.getByRole('option', { name: 'Firmware (recommended)' })).toBeInTheDocument();
  expect(target).toHaveAccessibleDescription('Sampling/timing failures usually come from firmware.');
  expect(api.startRepair).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: /Diagnose/ }));
  await screen.findByText(/Repair: review/);
  expect(api.startRepair).toHaveBeenCalledWith('p', { executionRunId: 'run_1', target: 'firmware', maxAttempts: 3, requireReal: true, requestedBy: USER_ACTOR });
  expect(target).toBeDisabled();
});
it('sends the operator-selected analysis target', async () => {
  vi.mocked(api.getExecution).mockResolvedValue({ executionRun: { status: 'failed', capability: 'python-kernel' } as never });
  render(<Harness />);
  const target = await screen.findByRole('combobox', { name: 'Repair target' });
  expect(screen.getByRole('option', { name: 'Analysis code' })).toBeInTheDocument();
  fireEvent.change(target, { target: { value: 'analysis' } });
  expect(target).toHaveValue('analysis');
  fireEvent.click(screen.getByRole('button', { name: /Diagnose/ }));
  await screen.findByText(/Repair: review/);
  expect(api.startRepair).toHaveBeenCalledWith('p', { executionRunId: 'run_1', target: 'analysis', maxAttempts: 3, requireReal: true, requestedBy: USER_ACTOR });
});
it('offers the repair target choice for timed-out analysis runs', async () => {
  vi.mocked(api.getExecution).mockResolvedValue({ executionRun: { status: 'timed-out', capability: 'python-kernel' } as never });
  render(<Harness />);
  const target = await screen.findByRole('combobox', { name: 'Repair target' });
  expect(target).toHaveValue('firmware');
});

it('sends the live operator identity in start and advance JSON bodies', async () => {
  const client = await vi.importActual<typeof api>('../../api/client');
  vi.mocked(api.startRepair).mockImplementation(client.startRepair);
  vi.mocked(api.advanceRepair).mockImplementation(client.advanceRepair);
  const bodies: Record<string, unknown>[] = [];
  const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    bodies.push(body);
    return new Response(JSON.stringify(body.action === 'start' ? state : { ...state, status: 'review' }), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  try {
    render(<Harness />);
    await screen.findByText(/compile failed/);
    fireEvent.click(screen.getByRole('button', { name: /Diagnose/ }));
    await screen.findByText(/Repair: review/);
    expect(bodies).toEqual([
      { action: 'start', executionRunId: 'run_1', target: 'firmware', maxAttempts: 3,
        requireReal: true, requestedBy: USER_ACTOR },
      { action: 'advance', repairId: 'repair_1', revision: 1, requestedBy: USER_ACTOR },
    ]);
    for (const body of bodies) {
      expect(body.requestedBy).toMatchObject({ actorId: USER_ACTOR.actorId });
    }
  } finally {
    vi.unstubAllGlobals();
  }
});

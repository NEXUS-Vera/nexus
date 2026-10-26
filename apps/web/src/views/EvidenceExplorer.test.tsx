import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { EvidenceExplorer } from './EvidenceExplorer';

vi.mock('../api/client', () => ({
  getVerificationEvidenceChain: vi.fn(),
}));

import { getVerificationEvidenceChain } from '../api/client';

describe('EvidenceExplorer', () => {
  beforeEach(() => {
    vi.mocked(getVerificationEvidenceChain).mockReset();
  });

  it('renders Requirement → Test → Evidence chain for R7/T7', async () => {
    vi.mocked(getVerificationEvidenceChain).mockResolvedValue({
      chains: [
        {
          requirementId: 'R7',
          verificationState: 'VERIFIED',
          testId: 'T7',
          testStatus: 'passed',
          assessment: 'PASS',
          assessmentAuthority: 'deterministic-code',
          actualResult: '0.0157 g',
          criterion: {
            criterionType: 'numeric-comparison',
            metricId: 'accel_x_rms_noise_g',
            operator: '<',
            expectedValue: 0.1,
          },
          evidenceReferences: [
            {
              evidenceId: 'evi_r7',
              sourceId: 'exec_GOLDEN_ANALYSIS_R7',
              sourceLocator: 'outputs/summary.json',
            },
          ],
          finding: 'Narrative explanation must not override PASS.',
        },
      ],
      requirementVerification: [],
    });

    render(
      <EvidenceExplorer
        projectId="proj_test"
        isDark={false}
        onOpenTestPlan={() => undefined}
        onOpenAnalysis={() => undefined}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId('evidence-chain-R7-T7')).toBeInTheDocument();
    });
    expect(screen.getByTestId('evidence-chain-R7-T7')).toHaveTextContent('VERIFIED');
    expect(screen.getByTestId('evidence-chain-R7-T7')).toHaveTextContent('PASS');
    expect(screen.getByTestId('evidence-chain-R7-T7')).toHaveTextContent(/0\.0157/);
    expect(screen.getByTestId('evidence-chain-R7-T7')).toHaveTextContent(
      /non-authoritative/i,
    );
    expect(screen.getByText('Open Test Plan')).toBeInTheDocument();
    expect(screen.getByText('Open Analysis')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Inspect Run Logs' })).not.toBeInTheDocument();
  });
  it.each(['STALE', 'RECHECK_REQUIRED'])('renders %s with its reason and historical PASS', async (state) => {
    vi.mocked(getVerificationEvidenceChain).mockResolvedValue({
      chains: [{
        requirementId: 'R7', testId: 'T7', verificationState: state,
        assessment: 'PASS',
        applicability: { state, reasons: [{
          reason: 'UNKNOWN_DEPENDENCY', triggerArtifactType: 'requirement-set',
          fromVersion: 1, toVersion: 2,
        }] },
      }],
      requirementVerification: [],
    });
    render(<EvidenceExplorer projectId="proj_test" isDark={false} />);
    const row = await screen.findByTestId('evidence-chain-R7-T7');
    expect(row).toHaveTextContent(`Applicability: ${state}`);
    expect(row).toHaveTextContent('UNKNOWN_DEPENDENCY');
    expect(row).toHaveTextContent('requirement-set v1 → v2');
    expect(row).toHaveTextContent('Assessment: PASS');
  });

  it('offers inspection only for rows with run IDs and only when opted in', async () => {
    vi.mocked(getVerificationEvidenceChain).mockResolvedValue({
      chains: [
        { requirementId: 'R1', testId: 'T1', executionRunId: 'exec_first' },
        { requirementId: 'R2', testId: 'T2', executionRunId: 'exec_second' },
        { requirementId: 'R3', testId: 'T3' },
      ], requirementVerification: [],
    });
    const onInspectRun = vi.fn();
    const { rerender } = render(<EvidenceExplorer projectId="proj_test" isDark={false} />);
    await screen.findByTestId('evidence-chain-R1-T1');
    expect(screen.queryByRole('button', { name: 'Inspect Run Logs' })).not.toBeInTheDocument();
    rerender(<EvidenceExplorer projectId="proj_test" isDark={false} onInspectRun={onInspectRun} />);
    for (const [requirement, test, run] of [['R1', 'T1', 'exec_first'], ['R2', 'T2', 'exec_second']]) {
      fireEvent.click(within(screen.getByTestId(`evidence-chain-${requirement}-${test}`)).getByRole('button', { name: 'Inspect Run Logs' }));
      expect(onInspectRun).toHaveBeenLastCalledWith(run);
    }
    expect(onInspectRun).toHaveBeenCalledTimes(2);
    expect(within(screen.getByTestId('evidence-chain-R3-T3')).queryByRole('button')).not.toBeInTheDocument();
    rerender(<EvidenceExplorer projectId="proj_test" isDark={false} />);
    expect(screen.queryByRole('button', { name: 'Inspect Run Logs' })).not.toBeInTheDocument();
  });

});

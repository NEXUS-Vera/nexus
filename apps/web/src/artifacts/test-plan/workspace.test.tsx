import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { TestPlanWorkspace } from './workspace';
import type { Artifact } from '@nexus/contracts';
import { getExecution, listProducedOutputs } from '../../api/client';

import golden from '../../../../../packages/contracts/examples/valid/esp32-imu-vibration-monitor/test-plan-artifact.json';

vi.mock('../../api/client', () => ({ getExecution: vi.fn(), listProducedOutputs: vi.fn() }));

function withPromotedR7(base: typeof golden) {
  const content = structuredClone(base.content) as Record<string, unknown>;
  const cases = (content.testCases as Array<Record<string, unknown>>).map((c) => {
    if (c.displayId === 'T7') {
      return {
        ...c,
        status: 'passed',
        assessment: 'PASS',
        assessmentAuthority: 'deterministic-code',
        actualResult: '0.0157 g',
        evidenceReferences: [
          {
            schemaVersion: '1.0.0',
            evidenceId: 'evi_16GOLDENT7ANALYSISOUT000001',
            sourceType: 'test-result',
            sourceId: 'exec_GOLDEN_ANALYSIS_R7',
            evidenceStrength: 'direct',
            supportedClaim: 'accel_x_rms_noise_g < 0.10 g',
            sourceLocator: 'outputs/summary.json',
          },
        ],
      };
    }
    return c;
  });
  const coverage = content.coverageSummary as Record<string, unknown>;
  content.testCases = cases;
  content.coverageSummary = {
    ...coverage,
    verifiedRequirements: 1,
    unverifiedRequirements: 7,
  };
  return { ...base, content } as unknown as Extract<Artifact, { artifactType: 'test-plan' }>;
}

describe('TestPlanWorkspace', () => {
  it('shows golden coverage starting ready/unverified before promotion', () => {
    const artifact = golden as unknown as Extract<Artifact, { artifactType: 'test-plan' }>;
    render(
      <TestPlanWorkspace
        artifact={artifact}
        isDark={false}
        selectedTestId="T7"
        onSelectTest={() => undefined}
        requirementStatements={{ R7: 'Stationary accel_x RMS noise < 0.10 g' }}
      />,
    );
    expect(screen.getByTestId('test-plan-coverage-summary')).toHaveTextContent('8 / 8');
    expect(screen.getByTestId('test-plan-coverage-R7')).toHaveTextContent('UNVERIFIED');
  });

  it('shows R7 VERIFIED after evidence promotion with deterministic authority', () => {
    const artifact = withPromotedR7(golden);
    render(
      <TestPlanWorkspace
        artifact={artifact}
        isDark={false}
        selectedTestId="T7"
        onSelectTest={() => undefined}
        requirementStatements={{ R7: 'Stationary accel_x RMS noise < 0.10 g' }}
      />,
    );
    expect(screen.getByTestId('test-plan-coverage-R7')).toHaveTextContent('VERIFIED');
    fireEvent.click(screen.getByTestId('test-plan-tab-tests'));
    expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('PASS');
    expect(screen.getByTestId('test-plan-assessment-authority')).toHaveTextContent(/Deterministic/i);
    expect(screen.getByTestId('test-plan-evidence')).toBeInTheDocument();
    expect(screen.getByTestId('test-plan-detail')).toHaveTextContent(/0\.0157/);
  });

  it.each([
    { state: 'STALE' as const, reasons: ['INPUT_REVISED'], assessment: 'PASS' as const },
    { state: 'CURRENT' as const, reasons: [], assessment: 'PASS' as const },
    { state: 'RECHECK_REQUIRED' as const, reasons: ['INPUT_REVISED', 'TRANSITIVE_DEPENDENCY_CHANGED'], assessment: 'FAIL' as const },
  ])('shows $state applicability alongside historical $assessment', ({ state, reasons, assessment }) => {
    const artifact = withPromotedR7(golden);
    const testCase = artifact.content.testCases.find((c) => c.displayId === 'T7')!;
    testCase.assessment = assessment;
    testCase.status = assessment === 'PASS' ? 'passed' : 'failed';
    testCase.applicability = {
      state,
      reasons: reasons.map((reason) => ({
        reason,
        eventId: 'event-input-revised',
        fromVersion: 1,
        toVersion: 2,
        path: ['requirement-set', 'test-plan'],
        triggerArtifactId: 'artifact-requirements',
        triggerArtifactType: 'requirement-set',
      })),
    };
    render(
      <TestPlanWorkspace artifact={artifact} isDark={false} selectedTestId="T7" onSelectTest={() => undefined} />,
    );
    const detail = within(screen.getByTestId('test-plan-assessment'));
    expect(detail.getByText(assessment)).toBeVisible();
    expect(detail.getByText(state)).toBeVisible();
    expect(detail.getByText(state)).toHaveStyle({ color: state === 'CURRENT' ? '#15803d' : '#b45309' });
    for (const reason of reasons) expect(detail.getByText(reason)).toBeVisible();
    fireEvent.click(screen.getByTestId('test-plan-tab-tests'));
    const row = within(screen.getByTestId('test-plan-case-T7'));
    expect(row.getByText(state)).toBeVisible();
    expect(screen.getByTestId('test-plan-case-T7')).toHaveTextContent(assessment);
    for (const reason of reasons) expect(row.getByText(reason)).toBeVisible();
    // Cases without applicability keep their existing status presentation.
    expect(within(screen.getByTestId('test-plan-case-T1')).queryByText(state)).not.toBeInTheDocument();
  });

  it('surfaces FAIL, BLOCKED, and INCONCLUSIVE assessment states', () => {
    const base = structuredClone(golden.content) as Record<string, unknown>;
    const cases = (base.testCases as Array<Record<string, unknown>>).map((c) => {
      if (c.displayId === 'T7') {
        return {
          ...c,
          status: 'failed',
          assessment: 'FAIL',
          assessmentAuthority: 'deterministic-code',
          actualResult: '0.12 g',
        };
      }
      if (c.displayId === 'T4') {
        return { ...c, status: 'blocked', assessment: undefined };
      }
      if (c.displayId === 'T6') {
        return {
          ...c,
          status: 'inconclusive',
          assessment: 'INCONCLUSIVE',
          assessmentAuthority: 'deterministic-code',
        };
      }
      return c;
    });
    const artifact = {
      ...golden,
      content: { ...base, testCases: cases },
    } as unknown as Extract<Artifact, { artifactType: 'test-plan' }>;
    render(
      <TestPlanWorkspace
        artifact={artifact}
        isDark={false}
        selectedTestId="T7"
        onSelectTest={() => undefined}
        requirementStatements={{ R4: 'init', R6: 'rate', R7: 'noise' }}
      />,
    );
    expect(screen.getByTestId('test-plan-coverage-R7')).toHaveTextContent('FAILED');
    expect(screen.getByTestId('test-plan-coverage-R4')).toHaveTextContent('BLOCKED');
    expect(screen.getByTestId('test-plan-coverage-R6')).toHaveTextContent('INCONCLUSIVE');
    fireEvent.click(screen.getByTestId('test-plan-tab-tests'));
    expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('FAIL');
  });

  it('surfaces uncovered requirements instead of hiding them', () => {
    const artifact = {
      ...(golden as object),
      content: {
        ...(golden as { content: Record<string, unknown> }).content,
        testCases: (
          (golden as { content: { testCases: unknown[] } }).content.testCases as unknown[]
        ).filter((c) => (c as { displayId: string }).displayId !== 'T8'),
        coverageSummary: {
          totalRequirements: 8,
          coveredRequirements: 7,
          verifiedRequirements: 0,
          failedRequirements: 0,
          blockedRequirements: 0,
          unverifiedRequirements: 7,
          uncoveredRequirements: 1,
        },
      },
    } as unknown as Extract<Artifact, { artifactType: 'test-plan' }>;
    render(
      <TestPlanWorkspace
        artifact={artifact}
        isDark={false}
        selectedTestId="T7"
        onSelectTest={() => undefined}
        requirementStatements={{
          R1: 'a',
          R2: 'b',
          R3: 'c',
          R4: 'd',
          R5: 'e',
          R6: 'f',
          R7: 'g',
          R8: 'Analysis deliverables',
        }}
      />,
    );
    expect(screen.getByTestId('test-plan-coverage-R8')).toHaveTextContent('UNCOVERED');
    expect(screen.getByTestId('test-plan-uncovered-R8')).toBeInTheDocument();
  });
});

describe('criterion evidence disclosure', () => {
  beforeEach(() => {
    vi.mocked(getExecution).mockReset();
    vi.mocked(listProducedOutputs).mockReset();
  });

  function setup(artifact = withPromotedR7(golden)) {
    render(<TestPlanWorkspace artifact={artifact} isDark={false} selectedTestId="T7" onSelectTest={() => undefined} />);
    fireEvent.click(screen.getByTestId('test-plan-tab-tests'));
    return screen.getByTestId('test-plan-case-T7').parentElement!;
  }

  async function toggle(card: HTMLElement, open: boolean) {
    const disclosure = card.querySelector('details')!;
    fireEvent.click(within(card).getByText('View Evidence'));
    await waitFor(() => {
      expect(disclosure.open).toBe(open);
      expect(disclosure.querySelector('div') !== null).toBe(open);
    });
    return disclosure;
  }

  it('toggles each card independently and renders artifact evidence without a network request', async () => {
    const artifact = withPromotedR7(golden);
    const c = artifact.content.testCases.find((item) => item.displayId === 'T7')!;
    c.actualResult = 'line one\n  line two <script>alert(1)</script>';
    const card = setup(artifact);
    expect(within(card).queryByText('Assessment authority:')).not.toBeInTheDocument();
    await toggle(card, true);
    expect(card).toHaveTextContent('deterministic-code');
    expect(card).toHaveTextContent('exec_GOLDEN_ANALYSIS_R7');
    expect(card).toHaveTextContent('outputs/summary.json');
    const observation = card.querySelector('pre')!;
    expect(observation.textContent).toBe(c.actualResult);
    expect(observation).toHaveStyle({ whiteSpace: 'pre-wrap' });
    expect(card.querySelector('script')).toBeNull();
    expect(card).toHaveTextContent('Evaluation timestamp (ISO): Not provided');
    expect(getExecution).not.toHaveBeenCalled();
    expect(screen.getByTestId('test-plan-case-T1').parentElement!.querySelector('details')!.open).toBe(false);
    await toggle(card, false);
    expect(card.querySelector('pre')).toBeNull();
  });

  it('loads existing run and output provenance and bounds long observations', async () => {
    const artifact = withPromotedR7(golden);
    const c = artifact.content.testCases.find((item) => item.displayId === 'T7')!;
    c.executionRunId = 'run-7';
    c.verificationBasis = { executionRunId: 'run-7', inputSnapshotId: 'snapshot-7', dependencies: [
      { artifactId: 'firmware-1', artifactType: 'firmware', artifactVersion: 3, contentHash: 'sha256-source' },
    ] };
    vi.mocked(getExecution).mockResolvedValue({ executionRun: {
      executionRunId: 'run-7', completedAt: '2026-11-06T05:00:00Z', workspaceId: 'workspace-7',
    } } as Awaited<ReturnType<typeof getExecution>>);
    vi.mocked(listProducedOutputs).mockResolvedValue([{
      schemaVersion: '1.0.0', artifactId: 'artifact-7', createdAt: '2026-11-06T05:00:00Z',
      evidenceStatus: 'tested', mediaType: 'text/plain', outputType: 'log', projectId: artifact.projectId, workspaceId: 'workspace-7', supports: [],
      outputId: 'output-7', executionRunId: 'run-7', name: 'serial.log', contentDigest: 'sha256-output',
      content: { kind: 'inline-structured', structuredResult: { text: 'x'.repeat(4001), inputSha256: 'sha256-input', firmwareOutputId: 'elf-7' } },
    }] as Awaited<ReturnType<typeof listProducedOutputs>>);
    const card = setup(artifact);
    expect(getExecution).not.toHaveBeenCalled();
    await toggle(card, true);
    await waitFor(() => expect(card).toHaveTextContent('sha256-input'));
    expect(getExecution).toHaveBeenCalledWith(artifact.projectId, 'run-7');
    expect(listProducedOutputs).toHaveBeenCalledWith(artifact.projectId, 'run-7');
    for (const value of ['2026-11-06T05:00:00Z', 'workspace-7', 'snapshot-7', 'firmware-1 v3', 'sha256-source', 'sha256-output', 'elf-7']) {
      expect(card).toHaveTextContent(value);
    }
    expect(card.querySelector('pre')!.textContent).toHaveLength(4000);
    expect(card).toHaveTextContent('Excerpt truncated to 4000 characters.');
  });

  it.each(['planned', 'ready', 'blocked'] as const)('keeps a stable pending state for %s criteria with missing evidence', async (status) => {
    const artifact = structuredClone(golden) as unknown as Extract<Artifact, { artifactType: 'test-plan' }>;
    const c = artifact.content.testCases.find((item) => item.displayId === 'T7')!;
    c.status = status;
    delete c.evidenceReferences;
    delete c.actualResult;
    const card = setup(artifact);
    await toggle(card, true);
    expect(card).toHaveTextContent('Evidence pending evaluation');
    expect(card).toHaveTextContent('Observation not provided');
    expect(card.querySelector('details > div')).toHaveStyle({ minHeight: '100px' });
    expect(getExecution).not.toHaveBeenCalled();
  });

  it('retains artifact evidence on provenance failure and permits retry', async () => {
    const artifact = withPromotedR7(golden);
    artifact.content.testCases.find((item) => item.displayId === 'T7')!.executionRunId = 'run-7';
    vi.mocked(getExecution).mockRejectedValue(new Error('offline'));
    vi.mocked(listProducedOutputs).mockResolvedValue([]);
    const card = setup(artifact);
    await toggle(card, true);
    expect(await within(card).findByRole('alert')).toHaveTextContent('Execution provenance unavailable');
    expect(card).toHaveTextContent('0.0157 g');
    await toggle(card, false);
    await toggle(card, true);
    await waitFor(() => expect(getExecution).toHaveBeenCalledTimes(2));
  });
});

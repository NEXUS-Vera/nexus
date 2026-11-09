import { useState } from 'react';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { USER_ACTOR } from '../../api/actor';
import { TestPlanWorkspace } from './workspace';
import type { Artifact } from '@nexus/contracts';
import { getExecution, listProducedOutputs } from '../../api/client';
import golden from '../../../../../packages/contracts/examples/valid/esp32-imu-vibration-monitor/test-plan-artifact.json';

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return {
    ...actual,
    getExecution: vi.fn(),
    listProducedOutputs: vi.fn(),
  };
});

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

function stalePlan(state: 'STALE' | 'RECHECK_REQUIRED' | 'CURRENT' = 'STALE') {
  const artifact = withPromotedR7(golden);
  artifact.content.testCases.find((c) => c.displayId === 'T7')!.applicability = {
    state, reasons: state === 'CURRENT' ? [] : [{ reason: 'INPUT_REVISED', eventId: 'event-input-revised', fromVersion: 1, toVersion: 2, path: ['requirement-set', 'test-plan'], triggerArtifactId: 'artifact-requirements', triggerArtifactType: 'requirement-set' }],
  };
  return artifact;
}

function mountPlan(artifact = stalePlan()) {
  return render(<TestPlanWorkspace artifact={artifact} isDark={false} selectedTestId="T7" onSelectTest={() => undefined} />);
}

function response(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), { status });
}

describe('Test Plan re-verification', () => {
  afterEach(() => vi.unstubAllGlobals());

  it.each(['STALE', 'RECHECK_REQUIRED', 'CURRENT'] as const)('enables only stale criteria: %s', (state) => {
    mountPlan(stalePlan(state));
    expect(screen.getByRole('button', { name: 'Re-verify Stale Criteria' })).toHaveProperty('disabled', state === 'CURRENT');
  });

  it('disables re-verification when applicability is absent', () => {
    mountPlan(withPromotedR7(golden));
    expect(screen.getByRole('button', { name: 'Re-verify Stale Criteria' })).toBeDisabled();
  });

  it('posts real verification as the user, shows loading, and uses the refreshed plan in place', async () => {
    let finish!: (value: Response) => void;
    const refreshed = stalePlan('CURRENT');
    refreshed.updatedAt = '2026-11-06T12:00:00Z';
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => new Promise<Response>((resolve) => { finish = resolve; }))
      .mockResolvedValueOnce(response(refreshed));
    vi.stubGlobal('fetch', fetchMock);
    const original = stalePlan();
    mountPlan(original);
    fireEvent.click(screen.getByTestId('test-plan-tab-tests'));
    fireEvent.click(screen.getByRole('button', { name: 'Re-verify Stale Criteria' }));
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`http://127.0.0.1:8000/v1/projects/${original.projectId}/verify`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ requireReal: true, requestedBy: USER_ACTOR });
    expect(screen.getByRole('button', { name: 'Evaluating…' })).toBeDisabled();
    expect(within(screen.getByTestId('test-plan-case-T7')).getByRole('status')).toHaveTextContent('Evaluating');
    expect(within(screen.getByTestId('test-plan-case-T1')).queryByRole('status')).not.toBeInTheDocument();
    finish(response({}));
    await screen.findByText('Verification complete. Criteria are current.');
    expect(fetchMock.mock.calls[1][0]).toBe(`http://127.0.0.1:8000/v1/projects/${original.projectId}/artifacts/test-plan`);
    expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('CURRENT');
    expect(screen.getByTestId('test-plan-case-T7')).toHaveTextContent('CURRENT');
    expect(screen.queryByText('INPUT_REVISED')).not.toBeInTheDocument();
    expect(screen.getByText(refreshed.updatedAt)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Re-verify Stale Criteria' })).toBeDisabled();
    expect(original.content.testCases.find((c) => c.displayId === 'T7')!.applicability!.state).toBe('STALE');
  });

  it('preserves success after the parent artifact update and retains the refreshed plan across navigation', async () => {
    const refreshed = stalePlan('CURRENT');
    refreshed.artifactVersion += 1;
    refreshed.updatedAt = '2026-11-06T12:00:00Z';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response({})).mockResolvedValueOnce(response(refreshed)));
    function Parent() {
      const [artifact, setArtifact] = useState(stalePlan());
      const [visible, setVisible] = useState(true);
      return <>
        <button onClick={() => setVisible(!visible)}>Navigate</button>
        {visible && <TestPlanWorkspace artifact={artifact} onArtifactUpdate={setArtifact} isDark={false} selectedTestId="T7" onSelectTest={() => undefined} />}
      </>;
    }
    render(<Parent />);
    fireEvent.click(screen.getByRole('button', { name: 'Re-verify Stale Criteria' }));
    await waitFor(() => expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('CURRENT'));
    expect(screen.getByText('Verification complete. Criteria are current.')).toHaveAttribute('role', 'status');
    fireEvent.click(screen.getByRole('button', { name: 'Navigate' }));
    fireEvent.click(screen.getByRole('button', { name: 'Navigate' }));
    expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('CURRENT');
    expect(screen.getByRole('button', { name: 'Re-verify Stale Criteria' })).toBeDisabled();
  });

  it('handles a refreshed plan with omitted test cases', async () => {
    const refreshed = stalePlan('CURRENT');
    Reflect.deleteProperty(refreshed.content, 'testCases');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response({})).mockResolvedValueOnce(response(refreshed)));
    mountPlan();
    fireEvent.click(screen.getByRole('button', { name: 'Re-verify Stale Criteria' }));
    await screen.findByText('Verification complete. Criteria are current.');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it.each(['verify', 'refresh'])('preserves the plan on %s failure and permits retry', async (failure) => {
    const fetchMock = vi.fn();
    if (failure === 'refresh') fetchMock.mockResolvedValueOnce(response({}));
    fetchMock.mockResolvedValueOnce(response({ error: { message: 'Unavailable' } }, 503))
      .mockResolvedValueOnce(response({}))
      .mockResolvedValueOnce(response(stalePlan('CURRENT')));
    vi.stubGlobal('fetch', fetchMock);
    mountPlan();
    fireEvent.click(screen.getByRole('button', { name: 'Re-verify Stale Criteria' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Please retry');
    expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('STALE');
    expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('INPUT_REVISED');
    expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('PASS');
    fireEvent.click(screen.getByRole('button', { name: 'Retry Re-verify Stale Criteria' }));
    await waitFor(() => expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('CURRENT'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('retains stale badges returned by the server after a successful verify', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response({})).mockResolvedValueOnce(response(stalePlan())));
    mountPlan();
    fireEvent.click(screen.getByRole('button', { name: 'Re-verify Stale Criteria' }));
    await screen.findByText('Verification finished; some criteria still require re-verification.');
    expect(screen.getByTestId('test-plan-assessment')).toHaveTextContent('STALE');
    expect(screen.getByRole('button', { name: 'Re-verify Stale Criteria' })).toBeEnabled();
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


describe('Option B dynamic verification', () => {
  function completedPlan() {
    const artifact = structuredClone(golden) as unknown as Extract<Artifact, { artifactType: 'test-plan' }>;
    for (const c of artifact.content.testCases) {
      if (c.verificationMethod === 'inspection') {
        c.status = 'planned';
        delete c.assessment;
      } else {
        c.status = 'passed';
        c.assessment = 'PASS';
        c.assessmentAuthority = 'deterministic-code';
      }
    }
    return artifact;
  }

  it('shows 6/6 PASS and accessible manual-review badges without promoting inspections', () => {
    const artifact = completedPlan();
    mountPlan(artifact);
    expect(screen.getByRole('status')).toHaveTextContent('Dynamic Verification PASS (Option B, 6/6 cases)');
    expect(screen.getByRole('status')).toHaveTextContent('Manual-review cases are not established as PASS.');
    fireEvent.click(screen.getByRole('button', { name: 'Test cases' }));
    expect(screen.getAllByText('Manual Review (Option B)')).toHaveLength(2);
    expect(screen.getAllByText('Planned for manual inspection; does not block completion')).toHaveLength(2);
    for (const c of artifact.content.testCases.filter((item) => item.verificationMethod === 'inspection')) {
      const card = screen.getByRole('button', { name: new RegExp(`${c.displayId} — ${c.title}`) });
      expect(within(card).getByText('Manual Review (Option B)')).toBeVisible();
      expect(card).toHaveTextContent('PLANNED');
      expect(card).not.toHaveTextContent('PASS');
    }
  });

  it('names dynamic failures even when inspections remain planned', () => {
    const artifact = completedPlan();
    for (const c of artifact.content.testCases.filter((item) => item.verificationMethod === 'analysis')) {
      c.assessment = 'FAIL';
      c.status = 'failed';
    }
    mountPlan(artifact);
    const banner = screen.getByRole('alert');
    expect(banner).toHaveTextContent('Dynamic Verification FAIL (Option B)');
    for (const c of artifact.content.testCases.filter((item) => item.assessment === 'FAIL')) {
      expect(banner).toHaveTextContent(`${c.displayId} — ${c.title}`);
    }
    expect(screen.queryByText(/Dynamic Verification PASS/)).not.toBeInTheDocument();
  });

  it.each(['INCONCLUSIVE', 'planned', 'missing'] as const)('keeps %s dynamic cases in progress', (state) => {
    const artifact = completedPlan();
    const c = artifact.content.testCases.find((item) => item.verificationMethod !== 'inspection')!;
    if (state === 'INCONCLUSIVE') {
      c.assessment = 'INCONCLUSIVE';
      c.status = 'inconclusive';
    } else {
      delete c.assessment;
      if (state === 'planned') c.status = 'planned';
    }
    mountPlan(artifact);
    expect(screen.getByRole('status')).toHaveTextContent('Dynamic verification in progress (5/6 passed)');
    expect(screen.queryByText(/Dynamic Verification PASS/)).not.toBeInTheDocument();
  });

  it('renders no manual-review badges without inspection cases', () => {
    const artifact = completedPlan();
    const cases = artifact.content.testCases;
    cases.splice(0, cases.length, ...cases.filter((c) => c.verificationMethod !== 'inspection'));
    mountPlan(artifact);
    fireEvent.click(screen.getByRole('button', { name: 'Test cases' }));
    expect(screen.queryByText('Manual Review (Option B)')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Dynamic Verification PASS (Option B, 6/6 cases)');
  });

  it('never claims PASS when there are no dynamic cases', () => {
    const artifact = completedPlan();
    const cases = artifact.content.testCases;
    cases.splice(0, cases.length, ...cases.filter((c) => c.verificationMethod === 'inspection'));
    mountPlan(artifact);
    expect(screen.getByRole('status')).toHaveTextContent('Dynamic verification in progress (0/0 passed)');
    expect(screen.queryByText(/Dynamic Verification PASS/)).not.toBeInTheDocument();
  });
});

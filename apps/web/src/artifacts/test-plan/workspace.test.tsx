import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { USER_ACTOR } from '../../api/actor';
import { TestPlanWorkspace } from './workspace';
import type { Artifact } from '@nexus/contracts';
import golden from '../../../../../packages/contracts/examples/valid/esp32-imu-vibration-monitor/test-plan-artifact.json';

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

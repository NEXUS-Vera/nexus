import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
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

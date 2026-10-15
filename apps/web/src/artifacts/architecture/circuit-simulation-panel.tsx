import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ExecutionRun, ProducedOutput } from '@nexus/contracts';
import {
  ApiClientError,
  getCircuitSimulationExportUrl,
  getCircuitSimulationSupport,
  listExecutions,
  listProducedOutputs,
  validateCircuitSimulation,
  type CircuitSimulationSupportResponse,
  type CircuitSimulationValidationResponse,
} from '../../api/client';
import { themeColors } from '../../lib/theme';

type Props = {
  projectId: string;
  isDark: boolean;
  onRunSimulation: () => Promise<void>;
};

function displayStatus(value: string): string {
  return value.replaceAll('_', ' ').replaceAll('-', ' ');
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiClientError || error instanceof Error ? error.message : fallback;
}

export function CircuitSimulationPanel({ projectId, isDark, onRunSimulation }: Props) {
  const t = themeColors(isDark);
  const [support, setSupport] = useState<CircuitSimulationSupportResponse | null>(null);
  const [runs, setRuns] = useState<ExecutionRun[]>([]);
  const [outputs, setOutputs] = useState<ProducedOutput[]>([]);
  const [validation, setValidation] = useState<CircuitSimulationValidationResponse | null>(null);
  const [busy, setBusy] = useState<'refresh' | 'validate' | 'run' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showOutputs, setShowOutputs] = useState(false);

  const refresh = useCallback(async () => {
    setBusy('refresh');
    setError(null);
    const [supportResult, runsResult, outputsResult] = await Promise.allSettled([
      getCircuitSimulationSupport(projectId),
      listExecutions(projectId),
      listProducedOutputs(projectId),
    ]);
    if (supportResult.status === 'fulfilled') setSupport(supportResult.value);
    else setError(errorMessage(supportResult.reason, 'Unable to check simulation support.'));
    if (runsResult.status === 'fulfilled') setRuns(runsResult.value);
    if (outputsResult.status === 'fulfilled') setOutputs(outputsResult.value);
    setBusy(null);
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const simulationRuns = useMemo(
    () =>
      runs
        .filter((run) => run.capability === 'circuit-simulation')
        .sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt)),
    [runs],
  );
  const latestRun = simulationRuns[0];
  const simulationOutputs = useMemo(() => {
    const runIds = new Set(simulationRuns.map((run) => run.executionRunId));
    return outputs
      .filter((output) => runIds.has(output.executionRunId))
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }, [outputs, simulationRuns]);
  const hasWorkspaceExport = simulationOutputs.some(
    (output) => output.name === 'provider-workspace-manifest',
  );

  const availabilityReady =
    support?.providerAvailability.available === true &&
    support.providerAvailability.status.toUpperCase() === 'READY';
  const assessmentBlocksRun =
    !support ||
    support.assessment.status === 'UNSUPPORTED' ||
    support.assessment.status === 'FIRMWARE_REQUIRED' ||
    support.assessment.firmwareRequired;
  const runDisabled = busy !== null || !availabilityReady || assessmentBlocksRun;

  async function handleValidate(): Promise<void> {
    setBusy('validate');
    setError(null);
    try {
      setValidation(await validateCircuitSimulation(projectId));
    } catch (err) {
      setError(errorMessage(err, 'Provider representation validation failed.'));
    } finally {
      setBusy(null);
    }
  }

  async function handleRun(): Promise<void> {
    setBusy('run');
    setError(null);
    try {
      await onRunSimulation();
      await refresh();
    } catch (err) {
      setError(errorMessage(err, 'Circuit simulation failed.'));
      setBusy(null);
    }
  }

  const buttonStyle = {
    border: `1px solid ${t.border}`,
    borderRadius: 6,
    background: t.surface,
    color: t.text,
    padding: '5px 8px',
    fontSize: 11,
    cursor: 'pointer',
  } as const;

  return (
    <section
      aria-label="Circuit Simulation"
      data-testid="circuit-simulation-panel"
      style={{
        borderBottom: `1px solid ${t.border}`,
        background: t.surface2,
        padding: '10px 16px',
        color: t.text,
        fontSize: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <strong>Circuit Simulation</strong>
        <span data-testid="simulation-provider-health">
          Provider: {support ? displayStatus(support.providerAvailability.status) : 'checking'}
        </span>
        <span>
          Support: {support ? displayStatus(support.assessment.status) : 'checking'}
        </span>
        <span>
          Firmware: {support?.assessment.firmwareRequired ? 'required' : 'ready'}
        </span>
        {support?.assessment.surrogateUsed ? (
          <strong style={{ color: '#b7791f' }}>Surrogate model is being used.</strong>
        ) : null}
      </div>

      {support?.providerAvailability.message ? (
        <div style={{ marginTop: 5, color: t.textMuted }}>
          {support.providerAvailability.message}
        </div>
      ) : null}

      {(support?.assessment.findings.length ?? 0) > 0 ? (
        <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
          {support!.assessment.findings.map((finding) => (
            <li key={finding.findingId}>
              {displayStatus(finding.mappingType)}: {finding.message}
            </li>
          ))}
        </ul>
      ) : null}

      <div style={{ marginTop: 7, color: t.textMuted }}>
        Simulation checks the provider representation; it does not verify real component
        compatibility or physical hardware behavior.
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
        <button type="button" style={buttonStyle} disabled={busy !== null} onClick={() => void refresh()}>
          {busy === 'refresh' ? 'Checking…' : 'Check support'}
        </button>
        <button
          type="button"
          style={buttonStyle}
          disabled={busy !== null || !support?.providerAvailability.lintAvailable}
          onClick={() => void handleValidate()}
        >
          {busy === 'validate' ? 'Validating…' : 'Validate representation'}
        </button>
        <button
          type="button"
          style={buttonStyle}
          disabled={runDisabled}
          data-testid="run-circuit-simulation"
          onClick={() => void handleRun()}
        >
          {busy === 'run' ? 'Running…' : 'Run simulation'}
        </button>
        <button
          type="button"
          style={buttonStyle}
          disabled={simulationOutputs.length === 0}
          onClick={() => setShowOutputs((shown) => !shown)}
        >
          {showOutputs ? 'Hide outputs' : `Inspect outputs (${simulationOutputs.length})`}
        </button>
        {hasWorkspaceExport ? (
          <a
            href={getCircuitSimulationExportUrl(projectId)}
            style={{ ...buttonStyle, textDecoration: 'none' }}
          >
            Export workspace
          </a>
        ) : (
          <button type="button" style={buttonStyle} disabled>
            Export workspace
          </button>
        )}
      </div>

      {validation ? (
        <div data-testid="simulation-validation-result" style={{ marginTop: 7 }}>
          Validation: {validation.ok ? 'passed' : 'issues found'} · {validation.findings.length}{' '}
          finding(s)
        </div>
      ) : null}
      {latestRun ? (
        <div data-testid="latest-simulation-run" style={{ marginTop: 7 }}>
          Latest run: {displayStatus(latestRun.status)} · {latestRun.providerId} ·{' '}
          {latestRun.outputReferences.length} output reference(s)
        </div>
      ) : (
        <div style={{ marginTop: 7, color: t.textMuted }}>No circuit simulation runs yet.</div>
      )}
      {showOutputs ? (
        <div data-testid="simulation-outputs" style={{ marginTop: 7 }}>
          {simulationOutputs.map((output) => (
            <div key={output.outputId}>
              {output.name} · {displayStatus(output.outputType)} · {output.mediaType}
            </div>
          ))}
        </div>
      ) : null}
      {error ? <div role="alert" style={{ marginTop: 7, color: '#c53030' }}>{error}</div> : null}
    </section>
  );
}

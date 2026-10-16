import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ExecutionRun, ProducedOutput } from '@nexus/contracts';
import {
  ApiClientError,
  getCircuitSimulationExportUrl,
  getCircuitSimulationPreview,
  getCircuitSimulationSupport,
  getProducedOutput,
  listExecutions,
  listProducedOutputs,
  validateCircuitSimulation,
  type CircuitSimulationPreviewResponse,
  type CircuitSimulationSupportResponse,
} from '../../../../api/client';
import { themeColors } from '../../../../lib/theme';
import { adaptSimulationVisualGraph } from '../adapters/simulation-visual-adapter';
import type { SimulationVisualGraph } from '../types';

type Props = {
  projectId: string;
  isDark: boolean;
  currentArtifactVersion?: number;
  onRunSimulation: () => Promise<void>;
};

function displayStatus(value: string): string {
  return value.replaceAll('_', ' ').replaceAll('-', ' ');
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiClientError || error instanceof Error ? error.message : fallback;
}

function SerialOutputPanel({
  text,
  isDark,
}: {
  text: string;
  isDark: boolean;
}) {
  const t = themeColors(isDark);
  return (
    <pre
      data-testid="simulation-serial-output"
      style={{
        margin: 0,
        maxHeight: 180,
        overflow: 'auto',
        padding: 10,
        borderRadius: 8,
        border: `1px solid ${t.border}`,
        background: isDark ? '#0B1220' : '#0F172A',
        color: '#E2E8F0',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        fontSize: 12,
        whiteSpace: 'pre-wrap',
      }}
    >
      {text || 'No serial output captured.'}
    </pre>
  );
}

function SimulationGraphPreview({
  graph,
  isDark,
}: {
  graph: SimulationVisualGraph;
  isDark: boolean;
}) {
  const t = themeColors(isDark);
  return (
    <div
      data-testid="simulation-visual-graph"
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto 1fr',
        gap: 16,
        alignItems: 'start',
        padding: 12,
        border: `1px solid ${t.border}`,
        borderRadius: 10,
        background: t.surface,
      }}
    >
      {graph.nodes.map((node) => (
        <div
          key={node.id}
          data-testid={`simulation-part-${node.id}`}
          style={{
            border: `1px solid ${t.border}`,
            borderRadius: 10,
            padding: 12,
            background: t.surface2,
          }}
        >
          <div style={{ fontWeight: 700 }}>{node.providerPartType}</div>
          <div style={{ fontSize: 11, color: t.textMuted, marginTop: 4 }}>
            Nexus: {node.nexusTitle}
          </div>
          <div style={{ fontSize: 11, marginTop: 4 }}>
            Mapping: <strong>{node.mappingType}</strong>
          </div>
          <ul style={{ margin: '8px 0 0', paddingLeft: 16, fontFamily: 'ui-monospace, monospace', fontSize: 11 }}>
            {node.pins.map((pin) => (
              <li key={`${pin.sourcePin}-${pin.providerPin}`}>
                {pin.sourcePin} → {pin.providerPin}
              </li>
            ))}
          </ul>
        </div>
      ))}
      <div style={{ alignSelf: 'center', fontSize: 12, color: t.textSec, textAlign: 'center' }}>
        {graph.connections.map((connection) => (
          <div key={connection.id} style={{ marginBottom: 6 }}>
            {connection.sourcePin} ── {connection.label} ── {connection.targetPin}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ElectricalSimulationView({
  projectId,
  isDark,
  currentArtifactVersion,
  onRunSimulation,
}: Props) {
  const t = themeColors(isDark);
  const [support, setSupport] = useState<CircuitSimulationSupportResponse | null>(null);
  const [preview, setPreview] = useState<CircuitSimulationPreviewResponse | null>(null);
  const [runs, setRuns] = useState<ExecutionRun[]>([]);
  const [outputs, setOutputs] = useState<ProducedOutput[]>([]);
  const [serialText, setSerialText] = useState<string>('');
  const [busy, setBusy] = useState<'refresh' | 'validate' | 'run' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy('refresh');
    setError(null);
    const [supportResult, previewResult, runsResult, outputsResult] = await Promise.allSettled([
      getCircuitSimulationSupport(projectId),
      getCircuitSimulationPreview(projectId),
      listExecutions(projectId),
      listProducedOutputs(projectId),
    ]);
    if (supportResult.status === 'fulfilled') setSupport(supportResult.value);
    else setError(errorMessage(supportResult.reason, 'Unable to check simulation support.'));
    if (previewResult.status === 'fulfilled') setPreview(previewResult.value);
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
  const stale =
    latestRun != null &&
    currentArtifactVersion != null &&
    latestRun.baseArtifactVersion !== currentArtifactVersion;

  const simulationOutputs = useMemo(() => {
    const runIds = new Set(simulationRuns.map((run) => run.executionRunId));
    return outputs
      .filter((output) => runIds.has(output.executionRunId))
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  }, [outputs, simulationRuns]);

  useEffect(() => {
    const serial = simulationOutputs.find(
      (output) => output.name === 'serial.log' || output.outputType === 'log',
    );
    if (!serial) {
      setSerialText('');
      return;
    }
    void getProducedOutput(projectId, serial.outputId)
      .then((output) => {
        if (output.content.kind === 'inline-structured') {
          const structured = output.content.structuredResult;
          if (structured && typeof structured === 'object' && 'text' in structured) {
            setSerialText(String((structured as { text?: unknown }).text ?? ''));
            return;
          }
        }
        setSerialText(`${output.name} (${output.mediaType})`);
      })
      .catch(() => setSerialText('Unable to load serial output.'));
  }, [projectId, simulationOutputs]);

  const visual = useMemo(() => adaptSimulationVisualGraph(preview ?? undefined), [preview]);
  const availabilityReady =
    support?.providerAvailability.available === true &&
    support.providerAvailability.status.toUpperCase() === 'READY';
  const unsupported = support?.assessment.status === 'UNSUPPORTED';
  const partiallySupported = support?.assessment.status === 'PARTIALLY_SUPPORTED';
  const firmwareRequired =
    support?.assessment.status === 'FIRMWARE_REQUIRED' || support?.assessment.firmwareRequired;
  const runDisabled =
    busy !== null ||
    !availabilityReady ||
    unsupported ||
    partiallySupported ||
    Boolean(firmwareRequired);
  const hasWorkspaceExport = simulationOutputs.some(
    (output) => output.name === 'provider-workspace-manifest',
  );

  const buttonStyle = {
    border: `1px solid ${t.border}`,
    borderRadius: 6,
    background: t.surface,
    color: t.text,
    padding: '6px 10px',
    fontSize: 12,
    cursor: 'pointer',
  } as const;

  return (
    <section
      aria-label="Circuit Simulation"
      data-testid="electrical-simulation-view"
      style={{
        height: '100%',
        overflow: 'auto',
        padding: 16,
        background: t.bg,
        color: t.text,
      }}
    >
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <strong>Circuit Simulation</strong>
        <span>Provider: {support ? displayStatus(support.providerAvailability.status) : 'checking'}</span>
        <span>Support: {support ? displayStatus(support.assessment.status) : 'checking'}</span>
        {support?.assessment.surrogateUsed ? (
          <strong style={{ color: '#b7791f' }}>Surrogate hardware</strong>
        ) : null}
      </div>

      {unsupported ? (
        <div
          data-testid="simulation-unsupported-state"
          style={{
            marginTop: 12,
            padding: 12,
            borderRadius: 10,
            border: `1px solid ${t.border}`,
            background: t.surface,
          }}
        >
          <strong>Simulation unavailable for this architecture</strong>
          <p style={{ margin: '6px 0 0', color: t.textMuted }}>
            Unmapped components prevent a provider materialization. Design editing remains available.
          </p>
          <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
            {(support?.assessment.findings ?? []).map((finding) => (
              <li key={finding.findingId}>{finding.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {partiallySupported ? (
        <div
          data-testid="simulation-partial-state"
          style={{
            marginTop: 12,
            padding: 12,
            borderRadius: 10,
            border: `1px solid ${t.border}`,
            background: t.surface,
          }}
        >
          <strong>Simulation blocked — architecture only partially supported</strong>
          <p style={{ margin: '6px 0 0', color: t.textMuted }}>
            Provider mappings exist, but Electrical Architecture still has blocking findings (for
            example a missing I²C connection). Fix Design before running.
          </p>
          <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
            {(support?.assessment.findings ?? []).map((finding) => (
              <li key={finding.findingId}>{finding.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {!unsupported && visual.nodes.length > 0 ? (
        <div style={{ marginTop: 14 }}>
          <SimulationGraphPreview graph={visual} isDark={isDark} />
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
        <button type="button" style={buttonStyle} disabled={busy !== null} onClick={() => void refresh()}>
          {busy === 'refresh' ? 'Refreshing…' : 'Refresh support'}
        </button>
        <button
          type="button"
          style={buttonStyle}
          disabled={busy !== null || !support?.providerAvailability.lintAvailable}
          onClick={() =>
            void (async () => {
              setBusy('validate');
              setError(null);
              try {
                await validateCircuitSimulation(projectId);
                await refresh();
              } catch (err) {
                setError(errorMessage(err, 'Provider representation validation failed.'));
              } finally {
                setBusy(null);
              }
            })()
          }
        >
          Validate provider representation
        </button>
        <button
          type="button"
          style={{
            ...buttonStyle,
            background: runDisabled ? t.surface2 : t.cobalt,
            color: runDisabled ? t.textMuted : '#fff',
            borderColor: runDisabled ? t.border : t.cobalt,
          }}
          disabled={runDisabled}
          data-testid="run-circuit-simulation"
          onClick={() =>
            void (async () => {
              setBusy('run');
              setError(null);
              try {
                await onRunSimulation();
                await refresh();
              } catch (err) {
                setError(errorMessage(err, 'Circuit simulation failed.'));
              } finally {
                setBusy(null);
              }
            })()
          }
        >
          {busy === 'run' ? 'Running…' : 'Run Simulation'}
        </button>
        {hasWorkspaceExport ? (
          <a href={getCircuitSimulationExportUrl(projectId)} style={{ ...buttonStyle, textDecoration: 'none' }}>
            Export Wokwi workspace
          </a>
        ) : null}
      </div>

      {firmwareRequired ? (
        <div style={{ marginTop: 10, color: t.textMuted }}>
          Supported architecture · Firmware required to run
        </div>
      ) : null}

      {latestRun ? (
        <div data-testid="latest-simulation-run" style={{ marginTop: 14 }}>
          <strong>
            {stale ? 'Simulation from previous Electrical revision' : 'Latest simulation'}
          </strong>
          <div style={{ marginTop: 4 }}>
            Result: {displayStatus(latestRun.status)} · Provider {latestRun.providerId}
            {stale
              ? ` · Based on Electrical v${latestRun.baseArtifactVersion} · Current v${currentArtifactVersion}`
              : null}
          </div>
          <div style={{ marginTop: 6, color: t.textMuted, fontSize: 12 }}>
            Behavior simulation evidence only. Actual component compatibility remains unverified.
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 14, color: t.textMuted }}>No circuit simulation runs yet.</div>
      )}

      <div style={{ marginTop: 14 }}>
        <strong>Serial Output</strong>
        <div style={{ marginTop: 6 }}>
          <SerialOutputPanel text={serialText} isDark={isDark} />
        </div>
      </div>

      <div data-testid="simulation-outputs" style={{ marginTop: 14 }}>
        <strong>Produced outputs</strong>
        <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
          {simulationOutputs.map((output) => (
            <li key={output.outputId}>
              {output.name} · {displayStatus(output.outputType)} · {output.mediaType}
            </li>
          ))}
        </ul>
      </div>

      {error ? (
        <div role="alert" style={{ marginTop: 12, color: '#c53030' }}>
          {error}
        </div>
      ) : null}
    </section>
  );
}

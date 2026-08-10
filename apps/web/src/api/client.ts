export type AutonomyMode = 'collaborate' | 'delegate';

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    requestId?: string;
    supportedFamilies?: Array<{ family: string; examplePrompt: string }>;
    matchedFamilies?: string[];
    details?: string[];
  };
};

export class ApiClientError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;

  constructor(message: string, status: number, body: ApiErrorBody | null) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.body = body;
  }
}

function apiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';
}

export type CircuitSimulationProviderAvailability = {
  providerId: string;
  status: string;
  available: boolean;
  lintAvailable: boolean;
  message?: string;
};

export type CircuitSimulationMapping = {
  mappingType?: 'exact' | 'equivalent' | 'surrogate' | 'unsupported';
  message?: string;
  sourceEntityId?: string;
  providerEntityId?: string;
  [key: string]: unknown;
};

export type CircuitSimulationSupportResponse = {
  schemaVersion: string;
  projectId: string;
  artifactId: string;
  providerAvailability: CircuitSimulationProviderAvailability;
  assessment: import('@nexus/contracts').CircuitSimulationSupportAssessment & {
    mappings?: CircuitSimulationMapping[];
  };
};

export type CircuitSimulationValidationResponse = {
  ok: boolean;
  findings: import('@nexus/contracts').CircuitSimulationSupportAssessment['findings'];
  outputs?: import('@nexus/contracts').ProducedOutput[];
  workspaceDigest?: string;
};

export type CircuitSimulationPreviewResponse = {
  schemaVersion: string;
  providerId: string;
  status: string;
  surrogateUsed: boolean;
  workspaceDigest?: string;
  mappings: Array<{
    providerPartId: string;
    providerPartType: string;
    mappingType?: string;
    pinProfile?: Array<{ sourcePin?: string; providerPin?: string }>;
    sourceReferences?: Array<{
      entityId?: string;
      entityType?: string;
      displayLabel?: string;
      artifactType?: string;
    }>;
  }>;
  connections: Array<{
    id?: string;
    sourcePartId?: string;
    targetPartId?: string;
    sourcePin?: string;
    targetPin?: string;
    label?: string;
  }>;
  findings: Array<{ findingId?: string; message?: string; mappingType?: string }>;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

const CORE_ARTIFACT_TYPES = [
  'project-brief',
  'requirement-set',
  'functional-architecture',
  'next-action',
] as const;

function parseProjectPackage(payload: unknown): import('@nexus/contracts').ProjectCurrentState {
  if (!isRecord(payload)) {
    throw new Error('Project response is not an object');
  }
  if (payload.schemaVersion !== '1.0.0') {
    throw new Error('Unexpected project schemaVersion');
  }
  if (!Array.isArray(payload.artifacts) || payload.artifacts.length < 4) {
    throw new Error('Project response must include at least four artifacts');
  }
  const types = new Set(
    payload.artifacts
      .filter(isRecord)
      .map((artifact) => artifact.artifactType)
      .filter((type): type is string => typeof type === 'string'),
  );
  for (const required of CORE_ARTIFACT_TYPES) {
    if (!types.has(required)) {
      throw new Error(`Project response missing required artifact: ${required}`);
    }
  }
  if (!isRecord(payload.veraResponse) || typeof payload.veraResponse.userFacingMessage !== 'string') {
    throw new Error('Project response missing veraResponse.userFacingMessage');
  }
  return payload as unknown as import('@nexus/contracts').ProjectCurrentState;
}

export function parseInitializationResult(
  payload: unknown,
): import('@nexus/contracts').ProjectInitializationResult {
  return parseProjectPackage(payload) as unknown as import('@nexus/contracts').ProjectInitializationResult;
}

async function requestJson(path: string, init?: RequestInit): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, init);
  } catch {
    throw new ApiClientError('Network failure while contacting the API.', 0, null);
  }
  const text = await response.text();
  let json: unknown = null;
  if (text) {
    try {
      json = JSON.parse(text) as unknown;
    } catch {
      throw new ApiClientError('API returned non-JSON content.', response.status, null);
    }
  }
  if (!response.ok) {
    const body = isRecord(json) && isRecord(json.error) ? (json as ApiErrorBody) : null;
    throw new ApiClientError(
      body?.error.message ?? `Request failed with status ${response.status}`,
      response.status,
      body,
    );
  }
  return json;
}

export async function initializeProject(input: {
  message: string;
  autonomyMode?: AutonomyMode;
}): Promise<import('@nexus/contracts').ProjectInitializationResult> {
  const json = await requestJson('/v1/projects/initialize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: input.message,
      autonomyMode: input.autonomyMode ?? 'collaborate',
    }),
  });
  return parseInitializationResult(json);
}

export async function getProject(
  projectId: string,
): Promise<import('@nexus/contracts').ProjectCurrentState> {
  return parseProjectPackage(await requestJson(`/v1/projects/${projectId}`));
}

export async function getProjectArtifacts(
  projectId: string,
): Promise<{ schemaVersion: string; artifacts: unknown[] }> {
  return (await requestJson(`/v1/projects/${projectId}/artifacts`)) as {
    schemaVersion: string;
    artifacts: unknown[];
  };
}

export async function getProjectHistory(
  projectId: string,
): Promise<import('@nexus/contracts').ProjectHistory> {
  return (await requestJson(`/v1/projects/${projectId}/history`)) as import('@nexus/contracts').ProjectHistory;
}

export async function submitProjectTurn(input: {
  projectId: string;
  message: string;
  autonomyMode?: AutonomyMode;
}): Promise<import('@nexus/contracts').ProjectTurnResult> {
  const json = await requestJson(`/v1/projects/${input.projectId}/turns`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message: input.message,
      autonomyMode: input.autonomyMode ?? 'collaborate',
    }),
  });
  if (!isRecord(json) || !isRecord(json.currentState)) {
    throw new Error('Turn response missing currentState');
  }
  return json as unknown as import('@nexus/contracts').ProjectTurnResult;
}

export async function getArtifactVersion(input: {
  projectId: string;
  artifactType: string;
  version?: number;
}): Promise<import('@nexus/contracts').Artifact> {
  const query =
    input.version != null ? `?version=${encodeURIComponent(String(input.version))}` : '';
  return (await requestJson(
    `/v1/projects/${input.projectId}/artifacts/${input.artifactType}${query}`,
  )) as import('@nexus/contracts').Artifact;
}

export async function listArtifactTypes(): Promise<
  import('@nexus/contracts').ArtifactTypeDefinition[]
> {
  const json = await requestJson('/v1/artifact-types');
  if (Array.isArray(json)) {
    return json as import('@nexus/contracts').ArtifactTypeDefinition[];
  }
  if (isRecord(json) && Array.isArray(json.artifactTypes)) {
    return json.artifactTypes as import('@nexus/contracts').ArtifactTypeDefinition[];
  }
  throw new Error('Artifact types response must be an array or { artifactTypes }');
}

export async function getProjectBoard(
  projectId: string,
): Promise<import('@nexus/contracts').ProjectBoardProjection> {
  const json = await requestJson(`/v1/projects/${projectId}/board`);
  if (
    !isRecord(json) ||
    json.schemaVersion !== '1.0.0' ||
    typeof json.projectId !== 'string' ||
    !Array.isArray(json.artifactSummaries)
  ) {
    throw new Error('Invalid project board projection');
  }
  return json as unknown as import('@nexus/contracts').ProjectBoardProjection;
}

export async function getWorkspace(
  projectId: string,
  artifactType: string,
): Promise<import('@nexus/contracts').WorkspaceDescriptor> {
  return (await requestJson(
    `/v1/projects/${projectId}/artifacts/${artifactType}/workspace`,
  )) as import('@nexus/contracts').WorkspaceDescriptor;
}

export async function createWorkspace(
  projectId: string,
  artifactType: string,
  body?: Record<string, unknown>,
): Promise<import('@nexus/contracts').WorkspaceDescriptor> {
  return (await requestJson(`/v1/projects/${projectId}/artifacts/${artifactType}/workspace`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })) as import('@nexus/contracts').WorkspaceDescriptor;
}

export async function ensureLayeredArchitecture(
  projectId: string,
  body?: Record<string, unknown>,
): Promise<{
  schemaVersion: string;
  projectId: string;
  createdArtifactTypes: string[];
  currentState: import('@nexus/contracts').ProjectCurrentState;
}> {
  return (await requestJson(`/v1/projects/${projectId}/ensure-layered-architecture`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })) as {
    schemaVersion: string;
    projectId: string;
    createdArtifactTypes: string[];
    currentState: import('@nexus/contracts').ProjectCurrentState;
  };
}

export async function submitArtifactCommand(
  projectId: string,
  command: import('@nexus/contracts').ArtifactCommand,
): Promise<import('@nexus/contracts').ArtifactCommandResult> {
  return (await requestJson(`/v1/projects/${projectId}/artifact-commands`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(command),
  })) as import('@nexus/contracts').ArtifactCommandResult;
}

export async function listExecutions(
  projectId: string,
): Promise<import('@nexus/contracts').ExecutionRun[]> {
  const json = await requestJson(`/v1/projects/${projectId}/executions`);
  if (Array.isArray(json)) {
    return json as import('@nexus/contracts').ExecutionRun[];
  }
  if (isRecord(json) && Array.isArray(json.executions)) {
    return json.executions as import('@nexus/contracts').ExecutionRun[];
  }
  if (isRecord(json) && Array.isArray(json.items)) {
    return json.items as import('@nexus/contracts').ExecutionRun[];
  }
  throw new Error('Executions response must include an items array');
}

export async function listProducedOutputs(
  projectId: string,
): Promise<import('@nexus/contracts').ProducedOutput[]> {
  const json = await requestJson(`/v1/projects/${projectId}/outputs`);
  if (isRecord(json) && Array.isArray(json.items)) {
    return json.items as import('@nexus/contracts').ProducedOutput[];
  }
  throw new Error('Outputs response must include an items array');
}

const CIRCUIT_SIMULATION_PATH =
  'artifacts/electrical-architecture/circuit-simulation';

export async function getCircuitSimulationSupport(
  projectId: string,
): Promise<CircuitSimulationSupportResponse> {
  return (await requestJson(
    `/v1/projects/${encodeURIComponent(projectId)}/${CIRCUIT_SIMULATION_PATH}/support`,
  )) as CircuitSimulationSupportResponse;
}

export async function getCircuitSimulationPreview(
  projectId: string,
): Promise<CircuitSimulationPreviewResponse> {
  return (await requestJson(
    `/v1/projects/${encodeURIComponent(projectId)}/${CIRCUIT_SIMULATION_PATH}/preview`,
  )) as CircuitSimulationPreviewResponse;
}

export async function validateCircuitSimulation(
  projectId: string,
): Promise<CircuitSimulationValidationResponse> {
  return (await requestJson(
    `/v1/projects/${encodeURIComponent(projectId)}/${CIRCUIT_SIMULATION_PATH}/validate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    },
  )) as CircuitSimulationValidationResponse;
}

export function getCircuitSimulationExportUrl(projectId: string): string {
  return `${apiBaseUrl()}/v1/projects/${encodeURIComponent(projectId)}/${CIRCUIT_SIMULATION_PATH}/export`;
}

export async function getProducedOutput(
  projectId: string,
  outputId: string,
): Promise<import('@nexus/contracts').ProducedOutput> {
  return (await requestJson(
    `/v1/projects/${projectId}/outputs/${encodeURIComponent(outputId)}`,
  )) as import('@nexus/contracts').ProducedOutput;
}

export async function listEvents(
  projectId: string,
): Promise<import('@nexus/contracts').ProjectEvent[]> {
  const json = await requestJson(`/v1/projects/${projectId}/events`);
  if (Array.isArray(json)) {
    return json as import('@nexus/contracts').ProjectEvent[];
  }
  if (isRecord(json) && Array.isArray(json.events)) {
    return json.events as import('@nexus/contracts').ProjectEvent[];
  }
  if (isRecord(json) && Array.isArray(json.items)) {
    return json.items as import('@nexus/contracts').ProjectEvent[];
  }
  throw new Error('Events response must include an items array');
}

export async function getProjectGraph(
  projectId: string,
): Promise<import('@nexus/contracts').GraphTraversalResult> {
  return (await requestJson(
    `/v1/projects/${projectId}/graph`,
  )) as import('@nexus/contracts').GraphTraversalResult;
}

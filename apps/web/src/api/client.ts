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

/**
 * What the desktop shell hands the renderer through its preload bridge.
 *
 * Both values are decided at launch and cannot be known at build time: the
 * sidecar binds an operating-system-assigned port, and its credential is minted
 * per launch. A bundle that read only `import.meta.env` would therefore be
 * built pointing at an address nothing listens on, carrying a token the service
 * rejects - which is why the bridge is consulted first and the environment is
 * only the fallback.
 */
function desktopApiRuntime(): { baseUrl: string; sessionToken: string } | undefined {
  // Read off `globalThis` rather than `window` so this stays evaluable under
  // the Node-based test environment, where there is no window at all.
  const api = (globalThis as { nexus?: { api?: unknown } }).nexus?.api;
  if (!isRecord(api)) {
    return undefined;
  }

  const { baseUrl, sessionToken: token } = api;
  if (typeof baseUrl !== 'string' || typeof token !== 'string') {
    // A bridge that is present but malformed is a shell/renderer mismatch. The
    // environment fallback below is a better answer than a request addressed to
    // `undefined`, and the failure then surfaces as an ordinary connection error.
    return undefined;
  }

  return { baseUrl, sessionToken: token };
}

function apiBaseUrl(): string {
  return (
    desktopApiRuntime()?.baseUrl ??
    (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
    'http://127.0.0.1:8000'
  );
}

/**
 * Every API request carries the sidecar session token. The API listens on
 * loopback, so this token - not the network boundary - is the security
 * boundary. The desktop shell injects a per-session value through the preload
 * bridge; a browser development target falls back to the environment, and then
 * to the API's well-known development token.
 */
function sessionToken(): string {
  return (
    desktopApiRuntime()?.sessionToken ??
    (import.meta.env.VITE_API_SESSION_TOKEN as string | undefined) ??
    'nexus-dev-session-token'
  );
}

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
  if (
    !Array.isArray(payload.artifacts) ||
    payload.artifacts.length < 4 ||
    payload.artifacts.length > 5
  ) {
    throw new Error('Project response must include four or five artifacts');
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
  const headers = new Headers(init?.headers);
  headers.set('Authorization', `Bearer ${sessionToken()}`);
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, { ...init, headers });
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
  throw new Error('Executions response must be an array or { executions }');
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
  throw new Error('Events response must be an array or { events }');
}

export async function getProjectGraph(
  projectId: string,
): Promise<import('@nexus/contracts').GraphTraversalResult> {
  return (await requestJson(
    `/v1/projects/${projectId}/graph`,
  )) as import('@nexus/contracts').GraphTraversalResult;
}

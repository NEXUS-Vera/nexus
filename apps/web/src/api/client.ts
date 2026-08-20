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

/**
 * Every API request carries the sidecar session token. The API listens on
 * loopback, so this token - not the network boundary - is the security
 * boundary. The desktop shell injects a per-session value; local development
 * falls back to the API's well-known development token.
 */
function sessionToken(): string {
  return (
    (import.meta.env.VITE_API_SESSION_TOKEN as string | undefined) ?? 'nexus-dev-session-token'
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function parseProjectPackage(payload: unknown): import('@nexus/contracts').ProjectCurrentState {
  if (!isRecord(payload)) {
    throw new Error('Project response is not an object');
  }
  if (payload.schemaVersion !== '1.0.0') {
    throw new Error('Unexpected project schemaVersion');
  }
  if (!Array.isArray(payload.artifacts) || payload.artifacts.length !== 4) {
    throw new Error('Project response must include exactly four artifacts');
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
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      headers: { ...init?.headers, Authorization: `Bearer ${sessionToken()}` },
    });
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

export type AutonomyMode = 'collaborate' | 'delegate';

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    requestId?: string;
    supportedFamilies?: Array<{ family: string; examplePrompt: string }>;
    matchedFamilies?: string[];
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function parseInitializationResult(payload: unknown): import('@nexus/contracts').ProjectInitializationResult {
  if (!isRecord(payload)) {
    throw new Error('Initialization response is not an object');
  }
  if (payload.schemaVersion !== '1.0.0') {
    throw new Error('Unexpected initialization schemaVersion');
  }
  if (!Array.isArray(payload.artifacts) || payload.artifacts.length !== 4) {
    throw new Error('Initialization response must include exactly four artifacts');
  }
  if (!isRecord(payload.veraResponse) || typeof payload.veraResponse.userFacingMessage !== 'string') {
    throw new Error('Initialization response missing veraResponse.userFacingMessage');
  }
  return payload as unknown as import('@nexus/contracts').ProjectInitializationResult;
}

export async function initializeProject(input: {
  message: string;
  autonomyMode?: AutonomyMode;
}): Promise<import('@nexus/contracts').ProjectInitializationResult> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/v1/projects/initialize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: input.message,
        autonomyMode: input.autonomyMode ?? 'collaborate',
      }),
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

  return parseInitializationResult(json);
}

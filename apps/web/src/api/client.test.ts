import { afterEach, describe, expect, it, vi } from 'vitest';

import { getProject } from './client';

/**
 * Where the client gets its address and its credential from.
 *
 * This is the seam between the two ways the same bundle runs. In a browser it
 * is a development target reading `import.meta.env`; inside the desktop shell
 * the sidecar binds an operating-system-assigned port and mints a fresh token
 * per launch, so neither value can be known at build time and both arrive
 * through the preload bridge instead.
 */

type NexusBridge = { api: { baseUrl: string; sessionToken: string } };

function installBridge(bridge: unknown): void {
  (globalThis as { nexus?: unknown }).nexus = bridge;
}

afterEach(() => {
  delete (globalThis as { nexus?: unknown }).nexus;
  vi.unstubAllGlobals();
});

/** Capture the one request the client makes, and answer it with a 404 body. */
function captureRequest(): { calls: Array<[string, RequestInit | undefined]> } {
  const calls: Array<[string, RequestInit | undefined]> = [];
  vi.stubGlobal('fetch', (input: string, init?: RequestInit) => {
    calls.push([input, init]);
    return Promise.resolve(
      new Response(JSON.stringify({ error: { code: 'PROJECT_NOT_FOUND', message: 'no' } }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });
  return { calls };
}

describe('API client host resolution', () => {
  it('addresses the sidecar the preload bridge names, with the token it minted', async () => {
    const bridge: NexusBridge = {
      api: { baseUrl: 'http://127.0.0.1:54321', sessionToken: 'a-per-launch-token' },
    };
    installBridge(bridge);
    const { calls } = captureRequest();

    await expect(getProject('proj_abcdefghijklmnop')).rejects.toBeDefined();

    // Anything baked in at build time is wrong here by construction: the port
    // did not exist and the token had not been minted when the bundle was made.
    expect(calls).toHaveLength(1);
    const [url, init] = calls[0];
    expect(url).toBe('http://127.0.0.1:54321/v1/projects/proj_abcdefghijklmnop');
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer a-per-launch-token');
  });

  it('falls back to the build-time configuration when there is no bridge', async () => {
    const { calls } = captureRequest();

    await expect(getProject('proj_abcdefghijklmnop')).rejects.toBeDefined();

    // The browser development target has no shell around it, and must keep
    // working exactly as it did before the bridge existed.
    expect(calls).toHaveLength(1);
    const [url, init] = calls[0];
    expect(url).toBe('http://127.0.0.1:8000/v1/projects/proj_abcdefghijklmnop');
    expect(new Headers(init?.headers).get('Authorization')).toBe(
      'Bearer nexus-dev-session-token',
    );
  });

  it('falls back rather than addressing a malformed bridge', async () => {
    // A bridge whose shape does not match is a shell/renderer version mismatch.
    // Reading through it regardless would send a request to `undefined`, which
    // reports as neither an address problem nor a credential one.
    installBridge({ api: { baseUrl: 42 } });
    const { calls } = captureRequest();

    await expect(getProject('proj_abcdefghijklmnop')).rejects.toBeDefined();

    expect(calls[0][0]).toBe('http://127.0.0.1:8000/v1/projects/proj_abcdefghijklmnop');
  });
});

/**
 * The one payload the shell hands across the preload bridge.
 *
 * This module is imported by both the main process and the preload script, so
 * it must stay free of Electron and Node imports: the preload runs sandboxed in
 * the renderer's process and can require nothing but a small allowlist.
 */

/** The single synchronous channel the renderer is allowed to speak on. */
export const RUNTIME_CONFIG_CHANNEL = 'nexus:runtime-config';

/**
 * What the renderer is told about its host.
 *
 * Every field here is readable by any script the renderer ends up running, so
 * the shape is the allowlist: nothing reaches the page unless it is named here.
 */
export interface RendererRuntimeConfig {
  /** Where the local API is listening, resolved from the sidecar handshake. */
  readonly baseUrl: string;
  /** Shared secret the local API requires on every request. */
  readonly sessionToken: string;
}

/**
 * The subset of `ipcMain` this module needs, so it stays testable in plain Node.
 *
 * Taking the host as an argument rather than importing `electron` keeps the
 * package's rule intact: only the composition entry point touches Electron.
 */
export interface SyncChannelHost {
  on(channel: string, listener: (event: { returnValue: unknown }) => void): void;
}

/**
 * Answer the renderer's bootstrap request with the runtime configuration.
 *
 * The answer is synchronous because the renderer needs its API address and
 * credential before it issues its first request, and a promise would force
 * every caller to be async for a value the main process already holds in
 * memory. The handler does no work beyond returning that value.
 *
 * The value is read per request rather than captured once, because the address
 * can change while the application is running: a sidecar that crashes is
 * replaced on a fresh operating-system-assigned port, and the page is reloaded
 * to pick the replacement up. A captured value would hand that reload the dead
 * address and leave the window looking healthy while every request failed.
 */
export function serveRuntimeConfig(
  host: SyncChannelHost,
  readConfig: () => RendererRuntimeConfig,
): void {
  host.on(RUNTIME_CONFIG_CHANNEL, (event) => {
    event.returnValue = readConfig();
  });
}

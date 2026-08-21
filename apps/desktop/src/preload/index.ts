import { contextBridge, ipcRenderer } from 'electron';

import { RUNTIME_CONFIG_CHANNEL } from '../shared/runtime-config.js';
import type { RendererRuntimeConfig } from '../shared/runtime-config.js';

/**
 * Electron preload entry point.
 *
 * This is the entire boundary between a web page and the user's machine. Vera
 * writes files and spawns shells, so anything reachable from the page - a
 * `require`, a live `process`, a generic `invoke(channel, ...)` - turns a
 * cross-site script or a hostile model output into arbitrary local code
 * execution. The bridge therefore exposes named values and nothing callable:
 * there is no channel argument for a caller to control.
 */

const runtimeConfig = ipcRenderer.sendSync(RUNTIME_CONFIG_CHANNEL) as RendererRuntimeConfig;

contextBridge.exposeInMainWorld('nexus', {
  api: {
    baseUrl: runtimeConfig.baseUrl,
    sessionToken: runtimeConfig.sessionToken,
  },
  shell: {
    serviceRestarted: runtimeConfig.serviceRestarted,
  },
});

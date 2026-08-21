import { describe, expect, it } from 'vitest';

import { resolveSidecarLaunch } from './sidecar-launch.js';

describe('resolveSidecarLaunch', () => {
  it('takes the executable and its arguments from the environment', () => {
    const launch = resolveSidecarLaunch({
      NEXUS_SIDECAR_COMMAND: '/Applications/Nexus.app/Contents/Resources/python',
      NEXUS_SIDECAR_ARGS: '["-m","nexus_api"]',
    });

    // The argument list is JSON rather than a whitespace-separated string
    // because the paths that end up in it routinely contain spaces, and a split
    // on whitespace turns one such path into two broken arguments.
    expect(launch).toEqual({
      command: '/Applications/Nexus.app/Contents/Resources/python',
      args: ['-m', 'nexus_api'],
    });
  });

  it('says which setting is missing rather than spawning nothing', () => {
    // Spawning an unconfigured command does not fail fast: it fails as a
    // handshake that never arrives, so the user waits out the timeout and is
    // then told the service did not respond, which is not what went wrong.
    expect(() => resolveSidecarLaunch({})).toThrow(/NEXUS_SIDECAR_COMMAND/);
  });
});

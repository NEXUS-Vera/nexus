/**
 * What the shell spawns to get a local API.
 *
 * The executable is configuration, not a constant: during development it is the
 * repository's own interpreter, and in a packaged application it is the runtime
 * shipped inside the bundle. Naming it here rather than hard-coding one of
 * those would make the other one impossible.
 */

/** Executable and arguments for the sidecar process. */
export interface SidecarLaunch {
  readonly command: string;
  readonly args: readonly string[];
}

const COMMAND_VARIABLE = 'NEXUS_SIDECAR_COMMAND';
const ARGS_VARIABLE = 'NEXUS_SIDECAR_ARGS';

export function resolveSidecarLaunch(env: Record<string, string | undefined>): SidecarLaunch {
  const command = env[COMMAND_VARIABLE];

  if (command === undefined || command.trim() === '') {
    // Spawning an unconfigured command does not fail fast: it fails as a
    // handshake that never arrives, so the user waits out the timeout and is
    // then told the service did not respond, which is not what went wrong.
    throw new Error(
      `${COMMAND_VARIABLE} is not set, so there is no local service to start. ` +
        `Set it to the interpreter that runs the Nexus API, and set ${ARGS_VARIABLE} ` +
        'to its arguments as a JSON array.',
    );
  }

  // The arguments are JSON rather than a whitespace-separated string because
  // the paths that end up in them routinely contain spaces, and splitting on
  // whitespace turns one such path into two arguments that name nothing.
  const args = JSON.parse(env[ARGS_VARIABLE] ?? '[]') as string[];

  return { command, args };
}

import { spawn } from 'node:child_process';
import type { Readable } from 'node:stream';

/**
 * Supervision of the local `nexus_api` sidecar process.
 *
 * The sidecar binds an operating-system-assigned loopback port and announces it
 * on stdout as exactly one newline-terminated JSON line:
 *
 * ```json
 * {"event":"nexus.api.listening","schemaVersion":"1.0.0","host":"127.0.0.1","port":54321,"pid":4242}
 * ```
 *
 * The socket is already bound and listening when that line is written, so a
 * connection made the instant it is read is accepted rather than refused. There
 * is therefore no reason to poll or retry after the handshake: read one line,
 * stop reading, connect.
 */

/** The sidecar's announcement that it is bound and listening. */
export interface SidecarHandshake {
  readonly schemaVersion: string;
  readonly host: string;
  readonly port: number;
  /** The sidecar's own pid, used to reap it and to detect orphans. */
  readonly pid: number;
}

export interface SidecarSupervisorOptions {
  /** Executable to spawn, for example a bundled Python interpreter. */
  readonly command: string;
  readonly args: readonly string[];
  /** Shared secret the sidecar requires on every loopback request. */
  readonly sessionToken: string;
}

export class SidecarSupervisor {
  readonly #options: SidecarSupervisorOptions;

  constructor(options: SidecarSupervisorOptions) {
    this.#options = options;
  }

  /** Spawn the sidecar and resolve once it has announced a listening socket. */
  async start(): Promise<SidecarHandshake> {
    const child = spawn(this.#options.command, [...this.#options.args], {
      // Port 0 asks the operating system for a free port; a fixed port would
      // collide with the user's own tooling and with a second Nexus instance.
      env: {
        ...process.env,
        NEXUS_API_PORT: '0',
        NEXUS_API_SESSION_TOKEN: this.#options.sessionToken,
      },
      // stdout is the contract channel. stderr is inherited so sidecar logging
      // reaches the shell's own diagnostics instead of filling an unread pipe.
      stdio: ['ignore', 'pipe', 'inherit'],
    });

    return parseHandshake(await readFirstLine(child.stdout));
  }
}

/**
 * Read the first newline-terminated line from a stream and stop listening.
 *
 * The sidecar writes one line and nothing else, so consuming further output
 * would only be a way to keep the read alive past the point of interest.
 */
function readFirstLine(stream: Readable): Promise<string> {
  return new Promise((resolve) => {
    let buffered = '';

    stream.setEncoding('utf8');
    stream.on('data', function onData(chunk: string) {
      buffered += chunk;
      const newline = buffered.indexOf('\n');
      if (newline === -1) {
        return;
      }

      stream.off('data', onData);
      resolve(buffered.slice(0, newline));
    });
  });
}

function parseHandshake(line: string): SidecarHandshake {
  const announcement = JSON.parse(line) as SidecarHandshake;

  return {
    schemaVersion: announcement.schemaVersion,
    host: announcement.host,
    port: announcement.port,
    pid: announcement.pid,
  };
}

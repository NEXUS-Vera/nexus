import { spawn } from 'node:child_process';
import type { ChildProcessByStdio } from 'node:child_process';
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

/**
 * Handshake major version this supervisor understands.
 *
 * Per the contract policy, a major bump means required fields moved, so an
 * announcement from a newer major is not something to interpret optimistically.
 */
const SUPPORTED_SCHEMA_MAJOR = 1;

/**
 * The spawned sidecar, typed to the exact stdio shape the supervisor requests:
 * no stdin, a piped stdout carrying the handshake, an inherited stderr.
 */
type SidecarProcess = ChildProcessByStdio<null, Readable, null>;

/**
 * How long to wait for the handshake before giving up.
 *
 * Generous enough for a cold interpreter start on a slow disk, short enough
 * that a broken install produces a message instead of a blank window.
 */
const DEFAULT_HANDSHAKE_TIMEOUT_MS = 15_000;

/**
 * Restarts allowed before the failure is treated as terminal.
 *
 * One retry covers the genuinely transient case - a port raced away, a
 * half-released resource. Beyond that the sidecar is failing for a reason a
 * respawn cannot fix, and looping would spin the CPU while hiding the fault.
 */
const MAX_RESTART_ATTEMPTS = 1;

/** Why the sidecar failed to reach a usable listening state. */
export type SidecarStartFailureReason = 'handshake-timeout' | 'unsupported-schema-version';

/** Typed failure surfaced by {@link SidecarSupervisor.start}. */
export class SidecarStartError extends Error {
  readonly reason: SidecarStartFailureReason;

  constructor(reason: SidecarStartFailureReason, message: string) {
    super(message);
    this.name = 'SidecarStartError';
    this.reason = reason;
  }
}

/** Why the sidecar is considered unrecoverable and will not be respawned. */
export type SidecarTerminalFailureReason = 'restart-limit-exceeded';

/**
 * Typed failure surfaced after a successful start, through `onTerminalFailure`.
 *
 * A crash after startup cannot be reported by rejecting `start()`; that promise
 * has already settled. This is the channel the shell listens on to tell the
 * user the local API is gone for good.
 */
export class SidecarTerminalError extends Error {
  readonly reason: SidecarTerminalFailureReason;

  constructor(reason: SidecarTerminalFailureReason, message: string) {
    super(message);
    this.name = 'SidecarTerminalError';
    this.reason = reason;
  }
}

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
  /** Defaults to {@link DEFAULT_HANDSHAKE_TIMEOUT_MS}. */
  readonly handshakeTimeoutMs?: number;
  /** Called once when the sidecar has failed in a way a restart cannot fix. */
  readonly onTerminalFailure?: (error: SidecarTerminalError) => void;
}

export class SidecarSupervisor {
  readonly #options: SidecarSupervisorOptions;
  #current: SidecarProcess | undefined;
  #restarts = 0;

  constructor(options: SidecarSupervisorOptions) {
    this.#options = options;
  }

  /** Spawn the sidecar and resolve once it has announced a listening socket. */
  async start(): Promise<SidecarHandshake> {
    return this.#launch();
  }

  /**
   * Terminate the sidecar and resolve only once it has actually exited.
   *
   * Resolving on the signal rather than on the exit would let the shell quit
   * while the sidecar is still shutting down, which is exactly how an orphan
   * that still holds the local database survives a quit.
   */
  async stop(): Promise<void> {
    const child = this.#current;
    if (child === undefined) {
      return;
    }

    // Clearing the reference first makes this exit read as superseded, so the
    // restart policy does not resurrect a deliberately stopped sidecar.
    this.#current = undefined;

    const exited = new Promise<void>((resolve) => {
      child.once('exit', () => {
        resolve();
      });
    });

    child.kill('SIGTERM');
    await exited;
  }

  async #launch(): Promise<SidecarHandshake> {
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

    this.#current = child;
    // Subscribed before the handshake is awaited: a sidecar that announces and
    // then dies immediately would otherwise emit `exit` before anyone listened.
    child.once('exit', (code, signal) => {
      this.#onChildExit(child, code, signal);
    });

    const line = await withHandshakeTimeout(
      readFirstLine(child.stdout),
      this.#options.handshakeTimeoutMs ?? DEFAULT_HANDSHAKE_TIMEOUT_MS,
    );

    return parseHandshake(line);
  }

  #onChildExit(
    child: SidecarProcess,
    code: number | null,
    signal: NodeJS.Signals | null,
  ): void {
    if (child !== this.#current) {
      // A superseded child; the supervisor has already moved on.
      return;
    }

    this.#current = undefined;

    if (this.#restarts >= MAX_RESTART_ATTEMPTS) {
      this.#options.onTerminalFailure?.(
        new SidecarTerminalError(
          'restart-limit-exceeded',
          `Sidecar exited (code ${String(code)}, signal ${String(signal)}) after ` +
            `${this.#restarts} restart attempt(s); not restarting again`,
        ),
      );
      return;
    }

    this.#restarts += 1;
    void this.#launch().catch(() => {
      // A restart that cannot even hand shake is itself an exit-shaped failure;
      // the replacement child's own `exit` carries it to the terminal branch.
    });
  }
}

/**
 * Bound the wait for the handshake.
 *
 * A sidecar can be alive and useless: a broken install, a missing dependency,
 * an interpreter wedged on an import. Without a bound, that state is
 * indistinguishable from a slow start and the shell waits forever.
 */
async function withHandshakeTimeout<T>(pending: Promise<T>, timeoutMs: number): Promise<T> {
  let timer: NodeJS.Timeout | undefined;

  const expiry = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      reject(
        new SidecarStartError(
          'handshake-timeout',
          `Sidecar did not announce a listening port within ${timeoutMs}ms`,
        ),
      );
    }, timeoutMs);
  });

  try {
    return await Promise.race([pending, expiry]);
  } finally {
    clearTimeout(timer);
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
  const major = Number.parseInt(announcement.schemaVersion.split('.')[0] ?? '', 10);

  if (major !== SUPPORTED_SCHEMA_MAJOR) {
    throw new SidecarStartError(
      'unsupported-schema-version',
      `Sidecar announced handshake schema version ${announcement.schemaVersion}; ` +
        `this shell supports major version ${SUPPORTED_SCHEMA_MAJOR}`,
    );
  }

  return {
    schemaVersion: announcement.schemaVersion,
    host: announcement.host,
    port: announcement.port,
    pid: announcement.pid,
  };
}

import { spawn } from 'node:child_process';
import type { ChildProcessByStdio } from 'node:child_process';
import type { Readable, Writable } from 'node:stream';

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
type SidecarProcess = ChildProcessByStdio<Writable, Readable, null>;

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

/**
 * How long a sidecar gets to exit on its own after the polite signal, before
 * the supervisor stops asking. Long enough to close the database cleanly, short
 * enough that a wedged sidecar does not hold application quit open.
 */
const DEFAULT_TERMINATION_GRACE_MS = 5_000;

/** Why the sidecar failed to reach a usable listening state. */
export type SidecarStartFailureReason =
  | 'handshake-timeout'
  | 'handshake-stream-closed'
  | 'malformed-handshake'
  | 'unsupported-schema-version';

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
export type SidecarTerminalFailureReason = 'restart-limit-exceeded' | 'restart-failed';

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
  /**
   * Absolute path of the SQLite file the sidecar keeps the user's projects in.
   *
   * Required rather than defaulted, because the sidecar's own default storage
   * backend is in-memory: a shell that forgot to say where the database lives
   * would run perfectly and lose every project the moment the user quits. The
   * shell is also the only party that knows the per-user application data
   * directory this belongs in, so the decision cannot live down here.
   */
  readonly databaseFile: string;
  /** Defaults to {@link DEFAULT_HANDSHAKE_TIMEOUT_MS}. */
  readonly handshakeTimeoutMs?: number;
  /** Defaults to {@link DEFAULT_TERMINATION_GRACE_MS}. */
  readonly terminationGraceMs?: number;
  /** Called once when the sidecar has failed in a way a restart cannot fix. */
  readonly onTerminalFailure?: (error: SidecarTerminalError) => void;
  /**
   * Called when a replacement sidecar has announced itself after a crash.
   *
   * The replacement is spawned with `NEXUS_API_PORT=0` like the original, so it
   * binds a *different* port. Everything holding the port `start()` returned is
   * now pointed at nothing. A recovery nobody is told about is worse than no
   * recovery: the supervisor reads as healthy while every request fails.
   */
  readonly onRestart?: (handshake: SidecarHandshake) => void;
}

export class SidecarSupervisor {
  readonly #options: SidecarSupervisorOptions;
  #current: SidecarProcess | undefined;
  #restarts = 0;
  #started = false;
  #terminalReported = false;

  constructor(options: SidecarSupervisorOptions) {
    this.#options = options;
  }

  /** Spawn the sidecar and resolve once it has announced a listening socket. */
  async start(): Promise<SidecarHandshake> {
    const handshake = await this.#launch();
    // The restart policy arms itself only here. Before this point there is a
    // caller still waiting on an answer, and the honest answer to a sidecar
    // that will not come up is the failure itself.
    this.#started = true;
    return handshake;
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
    await this.#terminate(child);
  }

  /** Signal, wait, escalate, and resolve only once the child has really gone. */
  async #terminate(child: SidecarProcess): Promise<void> {
    // A child that has already exited will never emit `exit` again, so waiting
    // for one below would hang whatever is holding this - application quit
    // included - on a process that is already gone.
    if (child.exitCode !== null || child.signalCode !== null) {
      return;
    }

    const exited = new Promise<void>((resolve) => {
      child.once('exit', () => {
        resolve();
      });
    });

    child.kill('SIGTERM');

    // A sidecar can be alive and unable to respond: wedged in a native call, or
    // holding SIGTERM itself. Asking politely forever would hang application
    // quit, so the request becomes an order once the grace period is spent.
    const grace = setTimeout(() => {
      child.kill('SIGKILL');
    }, this.#options.terminationGraceMs ?? DEFAULT_TERMINATION_GRACE_MS);

    try {
      await exited;
    } finally {
      clearTimeout(grace);
    }
  }

  async #launch(): Promise<SidecarHandshake> {
    const child = spawn(this.#options.command, [...this.#options.args], {
      // Port 0 asks the operating system for a free port; a fixed port would
      // collide with the user's own tooling and with a second Nexus instance.
      env: {
        ...process.env,
        // Everything below is stated rather than inherited, and stated after
        // the spread, so that nothing the launching shell happens to export can
        // change what a packaged application does. The variables the sidecar
        // reads are a configuration surface for a developer running it by hand;
        // for the shipped shell they are decisions this module has already made.
        NEXUS_API_PORT: '0',
        NEXUS_API_SESSION_TOKEN: this.#options.sessionToken,
        // Loopback is the invariant the session token is layered on top of. An
        // inherited `0.0.0.0` would bind every interface, and nothing would look
        // wrong: the announced address still reaches the renderer, so the window
        // works normally while the student's project API answers their whole
        // network to anyone holding a token.
        NEXUS_API_HOST: '127.0.0.1',
        // Emptied rather than set, so the sidecar applies its own default. The
        // packaged renderer loads over `file://` and sends `Origin: null`, which
        // no allowlist contains, so an inherited one would not narrow the shell
        // - it would break every request it makes.
        NEXUS_API_CORS_ORIGINS: '',
        // A stray value here would redirect the user's projects into a
        // developer's Postgres, or back into memory to be lost on quit.
        NEXUS_STORAGE_BACKEND: 'sqlite',
        NEXUS_DATABASE_URL: sqliteUrl(this.#options.databaseFile),
      },
      // stdout is the contract channel. stderr is inherited so sidecar logging
      // reaches the shell's own diagnostics instead of filling an unread pipe.
      //
      // stdin is a pipe that is never written to. It exists so the sidecar can
      // tell that this process died: the operating system closes a dead
      // process's pipe ends on every platform, whereas the sidecar's other
      // watchdog polls os.getppid() and so only works where orphans are
      // reparented - not on Windows. Without this pipe, force-quitting the shell
      // there leaves a sidecar holding the database file.
      stdio: ['pipe', 'pipe', 'inherit'],
    });

    this.#current = child;
    // Subscribed before the handshake is awaited: a sidecar that announces and
    // then dies immediately would otherwise emit `exit` before anyone listened.
    child.once('exit', (code, signal) => {
      this.#onChildExit(child, code, signal);
    });

    try {
      const line = await withHandshakeTimeout(
        readFirstLine(child.stdout),
        this.#options.handshakeTimeoutMs ?? DEFAULT_HANDSHAKE_TIMEOUT_MS,
      );

      return parseHandshake(line);
    } catch (error) {
      // The child that failed the handshake is still holding whatever it did
      // manage to acquire. Reap it before reporting, or a startup failure
      // becomes an orphan that outlives the shell.
      if (child === this.#current) {
        this.#current = undefined;
        await this.#terminate(child);
      }

      throw error;
    }
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

    if (!this.#started) {
      // A sidecar that dies before `start()` has resolved is a build that
      // cannot start, not a service that fell over: retrying it would spawn a
      // replacement nobody is waiting for and nobody owns, since the shell has
      // already taken the startup-failure path and never registered a shutdown
      // for it. The pending `start()` rejects on its own - on the closed stdout
      // or on the handshake timeout - and that is what the user is told, once.
      return;
    }

    if (this.#restarts >= MAX_RESTART_ATTEMPTS) {
      this.#reportTerminalFailure(
        new SidecarTerminalError(
          'restart-limit-exceeded',
          `Sidecar exited (code ${String(code)}, signal ${String(signal)}) after ` +
            `${this.#restarts} restart attempt(s); not restarting again`,
        ),
      );
      return;
    }

    this.#restarts += 1;
    void this.#launch()
      .then((handshake) => {
        // The replacement bound its own port. Hand it on, or the shell keeps
        // addressing the dead one.
        this.#options.onRestart?.(handshake);
      })
      .catch((error: unknown) => {
        // A replacement that never announces has to be reported from here. Its
        // own `exit` cannot carry it: the rejection above resumes in the
        // microtask drain that follows the closed stdout and clears `#current`
        // first, so by the time `exit` fires the child reads as superseded and
        // is dropped. Left unreported, the window stays open on a port nothing
        // is listening on, with nothing on screen saying why - which is the
        // failure the restart wiring exists to remove, one step later.
        this.#reportTerminalFailure(
          new SidecarTerminalError(
            'restart-failed',
            'Sidecar exited and its replacement could not start: ' +
              `${error instanceof Error ? error.message : String(error)}`,
          ),
        );
      });
  }

  /**
   * Tell the shell the sidecar is gone for good, at most once.
   *
   * Which of the two paths above gets here depends on whether a dying
   * replacement's `exit` or its closed stdout wins a race Node does not order.
   * Both describe the same end state, and the user needs to be told about it
   * once, not once per event that happened to observe it.
   */
  #reportTerminalFailure(error: SidecarTerminalError): void {
    if (this.#terminalReported) {
      return;
    }

    this.#terminalReported = true;
    this.#options.onTerminalFailure?.(error);
  }
}

/**
 * Address a SQLite file the way SQLAlchemy expects.
 *
 * The path is absolute, so it contributes its own leading separator and the
 * result carries four slashes on unix - which is the absolute form, as against
 * the three-slash relative one that would put the database wherever the
 * sidecar happened to be started from.
 */
function sqliteUrl(databaseFile: string): string {
  return `sqlite:///${databaseFile}`;
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
  return new Promise((resolve, reject) => {
    let buffered = '';

    const onData = (chunk: string): void => {
      buffered += chunk;
      const newline = buffered.indexOf('\n');
      if (newline === -1) {
        return;
      }

      stream.off('data', onData);
      stream.off('close', onClose);
      resolve(buffered.slice(0, newline));
    };

    // A sidecar that exits before announcing - a missing interpreter, a failed
    // import, the likeliest broken install - closes stdout without ever writing
    // a line. Waiting for the handshake timeout here would turn an immediate,
    // knowable failure into a blank window for the full timeout, and then
    // report it as slowness rather than as the crash it was.
    const onClose = (): void => {
      stream.off('data', onData);
      reject(
        new SidecarStartError(
          'handshake-stream-closed',
          buffered === ''
            ? 'Sidecar closed stdout without announcing a listening port'
            : `Sidecar closed stdout mid-handshake after ${JSON.stringify(buffered)}`,
        ),
      );
    };

    stream.setEncoding('utf8');
    stream.on('data', onData);
    stream.once('close', onClose);
  });
}

/**
 * Validate the announcement before trusting any of it.
 *
 * The line arrives from a separate process over a pipe. Reading fields off an
 * unchecked `JSON.parse` result would let a truncated or unexpected line throw a
 * raw SyntaxError or TypeError out of `start()`, past every caller that handles
 * the documented SidecarStartError.
 */
function parseHandshake(line: string): SidecarHandshake {
  let announcement: unknown;
  try {
    announcement = JSON.parse(line);
  } catch {
    throw new SidecarStartError(
      'malformed-handshake',
      `Sidecar announcement is not valid JSON: ${JSON.stringify(line)}`,
    );
  }

  if (typeof announcement !== 'object' || announcement === null) {
    throw new SidecarStartError(
      'malformed-handshake',
      `Sidecar announcement is not an object: ${JSON.stringify(line)}`,
    );
  }

  const fields = announcement as Record<string, unknown>;
  const { schemaVersion, host, port, pid } = fields;

  if (typeof schemaVersion !== 'string') {
    throw new SidecarStartError(
      'malformed-handshake',
      `Sidecar announcement has no schemaVersion: ${JSON.stringify(line)}`,
    );
  }
  if (typeof host !== 'string') {
    throw new SidecarStartError(
      'malformed-handshake',
      `Sidecar announcement has no host: ${JSON.stringify(line)}`,
    );
  }
  if (!Number.isInteger(port)) {
    throw new SidecarStartError(
      'malformed-handshake',
      `Sidecar announced a non-integer port: ${JSON.stringify(line)}`,
    );
  }
  if (!Number.isInteger(pid)) {
    throw new SidecarStartError(
      'malformed-handshake',
      `Sidecar announced a non-integer pid: ${JSON.stringify(line)}`,
    );
  }

  const major = Number.parseInt(schemaVersion.split('.')[0] ?? '', 10);

  if (major !== SUPPORTED_SCHEMA_MAJOR) {
    throw new SidecarStartError(
      'unsupported-schema-version',
      `Sidecar announced handshake schema version ${schemaVersion}; ` +
        `this shell supports major version ${SUPPORTED_SCHEMA_MAJOR}`,
    );
  }

  return { schemaVersion, host, port: port as number, pid: pid as number };
}

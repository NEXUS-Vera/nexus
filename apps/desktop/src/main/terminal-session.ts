import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

import { spawn } from 'node-pty';
import type { IPty } from 'node-pty';

const execFileAsync = promisify(execFile);

/**
 * A single PTY-backed terminal owned by the Electron main process.
 *
 * This is the capability a browser cannot supply. Nexus has to run the
 * student's real toolchain - `pio`, `avrdude`, `openocd`, a vendor SDK on disk
 * - and read back exactly what their own terminal would show, because that
 * output is what Vera has to interpret to coach a build-flash-observe loop.
 *
 * A pipe would not do. Compilers and flashers detect whether stdout is a
 * terminal and change what they emit: progress bars, colour, and line wrapping
 * all appear only on a TTY. Reading a pipe would mean reading a different
 * program's output than the student sees.
 *
 * This module is plain Node and takes no Electron dependency, so it is unit
 * tested against a real pseudoterminal without launching Electron.
 */

/** Default terminal geometry, matching the classic 80x24 VT100 window. */
const DEFAULT_COLUMNS = 80;
const DEFAULT_ROWS = 24;

/**
 * How long the terminal's processes get to exit on their own after the polite
 * signal, before the request becomes an order.
 *
 * Long enough for a flash tool to release the serial port and close its log,
 * short enough that closing a tab does not visibly stall.
 */
const DEFAULT_TERMINATION_GRACE_MS = 2_000;

/** How long to wait for the kernel to reap processes after `SIGKILL`. */
const KILL_TIMEOUT_MS = 2_000;

/** Gap between liveness checks while waiting for processes to disappear. */
const REAP_POLL_INTERVAL_MS = 25;

export interface TerminalSessionOptions {
  /** Executable to run on the pseudoterminal, typically the user's shell. */
  readonly command: string;
  readonly args: readonly string[];
  /** Working directory for the child; defaults to the shell's own default. */
  readonly cwd?: string;
  /** Environment for the child; defaults to the main process environment. */
  readonly env?: NodeJS.ProcessEnv;
  /** Initial width in character cells. Defaults to {@link DEFAULT_COLUMNS}. */
  readonly columns?: number;
  /** Initial height in character cells. Defaults to {@link DEFAULT_ROWS}. */
  readonly rows?: number;
  /** Defaults to {@link DEFAULT_TERMINATION_GRACE_MS}. */
  readonly terminationGraceMs?: number;
}

/** Unsubscribes a listener registered on this session. */
export type TerminalUnsubscribe = () => void;

/**
 * How the process on the terminal ended.
 *
 * The distinction between the two fields carries meaning a student needs. An
 * `exitCode` of 3 is the toolchain reporting its own verdict: the build failed
 * and the compiler said so. A `signal` means something ended the process from
 * outside - the terminal was closed, the machine ran out of memory, a watchdog
 * fired - and in that case the exit code says nothing about the build at all.
 * Collapsing them into one number would let Vera tell a student their code is
 * broken when what actually happened is that their terminal was closed.
 */
export interface TerminalExit {
  /** Status the process returned. Zero means success by POSIX convention. */
  readonly exitCode: number;
  /** Signal number that ended the process, or undefined for a normal exit. */
  readonly signal?: number;
}

export class TerminalSession {
  readonly #pty: IPty;
  readonly #options: TerminalSessionOptions;
  #disposed = false;

  constructor(options: TerminalSessionOptions) {
    this.#options = options;
    this.#pty = spawn(options.command, [...options.args], {
      cwd: options.cwd,
      env: { ...(options.env ?? process.env) } as Record<string, string>,
      cols: options.columns ?? DEFAULT_COLUMNS,
      rows: options.rows ?? DEFAULT_ROWS,
      // Toolchains branch on TERM to decide whether to emit colour and cursor
      // control. Declaring a real terminal type is what makes the output the
      // student sees and the output Nexus reads the same bytes.
      name: 'xterm-256color',
    });
  }

  /** Send input to the terminal exactly as a keystroke would. */
  write(data: string): void {
    this.#pty.write(data);
  }

  /**
   * Tell the terminal, and through it the child, its new size in cells.
   *
   * This is not bookkeeping for the view. The kernel stores the window size on
   * the terminal itself, so a running program reads it with `TIOCGWINSZ` and
   * wraps its output to that width. A resize the child never learns about
   * means the toolchain wraps to one width while Nexus renders another.
   */
  resize(columns: number, rows: number): void {
    this.#pty.resize(columns, rows);
  }

  /** Subscribe to everything the terminal emits, in arrival order. */
  onData(listener: (chunk: string) => void): TerminalUnsubscribe {
    const subscription = this.#pty.onData(listener);
    return () => {
      subscription.dispose();
    };
  }

  /**
   * Subscribe to the terminal ending, with the status it ended on.
   *
   * Fires once. A terminal that has already exited by the time a listener
   * subscribes will not call it, so callers that care about the status should
   * subscribe before writing the command whose result they want.
   */
  onExit(listener: (result: TerminalExit) => void): TerminalUnsubscribe {
    const subscription = this.#pty.onExit(({ exitCode, signal }) => {
      // node-pty reports a normal exit as `signal: undefined` on POSIX but has
      // been observed to use 0 as well. Both mean "nothing signalled this", and
      // the type says a signal is absent rather than zero, so it is normalised
      // here instead of leaving every caller to remember the difference.
      listener({
        exitCode,
        ...(signal === undefined || signal === 0 ? {} : { signal }),
      });
    });

    return () => {
      subscription.dispose();
    };
  }

  /**
   * Terminate everything running on this terminal, and resolve only once it is
   * really gone.
   *
   * Killing the shell alone is not enough, and relying on the terminal hangup
   * is not either. When the session leader dies the kernel sends `SIGHUP` to
   * the terminal's foreground process group, which reaps a well-behaved child
   * for free - but a process that ignores `SIGHUP` stays, and an ignored
   * disposition survives `exec`, so it stays after the toolchain has replaced
   * itself too. Signalling the shell's own process group does not reach it
   * either, because a job-control shell puts each job in a group of its own.
   *
   * The concrete cost of getting this wrong: `avrdude` or `pio` keeps the
   * board's serial port open after its terminal is closed, and the student's
   * next flash fails with "port busy" and nothing on screen to explain it.
   *
   * So the tree is captured first, signalled by process group, and escalated to
   * `SIGKILL` if the grace period lapses. The order matters: once the shell
   * dies its children are reparented to init and can no longer be found from
   * its pid, so the snapshot has to be taken before anything is signalled.
   *
   * Resolving on actual disappearance rather than on the signal is what lets a
   * caller open a new terminal on the same board without racing the old one.
   */
  async dispose(): Promise<void> {
    if (this.#disposed) {
      return;
    }

    this.#disposed = true;

    if (process.platform === 'win32') {
      // Windows has no POSIX signals and no process groups reachable this way.
      // `kill` here becomes `TerminateProcess` on the shell alone, so a
      // descendant holding a device leaks. This is the same unfixed gap the
      // sidecar supervisor has, and it needs a job object with
      // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE rather than a port of this code.
      this.#pty.kill();
      return;
    }

    const doomed = await readProcessTree(this.#pty.pid);
    const graceMs = this.#options.terminationGraceMs ?? DEFAULT_TERMINATION_GRACE_MS;

    // SIGHUP, not SIGTERM. Closing a terminal is a hangup, and that is the
    // signal an interactive shell is built to act on: it exits and passes the
    // hangup to its own jobs. Measured on macOS, SIGTERM does the opposite of
    // what it looks like it does here - an interactive bash ignores it outright
    // so that a stray signal cannot destroy a user's session, so the polite
    // request was being dropped and every close paid the full grace period
    // before SIGKILL did the work.
    signalProcessGroups(doomed, 'SIGHUP');
    if (await waitUntilAllGone(doomed, graceMs)) {
      return;
    }

    // A process can be alive and unable to leave: wedged in a driver call, or
    // holding the polite signal. SIGKILL is the one it does not get to refuse.
    signalProcessGroups(doomed, 'SIGKILL');
    await waitUntilAllGone(doomed, KILL_TIMEOUT_MS);
  }
}

/** One process, as reported by `ps`. */
interface ProcessRecord {
  readonly pid: number;
  readonly parentPid: number;
  readonly groupId: number;
}

/**
 * Every process descended from `rootPid`, including `rootPid` itself.
 *
 * Read from a single `ps` snapshot rather than walked live, so the tree cannot
 * shift underneath the traversal while it is being built.
 */
async function readProcessTree(rootPid: number): Promise<ProcessRecord[]> {
  let stdout: string;
  try {
    ({ stdout } = await execFileAsync('ps', ['-A', '-o', 'pid=,ppid=,pgid=']));
  } catch {
    // Without a process listing there is still one pid known for certain.
    return [{ pid: rootPid, parentPid: 0, groupId: rootPid }];
  }

  const all: ProcessRecord[] = [];
  for (const line of stdout.split('\n')) {
    const [pid, parentPid, groupId] = line.trim().split(/\s+/).map(Number);
    if (pid === undefined || Number.isNaN(pid)) {
      continue;
    }

    all.push({
      pid,
      parentPid: parentPid ?? 0,
      groupId: groupId ?? pid,
    });
  }

  const childrenByParent = new Map<number, ProcessRecord[]>();
  for (const record of all) {
    const siblings = childrenByParent.get(record.parentPid) ?? [];
    siblings.push(record);
    childrenByParent.set(record.parentPid, siblings);
  }

  const root = all.find((record) => record.pid === rootPid) ?? {
    pid: rootPid,
    parentPid: 0,
    groupId: rootPid,
  };

  const collected: ProcessRecord[] = [];
  const queue: ProcessRecord[] = [root];
  const seen = new Set<number>([rootPid]);
  while (queue.length > 0) {
    const record = queue.shift();
    if (record === undefined) {
      break;
    }

    collected.push(record);
    for (const child of childrenByParent.get(record.pid) ?? []) {
      if (seen.has(child.pid)) {
        continue;
      }

      seen.add(child.pid);
      queue.push(child);
    }
  }

  return collected;
}

/**
 * Signal each distinct process group in the tree.
 *
 * Signalling the group rather than the individual pids is what catches a
 * grandchild that was forked after the snapshot was taken: it inherits its
 * parent's process group, so a negative-pid signal still reaches it.
 */
function signalProcessGroups(tree: readonly ProcessRecord[], signal: NodeJS.Signals): void {
  const groupIds = new Set(tree.map((record) => record.groupId).filter((id) => id > 1));
  for (const groupId of groupIds) {
    try {
      process.kill(-groupId, signal);
    } catch {
      // Already gone, or never ours to signal. Either way there is nothing to
      // do about it here; the liveness poll is what decides whether this
      // worked.
    }
  }

  // A process whose group has since changed is not covered by the group signal,
  // so the individually known pids are signalled too.
  for (const record of tree) {
    try {
      process.kill(record.pid, signal);
    } catch {
      // See above.
    }
  }
}

/** Resolve true once no process in the tree is alive, or false on timeout. */
async function waitUntilAllGone(
  tree: readonly ProcessRecord[],
  timeoutMs: number,
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    if (!tree.some((record) => isRunning(record.pid))) {
      return true;
    }

    if (Date.now() >= deadline) {
      return false;
    }

    await delay(REAP_POLL_INTERVAL_MS);
  }
}

/** Signal 0 performs the permission and existence checks without delivering. */
function isRunning(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

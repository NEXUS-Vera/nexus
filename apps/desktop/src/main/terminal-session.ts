import { spawn } from 'node-pty';
import type { IPty } from 'node-pty';

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
}

/** Unsubscribes a listener registered on this session. */
export type TerminalUnsubscribe = () => void;

export class TerminalSession {
  readonly #pty: IPty;

  constructor(options: TerminalSessionOptions) {
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

  /** Terminate the terminal and the process running on it. */
  dispose(): void {
    this.#pty.kill();
  }
}

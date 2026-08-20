import { afterEach, describe, expect, it } from 'vitest';

import { TerminalSession } from './terminal-session.js';

/**
 * These suites drive a REAL pseudoterminal, not a mocked `node-pty`.
 *
 * A terminal is only a terminal because of what the operating system does: the
 * kernel line discipline echoes input, the winsize is visible to the child
 * through `TIOCGWINSZ`, and the controlling terminal binds a process group. A
 * test that stubs the PTY and asserts the stub was called proves that the
 * author remembers what they wrote, and nothing about whether a terminal works.
 *
 * So every case here spawns a real shell on a real PTY and observes it the way
 * a user would: through the bytes the child writes back.
 */

const openSessions: TerminalSession[] = [];

afterEach(async () => {
  await Promise.all(openSessions.splice(0).map((session) => session.dispose()));
});

/** `/bin/sh` with no profile: a POSIX shell whose behavior is the user's. */
function openShell(): TerminalSession {
  const session = new TerminalSession({ command: '/bin/sh', args: [] });
  openSessions.push(session);
  return session;
}

/**
 * Accumulate everything the terminal emits and let a case await a substring.
 *
 * PTY output arrives in arbitrary chunks - a prompt, a partial line, the rest
 * of it - so asserting on a single `onData` payload is a race. Accumulating and
 * waiting for the whole expected text is the only stable way to read it.
 */
function record(session: TerminalSession): {
  waitForText: (needle: string, timeoutMs?: number) => Promise<string>;
  waitForMatch: (pattern: RegExp, timeoutMs?: number) => Promise<string>;
} {
  let buffered = '';
  let notify: () => void = () => {};

  session.onData((chunk) => {
    buffered += chunk;
    notify();
  });

  async function waitFor(
    describeExpectation: string,
    isSatisfied: (text: string) => boolean,
    timeoutMs: number,
  ): Promise<string> {
    if (isSatisfied(buffered)) {
      return buffered;
    }

    return new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => {
        notify = () => {};
        reject(
          new Error(
            `Terminal never emitted ${describeExpectation} within ${timeoutMs}ms. ` +
              `Received: ${JSON.stringify(buffered)}`,
          ),
        );
      }, timeoutMs);

      notify = () => {
        if (!isSatisfied(buffered)) {
          return;
        }

        clearTimeout(timer);
        notify = () => {};
        resolve(buffered);
      };
    });
  }

  return {
    waitForText: async (needle, timeoutMs = 5_000) =>
      waitFor(JSON.stringify(needle), (text) => text.includes(needle), timeoutMs),
    waitForMatch: async (pattern, timeoutMs = 5_000) =>
      waitFor(String(pattern), (text) => pattern.test(text), timeoutMs),
  };
}

describe('TerminalSession.write', () => {
  it('delivers output the command produced inside the terminal', async () => {
    // The whole point of a PTY-backed terminal: what the student types runs,
    // and what the toolchain prints comes back. Without this there is no build
    // output for Vera to read.
    //
    // The expected text is deliberately something only the shell can produce.
    // A terminal echoes input back through the kernel line discipline, so
    // asserting on a substring of what was typed would also pass against an
    // implementation that ran nothing at all and merely mirrored its input.
    // `nexus-42` appears nowhere in the input; `/bin/sh` has to evaluate the
    // arithmetic to emit it.
    const session = openShell();
    const output = record(session);

    session.write('echo "nexus-$((6 * 7))"\n');

    await expect(output.waitForText('nexus-42')).resolves.toContain('nexus-42');
  }, 10_000);
});

describe('TerminalSession.resize', () => {
  it('changes the window size the child process itself reports', async () => {
    // Terminal width is not cosmetic here. A compiler wraps its diagnostics to
    // the terminal width, and that wrapped text is exactly what Vera has to
    // parse to tell a student which line failed. If the child never learns the
    // real width, Nexus renders one width and the toolchain wraps to another.
    //
    // Observed through `stty`, which asks the kernel for the window size of its
    // own controlling terminal. Reading back a field the session just stored
    // would prove only that the setter ran.
    const session = openShell();
    const output = record(session);

    session.resize(100, 30);
    session.write('stty size\n');

    // `stty size` reports rows first, then columns.
    await expect(output.waitForText('30 100')).resolves.toContain('30 100');
  }, 10_000);
});

describe('TerminalSession.dispose', () => {
  it('kills a descendant that survives the shell it was started from', async () => {
    // The leak this prevents is concrete: a flash tool holds the board's serial
    // port exclusively. If closing a terminal reaps the shell but leaves
    // `avrdude` or `pio` alive underneath it, the student's next flash fails
    // with "port busy" and nothing on screen explains why.
    //
    // The child deliberately ignores SIGHUP, because that is the only case that
    // actually tests this code. Measured on macOS: when the session leader
    // dies, the kernel hangs up the terminal's foreground process group, so an
    // ordinary child dies on its own and would let a do-nothing `dispose` pass.
    // A child with SIGHUP ignored does not, and an ignored disposition survives
    // `exec`, so the `sleep` that replaces this shell inherits it. It also sits
    // in its own process group, so signalling the shell's group never reaches
    // it either. That is a real toolchain that traps signals to clean up.
    const session = openShell();
    const output = record(session);

    // Matched on the digits, not on the marker alone: the terminal echoes the
    // command back, so `NEXUS_CHILD=` appears once as typed input with `$$`
    // unexpanded before it ever appears as the shell's own output.
    session.write("sh -c 'trap \"\" HUP; echo NEXUS_CHILD=$$; sleep 300'\n");
    const seen = await output.waitForMatch(/NEXUS_CHILD=\d+/);
    const childPid = readChildPid(seen);
    expect(isRunning(childPid)).toBe(true);

    await session.dispose();

    expect(isRunning(childPid)).toBe(false);
  }, 15_000);
});

/**
 * Pull the pid out of the marker the shell printed.
 *
 * The marker is matched on a line boundary because the terminal also echoes the
 * command that produced it, so the literal text appears twice in the stream.
 */
function readChildPid(terminalOutput: string): number {
  const matches = [...terminalOutput.matchAll(/NEXUS_CHILD=(\d+)/g)];
  const last = matches.at(-1);
  if (last === undefined) {
    throw new Error(`No child pid in terminal output: ${JSON.stringify(terminalOutput)}`);
  }

  return Number.parseInt(last[1] ?? '', 10);
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

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

afterEach(() => {
  for (const session of openSessions.splice(0)) {
    session.dispose();
  }
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
} {
  let buffered = '';
  let notify: () => void = () => {};

  session.onData((chunk) => {
    buffered += chunk;
    notify();
  });

  return {
    async waitForText(needle: string, timeoutMs = 5_000): Promise<string> {
      if (buffered.includes(needle)) {
        return buffered;
      }

      return new Promise<string>((resolve, reject) => {
        const timer = setTimeout(() => {
          notify = () => {};
          reject(
            new Error(
              `Terminal never emitted ${JSON.stringify(needle)} within ${timeoutMs}ms. ` +
                `Received: ${JSON.stringify(buffered)}`,
            ),
          );
        }, timeoutMs);

        notify = () => {
          if (!buffered.includes(needle)) {
            return;
          }

          clearTimeout(timer);
          notify = () => {};
          resolve(buffered);
        };
      });
    },
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

import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

import { afterEach, describe, expect, it } from 'vitest';

import {
  SidecarStartError,
  SidecarSupervisor,
  SidecarTerminalError,
} from './sidecar-supervisor.js';

/**
 * These suites drive a REAL child process, not a mocked `child_process`.
 *
 * The supervisor's whole job is to survive the messy parts of process
 * management: a child that never speaks, a child that dies, a child that has to
 * be reaped. A test that stubs `spawn` and then asserts `spawn` was called
 * proves only that the author remembers what they wrote. So each case writes a
 * small executable script to a scratch directory and supervises that.
 */

const scratchDirs: string[] = [];

afterEach(async () => {
  await Promise.all(scratchDirs.splice(0).map((dir) => rm(dir, { force: true, recursive: true })));
});

/**
 * Write a Node script that behaves like a sidecar and return its path.
 *
 * `keepAliveMs` bounds the fixture's own lifetime so a failing assertion can
 * never leave a process running past the end of the suite.
 */
async function writeFakeSidecar(body: string, keepAliveMs = 5_000): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), 'nexus-sidecar-'));
  scratchDirs.push(dir);
  const path = join(dir, 'fake-sidecar.mjs');
  await writeFile(path, `${body}\nsetTimeout(() => process.exit(0), ${keepAliveMs});\n`, 'utf8');
  return path;
}

function announce(port: number, schemaVersion = '1.0.0'): string {
  return [
    'process.stdout.write(JSON.stringify({',
    "  event: 'nexus.api.listening',",
    `  schemaVersion: ${JSON.stringify(schemaVersion)},`,
    "  host: '127.0.0.1',",
    `  port: ${port},`,
    '  pid: process.pid,',
    "}) + '\\n');",
  ].join('\n');
}

describe('SidecarSupervisor.start', () => {
  it('resolves with the port the sidecar announced on stdout', async () => {
    const executable = await writeFakeSidecar(announce(54_321));

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
    });

    const handshake = await supervisor.start();

    expect(handshake.port).toBe(54_321);
  });

  it('rejects a handshake announced under an unsupported schema major version', async () => {
    const executable = await writeFakeSidecar(announce(54_321, '2.0.0'));

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
    });

    await expect(supervisor.start()).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof SidecarStartError && error.reason === 'unsupported-schema-version',
    );
  });

  it('rejects rather than hanging when a live sidecar never announces a port', async () => {
    // Prints nothing and stays up: a broken install, a missing dependency, an
    // interpreter stuck on an import. Waiting forever turns that into a
    // permanently blank window with no explanation.
    const executable = await writeFakeSidecar('// never announces anything');

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      handshakeTimeoutMs: 150,
    });

    await expect(supervisor.start()).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof SidecarStartError && error.reason === 'handshake-timeout',
    );
  }, 2_000);
});

describe('SidecarSupervisor restart policy', () => {
  it('restarts a crashed sidecar exactly once, then surfaces a terminal failure', async () => {
    // Announces, then dies. An unbounded supervisor would respawn this forever,
    // burning battery while hiding the fault that is actually killing it.
    const executable = await writeFakeSidecar(
      [
        "import { appendFileSync } from 'node:fs';",
        "appendFileSync(new URL('runs.log', import.meta.url), 'run\\n');",
        announce(54_321),
        'setTimeout(() => process.exit(1), 100);',
      ].join('\n'),
    );
    const runLog = join(dirname(executable), 'runs.log');

    let surfaceTerminalFailure: (error: unknown) => void = () => {};
    const terminalFailure = new Promise<unknown>((resolve) => {
      surfaceTerminalFailure = resolve;
    });

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      handshakeTimeoutMs: 1_000,
      onTerminalFailure: (error) => surfaceTerminalFailure(error),
    });

    await supervisor.start();
    const failure = await terminalFailure;

    expect(failure).toBeInstanceOf(SidecarTerminalError);
    expect((failure as SidecarTerminalError).reason).toBe('restart-limit-exceeded');
    // One original launch plus exactly one restart.
    const runs = (await readFile(runLog, 'utf8')).trim().split('\n');
    expect(runs).toHaveLength(2);
  }, 5_000);
});

describe('SidecarSupervisor.stop', () => {
  it('leaves no orphaned sidecar process behind', async () => {
    // Runs long past the end of the suite unless the supervisor reaps it. An
    // orphan keeps holding the local database, so the next launch fails with no
    // visible cause.
    const executable = await writeFakeSidecar(announce(54_321), 30_000);

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      handshakeTimeoutMs: 1_000,
    });

    const { pid } = await supervisor.start();
    expect(isRunning(pid)).toBe(true);

    await supervisor.stop();

    expect(isRunning(pid)).toBe(false);
  }, 5_000);

  it('escalates to a kill when the sidecar ignores the polite signal', async () => {
    // A sidecar wedged in a native call or holding SIGTERM handles the signal
    // and never leaves. Waiting on it forever hangs application quit.
    const executable = await writeFakeSidecar(
      ["process.on('SIGTERM', () => {});", announce(54_321)].join('\n'),
      30_000,
    );

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      handshakeTimeoutMs: 1_000,
      terminationGraceMs: 200,
    });

    const { pid } = await supervisor.start();

    await supervisor.stop();

    expect(isRunning(pid)).toBe(false);
  }, 5_000);
});

/** Signal 0 performs the permission and existence checks without delivering. */
function isRunning(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

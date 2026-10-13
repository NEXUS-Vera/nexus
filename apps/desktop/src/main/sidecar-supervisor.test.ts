import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';

import { afterEach, describe, expect, it, vi } from 'vitest';

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
  vi.unstubAllEnvs();
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
      databaseFile: '/tmp/nexus-test.sqlite3',
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
      databaseFile: '/tmp/nexus-test.sqlite3',
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
      databaseFile: '/tmp/nexus-test.sqlite3',
      handshakeTimeoutMs: 150,
    });

    await expect(supervisor.start()).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof SidecarStartError && error.reason === 'handshake-timeout',
    );
  }, 2_000);

  it('reaps the sidecar it gave up on instead of leaving it running', async () => {
    // The child that failed the handshake is still holding whatever it managed
    // to acquire. Rejecting while it lives converts a startup failure into an
    // orphan that outlives the shell.
    const executable = await writeFakeSidecar(
      [
        "import { writeFileSync } from 'node:fs';",
        "writeFileSync(new URL('sidecar.pid', import.meta.url), String(process.pid));",
      ].join('\n'),
      30_000,
    );
    const pidPath = join(dirname(executable), 'sidecar.pid');

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      // vi.waitFor advances fake timers while polling for fixture readiness.
      // Keep that bounded wait well below the controlled handshake deadline.
      handshakeTimeoutMs: 30_000,
      terminationGraceMs: 200,
    });

    // A real 150 ms deadline can kill a slow-starting Node child before it
    // writes sidecar.pid. Control the deadline, then prove the fixture is alive
    // before timing out its handshake and checking that it was reaped.
    vi.useFakeTimers();
    try {
      const rejected = expect(supervisor.start()).rejects.toMatchObject({
        name: 'SidecarStartError',
        reason: 'handshake-timeout',
      });
      let pid = 0;
      await vi.waitFor(async () => {
        pid = Number.parseInt(await readFile(pidPath, 'utf8'), 10);
        expect(isRunning(pid)).toBe(true);
      }, 5_000);

      await vi.advanceTimersByTimeAsync(30_000);
      await rejected;
      expect(isRunning(pid)).toBe(false);
    } finally {
      vi.useRealTimers();
      await supervisor.stop();
    }
  }, 10_000);
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
      databaseFile: '/tmp/nexus-test.sqlite3',
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

  it('reports a terminal failure when the replacement never announces', async () => {
    // The first run announces and then dies, so the restart policy is armed and
    // fires; the replacement dies without announcing. Nothing downstream is
    // watching the replacement - its rejection resumes on the closed stdout and
    // clears the current child before its own `exit` fires, so that event reads
    // as superseded and is dropped. Unless this path reports, the shell keeps a
    // window open on a port nothing is listening on with no dialog at all.
    const dir = await mkdtemp(join(tmpdir(), 'nexus-sidecar-'));
    scratchDirs.push(dir);
    const counter = join(dir, 'launches');
    const executable = join(dir, 'fake-sidecar.mjs');
    await writeFile(
      executable,
      [
        "import { appendFileSync, existsSync, readFileSync } from 'node:fs';",
        `const counter = ${JSON.stringify(counter)};`,
        "const launches = existsSync(counter) ? readFileSync(counter, 'utf8').length : 0;",
        "appendFileSync(counter, 'x');",
        'if (launches > 0) { process.exit(1); }',
        announce(47_001),
        'setTimeout(() => process.exit(1), 100);',
      ].join('\n'),
      'utf8',
    );

    const failures: SidecarTerminalError[] = [];
    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      handshakeTimeoutMs: 1_000,
      onTerminalFailure: (error) => {
        failures.push(error);
      },
    });

    await supervisor.start();

    await vi.waitFor(() => {
      expect(failures).toHaveLength(1);
    }, 4_000);

    expect(failures[0].reason).toBe('restart-failed');
    // Whether the replacement's `exit` or its closed stdout wins that race is
    // not ordered by Node, and both describe the same end state. The user hears
    // about it once either way.
    await new Promise((resolve) => setTimeout(resolve, 300));
    expect(failures).toHaveLength(1);
    // Bounded as before: one original launch plus one replacement, no loop.
    expect((await readFile(counter, 'utf8')).length).toBe(2);
  }, 10_000);

  it('does not restart a sidecar that died before it ever announced', async () => {
    // A sidecar that cannot come up at all is a broken build, not a service
    // that fell over. Restarting it would spawn a replacement nobody is waiting
    // on and nobody owns - the shell has already taken the startup-failure path
    // by then and never registers a shutdown for it - so the user would be told
    // the shell cannot start while a live sidecar was left behind holding a
    // loopback port and the database.
    const executable = await writeFakeSidecar(
      [
        "import { appendFileSync } from 'node:fs';",
        "appendFileSync(new URL('runs.log', import.meta.url), 'run\\n');",
        // Dies without ever writing the handshake line.
        'process.exit(1);',
      ].join('\n'),
    );
    const runLog = join(dirname(executable), 'runs.log');

    let terminalFailures = 0;
    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      handshakeTimeoutMs: 1_000,
      onTerminalFailure: () => {
        terminalFailures += 1;
      },
    });

    await expect(supervisor.start()).rejects.toMatchObject({
      name: 'SidecarStartError',
      reason: 'handshake-stream-closed',
    });

    // Long enough for a restart to have spawned and logged a second run.
    await new Promise((resolve) => setTimeout(resolve, 500));

    const runs = (await readFile(runLog, 'utf8')).trim().split('\n');
    expect(runs).toHaveLength(1);
    // The rejection above is the whole report; a terminal-failure dialog on top
    // of it would tell the user the same thing twice.
    expect(terminalFailures).toBe(0);
  }, 5_000);

  it('says nothing about a replacement the shell itself shut down', async () => {
    // The sidecar crashes, a replacement is spawned, and the user quits while
    // that replacement is still handshaking. Stopping it makes its handshake
    // fail, which looks exactly like a replacement that could not start - but
    // it is the shell closing on request. Reported, it puts a modal saying
    // "Nexus has to close" in front of a user in the middle of their own quit.
    const dir = await mkdtemp(join(tmpdir(), 'nexus-sidecar-'));
    scratchDirs.push(dir);
    const counter = join(dir, 'launches');
    const executable = join(dir, 'fake-sidecar.mjs');
    await writeFile(
      executable,
      [
        "import { appendFileSync, existsSync, readFileSync } from 'node:fs';",
        `const counter = ${JSON.stringify(counter)};`,
        "const launches = existsSync(counter) ? readFileSync(counter, 'utf8').length : 0;",
        "appendFileSync(counter, 'x');",
        // The replacement stays alive and silent, so the restart is still in
        // flight when the stop arrives.
        'if (launches > 0) { setTimeout(() => process.exit(0), 30000); }',
        'else {',
        announce(48_001),
        '  setTimeout(() => process.exit(1), 100);',
        '}',
      ].join('\n'),
      'utf8',
    );

    const failures: SidecarTerminalError[] = [];
    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      // Long enough that the stop below, not the timeout, is what ends the
      // replacement's handshake.
      handshakeTimeoutMs: 30_000,
      terminationGraceMs: 500,
      onTerminalFailure: (error) => {
        failures.push(error);
      },
    });

    await supervisor.start();

    // The replacement is in flight once the fixture has recorded a second run.
    await vi.waitFor(async () => {
      expect((await readFile(counter, 'utf8')).length).toBe(2);
    }, 5_000);

    await supervisor.stop();
    await new Promise((resolve) => setTimeout(resolve, 300));

    expect(failures).toEqual([]);
  }, 15_000);

  it('leaves nothing running when the exit beats the closed stdout', async () => {
    // The same startup crash, but with the two events that report it arriving
    // in the other order. Node guarantees neither, and which one wins decides
    // which branch the supervisor takes - so this fixture forces the harder
    // one: a detached grandchild holds the stdout pipe open, so the read never
    // sees a close and `exit` is what arrives first. Without the guard the
    // supervisor treats that as a service that fell over, spawns a replacement
    // that nothing is waiting on, and still rejects `start()` - so the shell
    // reports that it cannot start while a live sidecar keeps the loopback port
    // and the database file.
    const executable = await writeFakeSidecar(
      [
        "import { appendFileSync } from 'node:fs';",
        "import { spawn } from 'node:child_process';",
        "appendFileSync(new URL('runs.log', import.meta.url), 'run\\n');",
        "spawn(process.execPath, ['-e', 'setTimeout(() => {}, 1500)'], {",
        "  stdio: ['ignore', 'inherit', 'ignore'],",
        '  detached: true,',
        '}).unref();',
        'process.exit(1);',
      ].join('\n'),
    );
    const runLog = join(dirname(executable), 'runs.log');

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'test-session-token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      handshakeTimeoutMs: 1_000,
    });

    await expect(supervisor.start()).rejects.toMatchObject({
      name: 'SidecarStartError',
      reason: 'handshake-timeout',
    });

    const runs = (await readFile(runLog, 'utf8')).trim().split('\n');
    expect(runs).toHaveLength(1);
  }, 10_000);
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
      databaseFile: '/tmp/nexus-test.sqlite3',
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
      databaseFile: '/tmp/nexus-test.sqlite3',
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

describe('SidecarSupervisor restart reporting', () => {
  it('reports the new port when a restarted sidecar announces a different one', async () => {
    // Each launch reads a counter off disk, so the replacement announces a
    // different port - which is what really happens, since the sidecar is
    // spawned with NEXUS_API_PORT=0 and the operating system picks again.
    const dir = await mkdtemp(join(tmpdir(), 'nexus-sidecar-'));
    scratchDirs.push(dir);
    const counter = join(dir, 'launches');
    const executable = join(dir, 'fake-sidecar.mjs');
    await writeFile(
      executable,
      [
        "import { appendFileSync, existsSync, readFileSync } from 'node:fs';",
        `const counter = ${JSON.stringify(counter)};`,
        "const launches = existsSync(counter) ? readFileSync(counter, 'utf8').length : 0;",
        "appendFileSync(counter, 'x');",
        "process.stdout.write(JSON.stringify({",
        "  event: 'nexus.api.listening',",
        "  schemaVersion: '1.0.0',",
        "  host: '127.0.0.1',",
        '  port: 41000 + launches,',
        '  pid: process.pid,',
        "}) + '\\n');",
        // The first sidecar crashes; the replacement stays up.
        'if (launches === 0) { setTimeout(() => process.exit(1), 100); }',
        'setTimeout(() => process.exit(0), 5000);',
      ].join('\n'),
      'utf8',
    );

    const restarts: number[] = [];
    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      onRestart: (handshake) => {
        restarts.push(handshake.port);
      },
    });

    const first = await supervisor.start();
    expect(first.port).toBe(41_000);

    // A restart that nobody is told about leaves the renderer pointed at a port
    // nothing is listening on, while the supervisor believes it is healthy.
    await vi.waitFor(() => {
      expect(restarts).toEqual([41_001]);
    }, 5_000);

    await supervisor.stop();
  }, 15_000);
});

describe('SidecarSupervisor.start when the sidecar dies without announcing', () => {
  it('rejects as soon as stdout closes rather than waiting out the timeout', async () => {
    // The most likely broken install: a missing interpreter, a failed import,
    // an exit before any output. stdout closes with no line ever written.
    const executable = await writeFakeSidecar('process.exit(1);', 0);

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      // Generous, so the assertion below can only pass by noticing the closed
      // stream. Waiting for this timeout is the bug.
      handshakeTimeoutMs: 30_000,
    });

    const started = Date.now();
    await expect(supervisor.start()).rejects.toBeInstanceOf(SidecarStartError);
    expect(Date.now() - started).toBeLessThan(5_000);
  }, 15_000);

  it('names the closed stream rather than blaming a timeout that did not happen', async () => {
    const executable = await writeFakeSidecar('process.exit(1);', 0);

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      handshakeTimeoutMs: 30_000,
    });

    // 'Sidecar did not announce within 30000ms' would be a lie about a process
    // that exited in milliseconds, and would send whoever reads the log looking
    // for a slow start instead of a crash.
    await expect(supervisor.start()).rejects.toMatchObject({
      reason: 'handshake-stream-closed',
    });
  }, 15_000);
});

describe('SidecarSupervisor.start with a malformed handshake', () => {
  const cases: ReadonlyArray<readonly [string, string]> = [
    ['a line that is not JSON', "process.stdout.write('not json at all\\n');"],
    ['JSON that is not an object', "process.stdout.write('42\\n');"],
    ['an object with no schemaVersion', "process.stdout.write('{\"port\":1}\\n');"],
    [
      'a non-numeric port',
      'process.stdout.write(JSON.stringify({' +
        " event: 'nexus.api.listening', schemaVersion: '1.0.0'," +
        " host: '127.0.0.1', port: 'nope', pid: 1 }) + '\\n');",
    ],
  ];

  // Every other failure in this class is a SidecarStartError carrying a reason.
  // A raw SyntaxError or TypeError escaping from JSON.parse or a missing field
  // would slip past a caller that handles the documented type, which is exactly
  // the caller that was written carefully.
  it.each(cases)('rejects %s as a typed start error', async (_label, body) => {
    const executable = await writeFakeSidecar(body);

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'token',
      databaseFile: '/tmp/nexus-test.sqlite3',
      handshakeTimeoutMs: 5_000,
    });

    await expect(supervisor.start()).rejects.toMatchObject({
      name: 'SidecarStartError',
      reason: 'malformed-handshake',
    });
  }, 15_000);
});

describe('SidecarSupervisor storage configuration', () => {
  it('tells the sidecar to persist to the SQLite file the shell chose', async () => {
    // The API's own default storage backend is in-memory. A shell that spawns
    // the sidecar without saying otherwise runs perfectly and loses every
    // project the moment the user quits, which no unit test of either half
    // catches - the fault lives exactly here, in what gets handed over.
    const dir = await mkdtemp(join(tmpdir(), 'nexus-sidecar-'));
    scratchDirs.push(dir);
    const observed = join(dir, 'env.json');
    const databaseFile = join(dir, 'projects.sqlite3');
    const executable = join(dir, 'fake-sidecar.mjs');
    await writeFile(
      executable,
      [
        "import { writeFileSync } from 'node:fs';",
        `writeFileSync(${JSON.stringify(observed)}, JSON.stringify({`,
        '  backend: process.env.NEXUS_STORAGE_BACKEND,',
        '  url: process.env.NEXUS_DATABASE_URL,',
        '  token: process.env.NEXUS_API_SESSION_TOKEN,',
        '  port: process.env.NEXUS_API_PORT,',
        '  host: process.env.NEXUS_API_HOST,',
        '  corsOrigins: process.env.NEXUS_API_CORS_ORIGINS,',
        '}));',
        announce(46_001),
        'setTimeout(() => process.exit(0), 5000);',
      ].join('\n'),
      'utf8',
    );

    // Poisoned deliberately: a packaged application must not be steerable by
    // whatever the launching shell happens to export. `0.0.0.0` would bind every
    // interface, publishing the student's project API to their whole network
    // behind nothing but a token, and an inherited origin allowlist cannot
    // contain the `Origin: null` a `file://` renderer sends - so it would break
    // every request the shipped app makes.
    vi.stubEnv('NEXUS_API_HOST', '0.0.0.0');
    vi.stubEnv('NEXUS_API_CORS_ORIGINS', 'https://evil.example');
    vi.stubEnv('NEXUS_STORAGE_BACKEND', 'postgres');
    vi.stubEnv('NEXUS_DATABASE_URL', 'postgresql+psycopg://someone@elsewhere/db');

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'a-session-token',
      databaseFile,
      handshakeTimeoutMs: 5_000,
    });

    await supervisor.start();
    await supervisor.stop();

    expect(JSON.parse(await readFile(observed, 'utf8'))).toEqual({
      backend: 'sqlite',
      // Absolute, and addressed with SQLAlchemy's four-slash form: the
      // three-slash one is relative and would put the database wherever the
      // sidecar was started from.
      url: `sqlite:///${databaseFile}`,
      token: 'a-session-token',
      port: '0',
      host: '127.0.0.1',
      // Emptied, so the sidecar applies its own default rather than an
      // allowlist that would exclude the packaged renderer.
      corsOrigins: '',
    });
  }, 15_000);
});

describe('SidecarSupervisor parent-death signalling', () => {
  it('gives the sidecar a stdin pipe to detect the shell dying', async () => {
    // The sidecar's other watchdog polls os.getppid(), which notices a dead
    // parent only because POSIX reparents orphans to init. Windows does not
    // reparent, so that watchdog never fires there. A pipe closes when its
    // holder dies on every platform, which is why the sidecar watches stdin -
    // and it can only do that if the supervisor hands it a pipe.
    const executable = await writeFakeSidecar(
      [
        "import { fstatSync } from 'node:fs';",
        // Node implements a 'pipe' stdio slot with a socketpair on unix, not a
        // FIFO, so the sidecar's own check has to accept either. Asserting only
        // isFIFO() here would pass a test the real sidecar then fails.
        'const stat = fstatSync(0);',
        'const piped = stat.isFIFO() || stat.isSocket();',
        "process.stdout.write(JSON.stringify({",
        "  event: 'nexus.api.listening',",
        "  schemaVersion: '1.0.0',",
        "  host: '127.0.0.1',",
        '  port: piped ? 45_001 : 45_002,',
        '  pid: process.pid,',
        "}) + '\\n');",
      ].join('\n'),
    );

    const supervisor = new SidecarSupervisor({
      command: process.execPath,
      args: [executable],
      sessionToken: 'token',
      databaseFile: '/tmp/nexus-test.sqlite3',
    });

    const handshake = await supervisor.start();
    expect(handshake.port).toBe(45_001);

    await supervisor.stop();
  }, 15_000);
});

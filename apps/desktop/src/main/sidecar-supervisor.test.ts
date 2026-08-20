import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, describe, expect, it } from 'vitest';

import { SidecarSupervisor } from './sidecar-supervisor.js';

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
});

import { mkdtemp, readFile, realpath, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterEach, describe, expect, it } from 'vitest';

import { Workspace } from './workspace.js';

/**
 * These suites drive REAL files in a REAL temporary directory.
 *
 * This module is the only part of the shell that can destroy a student's work,
 * so the things worth asserting are the things a mock cannot express: that the
 * bytes on disk did not move, that a discarded proposal left the file
 * byte-identical, that an edit made in another editor survived. Stubbing `fs`
 * here would assert that the author remembers which function they called.
 */

const scratchDirs: string[] = [];

afterEach(async () => {
  await Promise.all(scratchDirs.splice(0).map((dir) => rm(dir, { force: true, recursive: true })));
});

/**
 * Create a scratch directory and return its REAL path.
 *
 * `tmpdir()` is itself a symlink on macOS (`/var` -> `/private/var`), so a root
 * taken at face value would not match the realpath-resolved paths the workspace
 * computes, and every containment check would fail for the wrong reason.
 */
async function makeScratchRoot(): Promise<string> {
  const dir = await realpath(await mkdtemp(join(tmpdir(), 'nexus-workspace-')));
  scratchDirs.push(dir);
  return dir;
}

describe('Workspace.proposeEdit', () => {
  it('returns a diff without writing anything to disk', async () => {
    // "The AI recommends, the student approves" is the whole product promise.
    // Encoded as a test it means exactly this: a proposal is inert.
    const root = await makeScratchRoot();
    const file = join(root, 'main.c');
    await writeFile(file, 'int main(void) { return 0; }\n', 'utf8');
    const before = await stat(file);

    const workspace = await Workspace.open(root);
    const proposal = await workspace.proposeEdit('main.c', 'int main(void) { return 1; }\n');

    expect(proposal.diff).toContain('-int main(void) { return 0; }');
    expect(proposal.diff).toContain('+int main(void) { return 1; }');

    const after = await stat(file);
    expect(await readFile(file)).toEqual(Buffer.from('int main(void) { return 0; }\n', 'utf8'));
    expect(after.mtimeMs).toBe(before.mtimeMs);
  });
});

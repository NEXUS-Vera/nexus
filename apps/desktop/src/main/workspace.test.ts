import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, realpath, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';

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

const execFileAsync = promisify(execFile);

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

describe('Workspace.applyEdit', () => {
  it('writes the new content and leaves the previous version recoverable from git', async () => {
    const root = await makeScratchRoot();
    await initGitRepo(root);
    const file = join(root, 'main.c');
    await writeFile(file, 'int main(void) { return 0; }\n', 'utf8');
    await git(root, ['add', 'main.c']);
    await git(root, ['commit', '--message', 'initial']);

    const workspace = await Workspace.open(root);
    const proposal = await workspace.proposeEdit('main.c', 'int main(void) { return 1; }\n');
    const applied = await workspace.applyEdit(proposal);

    expect(await readFile(file, 'utf8')).toBe('int main(void) { return 1; }\n');
    // The point of the checkpoint: the student gets the previous bytes back out
    // of git without having had to commit them themselves first.
    expect(await git(root, ['show', `${applied.checkpointRef}:main.c`])).toBe(
      'int main(void) { return 0; }\n',
    );
  });
});

describe('Workspace.rejectEdit', () => {
  it('leaves the file byte-identical to what it was before the proposal', async () => {
    // Not trivially true once applying takes a checkpoint: a reject path that
    // shared any of that machinery would stage, snapshot, or rewrite the file.
    // "No" has to mean the workspace is indistinguishable from never asking.
    const root = await makeScratchRoot();
    await initGitRepo(root);
    const file = join(root, 'main.c');
    await writeFile(file, 'int main(void) { return 0; }\n', 'utf8');
    await git(root, ['add', 'main.c']);
    await git(root, ['commit', '--message', 'initial']);
    const hashBefore = await hashFile(file);

    const workspace = await Workspace.open(root);
    const proposal = await workspace.proposeEdit('main.c', 'int main(void) { return 1; }\n');
    workspace.rejectEdit(proposal);

    expect(await hashFile(file)).toBe(hashBefore);
    // A rejected proposal is not an event in the repository's life either.
    expect(await git(root, ['status', '--porcelain'])).toBe('');
  });
});

async function hashFile(path: string): Promise<string> {
  return createHash('sha256').update(await readFile(path)).digest('hex');
}

/** Run git in `cwd` and return its stdout, so the suites exercise real objects. */
async function git(cwd: string, args: readonly string[]): Promise<string> {
  const { stdout } = await execFileAsync('git', [...args], { cwd });
  return stdout;
}

async function initGitRepo(root: string): Promise<void> {
  await git(root, ['init', '--initial-branch', 'main']);
  await git(root, ['config', 'user.email', 'student@example.test']);
  await git(root, ['config', 'user.name', 'Student']);
}

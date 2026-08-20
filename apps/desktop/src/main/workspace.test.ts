import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, realpath, rm, stat, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';

import { afterEach, describe, expect, it } from 'vitest';

import type { WorkspaceChange } from './workspace.js';
import { Workspace, WorkspaceError } from './workspace.js';

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

  it('refuses a proposal whose file changed underneath it, and keeps the change', async () => {
    // The student hand-edits in their own editor while Vera edits the same
    // files. Between proposing and accepting, the bytes the proposal was
    // computed against can stop being the bytes on disk. Applying anyway would
    // silently overwrite work the student just did by hand, which is the one
    // failure this whole module exists to make impossible.
    const root = await makeScratchRoot();
    await initGitRepo(root);
    const file = join(root, 'main.c');
    await writeFile(file, 'int main(void) { return 0; }\n', 'utf8');
    await git(root, ['add', 'main.c']);
    await git(root, ['commit', '--message', 'initial']);

    const workspace = await Workspace.open(root);
    const proposal = await workspace.proposeEdit('main.c', 'int main(void) { return 1; }\n');

    const handEdited = 'int main(void) { return 42; } // the student typed this\n';
    await writeFile(file, handEdited, 'utf8');

    await expect(workspace.applyEdit(proposal)).rejects.toSatisfy(
      (error: unknown) => error instanceof WorkspaceError && error.reason === 'stale-proposal',
    );
    expect(await readFile(file, 'utf8')).toBe(handEdited);
  });

  it('keeps a gitignored file recoverable even though git would not track it', async () => {
    // The checkpoint is built with `git add`, which honours `.gitignore` - so
    // the files git was told to ignore are exactly the files the checkpoint
    // would silently omit. Embedded projects ignore generated headers, board
    // configs, and local overrides routinely, and those are real work: an edit
    // to one of them must be as undoable as an edit to anything else.
    const root = await makeScratchRoot();
    await initGitRepo(root);
    await writeFile(join(root, '.gitignore'), 'config.h\n', 'utf8');
    await git(root, ['add', '.gitignore']);
    await git(root, ['commit', '--message', 'ignore generated config']);

    const file = join(root, 'config.h');
    await writeFile(file, '#define BAUD 115200\n', 'utf8');

    const workspace = await Workspace.open(root);
    const proposal = await workspace.proposeEdit('config.h', '#define BAUD 9600\n');
    const applied = await workspace.applyEdit(proposal);

    expect(await readFile(file, 'utf8')).toBe('#define BAUD 9600\n');
    expect(await git(root, ['show', `${applied.checkpointRef}:config.h`])).toBe(
      '#define BAUD 115200\n',
    );
  });

  it('refuses to write into a directory that is not a git repository', async () => {
    // Recoverability is not a nicety here, it is the reason applying is allowed
    // at all: without a checkpoint there is no undo for an edit that overwrites
    // work the student never committed. A directory with no repository cannot
    // provide one, so this refuses rather than writing unprotected - and it
    // says so in a reason the shell can act on, instead of leaking whatever
    // `git` happened to print.
    const root = await makeScratchRoot();
    const file = join(root, 'main.c');
    await writeFile(file, 'int main(void) { return 0; }\n', 'utf8');

    const workspace = await Workspace.open(root);
    const proposal = await workspace.proposeEdit('main.c', 'int main(void) { return 1; }\n');

    await expect(workspace.applyEdit(proposal)).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof WorkspaceError && error.reason === 'not-a-git-repository',
    );
    expect(await readFile(file, 'utf8')).toBe('int main(void) { return 0; }\n');
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

describe('Workspace path containment', () => {
  /**
   * The path in an edit comes from a model, so it is untrusted input in the
   * sense of AGENTS.md section 13: it is attacker-influenceable through the
   * project's own files, a pasted error message, or a datasheet. A workspace
   * that follows it out of the project is an arbitrary-file-write primitive
   * running with the student's own credentials.
   */
  it('refuses a traversal path and an absolute path outside the root', async () => {
    const root = await makeScratchRoot();
    const outside = await makeScratchRoot();
    const outsideFile = join(outside, 'id_rsa');
    await writeFile(outsideFile, 'PRIVATE KEY\n', 'utf8');

    const workspace = await Workspace.open(root);

    await expect(workspace.proposeEdit('../../.ssh/id_rsa', 'pwned\n')).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof WorkspaceError && error.reason === 'path-escapes-workspace',
    );
    await expect(workspace.proposeEdit(outsideFile, 'pwned\n')).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof WorkspaceError && error.reason === 'path-escapes-workspace',
    );
    expect(await readFile(outsideFile, 'utf8')).toBe('PRIVATE KEY\n');
  });

  it('refuses a path inside the root whose symlink target is outside it', async () => {
    // A string prefix check passes this: the path really does start with the
    // root. Only resolving the link tells you where the write would land, and
    // a project can contain symlinks for entirely innocent reasons, so this is
    // not a hypothetical attack - it is Tuesday.
    const root = await makeScratchRoot();
    const outside = await makeScratchRoot();
    const outsideFile = join(outside, 'id_rsa');
    await writeFile(outsideFile, 'PRIVATE KEY\n', 'utf8');
    await symlink(outsideFile, join(root, 'notes.txt'));

    const workspace = await Workspace.open(root);

    await expect(workspace.proposeEdit('notes.txt', 'pwned\n')).rejects.toSatisfy(
      (error: unknown) =>
        error instanceof WorkspaceError && error.reason === 'path-escapes-workspace',
    );
    expect(await readFile(outsideFile, 'utf8')).toBe('PRIVATE KEY\n');
  });
});

describe('Workspace.watch', () => {
  it('reports a change made to a watched file from outside the application', async () => {
    // The student edits these files in VS Code, and a build or a formatter
    // rewrites them too. An application that only knows about its own writes
    // shows the student a stale copy of their own project, and every proposal
    // it computes from that copy is stale before it is offered.
    const root = await makeScratchRoot();
    const file = join(root, 'main.c');
    await writeFile(file, 'int main(void) { return 0; }\n', 'utf8');

    const workspace = await Workspace.open(root);
    let reportChange: (change: WorkspaceChange) => void = () => {};
    const changed = new Promise<WorkspaceChange>((settle) => {
      reportChange = settle;
    });

    const watcher = await workspace.watch(reportChange, { debounceMs: 50 });

    try {
      // Written straight to disk, as another editor would: the workspace is
      // not told, it has to notice.
      await writeFile(file, 'int main(void) { return 1; }\n', 'utf8');

      expect((await changed).paths).toContain('main.c');
    } finally {
      await watcher.close();
    }
  }, 10_000);
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

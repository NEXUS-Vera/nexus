import { execFile } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

/**
 * The file layer through which Vera edits a student's project.
 *
 * Every edit is a two-step transaction with the student in the middle:
 * {@link Workspace.proposeEdit} computes what would change and touches nothing,
 * and only {@link Workspace.applyEdit} writes. That split is the product
 * promise - the agent recommends, the student approves - expressed as the only
 * shape of the API, so there is no path through this module that writes a file
 * the student never saw.
 */

/**
 * A pending, inert edit to one file.
 *
 * It carries the hash of the bytes it was computed against so that applying it
 * can prove the file has not moved underneath it since.
 */
export interface EditProposal {
  /** Workspace-relative path of the file the edit targets. */
  readonly path: string;
  /** Hash of the file's bytes at the moment the proposal was made. */
  readonly baseHash: string;
  /** The full contents the file would have if the proposal were applied. */
  readonly newContent: string;
  /** Unified-style rendering of the change, for the student to review. */
  readonly diff: string;
}

/** The record of an edit that was accepted and written. */
export interface AppliedEdit {
  /** Workspace-relative path of the file that was written. */
  readonly path: string;
  /**
   * Ref naming the checkpoint commit taken immediately before the write.
   *
   * `git show <ref>:<path>` yields the bytes the file had beforehand, so an
   * edit the student regrets is undoable even if they had never committed.
   */
  readonly checkpointRef: string;
}

export class Workspace {
  readonly #root: string;

  private constructor(root: string) {
    this.#root = root;
  }

  /**
   * Open a workspace rooted at `root`.
   *
   * The root is resolved to its real path once, here, because every later
   * containment decision compares against it. A root left as a symlink would
   * make those comparisons fail against paths that are in fact inside it.
   */
  static async open(root: string): Promise<Workspace> {
    return new Workspace(await realpath(root));
  }

  /** The resolved real path this workspace is confined to. */
  get root(): string {
    return this.#root;
  }

  /**
   * Compute what an edit would change, without changing it.
   *
   * Nothing here writes, creates, or so much as opens the file for writing.
   */
  async proposeEdit(relativePath: string, newContent: string): Promise<EditProposal> {
    const absolutePath = join(this.#root, relativePath);
    const current = await readFile(absolutePath, 'utf8');

    return {
      path: relativePath,
      baseHash: hashContent(current),
      newContent,
      diff: renderDiff(current, newContent),
    };
  }

  /**
   * Accept a proposal: checkpoint the workspace, then write the new content.
   *
   * The checkpoint is taken first and unconditionally. An edit that turns out
   * to be wrong is then a recoverable mistake rather than a lost afternoon.
   */
  async applyEdit(proposal: EditProposal): Promise<AppliedEdit> {
    const absolutePath = join(this.#root, proposal.path);
    const checkpointRef = await this.#checkpoint();

    await writeFile(absolutePath, proposal.newContent, 'utf8');

    return { path: proposal.path, checkpointRef };
  }

  /**
   * Snapshot the whole working tree into a commit reachable from a private ref.
   *
   * Deliberately built through a throwaway index rather than `git commit`: the
   * student's own index, HEAD, and branch are theirs, and a file layer that
   * stages or commits on their behalf would corrupt the history they are in the
   * middle of writing. Nothing here mutates any state the student can see.
   */
  async #checkpoint(): Promise<string> {
    const indexFile = join(await this.#gitDir(), `nexus-checkpoint-index-${randomUUID()}`);
    const env = { ...process.env, GIT_INDEX_FILE: indexFile };
    const head = await this.#headCommit();

    try {
      // Untracked files count: a file Vera is about to overwrite may never have
      // been added, and that is exactly the case where losing it hurts most.
      await this.#git(['add', '--all'], env);
      const tree = await this.#git(['write-tree'], env);

      const commit = await this.#git(
        [
          'commit-tree',
          tree,
          ...(head === undefined ? [] : ['-p', head]),
          '-m',
          'nexus: checkpoint before applying an agent edit',
        ],
        {
          ...env,
          // The checkpoint is Nexus's own act, and it must succeed even in a
          // repository where the student has not configured an identity.
          GIT_AUTHOR_NAME: CHECKPOINT_IDENTITY_NAME,
          GIT_AUTHOR_EMAIL: CHECKPOINT_IDENTITY_EMAIL,
          GIT_COMMITTER_NAME: CHECKPOINT_IDENTITY_NAME,
          GIT_COMMITTER_EMAIL: CHECKPOINT_IDENTITY_EMAIL,
        },
      );

      const ref = `${CHECKPOINT_REF_PREFIX}${new Date().toISOString().replaceAll(':', '-')}-${randomUUID()}`;
      await this.#git(['update-ref', ref, commit], env);

      return ref;
    } finally {
      await rm(indexFile, { force: true });
    }
  }

  /** Absolute path of the `.git` directory backing this workspace. */
  async #gitDir(): Promise<string> {
    return this.#git(['rev-parse', '--absolute-git-dir']);
  }

  /** The current commit, or `undefined` in a repository with no commits yet. */
  async #headCommit(): Promise<string | undefined> {
    try {
      return await this.#git(['rev-parse', '--verify', 'HEAD']);
    } catch {
      return undefined;
    }
  }

  /** Run git inside the workspace root and return its trimmed stdout. */
  async #git(args: readonly string[], env: NodeJS.ProcessEnv = process.env): Promise<string> {
    const { stdout } = await execFileAsync('git', [...args], { cwd: this.#root, env });
    return stdout.trim();
  }
}

/** Namespace for checkpoint refs: private to Nexus, invisible to `git branch`. */
const CHECKPOINT_REF_PREFIX = 'refs/nexus/checkpoints/';
const CHECKPOINT_IDENTITY_NAME = 'Nexus';
const CHECKPOINT_IDENTITY_EMAIL = 'nexus@localhost';

/** Content hash used to detect that a file moved underneath a proposal. */
function hashContent(content: string): string {
  return createHash('sha256').update(content, 'utf8').digest('hex');
}

/**
 * Render a line-oriented diff of `before` -> `after`.
 *
 * Identical head and tail lines are held in common and the remaining span is
 * shown as a removal followed by an addition. That is not the minimal edit
 * script a full diff algorithm would produce, but it is a truthful one, and the
 * student-facing diff view that would justify a smarter algorithm is a later
 * slice.
 */
function renderDiff(before: string, after: string): string {
  const beforeLines = before.split('\n');
  const afterLines = after.split('\n');

  let head = 0;
  while (
    head < beforeLines.length &&
    head < afterLines.length &&
    beforeLines[head] === afterLines[head]
  ) {
    head += 1;
  }

  let tail = 0;
  while (
    tail < beforeLines.length - head &&
    tail < afterLines.length - head &&
    beforeLines[beforeLines.length - 1 - tail] === afterLines[afterLines.length - 1 - tail]
  ) {
    tail += 1;
  }

  const removed = beforeLines.slice(head, beforeLines.length - tail);
  const added = afterLines.slice(head, afterLines.length - tail);

  return [
    ...beforeLines.slice(0, head).map((line) => ` ${line}`),
    ...removed.map((line) => `-${line}`),
    ...added.map((line) => `+${line}`),
    ...beforeLines.slice(beforeLines.length - tail).map((line) => ` ${line}`),
  ].join('\n');
}

import { createHash } from 'node:crypto';
import { readFile, realpath } from 'node:fs/promises';
import { join } from 'node:path';

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
}

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

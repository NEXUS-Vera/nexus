import { execFile } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { basename, dirname, join, resolve, sep } from 'node:path';
import { promisify } from 'node:util';

import { watch as watchPaths } from 'chokidar';

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

/** Why a workspace operation was refused. */
export type WorkspaceFailureReason =
  | 'not-a-git-repository'
  | 'path-escapes-workspace'
  | 'stale-proposal';

/** Typed refusal raised by {@link Workspace} operations. */
export class WorkspaceError extends Error {
  readonly reason: WorkspaceFailureReason;

  constructor(reason: WorkspaceFailureReason, message: string) {
    super(message);
    this.name = 'WorkspaceError';
    this.reason = reason;
  }
}

/** A batch of files that changed on disk since the last report. */
export interface WorkspaceChange {
  /** Workspace-relative paths, coalesced over one debounce window. */
  readonly paths: readonly string[];
}

/** A running watcher; closing it releases the underlying file-system handles. */
export interface WorkspaceWatcher {
  close(): Promise<void>;
}

/**
 * How long to wait for the disk to settle before reporting a change.
 *
 * One save in an editor is several file-system events - a temporary file, a
 * rename, a permission change - and a build touches hundreds of files at once.
 * Reporting each one separately would re-run whatever listens for every
 * keystroke of a save, so events are coalesced into one report per quiet
 * window.
 */
const DEFAULT_DEBOUNCE_MS = 100;

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
    const absolutePath = await this.#resolveInside(relativePath);
    const current = await readFile(absolutePath, 'utf8');

    return {
      path: relativePath,
      baseHash: hashContent(current),
      newContent,
      diff: renderDiff(current, newContent),
    };
  }

  /**
   * Accept a proposal: verify it is still current, checkpoint, then write.
   *
   * The student is expected to be editing these same files by hand, in their
   * own editor, while Vera works. So the bytes a proposal was computed against
   * are not guaranteed to still be the bytes on disk when the student presses
   * accept, and writing regardless would silently destroy whatever they typed
   * in between. The proposal is therefore re-validated against the file rather
   * than trusted, and a mismatch is refused instead of merged: only the student
   * can say which of the two versions they meant to keep.
   *
   * The checkpoint follows the check, so a refused apply leaves no trace at all.
   */
  async applyEdit(proposal: EditProposal): Promise<AppliedEdit> {
    const absolutePath = await this.#resolveInside(proposal.path);

    const currentHash = hashContent(await readFile(absolutePath, 'utf8'));
    if (currentHash !== proposal.baseHash) {
      throw new WorkspaceError(
        'stale-proposal',
        `${proposal.path} changed after this edit was proposed; ` +
          're-read the file and propose again rather than overwriting the change',
      );
    }

    const checkpointRef = await this.#checkpoint();

    await writeFile(absolutePath, proposal.newContent, 'utf8');

    return { path: proposal.path, checkpointRef };
  }

  /**
   * Decline a proposal.
   *
   * Deliberately does nothing, and deliberately still exists: rejection is a
   * real step in the accept/reject gate, and naming it keeps the caller from
   * inventing its own cleanup - unstaging, restoring, rewriting the file - to
   * undo a proposal that never changed anything in the first place. Proposals
   * are immutable values held by the caller, so dropping one is the whole act.
   */
  rejectEdit(_proposal: EditProposal): void {
    // Intentionally empty. See above.
  }

  /**
   * Watch the workspace for changes made by anything other than this process.
   *
   * The student keeps working in their own editor while Vera works, and builds
   * and formatters rewrite files too. Without this the application holds a copy
   * of the project that quietly diverges from the disk, and every proposal
   * computed against that copy is stale before it is offered - the same failure
   * the apply-time hash check refuses, arriving as a surprise rather than as
   * information.
   *
   * Resolves once the watcher is actually established, so a caller that writes
   * immediately afterwards cannot race the initial scan.
   */
  async watch(
    onChange: (change: WorkspaceChange) => void,
    options: { readonly debounceMs?: number } = {},
  ): Promise<WorkspaceWatcher> {
    const debounceMs = options.debounceMs ?? DEFAULT_DEBOUNCE_MS;
    // Scoped to the root and to the root alone: this watcher exists to observe
    // the student's project and has no business reporting anything else.
    const watcher = watchPaths(this.#root, {
      cwd: this.#root,
      // The initial scan is inventory, not news; reporting it would fire a
      // change for every file in the project at startup.
      ignoreInitial: true,
    });

    const pending = new Set<string>();
    let timer: NodeJS.Timeout | undefined;

    watcher.on('all', (_event, changedPath) => {
      if (changedPath === undefined) {
        return;
      }

      pending.add(changedPath);
      // Restarted on every event, so the report lands once the disk has been
      // quiet for a full window rather than once per event in a burst.
      clearTimeout(timer);
      timer = setTimeout(() => {
        onChange({ paths: [...pending] });
        pending.clear();
      }, debounceMs);
    });

    await new Promise<void>((settle) => {
      watcher.once('ready', () => {
        settle();
      });
    });

    return {
      close: async () => {
        // Timer first: a report delivered after close would reach a listener
        // that has already been torn down.
        clearTimeout(timer);
        await watcher.close();
      },
    };
  }

  /**
   * Turn a caller-supplied path into an absolute path proven to be inside the
   * workspace, or refuse.
   *
   * The path originates with a model, so it is untrusted input: a project file,
   * a pasted compiler error, or a datasheet can all steer it. Unchecked, this
   * module is an arbitrary-file-write primitive running as the student.
   */
  async #resolveInside(candidate: string): Promise<string> {
    // `resolve` collapses `..` segments and lets an absolute candidate replace
    // the root outright, so both traversal and an absolute path outside the
    // workspace end up outside. Checked first, and lexically, so the obvious
    // escapes are refused before the filesystem is touched at all.
    const lexicalPath = resolve(this.#root, candidate);
    this.#assertContained(lexicalPath, candidate);

    // A path can start with the root and still land outside it: `notes.txt`
    // may be a symlink to somewhere else entirely, and projects contain
    // symlinks for innocent reasons. A string comparison cannot see that, so
    // the links are resolved and the containment question asked again of the
    // path the write would actually reach.
    const realPath = await realpathOfNearestExisting(lexicalPath);
    this.#assertContained(realPath, candidate);

    return realPath;
  }

  /** Refuse a path that is not the root itself or something beneath it. */
  #assertContained(absolutePath: string, candidate: string): void {
    if (absolutePath !== this.#root && !absolutePath.startsWith(this.#root + sep)) {
      throw new WorkspaceError(
        'path-escapes-workspace',
        `Refusing to touch ${candidate}: it resolves outside the workspace root`,
      );
    }
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

  /**
   * Absolute path of the `.git` directory backing this workspace.
   *
   * A workspace with no repository behind it cannot be checkpointed, and an
   * edit that cannot be checkpointed has no undo. That is refused rather than
   * written unprotected, and refused under a reason the shell can act on -
   * offering to initialise a repository is a sensible response to
   * `not-a-git-repository`, and no response at all is possible to whatever
   * `git` printed on stderr.
   */
  async #gitDir(): Promise<string> {
    try {
      return await this.#git(['rev-parse', '--absolute-git-dir']);
    } catch {
      throw new WorkspaceError(
        'not-a-git-repository',
        `${this.#root} is not inside a git repository, so an edit applied here ` +
          'could not be undone; refusing to write',
      );
    }
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


/**
 * Resolve every symlink in a path, tolerating a file that does not exist yet.
 *
 * `realpath` fails outright on a missing leaf, but an edit may legitimately
 * create a new file. Resolving the deepest ancestor that does exist and
 * re-attaching the missing tail answers the only question that matters - where
 * would a write to this path actually land - without requiring the target to
 * already be there.
 */
async function realpathOfNearestExisting(absolutePath: string): Promise<string> {
  let existing = absolutePath;
  const missing: string[] = [];

  for (;;) {
    try {
      return join(await realpath(existing), ...missing.reverse());
    } catch {
      const parent = dirname(existing);
      if (parent === existing) {
        // Walked to the filesystem root without finding anything that exists.
        return absolutePath;
      }

      missing.push(basename(existing));
      existing = parent;
    }
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

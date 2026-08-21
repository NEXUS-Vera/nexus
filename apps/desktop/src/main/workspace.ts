import { execFile } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdir, readFile, readlink, realpath, rm, writeFile } from 'node:fs/promises';
import { basename, dirname, join, relative, resolve, sep } from 'node:path';
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
  | 'unresolvable-path'
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
  /**
   * Hash of the file's bytes at the moment the proposal was made, or `null` if
   * there was no file there yet.
   *
   * `null` is a value the apply-time check compares against like any other, so
   * a file that appeared in between is refused rather than overwritten: the
   * proposal was computed against "nothing", and something is not nothing.
   */
  readonly baseHash: string | null;
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
   *
   * A path with no file behind it is a proposal, not an error: adding a source
   * or header file is an ordinary agent edit, and it has to reach the same
   * accept/reject gate as every other one rather than escaping as a raw
   * `ENOENT` the caller cannot tell from a permissions failure.
   */
  async proposeEdit(relativePath: string, newContent: string): Promise<EditProposal> {
    const absolutePath = await this.#resolveInside(relativePath);
    const current = await readExistingFile(absolutePath);

    return {
      path: relativePath,
      baseHash: current === undefined ? null : hashContent(current),
      newContent,
      diff: current === undefined ? renderCreation(newContent) : renderDiff(current, newContent),
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
   * The checkpoint follows the check, so a refused apply leaves no trace at all -
   * except where the file appears in the window between the two, which the
   * exclusive create below catches after the checkpoint has been taken. That
   * leaves one unused checkpoint ref, which is private to Nexus and describes a
   * tree nothing was written to.
   */
  async applyEdit(proposal: EditProposal): Promise<AppliedEdit> {
    const absolutePath = await this.#resolveInside(proposal.path);

    const current = await readExistingFile(absolutePath);
    const currentHash = current === undefined ? null : hashContent(current);
    if (currentHash !== proposal.baseHash) {
      throw new WorkspaceError('stale-proposal', staleProposalMessage(proposal.path));
    }

    const checkpointRef = await this.#checkpoint(absolutePath, current !== undefined);

    if (current === undefined) {
      // A new file may name a directory the project does not have yet - a
      // `src/` in a flat sketch, a `drivers/` beside it. Without this the write
      // fails with the same bare ENOENT that proposing one used to, which is
      // the failure this path exists to remove. The parent is inside the
      // workspace because the whole resolved path already was.
      await mkdir(dirname(absolutePath), { recursive: true });
      await this.#createFile(absolutePath, proposal);
    } else {
      await writeFile(absolutePath, proposal.newContent, 'utf8');
    }

    return { path: proposal.path, checkpointRef };
  }

  /**
   * Write a file the proposal expects not to exist, and refuse if it does.
   *
   * `wx` is `O_CREAT | O_EXCL`, which the kernel refuses on any existing name
   * including a symbolic link - so the create neither follows a link that
   * appeared since the path was resolved nor overwrites a file that did. It is
   * the same refusal the hash comparison above makes, taken atomically at the
   * moment of the write rather than a moment before it.
   */
  async #createFile(absolutePath: string, proposal: EditProposal): Promise<void> {
    try {
      await writeFile(absolutePath, proposal.newContent, { encoding: 'utf8', flag: 'wx' });
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'EEXIST') {
        throw new WorkspaceError('stale-proposal', staleProposalMessage(proposal.path));
      }
      throw error;
    }
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
      // The repository's internals are not the student's project, and applying
      // an edit writes objects and a ref into them - so an unfiltered watcher
      // answers Nexus's own checkpoint back as "the project changed". A
      // consumer cannot tell that from the student typing.
      ignored: (candidate: string) => this.#isRepositoryInternal(candidate),
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

  /** Whether a path lies inside the repository's own bookkeeping. */
  #isRepositoryInternal(candidate: string): boolean {
    return relative(this.#root, candidate).split(sep).includes('.git');
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
  async #checkpoint(targetPath: string, targetExists: boolean): Promise<string> {
    const indexFile = join(await this.#gitDir(), `nexus-checkpoint-index-${randomUUID()}`);
    const env = { ...process.env, GIT_INDEX_FILE: indexFile };
    const head = await this.#headCommit();

    try {
      // Untracked files count: a file Vera is about to overwrite may never have
      // been added, and that is exactly the case where losing it hurts most.
      await this.#git(['add', '--all'], env);
      // `add --all` honours `.gitignore`, so the files git was told to ignore
      // are precisely the files the checkpoint would omit - generated headers,
      // board configs, local overrides, all of which are real work. The file
      // about to be overwritten is forced in regardless, so recoverability does
      // not depend on the student's ignore rules. Only this one file is forced:
      // the whole ignored tree would drag in build output and dependencies.
      //
      // A file that does not exist yet has no prior bytes to preserve, and
      // naming it here would fail the whole checkpoint on a pathspec that
      // matches nothing. Its undo is that the checkpoint does not contain it.
      if (targetExists) {
        await this.#git(['add', '--force', '--', targetPath], env);
      }
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
 * How many links deep to follow before declaring a path unresolvable.
 *
 * A symlink that points at itself, directly or around a cycle, resolves
 * forever. The kernel's own limit is in this range, so a path that needs more
 * hops than this could not be opened anyway.
 */
const MAX_SYMLINK_HOPS = 32;

/**
 * Resolve every symlink in a path, tolerating a file that does not exist yet.
 *
 * `realpath` fails outright on a missing leaf, but an edit may legitimately
 * create a new file. Resolving the deepest ancestor that does exist and
 * re-attaching the missing tail answers the only question that matters - where
 * would a write to this path actually land - without requiring the target to
 * already be there.
 *
 * The subtlety is that `realpath` reports a dangling symlink and an absent name
 * identically, as `ENOENT`, and those two are not the same question at all: a
 * name that is not there will be created where it lexically sits, while a link
 * whose target does not exist yet still redirects the write to that target,
 * anywhere on the filesystem. Walking past the second case would hand back the
 * link's own path and let the containment check pass on a write that lands
 * outside the workspace. So a failure is interrogated rather than assumed: if
 * the name is a link, its target is resolved and answered with; only a name
 * that is genuinely absent is treated as a tail to re-attach.
 */
async function realpathOfNearestExisting(absolutePath: string, hops = 0): Promise<string> {
  let existing = absolutePath;
  const missing: string[] = [];

  for (;;) {
    try {
      return join(await realpath(existing), ...missing.reverse());
    } catch {
      const target = await readlinkOrUndefined(existing);
      if (target !== undefined) {
        if (hops >= MAX_SYMLINK_HOPS) {
          throw new WorkspaceError(
            'unresolvable-path',
            `Refusing to touch ${absolutePath}: it passes through more than ` +
              `${MAX_SYMLINK_HOPS} symbolic links, so where it would land cannot be decided`,
          );
        }

        // A relative link is relative to the directory holding it, not to the
        // process's working directory.
        const resolvedTarget = resolve(dirname(existing), target);
        return join(
          await realpathOfNearestExisting(resolvedTarget, hops + 1),
          ...missing.reverse(),
        );
      }

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

/**
 * The target of a symbolic link, or `undefined` if this name is not one.
 *
 * `readlink` answers the question `realpath` cannot: whether a path that failed
 * to resolve failed because nothing is there, or because something is there and
 * points elsewhere.
 */
async function readlinkOrUndefined(absolutePath: string): Promise<string | undefined> {
  try {
    return await readlink(absolutePath);
  } catch {
    return undefined;
  }
}

/**
 * Read a file, reporting a missing one as absence rather than as a failure.
 *
 * Only `ENOENT` is swallowed: a permissions error or an unreadable directory is
 * a real fault, and turning it into "the file is not there" would make an edit
 * that cannot be written look like an edit that creates something.
 */
async function readExistingFile(absolutePath: string): Promise<string | undefined> {
  try {
    return await readFile(absolutePath, 'utf8');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return undefined;
    }
    throw error;
  }
}

/**
 * Render a file that does not exist yet as a pure addition.
 *
 * Diffing against an empty string would hold the trailing empty element the two
 * have in common and print it as a context line, which reads as though the
 * student already had something there. A file that did not exist has no
 * context: every line of it is added. The empty element `split` yields for a
 * trailing newline is dropped, because it terminates the last line rather than
 * being a line of its own.
 */
function renderCreation(content: string): string {
  if (content === '') {
    return '';
  }

  const lines = content.split('\n');
  if (lines[lines.length - 1] === '') {
    lines.pop();
  }

  return lines.map((line) => `+${line}`).join('\n');
}

/** The one account of a proposal that no longer describes what is on disk. */
function staleProposalMessage(path: string): string {
  return (
    `${path} is no longer the file this edit was proposed against - it has since been ` +
    'created, changed, or removed; re-read it and propose again rather than overwriting ' +
    'the change'
  );
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

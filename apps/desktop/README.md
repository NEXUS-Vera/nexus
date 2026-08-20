# Desktop Application

## Purpose

Electron shell for Nexus. Hosts the main process and the preload bridge that
will front local, machine-bound capabilities the browser cannot reach.

## Ownership boundary

Deployable desktop process only. This package owns process composition for the
Electron main process and the `contextBridge` surface exposed to the renderer.
It does not own UI: the renderer is `@nexus/web`. It does not own domain logic
or shared contracts.

## Architecture

```text
apps/desktop/
  src/main/         Electron main process (plain Node, no DOM)
  src/preload/      contextBridge surface exposed to the renderer
  vitest.config.ts  main-process test runner (Node environment)
  tsconfig.*.json   one project per boundary: main, preload, tooling
```

The three tsconfig projects exist to keep the boundaries honest at type level:
`tsconfig.main.json` has no `DOM` lib, so main-process code cannot reach for
browser globals; `tsconfig.preload.json` has `DOM` because preload runs in the
renderer's context; `tsconfig.node.json` covers repository tooling files.

## What belongs here

- Electron main-process lifecycle and window composition
- The preload `contextBridge` surface, typed and explicit
- Supervision of local sidecar processes owned by the desktop shell
- Machine-local filesystem access to the student's project, behind the shell's
  accept/reject gate
- Native-module integration that only makes sense in a desktop host

## What must not be placed here

- Renderer/UI code (belongs in `@nexus/web`)
- Shared or reusable platform logic (belongs in `packages/`)
- Domain-agent internals (belong in `agents/`)
- Business logic that a non-desktop deployment would also need

## Testing

```bash
pnpm --filter @nexus/desktop test
```

Main-process modules are tested as plain Node modules. The runner uses
`environment: 'node'` and never launches Electron, so suites run headless in CI
without a display. It follows that **main-process modules that need unit
coverage must not import `electron` at module scope** — outside an Electron
runtime, `require('electron')` resolves to the path of the binary, not the API.
Take Electron APIs as constructor or function arguments so they can be
substituted in tests, and confine direct `electron` imports to the composition
entry point.

`src/main/vitest-harness.test.ts` is a harness smoke check, not a product test.
It exists only to prove the runner is still Node-based and Electron-free.

## Current status

`src/main/sidecar-supervisor.ts` supervises the local `nexus_api` sidecar: it
spawns the process, reads the one-line loopback handshake from stdout, rejects
an unsupported handshake major version, fails fast when no handshake arrives,
restarts a crashed sidecar once before surfacing a terminal failure, and stops
it without leaving an orphan. It is a plain Node module and takes no Electron
dependency, so it is unit tested against the runner configured here.

`src/main/workspace.ts` is the file layer through which Vera edits a student's
project, behind an accept/reject gate. It is the only module in the shell that
can destroy a student's work, so its guarantees are stated as behaviour:

- `proposeEdit` computes a diff and touches nothing - not the bytes, not the
  mtime. Writing is only reachable through `applyEdit`.
- `applyEdit` re-hashes the file and refuses with a typed `stale-proposal` error
  if it changed since the proposal was made, because the student is expected to
  be editing the same files by hand in their own editor at the same time. It
  does not attempt a merge; only the student can say which version they meant.
- `applyEdit` snapshots the working tree into a commit under
  `refs/nexus/checkpoints/` before writing, built through a throwaway index so
  the student's own index, HEAD, and branch are untouched. The file being
  overwritten is force-added, so a `.gitignore`d file is recoverable too.
- Paths are model-influenced, so they are treated as untrusted input under
  `AGENTS.md` section 13: they are resolved against the root and refused unless
  contained by it, lexically first and then again after resolving symlinks.
- `watch` reports external changes, coalesced per quiet window and scoped to the
  root, excluding `.git`.

Everything else is still scaffold: no window creation, no application
lifecycle, and no packaging configuration. There is no diff-review UI yet; the
renderer half of the accept/reject gate is a later phase in `@nexus/web`.

### Known limits of the checkpoint

`applyEdit` refuses with a typed `not-a-git-repository` error when the
workspace has no repository behind it, rather than writing an edit that could
not be undone. Opening such a project and offering to initialise a repository
is a shell-level decision that is not implemented yet.

A checkpoint captures the working tree as it stands on disk at that moment, so
it cannot capture an editor buffer the student has not saved. Anything they had
staged is unaffected either way, because the checkpoint is built in a throwaway
index and their own is never written.

Ignored files other than the one being edited stay out of the checkpoint, which
is deliberate - forcing the whole ignored tree in would snapshot build output
and dependencies on every accepted edit.

The staleness check re-reads the file immediately before writing, which closes
the window between proposing and accepting but not the microseconds between the
check and the write. Closing that fully needs an atomic
compare-and-swap-on-content, which the filesystem does not offer directly.

Checkpoint refs are never pruned, so they accumulate; expiring them is future
work.

### Platform assumption

`stop()` assumes POSIX process semantics: `SIGTERM` asks the sidecar to exit and
`SIGKILL` ends it if the grace period lapses. On Windows neither signal is real;
`ChildProcess.kill` terminates the process abruptly and the sidecar's own
parent-death watchdog (which polls `os.getppid()`) does not apply. Windows
support is a later phase and is not covered by these tests.

## Future development expectations

- Windows process termination and orphan cleanup, using a job object or an
  equivalent mechanism rather than POSIX signals.
- A bundler and packaging pipeline; until then the entry points are typechecked
  but not emitted, and `package.json` deliberately declares no `main` field
  rather than pointing at a build output that does not exist.
- Terminal and serial-device integration, each added as its own phase with the
  native dependency introduced at that point, not ahead of it.

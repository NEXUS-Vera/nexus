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

## Sidecar stdio contract

The supervisor spawns the sidecar with `['pipe', 'pipe', 'inherit']`:

- **stdin** is a pipe that is never written to. It is a liveness signal: the
  operating system closes a dead process's pipe ends on every platform, so the
  sidecar treats EOF here as "the shell is gone" and shuts down. Its other
  watchdog polls `os.getppid()`, which detects a dead parent only because POSIX
  reparents orphans to init - Windows does not, so without this pipe a
  force-quit there strands a sidecar holding the database file.
- **stdout** carries the handshake line and nothing else.
- **stderr** is inherited, so sidecar logging reaches the shell's diagnostics
  rather than filling a pipe nobody reads.

Note that Node implements a `'pipe'` slot with a socketpair on unix rather than
a FIFO, so the sidecar accepts either.

## Current status

`src/main/sidecar-supervisor.ts` supervises the local `nexus_api` sidecar: it
spawns the process, reads the one-line loopback handshake from stdout, rejects
an unsupported handshake major version, fails fast when no handshake arrives,
restarts a crashed sidecar once before surfacing a terminal failure, and stops
it without leaving an orphan. It is a plain Node module and takes no Electron
dependency, so it is unit tested against the runner configured here.

`src/main/terminal-session.ts` runs a command on a real pseudoterminal: input
written to the session reaches the child, a resize is visible to the child
through `TIOCGWINSZ`, disposal reaps the whole process tree, and the exit status
is reported as a typed result that keeps exit code and signal apart. It is also
a plain Node module with no Electron dependency, and its suite drives a real
`/bin/sh` on a real PTY rather than a mocked `node-pty`.

A PTY rather than a pipe, because toolchains branch on `isatty()`: they emit
colour, progress bars, and width-wrapped diagnostics to a terminal and something
different to a pipe. Reading a pipe would mean reading output the student never
sees.

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
lifecycle, no renderer surface for either the terminal or the diff-review
gate, and no packaging configuration. The renderer halves are later phases
in `@nexus/web`.

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

Process termination in this package is **POSIX-only**, in both modules, and
neither is verified on Windows.

`SidecarSupervisor.stop()` assumes `SIGTERM` asks the sidecar to exit and
`SIGKILL` ends it if the grace period lapses. On Windows neither signal is real;
`ChildProcess.kill` terminates the process abruptly and the sidecar's own
parent-death watchdog (which polls `os.getppid()`) does not apply.

`TerminalSession.dispose()` has the same defect and fails the same way. It reads
the process tree with `ps`, signals each process group through a negative pid,
and escalates to `SIGKILL` — none of which exists on Windows. The code branches
on `process.platform` and degrades to terminating the shell alone, so a
descendant holding a device leaks. Both need a Win32 job object with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` rather than a port of the POSIX path.

### What node-pty verification does and does not cover

`node-pty` is the reference cross-platform PTY and is the implementation that
solved Windows ConPTY, which is a stated reason ADR-0003 chose Electron over
Tauri. That is a reason to expect Windows to be reachable; it is not evidence
that it works here. The suite has only been run on macOS (arm64). ConPTY differs
from a POSIX PTY in ways these tests specifically depend on — there is no
`stty`, no process group, and no kernel hangup of a foreground group — so the
resize and disposal cases prove nothing about Windows until they run on a
Windows runner. All current CI workflows are `ubuntu-latest` only.

## Future development expectations

- Windows process termination and orphan cleanup, using a job object or an
  equivalent mechanism rather than POSIX signals.
- A bundler and packaging pipeline; until then the entry points are typechecked
  but not emitted, and `package.json` deliberately declares no `main` field
  rather than pointing at a build output that does not exist.
- Serial-device integration, added as its own phase with the native dependency
  introduced at that point, not ahead of it.
- A renderer surface for `TerminalSession`, over the preload bridge. The session
  is deliberately headless: it owns the process, not the view.

### Packaging `node-pty`

`node-pty` is a native addon, so packaging has requirements the test suite never
exercises. Recorded here so they are not discovered during a release:

- **Rebuild against Electron's ABI.** The prebuilds installed here are built for
  Node's ABI. Electron embeds a different one, and loading the wrong build fails
  at runtime on the user's machine with `NODE_MODULE_VERSION` mismatch, not at
  build time. `electron-rebuild` (or `@electron/rebuild`) has to run against the
  exact Electron version being shipped, which couples Electron upgrades to this
  dependency.
- **Rebuild per platform and architecture.** Native addons do not
  cross-compile, so each target needs its own build: `darwin-arm64`,
  `darwin-x64`, `win32-x64`. This is the same matrix ADR-0003 already requires
  for the PyInstaller freeze.
- **Keep the binaries unpacked from the asar.** `node-pty` resolves its POSIX
  `spawn-helper` relative to its own directory and execs it. An executable
  inside an `app.asar` cannot be exec'd, so `pty.node` and `spawn-helper` must
  be listed in `asarUnpack`. The library already rewrites `app.asar` to
  `app.asar.unpacked` in that path, which only works if the files are actually
  unpacked there.
- **Preserve the executable bit on `spawn-helper`.** This is not hypothetical.
  The current stable release, 1.1.0, publishes that file mode `0644`, so
  `node-pty` cannot exec its own helper and every spawn fails with
  `posix_spawnp failed`. The dependency is pinned to the exact prerelease
  `1.2.0-beta.15`, which restores the bit. Any signing, notarization, or
  archiving step in the pipeline must preserve it too, and the pin should not be
  moved to a 1.1.x line without re-checking.
- **Code signing on macOS.** Both `pty.node` and `spawn-helper` are Mach-O
  binaries and each needs its own signature; notarization rejects an unsigned
  nested executable.

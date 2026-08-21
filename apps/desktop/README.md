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
  src/main/            Electron main process (plain Node, no DOM)
  src/preload/         contextBridge surface exposed to the renderer
  src/shared/          the few declarations main and preload must agree on
  e2e/                 Playwright suites that launch the built application
  vitest.config.ts     main-process test runner (Node environment)
  playwright.config.ts Electron smoke-suite runner
  tsconfig.*.json      one project per boundary: main, preload, e2e, tooling
```

The tsconfig projects exist to keep the boundaries honest at type level:
`tsconfig.main.json` has no `DOM` lib, so main-process code cannot reach for
browser globals; `tsconfig.preload.json` has `DOM` because preload runs in the
renderer's context; `tsconfig.e2e.json` has `DOM` because `page.evaluate`
callbacks are renderer code; `tsconfig.node.json` covers repository tooling.

`src/shared/` holds only what the main process and the preload script must
agree on, and takes no Electron or Node imports: a sandboxed preload can
require nothing but a small allowlist, so anything it reads has to be portable
into that context.

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
  sidecar treats EOF here as "the shell is gone" and shuts down
  (`_watch_stdin` in `nexus_api/__main__.py`). Its other watchdog polls
  `os.getppid()`, which detects a dead parent only because POSIX reparents
  orphans to init - Windows does not, so without this pipe a force-quit there
  strands a sidecar holding the database file. The sidecar arms the stdin
  watchdog only when fd 0 really is a pipe, so a terminal, a file, or
  `/dev/null` reporting EOF does not stop a server started by hand.
- **stdout** carries the handshake line and nothing else.
- **stderr** is inherited, so sidecar logging reaches the shell's diagnostics
  rather than filling a pipe nobody reads.

Note that Node implements a `'pipe'` slot with a socketpair on unix rather than
a FIFO, so the sidecar accepts either.

A second suite launches the real thing:

```bash
pnpm --filter @nexus/desktop test:e2e
```

It builds the shell and the renderer, then drives a real Electron process with
Playwright. Some properties only exist at runtime and cannot be asserted any
other way: how the renderer routes over `file://`, what the preload bridge
actually reaches, which storage backend the sidecar was started with, and where
the student's database lands. It needs a display, so it is kept out of `test`
rather than making the unit runner conditional on one - but it is not optional:
`scripts/run-e2e.sh` runs it after the web suite (under `xvfb-run` on Linux), so
`make test-e2e` and the Playwright E2E workflow both cover it. A suite that
pins a security surface has to actually run, or it pins nothing.

These suites spawn `e2e/fixtures/fake-sidecar.mjs` instead of the Python API.
The fixture binds a real loopback socket and speaks the real handshake, so the
shell does the work it does in production while the suite stays runnable on a
machine with no Python runtime.

## Building

```bash
pnpm --filter @nexus/desktop build
```

Electron cannot execute TypeScript, so both entry points are bundled to
CommonJS with esbuild, alongside the renderer built from `@nexus/web` with a
relative asset base (absolute `/assets/...` URLs do not resolve over `file://`).
The preload is bundled rather than merely compiled because a sandboxed preload
can require nothing but a small allowlist, so it has to be one self-contained
file.

## Current status

`src/main/index.ts` composes the shell: it mints a session token with
`crypto.randomBytes`, starts the sidecar, waits for its handshake, and opens a
window that reaches the local API through the preload bridge and nothing else.
Startup failures - a sidecar that will not start, a renderer bundle that is not
there - are reported as messages naming a cause and a remedy. The sidecar's
shutdown is hung on `before-quit`, which every exit passes through, and is
arranged before the window exists so a quit during startup cannot outrun it.

It also decides two things the sidecar cannot decide for itself. The database
lives at `nexus.sqlite3` under Electron's `userData` directory, which is a
`Nexus` folder inside the per-user application data location the operating
system set aside for it - `~/Library/Application Support/Nexus` on macOS,
`%APPDATA%\Nexus` on Windows. That name comes from `productName` in
`package.json`, declared rather than defaulted: Electron otherwise falls back to
`name`, and this package is scoped, so the scope would end up in the path a
student's projects live in permanently. The sidecar is spawned with
`NEXUS_STORAGE_BACKEND=sqlite` pointing at that file, because the API's own
default backend is in-memory and would lose every project on quit. And when the supervisor replaces a crashed sidecar, the replacement binds
a different port, so the shell rewrites the runtime configuration the bridge
serves and reloads the window. The preload exposes named values rather than a
channel the page can poll, so a reload is how the renderer learns the new
address; without it the window would look healthy while every request failed.

`webContents.reload()` rather than a fresh `loadFile`, because it re-requests
the entry the window is already on and keeps the fragment with it - which under
the renderer's hash routing is the student's current view. What a reload cannot
keep is state held only in the page, a half-written message to Vera among it.
So the replacement configuration carries `serviceRestarted`, the bridge exposes
it as `window.nexus.shell.serviceRestarted`, and `@nexus/web` renders a notice
saying the local service restarted and the view was reloaded. The flag is spent
when it is served, so it describes the one load the restart caused rather than
every load after it.

`src/main/sidecar-supervisor.ts` supervises the local `nexus_api` sidecar: it
spawns the process, reads the one-line loopback handshake from stdout, rejects
an unsupported handshake major version, fails fast when no handshake arrives,
restarts a crashed sidecar once before surfacing a terminal failure, and stops
it without leaving an orphan. The restart policy arms only once `start()` has
resolved: a sidecar that dies before it ever announces is a build that cannot
start, so it is reported once through the typed `SidecarStartError` rather than
respawned into a replacement no one is waiting for and no one owns. A
replacement that does spawn but never announces is reported too, as a
`restart-failed` terminal error, because nothing downstream would otherwise
hear about it - its rejection clears the current child before its own `exit`
fires, so that event reads as superseded and is dropped. Reporting is
idempotent, since which of the two wins that race is not ordered.

It is also what decides the sidecar's environment. `NEXUS_API_HOST`,
`NEXUS_API_PORT`, `NEXUS_API_SESSION_TOKEN`, `NEXUS_API_CORS_ORIGINS`,
`NEXUS_STORAGE_BACKEND` and `NEXUS_DATABASE_URL` are all stated after the
inherited environment rather than left to it. For a developer running the API by
hand those are a configuration surface; for a packaged application they are
decisions already made, and a shell profile exporting `NEXUS_API_HOST=0.0.0.0`
would otherwise bind every interface - publishing a student's project API to
their whole network, with nothing on screen to say so, behind a token alone.

It is a plain Node module and takes no Electron dependency, so it is unit tested
against the runner configured here.

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
  mtime. Writing is only reachable through `applyEdit`. A file that does not
  exist yet is proposed against empty content with a `null` base hash, so
  adding a source or header file goes through the same gate as changing one.
- `applyEdit` re-hashes the file and refuses with a typed `stale-proposal` error
  if it is no longer what the proposal was computed against, because the student
  is expected to be editing the same files by hand in their own editor at the
  same time. That covers a file that changed, one that was removed, and one that
  appeared where the proposal expected nothing. It does not attempt a merge;
  only the student can say which version they meant.
- `applyEdit` snapshots the working tree into a commit under
  `refs/nexus/checkpoints/` before writing, built through a throwaway index so
  the student's own index, HEAD, and branch are untouched. The file being
  overwritten is force-added, so a `.gitignore`d file is recoverable too.
- Paths are model-influenced, so they are treated as untrusted input under
  `AGENTS.md` section 13: they are resolved against the root and refused unless
  contained by it, lexically first and then again after resolving symlinks. A
  symbolic link whose target does not exist yet is resolved too, rather than
  being mistaken for an absent file - `realpath` reports both as `ENOENT`, and
  walking past the link would let a create land wherever it points. Creating a
  new file is opened `O_EXCL`, so it refuses any name that has appeared since,
  a link included.
- Every refusal the file system has an account of arrives as a typed
  `WorkspaceError`, not a bare errno: `not-a-file` for a path that names a
  directory, `permission-denied` for one the file system will not open, and
  `unresolvable-path` for a name that cannot be resolved at all. Naming a
  directory is an ordinary model slip, and a caller that has only an `EISDIR`
  string cannot tell it from a permissions problem.
- `watch` reports external changes, coalesced per quiet window and scoped to the
  root, excluding `.git`.

What is not here yet is the renderer half: neither `TerminalSession` nor the
diff-review gate has a surface in `@nexus/web`, and both are later phases there.
Packaging is also still open - see *Future development expectations* below.

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

There is no packaging configuration yet, and no application menu.

### What the shell spawns

The sidecar executable is configuration, not a constant: a source checkout runs
the repository's interpreter and a packaged application runs the runtime inside
the bundle, and neither can be hard-coded without excluding the other.

```bash
NEXUS_SIDECAR_COMMAND=/path/to/python
NEXUS_SIDECAR_ARGS='["-m","nexus_api"]'
```

`NEXUS_SIDECAR_ARGS` is JSON rather than a whitespace-separated string because
the paths that end up in it routinely contain spaces. With no command
configured the shell says so, rather than spawning nothing and reporting a
handshake that never arrived.

### The renderer boundary

The window states `contextIsolation`, `nodeIntegration`, `sandbox` and
`webSecurity` explicitly even though they match Electron's current defaults.
They are the shell's security posture, and a default is a decision someone else
gets to change. Vera writes files and spawns shells on the user's machine, so a
renderer holding any Node handle turns a cross-site script or a hostile model
output into arbitrary local code execution.

The bridge exposes named values, never a callable taking a channel the page
chooses. `e2e/shell.e2e.test.ts` pins the whole surface, so widening it means
saying so in a test.

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
  equivalent mechanism rather than POSIX signals. The sidecar's stdin-EOF
  watchdog already covers the sidecar itself there; what remains is the
  descendant tree a `TerminalSession` leaves behind.
- A packaging pipeline. `pnpm build` bundles both entry points and the renderer,
  and `package.json` points `main` at `dist/main/index.cjs`, but nothing yet
  produces a distributable application. The renderer bundle is rebuilt in place,
  so a launch during a rebuild finds no interface - reported rather than crashed
  on, but packaging is what removes the window entirely.
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

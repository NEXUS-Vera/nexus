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

A second suite launches the real thing:

```bash
pnpm --filter @nexus/desktop test:e2e
```

It builds the shell and the renderer, then drives a real Electron process with
Playwright. Some properties only exist at runtime and cannot be asserted any
other way: how the renderer routes over `file://`, and what the preload bridge
actually reaches. It needs a display, so it is kept out of `test` rather than
making the unit runner conditional on one.

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

`src/main/sidecar-supervisor.ts` supervises the local `nexus_api` sidecar: it
spawns the process, reads the one-line loopback handshake from stdout, rejects
an unsupported handshake major version, fails fast when no handshake arrives,
restarts a crashed sidecar once before surfacing a terminal failure, and stops
it without leaving an orphan. It is a plain Node module and takes no Electron
dependency, so it is unit tested against the runner configured here.

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

`stop()` assumes POSIX process semantics: `SIGTERM` asks the sidecar to exit and
`SIGKILL` ends it if the grace period lapses. On Windows neither signal is real;
`ChildProcess.kill` terminates the process abruptly and the sidecar's own
parent-death watchdog (which polls `os.getppid()`) does not apply. Windows
support is a later phase and is not covered by these tests.

## Future development expectations

- Windows process termination and orphan cleanup, using a job object or an
  equivalent mechanism rather than POSIX signals.
- A packaging pipeline. The entry points are bundled but not yet packaged into
  a distributable application, and the renderer bundle is rebuilt in place,
  which means a launch during a rebuild finds no interface. That is reported
  rather than crashed on, but packaging is what removes the window entirely.
- Terminal and serial-device integration, each added as its own phase with the
  native dependency introduced at that point, not ahead of it.

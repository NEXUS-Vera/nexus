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

Scaffold only. There is no window creation, no application lifecycle, no
sidecar supervision, and no packaging configuration yet.

## Future development expectations

- A `SidecarSupervisor` for local sidecar process lifecycle, unit tested in
  plain Node against the runner configured here.
- A bundler and packaging pipeline; until then the entry points are typechecked
  but not emitted, and `package.json` deliberately declares no `main` field
  rather than pointing at a build output that does not exist.
- Terminal and serial-device integration, each added as its own phase with the
  native dependency introduced at that point, not ahead of it.

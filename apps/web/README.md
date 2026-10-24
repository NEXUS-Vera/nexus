# Web Application

## Purpose

User-facing Vera UI for embedded project initialization and the Nexus project
board workspace.

## Ownership boundary

Frontend application only. Contract types are imported from `@nexus/contracts`
(generated from JSON Schemas). Do not duplicate domain types in this app.

## Architecture

```text
apps/web/src/
  pages/           Home (init) + project workspace
  components/      layout shell, inspector, statuses, feedback
  artifacts/       product registry + workspaces
    renderers/     frontend workspace renderer registry (by artifactType)
    shell/         shared ArtifactWorkspaceShell
  api/             typed API client
  hooks/           theme + URL workspace state
  views/           overview + mind graph
  styles/          design tokens + base CSS
```

The project board uses a 64px header, collapsible workflow rail, central
workspace, and a collapsible context inspector with Context | Vera modes.

`ARTIFACT_REGISTRY` describes product availability and rail metadata.
`WORKSPACE_RENDERER_REGISTRY` maps `artifactType` / route keys to React
workspace components. Lookup is by key, never array position.

## Routes

Routing is hash-based (`HashRouter`), so a route survives being loaded from
disk: the desktop shell serves this bundle over `file://`, where a path-based
route has no server to rewrite it onto `index.html`.

- `/#/` — create a new project
- `/#/projects/:projectId` — persisted board workspace

Workspace URL query params:

- `view` — `overview` | `workspace` | `mind-graph`
- `artifact` — registry route key (for example `requirement-set`)
- `req`, `node`, `role`, `test`, `risk` — selection deep-links
- `sel`, `selId`, `revType`, `revVersion` — inspector selection
- `panel` — `context` | `vera` (inspector sidecar mode)
- `history=1` — open history panel

Browser refresh reloads live project state from the API.

## Live vs placeholder artifacts

| Artifact | Status |
| --- | --- |
| Project Brief | Live (`project-brief`) |
| Requirements | Live (`requirement-set`) |
| Architecture | Live (`functional-architecture`) |
| Next Action | Live global (`next-action`) |
| Components | Live (`component-plan`) |
| Firmware | Live scaffold, patch, and compile workspace (`firmware-scaffold`) |
| Analysis | Placeholder |
| Test Plan | Placeholder |
| Risk Register | Placeholder |

Mind Graph is a dependency preview until a canonical graph source exists.

## API

Base URL and credential are resolved in `src/api/client.ts`, in this order:

1. the desktop shell's preload bridge (`window.nexus.api`), which carries the
   port the sidecar actually bound and a token minted for that launch - neither
   is knowable at build time;
2. `VITE_API_BASE_URL` / `VITE_API_SESSION_TOKEN`;
3. `http://127.0.0.1:8000` and the published development token.

Every request sends `Authorization: Bearer <token>`; no route is exempt. See
[`apps/api/README.md`](../api/README.md) for what the API does with it, and
[`apps/desktop/README.md`](../desktop/README.md) for the bridge that supplies it.

Client methods in `src/api/client.ts`:

- `POST /v1/projects/initialize`
- `GET /v1/projects/:id`
- `GET /v1/projects/:id/artifacts`
- `GET /v1/projects/:id/artifacts/:type?version=`
- `GET /v1/projects/:id/history`
- `POST /v1/projects/:id/turns`
- `GET /v1/artifact-types`
- `GET /v1/projects/:id/board`
- `GET|POST /v1/projects/:id/artifacts/:type/workspace`
- `POST /v1/projects/:id/artifact-commands`
- `GET /v1/projects/:id/executions`
- `GET /v1/projects/:id/events`
- `GET /v1/projects/:id/graph`
- `GET /v1/projects/:id/artifacts/execution-plan` (`getExecutionPlan`)
- `POST /v1/projects/:id/execution-plan/propose` and `/materialize`
- `POST /v1/projects/:id/artifact-commands` revision acceptance/rejection helpers
- `POST /v1/projects/:id/repair` (`startRepair`, `getRepair`, `advanceRepair`, including cancellation)
- `GET /healthz` (`getHealthz`, including initialization provider and storage backend)

Revision decision helpers take caller-supplied command IDs, timestamps, actor and
version guards. Rejection accepts an optional reason and sends `rejected` when
omitted, satisfying the existing command schema. Plan and repair methods expose
the backend workflow envelopes without starting or approving any work themselves.
Health fields describe initialization and persistence, not toolchain availability.

`src/lib/invalidation-counts.ts` counts evidence-chain rows whose applicability is
`STALE` or `RECHECK_REQUIRED`, independently of historical assessments. It does not
deduplicate tests linked to multiple requirements. These helpers have no visible UI.

Board / kernel endpoints may return 404 until the API lands; the UI falls back
gracefully to current-state artifacts.

`src/views/ExecutionPlanReview.tsx` presents the typed execution-plan content as
steps with dependencies, a requirement/objective table and a pinout card. Its
accept/reject callbacks leave revision commands to the caller; rejection permits
an optional reason but provides no rationale input. The component is unmounted
pending W8 placement and rejection UX decisions. `EvidenceExplorer` accepts an
optional `onInspectRun(runId)` callback to show Inspect run for rows with execution
run IDs. No caller supplies it yet; run navigation remains pending. These pieces
do not complete the W8 real API/SQLite journey acceptance gate.

## Local development

```bash
cp apps/web/.env.example apps/web/.env   # optional
make dev-api    # defaults to fixture provider + memory store
make dev-web
```

Fixture mode does not require a model key:

```bash
NEXUS_INITIALIZATION_PROVIDER=fixture
```

Optional LLM initialization is configured on the API, not the web app.

## Tests

```bash
pnpm --filter @nexus/web test
make test-e2e   # Playwright; starts API+web in fixture/memory mode, then runs
                # the Electron shell suite
```

## Current limitations

- Component plan comparison is live for roles, candidates, and selection actions;
  datasheet retrieval remains deferred until providers are connected.
- Remaining unfinished artifact workspaces are honest placeholders.
- Electrical/Physical architecture modes are labeled placeholders.
- Mind Graph is a preview derived from board slots, not graph memory.
- Device simulation, verification runs, firmware execution, and notebooks are
  not implemented.
- Historical revision inspect uses metadata; versioned fetch is available via
  `getArtifactVersion` for future detail views.

Future artifact workspace implementations belong under `src/artifacts/<name>/`
and must be registered in `artifacts/renderers/registry.tsx`.

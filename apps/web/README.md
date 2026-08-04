# Web Application

## Purpose

User-facing Vera UI for embedded project initialization and the Nexus project
board workspace.

## Ownership boundary

Deployable frontend only. Contract types are imported from `@nexus/contracts`
(generated from JSON Schemas). Do not duplicate domain types in this app.

## Architecture

```text
apps/web/src/
  pages/           Home (init) + project workspace
  components/      layout shell, inspector, statuses, feedback
  artifacts/       registry + live/placeholder workspaces
  api/             typed API client
  hooks/           theme + URL workspace state
  views/           overview + mind graph
  styles/          design tokens + base CSS
```

The project board uses a 64px header, collapsible workflow rail, central
workspace, and collapsible context inspector.

## Routes

- `/` — create a new project
- `/projects/:projectId` — persisted board workspace

Workspace URL query params:

- `view` — `overview` | `workspace` | `mind-graph`
- `artifact` — registry route key (for example `requirement-set`)
- `req`, `node`, `test`, `risk` — selection deep-links
- `sel`, `selId`, `revType`, `revVersion` — inspector selection
- `history=1` — open history panel

Browser refresh reloads live project state from the API.

## Live vs placeholder artifacts

| Artifact | Status |
| --- | --- |
| Project Brief | Live (`project-brief`) |
| Requirements | Live (`requirement-set`) |
| Architecture | Live (`functional-architecture`) |
| Next Action | Live global (`next-action`) |
| Components | Placeholder |
| Firmware | Placeholder |
| Analysis | Placeholder |
| Test Plan | Placeholder |
| Risk Register | Placeholder |

Mind Graph is a dependency preview until a canonical graph source exists.

## API

Base URL: `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`).

Client methods in `src/api/client.ts`:

- `POST /v1/projects/initialize`
- `GET /v1/projects/:id`
- `GET /v1/projects/:id/artifacts`
- `GET /v1/projects/:id/artifacts/:type?version=`
- `GET /v1/projects/:id/history`
- `POST /v1/projects/:id/turns`

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
make test-e2e   # Playwright; starts API+web in fixture/memory mode
```

## Current limitations

- Unfinished artifact workspaces are honest placeholders.
- Electrical/Physical architecture modes are labeled placeholders.
- Mind Graph is a preview derived from board slots, not graph memory.
- Device simulation, verification runs, firmware execution, and notebooks are
  not implemented.
- Historical revision inspect uses metadata; versioned fetch is available via
  `getArtifactVersion` for future detail views.

Future artifact workspace implementations belong under `src/artifacts/<name>/`.

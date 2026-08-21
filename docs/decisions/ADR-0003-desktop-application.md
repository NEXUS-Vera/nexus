# ADR-0003: Ship Nexus as a desktop application

**Status:** Accepted
**Context:** design session with the founder, 2026-08-20 - deciding the shipping form factor for Nexus before the embedded-systems vertical goes in front of students.

## Context

Three drivers, established with the founder in that session. They are ordered by how hard they bind, not by how often they come up.

1. **Local hardware access.** The embedded-systems vertical is about a student and a dev board on a desk. Nexus has to open serial/USB to that board, flash firmware onto it, and drive locally-installed toolchains. A browser page cannot do this. WebSerial and WebUSB cover a fraction of it, on a fraction of the browsers, behind a per-connection permission prompt, and they do not reach `esptool`, `openocd`, `avrdude`, or a vendor SDK sitting on disk. There is no partial version of this requirement: either the process can open `/dev/tty*` and `exec` a toolchain, or the vertical does not work.
2. **IDE and terminal integration.** Nexus must spawn real PTYs and interoperate with the editor the student already has open, in practice VS Code with PlatformIO. Owning the build-flash-observe loop means reading the student's project on disk, running their build, and showing them the same output their terminal would show. That is process spawning and filesystem access, which is again outside what a page is allowed to do.
3. **Distribution and cost.** A downloadable binary has no hosting bill. Compute is the student's. This matters at the current stage: the repository has no deployment path built yet anyway. There is no `Dockerfile` anywhere in the tree, `infra/terraform` is a `README.md` and nothing else, and `infra/docker/docker-compose.yml` defines exactly one service, a local Postgres for development. Choosing desktop now avoids building a hosting story rather than abandoning one.

## Decision

Nexus ships as an **Electron desktop application**.

- **Shell.** Electron main process, with `node-pty` for terminals and `serialport` for board access.
- **Renderer.** `apps/web` becomes the renderer. It is already a Vite + React SPA (`apps/web/vite.config.ts`, React 18, dev server on `127.0.0.1:5173`) and needs no rewrite to be loaded by a `BrowserWindow`.
- **Backend as sidecar.** The Python backend, meaning `apps/api` and the agents and packages it imports, is frozen with PyInstaller and shipped inside the app bundle. The shell spawns it on an ephemeral loopback port and hands the renderer a per-session token. It is a child process, not a service.
- **Store.** SQLite becomes the desktop store. Postgres is **retained** behind the existing `build_project_store` factory in `packages/persistence/src/nexus_persistence/factory.py`, which today dispatches on `NEXUS_STORAGE_BACKEND` to `InMemoryProjectStore` or `PostgresProjectStore`. Adding a SQLite backend is a third branch in that one function, not a rewrite of every call site, because `apps/api/src/nexus_api/main.py` constructs its store through that factory once and passes the resulting `ProjectPackageStore` into the services. Keeping the Postgres branch alive keeps a hosted deployment reachable later without a second ADR.
- **Model access.** Model calls go through a Nexus-operated proxy that holds the provider keys and runs the light/heavy router. Students never hold API keys. Today the opposite is true in both model paths: `apps/api/src/nexus_api/config.py` reads `NEXUS_MODEL_API_KEY` from the local environment, and Mind Graph's `adapters.from_env` reads `MG_API_KEY`. Both become "point at the Nexus proxy" once the proxy exists.

## Why not the alternatives

**Tauri.** Rejected. Tauri would add Rust as a third language to a repository that is already Python plus TypeScript, and `AGENTS.md` §3 asks us to keep boundaries legible to humans and coding agents alike. That cost would be worth paying for a real benefit, and the binary size is a real benefit, but the thing we most need is the thing Tauri is weakest at: `node-pty` is the reference implementation for Windows ConPTY, and our student population is Windows-heavy. Betting the terminal on a less-travelled path, on the platform where terminals are hardest, is the wrong risk to take.

**A VS Code extension.** Rejected. It sounds appealing given driver (2), since the student is already in VS Code. It fails on the interface. The Mind Graph map is a WebGL canvas (`apps/mind-graph-web/src/components/MapView.tsx` renders a graph through Sigma into a `.map-canvas` host sized `width: 100%; height: min(62vh, 560px)`, and the file already carries a scar comment about leaking WebGL contexts on remount), and `apps/web` carries a real design system in `apps/web/src/styles/tokens.css`. A VS Code webview is a cramped, sandboxed panel with its own CSP and theming, sharing screen space with the editor. Putting a spatial canvas and a full design system in there would mean designing for the constraint rather than for the product.

**Building a full IDE, or embedding an editor.** Rejected as multi-year scope against VS Code, Cursor, and the JetBrains line, with the win condition being "as good as an editor people already have". Nexus is a **companion**: it owns the build-flash-observe loop and the reasoning around it, and it leaves editing to the editor. This is a scope boundary, not a temporary staging decision, and a later reversal should be a new ADR.

## Relationship to ADR-0001

The modular monorepo **stands**. Nothing here argues for splitting repositories, and the set of areas in the `AGENTS.md` §3 ownership map is unchanged.

One assumption in ADR-0001 is **partly superseded** and is recorded here so the two do not silently drift. Before this ADR, `AGENTS.md` §3 and `docs/architecture/overview.md` both described `apps/` as "deployable applications"; both now read "top-level applications" and defer here. Under this ADR:

- `apps/web` is no longer a deployed site. It is a renderer bundled into a desktop binary.
- `apps/api` is no longer a deployed service. It is a frozen sidecar spawned by the shell.

The `apps/` boundary itself survives intact, because what it was really enforcing is that shared business logic does not live in `apps/` (`AGENTS.md` §3, final line). That rule is unaffected and still binds. Only the word "deployable" narrows: `apps/` now means "the top-level assembled artifacts", of which some are shipped and some may later be deployed. The Postgres branch in `build_project_store` is deliberately kept so that "may later be deployed" is not hypothetical.

Worth stating plainly: this supersession is cheap precisely because nothing was ever deployed. There is no Dockerfile, no Terraform, and no release pipeline to unwind. We are narrowing an intention, not retiring an implementation.

## Relationship to ADR-0002

**Unaffected.** Not by assertion, and not merely because Mind Graph "keeps its own store" as ADR-0002 says. Checked:

- Mind Graph's ledger is **already SQLite**. `agents/mind-graph/src/mindgraph/ledger.py` imports `sqlite3` at module level, and `Ledger.__init__` (around line 65) is `sqlite3.connect(str(path))` on a path defaulting to `":memory:"`, immediately followed by `PRAGMA journal_mode = WAL` and an `executescript` of the `events` table DDL. There is no server, no connection pool, and no network dependency anywhere in the class.
- It is already stored as a **local file per user**. `agents/mind-graph/src/mindgraph/tenancy.py` provisions `users/{user_id}/ledger.db` plus `sidecars/` and `blobs/` directories, and its module docstring states outright that "tenancy isolation is a filesystem property plus a path check". That is a desktop-shaped design that happened to be written before this decision.
- Its API surface is already **loopback-bound with a token**. `agents/mind-graph/src/mindgraph/api.py` ends in `serve(api, host: str = "127.0.0.1", port: int = 8787)` over a stdlib `ThreadingHTTPServer`, minting opaque role tokens via `secrets.token_urlsafe(24)` and checking capabilities server-side. The pattern this ADR proposes for `apps/api` already exists in the repository, one directory over.

So the desktop pivot asks nothing of Mind Graph that it does not already do. ADR-0002's separate-store decision is not weakened by SQLite becoming the desktop store for `apps/api`; if anything the two now agree on a substrate they previously agreed on only by coincidence. ADR-0002 needs no amendment.

## Consequences

- **Per-platform release engineering.** Every CI workflow in `.github/workflows` currently runs on `ubuntu-latest` and nothing else, across all eight of them. A freeze matrix means macOS and Windows runners, because PyInstaller cannot cross-compile: each platform's binary must be frozen on that platform. This roughly triples build minutes and introduces the first platform-specific CI failures this repository will have seen.
- **Code signing, with long external lead times.** macOS needs a Developer ID certificate plus notarization on every build; Windows needs an Authenticode certificate, and an OV certificate accrues SmartScreen reputation slowly while an EV certificate needs hardware token logistics. Both are procurement problems with calendar time attached, not engineering tasks. They should be started before they are on the critical path. Signing identities are secrets and fall under `AGENTS.md` §13; they belong in CI secret storage and never in the tree.
- **Auto-update becomes mandatory.** A web app is patched by deploying. A desktop app that cannot update itself strands every user on the version they installed, including on a security fix. Auto-update has to exist before the first real user, not after.
- **A new security boundary on the loopback port.** This is the sharpest consequence. `apps/api/README.md` states that "Authentication and multi-user tenancy are **not** implemented", which is defensible for a dev-only service and indefensible once the process is running on every student's machine, since any local process could otherwise reach the API. The per-session token is therefore load-bearing and is the first authentication this app will have. Two specifics: bind to `127.0.0.1` on an ephemeral port and pass the actual port to the renderer rather than fixing 8000; and revisit `NEXUS_API_CORS_ORIGINS`, whose default is `http://localhost:5173,http://127.0.0.1:5173` and which will not match an Electron renderer's origin.
- **Native modules must be rebuilt against Electron's ABI.** `node-pty` and `serialport` are native addons and must be rebuilt for Electron's Node ABI on each target platform, which means `electron-rebuild` in the build and a hard version coupling between Electron upgrades and those modules. On the Python side the freeze pulls in native wheels too: `cryptography` (imported by `agents/mind-graph/src/mindgraph/crypto.py`) and `networkx`, plus whatever `pydantic-core` and the `uvicorn[standard]` extras drag along. PyInstaller hidden-import failures in this area surface at runtime on the user's machine, not at build time, so the freeze needs a smoke test that actually launches the frozen binary.

## What the repository check surfaced

Four things that this decision as described does not yet account for. None of them changes the decision; all of them are work items that would otherwise be discovered late.

1. **There are two frontends, not one.** `apps/web` (React 18, Vite 6, `@nexus/contracts`, the `tokens.css` design system) and `apps/mind-graph-web` (React 19, Vite 8, Sigma 3, Zustand, its own `package-lock.json` alongside the workspace's pnpm). "`apps/web` becomes the renderer" is therefore only half a plan: the WebGL Mind Graph canvas cited above as the reason to reject the VS Code webview lives in the *other* app. Whether these merge into one renderer, or the shell loads two windows, is unresolved and should be settled before shell work starts.
2. **The light/heavy router does not exist yet.** `packages/model-gateway` has `ModelGateway`, `AnthropicGateway`, `OpenAICompatibleGateway`, and `FakeModelGateway`, and its `ModelPolicy` carries `provider` and `model` per call. There is no tiering or routing logic in the package despite its README claiming "Model-provider abstraction and routing". A tier table does exist, but inside Mind Graph (`TIER_MODELS` in `adapters.py`, and the T0-T3 table in `docs/architecture/mind-graph/INTEGRATION.md`). The proxy's router is new work, and it will have to reconcile two model paths that currently do not know about each other.
3. **The Postgres SQLAlchemy models are not portable to SQLite.** The factory seam holds at the interface, but `packages/persistence/src/nexus_persistence/postgres/models.py` imports `JSONB` from `sqlalchemy.dialects.postgresql`, which SQLite does not have. A SQLite backend needs its own models using generic `JSON`, or a dialect-conditional type. The good news is that `packages/persistence/tests/test_store_contract.py` is a behavioral contract suite that a new backend can be held to, so the target is defined.
4. **`agents/mind-graph/pyproject.toml` declares `scipy>=1.11`, and no source file imports it.** Harmless today, expensive in a frozen bundle. Worth removing before the first freeze rather than shipping tens of megabytes of unused numerical libraries to every student.

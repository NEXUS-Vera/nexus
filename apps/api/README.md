# API Application

## Purpose

Public HTTP API for Nexus. Exposes embedded project initialization and
multi-turn modification with optional PostgreSQL persistence.

## Ownership boundary

API application only. Domain workflow logic lives in
`agents/embedded-systems`. Persistence adapters live in `packages/persistence`.

## Endpoints

Every route requires the session token (see below). Path parameters are
written in camelCase here (`{projectId}`); query parameters follow `?`. Request
bodies are JSON. `apps/api/tests/test_api_readme_routes.py` fails when a route
or one of its declared query parameters is added, removed or renamed without
updating this list. For the order an
agent calls them in to take a project from prompt to verified evidence, see
[Driving the golden flow over HTTP](../../docs/operations/agent-http-golden-flow.md).

### Service

- `GET /healthz` - liveness check
- `GET /v1/runtime/health` - internal/dev scheduler and execution runtime availability (not a product dashboard)
- `POST /v1/admin/retention/gc?dry_run=` - dev/admin reference-aware garbage collection; dry-run by default and never deletes protected references

### Projects, artifacts and history

- `POST /v1/projects/initialize` - create a project from a prompt (`ProjectInitializationResult`)
- `GET /v1/projects/{projectId}` - current project state
- `POST /v1/projects/{projectId}/ensure-layered-architecture` - idempotently materialize Electrical/Physical artifacts for projects created before Phase 13
- `GET /v1/artifact-types` - registered artifact types
- `GET /v1/projects/{projectId}/artifacts` - current artifacts
- `GET /v1/projects/{projectId}/artifacts/{artifactType}?version=` - one artifact, optionally at a past version
- `GET /v1/projects/{projectId}/history?limit=` - project history
- `POST /v1/projects/{projectId}/turns` - multi-turn modification (`ProjectTurnResult`, includes impact analysis)
- `GET /v1/projects/{projectId}/board` - board summary, including Component Plan maturity/coverage counts
- `POST /v1/projects/{projectId}/execution-plan/propose` - refresh and propose an actionable plan against explicit project/plan versions
- `POST /v1/projects/{projectId}/execution-plan/materialize` - retry interrupted materialization of the current user-approved plan
- `POST /v1/projects/{projectId}/artifact-commands` - typed artifact commands such as `workspace.acquire-edit-lease` (`ArtifactCommandResult`)
- `GET /v1/projects/{projectId}/events?limit=&cursor=` - project event feed
- `GET /v1/projects/{projectId}/graph?root=&direction=&maxDepth=` - artifact dependency graph

### Electrical architecture circuit simulation

- `GET /v1/projects/{projectId}/artifacts/electrical-architecture/circuit-simulation/support` - simulator provider availability and support assessment
- `GET /v1/projects/{projectId}/artifacts/electrical-architecture/circuit-simulation/preview` - translated simulation preview
- `POST /v1/projects/{projectId}/artifacts/electrical-architecture/circuit-simulation/validate` - validate the translation
- `GET /v1/projects/{projectId}/artifacts/electrical-architecture/circuit-simulation/export` - export the Wokwi workspace files and manifest

### Artifact workspaces

- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace` - the artifact's workspace
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace` - create the workspace if it is missing
- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/runtime` - artifact-to-filesystem-workspace binding, current draft and capabilities
- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/files` - list draft files
- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/file?path=` - read a draft file
- `PUT /v1/projects/{projectId}/artifacts/{artifactType}/workspace/file` - write a draft file
- `DELETE /v1/projects/{projectId}/artifacts/{artifactType}/workspace/file?path=&expectedDraftVersion=&baseArtifactVersion=&baseProjectStateVersion=&actorId=` - delete a draft file
- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/snapshots` - list immutable snapshots
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/snapshots` - take an immutable snapshot of the draft
- `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/snapshots/{snapshotId}/file?path=` - read a file from an immutable snapshot
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/snapshots/{snapshotId}/restore` - restore the draft from a snapshot
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/executions` - start a validated sandbox execution (not an unrestricted remote shell)

Workspace-id addressed file routes (the workspace id comes from the runtime binding):

- `GET /v1/projects/{projectId}/workspaces/{workspaceId}/files` - list draft files
- `GET /v1/projects/{projectId}/workspaces/{workspaceId}/file?path=` - read a draft file
- `PUT /v1/projects/{projectId}/workspaces/{workspaceId}/file` - write a draft file (body carries `requestedBy` and the expected versions)
- `POST /v1/projects/{projectId}/workspaces/{workspaceId}/files/rename` - rename a draft file
- `DELETE /v1/projects/{projectId}/workspaces/{workspaceId}/file?path=` - delete a draft file (versions and `requestedBy` in the JSON body)

### Scaffold, patch, compile and test

- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/scaffold` - generate the deterministic Firmware or Analysis scaffold
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/patch/propose` - propose a Firmware or Analysis patch against an immutable base snapshot
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/patch/apply` - apply a proposed patch
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/patch/discard` - discard a proposed patch without changing the workspace
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/compile` - compile firmware against an immutable pre-compile snapshot
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/test` - run firmware tests against an immutable pre-test snapshot

### Analysis workflow

- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/inputs/upload` - upload an input file into the analysis `data/` directory
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/inputs/import-produced-output` - copy an existing produced output into `data/`
- `PUT /v1/projects/{projectId}/artifacts/{artifactType}/workspace/investigation` - write validated investigation metadata to `nexus/investigation.json`
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/run` - run `analysis.py` against an immutable pre-run snapshot
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/rerun` - re-run analysis against a specific immutable snapshot
- `POST /v1/projects/{projectId}/artifacts/{artifactType}/workspace/compare-outputs` - compare produced-output content hashes between a baseline and a rerun
- `GET /v1/projects/{projectId}/artifacts/analysis/workspace/outputs/{outputId}/preview` - bounded preview of a produced output

### Executions and outputs

- `GET /v1/projects/{projectId}/executions?limit=&cursor=` - list execution runs
- `GET /v1/projects/{projectId}/executions/{executionRunId}` - one execution run, including its input snapshot and base versions
- `GET /v1/projects/{projectId}/executions/{executionRunId}/logs?after=&limit=` - execution logs
- `POST /v1/projects/{projectId}/executions/{executionRunId}/cancel` - cancel a run
- `GET /v1/projects/{projectId}/outputs` - list produced outputs
- `GET /v1/projects/{projectId}/outputs/{outputId}` - one produced output

### Verification

- `POST /v1/projects/{projectId}/verify/promote-execution` - promote an execution run's produced outputs into a Test Plan revision
- `POST /v1/projects/{projectId}/verify/promote-analysis-summary` - promote a deterministic analysis summary into a Test Plan revision
- `POST /v1/projects/{projectId}/verify/promote-structural` - promote Electrical/Wokwi pin maps into structural Test Plan evidence
- `GET /v1/projects/{projectId}/verify/evidence-chain` - Requirement to TestCase to EvidenceReference chains, case applicability with reasons, and requirement verification states
- `GET /v1/projects/{projectId}/verify/invalidations` - append-only verification invalidation events from the project ledger (`items`)

Successful initialize responses return `ProjectInitializationResult`.
Successful turn responses return `ProjectTurnResult` (includes current state and
impact analysis). Artifact commands return `ArtifactCommandResult` (or a
structured conflict/governance error envelope).

Phase 12 initialize packages include five artifact types, including
`component-plan`. Board summaries expose Component Plan maturity/coverage
counts. Fixture-mode turns support component-plan operations (approve/reject
candidates, constraints, alternatives) in addition to requirement edits.

Persistence not-found errors return HTTP 404; version/state conflicts and
snapshot/ledger immutability errors return HTTP 409. Responses use the standard
`error.code`, `error.message`, and `error.requestId` envelope and preserve the
persistence error code. Unclassified persistence and retrieval failures remain
HTTP 500 and are logged.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXUS_STORAGE_BACKEND` | `memory` | `memory`, `sqlite`, or `postgres`. The packaged desktop shell always runs `sqlite` |
| `NEXUS_DATABASE_URL` | `sqlite:///nexus.db` for SQLite; local postgres URL otherwise | Used by both `sqlite` and `postgres`. For SQLite it is `sqlite:///<absolute-path>` - note the four slashes an absolute path produces |
| `NEXUS_FILE_STORE_ROOT` | `files/` beside a SQLite database file; otherwise memory | Explicit blob directory override |
| `NEXUS_INITIALIZATION_PROVIDER` | `fixture` | `fixture`, `llm`, or `shadow` |
| `NEXUS_API_CORS_ORIGINS` | conditional, see below | Explicit allowlist of browser origins; overrides the default either way |
| `NEXUS_API_SESSION_TOKEN` | `nexus-dev-session-token` | Per-session bearer token; the desktop shell mints a fresh one per launch |

The desktop shell points `NEXUS_DATABASE_URL` at `nexus.sqlite3` under Electron's
per-user application data directory, so a student's projects survive a quit.
Alembic is the sole schema authority for that file as it is for Postgres: the
store runs migrations to head when it opens the database.

## Session-token authentication

The API is designed to run as a loopback sidecar of the desktop shell. Loopback
is not a security boundary: any local process, and any web page the user
visits, can reach it. Every request must therefore carry the session token:

```text
Authorization: Bearer <NEXUS_API_SESSION_TOKEN>
```

No route is exempt, including `GET /healthz`. Requests without a valid token
receive `401` with error code `SESSION_TOKEN_REQUIRED`.

The spawning process supplies `NEXUS_API_SESSION_TOKEN` in the environment so
the token is never written to disk. When the variable is unset the API falls
back to the well-known development token `nexus-dev-session-token`, which keeps
`make dev-api` and `make dev-web` working. Never run a packaged build without
setting a real token.

CORS is not the security boundary here; the session token is. A cross-origin
page cannot obtain a token it does not know, and an origin allowlist stops no
local process that is not a browser. A packaged renderer loads over `file://`
and sends `Origin: null`, which no useful allowlist contains - so when the token
is a real per-launch secret the default is unrestricted, which is what makes the
shipped shell work at all.

That argument holds only while the token is secret. With `NEXUS_API_SESSION_TOKEN`
unset the token is `nexus-dev-session-token`, a constant published in this
repository and baked into the built web bundle, so any page the user visits
could present it. The default therefore depends on the token:

| `NEXUS_API_SESSION_TOKEN` | Default allowed origins |
| --- | --- |
| set to a real secret | any origin |
| unset (development token) | `http://localhost:5173` and `http://127.0.0.1:5173` |

Those two are the Vite dev server, which is the browser `make dev-api` and
`make dev-web` are for. **Serving the web app from any other port** - a
`vite --port 3000`, a preview server, a Storybook - **needs
`NEXUS_API_CORS_ORIGINS` set to that origin**, or the browser blocks the
response with no `Access-Control-Allow-Origin`. Setting the variable is an
explicit override and replaces the default in both cases.

No request reaches the router without a valid token, preflights included -
because a browser's preflight never reaches the token check in the first place.
`CORSMiddleware` is registered outside it and answers any `OPTIONS` carrying
both an `Origin` and an `Access-Control-Request-Method` itself, which is exactly
what a browser sends and nothing else does. Every other response, a `401`
included, passes back out through that same layer, so a browser can read why it
was rejected instead of seeing an opaque network error.

Multi-user tenancy is **not** implemented.

## Sidecar mode and the stdout handshake

The API is spawned as a loopback child process by the desktop shell:

```bash
NEXUS_API_PORT=0 NEXUS_API_SESSION_TOKEN=<token> python -m nexus_api
```

`NEXUS_API_PORT=0` asks the operating system for a free port, which avoids
colliding with the user's own tooling and with other users on a shared machine.
The sidecar binds and listens first, then writes **exactly one line** to stdout:

```json
{"event":"nexus.api.listening","schemaVersion":"1.0.0","host":"127.0.0.1","port":54321,"pid":4242}
```

This line is a contract consumed by the shell's sidecar supervisor. stdout
carries nothing else; all logging goes to stderr. The socket is already
listening when the line is written, so a connection made immediately on reading
it is accepted rather than refused.

The sidecar also watches the process that spawned it and shuts itself down when
that process disappears. Without this, force-quitting the shell leaves an
orphaned Python process holding the database file and the next launch fails
with no visible cause.

## Local development

```bash
make dev-db          # optional postgres
make db-migrate
make dev-api
```

## Workspace runtime

Artifact-scoped `/workspace/runtime`, `/workspace/files`, `/workspace/file`,
`/workspace/snapshots` and `/workspace/executions` routes expose generic runtime
operations. Workspace file writes and snapshots require an edit lease acquired
through `workspace.acquire-edit-lease`. Execution routes expose status, bounded
logs and cancellation; project `/outputs` routes expose declared outputs.
All routes retain session-token authentication.

`GET /v1/runtime/health` reports runtime availability and guarantees.
`POST /v1/admin/retention/gc` accepts a dry-run retention request. Runtime, queue,
workspace and execution bounds are configured through `NEXUS_EXEC_*`,
`NEXUS_WORKSPACE_*`, `NEXUS_EXECUTION_RUNTIME`,
`NEXUS_EXECUTION_CONTAINER_IMAGE` and `NEXUS_FILE_STORE_ROOT`.

## Firmware operations

The Firmware workspace adds `/workspace/scaffold`, `/workspace/patch/propose`,
`/workspace/patch/apply`, `/workspace/patch/discard`, `/workspace/compile`,
`/workspace/test` and immutable snapshot file previews. All require the session
token. Patch apply checks the lease, draft and base revisions; compile/test run
against immutable snapshots. Firmware restore first creates a safety snapshot.

Compile responses report `toolchainProfile.executionMode`: `fixture` denotes
the offline stub and `platformio` denotes a real toolchain invocation. A build
result does not establish device execution or requirement verification.

## Electrical architecture and simulation

`POST /v1/projects/{projectId}/ensure-layered-architecture` adds missing
Electrical and Physical Architecture artifacts to existing projects. Electrical
Architecture exposes `/circuit-simulation/support`, `/preview`, `/validate`, and
`/export` under its artifact route. Execution uses the `circuit-simulation`
capability; support and preview remain available without a live provider.

Configure `NEXUS_WOKWI_CLI`, `WOKWI_CLI_TOKEN`, and
`NEXUS_WOKWI_FIRMWARE_ELF` for live execution. Missing provider credentials or
firmware are reported as availability gaps. Surrogate simulation output does
not establish real component compatibility or requirement verification.

## Actionable execution plans (W2 / P1)

`POST /v1/projects/{projectId}/execution-plan/propose` takes `requestedBy`,
`baseProjectStateVersion`, `basePlanVersion` (0 before first acceptance),
`configuration`, and optionally a revised `plan`. Omitting `plan` composes a
fresh W1 checklist from current artifacts and questions. Configuration follows
`artifacts/content/actionable-execution-plan.v1.schema.json`: select two current
candidate/role IDs, an existing I2C connection, distinct supported SDA/SCL GPIOs,
`buildProfileId: platformio-arduino-esp32-v1` and
`analysisProfileId: python-analysis-v1`. Only explicit ESP32-DEVKIT-V1/MPU6050
candidates are supported; fixture part numbers are rejected. Candidate and
interface edits use existing typed artifact revisions, including in LLM mode;
free-form live conversation modification remains unsupported.

The response includes reviewed `content`, `workspace` and `commandResult` with
`proposalId`. Review the immutable snapshot through existing workspace routes;
use `artifact.reject-revision` or `artifact.accept-revision` on `/artifact-commands`
with that workspace and current base versions. Rejection changes proposal audit
history only. Acceptance always requires a user, checks the proposal's original
project/artifact basis, and writes an immutable `execution-plan` artifact before
preparing firmware/analysis files. The project-level W1 `executionPlan` remains
the original initialization proposal; the accepted artifact is the authoritative
review decision. No new state store or migration is introduced.

Scaffolds contain identical `nexus/approved-plan.json` context, a PlatformIO
ESP32 Arduino build configuration, and explicit pin constants used by the Wire
initialization skeleton. Requirement criteria/methods are copied unchanged.
This is deterministic workspace preparation; sensor firmware authoring is W3.
Existing different files block application. Interrupted writes leave durable
approval and visible command failure; retry `/execution-plan/materialize` with
`planArtifactId`, `baseProjectStateVersion` and `requestedBy`. Matching files are
preserved; a changed accepted project basis requires renewed review. Normal
compile/analysis workspace APIs remain the execution entry points. Scaffold
creation runs no model, compiler, simulator or analysis and proves no hardware
compatibility. See the W2 live-evidence gate in the initialization boundary doc.

### Firmware authoring gates (W3 / P2)

Firmware patch proposals use the existing model generator and guarded review/apply
routes. Missing configuration or provider invocation failure returns
`MODEL_PROVIDER_UNAVAILABLE`; there is no automatic canned patch. Offline regression
callers must explicitly send `allowFixture: true` to permit the deterministic
fallback. Its proposal metadata says `mode: fixture`; scripted fake gateway replies
say `mode: regression` and cannot demonstrate live authoring.

The current user-approved `execution-plan` artifact is authoritative generation
context, including its configuration, verification objectives and the domain
artifact versions listed in its reviewed source references. Missing referenced
sources fail visibly. Only projects without that artifact fall back to project
brief, requirements, components, functional/electrical/physical architecture and
test plan. Unapproved plans and oversized
context fail visibly rather than silently discarding approved decisions. The model
receives artifact content and version/identity references, at most 128 KiB of
artifact JSON, 256 manifest entries, 32 eligible source files of at most 32 KiB
each, and an 8 KiB request. The workspace copy of the approved plan is not used as
an alternative authority. This avoids preferring a user-edited or stale file over
the accepted artifact.

Compile requests may send `requireReal: true`; this rejects explicit stub mode.
With `NEXUS_FIRMWARE_USE_STUB` unset, PlatformIO is always selected, and missing
`pio` returns `FIRMWARE_TOOLCHAIN_UNAVAILABLE` before accepting an execution.
Offline compile regressions must explicitly set `NEXUS_FIRMWARE_USE_STUB=1` and
retain the returned `executionMode: fixture` label. Neither fixture outputs nor
scripted authoring close the live P2 gate. W3 does not implement simulation or the
repair loop (W4/W5).

W4 simulation handoff requires `firmwareOutputId` in the existing `artifact.execute`
command input (`capability: circuit-simulation`, `executionMode: simulate`). The
caller names the exact successful project PlatformIO compile output
`.pio/build/nexus/firmware.elf`; there is no automatic latest-build selection or
fallback to `NEXUS_WOKWI_FIRMWARE_ELF` on this API path. The adapter reads and
checks the stored ELF bytes and passes them to the existing Wokwi runner. Standalone
Wokwi callers can still use a configured ELF. Simulation runs record the firmware
output in optional v1 `inputOutputReferences`; observations carry output/build
provenance. This additive contract preserves older v1 payloads.

Missing CLI/token, invalid or fixture firmware, failed simulation, and missing,
empty or truncated declared observations fail explicitly and produce no accepted
simulation evidence. Configuration failures retain their error codes and failed
run history rather than becoming stale results. Simulation remains surrogate
behavior, never proof of physical sensor performance. Fake-provider tests are
regression evidence only.

Import the resulting `serial.log` output using the existing analysis
`inputs/import-produced-output` route with destination `data/serial.log`.
The golden analysis script parses `TEL,time_s,accel_x_g,accel_y_g,accel_z_g` frames,
rejects missing/failed/nonfinite telemetry, and reports the exact input SHA256 in
its summary. CSV remains available for separate synthetic regressions. Analysis
now runs Python by default; `NEXUS_ANALYSIS_USE_STUB=1` is an explicit fixture
opt-in and its toolchain profile is labeled `fixture`.

W4 regression: `test_w4_firmware_simulation_import_analysis_regression` uses a
scripted compiler and Wokwi runner with real output import and Python computation.
The opt-in `test_w4_live_built_firmware_simulation_import_analysis` uses actual
PlatformIO/Wokwi (`RUN_WOKWI_INTEGRATION=1`). The N163 local live attempt stopped
before simulation: the restricted process runtime could not find `pio`
(`PROCESS_START_FAILED`), although both CLIs and a token were available to the
shell. The live gate remains unresolved; no sandbox changes or live success claim
are made. W5 repair orchestration and W6/W7 full dependency invalidation remain
separate work packages.

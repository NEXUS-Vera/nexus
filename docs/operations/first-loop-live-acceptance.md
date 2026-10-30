# First-loop live full-scope acceptance: ESP32-DEVKIT-V1 + MPU6050

## Objective and boundary

This is the **live real-model demonstration**, owned by Pranay's golden
acceptance environment. It covers real firmware generation, PlatformIO compilation,
labeled user edits injecting F2 (compiler), F4 (simulation I2C address), or F5
(analysis sample rate), model diagnosis, explicit patch approval, and
rebuild → Wokwi simulation → serial-log import → Python analysis → deterministic
verification. It is separate from the scripted offline regressions
(`apps/api/tests/test_repair_full_scope_api.py`, PR #152 with F4/F5 coverage in
PR #155) and the fixture HTTP [golden flow](agent-http-golden-flow.md). A regression PASS is not a live
acceptance result. Simulation is surrogate evidence, not physical IMU evidence.

The N261 outline has been checked against this checkout's
[API handlers](../../apps/api/src/nexus_api/main.py),
[request model](../../apps/api/src/nexus_api/models.py),
[API README](../../apps/api/README.md), and
[repair workflow](../../agents/embedded-systems/src/nexus_embedded_systems/workflows/repair.py).
There are material differences from the integration-branch specification:

- `advance_embedded_repair` does **not** read `scope`. Full scope is today's
  firmware repair path in `RepairWorkflow.advance` and `_launch`; sending
  `scope: "full"` would not select or enforce it. Verify all downstream runs.
- There is no `_downstream_lease` helper here. The operator must acquire the
  analysis and electrical workspace leases using the same actor before repair.
- Repair returns a proposal ID, not inline operations. Step 8 uses the read-only
  GET patch proposal route from PR #154, now merged into main. Inspect replacement
  bytes and generator metadata before approval; the unchanged draft is not the
  pending proposal.

## Host prerequisites and environment setup

Use the repository's installed development dependencies and loopback API.
`pio`, `wokwi-cli`, and `python3` must be executable on the API host's PATH.
The firmware toolchain invokes `pio run -e nexus`; its first build may need
PlatformIO packages/download access. Wokwi must be available to the API process
and its sandbox. Check binary presence without printing environment contents:

```bash
command -v pio
command -v wokwi-cli
command -v python3
```

Provision credentials privately before starting the API. Credential names only:
`WOKWI_CLI_TOKEN`, `NEXUS_MODEL_API_KEY`, `NEXUS_API_SESSION_TOKEN`.
Never print their values, paste them into evidence, enable HTTP tracing containing
Authorization, or copy credential files into the workspace.

Configuration names: `NEXUS_MODEL_PROVIDER`, `NEXUS_MODEL_NAME`, optional
`NEXUS_MODEL_BASE_URL`; storage uses `NEXUS_STORAGE_BACKEND`,
`NEXUS_DATABASE_URL`, and optionally `NEXUS_FILE_STORE_ROOT`. Do not record a
credential-bearing database URL. Choose a provider/model supported by the
configured gateway. Set `NEXUS_INITIALIZATION_PROVIDER=llm`,
`NEXUS_FIRMWARE_USE_STUB=0`, and `NEXUS_ANALYSIS_USE_STUB=0`:

```bash
NEXUS_INITIALIZATION_PROVIDER=llm NEXUS_FIRMWARE_USE_STUB=0 NEXUS_ANALYSIS_USE_STUB=0 make dev-api
```

`make dev-api` otherwise defaults to fixture initialization. Settings and model
clients are constructed at startup: restart after configuration changes. See
[config.py](../../apps/api/src/nexus_api/config.py), `load_settings`, and
`main.py:_build_firmware_patch_generator`. Do not use the golden flow's stub
startup command for this demonstration.

### Capability dependencies and settled live-demo decisions

- **PR #154 is merged into main:** the API host must include its read-only
  `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/patch/{proposalId}`
  route for Step 8. This branch's older API source does not yet contain that route;
  use a host with the merged capability. No code update is part of this runbook edit.
- **PR #155:** scripted offline F4/F5 regressions in
  `apps/api/tests/test_repair_full_scope_api.py` exercise simulation and analysis
  repair using stubs. Their PASS is separate from this real-model demonstration.
- **N275 implementation remains in progress:** synchronous simulation diagnostics
  need a `serial.log` fallback when `executionJob` is absent, and failed-case
  `actualResult` excerpts need a 400-character bound to fit the serialized
  4,096-character generation request. Confirm this fix is deployed before claiming
  F4 live acceptance; retain full original evidence outside the bounded request.

Pranay's decisions are settled: run **F2, F4, and F5 each in a fresh project**,
repeating Steps 1–4 independently. For F2 continue with Steps 5–9; for F4 or F5
skip the F2 injection and use Step 10 or 11. F5 repairs firmware
`src/main.cpp` (`SAMPLE_INTERVAL_MS`), preserving the seeded `analysis.py` and its
criteria. The default Wokwi hang triage threshold remains **30 seconds**; do not
increase it to obtain PASS. This is the operator hang threshold, distinct from
simulated duration (`maxDurationMs`) and the provider's calculated host-process
watchdog. Preserve run state/logs on a hang; only report `SIMULATION_TIMEOUT` when
that code is actually returned. R2/R3 sign-off remains the separate open question below.

## Request conventions

Base URL: `http://127.0.0.1:8000`. Every request uses Authorization with the
bearer credential supplied by `NEXUS_API_SESSION_TOKEN`; every JSON request uses
`Content-Type: application/json`. Keep response IDs and evidence outside Git.

**Every live call must send `requireReal:true`.** For JSON bodies below, merge
`"requireReal": true` into each body. For GET requests, send the query parameter
`requireReal=true` (append with `&` when a query already exists), with no body.
This is an operator convention: GET handlers do not consume that query flag;
initialization, scaffold, plan, file, patch and verification handlers do not
use it to enforce real execution either. Compile reads it; repair start persists
it and propagates it to rebuild and analysis. Repair advance uses the stored
value, even though the request also sends it. Real model initialization requires
`NEXUS_INITIALIZATION_PROVIDER=llm`; firmware proposal additionally requires
`allowFixture:false` and model metadata inspection. Never infer real evidence
merely because an ignored flag was sent.

The artifact-command schema has `additionalProperties:false` and no
`requireReal` field. Today's HTTP dispatcher/command shape checks accept the
extra field, but it is not a shared-contract field or an execution guard.
This runbook targets the verified HTTP implementation; a client enforcing that
schema cannot satisfy the literal all-call flag convention for artifact commands.
Record that limitation instead of changing the contract or dropping the flag.

Notation below is JSON-template notation: `actor` means this object, integers
such as `draftVersion` must be replaced by current response values, and string
placeholders must be replaced before sending:

```json
{"schemaVersion":"1.0.0","actorId":"actor_acceptance_operator","actorType":"user","displayName":"Acceptance Operator"}
```

For all workspace writes, obtain current `binding` and `draft` from
`GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/runtime`.
Use `binding.baseArtifactVersion`, `binding.baseProjectStateVersion` and
`draft.draftVersion` as `expectedDraftVersion`. Refresh after acceptance,
scaffold, patch application, or any edit; do not copy N261's fixed versions.
On stale versions, refresh and re-review rather than retrying blindly.

The command envelope for `POST /v1/projects/{projectId}/artifact-commands` is:

```json
{
  "schemaVersion":"1.0.0",
  "commandId":"cmd_REPLACEwithFreshAlphanumericId",
  "commandType":"workspace.acquire-edit-lease",
  "projectId":"{projectId}",
  "artifactId":"{artifactId}",
  "workspaceId":"{workspaceId}",
  "baseArtifactVersion":1,
  "baseProjectStateVersion":1,
  "requestedBy":actor,
  "requestedAt":"{current UTC ISO-8601 timestamp}",
  "input":{},
  "requireReal":true
}
```

Replace both example integers with current binding versions. Use a fresh
`cmd_` ID with at least 16 alphanumeric suffix characters for each command.
Require `status: "completed"`, not just HTTP 200. Acquire/renew leases for
`firmware`, `analysis`, and `electrical-architecture` with this envelope and
one actor. Release them at the end with `workspace.release-edit-lease` and
`input:{}`. Another actor's lease is a stop-and-triage condition.

## Execution steps and exact HTTP calls

### 1. Initialize from golden intent

`POST /v1/projects/initialize`:

```json
{"message":"Build an ESP32-based vibration monitor using an MPU6050. It should stream acceleration telemetry and analyze stationary sensor noise to verify that accel_x RMS noise stays below 0.10 g.","autonomyMode":"collaborate","requireReal":true}
```

Save `project.projectId` and `project.currentStateVersion`.
`POST /v1/projects/{projectId}/ensure-layered-architecture` with
`{"requestedBy":actor,"requireReal":true}` should return
`createdArtifactTypes:[]` for an already materialized project.
`GET /v1/projects/{projectId}/artifacts` must show `requirement-set`,
`component-plan`, and `electrical-architecture`.

Live initialization is variable. Inspect the requirement-set and component-plan
via `GET /v1/projects/{projectId}/artifacts/{artifactType}` before continuing:
require the supported ESP32/MPU6050 pair and intended criteria. Exact requirement
text drives deterministic IMU criterion seeding in
[execution_plan.py:IMU_VERIFICATION](../../agents/embedded-systems/src/nexus_embedded_systems/workflows/project_modification/execution_plan.py).
Do not assume a live model reproduced all eight canonical requirements. Missing
or mismatched criteria are a demonstration gap, not permission to claim PASS.

### 2. Propose and approve the actionable execution plan

`POST /v1/projects/{projectId}/execution-plan/propose`:

```json
{"requestedBy":actor,"baseProjectStateVersion":currentProjectVersion,"basePlanVersion":0,"configuration":null,"requireReal":true}
```

Use `0` only before the first plan acceptance. Null configuration derives the
supported pair and resolved I2C connection; ambiguous bindings require review.
Review returned `content`, then use `commandResult.proposalId` and the returned
`workspace` IDs/base versions in the command envelope, changing
`commandType` to `artifact.accept-revision` and
`input` to `{"proposalId":"{proposalId}"}`. This is explicit user approval.

Expect successful materialization of firmware/analysis workspaces, matching
`nexus/approved-plan.json`, `diagram.json`, `mapping-manifest.json`, and seeded
`analysis.py`. Read the test-plan artifact: require the intended R1–R8 cases,
criteria and verification methods, initially planned. Use current versions,
not an assumed project state of 2. Stop on partial materialization errors.

### 3. Generate firmware with the real model

Resolve the firmware runtime, acquire its lease, then
`POST /v1/projects/{projectId}/artifacts/firmware/workspace/scaffold` with
`requestedBy`, `expectedDraftVersion`, `baseArtifactVersion`,
`baseProjectStateVersion`, and `requireReal:true`. Expect `platformio.ini`,
`src/main.cpp`, and `nexus/approved-plan.json`; matching pre-materialized files
may already exist.

`POST /v1/projects/{projectId}/artifacts/firmware/workspace/patch/propose`:

```json
{"requestedBy":actor,"requestedChange":"Implement the approved ESP32 MPU6050 monitor with Wire.begin on the approved pins, actual sensor initialization and reads, 115200 baud serial, NEXUS_MPU_READY after successful initialization, NEXUS_MPU_INIT_FAIL without samples on failure, header time_s,accel_x_g,accel_y_g,accel_z_g, and TEL,<time_s>,<ax>,<ay>,<az> samples in seconds and g at 50 Hz using a non-blocking millis schedule. Preserve approved-plan context and build configuration.","allowFixture":false,"requireReal":true}
```

Review returned `proposal.operations`, `baseSnapshotId`, and
`proposal.generatorMetadata.mode:"llm"`. The S7 contract is in
[live_patch_generator.py:IMU_SERIAL_CONTRACT](../../packages/board/src/nexus_board/firmware/live_patch_generator.py):
3 decimal seconds, 5 decimal acceleration in g, 20 ms non-blocking schedule,
readiness marker and header before samples. A fixture proposal fails acceptance.

Apply the reviewed proposal using
`POST /v1/projects/{projectId}/artifacts/firmware/workspace/patch/apply` with
`{"proposalId":"{proposalId}","requestedBy":actor,"expectedDraftVersion":draftVersion,"baseArtifactVersion":artifactVersion,"baseProjectStateVersion":projectVersion,"requireReal":true}`.
Require `status:"applied"`; refresh runtime versions.

### 4. Baseline real compilation

`POST /v1/projects/{projectId}/artifacts/firmware/workspace/compile` with
`{"requestedBy":actor,"requireReal":true}`. Save
`executionRun.executionRunId`; require `toolchainProfile.executionMode:"platformio"`.
Poll `GET /v1/projects/{projectId}/executions/{executionRunId}` until terminal;
require `executionRun.status:"completed"`. Inspect diagnostics via
`GET /v1/projects/{projectId}/executions/{executionRunId}/logs`.

`GET /v1/projects/{projectId}/outputs` lists produced outputs. Match by run ID;
require `.pio/build/nexus/firmware.elf` and `.pio/build/nexus/firmware.bin`.
`GET /v1/projects/{projectId}/outputs/{outputId}` retrieves output metadata/content
references. Verify real ELF bytes (ELF magic `\x7fELF`, no fixture marker) where
available through the returned content representation; a filename alone is not
proof. Wokwi also validates the selected ELF before execution.

### 5. Inject F2 as a labeled user edit

Record in the acceptance evidence: **F2 — operator/user edit: Wire.begin →
Wire.begn; intentional compiler fault, not an agent generation failure.**
Read `GET /v1/projects/{projectId}/workspaces/{firmwareWorkspaceId}/file?path=src/main.cpp`.
Preserve the original response; replace exactly one real `Wire.begin(` call
with `Wire.begn(`. If no such call exists, stop and review the generated source.

`PUT /v1/projects/{projectId}/workspaces/{firmwareWorkspaceId}/file`:

```json
{"path":"src/main.cpp","content":"{entire mutated UTF-8 source}","requestedBy":actor,"expectedDraftVersion":draftVersion,"baseArtifactVersion":artifactVersion,"baseProjectStateVersion":projectVersion,"origin":"USER","writePolicy":"USER_EDITABLE","requireReal":true}
```

The HTTP golden flow's `contentBase64` is also supported; use one content
representation. Require a bumped `draft.draftVersion` and read back the edit.
Do not invent a fault-label request field; the label belongs in operator evidence.

### 6. Observe the intentional compiler failure

Repeat the compile POST from step 4, including `requireReal:true`. Save its new
run ID as `failedCompileRunId`, poll its execution and read its logs. Require
`status:"failed"` and a diagnostic about `TwoWire` lacking `begn` (wording can
vary by compiler). An unavailable compiler or timeout is not the expected F2
failure. Preserve its immutable `inputSnapshotId` and the logs.

### 7. Request bounded model diagnosis

Resolve and acquire/renew analysis and electrical-architecture leases with the
same actor as firmware. This checkout uses the operator actor for downstream
snapshot creation and serial import; it does not acquire those leases itself.

`POST /v1/projects/{projectId}/repair`:

```json
{"action":"start","executionRunId":"{failedCompileRunId}","target":"firmware","maxAttempts":3,"requestedBy":actor,"requireReal":true}
```

Save `repairId` and the returned `revision`; expect `status:"inspect"`.
The initial failure counts toward the three-attempt limit. Advance with:

```json
{"action":"advance","repairId":"{repairId}","revision":latestRevision,"requestedBy":actor,"requireReal":true}
```

Expect `status:"review"` and `proposalId`. Diagnostics remain under
`attempts[].diagnostics`. Check `evidenceMode` stays `real-requested`; regression
mode is not live acceptance. Do not hard-code revision 0/2/3: `_save` increments
for intermediate diagnosing/launching transitions as well as the final response.
To recover current state, POST the same route with
`{"action":"get","repairId":"{repairId}","requestedBy":actor,"requireReal":true}`.

### 8. Review and explicitly approve the repair patch

After repair advance returns `status:"review"`, inspect its `proposalId` using:

`GET /v1/projects/{projectId}/artifacts/firmware/workspace/patch/{proposalId}?requireReal=true`

For example (Authorization is redacted; supply the session bearer privately):

```bash
curl --fail-with-body -sS \
  -H 'Authorization: Bearer REDACTED' \
  'http://127.0.0.1:8000/v1/projects/{projectId}/artifacts/firmware/workspace/patch/{proposalId}?requireReal=true'
```

PR #154's response contains `binding`, `status`, `baseSnapshotId`, and `proposal`.
The stored `proposal` contains identity fields (`proposalId`, `projectId`,
`workspaceId`, `artifactType`), lifecycle `status`, `baseSnapshotId`,
`requestedChange`, `generatorMetadata`, and `operations`. Each replacement
operation supplies `operationType`, `path`, full `content`, `expectedBaseHash`,
and `contentHash`. The route is read-only and supports other lifecycle statuses;
GET success alone is not approval.

Before approving, verify:

1. Top-level and proposal `status` are `"proposed"`; IDs, firmware binding and
   base snapshot match this project, workspace and pending repair.
2. `proposal.generatorMetadata.mode` is `"llm"`; record actual provider/model.
   Fixture/fake metadata fails live acceptance.
3. `proposal.operations` contains exactly one `replace-file` for `src/main.cpp`.
   Inspect the full replacement and hashes against the base snapshot.
4. It corrects the injected fault: F2 restores `Wire.begin` on approved pins;
   F4 restores `MPU_ADDR` to `0x68`; F5 restores `SAMPLE_INTERVAL_MS` to `20`.
5. It retains S7 behavior: 115200 baud, `NEXUS_MPU_READY` only after successful
   initialization, `NEXUS_MPU_INIT_FAIL` without samples on failure,
   `time_s,accel_x_g,accel_y_g,accel_z_g` header, and `TEL,` frames at 50 Hz.

Only after explicit review, apply the reviewed ID:
`POST /v1/projects/{projectId}/artifacts/firmware/workspace/patch/apply`:

```json
{"proposalId":"{proposalId}","requestedBy":actor,"expectedDraftVersion":draftVersion,"baseArtifactVersion":artifactVersion,"baseProjectStateVersion":projectVersion,"requireReal":true}
```

Refresh current runtime versions before applying. Require `status:"applied"`;
read back `src/main.cpp` using the workspace file GET with `requireReal=true`.
On stale state, refresh and re-review. Never apply an unseen proposal.
Advance repair using the latest revision and `requireReal:true` as in Step 7;
expect `stage:"compile"`, `status:"running"`, `runId`. Continue through Step 9.

### 9. Drive full-scope completion and inspect deterministic evidence

For each returned `runId`, poll execution and inspect logs/outputs as in step 4.
After successful execution, POST repair `action:"advance"` with `repairId`,
latest `revision`, `requestedBy`, and `requireReal:true`:

| Completed stage | Next advance must do | Evidence to retain |
| --- | --- | --- |
| Rebuild (`compile`) | Select that run's ELF and launch `simulate` | Real PlatformIO profile, completed run, ELF output ID in `firmwareOutputId` |
| Wokwi (`simulate`) | Promote markers, import `serial.log`, launch `analyze` | Completed simulation; serial header, readiness marker, `TEL,` samples; no init-failure marker |
| Python (`analyze`) | Promote analysis and evaluate linked cases | Completed analysis; deterministic test-plan revision; repair `status:"completed"` |

The workflow itself selects `firmwareOutputId` in simulation options; operators
must not substitute an unrelated ELF or upload synthetic CSV to obtain PASS.
Read analysis `data/serial.log` through the workspace file GET and compare its
SHA-256 with the simulation output bytes and summary `inputSha256`. Preserve
analysis `inputSnapshotId`; inspect the actual run input with
`GET /v1/projects/{projectId}/artifacts/analysis/workspace/snapshots/{snapshotId}/file?path=data/serial.log`
and similarly `?path=analysis.py`.

List outputs for the analysis run; require `outputs/summary.json`,
`outputs/processed.csv`, and `outputs/accel_plot.png`. Preview summary using
`GET /v1/projects/{projectId}/artifacts/analysis/workspace/outputs/{outputId}/preview`.
Require `inputPath:"data/serial.log"`, matching input hash,
`authority:"deterministic-code"`, finite `accel_x_rms_noise_g < 0.10`, and
`sampling_hz` in 45–55 inclusive. Summary's R7 PASS alone does not establish R6.

Read `GET /v1/projects/{projectId}/artifacts/test-plan` and
`GET /v1/projects/{projectId}/verify/evidence-chain`. Repair already promotes
simulation and analysis; a separate promotion is not required. Check each case:

| Cases | Expected deterministic evidence | Required result |
| --- | --- | --- |
| R1, R4 | Simulation `NEXUS_MPU_READY` marker | `status:"passed"`, `assessment:"PASS"`, `assessmentAuthority:"deterministic-code"` |
| R5 | Simulation header contains `accel_x_g` | Same, linked to simulation run |
| R6 | Analysis `sampling_hz` 45–55 Hz | Same, linked to analysis run |
| R7 | Demeaned accel_x RMS noise < 0.10 g | Same, linked to analysis run |
| R8 | Summary JSON, processed CSV and plot PNG exist | Same, linked to analysis run |

Resolve cases by their requirement references and criteria; display IDs alone
cannot authorize evidence. Retain requirement → test → evidence links and
source run IDs from the current repair attempt. `RepairWorkflow.advance` checks
cases linked to attempt runs, not that all eight canonical cases exist: explicitly
check all six dynamic cases above. Agent prose and repair `completed` alone are
insufficient. Keep simulator/hardware divergence risk visible; no physical test
was performed.

On `review`, repeat explicit review for another bounded attempt. On `exhausted`,
`stopped`, `unavailable`, `rejected`, or `cancelled`, retain evidence and triage;
never call the demonstration passed. To stop an active repair, POST repair with
`action:"cancel"`, `repairId`, latest `revision`, `requestedBy`, and
`requireReal:true`; release operator leases after work stops.

### 10. Live F4: Wokwi simulation I2C address fault

Use a **fresh project** with Steps 1–4 completed, not the repaired F2 project.
All calls inherit the Authorization and `requireReal:true` conventions above,
including `requireReal=true` on every GET. Acquire/renew the three workspace
leases with the same actor and refresh versions before writes.

1. Record **F4 — operator/user edit: MPU_ADDR 0x68 → 0x69; intentional runtime
   I2C NACK fault, not an agent generation failure.** Read `src/main.cpp` through
   the workspace file GET. Locate the actual MPU6050 address constant and change
   only `MPU_ADDR` from `0x68` to `0x69`, preserving the generated declaration's
   type. If it is absent or ambiguous, stop and review. Use the Step 5 file PUT
   body with the entire mutated source, current versions, `origin:"USER"`,
   `writePolicy:"USER_EDITABLE"`, and `requireReal:true`. Require a bumped
   `draft.draftVersion` and read back the edit.
2. Repeat Step 4 compile with `requireReal:true`; require a completed real
   PlatformIO run. Save that run's `.pio/build/nexus/firmware.elf` output ID.
   A compiler failure is not the intended F4 fault.
3. Snapshot the electrical workspace:
   `POST /v1/projects/{projectId}/artifacts/electrical-architecture/workspace/snapshots`
   with `{"requestedBy":actor,"reason":"before-execution","requireReal":true}`.
   Save `snapshotId`. Send the command envelope from Request conventions to
   `POST /v1/projects/{projectId}/artifact-commands`, using the current electrical
   binding, `commandType:"artifact.execute"`, a fresh command ID, and this input:

   ```json
   {"snapshotId":"{snapshotId}","capability":"circuit-simulation","firmwareOutputId":"{elfOutputId}"}
   ```

   Keep `requireReal:true` at the envelope's top level. Save the command result's
   `executionRunId` as `simRunId`; poll the execution and inspect outputs by run ID.
   Apply the default 30-second hang triage threshold. Expected F4 is a completed
   runner with `serial.log` containing `NEXUS_MPU_INIT_FAIL`, no
   `NEXUS_MPU_READY`, and no telemetry samples. A timeout or unavailable simulator
   is a different failure; retain it and triage.
4. Explicitly promote the completed simulation:
   `POST /v1/projects/{projectId}/verify/promote-execution`:

   ```json
   {"executionRunId":"{simRunId}","requestedBy":actor,"accept":true,"requireReal":true}
   ```

   Read the test-plan artifact. Require R1/R4 readiness and R5 header cases to
   report `assessment:"FAIL"`, `status:"failed"`, linked to this simulation.
   Inspect `actualResult` against the serial failure evidence; do not assume
   exact text or rely solely on display IDs.
5. Start firmware repair and then advance as in Step 7, substituting `simRunId`:

   ```json
   {"action":"start","executionRunId":"{simRunId}","target":"firmware","maxAttempts":3,"requestedBy":actor,"requireReal":true}
   ```

   Expect `status:"inspect"`, `stage:"simulate"`, then `status:"review"` and
   `proposalId`. Check `evidenceMode:"real-requested"` and
   `attempts[].diagnostics`: failed criteria, output references and `logExcerpt`
   containing `NEXUS_MPU_INIT_FAIL`. This serial fallback and bounded case evidence
   depend on N275; missing evidence or generation-bound errors block acceptance.
6. Perform all Step 8 GET inspection and explicit approval checks, requiring
   restoration of `MPU_ADDR = 0x68`. Continue through Step 9: rebuilt ELF,
   successful Wokwi markers/telemetry, imported serial bytes, real Python
   `analysis.py`, and deterministic R1/R4/R5/R6/R7/R8 PASS linked to the current
   repair runs. Require repair `status:"completed"`; retain hashes and evidence
   chain. A simulation-only repair is insufficient.

### 11. Live F5: Python analysis sample-rate criteria fault

Use another **fresh project**, repeating Steps 1–4. Keep every live request
`requireReal:true` (GET query `requireReal=true`), current versions and all three
same-actor leases. F5 targets firmware; preserve `analysis.py` and R6's 45–55 Hz
criterion throughout diagnosis and repair.

1. Record **F5 — operator/user edit: SAMPLE_INTERVAL_MS 20 → 40; intentional
   analysis criteria fault (25 Hz instead of 50 Hz), not an agent generation
   failure.** Read `src/main.cpp`, locate its sample interval constant and change
   only `SAMPLE_INTERVAL_MS` from `20` to `40`. Stop for review if the generated
   schedule differs. Write the entire mutated source with the Step 5 PUT body,
   `origin:"USER"`, `writePolicy:"USER_EDITABLE"`, current versions and
   `requireReal:true`. Require a bumped draft version and read back the edit.
2. Compile and simulate using Step 10.2–3 with this project's new ELF, snapshot,
   command and run IDs. Require completed real compilation and simulation,
   `NEXUS_MPU_READY`, the serial header, and `TEL,` timestamps approximately
   0.040 s apart. Promote this simulation using Step 10.4's body with
   `requireReal:true`; R1/R4/R5 must PASS. Save its `serial.log` output ID.
3. Import that produced output:
   `POST /v1/projects/{projectId}/artifacts/analysis/workspace/inputs/import-produced-output`:

   ```json
   {"path":"data/serial.log","outputId":"{serialLogOutputId}","requestedBy":actor,"expectedDraftVersion":analysisDraftVersion,"baseArtifactVersion":analysisArtifactVersion,"baseProjectStateVersion":projectVersion,"requireReal":true}
   ```

   Resolve current analysis versions before import. Run
   `POST /v1/projects/{projectId}/artifacts/analysis/workspace/run` with
   `{"requestedBy":actor,"requireReal":true}`. Save `analysisRunId`, poll to
   `status:"completed"`, and preview its `outputs/summary.json` as in Step 9.
   Require `sampling_hz` near 25, matching serial input hash and
   `authority:"deterministic-code"`. A Python process crash is not this fault.
4. Explicitly promote analysis with Step 10.4's promotion body, substituting
   `analysisRunId` and retaining `requireReal:true`. Read the test-plan artifact:
   R6 must report `assessment:"FAIL"`, `status:"failed"`, and an `actualResult`
   near 25 Hz outside 45–55, linked to this analysis run. A completed process
   alone does not imply criteria PASS.
5. Start repair with Step 10.5's body, substituting `analysisRunId` and keeping
   `target:"firmware"`, `maxAttempts:3`, and `requireReal:true`. Expect
   `status:"inspect"`, `stage:"analyze"`. Advance with Step 7's current revision
   and `requireReal:true`; require `status:"review"`, a proposal ID, and
   `evidenceMode:"real-requested"`. Inspect diagnostics for the failed R6
   criterion/actual result and analysis output references.
6. Use Step 8's GET review and explicit approval. Require the model's firmware
   replacement to restore `SAMPLE_INTERVAL_MS = 20`, retaining the 50 Hz serial
   contract. Do not modify `analysis.py` or relax the criterion to accept 25 Hz.
   Continue through Step 9's complete rebuild → simulate → import → analyze →
   promote sequence, using new run IDs and the new serial input hash. Require
   `sampling_hz` in 45–55, deterministic R1/R4/R5/R6/R7/R8 PASS and repair
   `status:"completed"`. Retain original FAIL and repaired PASS evidence.

## R2/R3 today and the open product question for Pranay

R2 is inspection with `structural-mapping` (`SDA` → `GPIO21`; requirement also
names SCL GPIO22). R3 is inspection with `exact-match`, expected value `115200`.
The marker and analysis promoters in
[close.py](../../packages/board/src/nexus_board/verification/close.py) do not
promote these inspection cases. They remain `planned` and have no repair-run
link, so they do not block today's repair completion.

**Open product question for Pranay, acceptance environment owner — undecided:**

- **Option A:** require 100% PASS for all R1–R8. Should R2 use the existing
  `POST /v1/projects/{projectId}/verify/promote-structural` with
  `{"signalMap":{"SDA":"GPIO21"},"requestedBy":actor,"accept":true,"requireReal":true}`,
  and should R3 receive automated code inspection or formal manual verification?
  The route accepts a caller-supplied map; that alone does not prove wiring.
- **Option B:** require full dynamic repair completion and deterministic PASS
  for R1/R4/R5/R6/R7/R8, leaving R2/R3 explicitly documented in the review plan.

Do not execute Option A merely because its route is listed, resolve R3 by prose,
or represent Option B as an agreed acceptance policy. Record dynamic results
and leave final sign-off pending Pranay's decision.

## Failure triage

Paths below are repository-relative `file:function` targets verified in this
checkout, except the explicitly labeled merged PR #154 additions. Preserve actual
error envelopes and run state; asynchronous failures can appear in run/repair state rather than as an HTTP error.

| Symptom | Check/action | File:function |
| --- | --- | --- |
| 401 `SESSION_TOKEN_REQUIRED` | Session credential provisioned to API and caller; do not print it | `apps/api/src/nexus_api/main.py:require_session_token` |
| 422 `FIRMWARE_TOOLCHAIN_UNAVAILABLE` | `pio` available and firmware stub disabled; this code also covers real-requested stub rejection | `packages/board/src/nexus_board/firmware/toolchain.py:require_firmware_toolchain` |
| `MODEL_PROVIDER_UNAVAILABLE`, missing model generation | Model key configured before startup; no fixture fallback | `apps/api/src/nexus_api/main.py:_build_firmware_patch_generator`; `packages/board/src/nexus_board/services/workspace_runtime.py:WorkspaceRuntimeService.propose_firmware_patch` |
| Unsupported/ambiguous plan or missing criteria | Review supported pair and exact requirement semantics | `agents/embedded-systems/src/nexus_embedded_systems/workflows/project_modification/execution_plan.py:derive_default_configuration` |
| Stale draft, lease held/missing | Refresh versions; acquire/renew same-actor leases for all three workspaces | `packages/board/src/nexus_board/services/workspace_runtime.py:WorkspaceRuntimeService.apply_firmware_patch`; `agents/embedded-systems/src/nexus_embedded_systems/workflows/repair.py:RepairWorkflow._import` |
| Wokwi CLI/token unavailable | Check host executable and credential provision without exposing values | `packages/circuit-simulation/src/nexus_circuit_simulation/wokwi.py:WokwiProvider.availability` |
| `FIRMWARE_ELF_INVALID` | Selected output must be the actual completed rebuild ELF | `apps/api/src/nexus_api/circuit_simulation.py:CircuitSimulationExecutionAdapter._resolve_firmware` |
| `SIMULATION_TIMEOUT` or no telemetry | Inspect simulation diagnostics, boot and S7 markers/schedule | `apps/api/src/nexus_api/circuit_simulation.py:CircuitSimulationExecutionAdapter.execute` |
| 409 `REPAIR_CONFLICT` | Fetch repair state; send returned revision | `apps/api/src/nexus_api/main.py:advance_embedded_repair`; `agents/embedded-systems/src/nexus_embedded_systems/workflows/repair.py:RepairWorkflow.advance` |
| 404 / 422 on `GET .../workspace/patch/{proposalId}` | Confirm API host includes merged PR #154; check proposal project/workspace/artifact identity. Stop before apply if inspection fails | PR #154 route (absent from this branch): `apps/api/src/nexus_api/main.py:get_artifact_workspace_patch_proposal`; `packages/board/src/nexus_board/services/workspace_runtime.py:WorkspaceRuntimeService.get_firmware_patch_proposal` |
| `CommandValidationError: Failure criteria exceed generation bound` | Check deployment of the in-progress N275 fix; inspect failed-case count, serialized `actualResult` lengths and produced `serial.log` size. Preserve full evidence; do not drop criteria or disable real execution to bypass the 4,096-character request bound | `agents/embedded-systems/src/nexus_embedded_systems/workflows/repair.py:RepairWorkflow._inspect` |
| Missing telemetry/nonfinite values, R6/R7 FAIL | Inspect original serial input, sample timestamps and g conversion; do not replace input with fixture CSV | `agents/embedded-systems/src/nexus_embedded_systems/workflows/project_modification/imu_analysis.py:main`; `packages/board/src/nexus_board/firmware/live_patch_generator.py:LiveFirmwarePatchGenerator.generate` |

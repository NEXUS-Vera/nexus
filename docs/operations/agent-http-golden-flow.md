# Driving the golden flow over HTTP

This is the order an external agent calls the public API in to take the
ESP32 IMU vibration monitor golden project from a prompt to verified evidence,
with no UI and no in-process kernel access. It mirrors
[`apps/api/tests/test_golden_lifecycle_http_api.py`](../../apps/api/tests/test_golden_lifecycle_http_api.py),
which runs this exact sequence in CI, so treat that test as the authoritative,
executable version of this page. The full route list is in
[`apps/api/README.md`](../../apps/api/README.md#endpoints).

## Start the API

```bash
NEXUS_FIRMWARE_USE_STUB=1 NEXUS_ANALYSIS_USE_STUB=0 make dev-api   # http://127.0.0.1:8000
```

`make dev-api` uses in-memory storage and fixture initialization (no model key).

- `NEXUS_ANALYSIS_USE_STUB` defaults to `1`, which replaces `analysis.py` with a
  stub. Set it to `0` so the analysis really runs.
- `NEXUS_FIRMWARE_USE_STUB` defaults to the stub only when `pio` is not on
  `PATH`. Set it to `1` for the deterministic compile stub; stub output is never
  live compile evidence.

Every request carries `Authorization: Bearer <token>`; without
`NEXUS_API_SESSION_TOKEN` the token is `nexus-dev-session-token`. Mutating
calls carry a `requestedBy` actor:

```json
{"schemaVersion": "1.0.0", "actorId": "actor_0123456789abcdef", "actorType": "user", "displayName": "User"}
```

The golden inputs live in `packages/board/tests/golden/esp32_imu_vibration_monitor/`
(`main.cpp`, `platformio.ini`, `analysis.py`, `stationary_imu.csv`). File
contents travel base64-encoded in `contentBase64`.

## 1. Initialize the project

1. `POST /v1/projects/initialize` with `{"message": "<golden prompt>", "autonomyMode": "collaborate"}`.
   The project id is `project.projectId` in the response. The prompt is the
   `GOLDEN_PROMPT` in the test.
2. `POST /v1/projects/{projectId}/ensure-layered-architecture` with `{"requestedBy": actor}`.
   Initialization already materialized the layered architecture, so this is a
   no-op (`createdArtifactTypes` is empty).
3. `GET /v1/projects/{projectId}/artifacts` lists `requirement-set`,
   `component-plan`, `electrical-architecture` and `test-plan` among others.

## 2. Take an edit lease on a workspace

Each workspace (here `firmware`, later `analysis`) is edited the same way:

1. `GET /v1/projects/{projectId}/artifacts/{artifactType}/workspace/runtime` returns
   `binding` (`artifactId`, `workspaceId`, `baseArtifactVersion`,
   `baseProjectStateVersion`) and `draft.draftVersion`.
2. `POST /v1/projects/{projectId}/artifact-commands` with a
   `workspace.acquire-edit-lease` command: `schemaVersion`, a fresh `commandId`,
   `commandType`, `projectId`, the binding's `artifactId`, `workspaceId` and
   base versions, `requestedBy`, `requestedAt` and `"input": {}`.

Writes are optimistic: each one sends `expectedDraftVersion` (the current draft
version) plus the binding's `baseArtifactVersion` and `baseProjectStateVersion`,
and the response's `draft.draftVersion` is the value to send next. A stale
version is rejected rather than silently overwriting.

## 3. Firmware: scaffold, write, compile

1. `POST /v1/projects/{projectId}/artifacts/firmware/workspace/scaffold` with
   `requestedBy` and the three versions.
2. `PUT /v1/projects/{projectId}/workspaces/{workspaceId}/file` for `src/main.cpp`
   and then `platformio.ini`, each with `path`, `contentBase64`, `requestedBy`,
   `"origin": "USER"`, `"writePolicy": "USER_EDITABLE"` and the versions.
3. `POST /v1/projects/{projectId}/artifacts/firmware/workspace/compile` with
   `{"requestedBy": actor}`. It snapshots the draft and returns
   `executionRun.executionRunId`.
4. Poll `GET /v1/projects/{projectId}/executions/{executionRunId}` until
   `executionRun.status` is terminal (`completed`, `failed`, `cancelled` or
   `timed_out`). Logs are at
   `GET /v1/projects/{projectId}/executions/{executionRunId}/logs`.
5. `GET /v1/projects/{projectId}/outputs` lists produced outputs; the run's
   items (matched on `executionRunId`) include `firmware.elf`.

## 4. Analysis: scaffold, upload data, write the script, run

1. Take the lease on the `analysis` workspace (step 2).
2. `POST /v1/projects/{projectId}/artifacts/analysis/workspace/scaffold`; the
   generated files include `analysis.py`.
3. `POST /v1/projects/{projectId}/artifacts/analysis/workspace/inputs/upload` with
   `"path": "data/stationary_imu.csv"`, `contentBase64`, `"mediaType": "text/csv"`,
   `requestedBy` and the versions.
4. `PUT /v1/projects/{projectId}/workspaces/{workspaceId}/file` to replace
   `analysis.py` with the golden script.
5. Optionally, `PUT /v1/projects/{projectId}/artifacts/analysis/workspace/investigation`
   records validated investigation metadata.
6. `POST /v1/projects/{projectId}/artifacts/analysis/workspace/run` with
   `{"requestedBy": actor}`, then poll the execution as above.
7. The run's outputs include `outputs/summary.json`, `outputs/processed.csv` and
   `outputs/accel_plot.png`.
   `GET /v1/projects/{projectId}/artifacts/analysis/workspace/outputs/{outputId}/preview`
   on the summary returns its `text`: `assessment` `PASS`, `authority`
   `deterministic-code`, `requirementId` `R7`, and `accel_x_rms_noise_g`
   of about 0.015676.

## 5. Check what the run actually used

The execution run records `inputSnapshotId`, `baseArtifactVersion` and
`baseProjectStateVersion`.
`GET /v1/projects/{projectId}/artifacts/analysis/workspace/snapshots/{snapshotId}/file?path=analysis.py`
(and `?path=data/stationary_imu.csv`) returns the exact bytes the run read
from the immutable snapshot, even if the draft has changed since.

## 6. Promote the run as evidence

`POST /v1/projects/{projectId}/verify/promote-execution` with
`{"executionRunId": "<analysis run>", "requestedBy": actor, "accept": true}`.
The response reports `changed` and `accepted` as true and a new Test Plan
revision exists (`GET /v1/projects/{projectId}/artifacts/test-plan` shows a
higher `artifactVersion`). Risk K6 (simulator / hardware divergence) stays
`monitoring` in `riskMitigationAnnotations`: no physical evidence exists.
Promoting the same run again is idempotent (`idempotent` true, `changed` false).

## 7. Read the evidence chain

`GET /v1/projects/{projectId}/verify/evidence-chain` returns
`requirementVerification` (R7 and R8 `VERIFIED`) and `chains`. The R7 chain
names test `T7`, assessment `PASS` by `deterministic-code`, the criterion
`accel_x_rms_noise_g < 0.10`, the analysis `executionRunId`, and evidence
references whose `sourceId` is that run.

## Boundaries

- Verification state is computed by deterministic services from structured
  outputs. An agent cannot mark a test passing by writing prose; promoting a
  failed or crashing run does not produce PASS.
- A stub compile is not live compile evidence, and synthetic CSV analysis is
  not evidence from a physical IMU.
- Old evidence is not yet invalidated automatically when a requirement changes
  (see the golden demo notes in the root README).

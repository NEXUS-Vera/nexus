# Nexus Product MVP implementation plan

> Note (2026-10-22, 7:35 PM CT): PR #109 (M5 surfacing) was reviewed and merged to main as `113c7c7` after this document was drafted against `fa05c90`. References to #109 as in-flight describe that inspected checkout; it still needs inclusion in the Stage A baseline rerun.

Proposed for Pranay's review, 2026-10-22. Stage B ends with these documents. No work package below is authorized for implementation until review. Governing scope: [contract](NEXUS_PRODUCT_MVP_CONTRACT.md); source evidence and limits: [gap analysis](NEXUS_PRODUCT_MVP_GAP_ANALYSIS.md).

## Ordering and constraints

First confirm the Stage A frozen Engineering Core baseline independently, including merged #108 and review/integration of in-flight #109. Do not duplicate #109 or treat its diff as merged verification. Resolve critical baseline correctness/security failures before relying on the core; do not reopen M1–M10 for feature expansion.

Use the existing embedded workflow, model gateway, shared contracts, board kernel, revision governance, job scheduler, tool adapters, persistence and React workspaces. The inspected infrastructure is sufficient to attempt this scope; there is no demonstrated need for a new framework, general orchestration layer, service, package or parallel state database. Missing coordination belongs in the owning embedded workflow; reusable execution/governance remains in shared packages. Keep APIs available to external agents and CLI users.

Each row is one small reviewable work package mapped to exactly one P criterion. Dependencies refer to package IDs, not new frameworks. Split a package further if its diff cannot be reviewed narrowly. Verification is required work, not an optional later phase. Contract changes use `packages/contracts`, explicit schema versions, and compatibility tests; prompts belong in the owning agent's prompt directory with behavioral evaluations. Avoid elegance refactors and unrelated README cleanup.

## Dependency-ordered work packages

| ID / criterion | Depends on | Smallest deliverable and owning modules | Concrete verification / exit gate |
| --- | --- | --- | --- |
| W1 / P1 | Stage A baseline | Define the minimum reviewable execution-plan representation linking requirements, assumptions, component/interfaces, dependencies, workspaces and verification objectives. Extend existing embedded initialization and shared contracts only where necessary; retain current artifacts and next-action behavior. | Contract/schema/compatibility tests reject dangling links and unsupported versions; embedded evals cover novel in-scope paraphrases, unresolved consequential choices and excluded CAD/PCB/manufacturing goals. A persisted plan can be retrieved after SQLite restart. Fake-provider results are labeled regression evidence. |
| W2 / P1 | W1 | Make the approved plan actionable through existing revision governance and workspace/scaffold operations. Reconcile the fixture-only modification boundary for the narrow supported live updates in `agents/embedded-systems`; expose through existing API routes. Do not build a general conversational agent. | HTTP test initializes, proposes, rejects without mutation, revises, approves and materializes matching workspaces. Verify component/pin/build/objective consistency and stale-version rejection. Separately record live intent → reviewed plan → startable real build without developer source injection. |
| W3 / P2 | W2 | Use the existing firmware live patch generator and guarded patch application to author the golden firmware from approved context. Make missing model/toolchain explicit; prevent fixture fallback from satisfying a real-build request. Owners: embedded workflow, board firmware operations, thin API wiring. | Scripted gateway regression checks bounded context, proposal review, denied apply and stale base rejection. Live-model run creates firmware; actual PlatformIO run produces nonempty ELF/BIN tied to its snapshot with real execution mode. Missing `pio` must produce visible unavailability, not accepted live evidence. |
| W4 / P2 | W3 | Connect the newly produced firmware to existing circuit-simulation execution and capture declared observation outputs, then import those outputs into real analysis. Reuse Wokwi support/translation/runner and existing output import. Resolve the configured-ELF handoff explicitly. | Integration test checks exact build-output identity/hash consumed by simulation and exact observation bytes consumed by analysis. Run real Wokwi/test with configured prerequisites; retain logs, outputs and surrogate limits. Wrong/missing ELF, missing provider, no observations and failed simulation cannot yield claimed live verification. Synthetic input remains a separate regression. |
| W5 / P2 | W4 | Add a bounded failure-inspection/correction/rerun sequence to the embedded workflow, reusing jobs, guarded proposals and approval. Feed actual diagnostics and relevant context to the existing generator. Preserve attempts, stop on exhaustion, support cancellation. | Inject a controlled firmware/test defect; scripted regression asserts failure → diagnosis request → reviewed patch → affected reruns and retained failure history. Separately run the real model/tool loop without a human supplying the fix. Test rejected patch, unrepairable failure, timeout and cancellation; none may synthesize PASS. |
| W6 / P3 | W4 | Complete provenance at tool handoffs using existing snapshot/run/output/artifact references and dependency graph. Fix only gaps exposed by tests. Include agent context basis; avoid another ledger. Owners: board services, circuit-simulation adapter, persistence and embedded context assembly. | HTTP integration traverses requirement → firmware snapshot → build → simulator output → analysis → assessment, comparing IDs/hashes/bytes before and after SQLite restart. Wrong-project output and missing basis are rejected or require recheck; agent requests name the current relevant versions. |
| W7 / P3 | W5, W6, reviewed #109 | Exercise M5 through the completed user-facing lifecycle. Extend dependency capture only for observed missing cross-tool inputs; reuse #108 invalidation and #109 surfacing. | Accepted relevant interface/requirement/input change causes transitive STALE or RECHECK_REQUIRED with persisted reasons, unrelated result remains current, historical PASS/evidence is byte-equivalent, old-run replay cannot restore current applicability. Execute current affected steps and accept authorized verification to restore validity; repeat after restart and duplicate processing. |
| W8 / P4 | W2, W5, W7 | Connect the reviewed plan, approvals and loop progress into existing Home/project/workspace views. Finish run-output/failure/history navigation and refresh behavior; show provider modes, missing tools, limits, historical assessment and current applicability. Reuse #109 reason rendering. | Component tests cover state/error transitions. One browser/desktop journey against the real API and SQLite completes P1–P3 with rejected approval, cancellation, reload/restart and evidence navigation. Assert real-mode labels and keyboard-operable labeled primary controls at laptop sizes. A mocked API test cannot close this gate. **OPEN (N205, N223):** fixture-only profile compatibility fixed with API regressions; fixture-mode browser journey passed on host; live-mode journey still open. Host run on 2026-10-27 at main `82c911c`: 1 passed (8.6s); see slice 4 notes for command, environment and limits. P1–P3 closure remains open. |
| W9 / P5 | Contract review; session execution waits for W8 | Prepare a short external-user task and evidence protocol; recruit at least three target users. Use existing product and issue tracking, without building telemetry infrastructure. | Three distinct external participants attempt the golden workflow. Record anonymized qualification, build/environment, task, completion, assistance, failures and feedback. Each explains failure, applicability and surrogate limits. Store consented private session material outside Git and publish a sanitized aggregate suitable for review. |
| W10 / P5 | W9 | Triage observed external-user blockers into P1–P4 follow-up tasks; present outcomes, limitations and remaining risks to Pranay. Retests belong to the affected criterion's package, not silent scope expansion. | Trace every reported blocker to evidence and a criterion; report unresolved blockers and assisted completions explicitly. Obtain product acceptance review based on actual sessions and linked golden evidence; do not substitute a fabricated pass threshold or internal sign-off for external validation. |

W6 can start once W4 yields real handoff artifacts; W5 and W6 converge at W7. W9 protocol preparation can occur after contract review, but participant acceptance sessions require W8's usable workflow. No parallel-agent execution is prescribed.

W8 slice 1 (N192), approved D1/D2: keep Next Action and add Execution Plan under
FOUNDATION. The workspace mounts the typed plan review and sends revision decisions
through the typed API client. Reject is one click with an optional inline reason;
an empty reason uses the existing client default. This slice does not close the
real API/SQLite browser journey gate above.

W8 slice 2 (N193), approved D3/D4/D5: Evidence Explorer run inspection opens
an in-place log modal. Explicit Diagnose & Repair advances the existing bounded,
review-paused loop; no automatic repair or approval. The header provider pill
opens diagnostics, distinguishing initialization mode from unreported tool
availability. Component regressions cover controls and masked diagnostic text;
the real API/SQLite journey remains an open gate.

W8 slice 3 (N197, historical blocker addressed in slice 4): not accepted. Option B adds the explicit
Create Execution Plan button for projects without a saved plan, using project
I2C-connected candidates and pin specifications (GPIO 21/22 defaults). It calls
the existing propose endpoint; no automatic proposal or approval occurs. Web unit
tests cover keyboard creation, project-derived configuration, rejection/recreation,
acceptance of the pending proposal and visible API errors.

N197 host testing exposed a real HTTP 422 on propose because fixture parts
`FX-MCU-32` / `FX-IMU-200` failed the supported ESP32/MPU6050 profile check.

W8 slice 4 (N205): recognize only the documented fixture source/manufacturer/part
identities as profile surrogates, retaining their original provenance. Real-part
rules and public schemas stay unchanged. API regressions cover proposal and
materialization without candidate changes, and reject unrelated identities,
non-fixture provenance and incorrect manufacturers (19 passed, one opt-in skip in
the actionable-plan file).

The completed `apps/web/e2e/w8-golden-journey.spec.ts` and
`scripts/run-w8-e2e.sh` cover keyboard create/reject twice/recreate/accept,
real Python analysis cancellation, completed analysis evidence, actual process
stop/await/restart with the same temporary SQLite DB, persisted project/run state,
and evidence navigation into the run-log modal at 1366×768 with FIXTURE visible
and LIVE absent. Controlled user analysis files and the golden CSV are prepared
through real HTTP file routes; evidence promotion uses the real verification API.
No API interception, model generation or live firmware/simulator success is claimed.

**OPEN / fixture-mode browser journey passed on host; live-mode journey still open:**
The manager ran `COREPACK_HOME=$HOME/.cache/corepack bash scripts/run-w8-e2e.sh`
on 2026-10-27 at approximately 11:35 AM CT, on main commit `82c911c` after
PRs #125, #127 and #129 merged. On the Linux engineering box, Chromium via
Playwright, the FIXTURE initialization provider, real FastAPI with temporary
SQLite and real Python analysis reported `1 passed (8.6s)` for
`e2e/w8-golden-journey.spec.ts` ("W8 golden journey through the real API and
SQLite", 7.6s), including API process stop/restart on the same SQLite DB.
Environment note: Corepack's default cache was not writable on that box, so the
runner needed `COREPACK_HOME` set to the writable directory shown above.
This was FIXTURE initialization with no model generation, no live firmware build
or simulator success, and ran on the Linux box rather than the desktop shell.
Live provider/tool acceptance remains separately required; P1–P3 closure remains
explicitly open.

Local validation passed the 138-test web suite, web/spec TypeScript checks,
formatting/linting, repository policy, and 20 fake-provider evaluations. The plan
API regressions plus golden HTTP lifecycle passed together (20 passed, one opt-in
real-build skip). Contracts excluding type generation plus embedded unit/integration
tests passed (174 passed, one opt-in integration skip). `make check` stopped at the
repository-wide mypy check (700 errors). Broader Python runs were interrupted after
stalled progress; the verbose agent run stalled at
`test_inflight_stop_uses_existing_job_runtime[timeout]`. These runs are not claimed
as passes; sandbox/job-runner code was left unchanged.

## Verification discipline per implementation PR

Every future PR must state its P criterion, trigger and resulting behavior, owning module, architecture/contract impact, test/eval evidence, execution modes and risks. Add deterministic tests for new behavior and controlled model evaluations for prompt changes. Run the affected unit and integration suites, relevant evaluations, formatter/lint/typecheck, contract checks where applicable, and `make check`; distinguish skips, missing dependencies and failures from passes. Review diffs for secrets, user data, generated binaries/logs and prohibited documentation. Retain heavyweight run artifacts outside Git with review links.

The golden acceptance record must connect one project's steps, not assemble unrelated passing demonstrations into an end-to-end claim. Use a deterministic regression lane for repeatable CI plus separately recorded live provider/tool evidence. Live acceptance requires a configured model, installed/cached ESP32 PlatformIO toolchain, simulator CLI/entitlement/token and Python analysis dependencies; missing access is an unresolved gate. Do not read or copy credential files into evidence. Hardware validation remains outside the simulator claim.

## Post-MVP

Mechanical CAD, PCB layout, manufacturing workflows, broad multi-domain orchestration, general PLM, new simulator families, generalized planning engines, multi-user tenancy, automated telemetry infrastructure and elegance refactors are outside this plan. Broader boards/sensors and physical-device characterization are future scope unless Pranay explicitly changes the approved golden target. Critical correctness/security defects remain eligible for immediate baseline repair; they are not justification for unrelated expansion.

## Review handoff

Pranay reviews these three documents before implementation. Review should settle the proposed acceptance interpretations and dependency order, while keeping any unavailable live evidence visible. Implementation PRs remain small and criterion-mapped. Never self-merge. This task's local-only/no-remote instruction means the Stage B draft PR must be opened by an authorized follow-up; no push or remote operation is part of this work.

B5/B6 baseline correctness: functional architecture may retain concrete part names
explicitly present in the user prompt (case-insensitive exact identifiers); it
still rejects unrequested parts and more specific variants. Firmware compile/test
results containing `-Woverflow` or `-Wdiv-by-zero` are failed with
`FIRMWARE_UNSAFE_COMPILER_WARNING`, retain compiler logs, and promote no outputs
even when the compiler exits successfully. Scripted compiler regressions cover
this gate; they do not establish live toolchain acceptance.

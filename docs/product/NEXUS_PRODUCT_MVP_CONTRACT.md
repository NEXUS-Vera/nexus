# Nexus Product MVP contract — P1–P5

> Note (2026-10-22, 7:35 PM CT): PR #109 (M5 surfacing) was reviewed and merged to main as `113c7c7` after this document was drafted against `fa05c90`. References to #109 as in-flight describe that inspected checkout; it still needs inclusion in the Stage A baseline rerun.

Status: proposed for Pranay's review, 2026-10-22. Stage B documentation only; no authorization to implement Stage C. Source: approved direction `engineering-ops/directives/NEXUS_DIRECTION_2026-10-22.md`, Parts 3–7 (external to this repository). See [gap analysis](NEXUS_PRODUCT_MVP_GAP_ANALYSIS.md) and [implementation plan](NEXUS_PRODUCT_MVP_IMPLEMENTATION_PLAN.md).

## Product and scope

Nexus is “Cursor for engineering”: an interactive engineering workspace in which an agent turns intent into reviewable engineering artifacts, executes tools, learns from their actual outputs, and proposes corrections while the user retains authority. It is not a PLM system or a clone of Cursor.

Target users are students, independent engineers, researchers, and early hardware/robotics founders. The MVP serves the embedded robotics vertical through the existing ESP32 + MPU6050 vibration-monitor project. It supports requirements, components and interfaces, firmware, build, surrogate simulation/test observations, analysis, verification, and history. Mechanical CAD, PCB design, and manufacturing are outside scope. Existing physical-architecture representations do not expand that scope. Build success, simulated behavior, physical compatibility, and measured hardware performance remain distinct claims.

Engineering Core M1–M10 is a separate, frozen baseline. P1–P5 neither replace those criteria nor add new core criteria. M2 persistence, M3 traceability, M5 invalidation, and M8 reconstruction underpin P3. Core completion must be evidenced independently; this document does not certify it. In particular, merged M5 core #108 and in-flight surfacing #109 must not be conflated.

## Evidence rules

A product-path demonstration uses the normal authenticated API and product UI, durable project/file storage, configured model generation, approved tool invocations, actual run outputs, and ordinary approval/revision operations. Record commit, provider/model and tool versions, execution modes, project/revision/snapshot/run/output identities, commands, outcomes, and limitations. Keep demonstration artifacts outside Git; link them in review evidence. API/CLI remains a first-class way to drive and reconstruct the workflow.

Deterministic scaffolds and validators are legitimate product implementation. Returning a preselected project fixture instead of interpreting the user's intent, scripted model replies, fake runtimes, compile stubs, hardcoded repair scripts, and fabricated telemetry cannot prove agentic or live execution criteria. They remain useful regression tests when labeled. Real Python processing of synthetic input proves computation on that input only. A simulator's real invocation proves surrogate behavior, not physical IMU performance. Developer harness calls into the kernel prove service integration, not UI completion. Manual approvals are required product interactions; manually copying code, diagnosing the failure for the agent, or fixing its files is not evidence of P2. Manual external-user observation is the appropriate evidence for P5.

Unavailability must be visible and block the corresponding acceptance claim; fallback success cannot count as real execution. Isolated tests support, but do not replace, a linked end-to-end acceptance record. Proposed verification below is a release gate, not a claim it ran.

## P1 — Intent to executable project

Given an in-scope goal in the normal product entry point, Nexus must:

- Produce linked requirements with testable objectives, component choices and interfaces, explicit assumptions/open questions, workspace bindings and dependencies, and an ordered, reviewable execution plan.
- Make unresolved consequential choices visible; obtain user approval before consequential changes or execution requiring it. Reject unsupported scope clearly.
- After approval, instantiate a usable firmware/analysis project whose selected interfaces, build configuration and verification objectives agree. A next-action label alone is insufficient.

Verification: enter a novel paraphrase of the ESP32/MPU6050 goal using the configured model, inspect the proposed artifacts and plan in the UI and API, reject one consequential proposal and prove no application, approve a revised proposal, and start its build without developer file injection. Assert requirement-to-plan-to-workspace references and persistence after restart. Repeat out-of-scope and unresolved-interface cases. Fixture initialization/schema tests are supporting evidence only.

## P2 — Closed-loop agentic engineering

Given that approved project, the agent must write/modify real firmware through guarded patches, run a real ESP32 build, run real simulation/test with captured observations, inspect outputs, identify an injected failure, propose a causally relevant correction, and rerun the affected steps. Preserve failed attempts and patch/review/run history. Deterministic verification alone assigns PASS/FAIL; the agent cannot restore validity with prose. Retrying is bounded and cancellable; inability to repair ends in a visible explanation and retained evidence.

Verification: run the golden sequence below with stubs disabled and actual providers. Introduce a controlled, documented firmware/test defect; do not supply its fix to the model. Capture failing outputs, the agent's diagnosis and reviewed diff, corrected run, and deterministic result. Check that outputs derive from the newly built firmware, rather than an unrelated configured ELF or uploaded CSV. Also test an unrepairable failure, cancellation, stale proposal rejection, and rejected approval. Scripted model tests prove control flow only; a separately executed live-model acceptance record proves agentic repair.

## P3 — Cross-tool context continuity

Requirements, selected components/interfaces, source revisions, snapshots, builds, simulation/test observations, analysis and verification must remain linked across tool transitions and restart. The next agent action must use the relevant current context. An accepted relevant input change must invalidate affected applicability automatically, preserve historical PASS/FAIL and evidence, explain dependencies/reasons, and leave unrelated results valid. Unknown impact requires recheck. Only authorized verification of current inputs can restore applicability.

Verification: on the P2 project, traverse requirement → source snapshot → build → simulation observation → analysis → assessment through API and UI. Restart and compare identities and bytes. Change a relevant input through ordinary revision acceptance, assert STALE/RECHECK_REQUIRED and reasons; make an unrelated change and assert its results stay current. Reject replay of old runs as revalidation, then execute and approve current verification. Include a transitive cross-tool change and missing provenance. M5 unit/service tests alone do not establish the entire chain.

## P4 — Accessible, cohesive UI workflow

A target user must be able to start from a goal, review the plan and artifacts, approve/reject changes, observe/control execution, inspect outputs, understand failures, and explore revisions, verification and limitations in one product workflow. Show fixture/live mode, unavailable tools, pending/running/failed/cancelled states, historical assessment versus current applicability, and actionable reasons. Key controls must be labeled, keyboard operable, and usable at ordinary laptop viewport sizes. No developer shell or direct database manipulation may be needed for the normal golden workflow. API/CLI functionality must remain available.

Verification: browser/desktop end-to-end test against real API and durable storage, covering the P1–P3 sequence, reload/restart, failure, cancellation, approval rejection and history navigation. Check keyboard traversal and accessible labels for primary controls. Run a human walkthrough recording any assistance; mocked client rendering tests and fixture browser navigation are supporting evidence only.

## P5 — External target-user validation

At least three external target users from the stated audience must attempt the golden workflow in the product. Record anonymized target-user qualification, build/environment, task, completion/abandonment, assistance, failures, evidence interpretation and feedback. Internal engineering runs or three scripted personas do not count. Do not invent a satisfaction threshold absent from the approved direction: report outcomes honestly, including blockers, and present them to Pranay for acceptance.

Verification: observe three distinct external participants, capture consented and sanitized session evidence outside Git, and provide a durable aggregate record plus linked issues mapped to P1–P4. Ask each user to explain the failure, the current verification state, and the simulator/hardware limitation. Product usability is not established by a test count or developer demonstration.

## Golden acceptance sequence

1. Describe the ESP32 + MPU6050 embedded robotics project.
2. Review and approve its plan, requirements, assumptions and verification objectives.
3. Open the component/interface and firmware workspaces.
4. Have the agent write real firmware through reviewed proposals.
5. Execute a real ESP32 build and retain its produced binary identities.
6. Execute real simulation/test using those outputs; capture observations and analyze them.
7. Detect an injected failure from actual outputs.
8. Have the agent propose a fix, obtain required approval, and rerun affected steps.
9. Accept an input revision and observe automatic M5 invalidation and authorized re-verification.
10. Inspect artifacts, evidence, revisions, execution history and limitations in the UI.

P1–P5 are accepted only with their evidence and explicit limitations reviewed. This proposed contract makes no present MVP-complete claim.

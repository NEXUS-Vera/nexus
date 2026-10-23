# Embedded Project Initialization (v1)

This document freezes the **first supported workflow boundary** for Nexus’ embedded product slice.

## Workflow

**Workflow type (v1):** `embedded-project-initialization`

### Supported input (what the workflow accepts)

The workflow accepts **one user prompt**:

- An early-stage embedded-product idea expressed as natural-language text.
- The product may involve any combination of:
  - embedded sensing
  - simple robotics
  - environmental monitoring
  - wearable sensing
  - data logging
  - signal acquisition
  - microcontroller-based prototypes
  - simple connected devices
  - early-stage embedded instrumentation

#### Examples

- indoor environmental rover
- wearable tremor monitor
- greenhouse sensing node
- vibration-monitoring device
- obstacle-detection module
- temperature and humidity logger
- BLE motion tracker
- room-occupancy sensing device

### Required input characteristics

The prompt must describe or imply:

- something the user wants to build; and
- an embedded/physical-computing element; and
- an early concept or prototype-planning stage.

The prompt does **not** need to include complete requirements.
Missing requirements are expected and should later become explicit unknowns or open questions.

### Unsupported input (v1)

This workflow does **not** support:

- debugging an existing codebase
- diagnosing uploaded logs
- editing firmware
- generating production-ready firmware
- PCB layout
- schematic validation
- simulation execution
- detailed component selection
- final BOM generation
- regulatory certification
- medical-device approval
- manufacturing planning
- deployment
- purchasing components
- modifying an existing persisted project
- non-project factual questions
- products outside embedded products

## Promised outputs (what a successful run produces)

When the workflow accepts an input and reaches a successful completion, it produces exactly:

- one **Project**
- one **User Turn**
- one **Turn Route**
- one **Workflow Run**
- one **Project Brief** artifact
- one **Requirement Set** artifact
- one **Functional Architecture** artifact
- one **Component Plan** artifact (Phase 12: roles, constraints, provisional candidates, coverage)
- one **Next Action** artifact
- zero or more **Validation Issues**
- zero or more **Open Questions**
- one **Vera Response**

The workflow does **not** generate the requested artifacts using an unconstrained free-form LLM dump.
Artifact content is produced by staged generation + deterministic assembly (fixture or LLM provider), then validated against `packages/contracts`.

## Artifact maturity boundary

The workflow defines an architecture maturity scale:

- conceptual
- functional
- logical
- physical
- validated

For this first workflow:

- `architectureMaturity = functional`

The functional architecture is **functional**, not physical.
It describes responsibilities, data/control flow where relevant, and system-level interactions.

It must not claim validated choices of:

- sensor
- MCU
- board
- battery
- protocol
- firmware library
- operating system
- physical bus
- part number

Detailed procurement-ready BOM generation remains out of scope. Phase 12 introduces a **Component Plan** artifact that may propose provisional, unverified candidates and selection constraints without claiming grounded or tested evidence.

## Artifact meanings (what each artifact must contain)

### Project Brief

A concise structured definition of:

- problem
- goal
- intended context
- scope
- out-of-scope items
- success criteria
- assumptions
- unknowns

### Requirement Set

Requirements describe what the product must achieve.

Requirements must distinguish:

- explicit user requirements
- inferred proposed requirements
- unknown requirements
- confirmed requirements

The requirement set must not silently hard-code components or implementation choices unless:

- the user explicitly requires them; or
- they have already been accepted as project constraints.

### Functional Architecture

First architecture is functional, not physical.

It describes:

- major subsystem responsibilities
- data flow
- control flow where relevant
- inputs
- processing
- storage
- communication
- output or actuation

It must not claim validated choices of:

- sensor
- MCU
- board
- battery
- protocol
- firmware library
- operating system
- physical bus
- part number

### Component Plan

Phase 12 Component Plan content includes:

- component roles derived from architecture nodes (with architecture + requirement refs)
- selection constraints derived from requirements where possible
- provisional candidates (fixture or staged proposal at initialization; evidenceStatus must not be overstated)
- preferred selection proposals (`awaiting-user`) that are not auto-approved
- selection decisions and compatibility checks when present
- coverage summary (roles/candidates/architecture coverage)
- maturity from `roles-defined` through `validated`

Supported fixture initialization normally lands at `candidates-proposed` or
`selection-proposed` with provisional candidates for major roles. Users should
not need to click Request alternatives merely to see the first candidates.

Semantic validators reject unknown role references, blocked candidates approved as selections, duplicate approved selections per role, coverage mismatches, and `tested` candidate evidence in Phase 12.

### Next Action

The Next Action is the highest-value immediate step derived from:

- blockers
- unknown requirements
- validation issues
- architectural gaps
- component-plan gaps (missing constraints, awaiting approval, roles without candidates)

It must not be a generic statement such as:

- “continue building”

## Definition of success for the future embedded initialization workflow

The workflow will be considered successful when:

- all outputs conform to the contracts
- explicit and inferred information are distinguishable
- unsupported assumptions are not presented as fact
- architecture remains functional rather than component-specific
- requirements are traceable into architecture
- the Next Action follows from actual blockers
- all artifacts share common provenance and version metadata
- invalid or incomplete output is surfaced honestly

## Persistence and multi-turn modification (Phases 9–10)

After successful initialization, the complete project package is persisted
(backend selected by `NEXUS_STORAGE_BACKEND`; see
[`apps/api/README.md`](../../apps/api/README.md)). Projects reload by ID.

Multi-turn updates use `POST /v1/projects/{projectId}/turns`. Fixture mode
supports deterministic patterns (runtime/battery, accuracy answers, sampling,
environment, communication, size/weight, budget, reject proposed requirement,
and component-plan ops: approve/reject candidates, preferences, budget/interface
constraints, alternatives, answer component open questions)
without a model key. Only impacted artifacts receive new immutable revisions
(`new artifactId`, incremented `artifactVersion`, `supersedes*` links).
Unaffected component role IDs are preserved across selective updates.

Every API request carries a session token; multi-user tenancy is not
implemented. See [`apps/api/README.md`](../../apps/api/README.md).


## Reviewable initialization execution plan (W1 / P1)

Successful fixture and LLM initialization now include `project.executionPlan`,
using `project/execution-plan.v1.schema.json` in `packages/contracts`.
This optional addition preserves legacy v1 projects and the existing seven
artifacts and next-action selection. It is a proposed review checklist, not an
approval record or executable tool request. No workspace is created by this addition.

The plan pins source artifact IDs/revisions and the initialization project-state
version. Requirements, assumptions, component roles (including their existing
candidate/decision records), and electrical connections are referenced in those
sources; no component compatibility is asserted by the plan. Objectives preserve
requirement verification methods and acceptance criteria. Missing criteria remain
empty for review rather than being invented. Open questions remain open decisions.
Steps declare earlier-step dependencies, objective links, workspace targets and
required approval. Workspace keys are plan-local targets, not runtime workspace
IDs: `artifact-available` means an artifact exists, while `planned` explicitly
means a future artifact/workspace must be prepared.

The existing project JSON payload persists the plan atomically with initialization
in memory, SQLite or PostgreSQL. `POST /v1/projects/initialize` returns it and
`GET /v1/projects/{projectId}` retrieves it, including after SQLite restart.
No new endpoint, table, state store or migration is needed. JSON Schema rejects
unsupported plan versions; shared semantic validation checks links against the
pinned initialization basis, including objectives and workspace targets. Later
project changes retain the original proposal and basis; they do not reconcile or
approve it. Reconciliation, actionable approvals and scaffold consistency are W2.

`evals/embedded_project_initialization` includes a novel ESP32/MPU6050 paraphrase,
a consequential unresolved interface choice, and excluded CAD, PCB and
manufacturing requests. Fake-provider reports explicitly say `evidenceKind:
regression`: their model responses are scripted from case expectations. They
prove assembly, validation and question preservation, not live intent understanding
or P1 acceptance. A configured live-model run, plan review UI, rejection/revision,
approved workspace materialization and startable build remain open product gates.


## Actionable review and workspace preparation (W2 / P1)

W2 adds a bounded typed modification path in the embedded workflow, independent
of initialization provider mode. It uses the existing immutable snapshot,
revision proposal, user acceptance/rejection, ledger, workspace lease and file
operations. The fixture-only restriction on free-form `/turns` modification
remains; it does not apply to typed plan, component and interface revision review.
No general conversational interpreter or UI is added.

A new `execution-plan` artifact content contract wraps the unchanged W1 proposal
with explicit materialization configuration. The original project-level proposal
is retained as history, not silently reconciled. Proposal refresh pins current
source revisions, requirements/objectives, component roles/candidates, connection
and workspace targets. Source/objective mismatch, stale project/plan versions,
unsupported boards/parts, unresolved bus selection and conflicting pins fail
visibly. Fixture candidates must be explicitly revised to actual supported part
numbers through normal artifact governance; there is no alias/fallback that
turns FX parts into real component evidence. Approval authorizes prototype
selection and wiring only; existing provisional/unverified evidence stays so.

Rejection preserves accepted artifacts and scaffold bytes. A revised approval
creates the accepted plan artifact and deterministic firmware/analysis workspaces
with identical reviewed context, matching ESP32 build profile, explicit I2C pin
constants used by `Wire.begin`, and preserved verification methods/criteria.
Analysis remains the existing scaffold, not claimed sensor-noise verification.
Existing different files are never overwritten. Metadata acceptance and file
materialization are separate existing storage operations: an infrastructure
failure can leave an approved plan with partial files and a failed command. The
explicit materialization retry completes matching missing files without another
approval; stale bases and differing files remain blocked. This is not an atomic
cross-store filesystem transaction. Subsequent edits to already materialized
projects require workspace reconciliation; W2 does not overwrite user firmware.

### W2 verification and remaining live gate

`apps/api/tests/test_actionable_execution_plan.py` drives initialization, explicit
scripted component review, plan proposal/rejection/revision/acceptance, matching
firmware/analysis files, negative validation and stale rejection over HTTP.
SQLite restart checks retain accepted plan identities, file metadata/hashes and
actual context bytes. Shared contract tests retain legacy W1 compatibility and
reject unsupported actionable configurations. These are **regression evidence**:
fixture initialization and scripted reviewer choices do not prove live intent
interpretation. The opt-in real skeleton build, when executed, proves compilation
of that scaffold only; it is not agent-authored sensing firmware or P2 evidence.

**Remaining P1 live acceptance gate:** record one novel live intent → configured
model-generated artifacts → reviewed/rejected/revised/approved plan → startable
real build, without developer source injection. Record commit, model/provider,
project/source/plan/snapshot/run/output IDs, tool versions, actual execution modes
and limitations outside Git. No live-model acceptance run was performed for W2;
this gate remains open. Current candidate generation can still propose fixture
parts; their conversion must be an explicit reviewed component edit, never a
silent scaffold fallback. Model-supported component choice and review UI remain
product gaps. Firmware generation/repair and the real tool loop belong to W3–W5;
UI belongs to W8. This implementation does not close P1 product acceptance.

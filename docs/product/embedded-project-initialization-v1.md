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
- provisional candidates (fixture or staged proposal; evidenceStatus must not be overstated)
- selection decisions and compatibility checks when present
- coverage summary (roles/candidates/architecture coverage)
- maturity from `roles-defined` through `validated`

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


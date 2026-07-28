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
- one **Next Action** artifact
- zero or more **Validation Issues**
- zero or more **Open Questions**
- one **Vera Response**

The workflow does **not** generate the requested four artifacts using an LLM.
Instead, this slice defines the contract boundary and object meanings. Artifact content is produced by a non-LLM implementation in a later phase.

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

Component-level recommendations belong to a later workflow.

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

### Next Action

The Next Action is the highest-value immediate step derived from:

- blockers
- unknown requirements
- validation issues
- architectural gaps

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


# Golden Electrical Simulation Demo

This walkthrough opens the Phase 13C golden Nexus project (FX-MCU-32 + FX-IMU-200)
in the Electrical workspace Design and Simulation modes. Wokwi remains a backend
provider only.

## Prerequisites

- Local Nexus API and web (`make dev-api`, `make dev-web`)
- Optional for a real run: Wokwi CLI, `WOKWI_CLI_TOKEN`, and `NEXUS_WOKWI_FIRMWARE_ELF`
  (see `.env.example`)
- Normal `make check` never consumes Wokwi minutes

## Initialize / open the golden project

Fixture family: `esp32-imu-circuit-simulation`

From the home/new-project flow, initialize with:

```text
I want a golden Nexus circuit simulation project with an ESP32-class MCU and an IMU motion sensor for Wokwi surrogate simulation.
```

The live prompt is routed to fixture family `esp32-imu-circuit-simulation`. Requirements
marked user-explicit align with that golden prompt so fixture materialization validates
after `rawUserMessage` is replaced. The Component Plan is narrowed to FX-MCU-32 +
FX-IMU-200 for the Wokwi golden path.

Or:

```bash
make seed-wokwi-golden-project
```

Open Architecture → Electrical.

## Design mode

Expected:

- Fixture MCU (FX-MCU-32) and Fixture IMU (FX-IMU-200) as rich electrical nodes
- I²C connection label (composed from the golden Functional Architecture IMU→MCU edge)
- Power-domain rail treatment
- Inspector shows identity, interfaces, and requirement/component links from canonical data
- Surrogate provider identities are not shown as the selected Nexus parts

Re-initialize a **new** project after fixture updates; existing projects keep their older Electrical graph.

URL shape: `?view=electrical` (Design is default)

## Simulation mode

Switch to Simulation (`?view=electrical&mode=simulation`).

Expected:

- Provider: Wokwi (Circuit Simulation product label)
- Surrogate disclosure for ESP32 + MPU6050 mappings
- Provider pins derived from the same materialization the backend executes
- Run Simulation uses the existing lease → snapshot → execute path
- Serial output and ProducedOutputs appear inside Nexus
- Evidence wording stays unverified for actual hardware compatibility

## Real smoke test (opt-in)

```bash
RUN_WOKWI_INTEGRATION=1 make test-wokwi-smoke
```

## Unsupported projects

Wearable / greenhouse fixtures with unmapped FX-ENV-* parts remain unsupported.
Simulation mode lists unmapped components; Design remains fully usable.

## Future schematic boundary (not implemented)

```text
Electrical Architecture
        ↓
future Nexus Electrical Netlist / Schematic Model
        ↓
derived renderer / EDA provider
```

Do not add speculative netlist fields to Electrical Architecture v1.

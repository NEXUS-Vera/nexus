# Circuit Simulation

## Purpose

Reusable, provider-neutral circuit simulation support for Nexus.

## Ownership boundary

This package owns circuit support assessment, deterministic provider-workspace
translation, safe local simulator invocation, and normalized validation and
execution results.

## What belongs here

- The `CircuitSimulationProvider` protocol and typed public models
- Exact, explicit provider-part mappings
- Deterministic electrical-architecture translation
- Safe subprocess isolation for locally installed simulation providers
- Fake and Wokwi provider implementations

## What must not be placed here

- Firmware binaries or credentials
- Automatic provider installation
- Application, board, contract, or domain-agent orchestration
- UI layout coordinates or arbitrary subprocess arguments

`WokwiProvider` discovers or accepts an installed `wokwi-cli` executable. It
never installs the CLI. Materialization is offline and does not require a
credential; execution requires a constructor-injected token and firmware ELF.

The checked-in golden firmware is source-only at
`agents/embedded-systems/tests/fixtures/wokwi/sketch.ino`. Build it outside the
repository for an ESP32 target, then set `NEXUS_WOKWI_FIRMWARE_ELF` to the
resulting `.elf`, set `WOKWI_CLI_TOKEN`, and run:

```sh
RUN_WOKWI_INTEGRATION=1 make test-wokwi-smoke
```

The smoke target is intentionally excluded from `make check`. Wokwi account
availability, quotas, entitlements, and commercial terms are external to
Nexus. Simulation outputs describe behavior observed in a surrogate provider
model; they do not verify compatibility with the selected real component.

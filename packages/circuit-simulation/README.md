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
Provider diagnostics and every execution output redact that token before
serialization. The runner accepts only allowlisted workspace filenames, rejects
symlinks and special output files, bounds file reads, and bounds subprocess
timeout recovery even when descendants retain pipe handles.

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

The API simulation default is thirty simulated seconds (enough for at least 100
TEL samples at 100 Hz after a one-second settle). Explicit duration requests
remain supported. Wokwi gets a host budget of 20 times the simulated duration
plus 10 seconds for startup, capped at 310 seconds. On host timeout, available
serial output is retained on the timed-out run as unverified, truncated evidence;
it does not make the simulation successful. These budgets do not guarantee a
live provider will finish under every load.

Without expected serial text, a Wokwi simulation timeout (exit 42 with the
matching timeout diagnostic) completes the fixed capture window successfully.
The result retains exit code 42 and an informational `CAPTURE_WINDOW_REACHED`
finding. Requested observations must still be present and complete. With
expected text, the same timeout fails. Other nonzero exits fail with the exit
code and a bounded, credential-redacted stderr tail in the diagnostic.

Materialization accepts an optional execution-plan artifact on
`MaterializationRequest.execution_plan` (an additive Python API field). The API
supplies the user-approved plan. Its `configuration.i2c.sdaPin` and `sclPin`
drive both diagram wiring and the manifest pin profile. Missing pins default to
21/22. Pins must be distinct integers from the actionable v1 plan allowlist:
21, 22, 25, 26, 27, 32, 33. Unsupported pins produce an error finding and no I2C
wiring. Shared artifact schemas are unchanged.

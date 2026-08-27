# Golden Full Demo Execution

End-to-end walkthrough of the canonical Nexus golden project
`esp32-imu-vibration-monitor`: intent → board artifacts → Firmware / Analysis
execution → deterministic VERIFY evidence → Requirement coverage.

This is the single demo execution guide. Wokwi remains an optional backend
provider; physical hardware validation is intentionally out of scope.

## Prerequisites

- Local API and web: `make dev-api`, `make dev-web`
- Fixture initialization (default): `NEXUS_INITIALIZATION_PROVIDER=fixture`
- Optional live model: set `NEXUS_MODEL_*` in `.env` and use `llm` provider
- Optional containers: `nexus-python-analysis:1.0.0`, PlatformIO ESP32 image
- Optional Wokwi: `WOKWI_CLI_TOKEN`, firmware ELF (see `.env.example`)
- `make check` never requires live model, Docker, or Wokwi minutes

## Canonical prompt

Fixture family: `esp32-imu-vibration-monitor`

```text
Build an ESP32-based vibration monitor using an MPU6050. It should stream
acceleration telemetry and analyze stationary sensor noise to verify that
accel_x RMS noise stays below 0.10 g.
```

Initialize from the home / new-project flow with that prompt (fixture mode), or
use the live LLM provider when configured.

Electrical-only Wokwi seed (narrower circuit-simulation family):

```bash
make seed-wokwi-golden-project
```

## Expected board artifacts (eight-artifact path)

After initialization, the project board should include:

| Artifact | Golden expectation |
| --- | --- |
| Project Brief | Vibration monitor intent |
| Requirement Set | R1–R8 |
| Functional Architecture | MCU + IMU sensing / telemetry flow |
| Component Plan | ESP32 + MPU6050 class parts |
| Electrical Architecture | I²C SDA→GPIO21, SCL→GPIO22 |
| Firmware | PlatformIO scaffold / golden sources |
| Analysis | Stationary noise investigation |
| Test Plan | T1–T8 covering R1–R8 (start ready / unverified) |
| Risk Register | K1–K6; **K6 remains monitoring** |

Also: Next Action, Mind Graph edges, Evidence Explorer.

Coverage and verification are separate: **8/8 covered does not mean 8/8 verified**.

## Product flow

### 1. Intent → Requirements / Architecture / Components

1. Submit the canonical prompt.
2. Open Brief, Requirements (confirm R1–R8), Functional Architecture, Component Plan.
3. Confirm Next Action / Mind Graph still surface meaningful gaps when present.

### 2. Electrical Design (+ optional Simulation)

1. Open Architecture → Electrical (`?view=electrical`).
2. Confirm I²C mapping: SDA GPIO21, SCL GPIO22.
3. Optional Simulation mode (`?view=electrical&mode=simulation`):
   - Translation / pin map evidence is **structural**, not live runtime proof.
   - Live serial evidence only counts when a real Wokwi run produces it.
4. Promote structural evidence when available
   (`POST /v1/projects/{id}/verify/promote-structural`) or via product wiring.

### 3. Firmware workspace

1. Open Firmware → generate scaffold if empty (`platformio-arduino-esp32-v1`).
2. Compile (process stub or PlatformIO container when configured).
3. On successful completion, Nexus may promote execution/marker evidence into the
   Test Plan (idempotent). Marker tests require real log text such as
   `NEXUS_MPU_READY` — source inspection alone is not runtime evidence.

### 4. Analysis workspace

1. Open Analysis → scaffold / load golden `analysis.py` + `stationary_imu.csv`.
2. Run Analysis against an immutable snapshot.
3. Confirm ProducedOutputs: `outputs/summary.json`, `outputs/processed.csv`,
   `outputs/accel_plot.png`.
4. On run completion, product path promotes matching evidence into a **new**
   Test Plan revision (never mutates an accepted plan in place).

### 5. VERIFY — Test Plan, Risks, Evidence

1. Open Test Plan: cases start Ready / Unverified until evidence arrives.
2. After Analysis promotion, inspect **T7 / R7**:

   | Field | Expected |
   | --- | --- |
   | Requirement | R7 |
   | Expected | accel_x RMS noise &lt; 0.10 g |
   | Actual | ≈ 0.0157 g |
   | Assessment | PASS |
   | Authority | Deterministic |
   | Evidence | Analysis ExecutionRun + `summary.json` metric |
   | Requirement state | VERIFIED |

3. **T8**: existence of summary / processed / plot → PASS when outputs present.
4. Open Risk Register → **K6 Simulator / hardware divergence**:
   - Status: **Monitoring**
   - Reason: no physical hardware evidence
   - Wokwi success does **not** close K6
5. Open Evidence State: Requirement → TestCase → EvidenceReference → run/output.

## Hermetic proof (no live keys)

```bash
export NEXUS_STORAGE_BACKEND=memory NEXUS_EXECUTION_RUNTIME=process
export NEXUS_INITIALIZATION_PROVIDER=fixture
unset RUN_PHASE14_E2E RUN_DOCKER_INTEGRATION RUN_WOKWI_INTEGRATION
make check

# Phase 17F G1 + negative paths N1–N9
python -m pytest packages/board/tests/test_phase17f_verify_e2e.py -q
```

## Opt-in live gates

```bash
# Live LLM Test Plan + Risk Register drafts
RUN_PHASE17_LLM=1 python -m pytest \
  packages/board/tests/test_phase17f_verify_e2e.py::test_g2_live_llm_test_and_risk_generation -q

# Analysis Python container (Phase 16 G3)
RUN_ANALYSIS_DOCKER_INTEGRATION=1 python -m pytest \
  packages/board/tests/test_phase16_e2e_acceptance.py::test_phase16_g3_live_python_container_e2e -q

# Wokwi smoke (consumes provider minutes)
RUN_WOKWI_INTEGRATION=1 make test-wokwi-smoke
```

Missing PlatformIO image / Wokwi / model endpoint is
`GAP — ENVIRONMENT/HARNESS`, not a product defect, when hermetic G1 passes.

## Invariants to keep visible while demoing

- LLM prose is never PASS / FAIL / VERIFIED / MITIGATED authority.
- Evidence matching is structured (metric ID, outputs, markers, pin maps) — no fuzzy attach.
- Reprocessing the same ExecutionRun is idempotent.
- Requirement VERIFIED is a projection over accepted Test Plan state, not stamped prose.
- K6 stays open / monitoring without physical evidence.

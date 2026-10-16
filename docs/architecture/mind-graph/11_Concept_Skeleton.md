# Mind Graph — Concept Skeleton v0 (Embedded Systems)

**What this is:** the hand-built prerequisite graph the frontier engine needs on day one — **213 Concept nodes and their `requires` edges**, in the real ingest format.
**Status:** ⚠️ **v0 draft, authored from general knowledge. Expect ~20–30% correction by an ECE domain expert.** It is a starting point to argue with, not a source of truth.
**Owner after review:** the ECE teammate. This is domain work, not engineering work.
**Date:** 2026-08-07

> **Why this exists.** Report 04 §1.1: Knowledge Space Theory gives us the frontier engine — a student's *outer fringe* is exactly "what they're ready to learn next." But KST needs a prerequisite structure, and the research found that **"high-accuracy, standardised open datasets for granular engineering curricula remain remarkably scarce."** There is nothing to download. Knowledge tracing (BKT/DKT) can't substitute either — it *"suffers catastrophically from the cold start problem for a single, isolated learner."* Production systems answer this by falling back on a **predefined domain-expert ontology** (as ALEKS does) until behavioural data accumulates. This is ours.

---

# 1. Format

```yaml
- id: i2c                      # stable slug. NEVER changes once published.
  label: I²C                   # display name
  aliases: [I2C, IIC, TWI, Inter-Integrated Circuit]
  tier: 2                      # 0 background · 1 foundation · 2 core · 3 applied · 4 specialist
  domain: comms
  requires: [digital_io, clock_signals]
  verify: "wire two devices and read a register"   # what counts as knowing it
```

**Field rules:**

| Field | Rule |
|---|---|
| `id` | lowercase `[a-z0-9_]`. **Permanent** — renaming breaks every student graph |
| `aliases` | ⭐ **every** surface form. This is the entity-resolution seed (05 §1.6) and the cheapest defence against fragmentation. Under-filling it is the most damaging mistake available here |
| `tier` | rough depth. Used for semantic-zoom labels and initial layout, **not** for prerequisite logic |
| `requires` | **A requires B ⟺ you cannot meaningfully learn A before B.** Direction errors are the expensive kind — they send students backwards |
| `verify` | ⭐ what would count as evidence the student knows this. **This field is the bridge to the whole verifiability thesis** (07): it is the seed for an Artifact's `predicted` |

**`requires` discipline:**
- Concept → Concept only. Never a Source, Artifact, or Claim (enforced in `10 §4`).
- **Minimal edges only.** If `A→B` and `B→C`, do *not* also write `A→C`. Transitive closure is computed; redundant edges corrupt the fringe calculation by making concepts look more blocked than they are.
- Aim for **2–4 prerequisites per concept**. More than 5 usually means the concept should be split.
- **No cycles.** CI must check this — a cycle makes the outer fringe empty and the frontier engine silently returns nothing.

---


> ### ✅ RESOLVED — Q10 · *Is the granularity right?* — **structurally yes; `verify` is the real gap** *(2026-08-10)*
>
> **The structural half is measured and passes** (§1.1 below). The semantic half — *is this concept one afternoon of work?* — stays a domain judgement, but it is now a **bounded** ask rather than an open review. See §1.2.
>
> **Full record: `Backend/09` Q10.**

## 1.1 ⭐ The validator — `tools/validate_skeleton.py` *(added 2026-08-10)*

This document specified CI checks and nobody had run them. They now run:

```bash
python3 tools/validate_skeleton.py        # exits non-zero on any ERROR
```

**First run found six real defects.** Fixed in this revision:

| | Found | Status |
|---|---|---|
| cycles | 0 | ✅ |
| dangling `requires` | 0 | ✅ |
| **stated count** | doc said **187**; there are **213** (headers already summed to 213) | ✅ corrected |
| **redundant transitive edges** | **34** | ✅ 26 dropped · ⚠️ 8 kept, see below |
| isolated concepts | 3 — `version_control`, `soldering`, `enclosure_basics` | ⚠️ open |
| `verify` coverage | **14%** | ❌ see §1.2 |
| `aliases` coverage | **32%** | ❌ |

> ### ⚠️ Blind transitive reduction is **not** safe here
>
> The rule in §1 says redundant edges *"corrupt the fringe calculation by making concepts look more blocked than they are."* True — but only when the implying path stays in the same domain.
>
> `fft requires complex_numbers` is transitively implied via `impedance → ac_analysis → frequency_response → sampling_theorem`. **Drop it and a student who knows complex numbers but not impedance is told the FFT is blocked on electrical material they don't need.** The direct edge is load-bearing precisely because the implying path detours through another domain.
>
> ⭐ **So the validator splits redundancies by domain.** Same or adjacent domain → safe to drop (26, applied). **Crossing three or more domains → flagged, kept, human decides** (8: `bioimpedance`, `eis`, `fft`, `hardfault_debug`, `instrumented_logging`, `model_quantization`, `physiological_validation`, `rtos_basics`).

**Structural granularity signals** — these are what the fringe engine actually consumes:

| | Value | Read |
|---|---|---|
| `requires` per concept | mean **1.49**, median 1, max 3 | target is 2–4 → slightly **under**-connected |
| DAG depth | **15** | reasonable for a 4-tier domain |
| leaves | **83 / 213 (39%)** | ⚠️ *"unlocks N things"* is silent for two-fifths of the graph |
| ⭐ **outer fringe** | **7** cold → **19** at 15% known → **35** at 35% known | ⭐ **healthy** |

⭐ **The fringe row is the granularity test, run.** The Bench picks 3 `NOW` items from the fringe. **Choosing 3 from ~20–35 gives the DOI ranking real work to do** — too coarse would show as a fringe of 3–5 (no choice), too fine as 200 (ranking is arbitrary). It lands in the right band.

## 1.2 ⭐ The gap that matters more than granularity — `verify`

**86% of concepts have no `verify` statement.** §1 calls that field *"the bridge to the whole verifiability thesis — the seed for an Artifact's `predicted`."*

Without it the frontier can say **what** to learn next but not **what would count as having learned it** — and that loop is the entire product. It is worst exactly where it should be strongest:

```
math 0/8 · digital 0/16 · hardware 0/10 · programming 2/22 · dsp 1/10
```

**Granularity being slightly off degrades ranking. `verify` being absent breaks the mechanism.**

> ### 📋 The ECE teammate's task — deliberately narrow
>
> **Not** *"review 213 concepts"* — nobody does that, and an unbounded review returns nothing.
>
> ⭐ **Instead: write `verify` for the ~50 concepts on the biosensor path.** Bounded, concrete, and it targets the field that carries the most weight.
>
> **Granularity judgement arrives as a side effect** — you cannot write *"predict settling time and confirm on a scope"* for something that isn't about an afternoon of work. The task tests the thing by requiring it, instead of asking for an opinion about it.
>
> Second pass, same shape: `aliases` for the same 50. That's the entity-resolution seed, and §1 already calls under-filling it *"the most damaging mistake available here."*


# 2. Tier semantics

| Tier | Meaning | Where it usually comes from |
|---|---|---|
| **0** | background maths/physics | transcript, assumed |
| **1** | foundations | first/second-year courses |
| **2** | core embedded | the working vocabulary of the domain |
| **3** | applied subsystems | where projects actually live |
| **4** | specialist | the edge of an undergrad project |

Tiers also drive `labels_at` for semantic zoom (04 §2.1) — zoomed out you see tier-1 domain clusters, zoomed in you see tier-3/4 specifics.

---

# 3. The skeleton

## 3.1 Tier 0 — background (12)

```yaml
- {id: algebra_manipulation, label: Algebraic manipulation, tier: 0, domain: math, requires: []}
- {id: complex_numbers, label: Complex numbers, aliases: [phasors, imaginary numbers], tier: 0, domain: math, requires: [algebra_manipulation]}
- {id: calculus_derivatives, label: Derivatives, tier: 0, domain: math, requires: [algebra_manipulation]}
- {id: calculus_integrals, label: Integrals, tier: 0, domain: math, requires: [calculus_derivatives]}
- {id: differential_equations, label: Differential equations, aliases: [ODEs], tier: 0, domain: math, requires: [calculus_integrals]}
- {id: linear_algebra_basics, label: Vectors and matrices, tier: 0, domain: math, requires: [algebra_manipulation]}
- {id: probability_basics, label: Probability, tier: 0, domain: math, requires: [algebra_manipulation]}
- {id: statistics_basics, label: Descriptive statistics, aliases: [mean, standard deviation], tier: 0, domain: math, requires: [probability_basics]}
- {id: binary_numbers, label: Binary and hexadecimal, aliases: [base 2, hex, radix], tier: 0, domain: digital, requires: []}
- {id: boolean_algebra, label: Boolean algebra, tier: 0, domain: digital, requires: [binary_numbers]}
- {id: charge_current_voltage, label: Charge, current and voltage, tier: 0, domain: electrical, requires: []}
- {id: energy_power, label: Energy and power, tier: 0, domain: electrical, requires: [charge_current_voltage]}
```

## 3.2 Tier 1 — electrical foundations (24)

```yaml
- {id: ohms_law, label: Ohm's law, tier: 1, domain: electrical, requires: [charge_current_voltage], verify: "predict current through a known resistor and measure it"}
- {id: kirchhoff_laws, label: Kirchhoff's laws, aliases: [KCL, KVL], tier: 1, domain: electrical, requires: [ohms_law]}
- {id: series_parallel, label: Series and parallel networks, tier: 1, domain: electrical, requires: [kirchhoff_laws]}
- {id: voltage_divider, label: Voltage divider, tier: 1, domain: electrical, requires: [series_parallel], verify: "design a divider for a target voltage and measure the error"}
- {id: current_divider, label: Current divider, tier: 1, domain: electrical, requires: [series_parallel]}
- {id: thevenin_norton, label: Thévenin and Norton equivalents, tier: 1, domain: electrical, requires: [series_parallel]}
- {id: capacitance, label: Capacitance, tier: 1, domain: electrical, requires: [charge_current_voltage, calculus_derivatives]}
- {id: inductance, label: Inductance, tier: 1, domain: electrical, requires: [charge_current_voltage, calculus_derivatives]}
- {id: rc_circuit, label: RC circuits and time constants, aliases: [RC time constant, tau], tier: 1, domain: electrical, requires: [capacitance, ohms_law], verify: "predict settling time and confirm on a scope"}
- {id: rl_circuit, label: RL circuits, tier: 1, domain: electrical, requires: [inductance, ohms_law]}
- {id: impedance, label: Impedance, aliases: [Z, complex impedance], tier: 1, domain: electrical, requires: [capacitance, inductance, complex_numbers]}
- {id: ac_analysis, label: AC circuit analysis, aliases: [sinusoidal steady state], tier: 1, domain: electrical, requires: [impedance]}
- {id: frequency_response, label: Frequency response, aliases: [Bode plot], tier: 1, domain: electrical, requires: [ac_analysis]}
- {id: resonance, label: Resonance, tier: 1, domain: electrical, requires: [ac_analysis]}
- {id: diode, label: Diodes, tier: 1, domain: electrical, requires: [ohms_law]}
- {id: bjt, label: Bipolar transistors, aliases: [BJT], tier: 1, domain: electrical, requires: [diode]}
- {id: mosfet, label: MOSFETs, tier: 1, domain: electrical, requires: [diode]}
- {id: opamp_ideal, label: Ideal op-amp, tier: 1, domain: electrical, requires: [kirchhoff_laws]}
- {id: opamp_amplifier, label: Op-amp amplifier configurations, aliases: [inverting amp, non-inverting amp], tier: 1, domain: electrical, requires: [opamp_ideal], verify: "build a known-gain amplifier and measure gain error"}
- {id: opamp_nonideal, label: Op-amp non-idealities, aliases: [offset voltage, slew rate, GBW], tier: 1, domain: electrical, requires: [opamp_amplifier, frequency_response]}
- {id: noise_sources, label: Electronic noise, aliases: [thermal noise, Johnson noise, shot noise], tier: 1, domain: electrical, requires: [statistics_basics, ohms_law]}
- {id: snr, label: Signal-to-noise ratio, aliases: [SNR], tier: 1, domain: electrical, requires: [noise_sources]}
- {id: grounding, label: Grounding and ground loops, tier: 1, domain: electrical, requires: [kirchhoff_laws]}
- {id: decoupling, label: Decoupling and bypass capacitors, tier: 1, domain: electrical, requires: [capacitance, grounding], verify: "show supply ripple before and after adding decoupling"}
```

## 3.3 Tier 1 — digital foundations (14)

```yaml
- {id: logic_gates, label: Logic gates, tier: 1, domain: digital, requires: [boolean_algebra]}
- {id: combinational_logic, label: Combinational logic, tier: 1, domain: digital, requires: [logic_gates]}
- {id: flip_flops, label: Flip-flops and latches, tier: 1, domain: digital, requires: [logic_gates]}
- {id: sequential_logic, label: Sequential logic, tier: 1, domain: digital, requires: [flip_flops]}
- {id: clock_signals, label: Clocks and timing, aliases: [clock, oscillator], tier: 1, domain: digital, requires: [sequential_logic]}
- {id: setup_hold, label: Setup and hold time, tier: 1, domain: digital, requires: [clock_signals]}
- {id: state_machines, label: Finite state machines, aliases: [FSM], tier: 1, domain: digital, requires: [sequential_logic]}
- {id: digital_io, label: Digital I/O and logic levels, aliases: [GPIO levels, TTL, CMOS levels], tier: 1, domain: digital, requires: [logic_gates, mosfet]}
- {id: pull_resistors, label: Pull-up and pull-down resistors, tier: 1, domain: digital, requires: [digital_io, voltage_divider]}
- {id: open_drain, label: Open-drain outputs, tier: 1, domain: digital, requires: [pull_resistors]}
- {id: level_shifting, label: Logic level shifting, tier: 1, domain: digital, requires: [digital_io]}
- {id: serial_vs_parallel, label: Serial vs parallel transmission, tier: 1, domain: digital, requires: [digital_io]}
- {id: two_complement, label: Two's complement, tier: 1, domain: digital, requires: [binary_numbers]}
- {id: fixed_point, label: Fixed-point arithmetic, aliases: [Q format, Q15], tier: 1, domain: digital, requires: [two_complement]}
```

## 3.4 Tier 2 — programming for embedded (22)

```yaml
- {id: c_syntax, label: C syntax and control flow, tier: 2, domain: programming, requires: []}
- {id: c_types, label: C types and sizes, aliases: [stdint, uint8_t], tier: 2, domain: programming, requires: [c_syntax, binary_numbers]}
- {id: pointers, label: Pointers, tier: 2, domain: programming, requires: [c_types]}
- {id: memory_layout, label: Stack, heap and static memory, tier: 2, domain: programming, requires: [pointers]}
- {id: structs_unions, label: Structs and unions, tier: 2, domain: programming, requires: [pointers]}
- {id: bit_manipulation, label: Bit manipulation, aliases: [bitmask, shifting], tier: 2, domain: programming, requires: [c_types, boolean_algebra], verify: "set and clear a specific register bit without disturbing others"}
- {id: volatile_keyword, label: volatile and compiler barriers, tier: 2, domain: programming, requires: [memory_layout]}
- {id: register_access, label: Memory-mapped register access, tier: 2, domain: programming, requires: [bit_manipulation, volatile_keyword]}
- {id: header_files, label: Headers and linkage, tier: 2, domain: programming, requires: [c_syntax]}
- {id: build_toolchain, label: Compile, link and flash, aliases: [toolchain, gcc-arm], tier: 2, domain: programming, requires: [header_files]}
- {id: makefiles, label: Build systems, aliases: [Make, CMake, PlatformIO], tier: 2, domain: programming, requires: [build_toolchain]}
- {id: linker_script, label: Linker scripts and memory maps, tier: 2, domain: programming, requires: [build_toolchain, memory_layout]}
- {id: startup_code, label: Startup code and vector table, tier: 2, domain: programming, requires: [linker_script]}
- {id: version_control, label: Version control, aliases: [git], tier: 2, domain: programming, requires: []}
- {id: dynamic_allocation_risk, label: Why malloc is avoided in embedded, tier: 2, domain: programming, requires: [memory_layout]}
- {id: static_allocation, label: Static allocation patterns, tier: 2, domain: programming, requires: [dynamic_allocation_risk]}
- {id: ring_buffer, label: Ring buffers, aliases: [circular buffer, FIFO], tier: 2, domain: programming, requires: [structs_unions, static_allocation], verify: "implement one and prove it survives overflow"}
- {id: state_machine_code, label: State machines in code, tier: 2, domain: programming, requires: [state_machines, structs_unions]}
- {id: unit_testing_embedded, label: Testing embedded code, aliases: [Unity, host-side tests], tier: 2, domain: programming, requires: [build_toolchain]}
- {id: hal_abstraction, label: Hardware abstraction layers, aliases: [HAL], tier: 2, domain: programming, requires: [register_access, header_files]}
- {id: undefined_behaviour, label: Undefined behaviour, tier: 2, domain: programming, requires: [pointers]}
- {id: endianness, label: Endianness, tier: 2, domain: programming, requires: [c_types]}
```

## 3.5 Tier 2 — microcontroller core (18)

```yaml
- {id: mcu_architecture, label: Microcontroller architecture, aliases: [MCU], tier: 2, domain: mcu, requires: [sequential_logic, memory_layout]}
- {id: harvard_von_neumann, label: Harvard vs von Neumann, tier: 2, domain: mcu, requires: [mcu_architecture]}
- {id: instruction_cycle, label: Fetch-decode-execute, tier: 2, domain: mcu, requires: [mcu_architecture, clock_signals]}
- {id: clock_tree, label: Clock configuration and PLLs, aliases: [PLL, clock tree], tier: 2, domain: mcu, requires: [clock_signals, mcu_architecture], verify: "set the core clock to a target frequency and confirm on a scope pin"}
- {id: gpio, label: GPIO configuration, tier: 2, domain: mcu, requires: [digital_io, register_access], verify: "blink an LED at a measured frequency"}
- {id: interrupts, label: Interrupts, aliases: [ISR, IRQ], tier: 2, domain: mcu, requires: [instruction_cycle, register_access], verify: "trigger an ISR from a pin edge and confirm latency"}
- {id: interrupt_priority, label: Interrupt priority and nesting, aliases: [NVIC], tier: 2, domain: mcu, requires: [interrupts]}
- {id: isr_safety, label: ISR-safe code, aliases: [reentrancy, atomic access], tier: 2, domain: mcu, requires: [interrupts]}
- {id: timers, label: Hardware timers, tier: 2, domain: mcu, requires: [clock_tree, register_access]}
- {id: timer_capture, label: Input capture, tier: 2, domain: mcu, requires: [timers, interrupts]}
- {id: pwm, label: PWM generation, aliases: [pulse width modulation, duty cycle], tier: 2, domain: mcu, requires: [timers], verify: "generate a target duty cycle and measure average voltage"}
- {id: watchdog, label: Watchdog timers, tier: 2, domain: mcu, requires: [timers]}
- {id: dma, label: DMA, aliases: [direct memory access], tier: 2, domain: mcu, requires: [interrupts]}
- {id: low_power_modes, label: Sleep and low-power modes, tier: 2, domain: mcu, requires: [clock_tree, interrupts]}
- {id: flash_vs_ram, label: Flash vs RAM constraints, tier: 2, domain: mcu, requires: [mcu_architecture]}
- {id: nvm_storage, label: Non-volatile storage, aliases: [EEPROM, flash writes], tier: 2, domain: mcu, requires: [flash_vs_ram]}
- {id: bootloader, label: Bootloaders and firmware update, aliases: [DFU, OTA], tier: 2, domain: mcu, requires: [startup_code, nvm_storage]}
- {id: brownout_reset, label: Brownout and reset sources, tier: 2, domain: mcu, requires: [mcu_architecture, power_supply_basics]}
```

## 3.6 Tier 2 — communication (17)

```yaml
- {id: uart, label: UART, aliases: [serial, RS-232, TTL serial], tier: 2, domain: comms, requires: [serial_vs_parallel, timers], verify: "send a known byte and read it correctly at a set baud rate"}
- {id: baud_rate, label: Baud rate and framing errors, tier: 2, domain: comms, requires: [uart]}
- {id: i2c, label: I²C, aliases: [I2C, IIC, TWI, Inter-Integrated Circuit], tier: 2, domain: comms, requires: [serial_vs_parallel, open_drain, clock_signals], verify: "read a known register from a real device and match the datasheet default"}
- {id: i2c_addressing, label: I²C addressing and ACK/NACK, tier: 2, domain: comms, requires: [i2c]}
- {id: i2c_pullups, label: I²C pull-up sizing, tier: 2, domain: comms, requires: [i2c, rc_circuit]}
- {id: i2c_clock_stretching, label: Clock stretching, tier: 2, domain: comms, requires: [i2c]}
- {id: spi, label: SPI, aliases: [Serial Peripheral Interface], tier: 2, domain: comms, requires: [serial_vs_parallel, clock_signals]}
- {id: spi_modes, label: SPI clock polarity and phase, aliases: [CPOL, CPHA], tier: 2, domain: comms, requires: [spi, setup_hold]}
- {id: can_bus, label: CAN bus, tier: 2, domain: comms, requires: [serial_vs_parallel, differential_signalling]}
- {id: differential_signalling, label: Differential signalling, tier: 2, domain: comms, requires: [digital_io, noise_sources]}
- {id: usb_basics, label: USB device basics, tier: 3, domain: comms, requires: [serial_vs_parallel, interrupts]}
- {id: protocol_framing, label: Protocol framing, aliases: [start byte, length, checksum], tier: 2, domain: comms, requires: [uart, ring_buffer]}
- {id: checksums_crc, label: Checksums and CRC, tier: 2, domain: comms, requires: [bit_manipulation]}
- {id: bit_banging, label: Bit-banging a protocol, tier: 3, domain: comms, requires: [gpio, timers, i2c]}
- {id: logic_analyzer_use, label: Reading a bus with a logic analyzer, tier: 2, domain: tooling, requires: [i2c, spi], verify: "capture a transaction and decode it against the datasheet"}
- {id: bus_arbitration, label: Bus arbitration and collisions, tier: 3, domain: comms, requires: [i2c, can_bus]}
- {id: interface_selection, label: Choosing an interface, tier: 3, domain: comms, requires: [i2c, spi, uart]}
```

## 3.7 Tier 2–3 — analog, sensing, signals (26)

```yaml
- {id: adc, label: Analog-to-digital conversion, aliases: [ADC], tier: 2, domain: analog, requires: [digital_io, ac_analysis], verify: "convert a known DC voltage and compute the error in LSBs"}
- {id: adc_resolution, label: ADC resolution and LSB size, tier: 2, domain: analog, requires: [adc]}
- {id: adc_reference, label: ADC reference voltage, aliases: [Vref], tier: 2, domain: analog, requires: [adc], verify: "show how a changing rail shifts a reading when Vref is tied to VDD"}
- {id: adc_input_impedance, label: ADC input impedance and settling, tier: 3, domain: analog, requires: [adc, rc_circuit]}
- {id: sampling_theorem, label: Nyquist sampling theorem, aliases: [Nyquist, sampling rate], tier: 2, domain: dsp, requires: [frequency_response, adc]}
- {id: aliasing, label: Aliasing, tier: 2, domain: dsp, requires: [sampling_theorem], verify: "sample a tone above Nyquist and show the false frequency"}
- {id: anti_alias_filter, label: Anti-aliasing filters, tier: 3, domain: dsp, requires: [aliasing, analog_filter]}
- {id: quantization_noise, label: Quantisation noise, tier: 3, domain: dsp, requires: [adc_resolution, noise_sources]}
- {id: dac, label: Digital-to-analog conversion, aliases: [DAC], tier: 2, domain: analog, requires: [adc]}
- {id: analog_filter, label: Passive analog filters, aliases: [RC filter, low-pass], tier: 2, domain: analog, requires: [rc_circuit, frequency_response]}
- {id: active_filter, label: Active filters, tier: 3, domain: analog, requires: [analog_filter, opamp_amplifier]}
- {id: instrumentation_amp, label: Instrumentation amplifier, tier: 3, domain: analog, requires: [opamp_amplifier, differential_signalling]}
- {id: sensor_interfacing, label: Sensor interfacing, tier: 2, domain: sensing, requires: [adc, i2c]}
- {id: sensor_calibration, label: Sensor calibration, aliases: [two-point calibration, offset and gain], tier: 3, domain: sensing, requires: [sensor_interfacing, statistics_basics], verify: "calibrate against a known reference and report residual error"}
- {id: sensor_drift, label: Sensor drift and temperature dependence, tier: 3, domain: sensing, requires: [sensor_calibration]}
- {id: wheatstone_bridge, label: Wheatstone bridge, tier: 3, domain: sensing, requires: [voltage_divider, instrumentation_amp]}
- {id: thermistor, label: Thermistors and RTDs, tier: 3, domain: sensing, requires: [wheatstone_bridge, sensor_calibration]}
- {id: strain_gauge, label: Strain gauges, tier: 3, domain: sensing, requires: [wheatstone_bridge]}
- {id: imu_basics, label: Accelerometers and gyroscopes, aliases: [IMU], tier: 3, domain: sensing, requires: [sensor_calibration]}
- {id: sensor_fusion, label: Sensor fusion, aliases: [complementary filter, Kalman], tier: 4, domain: sensing, requires: [imu_basics, digital_filter, linear_algebra_basics]}
- {id: digital_filter, label: Digital filters, aliases: [FIR, IIR], tier: 3, domain: dsp, requires: [sampling_theorem, fixed_point]}
- {id: moving_average, label: Moving average filter, tier: 2, domain: dsp, requires: [ring_buffer, statistics_basics]}
- {id: fft, label: FFT and spectral analysis, aliases: [DFT, Fourier transform], tier: 3, domain: dsp, requires: [sampling_theorem, complex_numbers]}
- {id: windowing, label: Windowing and spectral leakage, tier: 4, domain: dsp, requires: [fft]}
- {id: dsp_fixed_point_scaling, label: Fixed-point scaling in DSP, aliases: [Q15 scaling, saturation], tier: 4, domain: dsp, requires: [digital_filter]}
- {id: oversampling, label: Oversampling and decimation, tier: 4, domain: dsp, requires: [sampling_theorem, adc_resolution]}
```

## 3.8 Tier 2–3 — power (14)

```yaml
- {id: power_supply_basics, label: Power supply fundamentals, tier: 2, domain: power, requires: [energy_power, ohms_law]}
- {id: linear_regulator, label: Linear regulators, aliases: [LDO], tier: 2, domain: power, requires: [power_supply_basics], verify: "measure dropout and thermal rise at a known load"}
- {id: switching_regulator, label: Switching regulators, aliases: [buck, boost, SMPS], tier: 3, domain: power, requires: [power_supply_basics, inductance, pwm]}
- {id: regulator_efficiency, label: Regulator efficiency, tier: 3, domain: power, requires: [linear_regulator, switching_regulator]}
- {id: supply_ripple, label: Supply ripple and noise, tier: 3, domain: power, requires: [switching_regulator, decoupling, noise_sources]}
- {id: current_budget, label: Current budgeting, tier: 2, domain: power, requires: [power_supply_basics], verify: "predict total draw from datasheets, then measure it"}
- {id: battery_chemistry, label: Battery chemistry and capacity, aliases: [LiPo, mAh], tier: 2, domain: power, requires: [energy_power]}
- {id: battery_discharge_curve, label: Discharge curves and cutoff, tier: 3, domain: power, requires: [battery_chemistry]}
- {id: battery_life_estimation, label: Battery life estimation, tier: 3, domain: power, requires: [current_budget, battery_discharge_curve, low_power_modes], verify: "predict runtime, then run it flat and compare"}
- {id: duty_cycling, label: Duty cycling for power saving, tier: 3, domain: power, requires: [battery_life_estimation]}
- {id: inrush_current, label: Inrush current, tier: 3, domain: power, requires: [capacitance, power_supply_basics]}
- {id: reverse_polarity_protection, label: Reverse polarity protection, tier: 3, domain: power, requires: [mosfet]}
- {id: thermal_management, label: Thermal considerations, tier: 3, domain: power, requires: [linear_regulator]}
- {id: power_sequencing, label: Power-up sequencing, tier: 4, domain: power, requires: [brownout_reset]}
```

## 3.9 Tier 3 — concurrency and RTOS (13)

```yaml
- {id: superloop, label: Super-loop architecture, aliases: [main loop, bare metal], tier: 2, domain: rtos, requires: [state_machine_code, interrupts]}
- {id: blocking_vs_nonblocking, label: Blocking vs non-blocking code, tier: 2, domain: rtos, requires: [superloop], verify: "show a blocking delay causing a missed event, then fix it"}
- {id: cooperative_scheduling, label: Cooperative scheduling, tier: 3, domain: rtos, requires: [blocking_vs_nonblocking, timers]}
- {id: rtos_basics, label: RTOS concepts, aliases: [FreeRTOS, Zephyr], tier: 3, domain: rtos, requires: [cooperative_scheduling, memory_layout]}
- {id: tasks_threads, label: Tasks and context switching, tier: 3, domain: rtos, requires: [rtos_basics]}
- {id: preemption, label: Preemptive scheduling and priorities, tier: 3, domain: rtos, requires: [tasks_threads, interrupt_priority]}
- {id: race_conditions, label: Race conditions, tier: 3, domain: rtos, requires: [tasks_threads, isr_safety]}
- {id: mutex_semaphore, label: Mutexes and semaphores, tier: 3, domain: rtos, requires: [race_conditions]}
- {id: priority_inversion, label: Priority inversion, tier: 4, domain: rtos, requires: [mutex_semaphore, preemption]}
- {id: queues_ipc, label: Queues and inter-task messaging, tier: 3, domain: rtos, requires: [tasks_threads, ring_buffer]}
- {id: stack_sizing, label: Per-task stack sizing, tier: 4, domain: rtos, requires: [tasks_threads]}
- {id: real_time_deadlines, label: Real-time deadlines and jitter, tier: 4, domain: rtos, requires: [preemption, timer_capture], verify: "measure worst-case response over 10k events"}
- {id: wcet, label: Worst-case execution time, aliases: [WCET], tier: 4, domain: rtos, requires: [real_time_deadlines]}
```

## 3.10 Tier 2–3 — debugging and tooling (13)

```yaml
- {id: multimeter_use, label: Using a multimeter, tier: 1, domain: tooling, requires: [ohms_law]}
- {id: oscilloscope_use, label: Using an oscilloscope, tier: 2, domain: tooling, requires: [ac_analysis], verify: "capture a signal and correctly report its frequency and amplitude"}
- {id: scope_triggering, label: Scope triggering, tier: 2, domain: tooling, requires: [oscilloscope_use]}
- {id: probe_loading, label: Probe loading and bandwidth, tier: 3, domain: tooling, requires: [oscilloscope_use]}
- {id: printf_debugging, label: Debug output over serial, tier: 2, domain: tooling, requires: [uart]}
- {id: debugger_swd, label: On-chip debugging, aliases: [SWD, JTAG, breakpoints], tier: 2, domain: tooling, requires: [build_toolchain, mcu_architecture]}
- {id: reading_datasheet, label: Reading a datasheet, tier: 2, domain: tooling, requires: [register_access], verify: "find a register's reset value and confirm it on hardware"}
- {id: errata_reading, label: Reading errata, tier: 3, domain: tooling, requires: [reading_datasheet]}
- {id: hardware_bringup, label: Board bring-up procedure, tier: 3, domain: tooling, requires: [multimeter_use, power_supply_basics, gpio]}
- {id: fault_isolation, label: Isolating a fault, aliases: [bisection debugging], tier: 3, domain: tooling, requires: [hardware_bringup, oscilloscope_use]}
- {id: hardfault_debug, label: Debugging hard faults, tier: 3, domain: tooling, requires: [debugger_swd, memory_layout]}
- {id: reproducing_bugs, label: Reproducing intermittent faults, tier: 4, domain: tooling, requires: [fault_isolation, statistics_basics]}
- {id: instrumented_logging, label: Timestamped logging, tier: 3, domain: tooling, requires: [printf_debugging, timers]}
```

## 3.11 Tier 3–4 — hardware build (10)

```yaml
- {id: breadboarding, label: Breadboard prototyping, tier: 1, domain: hardware, requires: [series_parallel]}
- {id: soldering, label: Soldering, tier: 2, domain: hardware, requires: []}
- {id: schematic_capture, label: Schematic capture, aliases: [KiCad, EDA], tier: 3, domain: hardware, requires: [series_parallel, reading_datasheet]}
- {id: pcb_layout, label: PCB layout, tier: 3, domain: hardware, requires: [schematic_capture, grounding]}
- {id: trace_width, label: Trace width and current capacity, tier: 4, domain: hardware, requires: [pcb_layout, energy_power]}
- {id: ground_plane, label: Ground planes and return paths, tier: 4, domain: hardware, requires: [pcb_layout]}
- {id: emi_basics, label: EMI and signal integrity, tier: 4, domain: hardware, requires: [ground_plane, differential_signalling]}
- {id: connector_selection, label: Connectors and mechanical interface, tier: 3, domain: hardware, requires: [schematic_capture]}
- {id: enclosure_basics, label: Enclosures and mounting, tier: 3, domain: hardware, requires: []}
- {id: bom_sourcing, label: BOM and component sourcing, tier: 3, domain: hardware, requires: [schematic_capture]}
```

## 3.12 Tier 3–4 — wireless and connectivity (8)

```yaml
- {id: rf_basics, label: RF fundamentals, tier: 4, domain: wireless, requires: [resonance]}
- {id: antenna_basics, label: Antennas and matching, tier: 4, domain: wireless, requires: [rf_basics]}
- {id: ble, label: Bluetooth Low Energy, aliases: [BLE], tier: 3, domain: wireless, requires: [protocol_framing, interrupts]}
- {id: ble_gatt, label: GATT services and characteristics, tier: 4, domain: wireless, requires: [ble]}
- {id: wifi_embedded, label: Wi-Fi on embedded, tier: 3, domain: wireless, requires: [protocol_framing, current_budget]}
- {id: mqtt, label: MQTT, tier: 3, domain: wireless, requires: [wifi_embedded]}
- {id: lora, label: LoRa and low-power WAN, tier: 4, domain: wireless, requires: [rf_basics, duty_cycling]}
- {id: wireless_power_cost, label: Power cost of radio, tier: 3, domain: wireless, requires: [ble, current_budget], verify: "measure average current with the radio on vs duty-cycled"}
```

## 3.13 Tier 3–4 — control (8)

```yaml
- {id: open_loop_control, label: Open-loop control, tier: 2, domain: control, requires: [pwm]}
- {id: feedback_control, label: Closed-loop feedback, tier: 3, domain: control, requires: [open_loop_control, sensor_interfacing]}
- {id: pid_control, label: PID control, aliases: [PID, proportional integral derivative], tier: 3, domain: control, requires: [feedback_control, calculus_integrals], verify: "tune to a step response spec and measure overshoot and settling time"}
- {id: pid_tuning, label: PID tuning methods, aliases: [Ziegler-Nichols], tier: 3, domain: control, requires: [pid_control]}
- {id: integral_windup, label: Integral windup, tier: 4, domain: control, requires: [pid_control]}
- {id: control_stability, label: Stability and phase margin, tier: 4, domain: control, requires: [pid_control, frequency_response]}
- {id: motor_drive, label: Motor driving, aliases: [H-bridge], tier: 3, domain: control, requires: [pwm, mosfet]}
- {id: encoder_feedback, label: Encoders and closed-loop position, tier: 3, domain: control, requires: [timer_capture, feedback_control]}
```

## 3.14 Tier 4 — bioinstrumentation *(the demo path)* (8)

```yaml
- {id: bioimpedance, label: Bioimpedance, aliases: [BIA, body impedance], tier: 4, domain: bio, requires: [impedance, sensor_interfacing]}
- {id: electrode_skin_interface, label: Electrode-skin interface, aliases: [contact impedance], tier: 4, domain: bio, requires: [bioimpedance]}
- {id: eis, label: Electrochemical impedance spectroscopy, aliases: [EIS], tier: 4, domain: bio, requires: [bioimpedance, frequency_response, fft]}
- {id: four_wire_measurement, label: Four-wire (Kelvin) measurement, tier: 4, domain: bio, requires: [electrode_skin_interface, instrumentation_amp]}
- {id: biosignal_noise, label: Biosignal noise and motion artefact, tier: 4, domain: bio, requires: [snr, electrode_skin_interface]}
- {id: mains_interference, label: 50/60 Hz mains interference, tier: 4, domain: bio, requires: [biosignal_noise, digital_filter]}
- {id: patient_isolation, label: Electrical isolation and safety, tier: 4, domain: bio, requires: [power_supply_basics, biosignal_noise]}
- {id: physiological_validation, label: Validating against a physiological reference, tier: 4, domain: bio, requires: [sensor_calibration, statistics_basics], verify: "correlate against an accepted reference method and report r and n"}
```

## 3.15 Tier 4 — edge ML *(the second-project path)* (6)

```yaml
- {id: feature_extraction, label: Feature extraction from sensor data, tier: 4, domain: ml, requires: [digital_filter, statistics_basics]}
- {id: model_quantization, label: Model quantisation, aliases: [int8 quantization], tier: 4, domain: ml, requires: [fixed_point, feature_extraction]}
- {id: tflite_micro, label: Inference on microcontrollers, aliases: [TFLite Micro, TinyML], tier: 4, domain: ml, requires: [model_quantization, flash_vs_ram]}
- {id: inference_latency, label: Inference latency budgeting, tier: 4, domain: ml, requires: [tflite_micro, real_time_deadlines], verify: "measure per-inference time and compare to the deadline"}
- {id: train_test_split, label: Train/test discipline, tier: 4, domain: ml, requires: [statistics_basics]}
- {id: overfitting_small_data, label: Overfitting on small datasets, tier: 4, domain: ml, requires: [train_test_split]}
```

**Total: 213 concepts.**

---

# 4. Cross-domain bridges — the crossover seeds

These are `relates_to`, **not** `requires`. They exist so the crossover detector (01 §13.11) has real structure to find rather than inventing it:

```yaml
bridges:
  - {a: fixed_point, b: model_quantization, why: "both trade dynamic range for hardware speed"}
  - {a: digital_filter, b: feature_extraction, why: "same convolution maths, different intent"}
  - {a: impedance, b: bioimpedance, why: "the same measurement applied to tissue"}
  - {a: pid_control, b: duty_cycling, why: "both regulate a quantity by modulating on-time"}
  - {a: ring_buffer, b: queues_ipc, why: "producer-consumer decoupling at two layers"}
  - {a: sensor_calibration, b: train_test_split, why: "both guard against fitting your own reference"}
  - {a: snr, b: overfitting_small_data, why: "both are about mistaking noise for signal"}
  - {a: real_time_deadlines, b: inference_latency, why: "identical budget, different consumer"}
```

That last pair is the biosensor→robotics continuity story made concrete: a student who understands deadlines in an RTOS already holds most of what inference budgeting requires.

---

# 5. Review protocol for the ECE teammate

Do **not** read this end to end. Work in this order:

1. **Direction check (highest value).** For every `requires`, ask: *"could a competent student learn A without B?"* If yes, delete the edge. **False prerequisites are the damaging error** — they make the frontier engine tell students to go backwards, which is exactly the experience that gets a tutoring product abandoned.
2. **Aliases.** Add every name you have ever heard used. This is the cheapest possible defence against entity fragmentation (05 §1.2) and the one place where five minutes of your time is worth the most.
3. **`verify` fields.** Only 34 of 187 have one. Fill in as many as you can, especially tiers 2–3. A concept with a `verify` can be *proved* known; one without can only be *claimed* known.
4. **Missing concepts.** What would a student on your project hit in week 3 that isn't here?
5. **Tier sanity.** Only affects zoom labels and layout, not logic. Lowest priority.

**Known gaps I'm aware of:** no automotive/industrial (CAN is a stub), no FPGA/HDL, no safety certification, no security/crypto (secure boot, TLS on embedded), thin on mechanical, thin on manufacturing/DFM.

---

# 6. Validation — CI must enforce

```python
def validate_skeleton(concepts: list[dict]) -> list[str]:
    errs = []
    ids = {c["id"] for c in concepts}
    if len(ids) != len(concepts):
        errs.append("duplicate ids")
    for c in concepts:
        for r in c.get("requires", []):
            if r not in ids:
                errs.append(f"{c['id']} requires unknown {r}")
    # ⭐ a cycle makes the outer fringe empty and the frontier engine
    #    silently returns nothing — fail loudly instead
    g = nx.DiGraph((c["id"], r) for c in concepts for r in c.get("requires", []))
    if not nx.is_directed_acyclic_graph(g):
        errs.append(f"cycles: {list(nx.simple_cycles(g))[:5]}")
    # redundant transitive edges corrupt fringe computation
    tr = nx.transitive_reduction(g)
    for u, v in g.edges():
        if not tr.has_edge(u, v):
            errs.append(f"redundant transitive edge {u} -> {v}")
    for c in concepts:
        if len(c.get("requires", [])) > 5:
            errs.append(f"{c['id']} has >5 prerequisites — consider splitting")
    return errs
```

---

# 7. How this gets used

**Ingest.** Loaded as global `Concept` nodes with `project_id: null` and `requires` edges at `confidence: EXTRACTED, score: 1.0` — authored by a human, not inferred.

**Transcript mapping** (04 §6.5). A passed course maps to Concepts with **confidence, not certainty**: `taught_by` edges scaled by grade and decayed by `valid_from`. **A course is evidence of exposure, not knowledge.** These never enter the knowledge state directly.

**Knowledge state.** A Concept enters `K` only when a `Claim(conclusion)` or an `Artifact(agreement=matched)` validates it. That predicate is the entire interface between this file and Knowledge Space Theory (04 §1.1).

**Frontier.**
```
outer_fringe = { c ∉ K : all requires(c) ⊆ K }
```
Ranked by information gain per unit effort (08 §8).

**Semantic zoom.** `domain` supplies the tier-1 label, `tier` decides at what zoom a node's label appears.

---

# 💡 Visionary Vector — `verify` is a curriculum in disguise

Only 34 of 213 concepts currently carry a `verify` string, and it's tempting to treat that field as documentation — a nice-to-have hint about what mastery means.

It's the most consequential field in the file, and finishing it changes what the product *is*.

Look at what a `verify` actually specifies: *"predict settling time and confirm on a scope"*, *"generate a target duty cycle and measure average voltage"*, *"correlate against an accepted reference and report r and n."* **Every one is a complete, falsifiable, sub-hour experiment with a predicted value and a measured value.** Which is to say: **every `verify` field is a pre-written `Artifact` template.**

Fill all 187 and we don't have documentation — we have **a library of 187 verifiable micro-experiments covering an entire domain**, each one machine-checkable, each one generating exactly the `(predicted, measured, agreement)` triple that report 07 identified as the whole asset.

Three things follow immediately:

1. **The cold-start problem inverts.** A brand-new student with an empty graph isn't stuck — the frontier engine can hand them a real fifteen-minute experiment from their outer fringe on day one, before they have a project at all.
2. **Calibration becomes measurable from the first week** rather than after months of project work, because each micro-experiment is a prediction with a known answer.
3. **It's the ideal seed for a professor.** The Chairman doc's "professors publish ideal plans" idea has never had a concrete unit before. This is it: an instructor contributes `verify` strings for their course's concepts, and their teaching intent enters every student's graph as executable experiments rather than as text.

The action is unglamorous and cheap: **make `verify` a required field.** No concept ships without an answer to *"what would prove you know this?"* — which is, not coincidentally, the same question we're teaching students to ask about their own projects.

---

*v0 ends. This file is domain property — the ECE teammate owns it from here.*

---

# v0.2 — the robotics and life-sciences packs

**Added 2026-08-13.** v0 was 213 concepts and effectively ECE-only, which
matched the first vertical and nothing else. ⚠️ Measured before writing this:
*"I want to build a robot arm"* matched **zero** concepts, and a quartz-crystal
microbalance question matched two — both generic maths. A frontier that cannot
place a student's question is a frontier that recommends nothing, and cold
start is where the product is actually won or lost.

⭐ These packs hook into the existing tiers by `requires` rather than sitting
beside them. A robotics student who already holds `pid_control` from an ECE
course should not be told to learn it again — the prerequisite edges are what
make that work, so every row below points back into v0 wherever it honestly can.

**`verify` is filled for every leaf concept**, per the v0 closing note: no
concept ships without an answer to *"what would prove you know this?"*

## Robotics — kinematics, control, ROS, perception

- {id: rigid_transforms, label: Rigid-body transforms, aliases: [SE(3), poses], tier: 2, domain: robotics, requires: [linear_algebra_basics]}
- {id: homogeneous_coords, label: Homogeneous coordinates, tier: 2, domain: robotics, requires: [rigid_transforms]}
- {id: rotation_representations, label: Rotation representations, aliases: [quaternions, euler angles], tier: 3, domain: robotics, requires: [rigid_transforms], verify: "convert the same rotation between quaternion and Euler and show gimbal lock where it occurs"}
- {id: dh_parameters, label: Denavit-Hartenberg parameters, tier: 3, domain: robotics, requires: [homogeneous_coords]}
- {id: forward_kinematics, label: Forward kinematics, aliases: [robot arm, manipulator, robotic arm], tier: 3, domain: robotics, requires: [dh_parameters], verify: "predict the end-effector pose for a known joint vector and measure it within 5 mm"}
- {id: inverse_kinematics, label: Inverse kinematics, aliases: [IK, reach a pose, pick and place], tier: 4, domain: robotics, requires: [forward_kinematics], verify: "solve IK for a reachable pose and show the solution drives the arm there"}
- {id: jacobian, label: The Jacobian, tier: 4, domain: robotics, requires: [forward_kinematics, calculus_derivatives]}
- {id: workspace_singularity, label: Workspace and singularities, tier: 4, domain: robotics, requires: [jacobian], verify: "identify a singular configuration and show the commanded joint velocity blowing up near it"}
- {id: trajectory_generation, label: Trajectory generation, aliases: [motion profiles], tier: 4, domain: robotics, requires: [inverse_kinematics, calculus_derivatives], verify: "generate a trapezoidal profile and show measured velocity matches the plan"}
- {id: joint_space_control, label: Joint-space control, tier: 4, domain: robotics, requires: [pid_control, encoder_feedback]}
- {id: task_space_control, label: Task-space control, tier: 5, domain: robotics, requires: [joint_space_control, jacobian]}
- {id: feedforward_gravity, label: Gravity and feedforward compensation, tier: 5, domain: robotics, requires: [joint_space_control], verify: "show steady-state error falling when the gravity term is added"}
- {id: actuator_sizing, label: Actuator sizing, aliases: [torque-speed curve], tier: 3, domain: robotics, requires: [motor_drive], verify: "compute required torque at worst-case reach and show the chosen motor meets it with margin"}
- {id: gearing_backlash, label: Gearing and backlash, tier: 3, domain: robotics, requires: [actuator_sizing], verify: "measure backlash by reversing direction and reading the encoder deadband"}
- {id: servo_stepper_choice, label: Servo vs stepper selection, tier: 3, domain: robotics, requires: [actuator_sizing, motor_drive]}
- {id: realtime_control_loop, label: Real-time control loop timing, tier: 4, domain: robotics, requires: [pid_control, interrupts], verify: "log loop jitter over 10 000 cycles and show it inside the deadline"}
- {id: odometry, label: Wheel and joint odometry, tier: 3, domain: robotics, requires: [encoder_feedback], verify: "drive a known 2 m path and report accumulated position error"}
- {id: imu_basics, label: IMU basics, aliases: [accelerometer, gyroscope], tier: 3, domain: robotics, requires: [sensor_interfacing, snr]}
- {id: complementary_filter, label: Complementary filter, tier: 4, domain: robotics, requires: [imu_basics, digital_filter], verify: "show tilt estimate drift falling versus gyro-only integration"}
- {id: kalman_filter, label: Kalman filtering, tier: 5, domain: robotics, requires: [imu_basics, probability_basics, linear_algebra_basics], verify: "show the estimate tracking ground truth with covariance behaving as predicted"}
- {id: sensor_fusion, label: Sensor fusion, tier: 5, domain: robotics, requires: [complementary_filter]}
- {id: ros_nodes_topics, label: ROS nodes and topics, tier: 2, domain: robotics, requires: [version_control], verify: "publish and subscribe between two nodes and show the message rate"}
- {id: ros_services_actions, label: ROS services and actions, tier: 3, domain: robotics, requires: [ros_nodes_topics]}
- {id: tf_tree, label: The TF transform tree, tier: 3, domain: robotics, requires: [ros_nodes_topics, rigid_transforms], verify: "show a correctly connected TF tree with no unpublished frames"}
- {id: urdf_modelling, label: URDF robot description, tier: 3, domain: robotics, requires: [tf_tree, forward_kinematics]}
- {id: sim_to_real, label: Simulation-to-real gap, tier: 5, domain: robotics, requires: [urdf_modelling], verify: "run the same controller in sim and on hardware and report where they diverge"}
- {id: occupancy_grid, label: Occupancy grids, tier: 4, domain: robotics, requires: [probability_basics]}
- {id: lidar_processing, label: Lidar range processing, tier: 4, domain: robotics, requires: [sensor_interfacing, snr], verify: "show false-return rate against a known obstacle at three distances"}
- {id: point_cloud_registration, label: Point-cloud registration, aliases: [ICP], tier: 5, domain: robotics, requires: [lidar_processing, rigid_transforms]}
- {id: path_planning, label: Path planning, aliases: [A*, RRT, navigation, obstacle avoidance], tier: 4, domain: robotics, requires: [occupancy_grid], verify: "show a planned path avoiding a mapped obstacle and its length versus straight line"}
- {id: collision_checking, label: Collision checking, tier: 4, domain: robotics, requires: [workspace_singularity, occupancy_grid]}
- {id: slam_basics, label: SLAM, tier: 5, domain: robotics, requires: [occupancy_grid, sensor_fusion], verify: "close a loop and report drift before and after correction"}
- {id: force_torque_sensing, label: Force-torque sensing, tier: 4, domain: robotics, requires: [sensor_interfacing, sensor_calibration]}
- {id: compliance_control, label: Compliance and impedance control, aliases: [gripper force, grasping], tier: 5, domain: robotics, requires: [force_torque_sensing, task_space_control], verify: "show contact force staying bounded when the arm is pushed"}
- {id: robot_safety, label: Safety, e-stop and limits, tier: 3, domain: robotics, requires: [realtime_control_loop], verify: "show the e-stop cutting drive current within the specified time"}

## Life sciences — wet lab, assays, quantification

- {id: molarity_dilution, label: Molarity and dilutions, tier: 0, domain: lifesci, requires: [algebra_manipulation], verify: "prepare a 10x dilution series and confirm concentration on a spectrophotometer"}
- {id: buffers_ph, label: Buffers and pH, tier: 1, domain: lifesci, requires: [molarity_dilution], verify: "make a buffer at a target pH and measure it within 0.1 units"}
- {id: pipetting_accuracy, label: Pipetting accuracy, tier: 1, domain: lifesci, requires: [molarity_dilution], verify: "gravimetrically check a pipette and report CV across ten draws"}
- {id: aseptic_technique, label: Aseptic technique, tier: 1, domain: lifesci, requires: [], verify: "run a blank plate alongside and show no growth"}
- {id: biosafety_levels, label: Biosafety levels and containment, tier: 1, domain: lifesci, requires: [aseptic_technique]}
- {id: sample_storage, label: Sample storage and freeze-thaw, tier: 2, domain: lifesci, requires: [aseptic_technique], verify: "compare signal from fresh versus once-thawed aliquots"}
- {id: cell_culture, label: Cell culture basics, tier: 2, domain: lifesci, requires: [aseptic_technique, buffers_ph]}
- {id: passaging, label: Passaging and confluence, tier: 2, domain: lifesci, requires: [cell_culture]}
- {id: cell_viability, label: Cell viability assays, tier: 3, domain: lifesci, requires: [cell_culture, standard_curve], verify: "show a dose-dependent drop in viability against a known cytotoxic control"}
- {id: contamination_control, label: Contamination detection, aliases: [mycoplasma], tier: 3, domain: lifesci, requires: [cell_culture], verify: "run a contamination test and report the result before using the line"}
- {id: nucleic_acid_extraction, label: Nucleic acid extraction, tier: 2, domain: lifesci, requires: [pipetting_accuracy], verify: "report yield and A260/A280 purity"}
- {id: pcr_basics, label: PCR, tier: 3, domain: lifesci, requires: [nucleic_acid_extraction], verify: "amplify a known target and show a single band at the expected size"}
- {id: primer_design, label: Primer design, tier: 3, domain: lifesci, requires: [pcr_basics], verify: "show predicted Tm and no primer-dimer in the no-template control"}
- {id: gel_electrophoresis, label: Gel electrophoresis, tier: 3, domain: lifesci, requires: [pcr_basics], verify: "size a product against a ladder within one band"}
- {id: qpcr_quantification, label: qPCR quantification, aliases: [Ct values], tier: 4, domain: lifesci, requires: [primer_design, standard_curve], verify: "show an efficiency between 90 and 110 percent on the standard curve"}
- {id: protein_expression, label: Protein expression, tier: 4, domain: lifesci, requires: [cell_culture, pcr_basics]}
- {id: sds_page, label: SDS-PAGE, tier: 3, domain: lifesci, requires: [pipetting_accuracy], verify: "resolve a known protein at the expected molecular weight"}
- {id: western_blot, label: Western blot, tier: 4, domain: lifesci, requires: [sds_page, assay_controls], verify: "show a band at the expected size that disappears in the knockdown"}
- {id: affinity_purification, label: Affinity purification, tier: 4, domain: lifesci, requires: [protein_expression, sds_page]}
- {id: elisa, label: ELISA, tier: 4, domain: lifesci, requires: [standard_curve, assay_controls], verify: "report a standard curve R-squared above 0.98 and recovery within 20 percent"}
- {id: brightfield_microscopy, label: Brightfield microscopy, tier: 2, domain: lifesci, requires: [cell_culture]}
- {id: fluorescence_microscopy, label: Fluorescence microscopy, tier: 3, domain: lifesci, requires: [brightfield_microscopy], verify: "show signal above an unstained control at the same exposure"}
- {id: immunostaining, label: Immunostaining, tier: 4, domain: lifesci, requires: [fluorescence_microscopy, assay_controls]}
- {id: image_quantification, label: Image quantification, tier: 4, domain: lifesci, requires: [fluorescence_microscopy, statistics_basics], verify: "quantify blind to condition and report the effect with n and spread"}
- {id: assay_controls, label: Positive and negative controls, tier: 2, domain: lifesci, requires: [], verify: "show the assay separating a known positive from a known negative"}
- {id: assay_replicates, label: Technical and biological replicates, tier: 3, domain: lifesci, requires: [statistics_basics, assay_controls], verify: "report both kinds of replicate separately and show which dominates the variance"}
- {id: standard_curve, label: Standard curves, tier: 3, domain: lifesci, requires: [molarity_dilution, statistics_basics], verify: "fit a curve and report the linear range you will actually work in"}
- {id: limit_of_detection, label: Limit of detection, aliases: [LOD, LOQ], tier: 4, domain: lifesci, requires: [standard_curve, snr], verify: "compute LOD from blank variance and demonstrate it on a spiked sample"}
- {id: dose_response, label: Dose-response and EC50, tier: 5, domain: lifesci, requires: [standard_curve, assay_replicates], verify: "fit EC50 with confidence intervals and state the model used"}
- {id: qcm_sensing, label: Quartz crystal microbalance, aliases: [QCM, QCM-D], tier: 5, domain: lifesci, requires: [resonance, sensor_calibration, limit_of_detection], verify: "show a frequency shift proportional to bound mass against a blank surface"}
- {id: surface_functionalisation, label: Surface functionalisation, tier: 5, domain: lifesci, requires: [qcm_sensing, assay_controls], verify: "show specific binding above a non-functionalised control surface"}
- {id: biosensor_specificity, label: Biosensor specificity, tier: 5, domain: lifesci, requires: [surface_functionalisation, assay_controls], verify: "show response to target far exceeding response to a close-matched interferent"}

*v0.2 ends. Robotics and life-sciences rows added by Claude 2026-08-13; the
domain teammates own them from here, and the `verify` column is where their
judgement matters most.*

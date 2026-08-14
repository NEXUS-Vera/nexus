# Visual System

**Frontend / 02.** Colour, encoding, typography, dark mode, accessibility.
**Governing constraint:** the force layout consumes the two most effective visual channels, so every remaining channel must be spent deliberately and in order.
**Date:** 2026-08-10

---

# 1. The constraint

> **The force-directed layout preemptively consumes spatial position (the #1 magnitude channel) and spatial region (the #1 identity channel) to express topology.**

Everything else — node type, confidence, support, corroboration, staleness, edge weight, relation class — must be encoded on **weaker channels**. There are not enough of them to be casual about it.

**Channel effectiveness, in order:**

| Magnitude | Identity |
|---|---|
| 1. spatial position ⛔ *taken* | 1. spatial region ⛔ *taken* |
| 2. length | 2. **colour hue** |
| 3. **area** | 3. **shape** — max ~5–7 forms |
| 4. **luminance / saturation** | |

**Separable vs integral:** hue and size decode independently (safe to combine); width and height fuse into one perceived area (never use as two variables).

---

# 2. The encoding matrix

## 2.1 Nodes

| Attribute | Channel | Rationale |
|---|---|---|
| **type** (6) | **hue** | best remaining identity channel |
| **importance** (DOI rank) | **area** | best remaining magnitude channel |
| **support state** | **fill style** — solid / half / hollow-dashed | fill is separable from hue and doesn't disturb perceived area |
| **confidence** | ⭐ **saturation (VSUP)** — desaturate toward neutral as confidence falls | see §3 |
| **corroboration** (0 / 1 / 2+) | **concentric inner ring**, stroke width | an inner ring encodes an ordinal without changing the outer silhouette |
| **contested** | **badge glyph** — a notch on the rim | a state this important must not rely on colour alone |
| **stale** | **badge glyph** — a small clock | ditto |
| ⭐ **single-method** *(added 2026-08-10, Backend/09 Q12)* | **badge glyph** — `◑` on the rim | ⚠️ **not** fill style — that channel is already carrying support state, and doubling it up would make two unrelated properties indistinguishable. A rim badge is the only free identity channel left, and it sits with `contested` and `stale` because it belongs to the same family: *"something about the evidence here deserves a look."* |
| **phantom** | **dashed perimeter + hollow fill** | the "Ghost Node" spec — Gestalt closure |

## 2.2 Edges

| Attribute | Channel |
|---|---|
| **weight** (distinct sources) | **line width** |
| **epistemic class** | **colour + texture** — see §4 |
| **relation type** (18) | **dash pattern**, within class |
| **confidence** | opacity floor — never below 35%, or it reads as absence |

## 2.3 What must *not* be encoded on a data channel

**Selection.** Using a fifth channel for selection falsely implies the data changed. Three safe mechanisms (`Frontend/03` §2).

**Hover.** Same reasoning — use a halo, not a colour change.

**Project membership.** ⚠️ The current design puts *projects* and *kinds* in the same hue space. **Hue can carry one categorical variable.** Projects become **spatial grouping** — soft region tinting behind clusters — which is the #1 identity channel and is otherwise unused at the group level.

---

# 3. Encoding uncertainty

## 3.1 What we're not doing, and why

| Rejected | Reason |
|---|---|
| **Blur / fuzziness** | ⛔ **artificially expands perceived node area**, corrupting the size channel — which we're using for importance |
| **Transparency** | reads as physical absence or backgrounding, not variance |
| **Error bars** | on 50 interconnected nodes: an unreadable thicket |

## 3.2 What we are doing — VSUP

**Value-Suppressing Uncertainty Palette.** As confidence falls, aggressively **desaturate toward neutral grey**.

```
EXTRACTED  1.00   full chroma      "this is stated, here, in this passage"
INFERRED   0.95 ─ 0.55   graded    chroma falls with the score
AMBIGUOUS  0.1–0.3   near-grey     visibly not a fact yet
```

This defeats the specific cognitive trap where a bright saturated node reads as *important* when it is merely *noisy*. **The interface physically prevents a student from drawing a confident conclusion from an uncertain node.**

⚠️ **VSUPs collapse** at low resolution, on uncalibrated monitors, and under colour-vision deficiency. **They must always be paired with an explicit numeric readout on inspection** — hover or selection shows `INFERRED 0.75 · 1 source · citation: present_weak`. Non-negotiable.

**Cost, stated honestly:** a low-confidence Concept and a low-confidence Source both trend grey, so *type* becomes harder to read exactly where confidence is lowest. That's the intended trade — at low confidence, "you shouldn't trust this" matters more than "what kind of thing is it."

## 3.3 HOPs — on demand only

Hypothetical Outcome Plots animate discrete draws from a distribution, converting probability into countable frequency, which humans read far better than Bayesian intervals.

⚠️ **The multiple-object-tracking limit is ~5 targets.** So HOPs are:
- **localised** — one node, never the graph
- **layout frozen** during the animation
- **on demand only** — triggered by hover or explicit selection, never ambient

Use them where a measurement has a real distribution — a sensor reading with variance across trials.

---

# 4. Contradiction, support, and absence

## 4.1 Edges — Scite's model, not Kialo's

⚠️ Kialo's strict pro/con hierarchy **breaks down in a force-directed topology** with cycles and multi-directional dependencies. Scite's three directional vectors map cleanly onto our relation classes:

| Class | Rendering | Psychology |
|---|---|---|
| **supporting** (`supports`, `evidence_for`, `confirms`, `measured_by`) | solid, **cool-toned** vector | stability |
| **contradicting** (`contradicts`, `refutes`) | ⭐ **sharp dashed / zigzag, warm high-alert** | pre-attentive **pop-out** — spotted the instant the view loads |
| **mentioning** (`relates_to`, `cites`, `references`) | thin, **low-luminance grey** | deliberately suppressed |
| **structural** (`contains`, `part_of`, `requires`) | very thin, near-background | scaffolding, not argument |

⭐ **Refutation also changes the physics.** A refuting edge introduces a small **repulsive** force between the source and what it refutes — semantic distance rendered spatially. Disagreement doesn't just look different; it *pushes apart*.

## 4.2 Absence — Ghost Nodes

⚠️ **The dangerous anti-pattern** is leaving a node blank, defaulting to zero, or omitting it. **Users read a zero as a literal measurement**, which downstream produces confident, wrong conclusions.

```
Ghost Node:  heavily dashed perimeter  +  completely hollow, transparent fill
```

This exploits **Gestalt closure** — the perceptual system registers the object as explicitly incomplete but *necessary*, rather than absent.

That's our phantom node, and it should read as **opportunity**: a slot waiting to be filled, not a hole. Practically — dashed but *bright*, and hovering shows *"nothing has validated this yet — here's the cheapest way to"*.

---

# 5. Palette

## 5.1 The brand resolution

The README specified "strictly black + orange." That cannot survive contact with six node types — **hue is our primary identity channel and there is no substitute.**

> **Resolution: orange becomes the *interface* colour precisely because it is not a *data* colour.**

Buttons, focus rings, the active tab, the capture bar, the brand mark: orange. **Nothing in the graph is orange**, so there's no collision and the brand stays intact where people actually perceive it — in the chrome.

## 5.2 Node palette — desaturated, dark-mode-safe

⚠️ Saturated colour at high luminance on dark backgrounds causes **halation** — glow that accelerates eye fatigue over the long sessions this product is for. The current set (`#3fb64f`, `#f0626b`, `#c084fc`) is too saturated.

Built in a perceptually uniform space (Oklab), five to seven desaturated pastels:

| Type | Hex | Reasoning |
|---|---|---|
| **Concept** | `#7EC8C0` soft teal | the neutral backbone; most numerous |
| **Question** | `#E0B978` soft amber | warm, unresolved, draws the eye without alarm |
| **Claim** | `#B49BD8` soft lavender | distinct from both evidence and concept |
| ⭐ **Artifact** | `#8FD18A` soft green | **the thing you made.** Most distinctive on purpose — it's the moat |
| **Source** | `#8FA9C9` soft slate blue | recedes; it's supporting material |
| **Note** | `#A8A29A` warm grey | unstructured, deliberately quiet |

**Interface:** background `#0B0D10` · surface `#14171C` · text `#E8E6E3` · accent `#FF6B2C` (orange) · alert `#E4756B` (contradiction) · muted `#6B7280`.

**Ordinal scales** vary by **lightness, not saturation**, and invert for dark mode: low values dark and receding, high values luminous and commanding.

## 5.3 Colour-vision deficiency

**~15% of users** have some CVD; red-for-bad / green-for-good is illegible to them.

**Colour is always redundantly encoded.** Every state that matters carries a second signal:

| State | Colour | Redundant signal |
|---|---|---|
| contested | warm | **notch glyph** on the rim |
| stale | desaturated | **clock glyph** |
| phantom | hollow | **dashed perimeter** |
| contradicting edge | warm | **zigzag texture** |
| low confidence | grey | **numeric readout on hover** |

⭐ **Ship a high-contrast mode** that strips all categorical hue and replaces it with **geometric hatch patterns** — diagonal striping, cross-hatching, stippling. Full data legibility with colour vision entirely removed from the equation.

## 5.4 Contrast

WCAG 2.1 AA: **3:1 for large graphical objects, 4.5:1 for text.** Every node border against the canvas, and every label over a node fill, must clear these. Focus indicators: ≥3:1, 4.5:1 preferred.

---

# 6. Typography and labels

## 6.1 Type

| Use | Face | Why |
|---|---|---|
| identifiers, values, code, measurements | **monospace** | engineering context; alignment matters; the current design already does this and it's right |
| prose, labels, UI | **humanist sans** | legible at small sizes |
| numerals in data | **tabular figures** | columns align |

## 6.2 Label placement is NP-hard

Point-Feature Label Placement is provably NP-hard; even the four-slider variant is NP-complete. Moving one label to fix an overlap cascades. **Exact solutions are not computable in real time.**

**Our approach — two-pass, with force-directed refinement:**

```
pass 1   render opaquely at naive fixed offsets (top-right of node)
         → immediate, never blank, never blinking
pass 2   force-directed label refinement in the Worker
         labels repel each other and nodes, tethered by a spring
         → CROSSFADE into refined positions when settled
fallback if no legible placement exists for a cluster:
         collapse to an aggregate label — "Cluster: 14 claims"
```

*Why force-directed rather than simulated annealing: annealing yields better static layouts but computes in epochs that freeze the UI, and our graph is continuously manipulated. See `Research/07` §8.1.*

## 6.3 Semantic zoom for text

**Mandatory.** Rendering every label at every scale is what produces the collisions visible in the current screenshot (*"Safety Brake"* over *"Fixed-Point Math"*).

| Scale | Shows |
|---|---|
| macro | region names only — *"Power"*, *"Sensing"* |
| mid | truncated identifiers — *"MAX30100"*, *"Q15 fixed-point"* |
| near | full labels |
| hover / select | full label + values + provenance, in the right pane |

This needs the `labels_at` field already in the backend schema (Backend/01 §3.2) — a label per zoom level, which is why it was a schema requirement rather than a UI one.

---

# 7. Accessibility

## 7.1 The dual-layer approach

⚠️ ARIA forces **strictly linear traversal.** Tabbing serially through hundreds of nodes to reach a structural sibling destroys context and is functionally unusable.

**So the visual encoding and the screen-reader encoding are decoupled:**

```
canvas          role="presentation" aria-hidden="true"
hidden table    role="table" / "row" / "cell"  — visually hidden, fully accessible
live region     announces the focused node: "Concept: I²C.
                Established. 3 supporting, 1 contradicting. 5 connections."
```

**We already compute a ranked top-50 list with typed relations — the accessible representation *is* the data we render from.** It costs almost nothing.

## 7.2 Keyboard

Every interactive node is focusable, with a **high-contrast focus ring** (≥3:1). Full bindings in `Frontend/03` §4.

## 7.3 Motion

`prefers-reduced-motion` is honoured everywhere — layout computes in the background and crossfades rather than animating (`Frontend/03` §5.4).

---

# 8. Summary — the encoding at a glance

```
NODE
  hue          type            teal/amber/lavender/green/slate/grey
  area         importance      DOI rank
  fill         support         solid · half · hollow-dashed
  saturation   confidence      full chroma → grey  (VSUP)
  inner ring   corroboration   0 / 1 / 2+
  rim notch    contested       ⚠ redundant to colour
  clock glyph  stale           ⚠ redundant to colour
  region tint  project         spatial grouping, NOT hue

EDGE
  width        weight          distinct sources asserting it
  colour       class           cool=support · warm=contradict · grey=mention
  texture      class           solid · zigzag · thin
  dash         relation type   within class
  physics      refutation      repulsive force ⭐

NEVER ENCODED ON DATA CHANNELS
  selection · hover · project membership
```

---

# 💡 Visionary Vector — a progress bar made of epistemics

Research/07 §7.3 is emphatic: streaks backfire, time-in-tool backfires, and any metric that rewards *using the tool* rather than *doing the work* will be resented and then abandoned. It also says what to show instead — **uncertainty reduction.**

Look at what §3.2 produces as a side effect.

Every node's saturation is a direct function of its confidence. A project that begins as a field of grey ghost-nodes and unvalidated claims **literally gains colour as the student validates things.** Week 1 is a grey wireframe. Week 6 is saturated.

**That's a progress indicator that cannot be gamed**, because the only way to add colour is to actually establish something — two independent results, real measurements, real corroboration. Opening the app more doesn't do it. Writing more notes doesn't do it. Only *proving* things does.

No competitor can build this. Not because it's clever, but because **you cannot desaturate by confidence if you never recorded confidence** — and none of them do.

The sharpest form of it lives on the Share page: a six-week time-lapse of a project going from grey to colour, with the retractions visible as things briefly losing their saturation and then earning it back. That single animation says *"here is what learning actually looked like"* more honestly than any write-up, and it falls straight out of an encoding decision we made for entirely different reasons.

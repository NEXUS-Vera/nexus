# Frontend Design — Complete Summary

**Frontend / 05.** The entire frontend design in one document: what it is, every major decision, why, and where the reasoning came from.
**Written to be the only frontend document you have to read.** Self-contained.
**Status:** first draft. Backend is design-complete; this is built against it and can be re-tuned if the backend changes.
**Date:** 2026-08-10

---

# 1. The decision that shaped everything

> **The graph is an engine. The interface is a workbench.**

The evidence forced it: node-link diagrams show **null-to-negative learning outcomes**, comprehension collapses past **~50 nodes** (measured with EEG and pupil instrumentation), and **every capability the graph genuinely provides — multi-hop retrieval, provenance, supersession, crossover detection, the frontier — is machine-facing.** None of it needs a human looking at a diagram.

So the product is a focused workspace answering *"what should I do next, and what do I already know?"* — with the graph as a **secondary view you open when it answers a question.**

**What this buys:** the ranking function becomes the product (a list renders a ranking better than a canvas does); nothing requires curation, so it survives week 3; and because the graph is used rarely and deliberately, we can spend real visual bandwidth on ≤50 nodes.

**What it costs:** the graph is our most demo-able asset. **We keep the sprawl for marketing and refuse it in the product.** That split is deliberate.

---

# 2. The daily loop and the six surfaces

```
1. WHAT NOW?   ranked actions + open tensions      → Bench    (home)
2. WORK        read, build, capture                 → Sources, capture bar
3. RECORD      predicted → measured → agreement     → Artifact ⭐ the moat
4. RECONCILE   review what the system proposed      → Review
                                                    → Log     (the document)
                                                    → Share   (for other people)
                                                    → Map     (the graph, on demand)
```

## The surfaces *(seven now — see §2a)*

| Surface | What it is |
|---|---|
| ⭐ **Bench** | Home. Ranked next actions, open tensions, recent outcomes. **No graph.** Every item is one click from what resolves it, and about the project — never about the tool. Disagreements surface here by **computed priority** (P0 inline → P4 suppressed), competing with gaps for the same three `NOW` slots |
| ⭐ **Artifact** | Predict → lock → measure → agreement. The simplest screen and the most important. `Lock prediction` is timestamped and immutable, which is what makes calibration real |
| **Review** | ⭐ **The thinking prompt** — holds only `AMBIGUOUS` items, the ones nobody but the student can settle. Split view, keyboard-driven (A/R/E), never blocking |
| **Log** | The project document, growing. Becomes the write-up; time-lapse is the progress artifact |
| ⭐ **Share** | Read-only, for teammates, mentors, investors, professors. What it is / what was proven / how it got there. **Failures stay visible** |
| **Map** | The graph. ≤50 nodes, semantic controls, opened deliberately. **Fifth thing I'd build** |

**Layout:** IDE-style three panes (navigate · work · context) with an always-present capture bar. One input, no decision about where things go — the system routes it. That directly attacks the "organisational tax" the research names as the primary driver of PKM churn.

---

# 3. The visual system

## The constraint

> **The force layout consumes spatial position and spatial region — the #1 magnitude and #1 identity channels — just to show topology.**

Everything else must be spent on weaker channels, in a strict order. There aren't enough to be casual.

```
NODE
  hue          type              6 desaturated pastels
  area         importance        DOI rank
  fill         support           solid · half · hollow-dashed
  saturation   confidence        full chroma → grey  (VSUP) ⭐
  inner ring   corroboration     0 / 1 / 2+
  rim notch    contested         ⚠ redundant to colour
  region tint  project           spatial grouping, NOT hue

EDGE
  width        weight
  colour       class             cool=support · warm=contradict · grey=mention
  texture      class             solid · zigzag ⭐ · thin
  physics      refutation        repulsive force ⭐

NEVER on a data channel:  selection · hover · project membership
```

## Uncertainty

**VSUP — desaturate toward grey as confidence falls.** This defeats the trap where a bright saturated node reads as *important* when it's merely *noisy*. The interface physically prevents drawing a confident conclusion from an uncertain node. ⚠️ Always paired with a numeric readout on hover, because VSUPs collapse under low resolution and CVD.

**Rejected:** blur (⛔ **expands perceived node area**, corrupting the size channel), transparency (reads as absence), error bars (unreadable at 50 nodes).

**HOPs** for measurements with real variance — but localised, layout frozen, on-demand only, because the multiple-object-tracking limit is ~5 targets.

## Contradiction and absence

**Contradiction uses Scite's three-vector model, not Kialo's hierarchy** — Kialo's strict pro/con tree breaks down in a force-directed topology with cycles. Supporting = solid cool. **Contradicting = sharp zigzag, warm** — a pre-attentive pop-out spotted the instant the view loads. Mentioning = thin grey.

⭐ **A refuting edge also inverts the physics** — a repulsive force pushes the source away from what it refutes. Disagreement doesn't just look different, it *pushes apart*.

**Absence = Ghost Nodes** — dashed perimeter, hollow fill, exploiting Gestalt closure. ⚠️ The dangerous anti-pattern is blank/zero/omit: **users read a zero as a literal measurement.**

## The palette, and the brand

The README said "strictly black + orange." That cannot survive six node types.

> **Resolution: orange becomes the *interface* colour precisely because it is not a *data* colour.**

Buttons, focus rings, active tabs, brand mark: orange. **Nothing in the graph is orange.** No collision, and the brand stays where people actually perceive it.

Nodes are six desaturated pastels in Oklab — saturated colour at high luminance on dark backgrounds causes **halation** and eye fatigue over long sessions. `Artifact` gets the most distinctive hue on purpose: it's the moat.

**~15% of users have CVD**, so every state that matters carries a redundant non-colour signal, plus a high-contrast mode that strips hue entirely for geometric hatch patterns.

## Labels

Point-Feature Label Placement is **NP-hard** — exact solutions aren't computable in real time. Two-pass: render at naive offsets immediately, then crossfade to force-directed refinement from the Worker. Fall back to an aggregate label (*"Cluster: 14 claims"*) when no legible placement exists.

**Semantic zoom is mandatory** — regions → truncated identifiers → full labels → full detail in the context pane. This is what fixes the label collisions visible in the current design.

---

# 4. Interaction

**Selection never uses a data channel.** Primary mechanism is ⭐ **negative highlighting** — dim luminance and saturation of everything *unselected*. Luminance is separable from hue, so selected nodes keep their identity and pop by contrast. Plus enclosure ("marching ants") and drop shadow.

⭐ **A multi-select drag is a single rigid body with aggregated mass** — otherwise the layout keeps computing intra-group repulsion and **the cluster visually explodes.**

**Drag-and-drop is a state machine**, and ⭐ **failure animates back along a reverse trajectory.** A node that vanishes reads as a bug; one that teleports reads as a glitch. The kinesthetic reversal is what communicates rejection.

**Undo has two modes:** spatial undo is **debounced** (capture at drag-start, commit at drop — otherwise "undo" rewinds physics by pixels); semantic undo stores a ⭐ **deep structural memento** of the affected subgraph, because deleting a foundational node cascades.

⭐ **Retraction shows its consequences first:** *"this will unsupport 2 conclusions — here they are. Nothing is deleted."*

**Keyboard: arrows by default, Vim opt-in.** Dual-mode traversal — arrows move **structurally** along edges, ⌥+arrows move **spatially** to the nearest node in a direction. ⚠️ Vim modal bindings are detrimental as a default for undergraduates; our users are ECE students, not software engineers.

**Command palette** always paired with visible GUI, shortcut hints, and fuzzy/synonym matching — palettes fail on **recall over recognition**.

---

# 5. Motion

⭐ **Staged, never simultaneous** — measured to significantly improve change tracking and reduce error.

```
Stage 1  TOPOLOGY PREP    180ms   layout opens a void around the target
Stage 2  FOCAL EXPANSION  140ms   children fade in at the void's centre
Stage 3  DISTRIBUTION     260ms   children animate out to equilibrium
```

New children are injected **at the parent's exact coordinates** so nothing flies in from the origin.

**Don't lock coordinates.** Mental-map preservation is a **measured null result** — users preferred it and gained nothing. Let the layout restructure; the only exception is explicit user pins.

⭐ **Map the layout's "swinging" value to a subtle settling indicator** so the graph reads as converging rather than glitching.

`prefers-reduced-motion`: compute in the background, crossfade to final positions, render no iteration at all.

**Nothing exceeds ~600ms** — beyond that it stops reading as feedback and starts reading as waiting.

---

# 6. Surviving week 3

⭐ **The abandonment cliff is week 3** — the transition from research to execution, when debugging begins and time spent organising drops to zero. Anything requiring upkeep dies there.

| Rule | |
|---|---|
| **Zero organisational tax** | one capture bar; the system routes |
| **Nothing to maintain** | no folders, no tags, no schema for the user to fill |
| **Home screen is about the project, never the tool** | |
| ⛔ **No streaks, no time-in-tool, no completion %** | measured to **backfire** — they reward using the tool rather than doing the work, and penalise a student who spent 40 hours at an oscilloscope |
| **Progress = uncertainty resolved + components advanced** | the only mechanic the evidence supports |
| **Pseudo-ambient only** | milestone-triggered, silent between; ⛔ no continuous peripheral motion |
| **Useful having done nothing** | the cold-start graph gives the Bench content on day one |

**Empty states:** the cold-start graph (~25 real nodes from one typed sentence) plus a functional worked-example template. **No unskippable modal tours.**

---

# 7. What changes in the existing design

| Feature | Verdict |
|---|---|
| Local-graph depth slider | ✅ keep — the only genuinely useful graph affordance |
| Node size by degree | ⚠️ change → **DOI importance**, not raw degree |
| Node size / opacity / spread sliders | ❌ drop → **semantic controls** (lens, depth, show, since) |
| Text-fade slider | ✅ keep, as semantic zoom |
| Timelapse | ⚠️ change → **validation order**, not creation order. Becomes the Share artifact |
| Saved views | ✅ keep — it's the `View` object, now shareable |
| Key nodes | ✅ keep, with mechanical-edge filtering |
| Surprising links | ✅ keep + upgrade → computed by the crossover scorer with a generated `why` |
| Suggested questions | ✅ keep, derived from graph deficiencies |
| Graph report | ✅ keep → becomes Log + Share |

**From the current screenshot, three fixes beyond that list:**
1. ⚠️ **Hue is doing two jobs** — the legend shows four *projects* and four *kinds* in one colour space. Projects move to spatial regions.
2. ⚠️ **644 nodes** is 13× the comprehension limit. Beautiful; not a product view.
3. ⚠️ **Labels collide** — needs two-pass placement and semantic zoom.

**What it gets right and should survive:** the right-panel structure, *"Search a node, or ask your graph…"* as the entry point, and the Insights triad (Key nodes / Surprising links / Summarize), which maps almost exactly onto god nodes, the crossover scorer, and the report.

---

# 8. Build order

⭐ **Superseded by `Frontend/07 §6`**, which sequences all nine steps with days and dependencies. The ordering below is kept as the reasoning behind it.


| | Surface | Why |
|---|---|---|
| 1 | **Artifact** | the moat. Two days, testable by a real student in week 1 with no graph at all |
| 2 | **Bench** | the daily loop. Proves the ranking is any good |
| 3 | **Review** | produces the accept rate — the most important early number |
| 4 | **Log + Share** | the first thing worth showing anyone |
| 5 | **Map** | deliberately last |

**The Map is fifth.** That's the thesis of this document made concrete, and if it feels wrong, that's the argument worth having.

**Mobile:** desktop-only for work; **Share, Bench, and Log responsive**; one Quick Capture affordance for photographing a scope trace. No feature parity.

---

# 9. What I'm not sure about

Eleven documented doubts (`Frontend/04`). The four that matter:

**F1 — is graph-as-engine right, and did I over-correct?** The research condemns *unbounded* graphs given to people with a search task. A 50-node, well-encoded, deliberately-scoped graph is a different object and might be fine as a primary surface. **Time-to-close on the Map is the tell.**

**F4 — do six desaturated hues actually separate?** Desaturation is required for dark mode but **compresses the distance between hues**, especially at small sizes and under CVD. ⭐ **Half a day to test, and it should happen before any UI is built** — if it fails, node types collapse to four or five.

**F8 — will anyone fill in the prediction form?** It's the most form-like thing in a product designed to eliminate friction, and it appears exactly when a student is impatient to go build something. **If it feels like paperwork it won't get used — and it's the moat.**

⭐ **F11 — have I designed for the wrong moment?** Every surface here assumes a *planning* posture. The abandonment cliff is week 3, at 1am, mid-debug — where the question isn't *"what next?"* but *"why isn't this working, and have I already tried this?"* The highest-value surface might be a **debug companion** I haven't designed: everything the graph knows about the one thing in front of you, including your own dead ends. **One afternoon observing a real student in week 3 would be worth more than another research pass.**

---

# 10. Status

| | |
|---|---|
| **Frontend research** | ✅ complete — 97 citations, `Research/07` rev 2 |
| **Frontend design** | ✅ first draft — `Frontend/01–05` |
| **Built** | ❌ nothing |
| **Blocking** | F4 (half a day) · then backend Phase 0 |

**`Frontend/06_Foundations`** settles the three things that blocked everything else: **node anatomy** (the encoding matrix composited, with the legibility floor), **design tokens** (runtime-switchable CSS variables so the accessibility modes work), and the **stack + data flow**. Screen specs are deliberately deferred until after backend Phase 0 — F1 and F11 could still relocate the product, and specs written now would be rewritten.

## 10.1a ⭐ The gaps are closed — end to end *(2026-08-10, second pass)*

The first draft designed the six surfaces and left everything the backend grew
afterwards undesigned. **Eight gaps, now closed:**

| Gap | Where it landed |
|---|---|
| ⭐ **Ask — the main verb** | `01 §4.0`. Deferred as "the search flow", which was wrong: the turn protocol is the primary interaction and everything else is scaffolding around it |
| ⭐ **Explain — *why do I believe this?*** | `01 §4.0a`. Right pane, never a modal. **Renders retracted support as its own block** — a claim that LOST its evidence is a different state from one that never had any |
| **Sources / ingest / quarantine** | `01 §4.4a`. Files are how the graph gets made. ⭐ `0 tokens` is user-facing: the student can see which parts are certain by construction |
| **Dead-end resurrection** | `01 §4.1`. ⭐ Names the *change*, not the memory — *"you tried this before"* is an accusation, *"the blocker has changed"* is an offer |
| **Crossovers** | `01 §4.1`. Always with the `why`, as bullets. **A connection without the reason it is surprising is a horoscope** |
| **Cold start** | `01 §8`. ⭐ *"How will you know it worked?"* is the most important screen in the product — a nudge, never a gate |
| **Calibration + cost** | `01 §4.7a–b`. ⚠️ **Never render the curve under 15 predictions**: noise shaped like a finding, and a student reading a random walk as *"I'm getting worse"* stops predicting |
| **Screen specs, settings, notifications, offline, build plan** | ⭐ **new `Frontend/07`** |

**Two things `Frontend/07` settles that nothing else had.**

⭐ **Offline is scoped honestly.** The frontier, capture, and predict/measure
all work with no signal; `ask`, extraction and embeddings do not. That split is
the surviving argument for graphology on both sides — **a student at a bench
with no signal asking what to do next, and getting an answer.**

⚠️ **Rim glyphs are nearly full.** Three (`◑` single-method, `⚡` contested, `◷`
stale) is readable; five is a rash. Anything new competes for one of the three
rather than adding a fourth.

## 10.1 ⭐ Reconciled against the final backend *(2026-08-10)*

The backend closed all twelve of its open questions after this design was drafted. **Three of those resolutions reach the frontend**, and they are folded in:

| Backend change | Frontend effect | Where |
|---|---|---|
| ⭐ **Display decoupled from acceptance** (`Backend/05 §4.2`) — the answer streams while the Critic runs concurrently | **A new async class.** The answer arrives with a visible `◌ checking` from the first token; the verdict resolves **in place**, never re-flowing text; a `CRITICAL` verdict **demotes** the answer rather than annotating it. ⚠️ This is the only place the interface can show something that later proves wrong, so it has stricter rules than optimistic UI | `01 §4.1a` · `03 §6.1a` |
| **`Method` is `Artifact(kind=method)`** with a `single_method` flag (`Backend/09` Q12) | A run picks its method (defaulting to *"same as last time"*), and a claim corroborated only by one rig carries a **`◑` rim badge**. It reads as information, not a warning — the value is the click, which asks *"what would a different method look like?"* | `01 §4.3` · `02 §2.1` |
| **Model tiering** and the Tier 0 router (`Backend/05 §3.2`) | ⭐ **No frontend effect, deliberately.** Which model answered is a cost and quality concern, not a user-facing one — the single exception is the **`degraded` badge** when a budget breach forces a cheaper answer mid-turn, because *"a cheaper answer presented identically to an expensive one"* is the one failure a student cannot detect for themselves | `01 §4.1a` |

⚠️ **One collision this reconciliation caught.** The `single_method` badge was first specified as a **half-fill** — but fill style already carries **support state** in `02 §2.1`. Two unrelated properties would have become indistinguishable. It's a rim glyph now, alongside `contested` and `stale`, which is the right family anyway: *"something about the evidence here deserves a look."*

**Nothing else moved** in that pass. The encoding matrix, the interaction model and the eleven doubts in `Frontend/04` all stand as drafted — and after §10.1a's second pass, **the design is complete end to end.**

⚠️ **F4 is still what blocks UI work**, and it is now step 0 of the build plan
(`07 §6`) rather than a note: half a day, and it can invalidate the palette, the
node chip and the encoding matrix. **Everything below it assumes it passed.**

---

# 💡 The two things that make this different

**1. The frontend's real job is rendering doubt.**

Every graph UI in existence encodes two things: a node exists, a link exists. Colour is decorative. Our backend produces something categorically richer — **how strongly believed, whether disputed, how well-grounded, whether stale, whether it exists yet** — and R4/R5 handed us the vocabulary for all of it.

A competitor could clone our layout in a week. They cannot clone the encoding, because **you can't desaturate by confidence if you never recorded confidence.**

And the 50-node cap stops being a ceiling: with only fifty things on screen you can spend real visual bandwidth on *each one's epistemic state*. A tool rendering 10,000 nodes structurally cannot. **The comprehension limit is a budget you get to spend on depth instead of breadth.**

**2. The Share page is the product's distribution.**

It contains a verifiable, timestamped, cryptographically-chained record of what a student predicted, what they measured, when, in what order — **including everything that failed** — with a calibration curve showing their judgement improving over six weeks.

Nothing in education produces that artifact. A transcript records which courses you sat in. *"Built a biosensor prototype"* on a résumé is unverifiable and everyone knows it.

So Share isn't a feature — **it's the reason a student tells another student about Nexus.** Every project produces one, it has a URL, and it contains something they want seen. Organic distribution built into the core loop, at near-zero cost, because the ledger already holds every input.

The sharp version: **the calibration curve is a credential.** If predictions measurably improve, then this isn't a note-taking tool with a graph — it's the first system that can produce **evidence of engineering judgement**, which is the thing every employer claims to select for and nobody can currently measure.

**Which is also the best argument for graph-as-engine: the output isn't the map. It's the proof.**

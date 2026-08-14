# Frontend Design

**Frontend / 01.** The complete frontend architecture: what the product *is*, the surfaces, the information architecture, and how the graph fits in.
**Premise (decided 2026-08-10):** **graph-as-engine.** The graph powers the product; it is not the product.
**Status:** first draft, built on `Research/07` rev 2 (97 citations) and the backend as it stands (`Backend/01–11`).
**Date:** 2026-08-10

---

# 1. The decision that shapes everything

> **The graph is an engine. The interface is a workbench.**

The evidence forced this (Research/07 §2): node-link diagrams show null-to-negative learning outcomes, comprehension collapses past ~50 nodes, and **every capability the graph genuinely provides — multi-hop retrieval, provenance, supersession, crossover detection, the frontier — is machine-facing.** None of it requires a human to look at a diagram.

So the product is **not** a canvas you live inside. It's a focused workspace that answers *"what should I do next, and what do I already know?"* — with the graph available as a **secondary view you open when it answers a question**.

## 1.1 What that buys us

| | |
|---|---|
| The ranking function becomes the product | If only ~50 things matter, a **ranked list renders a ranking better than a canvas does** |
| Week-3 survival | A list requires no curation. A canvas does (Research/07 §7.2) |
| Everything gets a non-graph path | Rule 13 in the research: for many tasks a list genuinely beats a graph |
| The graph gets to be excellent | Because it's used rarely and deliberately, we can spend real visual bandwidth on ≤50 nodes |

## 1.2 What we lose, honestly

The graph is the most *demo-able* thing we have. The screenshot of 644 nodes is genuinely striking, and it's what makes people say "oh, that's interesting."

**We keep that — for marketing.** The landing page can render the sprawl. The product cannot. That split is deliberate, not a compromise.

---

# 2. The daily loop

Everything follows from what a student actually does:

```
  ┌──────────────────────────────────────────────────────────┐
  │  1. WHAT NOW?      ranked next actions + open tensions     │  ← the home screen
  │  2. WORK           read, build, measure, capture           │
  │  3. RECORD         predicted → measured → agreement        │  ← the moat
  │  4. RECONCILE      review what the system proposed         │
  └──────────────────────────────────────────────────────────┘
                    each pass makes the next one sharper
```

**The home screen is step 1**, not a graph and not a blank page. That single decision resolves most of the layout questions below.

---

# 3. Information architecture

**IDE-style three-pane on desktop, with a zero-friction capture bar.** This is R6's recommended hybrid: the spatial separability of an IDE, the input friction of a chat.

```
┌────────────┬──────────────────────────────────────┬────────────────┐
│            │                                       │                │
│  NAVIGATE  │           ACTIVE SURFACE              │    CONTEXT     │
│            │                                       │                │
│  projects  │   Bench · Map · Log · Source · Review  │  selection     │
│  questions │                                       │  provenance    │
│  sources   │   (one at a time, tabbed)             │  citations     │
│  artifacts │                                       │  actions       │
│            │                                       │                │
│  240px     │            fluid                      │     320px      │
├────────────┴──────────────────────────────────────┴────────────────┤
│  ⌘K  ·  capture bar — type anything, it lands in the right place    │
└─────────────────────────────────────────────────────────────────────┘
```

**Left pane collapses** (⌘\). **Right pane is contextual** — empty when nothing is selected, and that's fine.

**The capture bar is always present.** One input, no decision about where things go. Type a note, paste a link, drop a file, record a measurement. The system routes it. This is the direct answer to the "organisational tax" that Research/07 §7.1 identifies as the primary driver of churn.

---

# 4. The surfaces

## 4.0 ⭐ Ask — the main verb *(added 2026-08-10)*

⚠️ **This was deferred as "the search flow" and that was wrong.** The backend's
turn protocol is now the product's primary interaction: a student types a
question, the graph answers with cited claims, and the Critic annotates it a
second later. Everything else on this list is scaffolding around that.

**It lives in the capture bar, not on a separate screen.** One input for
capture and for asking is the direct answer to the organisational tax — the
student never decides *"is this a note or a question?"*, the router does.

```
┌──────────────────────────────────────────────────────────┐
│  does my 47.2 kΩ match the Zhang paper?          ⌘K       │
└──────────────────────────────────────────────────────────┘
        ↓  answer streams into the ACTIVE SURFACE
┌──────────────────────────────────────────────────────────┐
│  Zhang reports 30–40 kΩ for gel electrodes. Yours is     │
│  dry-electrode, and the difference is the expected       │
│  direction…                             ◌ checking       │
│                                                          │
│  ▸ Zhang 2019 §3.2  ·  your 14 Mar sweep                 │
└──────────────────────────────────────────────────────────┘
```

**Four rules, each earned from a backend property:**

1. ⭐ **Every claim in the answer is a chip that opens `explain`** (§4.0a). An
   answer you cannot interrogate is a chatbot; the whole reason this is a
   graph is that you can walk backwards from any assertion.
2. **Citations render as their `citation_state`, not as a uniform footnote.**
   `present_relevant` is a solid link; `present_weak` is dashed; `missing` says
   *"unverified"* in words. **A citation is an inspection path, not proof**, and
   flattening the five states into one blue superscript re-introduces exactly
   the false confidence the backend spent a whole contract preventing.
3. **The answer streams; the critique lands after** — §4.1a, unchanged.
4. ⚠️ **`degraded` shows.** If a budget breach forced a cheaper path mid-turn,
   the answer carries a small `economy` mark. A cheaper answer presented
   identically to an expensive one is the single failure a student cannot
   detect for themselves.

### 4.0a ⭐ Explain — *why do I believe this?*

Opens in the **right pane**, never a modal — you are comparing it against what
is on screen, so it must not cover it.

```
┌─ 47 kΩ at 50 kHz indicates hydrated skin ────────────────┐
│  CONTESTED · tentative · corroboration 1                  │
│  ◑ all corroboration from one method                      │
│                                                           │
│  ← supported by                                           │
│     ▪ your 14 Mar sweep          measured_by · EXTRACTED  │
│  ⚡ contradicted by                                        │
│     ▪ Zhang 2019 §3.2            contradicts · 0.85       │
│  ✗ support you retracted                                  │
│     ▪ 2 Mar sweep — bad probe    deprecated wk 4          │
└───────────────────────────────────────────────────────────┘
```

⭐ **The third block is the one no competitor can render.** A claim that *lost*
its evidence is a different state from one that never had any, and showing them
identically is what makes a system feel like it is hiding something. The
backend distinguishes them (`explain.retracted_support`); the UI must too.

**Every row is clickable and lands on the thing itself.** `explain` is a
navigation surface, not a report.

## 4.1 ⭐ Bench — the home screen

What you see on open. Three stacked sections, ranked, no graph:

```
┌─ NOW ────────────────────────────────────────────────────┐
│  ◆ Measure electrode impedance at 50 kHz                  │
│    unlocks 3 things · ~2h · you have the parts            │
│                                                           │
│  ◆ Resolve: your 47 kΩ vs Chen et al.'s 30–40 kΩ         │  ← tension
│    2 measurements agree · paper is well-grounded          │
│                                                           │
│  ◆ Read: MAX30100 datasheet §7 (settling time)            │
│    3 open questions depend on this                        │
└───────────────────────────────────────────────────────────┘

┌─ OPEN ───────────────────────────────────────────────────┐
│  ⚠ 2 contested claims        ○ 7 gaps you can reach now   │
│  ◷ 1 claim went stale        ◻ 4 proposals to review      │
└───────────────────────────────────────────────────────────┘

┌─ RECENT ─────────────────────────────────────────────────┐
│  yesterday  measured 47.2 kΩ  → matched your prediction ✓ │
│  Tue        retracted "5V rail is clean" — bad probe       │
└───────────────────────────────────────────────────────────┘
```

**Every item is one click from the thing that resolves it.** No item is a chore about the tool — each one is about the project.

### How disagreements surface here *(Backend/01 §8.2, revised 2026-08-10)*

The Disagreement Engine emits a **priority**, not just a tension, and priority decides the surface:

| | Where it lands | |
|---|---|---|
| **P0** | ⚠️ **inline, immediately** — wherever the student currently is | active work depends on something now contested. **Never more than one at a time** |
| **P1** | `NOW` — **competing with gaps for the same three slots** | not blocking, but the highest-value next action |
| **P2** | `OPEN` — counted, not listed (*"⚠ 2 contested claims"*) | real, not urgent |
| **P3** | inline where the student already is, **never pushed** | only relevant when nearby |
| **P4** | nowhere | resolved, dismissed, or superseded |

⭐ **P1 tensions do not get their own queue.** They compete in the same ranking as everything else, so the product has one notion of *"what matters now"* rather than a frontier and an alert system disagreeing with each other.

**Ranked by the DOI function** (Backend/01 §6). This is the ranking made visible, which is the whole point of §1.1.

### ⭐ Two row types that only we can produce *(added 2026-08-10)*

The backend emits both; neither had a rendering.

```
┌─ NOW ─────────────────────────────────────────────────────┐
│  ↻ You gave up on 400 kHz I²C in week 2 — the blocker      │
│    has changed. You added shielding on Tuesday.           │
│                                          [ retry ] [ no ] │
│                                                            │
│  ✦ Your electrode drift problem is the same shape as the  │
│    filter settling problem in Robotics Lab.               │
│    · crosses bio ↔ control                                 │
│    · connects a published claim to your own measurement    │
└────────────────────────────────────────────────────────────┘
```

**Resurrection (`↻`) names the change, not the memory.** *"You tried this
before"* is an accusation; *"the blocker has changed"* is an offer. The backend
tracks exactly which node moved, so the copy can be specific — and specificity
is the whole difference between the two readings.

⭐ **Crossover (`✦`) always shows its `why`, as bullets, never prose.** A
connection without the reason it is surprising is a horoscope. The reasons come
from the scorer verbatim; if the list is empty the row is not shown at all.

⚠️ **Both are capped at one each per Bench.** They are the highest-variance
suggestions in the system — a wrong crossover is memorable in the bad way — so
they earn a slot by outranking gaps, never by having a reserved one.

### ⭐ 4.1a Answers stream; the critique lands after *(added 2026-08-10, Backend/05 §4.2)*

The backend decoupled **display** from **acceptance**. The Critic no longer blocks the text — it runs concurrently and its verdict arrives about a second later. That removes two of the three sequential model round-trips a student used to wait through, and the frontend has to hold up its end of it.

```
t=0.4s   ┌──────────────────────────────────────────┐
         │ Your 47.2 kΩ is consistent with a        │   text streaming
         │ hydrated reading at 50 kHz…              │   ◌ checking      ← quiet, inline
         └──────────────────────────────────────────┘

t=1.6s   ┌──────────────────────────────────────────┐
         │ Your 47.2 kΩ is consistent with a        │
         │ hydrated reading at 50 kHz…              │
         │ ⚠ Chen et al. report 30–40 kΩ  →         │   ← badge resolves in place
         └──────────────────────────────────────────┘
```

**Three rules, because this is the one place the product can mislead:**

1. **The pending state is visible from the first token.** A quiet `◌ checking` sits with the answer from the moment it starts. The student is never shown a bare answer that *looks* settled and then isn't — **the uncertainty is on screen before the certainty is.**
2. **The badge resolves in place — it never re-flows the text.** Reserve the row. Content that jumps while being read is the failure mode that makes people distrust streaming interfaces.
3. ⭐ **`CRITICAL` demotes the answer; it doesn't just annotate it.** On a P0 verdict the prose desaturates and the tension takes visual primacy. Anything lower resolves quietly. This is the Q8 priority tiers doing the work — **the ~1-second uncritiqued window is bounded by them**, which is why widening the trigger in Q8 mattered more than it looked.

**Nothing is written until the Critic returns.** No `accepted` event, no node, no edge. **The student reads early; the graph waits.** If the answer is retracted before acceptance it simply never entered the record — which is the correct behaviour and is only possible because the ledger is append-only in the first place.

## 4.2 Map — the graph, used deliberately

Opened from a specific question, never as a destination. **Hard cap ~50 nodes.**

Entry points:
- *"show me what this connects to"* from any node
- *"show me this project as a power problem"* — the lens control
- from a tension, to see the disagreement in context
- from search, when the answer is structural

**Controls are semantic, not physical.** The current design exposes `node size`, `link opacity`, `spread` — raw physics. Nobody wants those. They want:

| Control | Does |
|---|---|
| **Lens** (text) | re-weights edge distance by relevance — *"power budget"*, *"what's unvalidated"* |
| **Depth** | 1 / 2 / 3 hops from focus |
| **Show** | ☑ gaps ☑ contested ☐ superseded ☐ sources |
| **Since** | time window — *"only what changed this week"* |

**Always paired with an overview** (§4.7) — never focus+context distortion, which the research prohibits outright.

## 4.3 ⭐ Artifact — the moat loop

The most important screen in the product, and the simplest.

```
┌─ PREDICT ─────────────────────────────────────────────────┐
│  What are you about to do?                                 │
│  ▸ Measure skin impedance at 50 kHz, dry electrodes         │
│                                                            │
│  What do you expect?      40  –  60   kΩ                    │
│  How sure are you?        ○──────●──○   fairly confident     │
│                                                            │
│  [ Lock prediction ]   ← timestamped, cannot be edited after │
└────────────────────────────────────────────────────────────┘

           ↓  (you go and do the thing)

┌─ MEASURE ─────────────────────────────────────────────────┐
│  What happened?           47.2  kΩ      [ photo ] [ csv ]   │
│                                                            │
│  → MATCHED. Your predicted range contained the result.      │
│    Calibration: 7 of 9 predictions correct so far.          │
└────────────────────────────────────────────────────────────┘
```

**`Lock prediction` is the load-bearing interaction.** Once locked it's in the ledger and immutable — which is what makes the calibration record real rather than self-flattering. The UI should make that feel like a commitment, not a form field.

### ⭐ Method, and the `single_method` badge *(added 2026-08-10, Backend/09 Q12)*

A run declares the method it used — `Artifact(kind=method)`, reused across runs rather than retyped. In the SETUP block that is a **picker with a default of "same as last time"**, because the common case is the third run on the same rig and typing it again is how the field goes empty.

Where it earns its place is on a Claim:

```
┌────────────────────────────────────────────────────────────┐
│  47 kΩ at 50 kHz indicates hydrated skin                    │
│  ESTABLISHED · 3 results agree                              │
│  ◑ all three used one method — 4-wire Kelvin, 2 cm  →       │
└────────────────────────────────────────────────────────────┘
```

**It reads as information, not as a warning.** `ESTABLISHED` is not withdrawn and the badge is not red — because same-method replication *is* a legitimate reproducibility check, and an undergraduate usually has one rig. Flagging it as a defect would punish the normal case to catch the rare one.

⭐ **What it's for is the click.** Expanding it names the method and offers *"what would a different method look like?"* — which is the highest-value experiment suggestion the system can make, and it is invisible without a Method node. **A claim backed three times by one setup is the most common way a student is confidently wrong**, and until now nothing in the design could see it.

**`◑` is a rim badge, not a fill.** ⚠️ Fill style is already carrying support state (`Frontend/02 §2.1`) — reusing it would make two unrelated properties indistinguishable. It joins `contested` and `stale` as a rim glyph, which is the right family anyway: *"something about the evidence here deserves a look."* Being a glyph rather than a hue also means it survives the CVD constraint in `Frontend/04` F4.

## 4.4 Review — the thinking prompt

⭐ **Revised 2026-08-10 (`Backend/09` Q1):** this queue holds **only `AMBIGUOUS`** items — the cases the system genuinely cannot resolve. Everything the extractor is confident about is auto-accepted and reversible. So Review is not a chore list; it is *"here are the four things nobody can settle but you."* Small, high-value, and never blocking.

Batch, keyboard-driven, capped. Split view per Research/07 §4:

```
left:   the proposal in local graph context (5–8 nodes, not 50)
right:  the source passage, the claim, confidence, citation state
keys:   A accept · R reject · E edit · ␣ skip · ⌘A bulk accept selection
```

**Never more than ~20 items in a session.** When the queue exceeds ~50, the system stops proposing anything below `INFERRED 0.85` until it drains (Backend/05 §6.3). A flooded queue gets abandoned, and an abandoned queue means auto-accept is silently the only gate.

**AI-proposed items are visually distinct** — dashed stroke, muted fill — until a human touches them.

⭐ **Review also hosts the structuring nudge** (Backend/01 §5.1). When unstructured notes build up, the offer appears on the Bench — *"18 notes I haven't structured. Take a pass?"* — and opens the same batch surface: proposed structure per note, A/R/E, bulk-accept the confident ones. **An offer, never a blocker**, and a note that resists twice is left alone permanently.

## 4.4a ⭐ Sources — ingest, and the answer to *"why didn't it pick that up?"*

Files are how the graph gets **made**, and until now nothing was designed for
them. It is the left pane's `sources` section plus one full surface.

**Drop anything.** The capture bar and the left pane both accept files; routing
is the backend's job and is never asked about.

```
┌─ ADDED TODAY ─────────────────────────────────────────────┐
│  zhang2019.pdf     ▓▓▓▓▓▓▓▓░░  reading…    24 claims      │
│  sweep_0314.csv    ✓ parsed    0 tokens    3 quantities   │
│  driver.py         ✓ parsed    0 tokens    12 functions   │
│  scope_trace.png   ⏸ needs a look          1 unclear      │
└───────────────────────────────────────────────────────────┘
```

⭐ **The `0 tokens` mark is deliberate and user-facing.** Code and measurements
are *parsed*, not guessed at — the student should be able to see which parts of
their graph are certain by construction. It is also the most honest possible
answer to *"is this thing making things up?"*

### Quarantine — visible, low-priority, and never silent

Anything the validator rejected is **kept and shown here**, not dropped:

```
┌─ COULDN'T USE (4) ────────────────────────────── show ▾ ──┐
│  zhang2019.pdf p7   "unknown relation: correlates_with"    │
│  notes.md L12       "label was a sentence — kept as a Note"│
└───────────────────────────────────────────────────────────┘
```

Two reasons this earns screen space. **A student asking *"why didn't it pick up
X?"* deserves an answer better than silence** — and ⚠️ **a spike in one
rejection reason is the earliest signal a prompt has regressed**, which is a
thing we want a human to notice before a metric does.

### The Sources reader — span to claim

Opening a source shows the document with **extracted spans highlighted in
place**. Clicking a highlight selects the claim it produced; clicking a claim
elsewhere scrolls the source to its span.

⚠️ **PDF spans are page-level, not character-level** (`extract.read_document`
discards layout). The highlight is therefore a **page band, not a phrase box** —
showing a tight rectangle we cannot actually locate would be a precise-looking
lie, and the student would trust it exactly once.

## 4.5 Log — the project document

The accretion view. Every validated finding, in order, as a readable document. This is:
- the thing that becomes the write-up
- the **progress artifact** — visible diffs and a time-lapse of how the project evolved (Research/07 §7.3, and the *only* progress mechanic the evidence supports)
- the export target

**Not a feed.** A document that grows.

## 4.6 ⭐ Share — read-only, for other people

*New requirement: teammates, mentors, investors, and professors will look at this.*

A published, read-only view. **Different audiences want different things, so it's one page with three sections:**

```
┌─ WHAT THIS IS ────────────────────────────────────────────┐
│  The question, the current answer, the confidence           │
├─ WHAT WAS PROVEN ─────────────────────────────────────────┤
│  Artifacts with measured results. Predicted vs actual.      │
│  ⭐ The calibration curve over the project                   │
├─ HOW IT GOT THERE ────────────────────────────────────────┤
│  Time-lapse in VALIDATION order — including the retractions │
│  Ledger head hash + verifier link                           │
└────────────────────────────────────────────────────────────┘
```

Three deliberate choices:

- **Failures stay visible.** The retracted measurement, the dead end, the paper that turned out not to apply. That's what demonstrates competence, and it's exactly what a polished write-up destroys.
- ⭐ **The calibration curve is the headline** — *"this student's predictions got measurably better over six weeks"* is a claim no transcript, grade, or résumé line can make. Rendered as a **reliability curve** (stated confidence vs observed accuracy, with the diagonal marked) plus **interval coverage**, not a single score — see `Backend/06 §5`.
- **The hash makes it verifiable.** Anyone can replay the ledger and confirm the predictions weren't written afterwards (Backend/02 vector).

**No editing, no review queue, no frontier.** Sharing is a different job from working.

## 4.7 Overview — the persistent companion

Because focus+context loses to **overview+detail** across all display sizes, the Map is never alone. The overview sits in the right pane and is **abstracted, not shrunken** — a small hairball is still a hairball.

**Proposal: the overview is a state dashboard, not a minimap.**

```
  ████████░░░░  62% of concepts established
  ▲ 2 contested   ○ 7 reachable gaps   ◷ 1 stale
  ●●●●●●●○○○  calibration, last 10 predictions
```

That's more useful than a shrunken picture, and **only we can build it** — it requires the epistemic state no competitor records. *(Flagged as an open question — see `Frontend/04` F2.)*

### 4.7a ⭐ Calibration over time — the claim nobody else can make

Lives on Share (§4.6) and, collapsed, in the Overview.

```
  observed  1.0┤                              ╱
               │                        ╱  ← perfect
            0.5┤          ●   ●    ╱
               │   ●          ╱
            0.0└──────────────────────────  stated
               0.0        0.5         1.0
  you said 90% and were right 55% of the time   n=11
```

⭐ **A reliability curve, not a score.** *"When you said 80% sure, were you right
80% of the time?"* — and the diagonal is drawn, because the whole reading is
distance from it.

⚠️ **Never render this before 15 resolved predictions.** Below that the curve is
noise shaped like a finding, and a student who reads a random walk as *"I'm
getting worse"* will stop predicting — which destroys the only dataset that
matters. Under the threshold, show the count and nothing else.

### 4.7b Cost — visible, unglamorous, in settings

A student on a shared budget should be able to see what their questions cost,
by tier. **Not on the Bench** — it is not a next action, and putting money in
front of someone mid-thought changes what they ask. Settings, and the Share
page's footer for whoever is paying.

---

# 5. What happens to the existing design

Reconciling the ten features shipped in `ce03565` against the research.

| # | Feature | Verdict | Why |
|---|---|---|---|
| 1 | Local-graph depth slider | ✅ **keep** | scoping is the only genuinely useful graph affordance |
| 2 | Node size by degree | ⚠️ **change** | area is our best remaining magnitude channel — spend it on **DOI importance**, not raw degree. Degree alone over-weights mechanically-connected hubs |
| 3 | Node size / link opacity / spread sliders | ❌ **drop** | raw physics. Replace with semantic controls (§4.2) |
| 4 | Text-fade slider | ✅ **keep** — as semantic zoom | label density is a legitimate user variable; drive it from zoom rather than a slider |
| 5 | Timelapse | ⚠️ **change** | rebase on `valid_from` — **validation order, not creation order.** Becomes the Share artifact |
| 6 | Saved views | ✅ **keep** | it's the `View` object (Backend/01 §9). Now shareable |
| 7 | Key-node auto-detection | ✅ **keep** | god nodes, with mechanical-edge filtering |
| 8 | Surprising cross-project links | ✅ **keep and upgrade** | now computed by the crossover scorer with a generated `why`, not curated copy |
| 9 | Per-node suggested questions | ✅ **keep** | but derive from graph deficiencies, not templates |
| 10 | GRAPH_REPORT + copy/ask | ✅ **keep** | becomes the Log and Share surfaces |

**From the current screenshot, three things to fix beyond the list:**

1. ⚠️ **Hue is doing two jobs.** The legend shows four *projects* and four *kinds* in the same colour space. Hue can encode one categorical variable. Projects should be **spatial grouping** (regions), kinds get hue.
2. ⚠️ **644 nodes** is 13× the comprehension limit. Beautiful; not a product view.
3. ⚠️ **Labels collide** — *"Safety Brake"* over *"Fixed-Point Math"*, *"RTQS joint synchronization"* over *"DDS Transport"*. Needs the two-pass placement in `Frontend/03`.

**What the current design gets right and should survive:** the right-hand panel structure (Display / Layout / Insights / Views), *"Search a node, or ask your graph…"* as the entry point, and the Insights triad — Key nodes / Surprising links / Summarize — which maps almost exactly onto god nodes, the crossover scorer, and the report.

---

# 6. Mobile — viewable, not workable

Desktop-only for v1, **but it must be viewable on a phone.**

| Surface | Mobile |
|---|---|
| **Share** | ✅ fully responsive — mentors and investors will open it on a phone |
| **Bench** | ✅ read-only list |
| **Log** | ✅ readable |
| **Capture** | ⭐ **one affordance: photograph a scope trace, a burnt component, a whiteboard.** Timestamp, push to inbox, organise later on desktop |
| Map | ⚠️ degraded — top-10 list instead of a canvas |
| Review, Artifact | ❌ desktop |

**No feature parity.** Full mobile is an open question (`Frontend/04` F6).

---

# 7. Surviving week 3

The abandonment cliff (Research/07 §7.2) is the single most actionable retention finding: by week 3 the project shifts to debugging and time spent organising drops to zero.

**Every one of these is a design rule, not a feature:**

| Rule | Where |
|---|---|
| **Zero organisational tax.** One capture bar; the system routes it | §3 |
| **Nothing to maintain.** No folders, no tags to curate, no schema for the user to fill | Backend/01 §3.1 |
| **The home screen is about the project, never about the tool** | §4.1 |
| **No streaks, no time-in-tool, no completion percentages** | Research/07 §7.3 |
| **Progress = uncertainty resolved + components advanced**, never keystrokes | §4.7 |
| **Pseudo-ambient only** — milestone-triggered, silent between | `Frontend/03` |
| **It must be useful having done nothing** — the cold-start graph means the Bench has content on day one | Backend/07 §1 |

---

# 8. Onboarding — the first sixty seconds

⭐ **The graph is never empty, because it starts as a structured question.** An
empty graph is worse than no graph: it makes the product look broken at exactly
the moment a student decides whether to continue.

```
        ┌──────────────────────────────────────────────┐
   1    │  What are you trying to find out?             │
        │  ┌────────────────────────────────────────┐  │
        │  │ Can skin impedance track hydration?    │  │
        │  └────────────────────────────────────────┘  │
        └──────────────────────────────────────────────┘
                            ↓
   2    ⚠️  How will you know it worked?
        No number in that question. Add one — "to within 10%",
        "within 2 seconds", "better than the datasheet".
                            ↓
   3    ┌─ your graph, 8 seconds later ─────────────────┐
        │  1 question · 4 sub-questions · 12 concepts   │
        │  nothing proven yet — that's correct          │
        │                                               │
        │  ready to learn:  Capacitance · Charge        │
        └───────────────────────────────────────────────┘
```

**Step 2 is the most important screen in the product.** ⭐ *"How will you know
it worked?"* is the single most useful question anyone can ask an
undergraduate, and it fixes the cold start as a side effect — a vague question
produces a generic decomposition and a useless graph. **It is a nudge, never a
gate**: the student can proceed anyway and the graph is flagged low-confidence.

**Step 3 leads with what is NOT known.** The first screen shows the frontier,
not achievements. Nothing is validated at t=0 and saying so plainly is more
honest than an empty progress bar — and it sets the expectation that this
product is about what you have yet to do.

⚠️ **If nothing matched the skeleton** (a student outside embedded systems), say
so: *"I don't know this domain yet — you'll get question decomposition only."*
Silently degrading to a worse experience is how a student concludes the product
is bad rather than out of scope.

## 8.1 The first session's goal

**Get one Artifact with an `agreement` value before they leave.** That is the
loop closing, the first non-phantom node, and the first calibration point — and
onboarding should aim at whatever the *cheapest verifiable thing* nearby is:
flash a blink sketch, read a sensor once, confirm a supply rail.

## 8.2 Other empty states

⚠️ A blank screen reads as *"this tool requires upfront labour"* and is cognitively paralysing.

**Two layers, and they're complementary:**

1. **The cold-start graph** (Backend/07 §1) — the student types one sentence, and gets ~25 real nodes: their question decomposed, the concepts it depends on, prerequisite structure, and a computable frontier. **Real content about their actual project.**
2. **A functional template** — a worked example project (mock BOM, firmware placeholder, an integration checklist) sitting alongside, learnable by modification.

**No unskippable modal tour.** Technical audiences click through them without reading.

**Safe exploration:** visible undo everywhere, plus an accessible history log. When the cost of experimentation is zero, users teach themselves the deeper features.

---

# 9. What I'd build first

| | Surface | Why |
|---|---|---|
| **1** | **Artifact** (§4.3) | the moat, two days, testable by a real student in week 1 with no graph at all |
| **2** | **Bench** (§4.1) | the daily loop. Proves the ranking is any good |
| **3** | **Review** (§4.4) | gives us the accept rate — the most important early number |
| **4** | **Log + Share** (§4.5, §4.6) | the first thing worth showing anyone |
| **5** | **Map** (§4.2) | deliberately last. It's the secondary view |

**The Map is fifth.** That ordering is the whole thesis of this document made concrete — and if it feels wrong, that's the argument worth having.

---

# 💡 Visionary Vector — the share page is the product's real distribution

§4.6 was added because you said mentors, investors, and professors would look at this. It's worth taking further than a read-only mode.

Consider what that page actually contains: a verifiable, timestamped, cryptographically-chained record of **what a student predicted, what they measured, when, in what order — including everything that failed** — with a calibration curve showing their judgement improving over six weeks.

**Nothing in education currently produces that artifact.** A transcript records which courses you sat in. A résumé line says *"built a biosensor prototype"* and is unverifiable, and every admissions committee and hiring manager knows it. A GitHub profile shows code, not reasoning.

So the Share page isn't a feature — **it's the reason a student would tell another student about Nexus.** Every project produces one, it's public by choice, it has a URL, and it contains something they genuinely want seen. That's organic distribution built into the core loop rather than bolted on, and it costs almost nothing because the ledger already holds every input.

The sharper version: **the calibration curve is a credential.** If it holds up — if predictions measurably improve — then the thing we're building isn't a note-taking tool that happens to have a graph. It's the first system that can produce **evidence of engineering judgement**, which is the one thing every employer claims to select for and nobody can currently measure.

That would also explain why the graph should be an engine. **The output isn't the map. It's the proof.**

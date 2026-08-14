# Mind Graph — Frontend Assessment & Design Corrections

**Three things:** what R3 forces me to change in my own design (08/09), an honest assessment of the Mind Graph you've already built, and the corrected frontend architecture.
**Date:** 2026-08-07

> **Is R3 enough?** Yes. 16 citations, it answered all six items, and it delivered the thing I most wanted — **empirical null and negative results on the interaction patterns I had recommended.** Two of them contradict me. That's the most useful research outcome available, and it's why item 5 was in the prompt.

---

# PART 1 — Corrections to my own design

## 1.1 ⚠️ "Layout stability is a correctness property" — **overstated**

**What I claimed** (01 §12.6, 08): community/layout stability is a correctness property, not polish. *"If a student's graph re-clusters and their canvas rearranges, you have destroyed the one thing a mind graph is for."*

**What the evidence says** (R3 §4): Archambault et al., independent within-participant experiment, **48 tasks per user**, testing whether preserving the mental map (keeping node positions stable through dynamic updates) improves orientation and task completion.

> **It did not have a significant effect on performance** — for either animated transitions or small multiples. Users **explicitly preferred** the preserved mental map, but the subjective preference **yielded no measurable improvement in actual task execution.**

**Corrected position:** mental-map preservation is a **satisfaction and trust property, not a task-performance one.**

Keep it — users prefer it, and R3 §1 shows it's *cheap* (coordinate pinning via `fx`/`fy`, injecting children at parent coordinates). But:
- **Don't justify engineering spend on it with performance claims.** It won't show up in task times.
- **Don't over-invest.** Elaborate incremental-layout machinery to preserve positions perfectly is not earning what I implied.
- **Do keep community-identity stability** — that argument was about *labels being wrong*, which is a correctness issue and untouched by this result. A region that silently becomes a different region still lies. Separate claim, still stands.

## 1.2 ⚠️ "Expand-on-demand + DOI + semantic zoom is the answer" — **incomplete, and partly contradicted**

**What I claimed** (06 §2.4, 08): the ~50-node comprehension limit is survivable because the three production patterns — expand-on-demand, DOI filtering, semantic zoom — exist precisely to prevent it.

**What the evidence says** (R3 §4): a controlled independent experiment, 19 participants, comparing **focus+context** (the family that expand-on-demand and semantic zoom belong to), **overview+detail**, and raw zooming across display sizes.

> Focus+context is **relatively more difficult to use at small display sizes.** Across **all** display sizes, **overview+detail proved superior — particularly for tasks requiring users to compare items.**

**This is a direct hit on my recommendation**, and comparison tasks are exactly what a student does (*"how does this measurement relate to that claim?"*).

**Corrected position:** the answer is **not** focus+context alone. It is **overview + detail**: two coordinated views, not one distorted view.

```
┌─────────────────────────────┬───────────────┐
│   DETAIL — the working view │  OVERVIEW     │
│   ≤ 50 nodes, DOI-ranked    │  the whole    │
│   expand-on-demand          │  project,     │
│   this is where you work    │  abstracted,  │
│                             │  always on,   │
│                             │  shows where  │
│                             │  you are      │
└─────────────────────────────┴───────────────┘
```

The overview is *not* a shrunken copy of the graph — that's the hairball again. It's an **abstracted** view: communities as blobs, phantom counts, contradiction markers, and a viewport indicator. Persistent, small, cheap.

**Caveat, honestly:** R3 §4 also notes the evidence base is weak — **three-quarters of graph-visualisation evaluations use graphs of ≤100 nodes**, and one attempt to evaluate focus+context on a complex UML diagram produced such extreme between-subject variance that the data had to be discarded entirely. So this is *the best available evidence*, not a settled result. But its direction is against pure focus+context, and overview+detail costs us little to add.

## 1.3 ✅ Confirmed: the approval-queue design

R3 §3 independently validates §5 of the extraction contract:

- **Bulk review actions** — multi-select accept/reject rather than serial review. Already specified; now evidenced.
- **Agreement-based sampling** — production systems route to humans only **below ~80% agreement**, bypassing consensus items. My 0.85 auto-accept threshold sits in the right band.
- **Vertical annotation sidebars** — metadata beside the item, not behind tabs, reduces scroll fatigue.

⚠️ And a hard number that should scare us: trained professional reviewer pods handle **2,000–12,000 AI outputs/day**, and the true operating cost of a review queue runs **4–6× the platform's sticker price**. Our reviewer is one unpaid undergraduate with a deadline. **Budget 20–30 decisions per session.** Auto-accept calibration isn't an optimisation, it's survival.

---

# PART 2 — Assessment of the Mind Graph you've built

Read from `unpacked_demo/assets/33a3ad5f…` (`MindGraphView`) and the landing page section.

## 2.1 ⭐ The headline: your ontology already converged with mine

Your `MG_TAG` map:

```js
core: "YOU"   idea: "PROJECT"  concept: "CLAIM"  note: "ARTIFACT"
gap:  "QUESTION"  risk: "REBUT"  signal: "SOURCE"  active: "ACTION"
```

Against the six types I derived independently in 08:

| Your UI tag | My backend type | Match |
|---|---|---|
| CLAIM | `Claim` | ✅ exact |
| ARTIFACT | `Artifact` | ✅ exact |
| QUESTION | `Question` | ✅ exact |
| SOURCE | `Source` | ✅ exact |
| PROJECT | `Question(kind=project)` | ✅ same thing, different level |
| YOU | — | ⚠️ **you have something I don't** |
| REBUT | `contradicts` **edge** | ⚠️ divergence |
| ACTION | frontier engine **output** | ⚠️ divergence |

**Four exact matches out of six, derived independently.** That's a strong signal for both — it suggests the ontology is being forced by the domain rather than invented, which is the best thing you can learn about a schema.

## 2.2 The four divergences, and who's right

### (a) `CLAIM` is doing double duty — **this one matters most**

Your `MG_ROLE` reads `concept: "Concept you know"` but tags it `CLAIM`. So a *unit of knowledge* and an *assertion* are the same node type.

**They can't be.** The knowledge-state predicate — the entire interface to the frontier engine (11 §7) — needs to distinguish:
- *"the student knows I²C"* → a **Concept**, in `K` or not
- *"the student asserts the ADC saturates at 3.1 V"* → a **Claim**, true or false, supported or not

Conflated, you can't compute an outer fringe, can't map a transcript, and can't tell "understands the idea" from "believes the statement."

**Verdict: split them.** Cheapest fix in this document, and everything in 11 depends on it.

### (b) `REBUT` as a node — **make it an edge, keep the visuals**

Red risk nodes look great and read instantly. But as a *node*, "risk" can only be pointed at; it can't say **what** contradicts **what**. You can't count unresolved tensions, can't resolve one, can't cascade when the underlying evidence is retracted.

**Verdict: `contradicts` as an edge, rendered in your existing red visual language.** You lose nothing visually and gain a queryable, resolvable, cascading object. (This is also the one relation the extraction contract routes to human review every time.)

### (c) `ACTION` as a node — **should be computed, not stored**

Actions are the frontier engine's *output*: a ranked list recomputed as the graph changes. Persisted as nodes they go stale, accumulate, and become a graveyard of things you were once told to do.

**Verdict: render as an overlay/panel driven by `frontier()`, not as persisted nodes.** Keep the white "next action" styling — attach it to the top-ranked frontier item.

### (d) `YOU` / identity core — ⭐ **you're right and I was wrong**

My backend has no equivalent, and it needs one. The DOI function `D(x, focus·lens)` needs an origin when there's no active focus — and *"distance from the student"* is the correct default. It's also the natural anchor for a stable layout centre.

**Verdict: adopt it backwards into the backend.** A single per-user `Root` node, or a reserved `Question(kind=identity)`. Your UI intuition found something the architecture was missing.

## 2.3 Functionality — what maps, what's missing

**Maps cleanly to backend capability I'd specified anyway:**

| Your feature | Backend counterpart |
|---|---|
| local-graph depth slider (1/2/3-hop) | `neighbors(id, hops)` — and now the **detail** pane of overview+detail |
| node size by degree | `API` centrality term in DOI |
| key-node auto-detection (top-8 degree) | god nodes, with mechanical-edge filtering |
| surprising cross-project links + insight text | crossover scoring (01 §13.11) |
| per-node suggested Vera questions | question generation from graph deficiencies |
| GRAPH_REPORT + copy/ask-Vera | the report artifact |
| saved views (filter+focus combos) | ⭐ **this is the lens/angle-prompt primitive** — better than I gave you credit for |
| text-fade slider | label density; keep, and let semantic zoom drive it |
| timelapse | ⚠️ rebase on `valid_from` (validation order), not creation order |

**Missing, and the gaps are the interesting part:**

1. ⭐ **Nothing about outcome.** No predicted, no measured, no "did it work." Given 07, this is *the* functional gap — the demo shows a graph of what you know, not a record of what you proved. The `Artifact` nodes are labels, not measurements.
2. **No review/approval surface.** Nowhere to accept or reject a proposed edge. With a ~2% fabrication rate this isn't optional.
3. **No phantoms.** `gap` exists as a colour, but nothing is *"referenced by something and never validated."* Gaps are currently asserted; they should be generated by reference (02 §7.1).
4. **No contradiction resolution.** Red nodes are decoration; nothing resolves them.
5. **No overview pane** — see §1.2.

## 2.4 UI — honest read

**Good:**
- Colour-by-kind with a fixed legend. This is exactly the "ship canonical groups instead of making users write search queries" recommendation (02 §8.13). Nailed.
- The curated surprising-links copy is genuinely the best thing in the demo — a connection *with a reason attached* is what turns a graph into a mentor.
- Controls are grouped and legible; the macOS window framing works.
- Deterministic seeded RNG (`mgRng`) — layout is reproducible. Good instinct, and it's the cheap half of mental-map preservation.

**Problems:**

| Issue | Severity |
|---|---|
| **~780 nodes on landing, ~340 in demo** — 7–15× past the measured comprehension limit (06 §2) | **high** as product default, fine as marketing |
| **Sphere/starburst layout is semantically arbitrary** — position carries no meaning. With DOI available, radial distance should encode relevance to focus | **high** — this is free meaning currently unused |
| **Layout runs on the main thread** | medium — R3 §1: offload to a WebWorker or the UI locks during expansion |
| Filler nodes exist purely for density | fine for a demo; must not survive into product |
| No keyboard navigation, no screen-reader path | medium — see §3.4 |

**On the sphere layout specifically:** it's the single highest-leverage visual change available. Right now it says "there is a lot here." If radial distance encoded DOI, the *same picture* would say "here is what matters to you right now, and here is what's peripheral" — at no cost in beauty and a large gain in meaning.

---

# PART 3 — Corrected frontend architecture

## 3.1 Layout

```
┌──────────────┬────────────────────────────────┬──────────────┐
│  LEFT        │   MAIN — detail view           │  RIGHT       │
│  projects    │   ≤50 nodes, DOI-ranked        │  chat +      │
│  sources     │   expand-on-demand             │  citations   │
│  notes       │   pinned focus                 │              │
│  ─────────   │                                │  ──────────  │
│  OVERVIEW    │                                │  REVIEW      │
│  abstracted  │                                │  queue       │
│  communities │                                │  (batched)   │
│  + viewport  │                                │              │
└──────────────┴────────────────────────────────┴──────────────┘
```

Three panels (validated by Atlas, 03 §5) **plus a persistent overview** (forced by R3 §4). The overview lives in the left rail because it's navigation, not work.

## 3.2 Rendering and layout mechanics — straight from R3 §1

```
sigma.js + graphology                  render
graphology-layout-forceatlas2/worker   layout — ⭐ IN A WEB WORKER
```

| Technique | Why |
|---|---|
| **Inject expanded children at the parent's exact x/y** | continuous FA2 repulsion pushes them outward organically — **no "big bang" layout shift.** This is the whole trick, and it's three lines |
| **Pin the focus** (`fx`/`fy`; ignored by the velocity Verlet integrator) | anchors what the user is looking at while new branches arrange around it |
| **Barnes-Hut** | repulsion from O(n²) to O(n log n) |
| **`strongGravityMode`** | stops disconnected components drifting off-canvas — we will have plenty (phantoms, orphan notes) |
| **FA2 swinging constraint** | if a node oscillates between frames, its local speed is cut — prevents local chaos rippling through the topology |
| **Layout in a worker, render on main** | a global force sim on the main thread locks the UI. Non-negotiable |

**Not cola.js**: better structural guarantees, but R3 reports it struggles to hold 60 fps during continuous incremental expansion — which is our primary interaction.

## 3.3 Sync — R3 §2 matches the backend exactly

```
BACKEND                          CLIENT
ledger append                    embedded SQLite (WASM)
   │                                  │
   └─ sync engine ships delta ───────▶ patch local DB
                                      │
                                 reactive query re-executes
                                 (top-50 by DOI)
                                      │
                                 renderer DIFFS new list vs canvas objects
                                      │
                                 existing nodes KEEP x/y
                                 worker layout is "nudged"
```

Two things worth stating plainly:

**This is the natural client for an event-sourced backend, and it wasn't designed to be.** SQLite at both ends, deltas rather than payload diffs, a reactive query as the DOI selection. The architecture in 08/09 and the frontend architecture in R3 fit together without adaptation — which is a good sign that both are following the grain of the problem.

**Optimistic UI comes free.** A student's own edit writes to the local DB immediately and renders instantly; the sync engine reconciles in the background. That matters because our expensive operations (extraction, clustering) are seconds-to-minutes and must never block a keystroke.

Candidates: PowerSync (native Rust + SQLite SDKs) or Replicache. Evaluate against plain SSE + a client-side store — for a single-user, single-device v1, the simpler option may well win, and the sync engine can arrive with collaboration.

## 3.4 Accessibility — R3 §5, and it's cheap for us

**The honest finding:** ARIA fundamentally does not work for graphs. `aria-describedby` collapses to a single continuous paragraph, so **screen readers lose all structural and relational information**, and ARIA's linear serial navigation makes tabbing a complex graph both excruciating and uninformative about topology.

**The established production fallback**, and it's nearly free for us:

```html
<div role="presentation" aria-hidden="true"> …canvas… </div>
<table class="sr-only">  <!-- visually hidden, fully accessible -->
  <caption>Mind graph: 47 nodes shown, ranked by relevance</caption>
  …role=row / role=cell over the ranked list and its relations…
</table>
```

We already compute a ranked top-50 list with typed relations — **the accessible representation is the data we're rendering from.** Add `tabIndex="0"` and 3:1 contrast on interactive elements for WCAG 2.1 AA, and ship the hidden table.

Worth watching: **Data Navigator** (MIT / Frank Elavsky) decouples visual encoding from navigation rules so keyboard and screen-reader users traverse structure dynamically rather than linearly. If it matures, it's the real answer.

## 3.5 The review queue

Per R3 §3 and extraction contract §5: **bulk multi-select accept/reject**, agreement-based routing (~80% threshold), metadata in a **vertical sidebar** beside the item, batched into one surface. **Budget 20–30 decisions per session** — not hundreds.

---

# PART 4 — What I'd change first

| # | Change | Effort | Why |
|---|---|---|---|
| 1 | **Split `Concept` from `Claim`** | small | unblocks the knowledge state, the frontier engine, and transcript mapping. Everything in 11 depends on it |
| 2 | **Add the outcome loop** — predicted / measured / agreement on Artifacts | medium | ⭐ the moat. Currently entirely absent from the UI |
| 3 | **Cap the default view at ~50 and add the overview pane** | medium | the measured comprehension limit + the overview+detail correction |
| 4 | **Radial distance = DOI** instead of an arbitrary sphere | small | free meaning; the single highest-leverage visual change |
| 5 | **`contradicts` as an edge**, same red styling | small | makes tension countable and resolvable |
| 6 | **Move layout to a WebWorker** | small | R3 §1; prevents UI lockup on expansion |
| 7 | **Render phantoms** — referenced-but-unvalidated, hollow | medium | gaps generated by reference, not asserted |
| 8 | **Actions become a `frontier()` panel**, not stored nodes | small | stops the action graveyard |
| 9 | **Hidden accessible table** | small | near-free given the ranked list already exists |
| 10 | **Timelapse on `valid_from`** | small | replay by validation order — the shareable artifact |

Items 1, 4, 5, 6, 8 are all small and mostly independent. That's a good week.

---

# 💡 Visionary Vector — the overview pane is the calibration display

R3 forced the overview pane on me as a *correction* — focus+context loses to overview+detail, so add a small abstracted view. Purely defensive.

But look at what an overview of *our* graph can show that no other product's overview could. Obsidian's overview is a smaller hairball. Atlas's is a scatter plot. Ours has access to something categorically different: **every Artifact carries `predicted`, `measured`, and `agreement`.**

So the overview doesn't have to show *structure* at all. It can show **standing**:

```
  ●●●●●●●○○     7 of 9 predictions matched          ← calibration
  ▲▲            2 unresolved contradictions          ← tension
  ○○○○○         5 gaps reachable right now           ← frontier
  ⋯⋯⋯           3 claims stale since Tuesday         ← drift
```

That's a **one-glance state-of-your-thinking display**, computable entirely from fields the backend already has, occupying a corner of the screen, and answering the question a student actually opens the app with — *"where am I?"* — which the graph itself, at 50 nodes or 780, has never answered well.

And it reframes the ~50-node limit entirely. The graph stops needing to be an overview, because **it was never good at being one.** The graph becomes the *working surface* — where you manipulate fifty things — and the overview becomes a *dashboard of epistemic state*. Two views doing two jobs, each good at its own.

The deepest version: over weeks, the calibration bar is the only number in the product that reflects whether the student is actually getting better at engineering rather than merely accumulating notes. Put it where they see it every session, and the product's north-star metric and the student's own progress indicator become **the same object on screen.**

---

*Ends. Corrections to 08 §1.2/§7 and 09 as noted — the layout-stability justification and the focus+context recommendation are the two that changed.*

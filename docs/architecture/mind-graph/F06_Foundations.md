# Frontend Foundations

**Frontend / 06.** The three things that block everything else: **node anatomy**, **design tokens**, and the **stack + data flow**.
**Deliberately not here:** screen specs. Those get written after backend Phase 0, because F1 and F11 could still relocate the product and specs written now would be thrown away.
**Date:** 2026-08-10

---

# 1. ⭐ Node anatomy

The encoding matrix in `Frontend/02` is theoretical until one node is drawn with all of it composited. This is where **F4** gets tested — and where it might fail.

## 1.1 The composite

```
                    ╭─── rim notch (contested)
                    │
              ┌─────▼─────┐
             ╱             ╲
            │   ╭───────╮   │  ← outer circle
            │   │       │   │     area       = importance (DOI)
            │   │   ◷   │   │     hue        = type
            │   │       │   │     saturation = confidence  (VSUP)
            │   ╰───────╯   │     fill       = support state
             ╲             ╱      dash       = phantom
              └───────────┘
                    ▲   ▲
                    │   ╰── inner ring = corroboration (0/1/2+)
                    ╰────── glyph = stale (◷) / other status
                 label
```

## 1.2 ⚠️ The legibility floor — and why it resolves itself

Not every encoding survives at every size. Measured against a 6px baseline:

| Diameter | What is legible |
|---|---|
| **12px** | hue, fill style only |
| **16px** | + rim notch |
| **20px** | + inner ring |
| **28px** | + status glyph |
| **36px+** | + inline label |

**This looks like a problem and isn't.** Diameter encodes *importance*, so:

> **The nodes that can carry the least information are the ones you need to know the least about.**

Encoding richness and importance are aligned rather than competing. A peripheral node shows type and support; the node you're focused on shows everything. **Progressive disclosure by size, for free.**

**Rule:** anything below 12px renders as a plain dot with hue only. If the DOI range would push nodes below that, **reduce K** rather than shrinking further.

## 1.3 Concrete geometry

```
diameter      = clamp(12, 12 + 28 × doi_normalised, 40)   px
outer stroke  = 1.5px, colour = fill colour at +18% lightness
inner ring    = inset 4px, stroke width 1px (1 result) / 2.5px (2+)
rim notch     = 4px wedge at 45°, alert colour, on the stroke
glyph         = 8px, centred, 70% opacity
phantom       = perimeter dash 3-2, fill none
label offset  = diameter/2 + 6px, top-right (naive pass)
```

## 1.4 Fill styles carry support

| Support | Fill | Reads as |
|---|---|---|
| `supported` | solid at 85% opacity | settled |
| `tentative` | solid at 45% | present but thin |
| `unsupported` | 20% + 1px solid stroke | hollowed out |
| `contested` | solid + **rim notch** + alert stroke | flagged |
| phantom | none + dashed perimeter | ⭐ an opening, not a hole |

**Phantoms should read as opportunity.** Dashed but *bright* — a slot waiting to be filled. If they look like errors, the frontier engine's whole output looks like a defect list.

## 1.5 By zoom level

| Zoom | Node | Label |
|---|---|---|
| **macro** | 12px dots, hue only | region names only |
| **mid** | full anatomy from 16px up | truncated identifiers |
| **near** | full anatomy + glyphs | full labels |
| **focus** | selected node at 40px | full label + everything in the context pane |

## 1.6 ⭐ How to test F4 — do this before any UI

Half a day, and it can invalidate the encoding matrix:

1. Render all six hues as nodes at **12 / 16 / 20 / 28 / 40px** on `#0B0D10`.
2. Render each at **four confidence levels** (full chroma → grey).
3. Run through a **CVD simulator** — deuteranopia, protanopia, tritanopia.
4. Ask five people to sort them by type, then by confidence.

**Failure condition:** if type accuracy at 16px is below ~80%, or if any two hues are confused under deuteranopia, **collapse to four or five node types** and re-run. Better to lose a type than to ship an encoding nobody can read.

---

# 2. Design tokens

Everything as **CSS custom properties** — non-negotiable, because the high-contrast and reduced-motion modes must switch at runtime without a rebuild.

## 2.1 Colour

```css
/* surfaces */
--bg:            #0B0D10;   --surface:       #14171C;
--surface-2:     #1B1F26;   --border:        #262B33;

/* text */
--text:          #E8E6E3;   --text-muted:    #9BA1AA;
--text-dim:      #6B7280;

/* interface accent — NEVER used in the graph */
--accent:        #FF6B2C;   --accent-hover:  #FF8351;
--accent-dim:    #7A3417;

/* node types — desaturated Oklab pastels */
--type-concept:  #7EC8C0;   --type-question: #E0B978;
--type-claim:    #B49BD8;   --type-artifact: #8FD18A;
--type-source:   #8FA9C9;   --type-note:     #A8A29A;

/* semantic */
--support:       #7EC8C0;   /* cool  — supporting edges */
--contradict:    #E4756B;   /* warm  — contradicting edges, rim notch */
--mention:       #4A5058;   /* grey  — mentioning edges */
--stale:         #8A7F6B;

/* VSUP — confidence ramp, applied as chroma multiplier */
--vsup-1_00: 1.00;  --vsup-0_85: 0.72;  --vsup-0_75: 0.58;
--vsup-0_65: 0.44;  --vsup-0_55: 0.32;  --vsup-amb:  0.12;
```

**The VSUP ramp is a multiplier on chroma in Oklch**, not six separate hex values — so it composes with any type hue and stays perceptually even.

## 2.2 Space, type, radius, elevation

```css
/* 4px base scale */
--s-1: 4px;  --s-2: 8px;   --s-3: 12px;  --s-4: 16px;
--s-5: 24px; --s-6: 32px;  --s-7: 48px;  --s-8: 64px;

/* type — 1.20 ratio */
--fs-xs: 11px;  --fs-sm: 13px;  --fs-base: 15px;
--fs-lg: 18px;  --fs-xl: 22px;  --fs-2xl: 27px;
--lh-tight: 1.25;  --lh-base: 1.5;  --lh-loose: 1.7;

--font-mono: "Berkeley Mono", ui-monospace, "SF Mono", monospace;
--font-sans: "Inter", system-ui, sans-serif;
--fnum: tabular-nums;   /* all numeric data */

--r-sm: 4px;  --r-md: 8px;  --r-lg: 12px;  --r-full: 999px;

--e-1: 0 1px 2px rgb(0 0 0 / .3);      /* cards      */
--e-2: 0 4px 12px rgb(0 0 0 / .4);     /* panels     */
--e-3: 0 8px 32px rgb(0 0 0 / .5);     /* selection  */
```

**Monospace for every identifier, value, and measurement.** Sans for prose and UI. This matches the current design's instinct, which was right.

## 2.3 Layout

```css
--pane-nav: 240px;   --pane-ctx: 320px;
--capture-h: 56px;   --topbar-h: 44px;
--map-max-nodes: 50; --map-cold-start-max: 25;
```

## 2.4 Motion

```css
--d-hover: 80ms;   --d-select: 120ms;  --d-pane: 200ms;
--d-stage-1: 180ms; --d-stage-2: 140ms; --d-stage-3: 260ms;
--d-snapback: 240ms; --d-label: 300ms;

--ease-out: cubic-bezier(.2,.8,.3,1);
--ease-inout: cubic-bezier(.4,0,.2,1);
--ease-back: cubic-bezier(.5,-.4,.6,1.3);   /* snap-back rejection */
```

**Nothing exceeds 600ms.** Beyond that it stops reading as feedback and starts reading as waiting.

## 2.5 The two accessibility modes

```css
@media (prefers-reduced-motion: reduce) {
  :root { --d-hover:0ms; --d-select:0ms; --d-stage-1:0ms;
          --d-stage-2:0ms; --d-stage-3:0ms; --d-snapback:0ms; }
  /* layout computes in the Worker and crossfades — no iteration rendered */
}

:root[data-contrast="high"] {
  /* strip categorical hue entirely; type becomes hatch pattern */
  --type-concept:  var(--text);  /* + pattern: diagonal-45  */
  --type-question: var(--text);  /* + pattern: diagonal-135 */
  --type-claim:    var(--text);  /* + pattern: cross-hatch  */
  --type-artifact: var(--text);  /* + pattern: stipple      */
  --type-source:   var(--text);  /* + pattern: horizontal   */
  --type-note:     var(--text);  /* + pattern: none         */
}
```

**High-contrast mode is a real requirement, not a checkbox.** ~15% of users have some CVD, and stripping hue for geometric hatching keeps full data legibility with colour removed from the equation entirely.

## 2.6 Contrast floors

| Element | Minimum |
|---|---|
| body text on surface | 4.5:1 |
| node stroke on canvas | 3:1 |
| label over node fill | 4.5:1 |
| focus ring | 3:1, 4.5:1 preferred |
| edges | exempt, but ≥35% opacity floor — below that they read as absence |

---

# 3. Stack

## 3.1 The decisions

| Layer | Choice | Why |
|---|---|---|
| **Framework** | **React + TypeScript** | ecosystem, sigma bindings exist, hireable. Svelte is lighter but the graph work dominates and React's ecosystem wins there |
| **Build** | **Vite** | fast, Worker support out of the box |
| ⭐ **Graph data** | **graphology** | **runs in Node *and* the browser — backend and frontend share one graph model.** This is the single highest-leverage choice here |
| **Graph render** | **sigma.js v3** | WebGL, instance-based, MIT. Comfortable to ~100k edges — and we cap at 50 nodes, so the ceiling never binds |
| **Layout** | **`graphology-layout-forceatlas2/worker`** | continuous, Barnes-Hut, designed for exactly the 10–10k range, runs off the main thread |
| **Server state** | **TanStack Query** | caching, optimistic mutations, background refetch — the optimistic-UI requirement without a sync engine |
| **UI state** | **Zustand** | small, no boilerplate, easy to serialise into a `View` |
| **Styling** | **CSS custom properties + CSS Modules** | tokens must be runtime-switchable for §2.5. Tailwind is fine on top; the tokens are not negotiable |
| **Icons** | **Lucide** | consistent, tree-shakeable |
| **Charts** (calibration curve) | **Observable Plot** | small, declarative, honest defaults |

## 3.2 What we're deliberately not using yet

| Deferred | Until |
|---|---|
| **Sync engine** (PowerSync / Replicache) | collaboration is real. Single-user v1 doesn't need it, and TanStack Query covers optimistic updates |
| **IndexedDB local store** | offline is a requirement. In-memory + query cache is enough for v1 |
| **cosmos.gl / Embedding Atlas** | a project-landscape view at real scale exists. sigma handles 50 nodes trivially |
| **Cytoscape, D3-force, PIXI** | not needed — sigma + graphology covers the case, and mixing renderers is how you end up maintaining two |

## 3.3 Worker topology

```
main thread          React · sigma render · interaction
  │
  ├─ layout.worker   ForceAtlas2, streams x/y with dampened interpolation
  ├─ labels.worker   two-pass placement, crossfades on settle
  └─ search.worker   local trigram index for instant filtering
```

**Never run the force simulation on the main thread.** It locks the UI, and it's the specific failure mode behind Obsidian's single-core freeze.

---

# 4. Data flow

## 4.1 The shape

```
Graph API  ──►  TanStack Query cache  ──►  graphology instance  ──►  sigma
   ▲                    │                        │
   │                    ▼                        ▼
   └── mutations ── optimistic patch ──── layout.worker (x/y)
```

**The graphology instance is the single source of truth in the client.** Query results patch it; sigma renders from it; the Worker positions it. One model, three consumers.

## 4.2 Reads

| Call | Cache | Notes |
|---|---|---|
| `frontier(project, k)` | 30s stale | the Bench. Refetch on window focus |
| `query(text, lens, k)` | keyed by text+lens | cap at K; **always render the justified path** |
| `neighbors(id, hops)` | keyed by id+hops | drives expansion |
| `explain(id)` | keyed by id | the context pane |
| `tensions(project)` | 60s stale | |
| `stats(project)` | 5min stale | the overview dashboard |
| `timeline(project, t)` | on demand | Share page time-lapse |

## 4.3 Writes are optimistic, always

```
user acts
  │
  ├─► patch graphology immediately, render          ← instant
  ├─► POST to the API
  │      ├─ success  → reconcile (usually a no-op)
  │      └─ failure  → roll back + snap-back animation + reason
  └─► nudge the layout worker (don't restart it)
```

**Every mutation carries an idempotency key** (Backend/07 §3.4), so a retry after a timeout can't double-write to an append-only ledger.

## 4.4 The one thing that isn't optimistic

⭐ **`validate()` — recording a measurement — is never optimistic.** It waits for the server.

Everything else can be rolled back harmlessly. An outcome is a claim about physical reality and the foundation of the calibration record; showing it as recorded before it *is* recorded risks a student believing a measurement was saved when it wasn't. **Correctness beats snappiness at exactly one place in this product, and this is it.**

## 4.5 Long operations

Ingestion returns a job id immediately. The client polls (or takes SSE) and shows a card in the left pane with **stage-level progress** — *"extracting… resolving… 12 proposals ready"*. Never a spinner, never a live feed in the periphery.

---

# 5. What's still not specified

Deliberately, and why:

| Missing | Waiting on |
|---|---|
| **Screen specs** (dimensions, states, component anatomy per surface) | F1 and F11 — either could relocate the product |
| **Search / "ask your graph" flow** | the API's actual answer shape, which needs Phase 0 |
| **Sources reader** (PDF + span → claim) | the extraction pipeline being real |
| **Settings, notifications, offline** | not blocking anything |
| **Frontend build plan** | screen specs |

**None of these blocks starting.** The three things that did block — node anatomy, tokens, stack — are now settled.

---

# 6. What to do next, concretely

```
1. Run the F4 palette test                 half a day  ← may invalidate §1
2. Backend Phase 0 (ledger + projector)    1–2 days
3. Artifact CLI                            1–2 days    ← the moat, testable
4. Then: screen specs, against real data
```

**Backend Phase 0 is still the higher-value move.** Nothing in the frontend can be tested against real data until the ledger exists — and a screen spec written against imagined data is a screen spec you rewrite.

---

# 💡 Visionary Vector — one graph model, both sides

§3.1 picks graphology mostly for pragmatic reasons: it's the data layer sigma expects, and it carries the algorithms we need.

But it runs in **Node as well as the browser**, and that has a consequence worth planning for rather than discovering.

The backend already builds a graph (Backend/01 §10 — in-process NetworkX). The frontend builds a graph. Today those are two implementations of the same structure in two languages, which means **two places for the traversal logic to disagree** — and a disagreement between what the server thinks is connected and what the client draws is the kind of bug that takes a week to find and destroys trust in the visualisation permanently.

If both sides run graphology, the projection logic, the DOI ranking, and the traversal are **the same code**. The server can compute a view and ship it; the client can recompute it locally for instant interaction; and they provably agree because it's one implementation.

That also unlocks something we haven't designed: **the client can run the frontier engine offline.** Ranking is a pure function of the graph plus the sidecars. If the client holds both, a student on a lab bench with no signal can still ask *"what should I do next?"* — which is precisely the week-3 moment where the research says we lose them.

The cost is one decision made now instead of later: **make the backend's graph layer graphology-compatible rather than NetworkX-shaped.** Same algorithms, same semantics, one model. It costs almost nothing today and is expensive to retrofit once both sides have their own traversal code.

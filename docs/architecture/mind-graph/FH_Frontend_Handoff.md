# Frontend Handoff — start here

**For:** Antigravity / Gemini, or any assistant picking up frontend
implementation cold.
**Date:** 2026-08-10
**Read time:** 15 minutes. Then you can start.

> ⚠️ **Do not start with step 1. Start with step 0** (§6). F4 can invalidate the
> palette, the node chip and the encoding matrix, and it takes half a day.
> Everything below assumes it passed.

---

# 1. What exists right now

| | Status |
|---|---|
| **Backend** | ⭐ **Code-complete, 300 tests passing.** `mind-graph/Backend_build/` |
| **Backend design** | `Backend_design/01–11`. All twelve open questions closed |
| **Frontend design** | ⭐ **Complete end to end.** `Frontend_design/01–07` |
| **Frontend code** | **None.** `Frontend_build/` is empty. That is your job |

**Run the backend and look at it before writing any UI:**

```bash
cd mind-graph/Backend_build
python3 -m pytest -q                       # 300 pass
python3 -m mindgraph.cli --root /tmp/demo start "Can skin impedance track hydration to within 10 percent?"
python3 -m mindgraph.cli --root /tmp/demo next
python3 -m mindgraph.cli --root /tmp/demo ingest <some files>
python3 -m mindgraph.cli --root /tmp/demo query impedance
```

⭐ **Every screen you build has a CLI equivalent already working.** If you are
unsure what a surface should show, run its command and look at the real shape.

---

# 2. The one decision everything follows from

> **The graph is an engine. The interface is a workbench.**

Node-link diagrams show null-to-negative learning outcomes, comprehension
collapses past ~50 nodes, and every capability the graph genuinely provides is
machine-facing. So:

- The home screen is a **ranked list of next actions**, not a canvas.
- The Map is a **secondary view**, built **last** (§6 step 8).
- ⭐ **The ranking function is the product.** Every "show more" affordance is a
  decision not to rank well.

⚠️ **If you find yourself making the graph prettier before the Bench works, stop.**
That is the failure mode this decision exists to prevent.

---

# 3. Read in this order

| # | Document | Why |
|---|---|---|
| 1 | `Frontend_design/05_Summary` | 10pp, the whole design. **§10.1a lists what was added last** |
| 2 | `Frontend_design/07_Screen_Specs_and_Build` | component anatomy, states, settings, offline, the build plan you will follow |
| 3 | `Frontend_design/06_Foundations` | tokens, stack, worker topology, data flow. **Copy §2 verbatim into code** |
| 4 | `Frontend_design/01_Frontend_Design` | the surfaces in detail. Reference, not cover-to-cover |
| 5 | `Frontend_design/02_Visual_System` | the encoding matrix. **Read §2 before drawing anything** |
| 6 | `Frontend_design/03_Interaction_and_Motion` | drag, undo, keyboard, motion |
| 7 | `Frontend_design/04_Uncertainty_Register` | ⚠️ the eleven doubts. **F4, F8, F11 matter** |

**Skip** `Backend_design/*` unless you are wiring a specific call — §5 has what
you need.

---

# 4. The stack, already decided

```
React + TypeScript · Vite
graphology            ⭐ same graph model as the backend
sigma.js v3           WebGL render, capped at 50 nodes
forceatlas2/worker    layout, off the main thread
TanStack Query        server state, optimistic mutations
Zustand               UI state, serialisable into a View
CSS custom properties + CSS Modules    ⚠️ tokens must be runtime-switchable
Lucide · Observable Plot
```

**Deliberately NOT yet:** sync engine, IndexedDB, cosmos.gl, Cytoscape/D3/PIXI.
Reasons in `06 §3.2`. ⚠️ **Do not add a second renderer** — mixing them is how
you end up maintaining two.

**Data flow, one model three consumers:**

```
Graph API ──► TanStack Query ──► graphology instance ──► sigma
                    │                   │
                    └── optimistic ─────┴──► layout.worker (x/y)
```

⭐ **The graphology instance is the single source of truth in the client.**

---

# 5. Talking to the backend

Two options. **Use the HTTP API** — the CLI is for you to inspect behaviour, not
for the app to shell out to.

```python
from mindgraph.api import Api, serve
api = Api(root="users")
token = api.tokens.mint("local", "human")     # server-minted, opaque
serve(api, port=8787).serve_forever()
```

```
GET  /stats  /explain?id=  /path?a=&b=  /frontier?k=  /contradictions
     /query?q=&lens=&k=    /timeline?at=    /export
POST /propose  /predict  /validate  /retract
Authorization: Bearer <token>
```

⚠️ **Capabilities are enforced server-side and you will hit this.**

| Bundle | Can | Cannot |
|---|---|---|
| `reader` | stats, explain, path, frontier | ⭐ **text search** — seeding reads labels, which are user text |
| `grounder` | + query, propose | validate, retract |
| `critic` | + timeline, verify spans | validate, retract |
| `human` | everything | — |

⭐ **`validate` and `retract` are human-only in every bundle.** If AI could
write *"this worked"*, the record of what worked becomes fiction — and that
record is the entire asset.

**Missing from the API, add as you need them:** `neighbors`, `review` queue
accept/reject, `ingest` upload, `nudge`. All exist as Python functions; they
need routes. Follow the pattern in `api.py` — one function, `require(tok, ...)`
first line.

---

# 6. Build plan — nine phases

Sequenced so every phase is testable by a real student, and the riskiest
assumption is tested earliest.

### Phase 0 — Run F4 · 0.5 day · ⚠️ BLOCKING

Render 6 node hues × 5 sizes × 4 confidence levels through a CVD simulator
(deuteranopia, protanopia, tritanopia). Procedure in `06 §1.6`.

**Fail condition:** <80% type accuracy at 16px, or any two hues confused under
deuteranopia. **On failure: collapse to 4–5 node types and re-run** — then the
palette, node chip and encoding matrix all change before you have built on them.

**Gate:** a table of hue × CVD × size with a pass/fail per cell, committed.

### Phase 1 — Tokens, node chip, the five states · 1 day

Everything else is composed of these. `06 §2` verbatim, `07 §1–2.1`.

**Build:** CSS custom properties for colour/space/type/radius/motion · the two
accessibility modes (reduced motion, high contrast) · `<NodeChip>` · `<Empty>`
`<Loading>` `<Partial>` `<Error>` `<Stale>`.

⚠️ **`partial` is the one that matters.** A retrieval returning 12 of 50, an
ingest still parsing, a Critic that has not returned — all normal, and all must
look deliberate rather than half-broken.

**Gate:** a component gallery page rendering every state of every primitive, and
a token switch that visibly changes both accessibility modes.

### Phase 2 — Artifact: predict → measure · 2 days · ⭐ THE MOAT

`01 §4.3`, `07 §2.3`. **Do this before anything else that has a graph in it.**

⭐ **F8 is the biggest unknown in the product:** will anyone type a prediction
*before* they build? This phase is the cheapest possible test, and it needs no
graph at all.

**Build:** the lock form · `POST /predict` · `POST /validate` · the verdict
card · the calibration counter.

⚠️ **`Lock` is a commitment, not a save.** Heaviest affordance on screen; after
it fires the inputs become **text, not disabled inputs** — a greyed field
invites a search for the edit button.

**Gate:** a real student records one `predicted → measured → agreement` on real
hardware, and the claim shows `corroboration 1, TENTATIVE`.

### Phase 3 — Onboarding · 1 day

`01 §8`. Cold start already works server-side; this is three screens.

⭐ **Screen 2 is the most important in the product** — *"How will you know it
worked?"* It is a **nudge, never a gate**: the student can proceed and the graph
is flagged low-confidence.

**Gate:** one typed sentence produces a graph with a non-empty frontier in under
10 seconds, and a vague question visibly triggers the nudge.

### Phase 4 — Bench + tension card · 2 days

`01 §4.1`, `07 §2.2`, `07 §2.5`. The daily loop; proves the ranking is worth
anything.

**Build:** ranked action rows with their meta line · `GET /frontier` ·
`GET /contradictions` · the two-column tension card · resurrection and crossover
rows.

⭐ **Two columns, never a verdict.** The system's job is to put literature and
bench side by side; picking a winner is the one thing it must not do.

**Gate:** the top three Bench items are things a student would actually do next
— judged by a student, not by you.

### Phase 5 — Ask + explain · 2 days · ⚠️ needs the Tier 1a key

`01 §4.0`, `01 §4.0a`. ⭐ **The main verb.**

**Build:** capture-bar question → streaming answer · claim chips → `explain` in
the right pane · citation rendering **by `citation_state`** · the `◌ checking`
→ badge transition · the `degraded` mark.

⚠️ **Three rules on the streaming answer, from `01 §4.1a`:** the pending state
is visible from the first token · the badge resolves **in place**, never
re-flowing text · a `CRITICAL` verdict **demotes** the answer rather than
annotating it.

**Gate:** a wrong answer visibly demotes within ~1s of the text finishing, and
no text re-flows while it does.

### Phase 6 — Sources + review · 2 days

`01 §4.4a`, `01 §4.4`, `07 §2.4`.

**Build:** drop-to-ingest · per-file parse status with the ⭐ `0 tokens` mark ·
quarantine list with reasons · the review queue, keyboard-driven, `A/R/E/␣` ·
the span→claim reader.

⚠️ **PDF highlights are page bands, not phrase boxes.** Layout is discarded on
read; a tight rectangle we cannot locate is a precise-looking lie.

**Gate:** 20 real documents ingested and the **accept rate by tier** measured —
the most important early number in the project.

### Phase 7 — Log + Share · 2 days

`01 §4.5`, `01 §4.6`, `01 §4.7a`. The first thing worth showing anyone.

⭐ **Failures stay visible** — the retraction, the dead end, the paper that
turned out not to apply. That is what demonstrates competence and exactly what a
polished write-up destroys.

⚠️ **Never render the calibration curve under 15 resolved predictions.** Below
that it is noise shaped like a finding, and a student reading a random walk as
*"I'm getting worse"* stops predicting.

**Gate:** the Share page renders for a real project and someone outside the team
understands it without narration.

### Phase 8 — Map · 3 days · ⭐ DELIBERATELY LAST

`01 §4.2`, `02`, `03 §5`. sigma + graphology + forceatlas2 worker, capped at 50
nodes.

**Building this early is how a graph product becomes about the graph.**

**Gate:** ⭐ **time-to-close under 10 seconds means it is decoration** — that is
`Frontend/04` F1's tell, and it is worth knowing.

### Phase 9 — Settings, notifications, offline · 2 days

`07 §3–5`. Real, and none of it is the product.

⚠️ **Three notifications, no more.** P0 tension inline · ingest finished, quiet ·
resurrection on next Bench visit only. Everything else accumulates and is pulled.

⭐ **Offline scope:** the frontier, capture, and predict/measure work with no
signal. `ask`, extraction and embeddings do not. **A student at a bench with no
signal asking what to do next must get an answer.**

**≈17 days.** ⚠️ **Cut phase 8 if anything slips** — never phase 2.

---

# 7. Hard rules — breaking these breaks the design

1. ⭐ **Hue carries node type. Nothing else, ever.** Confidence is saturation,
   support is fill, everything else is a rim glyph.
2. ⚠️ **Rim glyphs are nearly full at three** (`◑` single-method, `⚡` contested,
   `◷` stale). Anything new competes for one; it does not add a fourth.
3. **Never show a connection without the reason it is surprising.** Crossovers
   carry their `why` verbatim from the scorer, as bullets. Empty `why` → no row.
4. ⭐ **Never pick a winner in a disagreement.** Two columns, both with evidence,
   and the student decides.
5. **A claim that lost its evidence is not a claim that never had any.**
   `explain` renders `retracted_support` as its own block.
6. ⚠️ **The review queue holds only `AMBIGUOUS`**, and every card says what the
   system could not decide. Without that line it is a rubber stamp.
7. **Nothing is written until the Critic returns.** Display may stream ahead of
   acceptance; the ledger may not.
8. ⚠️ **Never interrupt mid-build.** Batch everything except a P0 tension.
9. **≤50 nodes on the Map, always.** The limit is human, not technical — by a
   factor of 500.
10. ⭐ **Every result carries its justified path.** That is why this is graph
    traversal and not a vector index.

---

# 8. What is still unknown

Full detail in `Frontend_design/04`. Three matter:

- **F4** — §6 phase 0. **Blocking.**
- **F8** — will anyone fill in the prediction form? It is the most form-like
  thing in a friction-free product, appearing exactly when a student wants to go
  build. ⭐ **It is the moat.** Phase 2 tests it.
- ⚠️ **F11 — designed for the wrong moment?** Every surface assumes a *planning*
  posture; the abandonment cliff is week 3, 1am, mid-debug. If the highest-value
  surface is really a **debug companion**, §6's order is wrong rather than the
  components. **One afternoon watching a real student settles it. No amount of
  design does.**

---

# 9. Working protocol

1. Read `HANDOFF.md` (this file's backend sibling) for current state.
2. **Say which phase and gate you are on** before starting.
3. Work.
4. **Run the phase's gate before claiming it is done.**
5. **Append to `HANDOFF.md`** — what changed, decisions made, next action.
6. ⚠️ If a decision comes up you were not asked about → **a new entry in
   `Frontend_design/04`**, not a silent choice in code.

⭐ **Closed tasks, never open ones.** *"Implement `<NodeChip>` per `06 §2` and
`07 §2.1`, with the gallery states from `07 §1`"* — not *"build the design
system."*

# Uncertainty Register

**Backend / 09.** Every design call I am **not** confident about — what I chose, what I rejected, why, and what would settle it.
**Why this exists:** you asked whether I'm sure. For most of the design, yes. For twelve things, no — and a design document that hides its own soft spots is worse than useless, because you'd inherit my guesses as if they were conclusions.
**Date:** 2026-08-09

> **Convention:** resolved questions are **never deleted** — their status changes to ✅ **RESOLVED**, and the entry records the decision, the reasoning, and which documents changed. The register is a record of how the design was reasoned about, not just a to-do list.
>
> **How to use this.** Each entry has a **Q-number**. That number is marked inline in the relevant document at the exact section it concerns, so when you hit `❓ Q4` while reading Backend/01 §3.2, this is where the reasoning lives. Tell me what you think on any of them; I'll change the design or defend it.

---

## Confidence summary

| | Count | Meaning |
|---|---|---|
| 🟢 **Confident** | most of the design | Evidence-backed, or the alternative is clearly worse |
| ✅ **Resolved** | **all twelve** | decided, applied to the design, kept here as a record |

> **All twelve are closed as of 2026-08-10.** The last two — **Q10** (skeleton granularity) and **Q11** (SQLite + NetworkX at 10⁴) — were the two I'd said reasoning couldn't settle, and that was right: **both were closed by running something.** Q11 by a load test, Q10 by writing the CI validator the design had specified and never run. Each entry keeps what was decided, what I got wrong, and what to watch — several of those watch-items are live.

**What I *am* confident about**, for contrast — the ledger/graph/sidecar split, the ATMS cascade, crypto-shredding, ontology-constrained extraction with code validation, hybrid retrieval, deferred CPU-bound analysis, the ~50-node cap, and human-only `VALIDATE`. Those are either forced by evidence or the alternatives are demonstrably worse.

---

# ✅ Q1 · Will the student actually do the review? — **RESOLVED 2026-08-10**

## The decision

> **Auto-accept everything except `AMBIGUOUS`. `AMBIGUOUS` is always asked of the student.**

| Tier | Route |
|---|---|
| `EXTRACTED` | auto-accept |
| **all `INFERRED`** (0.95 → 0.55) | auto-accept, flagged, one-click reversible |
| ⭐ **`AMBIGUOUS`** | **always asked of the student** — never auto-accepted, never dropped |

**Review is never blocking.** The nightly **contradiction sweep** is the safety net for auto-accepted inferences.

## Why — and the reasoning that changed my mind

I framed this as an *integrity* question: will enough review happen to keep fabricated edges out? Aryav reframed it as a *pedagogical* one, and that's the better frame:

> **The point of Nexus is to make the student think.** So an item the system genuinely cannot resolve is not a chore to be gated — it is exactly the moment a human should be reasoning, and handing it to a model instead would defeat the product.

That inverts what the queue is *for*. It stops being an integrity gate and becomes a **thinking prompt** — which also happens to solve the throughput problem, because shrinking the queue to `AMBIGUOUS`-only makes it small enough to actually get done. **One decision fixes both the purpose and the volume.**

It also lines up with something already in the research: *AMBIGUOUS is never dropped — unresolved tension is the syllabus.*

## What protects the auto-accepted inferences

Fabrication runs ~1.5–1.9%, so a 5,000-edge graph carries ~75–95 invented relationships. Four defences, all already in the design:

1. **VSUP desaturation** — low-confidence edges render visibly grey. Low confidence *looks* low-confidence.
2. **DOI weights confidence**, so they rank low and rarely surface.
3. ⭐ **They cannot promote anything.** `established` requires ≥2 corroborating **validated results**, never edges — so a fabricated edge can never make a concept count as known, and can never enter the knowledge state that drives the frontier.
4. ⭐ **The nightly contradiction sweep** is now the primary catch. A fabricated edge usually collides with something real eventually, and the Disagreement Engine surfaces it at that point.

## What we gave up

Low-confidence inferences (0.55–0.75) now live in the graph unreviewed. Accepted, because defence 3 means they are inert — they decorate rather than promote — and defence 4 catches the ones that matter.

## Documents changed

`Backend/01 §5` (the gate) · `Backend/03 §5` (routing) · `Backend/11` (the flow diagram) · `Frontend/01 §4.4` and `Frontend/05` (Review reframed as the thinking prompt).

## What to still watch

**Queue completion rate in week 1.** If students don't clear even an `AMBIGUOUS`-only queue, the problem isn't volume — it's that they don't value the question, and that's a much more serious signal about the product.

---

# ✅ Q2 · Is the four-role agent split worth its cost? — **RESOLVED 2026-08-10**

## The decision

> **Keep all four. The split is not the cost driver — it is the cost *optimiser*.**
> **Extract the load-bearing property as an invariant, demote the roles to configuration, and re-point the experiment at model *tiering*.**

## ⭐ What I got wrong — the cost analysis that motivated the doubt

I wrote that waking four roles *"roughly doubles per-turn cost."* Working it properly, with illustrative rates:

| | payload | model | cost |
|---|---|---|---|
| Grounder | 8k in *(content)* / 1.5k out | mid | $0.047 |
| Synthesiser | **3k in** *(structure, **no bodies**)* / 1.5k out | frontier | $0.158 |
| Critic | 3k in / 0.8k out | mid | $0.021 |
| Planner | 1k / 0.3k | cheap | ~$0.002 |
| **split total** | | | **≈ $0.23** |
| **merged, one frontier call** | 11k in / 3k out | frontier | **≈ $0.39** |

**Merging is ~70% *more* expensive.** The reason is `project_view`: it strips document bodies from the Synthesiser, so the frontier model never carries the ~8k-token content payload. **The capability filter is a cost filter.** Merge the roles and you pay frontier rates on every content token the Synthesiser currently never sees — *and* you destroy the `EXTRACTED` guarantee at the same time.

The genuine saving from "one agent" comes entirely from **downgrading the model**, which is a tiering decision, not a role-count decision. **I had framed the question wrong.**

## The property the split was actually protecting

Not legibility. **Context isolation.**

*"The Synthesiser structurally cannot fabricate a citation"* is only true if it has genuinely never seen a source. Run the roles as turns of one conversation and the content is still in context — the gate checks declared capabilities, the context contains material those capabilities exclude, and **the capability check silently becomes a lie** while every test still passes.

Separate agents gave us isolation *incidentally*. Naming it directly is what makes the role count negotiable.

## What changed in the design

| Change | Where |
|---|---|
| **Invariant 3 — every dispatched call is context-isolated**, stateless, capability-scoped payload | `Backend/05 §1` |
| Roles demoted: architecture → **default configuration** | `Backend/05 §3` |
| ⭐ **Model tiering by *verifiability*** — 5 tiers, incl. our own OSS model | `Backend/05 §3.2` |
| ⭐ **The complete execution map** — all 23 model touchpoints named and assigned | `Backend/05 §3.3` |
| Planner → **Tier 0 Router**, with Opus escalation on HARD turns | `Backend/05 §3.4` |
| ⭐ **Display decoupled from acceptance** — Critic runs concurrently with streaming | `Backend/05 §4.2` |
| Cost rows gain `model_tier`, `model_id`, `escalated`, `ttft_ms` | `Backend/05 §7` |

## The other thing this exposed — ⚠️ latency

Aryav's framing was *"the most optimal reply in an efficient manner."* I had divided the roles by **safety** and never by **speed**. Run strictly in sequence, the turn protocol is **three sequential model round-trips before the student sees a word** — 10–20 seconds at a bench, and nothing to do with cost.

The Critic doesn't write the prose; it emits `contradicts` edges and flags. So it doesn't need to block the text. **Answer streams immediately; the Critic runs concurrently; no `accepted` event is appended until it returns.** Every invariant holds and the graph is exactly as correct as before — only *display* moved. **Three perceived hops → one.**

And it reframes the Planner: earlier I said dropping it saves nothing, which was true on **cost** and wrong on **what matters**. It buys back a whole round-trip on every turn, including the ones that never needed planning.

## What's still open

**Nothing architectural.** The live question is now `Synthesiser: Opus vs Sonnet` on 20 identical queries — **~60% of spend in one config line**, and §7's cost rows log it from day one, so the Phase 3 experiment is a query rather than a build.

## What to watch

- **Router escalation rate.** If it escalates on turns a SIMPLE path would have answered, that's pure latency. Logged as `escalated` vs accept rate.
- **Tier 1a extraction quality.** Constrained decoding guarantees *shape*, not *content*. Watch the quarantine rate — if it rises materially against the current hosted-model baseline, the OSS model is too small.
- **The ~1-second uncritiqued window** in §4.2. Bounded by the Q8 tier system, but if a `CRITICAL` badge ever arrives after a student has acted, revisit.

---

# ✅ Q3 · Will `Note` swallow everything? — **RESOLVED 2026-08-10**

## The decision

**Keep the escape hatch. Add a structuring nudge — an offer, never a requirement.**

```
trigger   unstructured Notes > 40% of nodes created in the last 14 days
          OR  > 15 outstanding
offer     "You've written 18 notes I haven't structured. Want me to take a pass?"
batch     one Review-style pass — proposed structure per note, A/R/E, bulk-accept
respect   a note that resists structuring twice is left alone permanently
```

**Health metric:** `Note` : structured-node ratio. **Below ~30% healthy; above ~60% means extraction isn't doing its job** — and the fix is **more aggressive proposal, not more required structure.**

## Why

Aryav: *"we don't want to be Obsidian — a notes app with a pretty UI graph. If it goes over a certain %, we need to structure and organise them properly."*

That's the right instinct and it's structural, not aesthetic. A `Note` cannot hold `predicted`/`measured`, cannot be corroborated, cannot be contradicted. **Everything distinctive about Nexus — calibration, the frontier, the Disagreement Engine — needs typed nodes.** A graph of Notes with links *is* Obsidian.

But requiring structure at capture is what *Formality Considered Harmful* says kills adoption. **A threshold-triggered batch offer is the only shape that gets both** — no form in front of anyone mid-project, and a real pull toward structure when drift sets in.

## ⭐ How Q1's resolution changed this

Before Q1, low-confidence structure proposals went to a review queue that might never be cleared, so notes stayed notes by default. **Now all `INFERRED` auto-accepts**, so structure proposed over a note is applied without the student doing anything.

**The nudge is the backstop, not the primary mechanism.** What remains of the risk is *extraction quality* — if the extractor can't turn *"the rail felt noisy tbh"* into a decent `Claim`, it stays a Note no matter how permissive the gate is.

## Documents changed

`Backend/01 §5.1` (the nudge) and §3.1 · `Frontend/01 §4.4` (Review hosts the batch surface) · `Queries/00`.

## What to still watch

The ratio itself, in the first ten projects. And whether the nudge gets dismissed every time — **if students never accept the offer, the problem isn't the threshold, it's that they don't believe structure buys them anything**, which is a far more serious signal.

---

# ✅ Q4 · Should `Concept` be globally scoped? — **RESOLVED 2026-08-10**

## The decision — neither pole

Aryav asked whether there was a middle ground. There is, and it's better than either option I'd put up. **The question isn't *"what scope?"* — it's *"where did this concept come from?"***

### Scope follows provenance

| Origin | Scope | Merge risk |
|---|---|---|
| ⭐ **Curated** — from the concept skeleton, or carrying a CASE `external_id` | **global by construction** | **zero** — a domain expert authored it; the resolver never created it |
| **Extracted** — invented by the LLM from this student's material | **project-scoped on creation** | contained to one project |
| **Promoted** — extracted, then appears in a **2nd project** *and* resolves **≥0.95** against an existing global | becomes global | high-confidence only, reversible |

**Why this is the right cut:** the concepts a student accumulates across a degree — I²C, PID, ADC, impedance spectroscopy — are almost all *curated skeleton concepts*. Global from day one, no resolver involved. **Compounding works immediately for the common case at zero risk**, while the risky ones stay local until they prove they generalise.

### Plus a soft-merge band

| Confidence | Action |
|---|---|
| ≥ 0.95 | hard merge — one node |
| ⭐ **0.70 – 0.95** | **`same_as` edge. Both nodes survive.** Retrieval unions them |
| < 0.70 | distinct |

**Identical behaviour for the student; an order of magnitude cheaper to undo.** A wrong `same_as` is an edge deletion the cascade already handles; a wrong hard merge needs a `split` and reconstructing which properties belonged where. `same_as` was already in the relation enum, so this costs nothing new.

## What I'd got wrong

I framed it as a binary and rated it 60/40. Two things I'd under-weighted:

1. **Merges are already reversible** — `merged` and `split` are both event types. The problem was never permanence, it was **detection**.
2. ⭐ **The Disagreement Engine detects bad merges for free.** Two wrongly-merged concepts produce claims that contradict each other — which after Q8's widening fires as **CONFLICT**, visibly, without anyone looking for it. *A feature added for a different reason turned out to be the missing safety net.*

## The comparison

| | Compounding | Blast radius | Organisational tax |
|---|---|---|---|
| Always global | ✅ full | ❌ whole account | none |
| Project-scoped + confirm | ⚠️ delayed | ✅ one project | ❌ a confirmation step |
| ⭐ **Provenance + soft merge** | ✅ **immediate for curated** | ✅ **contained for extracted** | **none** |

## Cost

One field (`Concept.scope`), one provenance field (`Concept.origin`), a promotion rule, and a change to the validator that previously *enforced* `project_id = None` on all Concepts.

## Documents changed

`Backend/01 §3.1, §3.2, §5` · `Backend/02 §2` (schema, validator, four new tests) · `Backend/03 §5` · `Backend/11 §3` · `Queries/00`.

## What to still watch

**The promotion rate and the false-merge rate in Phase 1.** If almost nothing gets promoted, the skeleton is carrying everything and extracted concepts are noise. If bad merges still appear among *curated* concepts, the skeleton itself has confusable entries (I²C/I²S, ADC/DAC) and needs a disambiguation pass.

---

# ✅ Q5 · Should `Claim.kind` be a node type? — **RESOLVED 2026-08-10**

## The decision — a third option

**Neither three types nor a stored enum. `Claim.kind` is DERIVED from graph structure.**

| kind | Structurally |
|---|---|
| `observation` | supported by evidence **outside your reasoning** — an `Artifact` or a `Source` |
| `conclusion` | supported by **other Claims** |
| `hypothesis` | **no live support at all** |

Computed in the same pass as `support` and `strength`. The extractor's guess is kept in `provenance.kind_hint` — recorded, **never authoritative**.

## How the test I set resolved

My own test was *"does any code ever branch on `kind`? If yes, it should be a type."* Running it honestly: **yes, at least twice** — a hypothesis must never promote a Concept into the knowledge state, and the corroboration bar arguably differs for observation vs conclusion.

**So by my test I'd chosen wrong — but the test was the wrong test.** Branching on a *derived* property is normal; we already do it with `support`. What actually matters is whether the three kinds are **intrinsic** to a node or **readable off the graph**. They're readable off the graph.

## What this buys

1. **The drift surface vanishes** — the model can't mislabel something it doesn't assert.
2. ⭐ **Transitions become automatic.** A hypothesis stops being a hypothesis the moment you measure it. No state machine, no migration, no *"why is this still marked hypothesis"*.
3. **The branch I was worried about already worked.** A hypothesis has no live support → can't reach `established` → can't enter the knowledge state. *Guessing something cannot make you know it.* Deriving `kind` doesn't add that rule, it makes it legible.

## Scope of the change

**Only `Claim.kind` becomes derived.** `Artifact.kind` (code / circuit / run / measurement / document) and `Source.kind` (paper / datasheet / video) stay **intrinsic** — a firmware build versus a measurement is not derivable from the graph.

## Documents changed

`Backend/01 §3.2a` (new) · `Backend/02 §2, §5.2` + two tests · `Backend/03` (kind becomes a hint in the prompt) · `Queries/00`.

## What to still watch

Whether the derived value ever disagrees with `kind_hint` in a way that matters. Prose signals intent — *"I think X"* versus *"I measured X"* — and if a claim the student clearly framed as a guess derives to `observation` because some source happens to support it, the hint was carrying real information we're discarding.

---

# ✅ Q6 · Is `evidence_mass` damping right? — **RESOLVED 2026-08-10**

## The decision

**The curve was the wrong thing to argue about.** Two changes:

**1. ⭐ Discount non-independent sources first.** `weight` counts *distinct* sources, but distinct ≠ independent — five papers repeating one original claim is one fact. Where we have the `cites` graph we can **measure** that instead of approximating it: a source reachable from another source via `cites` is not independent evidence.

```
independent_weight(edge) = |sources| − |sources reachable from another via `cites`|
```

**2. `sqrt` instead of `log₂`.** Our weights live in the **1–5** range, and there:

| weight | `1 + log₂(w)` | `√w` |
|---|---|---|
| 2 | **2.00** | **1.41** |
| 3 | 2.58 | 1.73 |
| 5 | 3.32 | 2.24 |

`log₂` says the second source **doubles** the evidence. That's too generous when independence is uncertain. `√w` says +41%, which is the honest default for the range we're actually in.

## Honest caveats

**The independence check is partial.** We often won't have the citation graph — a student's five sources may not cite each other *within our graph* unless we extracted those citations. So damping remains the fallback, not a formality.

**And Q6 is genuinely low-stakes.** It affects ranking only, never support classification (fixed earlier), and ranking gets tuned from click data in weeks 2–4 regardless. This is polish. It was flagged for honesty, not because it was risky.

## Documents changed

`Backend/02 §5.2` (`independent_weight`, `evidence_mass`) + one test · `Queries/00`.

---

# ✅ Q7 · Is the graph the right primary artifact? — **RESOLVED 2026-08-10**

## Decided by Aryav

> *"Let's go graph-as-engine, as it needs to be functional, but also show the design as a secondary view."*

The whole frontend design is built on it — **Bench** as home, **Map** as the fifth thing to build.

⚠️ **Bookkeeping note:** the decision was made on 2026-08-10 and I did not close this entry at the time. That drift is exactly what the register exists to prevent, and it's recorded rather than quietly fixed.

## What it actually changed in the backend

I claimed graph-as-engine *"changes almost nothing in Backend/01–08."* Mostly true, with four qualifications:

| | Effect |
|---|---|
| **Graph API surface** | ⬆️ **more important** — now the primary consumer path, not a supplement to a canvas |
| **`labels_at`** (semantic-zoom labels) | ⬇️ lower priority — serves only the rare visual view. **Keep** (unretrofittable), build late |
| **Leiden clustering** | unchanged. Two of three consumers are machine-facing — community labels for the report, crossover dedup by community pair |
| **Layout stability** | ⬇️ the *"protect the mental map"* justification weakens if the graph is rarely seen. But **community identity** stability still matters for the report and crossover dedup, so it stays |

⭐ **And it sharpens one argument.** `Frontend/06` justified graphology-on-both-sides partly as *"share one graph model."* Under graph-as-engine the client renders the Map rarely, so that's weaker than I made it. **The argument that survives is offline frontier** — a student at a lab bench with no signal can still ask *"what should I do next?"* That's the week-3 moment.

## What's left

Not the question — its residual, already tracked as **`Frontend/04` F1**: *did I over-correct?* The research condemns **unbounded** graphs given to people with a search task; a 50-node, well-encoded, deliberately-scoped one is a different object and might be fine as a primary surface.

**The tell is time-to-close on the Map.** Under 10 seconds and it's decoration.

## Documents changed

`Queries/00 §5.4` (picture-vs-substrate closed) · this entry. No design change required — the frontend was already built on the decision.

---

# ✅ Q8 · Will the Disagreement Engine fire often enough? — **RESOLVED 2026-08-10**

## The test I said would settle it, run

Hand-walked the biosensor project (*"Can skin impedance track hydration?"*, ESP32 + impedance rig, six weeks) and counted the disagreements that would genuinely arise:

| Week | Disagreement | Type |
|---|---|---|
| 1 | datasheet ADC range 0–3.3V vs saturation measured at 3.1V | spec vs measurement |
| 2 | forum says 4.7k I²C pull-ups; only works at 2.2k with long leads | source vs measurement |
| 2 | *"the 5V rail is clean"* vs the scope | own claim vs own measurement |
| 3 | Tuesday 47 kΩ, Thursday 62 kΩ, same setup | **own data vs itself** |
| 3 | Chen: 30–40 kΩ hydrated; measured 47 kΩ | ⭐ source vs corroborated measurement |
| 4 | two papers disagree on electrode material | source vs source |
| 4 | datasheet settling 100 ms; needs 400 ms | spec vs measurement |
| 5 | week-2 hypothesis contradicted by week-5 data | own claim vs own measurement |

**~8–12 over six weeks. Not two.**

## The design error the test exposed

**I built the ranking around the marketing headline rather than the frequency distribution.** The original trigger required a well-grounded source claim *and* a corroborated measurement *and* comparable conditions — that's line 5 of eight. The other seven are contradictions the graph can already see; they just aren't the glamorous case.

## The decision

**Fire on any live `contradicts` edge. The tier determines the framing, not whether it fires.** Six kinds — CHECK · CONFLICT · STALE · BOUNDARY · FINDING · LITERATURE.

⭐ **And separate *kind* from *priority*.** Kind says what it is; priority says where and when it surfaces, computed from `blocking × 100 + claim_load + resolvability + min(confidence) + recency − dismissals`, mapped to P0 (inline, immediate) → P4 (suppressed). **Recomputed continuously**, so a P3 that becomes blocking jumps to P0.

**No schema change** — it's a ranking and framing layer over `contradicts` edges, corroboration counts, `citation_state`, and provenance.

⭐ **CHECK fires in week 1**, needing one measurement and one datasheet. The corroboration gate governs what counts as *known*; it must not govern what's worth *flagging*.

## The thing I had backwards

**Pedagogical value is inverted from marketing value.** CHECK and CONFLICT are the most frequent *and* the most useful — *"your two runs disagree"* catches a real error a student would otherwise chase for two days. FINDING is the exciting one, fires 0–1 times, and is usually wrong.

So the headline changed too. *"We detect when you've discovered something"* would read as a lie at that frequency. **"Nexus notices when things don't add up"** is honest across all six kinds, and discovery becomes the upside rather than the promise.

## Guards added

**At most one P0 at a time** — more than one is the habituation failure the frontend research documents. And ⭐ **P1 tensions compete in the same ranking as gaps**, not a parallel queue: one notion of *"what matters now"* in the product, not two.

## Documents changed

`Backend/01 §8.2` (rewritten — six kinds, priority function, guards) · `Backend/11 §6.4` · `Frontend/01 §4.1` · `Frontend/05` · `Queries/00`.

## What to still watch

**Firing rate in week 1 of real use.** The estimate is a hand-walk of one imagined project, not a measurement. If CHECK fires on every trivial spec deviation it becomes noise regardless of tiering — in which case CHECK needs a materiality floor (only fire when the deviation exceeds the spec's own tolerance).

---

# ✅ Q9 · Will calibration actually move? — **RESOLVED 2026-08-10**

## The decision

**Keep calibration as the headline metric, but change how it's measured.** Not a Brier delta — a **reliability curve**, plus **interval coverage** as the more sensitive early signal, with the null **pre-registered**.

## The confound that forced it

The original design compared Brier in weeks 1–2 against weeks 5–6. Three problems, and the third I had missed entirely:

| | Problem |
|---|---|
| Sample size | ~12 predictions in six weeks makes first-5-vs-last-5 enormously noisy |
| Task heterogeneity | predicting an impedance value and predicting whether firmware compiles are different tasks |
| ⭐ **Difficulty drift** | **week-6 predictions are about harder things. Flat calibration on rising difficulty is a real improvement that a naive before/after shows as nothing.** |

⭐ **A reliability curve kills the third by construction** — it conditions on the student's *own stated confidence*, which we already capture on the Artifact screen. A harder prediction they were appropriately less sure about doesn't penalise them.

## Why there's reason to expect movement

**Calibration is known to be trainable, and the mechanism that trains it is rapid unambiguous feedback** — exactly what predict → measure provides. That prior wasn't in my original doubt and it should have been.

**And overconfidence is the specific thing to watch.** Undergraduates are systematically overconfident, so it's both the likeliest direction of movement and the easiest to detect.

## Interval coverage — the metric that moves first

*Of predictions stated as a range, what fraction contained the measured value?* Well-calibrated 80% intervals contain the truth ~80% of the time; undergraduates land far below. **Large gap → large effect size → detectable at much smaller n.**

## The pre-registered null

| | |
|---|---|
| Primary | mean \|stated confidence − observed accuracy\| across bins |
| Predicted | decrease **≥ 0.05** over six weeks |
| Null | no change, or an increase |
| Minimum n | **15 resolved predictions per student**, 8+ students |
| Secondary | interval coverage |

## If it's null

**Not fatal, and worth saying now rather than under pressure.** Calibration is the *measurement*, not the mechanism — the record, the frontier and the Disagreement Engine all still work. A null means leading with **proof completion** instead, and it would be a genuinely publishable finding: *six weeks of predict-measure feedback does not measurably improve undergraduate calibration.* Nobody has that result either.

## Documents changed

`Backend/06 §5` (rewritten — reliability curve, interval coverage, pre-registered null, guards) · `Backend/11` · `Frontend/01 §4.6` · `Queries/00`.

---

# ✅ Q10 · Is the concept skeleton at the right granularity? — **RESOLVED 2026-08-10**

## The decision

> **The question splits. Structural granularity is measured and passes. The semantic half becomes a bounded task, not an open review — and `verify`, not granularity, turns out to be the real gap.**

## What I actually did

Built `tools/validate_skeleton.py` and ran the CI checks this design has specified since 2026-08-07 and **never once executed.**

| Check | Result |
|---|---|
| cycles | ✅ 0 |
| dangling `requires` | ✅ 0 |
| **stated count** | ❌ doc said **187**; there are **213** — a stale header line, section counts already summed to 213 |
| **redundant transitive edges** | ⚠️ **34** |
| isolated concepts | ⚠️ 3 (`version_control`, `soldering`, `enclosure_basics`) |
| **`verify` coverage** | ❌ **14%** |
| `aliases` coverage | ❌ 32% |

## ⭐ What I got wrong mid-resolution

I said transitive reduction was *"safe by definition here."* **It isn't.**

`fft requires complex_numbers` is transitively implied — via `impedance → ac_analysis → frequency_response → sampling_theorem`. Drop it and a student who knows complex numbers but not impedance is told the FFT is blocked on **electrical material they don't need.** The direct edge is load-bearing *because* the implying path detours through another domain.

So the validator classifies redundancies by domain: **same/adjacent → safe to drop (26, applied); crossing three or more domains → flagged and kept (8).** A blind `transitive_reduction()` would have silently damaged the fringe for exactly the interdisciplinary students this product is for.

## Structural granularity — measured

| | Value | Read |
|---|---|---|
| `requires` per concept | mean **1.49**, median 1, max 3 | target 2–4 → slightly under-connected |
| DAG depth | 15 | reasonable |
| leaves | **83 / 213 (39%)** | *"unlocks N things"* is silent for two-fifths |
| ⭐ **outer fringe** | **7** cold → **19** at 15% → **35** at 35% known | ⭐ healthy |

⭐ **The fringe row is the granularity test.** The Bench picks 3 `NOW` items from it. **3-from-20-to-35 gives the DOI ranking real work** — too coarse reads as a fringe of 3–5, too fine as 200. It's in the right band, so the original worry was mostly unfounded.

## ⭐ The finding that reframes the question

**`verify` matters more than granularity, and 86% of it is missing** — 0% in `math`, 0% in `digital`, 0% in `hardware`, 9% in `programming`.

`Backend/04 §1` calls that field *"the bridge to the whole verifiability thesis — the seed for an Artifact's `predicted`."* Without it the frontier can say **what** to learn next but not **what would count as having learned it**, and that loop is the product.

**Granularity being slightly off degrades ranking. `verify` being absent breaks the mechanism.** I had ranked these the wrong way round.

## What the teammate is actually asked for

Not *"review 213 concepts"* — an unbounded review returns nothing. Instead: **write `verify` for the ~50 concepts on the biosensor path.**

⭐ **The granularity judgement then arrives as a side effect** — you cannot write *"predict settling time and confirm on a scope"* for something that isn't about an afternoon of work. **The task tests the property by requiring it**, rather than asking for an opinion about it. Second pass, same shape, for `aliases`.

## What changed

| Change | Where |
|---|---|
| `tools/validate_skeleton.py` — CI, domain-aware redundancy split | new |
| 26 safe redundant edges dropped; 8 cross-domain flagged and kept | `Backend/04` |
| 187 → 213 throughout | `Backend/04` |
| §1.1 validator + measured granularity · §1.2 the `verify` gap and the bounded ask | `Backend/04` |

## What to watch

- **The 3 isolated concepts.** `soldering` and `enclosure_basics` genuinely have no theory prerequisite — that may be correct rather than a defect. But four disconnected components means the graph isn't one structure, and the frontier treats each independently.
- **39% leaves.** If the frontier's *"unlocks N things"* line is silent for two-fifths of suggestions, that signal is weaker in practice than the design assumes.

---

# ✅ Q11 · Is SQLite + in-process the right storage? — **RESOLVED 2026-08-10, by measurement**

## The decision

> **Yes, and not narrowly.** Load-tested rather than deferred to Phase 4. `tools/bench_graph.py`.

## The numbers

Synthetic scale-free graph with community structure (`powerlaw_cluster`, avg degree 8), 60k-event SQLite ledger, every nightly job in `Backend/01 §7`. Python 3.12, NetworkX 3.3.

| Job | 10k nodes | 25k nodes |
|---|---|---|
| **Personalized PageRank** *(per-turn — a student is waiting)* | **27 ms** | **76 ms** |
| 2-hop neighbourhood from 8 seeds | 0.4 ms | 0.3 ms |
| shortest path | 0.1 ms | 0.2 ms |
| **Full replay, 60k events → graph** | **122 ms** | 123 ms |
| Louvain *(Leiden proxy)* | 592 ms | 1.75 s |
| eigenvector centrality | 53 ms | 114 ms |
| approx. betweenness *(k=200)* | 3.0 s | 9.3 s |
| ⚠️ **exact betweenness** | **~118 s** | **~738 s** |
| Adamic–Adar, 5k candidate pairs | 7.5 ms | 8.4 ms |
| append 60k events (batched) | 168 ms | — |
| 200 single-event commits | 8.8 ms | — |
| peak RSS | 144 MB | 240 MB |

## What it settles

⭐ **The per-turn path is 27 ms against a model call of 2–8 seconds.** Storage is **~100× off the critical path**, and still is at 25k nodes. There is no version of this where the database is the reason the product feels slow.

⭐ **Full replay is 122 ms — and I had never tested it.** *"The choice is reversible for the cost of a re-projection"* is the load-bearing claim of the whole event-sourced design, and it was an assertion. It's now measured, and it's **independent of graph size** because it's bound by event count.

**Only exact betweenness is slow, and it shouldn't be exact.** Betweenness is one blended term in DOI's `API(x)` — a **ranking input, not a truth claim** — so `k=200` sampling is correct on the merits rather than a concession. **118 s → 3 s.**

## ⭐ The constraint the doubt didn't anticipate — memory, not CPU

**144–240 MB per user held in-process.** Ten concurrent students ≈ 2.4 GB. The design says *"one file per user, in-process graph"* and **never asked how many fit in RAM at once.** I had been worrying about the wrong resource entirely.

⭐ **And the fix is the number in the table.** A 122 ms replay makes **LRU eviction free** — drop a user's graph, rebuild on their next request in a tenth of a second. *The property that makes the storage choice reversible is the same one that makes it multi-tenant*, and I had only ever argued the first.

## Honest caveats

- Synthetic topology, not a real knowledge graph. Real ones are lumpier.
- A laptop, not a server — could go either way.
- NetworkX's Louvain is pure Python; `leidenalg` is C-backed, so **592 ms is an upper bound**, and Leiden remains the choice (`Backend/01 §7`: Louvain can emit disconnected communities).

## What changed

| Change | Where |
|---|---|
| `tools/bench_graph.py` — the load test, repeatable | new |
| betweenness specified as **approximate, k=200** | `Backend/01 §7` |
| **LRU eviction** of in-process graphs, justified by the 122 ms replay | `Backend/07` |
| measured figures replace the estimate | `Backend/07 §6` |

## What to watch

- **Concurrency**, now that it's the real limit. The eviction policy is untested under load.
- **Real graph topology** at 10⁴ — if it's far denser than avg-degree 8, PPR and Louvain both rise.

---

# ✅ Q12 · Is six node types right? — **RESOLVED 2026-08-10**

## The decision

> **Six types stand. `Method` becomes `Artifact(kind=method)`, using the `uses_method_in` relation that already existed.**
> **One enum value. No new type, no new relation.**

```
Artifact(kind=run) --uses_method_in--> Artifact(kind=method)
```

## Why `Artifact` and not a seventh type

*"4-wire Kelvin at 50 kHz, 10 mV excitation, dry Ag/AgCl, 2 cm spacing, forearm."*

Not a `Concept` — the general technique is one, that specific parameterisation isn't. Not a `Claim` — it asserts nothing. Not a run, because **many runs share one method.** It *is* something the student made — a procedure — and `Artifact` already carries `spec` for parameters.

## ⭐ What I'd underweighted — corroboration independence

I flagged this as reuse convenience. It's more than that; it's an **epistemics bug in the current design.**

`ESTABLISHED` requires `corroboration ≥ 2` — two distinct validated results. But **two results from the same method are not independent corroboration.** Replication that varies nothing largely confirms your setup, not your claim. The projector currently counts them identically.

That is the same *distinct ≠ independent* insight Q6 applied to citations, now applied to results — and I applied it on one axis and missed the other.

**Three things the Method node buys**, in increasing order of importance:

1. **Comparability.** *"The paper doesn't apply to your setup"* is very often *"different method"* — which is precisely the `BOUNDARY` tier of the Disagreement Engine, currently forced to reason over unstructured prose.
2. **Reuse and refinement.** *"Every measurement taken before I fixed the electrode spacing"* — a common query, currently unanswerable.
3. ⭐ **Independence quality**, above.

## Why it flags rather than blocks

**`single_method` is surfaced, not gated.** Requiring two *different* methods for `ESTABLISHED` would be over-engineering: same-method replication is a legitimate reproducibility check, and an undergraduate usually has exactly one rig. Blocking would punish the normal case to catch the rare one.

So the flag is visible on the node and feeds the Disagreement Engine's assessment of how solid a claim is. **Surface the weakness; let the student judge it.**

## What changed in the design

| Change | Where |
|---|---|
| `Method` explained; `Artifact.kind` gains `method` | `Backend/01 §3.1a`, §3.2 |
| `corroborating_methods`, `single_method` on `Node` | `Backend/02` |
| `_method_of()`; `_validated` records the method; `_merged` unions the sets | `Backend/02` |
| `single_method` derived in `_recompute_support` | `Backend/02` |
| Three tests, incl. **methods survive a merge** | `Backend/02` |

## What to watch

- **Do students ever create a Method node unprompted?** If methods only ever appear because extraction invented them, the reuse argument was wrong and only the independence check earns its keep.
- **Does `single_method` fire on nearly everything?** If a typical project has one rig and every claim is flagged, the badge is noise and should be reserved for claims where a *second* method was plausible.

---

# What I'd do about all of this

*(Written 2026-08-09, when ten of these were open. Kept as a record of the plan; superseded by the resolutions above.)*

~~**Answer Q7 and Q8 before building Phase 5.**~~ ✅ both closed 2026-08-10.

~~**Q1, Q2, Q4, Q11 are answered by cheap experiments.**~~ Q1, Q2 and Q4 closed by reasoning. **Q11 stands** — it genuinely needs the load test.

~~**Q3, Q5, Q6, Q10, Q12 are watch-items.**~~ Q3, Q5, Q6 and Q12 closed. **Q10 stands** — it needs domain expertise, not observation.

**Where it actually landed: twelve of twelve.** Nine closed by reasoning; ⭐ **the last two closed by running code** — a load test for Q11, and the skeleton validator for Q10. Both had been filed as *"needs a later phase"*, and both took under an hour. **The lesson is worth keeping: two of the twelve were not hard questions, they were unrun measurements.**

**What is genuinely outstanding is no longer a design question.** It's the ~50 `verify` statements on the biosensor path (Q10), and the eleven frontend doubts in `Frontend/04`. **Phase 0 is unblocked and remains the next action.**

---

# 💡 Visionary Vector — the register is a feature, not an apology

Writing this down felt like admitting weakness. It isn't — and the reason connects to the product itself.

The whole thesis of the Mind Graph is that **a belief should carry its own confidence, its provenance, and its known objections** — that's `confidence`, `justification`, `citation_state`, and `CONTESTED`. A claim that hides how strongly it's held is the thing we built an entire architecture to prevent.

A design document that hides its own uncertainty commits exactly the error the design exists to fix.

Which suggests something worth doing: **this register should itself live in the graph.** Each Q is a `Question` node; the chosen design is a `Claim` with `strength: tentative`; the rejected alternative is a `contradicts` edge; and the "what settles it" line is a **frontier item with a resolvability score.** When Phase 1 produces a review-completion rate, Q1 resolves and its dependent design decisions update — through exactly the same cascade machinery a student's retracted measurement uses.

**We'd be the first users of our own system, on the hardest available test case: our own design decisions.** That's not a gimmick — it's the cheapest possible way to find out whether the thing is actually useful before asking a student to trust it. And if the Mind Graph can't help us keep track of what we're unsure about and why, it won't help a nineteen-year-old with a breadboard either.

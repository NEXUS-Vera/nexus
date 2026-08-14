# Open Questions — live tracker

**Updated 2026-08-10.** Backend and frontend design are both first-draft complete; questions are removed as they close.
**What's left:** things needing data, things that resolve by building, frontend items, and strategic decisions. ⭐ **§6 is now fully resolved — all twelve backend doubts are closed** (`Backend/09`); the entries are kept as the record of how each was reasoned about.

---

## Settled — don't re-litigate

Compact record so these don't quietly re-open. Each has a document behind it.

| Decision | Where |
|---|---|
| Ledger (truth) → Graph (materialised view) → Sidecars (derived) | Backend/01 §1 |
| Repair via tombstoning; graph state is a view over an immutable log | Backend/01, Research/05 |
| Erasure via crypto-shredding + split plaintext/encrypted payload | Backend/02 §0 |
| Six node types, closed and enforced in code; `Method` is `Artifact(kind=method)` | Backend/01 §3.1, §3.1a |
| Tension/limitation are **edges**, not node types | Backend/01 §3.3 |
| SQLite + in-process graph, one file per user; no graph DB in v1 — ⭐ **load-tested 2026-08-10** | Backend/01 §10, Backend/09 Q11 |
| Entity resolution: block → Splink → canonical UUID + alias table | Backend/03 §5 |
| Hybrid retrieval — embeddings seed, graph expands | Backend/01 §6 |
| Agents propose, never write; determinism preserved by *recording* | Backend/05 |
| `VALIDATE` and `RETRACT` are human-only | Backend/05 §5 |
| Confidence tier bound to capability | Backend/05 §2.1 |
| Evaluation: 5 families, temporal split, Adamic–Adar baseline | Backend/06 |
| Cold start: question decomposition + skeleton closure, capped at 25 nodes | Backend/07 §1 |
| Event evolution: read-time upcasting, append-only upcasters, golden-ledger tests | Backend/07 §2 |
| Auth/tenancy: one directory per user; keys backed up separately from data | Backend/07 §4 |

---

## 0. Document status

**All Backend/08 revisions are folded in.** Backend/01 and 02 were reissued as revision 2; Backend/03 and 05 amended in place. **08 is now a historical record of what the audit found — not something you read alongside the others.**

**Build order: `Backend/01 → 02 → 03 → 07`.** Frontend: `05_Summary` first, then `01`, `06`.

---

## 1. Needs data, not thought *(bucket B)*

Neither blocks building. Both have shipped defaults so they're decisions rather than accidents.

### 1.1 Retrieval parameters
Defaults set in Backend/07 §5 — α=0.15, 10 hybrid seeds, K=50/25, and DOI weights that **ramp with graph age** (learnability starts at 0.50 and decays as real salience and outcome data arrive).
**Resolves:** weeks 2–4 of real use, by coordinate descent over clicked-rank data.

### 1.2 Cost
Envelope was estimated at ≈$8–10 per 6-week project at flat mid-tier pricing. ⭐ **Superseded by model tiering (§6.2):** extraction moved to our own OSS model, so the largest line falls to cents and ~60% of what remains is Opus. Instrumentation is built and now logs `model_tier`.
**Resolves:** week 1 of real use.
**Watch:** cost per *accepted proposal*, not per turn.

---

## 2. Resolves by building *(bucket C)*

| Question | Answered by |
|---|---|
| ~~Auto-accept threshold~~ | ✅ **resolved** — see §6.1. All `INFERRED` auto-accepts |
| ~~Do four roles beat one capability-scoped model?~~ | ✅ **resolved** — see §6.2. Kept at four; the live test is `Synthesiser: Opus vs Sonnet` |
| Skeleton coverage — how many projects find no match? | the no-match counter (Backend/07 §1.6) |
| Does lazy execution actually hold turn costs down? | cost rows by depth |
| Is 25 nodes the right cold-start cap? | abandonment instrumentation |
| Does an `AMBIGUOUS`-only queue actually get cleared? | queue telemetry — ⭐ if not, the signal is about *value*, not volume |

---

## 4. Frontend — design-ready, specs deferred

**Design first draft complete:** `Frontend/01–06`. Premise settled — **graph-as-engine**. Six surfaces, encoding matrix, interaction model, node anatomy, design tokens, and stack all decided.

### 4.1 ⚠️ Blocking before any UI is built
**F4 — do six desaturated hues actually separate?** Desaturation is required for dark mode but compresses the distance between hues, especially at small sizes and under CVD. **Half a day:** render 6 hues × 5 sizes × 4 confidence levels through a CVD simulator. **Failure condition:** <80% type accuracy at 16px, or any two hues confused under deuteranopia → collapse to 4–5 node types and re-run. Procedure in `Frontend/06` §1.6.

### 4.2 Deliberately deferred until after backend Phase 0
Screen specs (dimensions, states, component anatomy) · the search / *"ask your graph"* flow · the Sources reader (PDF span → claim) · settings, notifications, offline · a frontend build plan.

**Why deferred:** F1 and F11 could still relocate the product, and a screen spec written against imagined data is a screen spec you rewrite.

### 4.3 The eleven frontend doubts
Full detail in `Frontend/04`. The four that matter:
- **F1** — is graph-as-engine right, or did I over-correct? The research condemns *unbounded* graphs; a 50-node scoped one is a different object. **Time-to-close on the Map is the tell.**
- **F4** — see 4.1.
- **F8** — will anyone fill in the prediction form? It's the most form-like thing in a friction-free product, appearing exactly when a student wants to go build. **It's the moat.**
- ⭐ **F11** — have I designed for the wrong moment? Every surface assumes a *planning* posture; the abandonment cliff is week 3 at 1am mid-debug. The highest-value surface may be an undesigned **debug companion** — everything known about the one thing in front of you, including your own dead ends. **One afternoon observing a real student beats another research pass.**

### 4.4 ⭐ New decision raised by `Frontend/06`
**Make the backend's graph layer graphology-compatible rather than NetworkX-shaped.** graphology runs in Node *and* the browser, so both sides share one model — no traversal disagreements between what the server computes and what the client draws, and the client can run the frontier engine **offline**, which is exactly the week-3 lab-bench moment. Cheap now, expensive to retrofit. **Affects Backend/01 §10 and Backend/02.**

---

## 5. Strategic — open, and not mine to settle

### 5.1 ⭐ The data flywheel, and its consent/IP terms
The asset is **outcome-labelled decision traces**, `(state, action, verified_reward)` — not "student building habits". Open: consent and ownership terms (must be explicit and student-favourable from user one, never retrofitted), volume realism, survivor bias, and whether the near-term use is training, evaluation, or retrieval. **Leaning: evaluation/retrieval, which works at ~100× less data.**

### 5.2 B2B thesis
Constraint identified — Atlas already occupies generic evidence-heavy knowledge work, so ours must be R&D and experiment provenance. Thesis undefined.

### 5.3 The Mind Graph problem statement
Still not written as one paragraph. Backend/01 answers it implicitly. **Yours to write**, and it should land before anything is locked.

### ✅ 5.4 Picture vs substrate — **RESOLVED**
Answered by the graph-as-engine decision (§6.7). The residual — *did we over-correct?* — is `Frontend/04` F1.

### 5.5 Vertical amendment
Embedded V1 / robotics V2 both stand. Proposed additions (Queries/07): verifiability as an explicit selection criterion, and V2 robotics PoCs required to be sim-verifiable or bench-measurable. **Pending the 20-project test, which nobody has run.**

---

# 6. ✅ The twelve doubts — all resolved

These were the places where I'd made a call I was **not confident in**. All twelve closed between 2026-08-10 and now; **kept, never deleted**, because the reasoning is the point. Several carry live watch-items.

### ✅ 6.1 Will the student actually do the review? — **RESOLVED 2026-08-10**
**Decision:** auto-accept everything except `AMBIGUOUS`; `AMBIGUOUS` is always asked of the student; the contradiction sweep is the safety net; review is never blocking.
**Why:** Aryav reframed it from integrity to pedagogy — *the point of Nexus is to make the student think*, so a case the system can't resolve is precisely where a human should be reasoning. That turns the queue from an integrity gate into a **thinking prompt**, and shrinking it to `AMBIGUOUS`-only fixes the throughput problem at the same time.
**Applied to:** Backend/01 §5 · Backend/03 §5 · Backend/11 · Frontend/01 §4.4 · Frontend/05. Full record in `Backend/09` Q1.
**Still watch:** queue completion rate in week 1 — if an `AMBIGUOUS`-only queue still doesn't get cleared, the signal is about value, not volume.

### ✅ 6.2 Is the four-role split worth its cost? — **RESOLVED 2026-08-10**
**Decision:** keep all four; the split is the cost **optimiser**, not the cost driver.
**⭐ What I got wrong:** I claimed merging roles would halve the bill. Worked properly, **merging is ~70% more expensive** — `project_view` strips document bodies from the Synthesiser, so the frontier model never carries the ~8k content payload. Merge, and you pay frontier rates on every content token *and* lose the `EXTRACTED` guarantee. The genuine saving from "one agent" comes entirely from **downgrading the model**, which is a tiering decision.
**What the split was actually protecting:** not legibility — **context isolation**. Run the roles as turns of one conversation and the content is still in context; the gate checks declared capabilities, the context contains material they exclude, and the check silently becomes a lie while all tests pass. Now **Invariant 3**.
**⭐ Replaced by a model-routing rule:** *if a wrong answer is caught by code, use the cheapest model that passes the validator; if it's caught only by a human, use the best.* Five tiers — Tier 0 (no model) · **1a our own OSS model** (embeddings + all bulk extraction) · 1b Haiku · 2 Sonnet · 3 Opus. All 23 model touchpoints are mapped in `Backend/05 §3.3`.
**⭐ And it exposed latency, which I'd never designed for.** Three sequential round-trips before the student saw a word. **Display is now decoupled from acceptance** — the answer streams, the Critic runs concurrently, nothing is written until it returns. Three perceived hops → one.
**Applied to:** Backend/05 §1 (Invariant 3), §3.2–3.4, §4.2, §7 · Backend/03 §2.1 · Backend/07 §6.2a · Backend/11 §8 · Frontend/01 §4.1a. Record in `Backend/09` Q2.
**Still open, narrowly:** `Synthesiser: Opus vs Sonnet` on 20 identical queries — **~60% of spend in one config line.** Cost rows log `model_tier` from day one, so it's a query, not a build.

### ✅ 6.2a Should `Method` be a node type? — **RESOLVED 2026-08-10** *(Q12)*
**Decision:** no seventh type. `Artifact(kind=method)`, using the `uses_method_in` relation that already existed. One enum value.
**⭐ What I'd underweighted:** I filed this as reuse convenience; it's an **epistemics bug**. `ESTABLISHED` requires two distinct validated results — but **two results from the same method are not independent corroboration.** Same *distinct ≠ independent* insight as Q6, applied to results instead of citations, and I'd applied it on one axis and missed the other.
**It flags, it doesn't block.** `single_method` is surfaced, never gated — same-method replication is a legitimate reproducibility check and an undergraduate usually has one rig. Blocking would punish the normal case to catch the rare one.
**Applied to:** Backend/01 §3.1a · Backend/02 (fields, `_method_of`, merge union, 3 tests) · Backend/11 §3 · Frontend/01 §4.3. Record in `Backend/09` Q12.
**Still watch:** if `single_method` fires on nearly everything it's noise, and should be reserved for claims where a second method was plausible.

### ✅ 6.3 Will `Note` swallow everything? — **RESOLVED 2026-08-10**
**Decision:** keep the escape hatch, add a **structuring nudge** — when unstructured Notes exceed 40% of recent nodes or 15 outstanding, offer a one-pass batch structuring. An offer, never a requirement; a note that resists twice is left alone.
**Why:** *"we don't want to be Obsidian — a notes app with a pretty UI graph."* A `Note` can't hold predicted/measured, can't be corroborated, can't be contradicted — so a graph of Notes has none of the differentiators. But requiring structure kills adoption, so a threshold-triggered *offer* is the only shape that gets both.
**Health metric:** Note:structured ratio — below ~30% healthy, above ~60% means extraction is failing. Fix is more aggressive *proposal*, not more required structure.
**Applied to:** Backend/01 §5.1 + §3.1 · Frontend/01 §4.4. Record in `Backend/09` Q3.
**Still watch:** if the offer is always dismissed, the problem isn't the threshold — students don't believe structure buys them anything.

### ✅ 6.4 Should `Concept` be globally scoped? — **RESOLVED 2026-08-10**
**Decision: neither pole — scope follows provenance.** Curated skeleton concepts (or anything with a CASE id) are **global by construction**, zero resolver risk. LLM-**extracted** concepts start **project-scoped** and are **promoted** to global on a 2nd project appearance at ≥0.95. Plus a **soft-merge band**: 0.70–0.95 creates a `same_as` edge instead of merging, so both nodes survive and a mistake is an edge deletion rather than node surgery.
**Why it beats both poles:** compounding is immediate for the concepts that actually accumulate across a degree (which are nearly all curated), blast radius is contained for the risky ones, and there's **no confirmation step** — so no organisational tax.
**What I'd under-weighted:** merges were always reversible (`merged`/`split` events), and ⭐ **the widened Disagreement Engine detects bad merges for free** — two wrongly-merged concepts produce contradicting claims, which fires as CONFLICT.
**Applied to:** Backend/01 §3.1/§3.2/§5 · Backend/02 §2 + tests · Backend/03 §5 · Backend/11 §3. Record in `Backend/09` Q4.
**Still watch:** promotion rate and false-merge rate in Phase 1 — and whether the *skeleton itself* has confusable entries needing a disambiguation pass.

### ✅ 6.5 Should `Claim.kind` be a node type? — **RESOLVED 2026-08-10**
**Decision: a third option — `Claim.kind` is DERIVED from graph structure, not stored.** `observation` = supported by an Artifact or Source · `conclusion` = supported by other Claims · `hypothesis` = no live support. Computed alongside `support` and `strength`; the extractor's guess is kept as `provenance.kind_hint`, never authoritative.
**How the test resolved:** my test was *"does code branch on kind?"* — it does, twice. But that was the wrong test. Branching on a **derived** property is normal (we already do it with `support`). What matters is whether the kinds are intrinsic or readable off the graph. They're readable.
**Buys:** drift surface vanishes · ⭐ **transitions are automatic** — a hypothesis stops being one the moment you measure it · the rule that mattered (a hypothesis can never establish a Concept) already held, deriving just makes it legible.
**Scope:** only `Claim.kind`. `Artifact.kind` and `Source.kind` stay intrinsic — a firmware build vs a measurement isn't derivable.
**Applied to:** Backend/01 §3.2a · Backend/02 §2/§5.2 + tests · Backend/03. Record in `Backend/09` Q5.

### ✅ 6.6 Is `evidence_mass` damping right? — **RESOLVED 2026-08-10**
**Decision: the curve was the wrong argument.** ⭐ **Discount non-independent sources first** — a source reachable from another via `cites` is not independent evidence, and that's measurable rather than approximable. Then damp with **`√w` instead of `log₂`**: our weights live in the 1–5 range, where log₂ says the second source *doubles* the evidence (too generous when independence is uncertain) and √w says +41%.
**Caveats:** the independence check is partial (we often lack the citation graph), so damping stays the fallback. And Q6 is **low-stakes** — ranking only, tuned from click data in weeks 2–4 anyway.
**Applied to:** Backend/02 §5.2 + one test. Record in `Backend/09` Q6.

### ✅ 6.7 Is the graph the right primary artifact? — **RESOLVED 2026-08-10**
**Decided by Aryav: graph-as-engine.** The whole frontend is built on it — Bench as home, Map as the fifth thing built. ⚠️ *I failed to close this entry when the decision was made; recorded rather than quietly fixed.*
**Backend effects:** Graph API surface ⬆️ more important · `labels_at` ⬇️ lower priority (keep, build late) · Leiden unchanged (2 of 3 consumers are machine-facing) · layout stability ⬇️ weaker justification but community *identity* stability stays.
⭐ **Sharpens one argument:** graphology-on-both-sides is now justified by **offline frontier**, not by "share one graph model" — the client renders the Map rarely.
**Residual:** `Frontend/04` F1 — did I over-correct? **Tell: time-to-close on the Map. Under 10s and it's decoration.**

### ✅ 6.8 Will calibration actually move? — **RESOLVED 2026-08-10**
**Decision:** keep calibration as the headline, **change how it's measured**. Not a Brier delta — a **reliability curve** (*when you said 80% sure, were you right 80% of the time?*), plus **interval coverage** as the more sensitive early signal, with the null pre-registered.
⭐ **The confound I'd missed: difficulty drift.** Week-6 predictions are about harder things, so flat calibration on rising difficulty is a real improvement a naive before/after shows as nothing. **A reliability curve kills it by construction** — it conditions on the student's own stated confidence, which we already capture.
**Reason for optimism I'd omitted:** calibration is known to be trainable, and the mechanism is rapid unambiguous feedback — exactly what predict → measure provides.
**Pre-registered null:** primary = mean |stated − observed| across bins; predicted decrease ≥0.05; min 15 resolved predictions/student, 8+ students.
**If null:** not fatal — calibration is the measurement, not the mechanism. Lead with proof completion, and publish the null.
**Applied to:** Backend/06 §5 (rewritten) · Backend/11 · Frontend/01 §4.6. Record in `Backend/09` Q9.

### 6.9 The skeleton's granularity, not just its content
I flagged ~20–30% correction expected on the 187 concepts (Backend/04). But my real uncertainty isn't *which* concepts — it's **granularity**. Too coarse and the frontier suggests things too big to act on; too fine and it suggests trivia. Granularity is the thing that most determines whether the frontier engine feels smart or useless, and it's a domain judgement I can't make.

### ✅ 6.9 Is the Disagreement Engine the right face? — **RESOLVED 2026-08-10**
**Test run:** hand-walked the biosensor project — **~8–12 real disagreements over six weeks**, but the original trigger would have caught **~2**. I'd built the ranking around the marketing headline instead of the frequency distribution.
**Decision:** fire on **any** live `contradicts` edge; **six kinds** (CHECK · CONFLICT · STALE · BOUNDARY · FINDING · LITERATURE) set the *framing*, not whether it fires. ⭐ **Priority is computed separately from kind** and maps to P0 (inline, now) → P4 (suppressed). CHECK fires in week 1. No schema change.
**Also changed:** the headline. *"We detect discoveries"* would read as a lie at 0–1 firings; **"Nexus notices when things don't add up"** is honest across all six.
**Guards:** at most one P0 at a time; P1 tensions compete in the same ranked list as gaps — one notion of *"what matters now"*, not two.
**Applied to:** Backend/01 §8.2 · Backend/11 §6.4 · Frontend/01 §4.1 · Frontend/05. Record in `Backend/09` Q8.
**Still watch:** if CHECK fires on every trivial spec deviation it's noise regardless of tiering — it may need a materiality floor.

---

### ✅ 6.10 Is the concept skeleton at the right granularity? — **RESOLVED 2026-08-10** *(Q10)*
**Decision:** the question splits. **Structural granularity is measured and passes; `verify` is the real gap.**
**What I did:** wrote `tools/validate_skeleton.py` — the CI this design has specified since 2026-08-07 and **never run.** It found six real defects: the doc claimed **187 concepts and there are 213**, 34 redundant transitive edges, 3 isolated concepts, 86% missing `verify`, 68% missing `aliases`. Cycles and dangling refs were clean.
**⭐ What I got wrong mid-fix:** I said transitive reduction was "safe by definition." It isn't — `fft requires complex_numbers` is implied only via `impedance → ac_analysis → frequency_response → sampling_theorem`, so dropping it tells a student who knows complex numbers but not impedance that the FFT is blocked on electrical material they don't need. **The validator now splits redundancies by domain:** same/adjacent → dropped (26, applied); crossing 3+ domains → flagged and kept (8).
**⭐ Granularity, measured:** the outer fringe holds **7 cold → 19 at 15% known → 35 at 35% known.** The Bench picks 3 `NOW` items from that — **3-from-20-to-35 gives DOI real work.** Too coarse reads as a fringe of 3–5, too fine as 200. It's in the right band, so the original worry was mostly unfounded.
**⭐ The finding that reframes it:** `verify` is the seed for an Artifact's `predicted`, and **86% of it is missing** — 0% in math, digital and hardware. **Granularity being slightly off degrades ranking; `verify` being absent breaks the mechanism.** I had ranked those the wrong way round.
**The teammate's task is now bounded:** not "review 213 concepts" (nobody does that) but **"write `verify` for the ~50 concepts on the biosensor path."** ⭐ The granularity judgement arrives as a side effect — you can't write *"predict settling time and confirm on a scope"* for something that isn't an afternoon of work.
**Applied to:** Backend/04 §1.1–1.2 (+ 26 edges dropped, 187→213) · `tools/validate_skeleton.py`. Record in `Backend/09` Q10.
**Still watch:** the 3 isolated concepts (4 disconnected components), and **39% leaves** — *"unlocks N things"* is silent for two-fifths of suggestions.

### ✅ 6.11 Does SQLite + in-process hold at 10⁴ nodes? — **RESOLVED 2026-08-10, by measurement** *(Q11)*
**Decision:** yes, and not narrowly. Load-tested with `tools/bench_graph.py` instead of deferring to Phase 4.

| | 10k | 25k |
|---|---|---|
| **Personalized PageRank** *(per-turn)* | **27 ms** | **76 ms** |
| **full replay, 60k events** | **122 ms** | 123 ms |
| Louvain *(Leiden proxy)* | 592 ms | 1.75 s |
| approx. betweenness *(k=200)* | 3.0 s | 9.3 s |
| ⚠️ exact betweenness | ~118 s | ~738 s |
| peak RSS | 144 MB | 240 MB |

**⭐ 27 ms against a 2–8 s model call — storage is ~100× off the critical path.** And the **122 ms replay finally proves** the "reversible for the cost of a re-projection" claim the design has always asserted and never tested.
**One spec change:** betweenness becomes **approximate (k=200)**. It's a ranking input to `API(x)`, not a truth claim — so 118 s → 3 s is correct on the merits, not a concession.
**⭐ The constraint the doubt missed: memory, not CPU.** 144–240 MB per live graph; ten concurrent students ≈ 2.4 GB. The design said "one file per user, in-process graph" and never asked how many fit in RAM. **The 122 ms replay makes LRU eviction free** — *the property that makes the storage reversible is the same one that makes it multi-tenant*, and I'd only ever argued the first.
**Applied to:** Backend/01 §7 + §10 · Backend/07 §4.6 (LRU) + §6 · `tools/bench_graph.py`. Record in `Backend/09` Q11.
**Still watch:** concurrency under real load, and real graph density — synthetic avg-degree was 8.

---

---

# 7. ⚙️ Backend implementation — what is left, and who does it

**Status: the backend is code-complete against `Backend/01`–`07`. 300 tests pass.**
`Backend_implementation/` · run `python3 -m pytest -q` · CI runs the suite under
two hash seeds plus the replay check and the skeleton validator.

## 7.1 🔴 Blocked on Aryav — nothing else moves

| # | What | Unblocks |
|---|---|---|
| **B-1** | ⭐ **An OpenAI-compatible endpoint + key.** `export MG_ENDPOINT=... MG_API_KEY=...` Together / Fireworks / Groq all work | `mg ask` (the entire agent layer) · real extraction · embeddings · **the Q2 tiering experiment** |
| **B-2** | **Confirm the four model choices.** Defaults are Llama-3.3-70B / Haiku 4.5 / Sonnet 5 / Opus 5, each overridable by env var | which model each tier actually runs |
| **B-3** | **10–20 real project files** — firmware, a datasheet PDF, measurement CSVs, your notes | ⭐ **accept rate by tier** (the most important early number) and **quarantine rate**, which is the guard on the Tier 1a choice |
| **B-4** | **~50 `verify` statements** from the ECE teammate (P-3 in `Backend/10`) | the frontier's gate — *what would count as knowing this* |

⚠️ **Do not run extraction on a frontier model "for now."** The quarantine rate
against the *small* model is what validates the tier decision, and you only get
it by running the tier you intend to ship.

## 7.2 🟡 Built, on standby — waiting on §7.1

Every one of these is written and unit-tested; none can produce a real number yet.

- **The Q2 experiment** — `Synthesiser: Opus vs Sonnet` on 20 identical queries. ~60% of turn spend in one config line; cost rows already log `model_tier`, so it is a query rather than a build.
- **The reliability curve** — needs 15 resolved predictions per student across 8+ students. Pre-registered null is in code (`evaluation.PREREG`) so it cannot be moved afterwards.
- **Retrieval vs the Adamic–Adar baseline** on real data. ⭐ If we cannot beat a 2003 algorithm, the graph is not earning its cost.
- **The cost envelope** — replaces `Backend/07 §6`'s estimate with measured rows.
- ⚠️ **Schema evolution is now proven, once.** `upcast.py` carries a real v1→v2 upcaster and a frozen v1 golden ledger that CI replays. The mechanism works; it stays lightly exercised until a genuine v3 exists.

## 7.3 🟢 Done since the last revision

Vision lane (images routed; ⚠️ **Tier 2, not 1a** — a misread scope trace is
caught by no schema check) · serial/scope-log parser · git-history parser ·
`HTTPAgent` and `HTTPEmbedder` · vector store · snapshot persistence ·
cost instrumentation · **the Graph API with server-minted role tokens** ·
`mg ask / nudge / promote / export / cost / embed` · packaging and CI.

## 7.4 ⚠️ Findings worth carrying into the frontend

Each is pinned as a test so it cannot silently regress.

- **A role without `READ_CONTENT` cannot text-search at all.** Hybrid seeding matches against labels, which are user text — so a structure-only caller gets *"you may not look"*, never a silent empty result. Structural routes stay open to it.
- **Lenses cancel where a node's relations are uniform.** PageRank normalises out-edges per node, so a lens reorders by relation *mix*, not by relation presence. Weaker than the design implies.
- **Trigram seeding false-matches on short queries** — `"hydrated"` retrieves `"calibrate"`. This is exactly what the embedding half of the hybrid seed fixes, and it will not improve until **B-1**.
- **Entity resolution under-merges.** `skin impedance` / `skin impedence` scores 0.684, under the 0.70 soft band. Exact-match and alias paths already catch the high-frequency `I²C` case; these are the residue, and `Backend/03 §5` says the threshold is calibrated in week one.

---

## Research status

| Area | State |
|---|---|
| Reference systems, prior art, formalisms, standards | ✅ complete |
| Failure modes, integrity, operating economics | ✅ complete |
| University / course data | ✅ complete |
| Frontend | ✅ complete (Research/07) |
| Agent contract, evaluation, cold start, schema evolution | ✅ complete (Backend/05–07) |

**Backend research and design are complete.** Everything above is either awaiting data, awaiting a build, strategic, or a doubt worth arguing about — none of it is awaiting further research.

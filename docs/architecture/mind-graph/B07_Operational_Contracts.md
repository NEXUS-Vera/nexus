# Operational Contracts

**Backend / 08.** Closes the last design gaps: cold start, event schema evolution, API contract, auth and operations, retrieval defaults, and a cost envelope.
**After this, the backend is design-complete.** What remains needs the system to exist before it can be answered.
**Date:** 2026-08-07

---

# 1. Cold start — what's in the graph 60 seconds after signup

## 1.1 The problem

A student arrives with one idea and no history. Atlas concedes the same failure — *"a project with one or two items will produce a sparse map that shows little structure."* An empty graph is worse than no graph: it makes the product look broken at exactly the moment the student decides whether to continue.

## 1.2 The principle

> **The graph is never empty, because it starts as a structured question rather than an empty container.**

At t=0 nothing is *validated* — and that's correct, not a deficiency. **The first screen should show what you don't know yet**, which is precisely what a student starting a project needs and precisely what the frontier engine is for.

## 1.3 Three seeding sources, in order of availability

**① The question itself — always available.**
The student types one sentence. It becomes the root `Question` node. An LLM decomposes it into 3–6 sub-`Question`s, emitted as `INFERRED` proposals routed straight to the student for confirmation — which doubles as the fastest possible demonstration of how the review gate works.

```
"Can skin impedance track hydration?"
 ├── What frequency range separates hydrated from dehydrated tissue?
 ├── What electrode configuration is stable on skin?
 ├── What confounds the measurement (sweat, temperature, contact pressure)?
 └── What accuracy would be enough to be useful?
```

**② The concept skeleton — available for any embedded project.**
Match the question and sub-questions against the skeleton (Backend/04) by label and alias, pull the matched concepts **plus their `requires` closure two levels up**. These enter as **phantom** `Concept` nodes — referenced, unvalidated — with prerequisite edges already in place.

That single step is what makes the frontier engine work on day one: `requires` edges exist, so the outer fringe is computable immediately.

**③ The transcript — optional, and it is a prior, not a state.**
If the student uploads one, matched concepts get `exposure` provenance — **never `validated`**. Research 04 §6.5: a passed course is evidence of exposure, not knowledge. Grade and recency modulate confidence; nothing enters the knowledge state without a `Claim` or an `Artifact` behind it.

## 1.4 The resulting graph, and its budget

| Element | Count |
|---|---|
| root `Question` | 1 |
| sub-`Question`s | 3–6 |
| phantom `Concept`s from the skeleton | 12–20 |
| `requires` edges | 15–30 |
| exposure marks (if transcript) | 0–15 |
| **validated anything** | **0** |

**Hard cap: 25 nodes in the initial view.** Half the comprehension limit (Research 07 §1.1), deliberately. If the skeleton match returns more, rank by DOI and show the top 25 — the rest exist in the graph and appear on expansion.

## 1.5 The first session's goal

**Get one `Artifact` with an `agreement` value before the student leaves.**

That's the loop closing, the first non-phantom node, and the first calibration data point. It's also the cheapest possible proof that this product is different from a notes app. For embedded projects it's usually achievable — flash a blink sketch, read a sensor once, confirm a supply rail — and the onboarding should aim at whatever the *cheapest verifiable thing* in the skeleton's neighbourhood is.

## 1.6 Failure modes

| Failure | Guard |
|---|---|
| **Question too vague** (*"build a robot"*) → generic decomposition | Ask for a measurable success criterion. This is Queries/07's verifiability rule arriving as an onboarding step — *"how will you know it worked?"* is the single most useful question to ask an undergraduate, and it fixes the cold start as a side effect |
| **No skeleton match** (student outside embedded systems) | Degrade to question decomposition only; flag the project low-confidence; log it. A count of these is the honest measure of when to invest in a second domain skeleton |
| **Over-seeding → day-one hairball** | The 25-node cap |
| **Transcript treated as knowledge** | Structurally prevented: `exposure` is provenance, not `Support.SUPPORTED` |

---

# 2. Event schema evolution — upcasting

## 2.1 Why this is load-bearing

The ontology *will* change in month 4. The projector must still fold events written under the old schema, or replay breaks — and replay determinism is the invariant the entire ledger design rests on (Backend/02 §5.2, Backend/05 Invariant 2).

## 2.2 The rule that decides the approach

> **Stored events are never rewritten.**

Not a preference — a consequence. The hash chain is computed over the stored bytes (Backend/02 §4). Rewriting an event invalidates every hash after it and destroys tamper evidence. So migration-in-place is unavailable, and **read-time upcasting** is the only option.

## 2.3 The mechanism

Every event carries `schema_version: int`. The projector folds an old event forward through a chain of pure functions before applying it.

```python
CURRENT_VERSION = 3

UPCASTERS: dict[int, Callable[[dict], dict]] = {
    1: _v1_to_v2,   # split `body` into `body_ref` + blob
    2: _v2_to_v3,   # relation `related_to` -> `relates_to`
}

def upcast(payload: dict, from_v: int) -> dict:
    for v in range(from_v, CURRENT_VERSION):
        payload = UPCASTERS[v](payload)
    return payload

def apply(state, event):
    payload = upcast(event.structural, event.schema_version)
    HANDLERS[event.type](state, payload, event.seq)
```

## 2.4 The four rules

1. **Upcasters are pure and total.** No I/O, no clock, no model calls. Same input → same output, forever. They run inside the projector and inherit its purity requirement.
2. **Upcasters are append-only.** ⭐ **Never edit a shipped upcaster** — that retroactively changes history and silently alters every past graph. If `_v1_to_v2` was wrong, fix it in `_v3_to_v4`.
3. **Prefer additive changes.** New optional fields and new enum members need no upcaster. Removals and renames do.
4. **Removing an enum member needs an explicit landing place.** Map the retired value to the nearest surviving one and set `quarantined=true`, so the loss is *visible in the graph* rather than silently absorbed.

## 2.5 The golden-ledger test — the thing that actually protects the invariant

Every version bump adds a frozen fixture:

```
tests/golden/
├── v1_ledger.jsonl   +  v1_expected_hash.txt
├── v2_ledger.jsonl   +  v2_expected_hash.txt
└── v3_ledger.jsonl   +  v3_expected_hash.txt
```

```python
@pytest.mark.parametrize("v", [1, 2, 3])
def test_old_ledger_still_projects(v):
    state = project(load_golden(f"v{v}_ledger.jsonl"))
    assert state_hash(state) == read(f"v{v}_expected_hash.txt")
```

**Read the semantics carefully, because this is subtle.** When an upcaster *deliberately* changes projected output, the expected hash changes — and that's fine. The test isn't asserting the output never changes; it's asserting the change was **intentional**. So:

> **Updating a golden hash requires a changelog entry naming the upcaster that caused it.** A hash that moves with no corresponding upcaster is a bug — usually accidental non-determinism creeping into the projector, which is exactly the failure this whole apparatus exists to catch.

---

# 3. API contract

## 3.1 Errors

| Code | Meaning | Retry? |
|---|---|---|
| `BAD_REQUEST` | malformed input | no |
| `NOT_FOUND` | unknown id | no |
| `CAPABILITY_DENIED` | role lacks the capability (Backend/05 §2) | no |
| `BUDGET_EXCEEDED` | turn or daily cap hit | after reset |
| `QUARANTINED` | target failed validation and is inert | no |
| `CONFLICT` | proposal already accepted/rejected | no |
| `SCHEMA_VERSION_UNSUPPORTED` | event newer than this projector | no — **deploy first** |
| `INTERNAL` | unexpected | yes, with backoff |

## 3.2 Pagination

**Cursor-based on `seq`, never offset.** `seq` is monotonic and stable, so a cursor stays valid while the graph grows underneath it — offsets don't.

```
GET /v1/graph/query?...&cursor=<seq>&limit=50
→ { items: [...], next_cursor: 1284, truncated: false }
```

## 3.3 Partial results are always explicit

A budget breach returns **200 with `truncated: true` and a `reason`** — never a silent short answer. A student who doesn't know the result was budget-limited will read it as complete, which is a correctness failure dressed as a performance optimisation.

## 3.4 Idempotency

`propose`, `accept`, `validate`, and `retract` take an `Idempotency-Key`. A repeat returns the original `proposal_id`/`seq` rather than appending a duplicate — necessary because a client retry after a network timeout must not double-write to an append-only log.

## 3.5 Versioning

Two independent version numbers, and conflating them is a trap:

- **`/v1/` — the HTTP API.** Changes when the client contract changes.
- **`schema_version` — the event format.** Changes when the ontology changes.

A projector must refuse events newer than it understands (`SCHEMA_VERSION_UNSUPPORTED`) rather than guessing. **Deploy the projector before anything writes the new version.**

---

# 4. Auth, tenancy, and operations

## 4.1 Layout — one directory per user

```
users/{user_id}/
├── ledger.db          # append-only, hash-chained
├── graph.snapshot     # derived — regenerable, never authoritative
├── vectors.db         # sqlite-vec
├── sidecars/          # salience, communities, centrality
└── blobs/             # encrypted bodies
```

**Tenancy isolation is a filesystem property plus a path check.** Boring, auditable, and it makes per-user backup and per-user deletion trivial.

## 4.2 Keys

- One encryption key per user, stored in a KMS or a keyfile **outside the data directory**.
- Erasure = destroy the key + append a `shredded` event (Backend/02 §0).
- ⚠️ **Keys and data must never be backed up to the same place.** If a restore can recover both, crypto-shredding is defeated by your own disaster recovery, and the erasure guarantee is fictional.

## 4.3 Auth

Standard sessions/JWT for users. For agents, the `role` token is **server-minted and server-checked** — capabilities are never accepted from the client (Backend/05 §8). A client that could name its own capabilities has none.

## 4.4 Backup and restore

| Artifact | Backup | Restore |
|---|---|---|
| `ledger.db` | ⭐ **yes — this is the only thing that matters** | copy back |
| encryption key | yes, **separately** | from KMS |
| `graph.snapshot` | no | **re-project from the ledger** |
| vectors, sidecars | no | recompute |

**Restore = replay, not snapshot restoration.** A restored snapshot could disagree with the ledger; a replayed one cannot. This is the ledger design paying rent.

## 4.5 Retention

Ledger forever (modulo erasure). Snapshots and sidecars are disposable by definition — deleting them costs CPU, never data.

## 4.6 ⭐ Concurrency — the constraint the load test actually found *(added 2026-08-10, Q11)*

`Backend/09` Q11 measured the design at 10⁴ and 25×10³ nodes. CPU was never close to a limit — **the per-turn retrieval path is 27 ms against a 2–8 second model call.** What it did find:

> **A live in-process graph costs 144 MB at 10k nodes, 240 MB at 25k.** Ten concurrent students ≈ **2.4 GB**.

The design has always said *"one file per user, in-process graph"* and **never asked how many fit in RAM at once.** That, not query speed, is what bounds a box.

**Policy — LRU eviction:**

```
resident_cap   = min(RAM_budget / 250MB, configured_max)
on evict       drop the in-process graph; keep ledger.db (it is the truth)
on next request replay from the ledger   ← 122 ms measured, 60k events
```

⭐ **This is free because of the number in the same table: full replay is 122 ms**, and it is bound by *event count*, not node count — so it does not degrade as a graph grows. **The property that makes the storage choice reversible is the same one that makes it multi-tenant**, which is an argument §4.4 makes for restore and never made for concurrency.

**Warm-path optimisation, if ever needed:** keep `graph.snapshot` on disk for evicted users and load it instead of replaying. **Not v1** — 122 ms does not need optimising, and a snapshot that disagrees with the ledger is exactly the failure mode §4.4 rejects.

---

# 5. Retrieval defaults

Not settleable from an armchair, but they should be a **decision** rather than an accident. Ship these, then tune.

| Parameter | Default | Why |
|---|---|---|
| PPR restart `α` | **0.15** | standard; higher = more local, lower = more diffuse |
| seeds | **10** — 5 embedding-kNN + 5 lexical, unioned and deduped | hybrid seeding (Research 05 §3.1) |
| K (UI) | **50**, capped at 25 during cold start | comprehension limit |
| K (agent) | `token_budget / avg_node_tokens` | hard cap |
| max hops in expansion | **3** | beyond this, PPR weight is negligible anyway |

## 5.1 DOI weights ramp with graph age

⭐ **The important subtlety: on day one, salience and outcome are empty.** Weighting them at t=0 means weighting noise. So the weights start skewed toward what actually exists and ramp as evidence accumulates.

| Weight | Day 1 | Mature | Rationale |
|---|---|---|---|
| `w₁` centrality | 0.30 | 0.20 | structure is all we have early |
| `w₂` salience | 0.00 | 0.20 | needs access history |
| `w₃` outcome | 0.00 | 0.20 | needs validated artifacts |
| `w₄` confidence | 0.20 | 0.15 | |
| `w₅` learnability | **0.50** | 0.25 | ⭐ early on, "what can you do next" dominates — and it's the only signal that exists at t=0 |
| `w₆` staleness | −0.10 | −0.10 | constant penalty |

Ramp linearly over the first ~200 accepted events, then hold.

## 5.2 Tuning protocol

Log the DOI rank of every node the student clicks. Weekly, run coordinate descent over `w₁..w₆` to minimise mean clicked-rank on the last two weeks of data. It's a learning-to-rank problem; coordinate descent is enough at this scale and is inspectable, which matters more than optimality here.

**Expected to converge in weeks 2–4 of real use.** Until then the defaults hold, and nothing is blocked.

---

# 6. Cost envelope

⚠️ **This is an estimate from token arithmetic, not a measurement.** No independent cost data exists for this class of system (Research 06 §1.1) — that's precisely why Backend/02 §8 instruments it. Treat the shape as informative and the magnitude as ±3×.

## 6.1 Assumptions — one 6-week embedded project

| | |
|---|---|
| sources ingested | 20 (papers, datasheets, pages) @ ~15k tokens |
| graph turns | ~100 over six weeks |
| retrieval per turn | 50 nodes ≈ 8k input tokens |
| roles woken per turn | ~2 average (lazy execution) |
| output per role | ~1.5k tokens |
| nodes embedded | ~2,000 |

## 6.2 Arithmetic

```
extraction    20 × 15k        =  300k in   |  20 × 2k  =  40k out
turns        100 × 8k         =  800k in   | 100 × 3k  = 300k out
embeddings  2,000 × 500       =    1M      (embedding-priced, ~50× cheaper)
                              ───────────────────────────────────────
                                 ~1.1M in  |  ~340k out  |  1M embed
```

At roughly **$3/M input and $15/M output** (mid-tier frontier pricing), that's **≈ $3.3 + $5.1 ≈ $8–10 per project**, plus cents for embeddings.

## 6.2a ⭐ Revised by model tiering *(2026-08-10, Backend/09 Q2)*

The arithmetic above prices **every token at mid-tier frontier rates**, which the design no longer does. `Backend/05 §3.2` routes each job by *verifiability*, and two lines move enough to change the shape:

| Line | Before | After | Effect |
|---|---|---|---|
| **extraction** 300k in / 40k out | mid-tier | ⭐ **Tier 1a — our own OSS model** | falls to **cents**. The output is schema-constrained and code-validated, so a small model is safe here *because it was never trusted* |
| **embeddings** 1M | embedding-priced | Tier 1a | already negligible; now also ours |
| **turns** 800k in / 300k out | flat mid-tier | **split Sonnet / Opus** | Grounder + routine Critic on Sonnet; Synthesiser, `BOUNDARY` and hard-turn planning on Opus |

**Directional share of what remains** — to be replaced by the `usd_est` rows in Backend/05 §7 as soon as Phase 3 runs:

| Tier | share |
|---|---|
| 0 (no model) | 0% |
| 1a (ours) + 1b (Haiku) | ~4% — ⭐ **was ~35%**, almost all of it extraction |
| 2 — Sonnet | ~35% |
| 3 — Opus | **~60%** |

⭐ **The whole cost question is now three lines of config**, and one of them — the Synthesiser — is most of it. That is exactly what the Q2 Phase 3 experiment tests, and §7's cost rows log `model_tier` from day one so the experiment is a query rather than a build.

**Two levers below tiering**, both cheap and both large at ingestion volume: **prompt-cache the extraction system prompt** (byte-identical for every chunk of every document — the largest cacheable surface in the system), and **cache the shared structural payload** across the parallel role calls within a turn.

## 6.3 What this implies

- ⚠️ **"Lazy execution is the business model" was wrong** — or at least mis-aimed. `Backend/09` Q2 works the arithmetic properly: because `project_view` strips content from the Synthesiser, **merging roles is ~70% more expensive, not cheaper.** The split is the cost *optimiser*, not the cost driver. What actually governs the bill is **which model each job runs on**, and lazy execution is a latency and quality lever rather than the thing keeping the lights on.
- ⭐ **Extraction was a third of the cost. After tiering it is close to zero** — and it was always the most compressible line, because it is the only large one whose output is mechanically validated.
- **Turns dominate and scale with engagement**, so a *more* engaged student costs more — the wrong-way-round incentive, and now concentrated almost entirely in Opus.
- Atlas charges **$16/month** (Research 03 §0). With extraction off the frontier models the envelope should land meaningfully under $8–10, but **I would not quote a number I have not measured** — the point of §7's rows is to replace this section, not decorate it.
- **The number to actually watch** is cost-per-*accepted*-proposal, not cost-per-turn — it's the one that says whether the graph is earning its keep, and Backend/05 §7 already logs both halves.

---

# 7. Status

**The backend is design-complete.** Everything remaining requires the system to exist:

| Item | Resolves |
|---|---|
| Retrieval weights | weeks 2–4 of real use, from click-rank data |
| Real cost numbers | week 1 of real use |
| Auto-accept threshold | week 1, from accept rate (Backend/06 §2.1) |
| Whether four roles beat one | first cost comparison |
| Skeleton coverage | from the count of no-match projects (§1.6) |

Nothing above is blocked on further thinking. **Phase 0 is the next action** (Backend/02 §9): ledger, projector, cascade, and the tests that prove replay determinism.

---

# 💡 Visionary Vector — cold start is the product demo

§1 solves an engineering problem: don't show an empty screen. But look at what the seeded graph actually *is*.

Sixty seconds after signup, before the student has done any work, the system displays: their question decomposed into the sub-questions that actually decide it, the concepts those depend on, the prerequisite structure between them, which ones their transcript suggests they've met, and **which single thing they're ready to do first.**

That is not an onboarding state. **That is the entire value proposition, rendered before the user has invested anything.**

Compare what every competitor shows at t=0: Atlas shows an empty project awaiting uploads. Obsidian shows an empty vault. Notion shows a blank page. All of them require the user to supply value before receiving any — which is exactly why PKM tools have famously brutal retention curves.

We can invert it, and the reason is structural rather than clever: **we have a domain model (the concept skeleton) that exists before the user does.** Nobody else in this category has one, because nobody else picked a vertical narrow enough to build one — which makes the vertical decision (Queries/07) load-bearing in a second, unexpected way.

The sharpest version of this: **the cold-start graph is the marketing asset.** Not a rendered hairball of 780 nodes, but a real, small, honest graph of *your* question with *your* gaps in it, generated live from one sentence, on the landing page, before signup. It's cheap to run (one decomposition call plus a skeleton lookup), it's impossible for a general-purpose competitor to imitate without the domain skeleton, and it demonstrates the product's actual claim — *we can tell you what you don't know yet* — in the only way that is ever convincing, which is by doing it to you.

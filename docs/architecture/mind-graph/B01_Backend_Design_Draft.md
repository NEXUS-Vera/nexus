# Mind Graph — Backend Design

**Revision 2** — 2026-08-07. Backend/08's revisions are folded in; section numbers are unchanged so cross-references from 03–08 still resolve.
**Purpose:** the complete backend architecture. Where I had to choose, I chose and named the tradeoff.
**Status:** draft for critique. Expect to disagree with ~30% of it; that's the point.

> **What changed in revision 2** (audit against Research/01–06 — full reasoning in Backend/08):
> `Edge.weight` · `Support.CONTESTED` · corroboration gate on claim strength · `external_ids` · the **crossover scorer** (§7) · **dead-end memory** with resurrection (§8.3) · the **Disagreement Engine** (§8.2) · co-citation and unlinked mentions (§7) · citation states (§5) · `View` as a first-class object (§9) · structured export (§9).
> Nothing was removed. The skeleton held; what was missing was epistemic richness.

---

## Assumptions I fixed rather than asked about

| # | Assumption |
|---|---|
| A1 | **Single user per graph.** No collaboration in v1; the design must not preclude it |
| A2 | **10³–10⁴ nodes per user.** A 6-week project makes hundreds; a degree makes thousands. Never millions |
| A3 | **Thousands of users, not millions.** Per-user cost matters more than aggregate throughput |
| A4 | **Latency:** ingest may take minutes (async). A query returns in **< 2 s**. A view renders in **< 500 ms** |
| A5 | **Cloud-hosted, not local-first.** Local-first is defensible but costs us the flywheel and the eval corpus |
| A6 | **Some agent architecture reads and writes the graph.** The design doesn't assume how many |
| A7 | **Embedded systems, V1** (Queries/07) |

---

# 1. The premise, settled

Everything depends on this, so it's decided first.

> **The ledger is the truth. The graph is a view.**

Not "record of a process" *or* "projection of a corpus" — **both, stacked**:

```
┌──────────────────────────────────────────────────────────┐
│  LEDGER          append-only, immutable, never edited     │  ← the asset
│                  every observation, assertion, outcome    │
└──────────────────────────────────────────────────────────┘
                            │  deterministic projection
                            ▼
┌──────────────────────────────────────────────────────────┐
│  GRAPH           materialised view. rebuildable at will.  │  ← the working set
└──────────────────────────────────────────────────────────┘
                            │  derived, disposable
                            ▼
┌──────────────────────────────────────────────────────────┐
│  SIDECARS        salience · embeddings · communities ·    │  ← recomputable
│                  centrality · crossover · learning signal │
└──────────────────────────────────────────────────────────┘
```

**Why this, not the alternatives:**

- It makes every failure mode **repairable**. Hallucinated edges, entity fragmentation, schema drift — all fixed by re-projecting rather than re-extracting. History survives; bad structure doesn't.
- ⭐ It makes the **graph database a swappable detail** — the single most valuable property here. If we pick wrong (and Kuzu was archived under us mid-research, so we might), we re-project into a different store in an afternoon. Almost nothing else is that reversible.
- Bitemporality is free: system time is the ledger's, world time lives on the events.
- The sidecar principle becomes structural rather than a discipline we maintain.

**Cost:** every write is two writes, and the projector becomes correctness-critical. Accepted.

**This is the one premise worth settling before anything else.**

> ### ✅ RESOLVED — Q7 · *Is the graph the right primary artifact?* — **graph-as-engine** *(2026-08-10)*
>
> Decided by Aryav: **the graph is the engine, and the visual map is a secondary view.** Everything the graph is good at — multi-hop retrieval, provenance, supersession, crossover — is machine-facing, and the HCI evidence for node-link diagrams and learning is null-to-negative. So the product leads with ranked *answers*, not a diagram.
>
> This section is unaffected: the ledger→graph→sidecar stack is what makes those machine-facing capabilities possible in the first place. What changed is downstream — the Graph API became the primary consumer path, and `labels_at` dropped in priority (kept, because it can't be retrofitted).
>
> **Full record: `Backend/09` Q7. The residual — *did we over-correct?* — is `Frontend/04` F1.**

It isn't forced — a projection-style graph regenerating from files and chat would be dramatically cheaper. The argument for this design is that it's the only version where time, outcome, and supersession mean anything. That's an argument, not a given.

---

# 2. Components

```
                        ┌───────────────┐
   files, chat,         │   INTAKE      │  route · dedupe · cache
   photos, serial ─────▶│               │  cheap filters first
   logs, transcript     └───────┬───────┘
                                ▼
                        ┌───────────────┐
                        │  EXTRACTOR    │  ontology-constrained
                        │  (async)      │  AST / vision / LLM
                        └───────┬───────┘  API+GPU-bound
                                ▼
                        ┌───────────────┐
                        │  RESOLVER     │  block → verify → canonical UUID
                        └───────┬───────┘
                                ▼
                        ┌───────────────┐
                        │  PROPOSALS    │  nothing is committed yet
                        └───────┬───────┘
                     ┌──────────┴──────────┐
              auto-accept              review queue
              (EXTRACTED)              (INFERRED/AMBIGUOUS)
                     └──────────┬──────────┘
                                ▼
                    ╔═══════════════════════╗
                    ║       LEDGER          ║  append-only
                    ╚═══════════┬═══════════╝
                                ▼
                        ┌───────────────┐
                        │  PROJECTOR    │  deterministic, replayable
                        └───────┬───────┘
                                ▼
                    ╔═══════════════════════╗
                    ║       GRAPH           ║
                    ╚═══════════┬═══════════╝
                     ┌──────────┴───────────┐
                     ▼                      ▼
             ┌───────────────┐      ┌───────────────┐
             │   ANALYZER    │      │  RETRIEVAL    │  seed→PPR→DOI
             │  (deferred)   │      │               │
             │  CPU-bound    │      └───────┬───────┘
             └───────┬───────┘              │
                     ▼                      ▼
             ┌───────────────┐      ┌───────────────┐
             │  SIDECARS     │─────▶│   FRONTIER    │  gaps + tensions
             └───────────────┘      └───────┬───────┘
                                            ▼
                                    ┌───────────────┐
                                    │  GRAPH API    │  agents + UI
                                    └───────────────┘
```

| Component | Job | Bound by |
|---|---|---|
| **Intake** | route by type, dedupe by content hash, drop what we don't want | I/O |
| **Extractor** | raw input → *candidate* nodes and edges under a fixed ontology | **API / GPU** |
| **Resolver** | is this entity one we already have? | CPU |
| **Proposals** | hold uncommitted changes; route by confidence | — |
| **Ledger** | the append-only truth | disk |
| **Projector** | fold events into a graph. Deterministic. Replayable from zero | CPU |
| **Analyzer** | clustering, centrality, salience, crossover, co-citation. **Incremental, deferred** | **CPU, single-core** |
| **Retrieval** | seed → expand → rank → cap | CPU |
| **Frontier** | what to do next: gaps *and* tensions | CPU |
| **Graph API** | the only way anything touches the graph | — |

**The split that matters:** the Extractor is API-bound and slow; the Analyzer is CPU-bound and slow. **Neither may sit in a user's blocking path, and they must not be the same worker.** Two independent sources confirmed the clustering/layout bottleneck is single-core CPU (Research/02 §6, Research/06 §1.2).

---

# 3. Data model

## 3.1 Node types — six, closed, enforced in code

```python
NodeType = Literal["Concept", "Question", "Claim", "Artifact", "Source", "Note"]
```

| Type | What it is | Example |
|---|---|---|
| **Concept** | a unit of knowledge. Aliased, and **scoped by provenance** (§3.2) | `I²C`, `PID control`, `skin impedance` |
| **Question** | an open problem at any scale. **The project itself is a Question** | *"Can skin impedance track hydration?"* |
| **Claim** | an assertion whose truth can change | *"47 kΩ at 50 kHz indicates hydrated"* |
| **Artifact** | ⭐ **something the student made or ran** | firmware build, circuit, experiment run, measurement, ⭐ **method** (§3.1a) |
| **Source** | external evidence | paper, datasheet, video, lecture, transcript line |
| **Note** | user prose not yet structured — **the escape hatch** | *"felt like the 5V rail was noisy?"* |

**Why these six:**

- **`Artifact` is the whole thesis.** No competitor has a node for a thing you built and measured (Research/03 §9). If we cut one type, it isn't this one.
- **`Note` is non-negotiable.** It's the direct implementation of *Formality Considered Harmful* (Research/04 §2.3): a student must always be able to dump unstructured thought in and have it be first-class. Structure gets *proposed* over it later. Without this, people work around the system. ⭐ **Guarded by the structuring nudge (§5.1)** so it doesn't swallow the graph.
- **`Claim` absorbs Verdict / Finding / Hypothesis** as a `kind` enum. Three types differing only in evidence depth is exactly the drift surface Research/05 §1.3 warns about.
- **Limitation and Tension are NOT node types.** They're edges (`contradicts`). That makes tension countable, rankable, and resolvable rather than decorative — and §8.2 depends on it.

> ### ✅ RESOLVED — *Is this the right set of six?* — **yes, six** *(Q3, Q5, Q12 all closed 2026-08-10)*
>
> **Q3** — will `Note` swallow everything? Guarded by the structuring nudge in §5.1: a batch offer when unstructured Notes exceed 40% of recent nodes or 15 outstanding. An offer, never a requirement.
>
> **Q5** — should `Claim.kind` be three types? No — `kind` is **derived from structure**, never stored (§3.2a).
>
> **Q12** — should `Method` be a seventh type? **No.** It is `Artifact(kind=method)` with the already-defined `uses_method_in` relation — see §3.1a. Zero new types.
>
> **Full record: `Backend/09` Q3, Q5, Q12.**

## 3.1a ⭐ Method — a kind of Artifact, not a seventh type *(added 2026-08-10, Q12)*

*"4-wire Kelvin at 50 kHz, 10 mV excitation, dry Ag/AgCl, 2 cm spacing, forearm."*

Not a `Concept` — the general technique is one, your specific parameterisation isn't. Not a `Claim` — it asserts nothing. And not a run, because **many runs share one method.**

It *is* something the student made — a procedure — so it is an **`Artifact`**:

```
Artifact(kind=run) --uses_method_in--> Artifact(kind=method)
```

`uses_method_in` was already in the relation vocabulary (§4, from CiTO) and `Artifact` already carries `spec` for parameters. **One enum value, no new type, no new relation.**

**Three things it buys, in increasing order of importance:**

1. **Comparability.** Two measurements taken with different methods are not directly comparable — and *"the paper doesn't apply to your setup"* is very often *"different method."* That is precisely the `BOUNDARY` tier of the Disagreement Engine (§8.2), which currently has to reason over unstructured prose.
2. **Reuse and refinement.** A method evolves over six weeks. *"Every measurement taken before I fixed the electrode spacing"* is a common query and is currently unanswerable.
3. ⭐ **Corroboration independence.** `ESTABLISHED` requires `corroboration ≥ 2`, but **two results from the same method are not independent evidence.** With a Method node this is computable, and `Backend/02` adds a `single_method` flag — which **surfaces the weakness without blocking establishment**, since same-method replication is a legitimate reproducibility check and an undergraduate usually has one rig.

The third is the same *distinct ≠ independent* insight Q6 applied to citations, now applied to results.


## 3.2 Node schema

```python
Node:
  id            UUID          # canonical, permanent, never derived from a path
  type          NodeType
  kind          str | None    # ⭐ Artifact/Source: INTRINSIC (code|run|paper…)
                              #    Claim: DERIVED from structure, never stored — §3.2a
                              # Artifact: code|circuit|run|measurement|document|method
                              # Source: paper|datasheet|video|course|web
  label         str           # display; ENCRYPTED at rest
  aliases       [str]         # every surface form seen ← entity resolution
  body_ref      str | None    # blob pointer, encrypted
  scope         global | project    # ⭐ Concept only — set by PROVENANCE, see below
  project_id    UUID | None        # null iff scope == global
  labels_at     {zoom: str}   # semantic-zoom label hierarchy
  external_ids  {str: str}    # ⭐ NEW — {"CASE": "...", "wikidata": "Q..."}
  created_seq   int           # system time
  valid_from    ts | None     # world time
  valid_to      ts | None
  rank          preferred|normal|deprecated     # Wikidata model
  support       supported|unsupported|contested|unknown   # ⭐ CONTESTED added
  superseded_by UUID | None
  quarantined   bool
```

Four fields earn their place specifically:

- **`aliases`** — the cheapest defence against entity fragmentation (Research/05 §1.2), the silent failure that destroys multi-hop.
- **`labels_at`** — semantic zoom needs a label per scale (`"Power"` → `"Buck converter"` → `"Inductor ripple"`). A *schema* requirement, not a UI one; retrofitting means re-labelling everything.
- **`rank`** — deprecated ≠ deleted. Straight from Wikidata at 100M-item scale.
- **`external_ids`** ⭐ — CASE gives competencies globally unique IDs (Research/04 Tier 6). Free now, expensive to backfill, and it's the hook for ever exchanging skeletons with an institution.

### ⭐ 3.2a `Claim.kind` is derived, not stored

Three kinds of Claim — but all three are readable off the graph rather than intrinsic to the node:

| kind | Structurally |
|---|---|
| `observation` | supported by evidence **outside your reasoning** — an `Artifact` or a `Source` |
| `conclusion` | supported by **other Claims** |
| `hypothesis` | **no live support at all** |

So `kind` is computed in the same pass as `support` and `strength`, never asserted by the extractor.

**Three consequences:**

1. **The drift surface vanishes** — the model can't mislabel something it doesn't assert.
2. ⭐ **Transitions are automatic.** A hypothesis stops being a hypothesis the moment you measure it. No state machine, no migration.
3. **The rule that mattered already holds:** a hypothesis has no live support → can never reach `established` → can never enter the knowledge state. *Guessing something cannot make you know it*, and deriving `kind` just makes that legible rather than adding a rule.

**The extractor's guess is kept in `provenance.kind_hint`** — recorded and useful (prose signals intent: *"I think X"* vs *"I measured X"*), but **not authoritative**.

**`Artifact.kind` and `Source.kind` stay intrinsic.** A firmware build versus a measurement is not derivable from the graph; an observation versus a conclusion is.

### ⭐ Concept scope — decided by provenance, not by policy

The compounding story needs *"I²C" learned in project 1 to be the same node in project 3*. Making **every** Concept global buys that — and makes one bad merge damage every project at once, silently. Making them all project-scoped is safe and kills the compounding.

**Neither. Scope follows where the concept came from:**

| Origin | Scope | Merge risk |
|---|---|---|
| ⭐ **Curated** — from the concept skeleton (Backend/04), or carrying a CASE `external_id` | **global by construction** | **zero** — a domain expert authored it; the resolver never created it |
| **Extracted** — invented by the LLM from this student's material | **project-scoped on creation** | contained to one project |
| **Promoted** — an extracted concept that appears in a **2nd project** *and* resolves **≥0.95** against an existing global | becomes global | high-confidence only, and reversible |

**Why this is the right cut:** the concepts a student accumulates across a degree — I²C, PID, ADC, impedance spectroscopy — are almost all *curated skeleton concepts*. They are global from day one with no resolver involved, so **compounding works immediately for the common case at zero risk.** The risky ones — LLM-invented concepts from one datasheet — stay local until they prove they generalise.

**And it costs no confirmation step**, so it doesn't reintroduce the organisational tax that made a "promote with user confirmation" design unattractive.

> ### ✅ RESOLVED — Q4 · *Should `Concept` be globally scoped?*
>
> **Decision (2026-08-10): neither pole — scope by provenance, plus a soft-merge band.** Curated skeleton concepts are global by construction (zero resolver risk); extracted concepts are project-scoped until promoted on a 2nd appearance at ≥0.95. The 0.7–0.95 band creates a `same_as` edge rather than merging. Full reasoning: `Backend/09` Q4.
>
> <details><summary>original doubt</summary>
>
> Global concepts are what make compounding across a degree possible — *I²C* learned in project 1 **is** the node in project 3. That's the moat story.
>
> **But a bad merge damages every project at once, and entity resolution fails silently.** I'm about 60/40 on this. The safer alternative: project-scoped, promoted to global only after appearing in two projects **and** you confirm.
>
> </details>


### Claim strength — the corroboration gate

```python
Claim(Node):
  corroboration  int    # ⭐ distinct supporting RESULTS, not re-assertions
  strength       tentative | established | contested
```

```
tentative     corroboration < 2                 ← one result cannot mint a belief
established   corroboration ≥ 2, no live contradiction
contested     live support AND live contradiction
```

> ⭐ **`established` — not merely `supported` — is what admits a Concept to the knowledge state** (§8). One lucky measurement must not mark something learned, or the frontier will confidently route students past gaps they only appeared to close.

Research/01 §12.4 is blunt about this: without the gate, `outcome` degenerates into a popularity counter.

## 3.3 Edge schema

```python
Edge:
  id            UUID
  src, dst      UUID
  relation      Relation                        # closed enum below
  confidence    EXTRACTED | INFERRED | AMBIGUOUS
  score         float          # discrete rubric ONLY
  weight        int = 1        # ⭐ NEW — distinct independent assertions
  weight_sources [int]         # ⭐ event seqs that contributed
  justification [UUID]         # ⭐ ATMS: what this edge rests on
  provenance    {actor, method, source_span, citation_state}
  created_seq   int
  valid_from, valid_to, rank, superseded_by
```

```python
Relation = Literal[
  "contains", "part_of",                                    # structural
  "supports", "contradicts", "refutes", "confirms", "extends",   # epistemic (CiTO)
  "evidence_for", "measured_by", "cites", "uses_method_in",      # evidential
  "requires", "relates_to", "same_as",                           # conceptual
  "answers", "raises", "supersedes", "derived_from",             # process
]
```

**`weight` semantics** ⭐ — re-asserting an existing `(src, relation, dst)` **increments `weight`** rather than creating a duplicate edge. Distinct-source counting: the same paper cited twice is weight 1; two papers agreeing is weight 2.

It earns its place four ways: it feeds centrality in DOI; it *is* the corroboration counter; it makes the retraction cascade smarter (losing one of five supports is survivable, losing the only one is not); and deduplication becomes free.

*I criticised Obsidian for computing edge weights and discarding them (Research/02 §6), then omitted the field. Revision 2 fixes that.*

**`citation_state`** — every grounded edge carries one of `present_relevant | present_weak | missing | wrong_source | anchor_unavailable`, with a tier ceiling enforced in the gate (Backend/03 §4, Backend/05 §3.1). It makes "how well-grounded is this?" a typed field rather than a vibe — and §8.2 depends on it.

**Hyperedges are first-class:**

```python
Hyperedge:
  id, relation: "jointly_support" | "jointly_contradict" | "participate_in"
  members: [UUID]      # 3+
  target:  UUID | None
  + confidence / score / weight / justification / temporal fields
```

*"These five measurements jointly support this conclusion"* is not five edges. Unretrofittable, so it's in from day one.

**`justification` is the ATMS field and it's the one people will want to cut.** Don't. Without it, retracting a bad measurement leaves every conclusion built on it standing and confident — not a degraded graph, a lying one.

## 3.4 The Artifact — where the moat lives

```python
Artifact(Node):
  spec        {what was built/run, params, hardware, commit}
  predicted   {quantity, value, unit, range}     # ⭐ BEFORE
  measured    {quantity, value, unit, raw_ref}   # ⭐ AFTER
  agreement   matched | diverged | inconclusive | not_run
  cost        {money, hours}
  attempt_of  UUID | None     # links retries into a chain
```

**`predicted` / `measured` / `agreement` is the highest-value schema decision in the design** (Queries/07). Free text is worthless in 18 months. This shape gives calibration, the eval benchmark, the training signal if we ever get there, and the student-facing moment: *"you predicted 40–60 kΩ and measured 47.2 — your model of this is good."*

## 3.5 Phantom nodes

Not a type — a **state**. A `Concept` referenced by an edge but never validated is a phantom. Gaps are therefore **generated by reference, not asserted by a model** (Research/02 §7.1), which is what makes them trustworthy.

```
phantom(c)   ⟺  c has inbound edges  ∧  no established Claim/Artifact validates it
frontier(c)  ⟺  phantom(c)  ∧  all `requires` prerequisites satisfied   ← KST outer fringe
```

---

# 4. The ledger

```python
Event:
  seq          int          # monotonic. THE ordering.
  ts           ts           # system time
  actor        user | agent:<role> | system | importer:<kind>
  type         EventType
  structural   dict         # PLAINTEXT — ids, types, relations, confidence
  content      bytes | None # ENCRYPTED — all user text
  caused_by    seq | None
  prev_hash, hash          # tamper-evident chain
```

```python
EventType = Literal[
  "observed", "proposed", "accepted", "rejected",
  "validated",    # ⭐ outcome recorded
  "retracted", "merged", "split", "annotated", "accessed",
  "dead_end",     # ⭐ NEW — this approach failed
  "correction",   # ⭐ NEW — user fixed something; a learning signal
  "shredded",
]
```

**The split payload is what makes erasure possible** (Backend/02 §0): crypto-shredding destroys the key, so content becomes noise while structure survives — the graph still projects, and aggregate calibration data outlives an erasure request.

**Retraction never deletes.** It appends and the projector tombstones the target, then **walks `justification` to cascade** — ATMS as a projector behaviour, not a database delete cascade.

---

# 5. Ingestion — four altitudes of selection

Our expensive step is far costlier than Graphify's, so selection is layered (Research/01 §1.1):

```
① ROUTE      by type → AST | chunker | vision | whisper | structured
② SKIP       SHA256 content hash — unchanged input never re-extracts
③ EXTRACT    ontology in the prompt. Type-check the output. Quarantine failures.
④ RESOLVE    MinHash/LSH block → probabilistic verify → canonical UUID + alias
             ⭐ ≥0.95 hard merge · 0.7–0.95 `same_as` edge (both survive)
               · <0.7 distinct                                    (see below)
⑤ PROPOSE    nothing committed. Confidence and citation_state decide the route.
```

**Extraction is ontology-constrained, always.** The prompt carries the closed enums; the output is validated **in code**. Unmatched values go to `quarantined: true` — visible in review, inert in retrieval. This is the mitigation for schema drift, and it's why Atlas ended up conceding *"labels vary by generation model"*: they didn't choose a loose ontology, they just didn't enforce one.

**Prose never becomes a node label.** A sentence becomes a `Note` or an attribute, never a `Concept`. This single check is the difference between a Mind Graph and a transcript with edges.

### ⭐ The soft-merge band

Entity resolution is the *silent* failure mode — a wrong merge produces a graph that looks fine and is wrong. So the middle confidence band never hard-merges:

| Match confidence | Action |
|---|---|
| **≥ 0.95** | hard merge — one node, one id |
| ⭐ **0.7 – 0.95** | **`same_as` edge. Both nodes survive.** Retrieval unions them; the graph keeps them distinct |
| **< 0.7** | distinct, no edge |

**Identical behaviour for the student; an order of magnitude cheaper to undo.** A wrong `same_as` is an *edge deletion* the retraction cascade already handles. A wrong hard merge needs a `split` event and reconstructing which properties belonged to which node.

`same_as` is already in the relation enum (§3.3) — this costs nothing new.

**The approval gate:**

| Route | When |
|---|---|
| auto-accept | `EXTRACTED` (requires `citation_state = present_relevant`) |
| auto-accept, flagged, one-click reversible | **all `INFERRED`** — 0.95 down to 0.55 |
| ⭐ **always asked of the student** | **`AMBIGUOUS`** — never auto-accepted, never dropped |

> ⭐ **The queue is not an integrity gate. It's a thinking prompt.**
> `AMBIGUOUS` means the system genuinely cannot tell — which is exactly the moment a *student* should be deciding rather than a model guessing. Unresolved tension is the syllabus. These items are the product, not a tax.

**What protects the auto-accepted `INFERRED` edges** — because at ~1.5–1.9% fabrication (Research/05 §1.1) a 5,000-edge graph carries ~75–95 invented relationships:

1. they render **visibly desaturated** (VSUP) — low confidence *looks* low-confidence
2. they **rank low**, because DOI weights confidence
3. ⭐ **they cannot promote anything.** `established` requires ≥2 corroborating *validated results*, never edges — so a fabricated edge can never make a concept count as known
4. the **nightly contradiction sweep** is now the primary catch: a fabricated edge usually collides with something real eventually, and the Disagreement Engine surfaces it then

**Review is never blocking.** A student can always keep working.

### 5.1 ⭐ The structuring nudge — keeping `Note` from swallowing the graph

`Note` is the escape hatch that makes the product usable (§3.1). It is also the failure mode: **if most of what a student writes stays a `Note`, the ontology is decoration and we have built a notes app with a graph attached.** Everything distinctive — calibration, the frontier, the Disagreement Engine — needs *structured* nodes. A `Note` cannot hold `predicted`/`measured`, cannot be corroborated, cannot be contradicted.

**The guard is a nudge, never a requirement:**

```
trigger   unstructured Notes > 40% of nodes created in the last 14 days
          OR  > 15 unstructured Notes outstanding
          ↓
offer     "You've written 18 notes I haven't structured. Want me to take a pass?"
          ↓
batch     one Review-style pass over all of them at once — proposed structure
          per note, A/R/E per item, bulk-accept the confident ones
          ↓
respect   a note that resists structuring twice is left alone permanently.
          Never nag. Some prose is just prose.
```

**Why an offer rather than a rule:** requiring structure is precisely the thing *Formality Considered Harmful* says kills adoption. The nudge creates a pull toward structure without ever putting a form in front of someone mid-project.

**Note also that Q1's resolution already helps here** — since all `INFERRED` now auto-accepts, structure proposed over a note is applied without the student doing anything. The nudge is the backstop for what extraction couldn't confidently type on its own.

**Health metric:** `Note` : structured-node ratio. Below ~30% is healthy; above ~60% means extraction isn't doing its job, and **the fix is more aggressive proposal, not more required structure.**

> ### ✅ RESOLVED — Q1 · *Will the student actually do the review?*
>
> **Decision (2026-08-10):** auto-accept everything except `AMBIGUOUS`; the contradiction sweep is the safety net. `AMBIGUOUS` is **always** asked of the student — not for integrity, but because *making the student think is the point of the product*. Shrinking the queue to only the pedagogically valuable items solves the throughput problem and the purpose problem at once. Full reasoning: `Backend/09` Q1.
>
> <details><summary>original doubt</summary>
>
> **The doubt I'm least comfortable with, and it has no fallback.** Professional reviewers handle 2,000–12,000 items/day. A student at 1am might do **zero** — and then auto-accept is the only gate and the fabrication rate flows straight in.
>
> Alternatives: make review *blocking* (can't proceed until the queue drains), or invert it — auto-accept everything and let the contradiction sweep catch fabrications when they conflict with something real.
>
> </details>


---

# 6. Retrieval

The most-corroborated finding in the whole research set — four independent sources, no dissent:

> **Embeddings for the entry point. Graph traversal for the expansion. Never embeddings for the whole job.**

```
QUERY ──▶ ① SEED      hybrid: embedding kNN + BM25/trigram over label+aliases → 10 seeds
          ② EXPAND    Personalized PageRank from seeds, α ≈ 0.15
          ③ RANK      DOI(x) = API(x) − D(x, focus·lens)
          ④ CAP       top-K.  UI: K ≈ 50 (25 at cold start).  Agent: by token budget.
          ⑤ SUMMARISE only if needed, only over what survived   ← LazyGraphRAG
```

**The ranking function — the actual product:**

```
API(x)  =  w₁·centrality(x)      # PageRank, weighted by Edge.weight
         + w₂·salience(x)        # access recency/count, 30-day half-life
         + w₃·outcome(x)         # did things built on this work?
         + w₄·confidence(x)      # EXTRACTED > INFERRED > AMBIGUOUS
         + w₅·learnability(x)    # is it on the outer fringe?
         − w₆·staleness(x)       # validity expired / dependency changed

D(x, focus·lens) = graph distance, edge weights re-scaled by
                   cosine(edge_context, lens_embedding)     ← the "angle prompt"
```

Weights **ramp with graph age** (Backend/07 §5.1) — on day one salience and outcome are empty, so weighting them weights noise.

**Why PPR, not a vector index over the whole graph:** provenance. Every result is reachable by a printable path. And `w₃`/`w₅` encode facts about *this student* that no embedding can carry.

---

# 7. Analyzer — deferred, incremental, off the request path

CPU-bound and single-core-ish. **Never runs synchronously.**

| Job | Cadence |
|---|---|
| Leiden clustering + community fingerprints + remap-to-previous | on change budget |
| PageRank / eigenvector centrality (weight-aware) | same |
| ⭐ **betweenness — APPROXIMATE, `k=200` pivots** *(measured 2026-08-10, Q11)* | same |
| Salience decay | nightly |
| Embedding backfill | on ingest, async |
| ⭐ **Crossover scoring** — see below | nightly |
| ⭐ **Co-citation**, proximity-weighted | nightly |
| ⭐ **Unlinked mentions** | on write (string scan, no model) |
| Link prediction — Adamic–Adar for phantom edges | nightly |
| Contradiction sweep — `contradicts` cycles, unresolved AMBIGUOUS | nightly |
| Staleness sweep — dependency changed after a claim was made | nightly |

**Community identity must be stable across runs.** Fingerprint members, remap to previous, never let a re-cluster renumber the student's mental map. A region that silently becomes a different region is worse than no regions. **Leiden, never Louvain** — Louvain can emit internally disconnected communities, and a labelled region around one is a lie rendered as a shape.

## 7.1 ⭐ The crossover scorer

Research/01 §13.11 called this *"the signal you already claim as differentiation."* Graphify's axes were file-type and directory; ours are **epistemic and disciplinary**:

```python
def crossover_score(state, u, v, edge) -> tuple[int, list[str]]:
    score, why = 0, []
    score += {"AMBIGUOUS": 3, "INFERRED": 2, "EXTRACTED": 1}[edge.confidence]
    if edge.confidence != "EXTRACTED":
        why.append("not explicitly stated in any source")
    if discipline(u) != discipline(v):
        score += 3; why.append(f"crosses {discipline(u)} ↔ {discipline(v)}")
    if project_of(u) != project_of(v):
        score += 2; why.append("connects two of your projects")
    if abs(age_days(u) - age_days(v)) > 30:
        score += 1; why.append("links work weeks apart")
    if {klass(u), klass(v)} == {"Source", "Artifact"}:
        score += 3; why.append("connects a published claim to your own measurement")
    if min(deg(u), deg(v)) <= 2 and max(deg(u), deg(v)) >= 5:
        score += 1; why.append("peripheral node unexpectedly reaches a hub")
    # suppression: label-matched INFERRED edges are resolver pollution, not insight
    if edge.confidence == "INFERRED" and edge.provenance.get("method") == "label_match":
        score = min(score, 2)
    return score, why
```

Then **deduplicate by community pair** — without it, one high-betweenness hub dominates every result.

**Every surfaced crossover carries its `why`.** Research/01 §12.9: *"never show a connection without the reason it is surprising — that is what turns a graph into a mentor."*

## 7.2 Co-citation and unlinked mentions

**Co-citation**, proximity-weighted, finds concepts the student *thinks about together* — complementary to Adamic–Adar's structural similarity:

```
cocitation(a,b) = Σ over containers holding both:  3.0 same sentence
                                                   2.0 same paragraph/Note
                                                   1.0 same session
```

**Unlinked mentions:** a `Note` or `Claim` whose text contains a Concept's label or alias with no edge to it → propose at `INFERRED 0.75`. One string scan against the alias table, no model call — the cheapest proposal source in the system.

---

# 8. Frontier engine

Two classes of next action: **gaps** (what you don't know) and **tensions** (what disagrees).

```
knowledge_state K = { c : Concept | established(c) }        ⭐ established, not supported
outer_fringe      = { c ∉ K | all `requires` prerequisites of c ∈ K }   ← KST
phantom_edges     = Adamic–Adar ∪ co-citation, top-N over non-adjacent pairs
open_questions    = Question nodes with no answering Claim
stale             = Claims whose justification changed after assertion
tensions          = unresolved `contradicts` pairs                      ← §8.2
```

Ranked by **information gain per unit of effort**:

```
priority(g) = expected_uncertainty_reduction(g) / estimated_cost(g)

  uncertainty ≈ #AMBIGUOUS edges resolved + #dependent claims unblocked
              + #phantom nodes validated
  cost        ≈ Artifact.cost from similar past attempts   ← the flywheel, used
```

**v1 is not KST-proper.** No borrowable prerequisite datasets exist and knowledge tracing fails for a single sparse learner (Research/04 §1.1). v1 = the hand-built `requires` skeleton (Backend/04) + adjacency heuristics. The formal machinery arrives when there's data to feed it; it must not gate the schema.

## 8.1 Dead-end memory ⭐

Research/01 §12.5: *"the highest-value memory type Vera can carry between sessions, and nobody in the student-tools space has it."*

```python
DeadEnd:
  id, question, nodes[], reason, seq
  resurrect_if: [UUID]     # ⭐ nodes whose change makes this worth retrying
```

1. **The frontier suppresses dead ends.** Without this it will re-suggest the thing that wasted a student's Tuesday — the fastest way to destroy trust in a recommender.
2. ⭐ **Resurrection.** If a node in `resurrect_if` gains support later, the dead end returns flagged *"you tried this before it was possible — the blocker has changed."* Nearly free: the justification index already tracks those dependencies.

## 8.2 ⭐ The Disagreement Engine

*Revised 2026-08-10 — see `Backend/09` Q8. The original design fired only on the three-way source-vs-bench case, which a hand-walk of the biosensor project showed would fire ~2 times in six weeks out of ~8–12 real disagreements. **The trigger is now wide; the tier determines the framing.***

The graph holds three kinds of claim, distinguishable by provenance: what the **literature** says (`Source`-backed), what the **student believes** (`Claim`), and what their **bench measured** (`Artifact`-backed). **When any of these disagree, the system can say something useful — and no competitor can, because none holds all three.**

### 8.2.1 Six kinds — what it *is*, and how it's framed

Fire on **any** live `contradicts` edge. The kind determines the framing and the suggested action, never whether it fires.

| Kind | Trigger | What it says |
|---|---|---|
| **CHECK** | 1 measurement vs a spec or source claim | *"most likely your setup — check contact pressure"* |
| **CONFLICT** | 2 of your own measurements disagree | *"these two runs disagree. Here's what changed between them"* |
| **STALE** | a new measurement contradicts your own earlier claim | *"you concluded the opposite in week 2"* |
| **BOUNDARY** | ≥2 measurements vs a well-grounded source, conditions differ | *"the paper may not apply here"* — note the boundary |
| ⭐ **FINDING** | ≥2 measurements vs a well-grounded source, conditions match | *"this may be real"* — escalate |
| **LITERATURE** | source vs source | *"these two disagree — which applies to you?"* |

⭐ **CHECK fires in week 1**, needing only one measurement and one ingested datasheet. The corroboration gate governs what counts as *known*; it must not govern what's worth *flagging*.

**Every input already exists** — corroboration counts (§3.2), confidence tiers, `citation_state` (§3.3), provenance-by-author (Backend/05 §2.1). **No schema change.** This is a ranking and framing layer over `contradicts` edges.

### 8.2.2 ⭐ Priority — computed, and separate from kind

Kind says *what it is*. Priority says *where and when it surfaces*, and it is recomputed continuously rather than fixed at creation.

```
priority = blocking            × 100   is it on the path from the current focus
                                       to the active Question?
         + claim_load                  Σ Edge.weight of what depends on it
         + resolvability               can it be settled now, with what's on hand?
                                       (estimated from Artifact.cost of similar attempts)
         + min(conf_a, conf_b)         two STRONG claims disagreeing is more serious
                                       than two weak ones
         + recency                     new disagreements are more actionable
         − dismissals                  seen and moved on
```

| | Level | Surface | Means |
|---|---|---|---|
| **P0** | Blocking | ⚠️ inline, immediately | active work depends on something now contested |
| **P1** | Next action | top of the Bench, in `NOW` | not blocking, but the highest-value thing to do |
| **P2** | Worth knowing | Bench `OPEN` — **counted, not listed** | real, not urgent |
| **P3** | Ambient | inline where the student already is, **never pushed** | only relevant when nearby |
| **P4** | Suppressed | nowhere | resolved, dismissed, or superseded — until new evidence lands |

**Typical priority by kind, and when it escalates:**

| Kind | Usually | Jumps to P0 when |
|---|---|---|
| CHECK | P3 | actively working on that component |
| CONFLICT | P1 | a conclusion depends on the disagreeing runs |
| STALE | P1 | about to build on the stale claim |
| BOUNDARY | P2 | it's on the critical path |
| ⭐ FINDING | **P1 floor — always** | rare enough that missing it is worse than interrupting |
| LITERATURE | P3 | choosing between those two approaches right now |

### 8.2.3 Two guards against the alert wall

**At most one P0 at a time.** If two things block, surface the cheaper one to resolve. More than one is exactly the habituation failure the frontend research documents — people learn to ignore the loudest signal in the product.

⭐ **P1 tensions compete in the same ranking as gaps.** They do not get a parallel queue. The Bench's `NOW` section holds three items, and a tension must *earn* a slot against *"measure the impedance"* and *"read §7 of the datasheet."*

That is the important structural choice: **there is one notion of "what matters now" in this product, not two.** The tension priority score is simply how a tension computes its numerator in the frontier's existing `uncertainty reduction ÷ effort` function (§8). Same maths, same competition, one ranked list.

### 8.2.4 Why it's defensible

**This is the only feature requiring every distinctive piece of the architecture at once** — `Artifact`, provenance-by-author, the confidence model, contradiction edges, corroboration counting, the bitemporal ledger. A competitor can't bolt it on.

> **Nexus notices when things don't add up — and tells you whether that means you're wrong, the source doesn't apply here, or you've found something.**

*(Framing note: the earlier headline led with discovery. FINDING fires perhaps 0–1 times per project, so promising it would read as a lie. The wide framing is honest across all six kinds, and discovery becomes the upside rather than the promise.)*

---

# 9. The Graph API — the only door

Everything — UI, agents, CLI — goes through one interface. Agents get **read + propose**, never direct write.

```
READ
  query(text, lens?, k)            → ranked nodes + paths + citations
  neighbors(id, hops, filter)      → local subgraph
  path(a, b)                       → shortest justified path
  explain(id)                      → supports / contradicts / provenance / citation_state
  frontier(project, k)             → ranked next actions (gaps)
  tensions(project, k)             → ⭐ ranked disagreements (§8.2)
  contradictions(project)          → raw unresolved pairs
  timeline(project, t)             → the graph as it stood at time t
  stats(project)                   → counts, confidence mix, cost to date

VIEWS  ⭐
  save_view(view) / get_view(id) / list_views / share_view(id)
  export(project, format)          → graph.json | canvas | graphml

WRITE (proposals only)
  propose(events[], basis, role)   → proposal_id
  accept(id) / reject(id, reason)

HUMAN-ONLY
  validate(artifact_id, measured)  → ⭐ the outcome path — never an agent
  retract(node_id, reason)         → cascades via justification
  mark_dead_end(question, nodes, reason, resurrect_if)
```

**`View` is a first-class object** ⭐ — structure is truth; views (filter, lens, focus, pinned positions) are separate, savable, shareable artifacts. Three payoffs: saved focus states, the "professor publishes an ideal view" idea becoming implementable, and **Halasz's issue #3 (virtual structures) closed** — the thing that killed prior generations of hypertext systems.

**`timeline()` is the one no competitor can implement**, and it costs nothing: replay to `seq(t)`.

**Agents are consumers, not privileged.** Whatever the reasoning architecture turns out to be, it sees the same API the UI does — which keeps the graph independent of an agent design that is still open.

---

# 10. Storage

| Layer | Choice | Why |
|---|---|---|
| **Ledger** | **SQLite, one file per user** | append-only, boring, trivially backed up; per-user isolation is a filesystem property |
| **Graph** | **in-process** (NetworkX server-side / graphology client-side), snapshot per user | 10³–10⁴ nodes fits in memory; **it's a derived view — swapping is cheap** |
| **Vectors** | **sqlite-vec** or LanceDB, same per-user file | one artifact per user, no separate service |
| **Sidecars** | JSON next to the snapshot | disposable by definition |

**Deliberately unfashionable: no graph database in v1.** For thousands of small isolated graphs, monolithic graph DBs are economically unviable. KuzuDB was the right shape and **Apple archived it in Oct 2025**. Because the graph is a projection, the decision is reversible for the cost of a re-projection — so defer it until real query patterns exist.

**Migration trigger:** per-user graphs above ~10⁵ nodes, or cross-user queries becoming a product requirement. Not before.

> ### ✅ RESOLVED — Q11 · *Does SQLite + in-process hold?* — **yes, measured** *(2026-08-10)*
>
> Load-tested with `tools/bench_graph.py` rather than deferred to Phase 4.
>
> | | 10k nodes | 25k nodes |
> |---|---|---|
> | **Personalized PageRank** *(per-turn)* | **27 ms** | **76 ms** |
> | **Full replay, 60k events** | **122 ms** | 123 ms |
> | Louvain *(Leiden proxy)* | 592 ms | 1.75 s |
> | approx. betweenness *(k=200)* | 3.0 s | 9.3 s |
> | ⚠️ exact betweenness | ~118 s | ~738 s |
> | peak RSS | 144 MB | 240 MB |
>
> ⭐ **27 ms against a 2–8 s model call — storage is ~100× off the critical path.** And the 122 ms replay finally *proves* the "reversible for the cost of a re-projection" claim this section has always asserted.
>
> **Two changes fell out.** Betweenness is now specified as **approximate** (§7) — it's a ranking input to `API(x)`, not a truth claim, so `k=200` is correct on the merits. And ⭐ **the real constraint turned out to be memory under concurrency, not CPU** — 144–240 MB per live graph. **The 122 ms replay makes LRU eviction free**, which is what makes the per-user in-process model multi-tenant (`Backend/07 §4.6`).
>
> **Full record: `Backend/09` Q11.**


---

# 11. Cost instrumentation — build it now

Nobody in the field has published real cost or curation data (Research/06 §1.1). Every operation writes one row:

```
op_id, user, project, op_type, model, tokens_in, tokens_out,
wall_ms, cpu_ms, usd_est, event_seq
```

Cheap now, impossible to reconstruct later, and it makes *"what does a personal knowledge graph cost per student per semester?"* a question only we can answer.

---

# 12. Tradeoffs made

| Chose | Over | Because |
|---|---|---|
| Event-sourced ledger + projection | mutable graph | repairability; swappable store; bitemporal free. **Costs:** double write, correctness-critical projector |
| 6 node types | Atlas's 8 | `Artifact` and `Note` earn their place; Verdict/Finding collapse to reduce drift surface |
| Closed enums in code | prompt-described ontology | drift is otherwise inevitable |
| Hybrid retrieval | vector-only / graph-only | four independent sources, no dissent |
| PPR | iterative LLM traversal | 10–30× cheaper, deterministic, printable path |
| Deferred clustering | live clustering | CPU-bound single-core |
| SQLite + in-process | Neo4j / Kuzu / Memgraph | viable per-user; reversible |
| Cap view at ~50 | render everything | measured comprehension limit |
| Approval gate | trust the model | ~2% hallucinated edges, structurally encoded |
| Weight increment | duplicate edges | corroboration becomes countable; dedup free |
| `established` for knowledge state | `supported` | one result cannot mint a belief |

---

# 13. What I would not do

- **No RDF / triple store / SPARQL.** Borrow CiTO's *vocabulary*, not its stack.
- **No graph database in v1.**
- **No vector-only memory.** Loses provenance, multi-hop, supersession.
- **No LLM as primary entity resolver.** Too slow, too expensive, non-deterministic on a decision that must be stable.
- **No eager community summarisation.** LazyGraphRAG: 0.1% of indexing cost.
- **No user-facing ontology.** The student never picks a node type.
- **No global graph as default view.** ~780 nodes is 8–15× past comprehension.
- **No GPU rendering in v1.** Wrong bottleneck by ~250×.
- **No CRDTs yet** — but the event log is an ordered op-log, so retrofitting is tractable.
- **No knowledge-tracing model in v1.** Cold start makes it worse than a hand-built skeleton.
- **No cross-user graph** until consent and IP are written down and student-favourable.

---

# 14. Open questions

Maintained in `Queries/00_Open_Questions` — §5 there lists the eight design calls I'm least confident in, including whether the Disagreement Engine fires often enough to be a product rather than a demo.

---

# 15. Phase 0 — the first three things

**1. The ledger and the projector.** `Event` → append → project → `Graph`. No LLM, no UI, no retrieval. Replay from zero must reproduce the graph byte-identically, and a `retract` must cascade correctly through `justification`. **If this isn't right, nothing built on it can be.** ~1 week, the highest-leverage week in the project.

**2. The Artifact loop, end to end, ugly.** Declare a prediction, run the thing, record the measurement, store `agreement`. Command line is fine. No graph view.
It's the moat, it's the one thing no competitor has, and it produces data we can't reconstruct later.

**3. Ingest + propose + review, on one input type.** PDFs. Extract under the closed ontology, type-check, entity-resolve, land in a review queue. **How many proposals a human actually accepts is the most important early metric in the system** — our real hallucination rate, our real review burden, and the calibration for auto-accept, from one screen.

Explicitly **not** in Phase 0: the visualisation, communities, the frontier engine, agents, KST, multi-tenancy.

---

# 💡 Visionary Vector — the graph that can tell you it is wrong

Stack three pieces of this design and something appears that isn't in any reference system:

```
Artifact.predicted   +   Artifact.measured   +   ledger.timeline()
```

The system can compute, at any point in time, **how well-calibrated this student is** — not how much they know, but *how accurately they predict what happens when they build something.*

Atlas measures whether you can find a citation. Knowledge tracing measures whether you can answer questions. **Calibration measures whether your model of the world survives contact with hardware**, which is close to the definition of engineering competence. Computable from day one: no ML, no scale, no cohort.

And after revision 2 the graph carries the rest of an epistemic state — how strongly each belief is held (`weight`, `corroboration`), whether it's disputed (`contested`), how well-grounded its evidence is (`citation_state`), what you've already failed at (dead ends), and where your bench disagrees with the world (§8.2).

That's not a memory system. **It's a model of the student's understanding that can detect its own faults** — and those three capabilities, *updated-state reasoning, conflict detection, and abstention*, are exactly what Research/01 §10.1 found every memory benchmark in the field fails to test. They arrived here as a by-product of fixing integrity bugs rather than as features, which suggests the benchmark gap and the product gap are the same gap.

The sharpest expression of it: **the best next action is where the student is most confident and most likely to be wrong.** A system that finds the place your intuition is about to fail and sends you there first is a different product from one that organises your notes — and every piece it needs is now in this design.

---

*Revision 2. Disagree freely — that's what it's for.*

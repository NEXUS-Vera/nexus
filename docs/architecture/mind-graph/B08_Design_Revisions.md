# Backend Design — Revisions

**Backend / 08.** A deliberate audit of Backend/01–07 against Research/01–06, hunting for things I recommended and then failed to build.
**Method:** re-read the STEAL/ADAPT sections of each teardown and checked each item against the actual design. Not from memory — from the documents.
**Result:** eleven verified misses. All fixes below are **additive**.
**Date:** 2026-08-07

> ## 📌 Precedence — this document is normative
>
> **Where this document and Backend/01–07 disagree, this document wins.** It is an errata/amendment layer, not a parallel opinion. §8 lists exactly which sections of which documents each revision overrides, so an implementer can work from 01–07 plus this.
>
> ✅ **All revisions are now folded in.** Backend/01 and 02 were reissued as **revision 2** on 2026-08-07; Backend/03 and 05 were amended in place. **This document is now a historical record of *why* the changes were made — you no longer need to read it alongside the others to build correctly.**

> ## ⚠️ Read this first
>
> **Nothing good is being removed.** Every revision here is an *addition* to Backend/01–07 or a new field on an existing schema. No decision is reversed, no subsystem is replaced. That's not a coincidence — it's the outcome of the audit. The design's *skeleton* held up; what it was missing was **epistemic richness**: the graph knew what you believed but not how strongly, how contested, or how many times you'd already failed at it.
>
> **The single biggest finding:** I criticised Obsidian for computing edge weights and throwing them away (Research/02 §6), then designed an `Edge` schema with no weight field. Same mistake, one document later.

---

# 1. The audit

| # | Research said | Design status | Severity |
|---|---|---|---|
| 1 | **Link multiplicity as edge weight** — *"Obsidian's mistake is computing it and throwing it away"* (R02 §7.5) | ❌ **absent** — `Edge` has no weight | 🔴 schema |
| 2 | **Contested state** — nodes with both positive and negative signals (R01 §7, R02 §13) | ❌ absent — `Support` has only supported/unsupported/unknown | 🔴 schema |
| 3 | **Corroboration gate** — *"Nexus's `outcome` field needs exactly this machinery or it degenerates into a popularity counter"* (R01 §12.4) | ❌ absent | 🔴 schema |
| 4 | **Surprise/crossover scoring with a generated `why`** — *"that is what turns a graph into a mentor"* (R01 §12.9) | ❌ **absent entirely** | 🔴 subsystem |
| 5 | **Dead-end memory** — *"the highest-value memory type Vera can carry between sessions, and nobody in the student-tools space has it"* (R01 §12.5) | ❌ absent | 🔴 subsystem |
| 6 | **Co-citation weighted by proximity** (R02 §7.6) | ⚠️ partial — only Adamic–Adar | 🟠 subsystem |
| 7 | **Unlinked mentions** — zero-cost deterministic suggester (R02 §7.4) | ❌ absent | 🟠 subsystem |
| 8 | **Views as savable, shareable artifacts** — Bases separation (R02 §7.9); also closes Halasz issue #3, which I flagged as unanswered | ❌ absent | 🟠 object |
| 9 | **Citation-state taxonomy** as the grounding output contract (R03 §8.3) | ❌ absent — I promised this explicitly | 🟠 contract |
| 10 | **Structured export / JSON Canvas** (R02 §7.10, R03 §9) | ❌ absent | 🟡 cheap |
| 11 | **User corrections as a learning signal** (R03 §9) | ❌ absent | 🟡 cheap |

Everything else in the STEAL lists **is** in the design — sidecar separation, discrete rubric, AMBIGUOUS-never-dropped, community stability, god-node filtering, hyperedges, determinism engineering, phantom nodes, span citation, contextual resolution, Adamic–Adar, canonical groups, KST, ATMS, DOI, tombstoning, entity resolution, hybrid retrieval.

---

# 2. Schema revisions *(amends Backend/01 §3, Backend/02 §2)*

## 2.1 `Edge.weight` — citation multiplicity

```python
class Edge(BaseModel):
    ...
    weight: int = 1        # ⭐ NEW — times this relation was independently asserted
    weight_sources: list[str] = Field(default_factory=list)   # distinct event seqs
```

**Semantics:** re-asserting an existing `(src, relation, dst)` **increments `weight`** and appends the event seq, rather than creating a duplicate edge. Distinct-source counting, not raw repetition — the same paper cited twice is weight 1; two papers agreeing is weight 2.

**Why it matters more than it looks:**
- feeds `w₁ centrality` in DOI — a heavily-leaned-on edge should pull rank
- it *is* the corroboration counter (§2.3)
- it makes the retraction cascade smarter: losing one of five supports is survivable, losing the only one is not — `_has_live_support` currently answers a boolean where it should answer a magnitude
- deduplication becomes free: the projector already resolves endpoints, so incrementing is cheaper than storing near-duplicates

## 2.2 `Support.CONTESTED`

```python
class Support(StrEnum):
    SUPPORTED   = "supported"
    UNSUPPORTED = "unsupported"
    CONTESTED   = "contested"     # ⭐ NEW — live support AND live contradiction
    UNKNOWN     = "unknown"
```

Graphify's `reflect` splits nodes into **preferred / tentative / contested**; Research/02 §13 lists *contested* among the canonical colour groups we should ship. My `Support` enum collapsed it into `unknown`, which is wrong: a claim nobody has tested and a claim two measurements disagree about are opposite epistemic states, and the second is far more interesting.

```python
def support_state(state, node_id) -> Support:
    pos = live_support_weight(state, node_id)      # Σ weight over live supporting edges
    neg = live_contradiction_weight(state, node_id)
    if pos and neg:  return Support.CONTESTED       # ⭐ the interesting one
    if pos:          return Support.SUPPORTED
    if neg:          return Support.UNSUPPORTED
    return Support.UNKNOWN
```

**Contested nodes are the raw material for §4.** They're also exactly what a student most needs pushed in their face, and what every notes tool hides.

## 2.3 Corroboration gate on claim strength

Research/01 §12.4, verbatim: *"`min_corroboration = 2`, 30-day half-life. One session cannot mint a belief."*

```python
class Claim(Node):
    ...
    corroboration: int = 0     # ⭐ distinct supporting results (NOT re-assertions)
    strength: Literal["tentative", "established", "contested"] = "tentative"
```

```
tentative     corroboration < 2                 ← one result. Cannot be treated as known.
established   corroboration ≥ 2, no live contra
contested     live support AND live contradiction
```

**Consequence that matters:** `strength == "established"` — not merely `supported` — is what admits a Concept to the **knowledge state** for KST (Backend/01 §8). One lucky measurement should not mark something learned, and without this gate the frontier will confidently route students past gaps they only appeared to close.

Time-decay uses the existing 30-day half-life already specified for salience.

## 2.4 External concept identity

```python
class Node(BaseModel):
    ...
    external_ids: dict[str, str] = Field(default_factory=dict)   # {"CASE": "...", "wikidata": "Q..."}
```

Research/04 Tier 6 identified **CASE** as the standard giving competencies globally unique IDs. Free to add now; expensive to backfill; and it's the hook for ever exchanging skeletons with an institution.

---

# 3. New derived subsystems *(amends Backend/01 §7–8)*

All run in the deferred Analyzer. All deterministic, no model calls, no schema risk.

## 3.1 ⭐ The crossover scorer — the biggest miss

Research/01 §13.11 called this *"the signal you already claim as differentiation"* and handed over a working template. It is entirely absent from Backend/01–07.

Graphify's axes were file-type, directory, community, degree. Ours must be **epistemic and disciplinary**:

```python
def crossover_score(state, u, v, edge) -> tuple[int, list[str]]:
    score, why = 0, []

    # 1. confidence — uncertain links are more noteworthy
    score += {"AMBIGUOUS": 3, "INFERRED": 2, "EXTRACTED": 1}[edge.confidence]
    if edge.confidence != "EXTRACTED":
        why.append("not explicitly stated in any source")

    # 2. ⭐ cross-discipline  (the ECE↔BioE claim, finally computed)
    if discipline(u) != discipline(v):
        score += 3
        why.append(f"crosses {discipline(u)} ↔ {discipline(v)}")

    # 3. cross-project — the compounding story, made visible
    if project_of(u) != project_of(v):
        score += 2
        why.append("connects two of your projects")

    # 4. cross-time — an old finding that now matters
    if abs(age_days(u) - age_days(v)) > 30:
        score += 1
        why.append(f"links work {abs(...)} days apart")

    # 5. ⭐ cross-source-class — the literature vs the bench
    if {klass(u), klass(v)} == {"Source", "Artifact"}:
        score += 3
        why.append("connects a published claim to your own measurement")

    # 6. peripheral → hub
    if min(deg(u), deg(v)) <= 2 and max(deg(u), deg(v)) >= 5:
        score += 1
        why.append(f"peripheral `{low}` unexpectedly reaches hub `{high}`")

    # suppression: cross-discipline INFERRED edges from pure label matching
    # are resolver pollution, not insight (Graphify's cross-language rule)
    if edge.confidence == "INFERRED" and edge.provenance.get("method") == "label_match":
        score = min(score, 2)

    return score, why
```

Then **deduplicate by community pair** — Graphify's fix, and it matters: *"without this, a single high-betweenness god node dominates all results."*

**Every surfaced crossover carries its `why` string.** Research/01 §12.9: *"never show a connection without the reason it is surprising — that is what turns a graph into a mentor."*

## 3.2 Dead-end memory

Research/01 §12.5 called this the highest-value cross-session memory, and noted nobody in the student space has it.

```python
class DeadEnd(BaseModel):
    id: str
    question: str            # what was being attempted
    nodes: list[str]         # what it rested on
    reason: str              # why it failed
    seq: int
    resurrect_if: list[str]  # ⭐ node ids whose change makes this worth retrying
```

Written by a new `dead_end` event (from an explicit "this didn't work" action, or a retraction with `reason="failed"`).

**Two behaviours:**
1. **The frontier suppresses dead ends.** A gap already attempted and abandoned drops out of ranking. Without this, the frontier will cheerfully re-suggest the thing that wasted a student's Tuesday — which is the fastest possible way to destroy trust in a recommender.
2. ⭐ **Resurrection.** If a node in `resurrect_if` gains support later, the dead end returns to the frontier flagged *"you tried this before it was possible — the blocker has changed."* That's a genuinely delightful moment and it's nearly free, because the justification index already tracks exactly these dependencies.

## 3.3 Co-citation, proximity-weighted

Research/02 §7.6. Adamic–Adar alone finds structurally-similar nodes; co-citation finds nodes the student *thinks about together* — a different and complementary signal, and closer to how implicit associations actually form.

```
cocitation(a, b) = Σ over containers c holding both:
                     3.0  same sentence
                     2.0  same paragraph / same Note
                     1.0  same session
```

Nightly, top-N, feeding phantom edges alongside Adamic–Adar. Deterministic, no embeddings.

## 3.4 Unlinked mentions

Research/02 §7.4 — *"a permanently-on, deterministic, zero-cost connection suggester."*

A `Note` or `Claim` whose text contains a Concept's label or alias, with no edge to it → propose the edge at `INFERRED 0.75`. Uses the alias table we already maintain. Costs one string scan on write, no model call, and it's the cheapest proposal source in the system.

---

# 4. ⭐ The Disagreement Engine — what these additions unlock

This is the part worth arguing about, and it's why the audit was worth doing.

## 4.1 The observation

After §2–3, the graph holds three kinds of claim, distinguishable by provenance:

| Claim backed by | Means |
|---|---|
| `Source` | **what the literature says** |
| `Claim` with no artifact | **what the student believes** |
| `Artifact` with `agreement` | **what their bench measured** |

**When those three disagree, that is the highest-value moment in any research project** — and no product in this space surfaces it, because no product holds all three. Atlas holds only the first. Obsidian holds only the second. Graphify holds neither.

## 4.2 The mechanism

A `contradicts` edge between a Source-backed claim and an Artifact-backed claim is **exactly one of three things**, and the system can tell you which:

| Pattern | Diagnosis | What the student should do |
|---|---|---|
| Artifact corroboration = 1, low confidence, source well-grounded | **probably your error** | re-measure; check the method |
| Artifact corroboration ≥ 2, source claim scoped to different conditions | **the paper doesn't apply here** | note the boundary — this is a real finding |
| Artifact corroboration ≥ 2, source well-grounded, conditions match | ⭐ **you may have something** | escalate; this is what a PI wants to hear about |

Every input already exists: corroboration counts (§2.3), confidence tiers, citation states (§5.1), and provenance-by-author (Backend/05 §2.1).

## 4.3 Where it goes

The frontier (Backend/01 §8) currently ranks **gaps**. Add a second class — **tensions** — ranked by:

```
tension_priority = crossover_score          # how surprising the disagreement is
                 × claim_load               # Σ edge weight of what depends on it
                 × resolvability            # is there a cheap measurement that settles it?
```

That last term is the one that makes it a *tutor* rather than an alarm: it surfaces disagreements the student can actually resolve this week with the hardware they have.

## 4.4 Why this is the face of the prototype

It is the only feature that requires **every distinctive thing in the architecture at once** — the `Artifact` node type, provenance-by-author, the confidence model, contradiction edges, corroboration counting, and the bitemporal ledger. A competitor cannot bolt it on; they'd have to rebuild to the same premise.

And the pitch is one sentence a student immediately understands:

> **Nexus tells you when your bench disagrees with the literature — and whether that means you're wrong, the paper doesn't apply, or you've found something.**

Compare the alternatives: *"organise your research"* (everyone), *"chat with your PDFs"* (everyone), *"see your knowledge as a graph"* (unproven, per Research/06 §2). This one is specific, checkable, and only true of us.

---

# 5. Contract and object additions

## 5.1 Citation states — the grounding output contract

Research/03 §8.3 said this *"becomes the Grounder's output contract"*, and I never wrote it. Every grounded claim carries one:

| State | Meaning | Remediation surfaced to the student |
|---|---|---|
| `present_relevant` | passage directly supports the claim | use it |
| `present_weak` | related but doesn't fully support | narrow the claim |
| `missing` | no source evidence | treat as unverified |
| `wrong_source` | retrieval found the wrong material | name the right source |
| `anchor_unavailable` | source known, exact location unresolvable | search manually |

Stored on the edge as `provenance.citation_state`. It's what makes §4.2's *"source well-grounded"* term computable rather than hand-waved.

## 5.2 `View` as a first-class object — closes Halasz #3

Research/02 §7.9 (Bases separation) and Research/04 §2.4, where I flagged **virtual structures** as having no answer anywhere in our thinking. It still had none.

```python
class View(BaseModel):
    id: str
    name: str
    filter: dict          # node/edge predicates
    lens: str | None      # the angle-prompt embedding target
    focus: str | None     # anchor node
    pinned: list[str]     # positions the user fixed
    owner: str
    shared: bool = False
```

Structure is truth; **views are separate, savable, shareable artifacts.** Three payoffs: saved focus states, the "professor publishes an ideal view" idea becoming implementable rather than aspirational, and Halasz's virtual structures closed — the thing that killed prior generations of hypertext systems.

## 5.3 Structured export

`GET /v1/projects/{id}/export?format=graph.json|canvas|graphml`

Research/03 §9 lists *"no structured export"* as an Atlas gap — a map cannot leave Atlas as data. JSON Canvas is nearly free: its `file + subpath` node type already matches our span-citation model.

## 5.4 User corrections as signal

When a student edits a label, rejects a proposal, or corrects a claim, that is training data for the extraction contract, not just an edit. Log `correction` events with before/after and feed the accept-rate telemetry (Backend/06 §2.1). Atlas's gap, one line of plumbing.

---

# 6. What I deliberately did **not** change

Explicitly, since the instruction was to be careful:

| Kept | Why |
|---|---|
| Ledger → Graph → Sidecars | audit found nothing against it; §2–3 all sit cleanly on top |
| Six node types | the misses were **fields and subsystems**, not missing types. Adding types would have increased drift surface for no gain |
| `Claim.kind` as an enum | still no evidence anything branches on it (the test in Queries/00 §5.5) |
| Four-role split | unvalidated, but the audit produced no new evidence either way. Still a bet, still worth testing early |
| SQLite + in-process graph | §2–3 add fields and nightly jobs; nothing here pressures the storage choice |
| Human-only `VALIDATE` / `RETRACT` | §4 *increases* the case for it — the Disagreement Engine is only meaningful if measurements are real |
| ≤50-node view cap | unchanged; §4 gives it better content, not more of it |
| Everything in Backend/02, 03, 05, 06, 07 | untouched except the schema additions in §2 |

---

# 7. Implementation cost

| Revision | Effort | Risk |
|---|---|---|
| §2.1–2.4 schema fields | hours | very low — additive, defaults preserve behaviour |
| §3.1 crossover scorer | ~1 day | low — pure function, deterministic, testable |
| §3.2 dead-end memory | ~1 day | low — one event type + a frontier filter |
| §3.3 co-citation | half day | low |
| §3.4 unlinked mentions | hours | low |
| §4 Disagreement Engine | ~2 days | medium — the ranking needs tuning against real tensions |
| §5.1 citation states | half day | low |
| §5.2 `View` object | ~1 day | low |
| §5.3–5.4 export, corrections | half day | low |

**~1 week total**, and the schema fields must go in before any real data exists. Everything else can land after Phase 0.

---

# 8. Override map — what this document supersedes

| Revision | Overrides | Status of the source doc |
|---|---|---|
| §2.1 `Edge.weight` | **Backend/01 §3.3**, **Backend/02 §2** (`class Edge`) | ✅ folded in (rev 2) |
| §2.2 `Support.CONTESTED` | **Backend/02 §2** (`class Support`) | ✅ folded in (rev 2) |
| §2.3 corroboration gate | **Backend/01 §3.1, §8** (knowledge-state definition) | ✅ folded in (rev 2) |
| §2.4 `external_ids` | **Backend/01 §3.2**, **Backend/02 §2** (`class Node`) | ✅ folded in (rev 2) |
| §3.1 crossover scorer | **Backend/01 §7** (Analyzer job list) — *adds a job* | ✅ folded in (rev 2) |
| §3.2 dead-end memory | **Backend/01 §8** (frontier), **Backend/02 §3** (`EventType`) — *adds `dead_end`* | ✅ folded in (rev 2) |
| §3.3–3.4 co-citation, unlinked mentions | **Backend/01 §7** — *adds jobs* | ✅ folded in (rev 2) |
| §4 Disagreement Engine | **Backend/01 §8** — *adds a second frontier class* | ✅ folded in (rev 2) |
| §5.1 citation states | **Backend/03 §4**, **Backend/05 §3** | ✅ **folded in** |
| §5.2 `View` object | **Backend/01 §9** (API) — *adds endpoints* | ✅ folded in (rev 2) |
| §5.3–5.4 export, corrections | **Backend/01 §9**, **Backend/06 §7** | ✅ folded in (rev 2) |

## Status — resolved 2026-08-07

**Backend/01 and 02 were reissued as revision 2 with every item above folded in.** Backend/03 and 05 were amended in place. There is no longer any gap between the documents and the design.

The build order is simply **Backend/01 → 02 → 03 → 07**. This document is retained as the record of *why* the changes were made, and of what the audit found — not as something you must read to build correctly.

---

# 💡 Visionary Vector — the graph should be able to tell you it is wrong

Every addition here points the same direction, and it's worth naming.

Before this audit the graph could say *"here is what you know."* After it, the graph can say:

- how **strongly** each belief is held (weight, corroboration)
- whether it is **disputed** (contested)
- how well its evidence is **grounded** (citation states)
- what you have **already failed at** (dead ends)
- where your bench **disagrees with the world** (§4)

That is not a memory system. **It's a model of the student's epistemic state that can detect its own faults** — and the interesting move is that this is exactly the property Research/01 §10.1 identified as missing from every memory benchmark in the field: *"the capabilities LOCOMO fails to test — updated state, conflict detection, abstention — are exactly the capabilities Nexus needs most."*

We now have all three, and they arrived as a by-product of fixing integrity bugs rather than as features.

Which suggests something worth taking seriously: **the benchmark gap and the product gap are the same gap.** Nobody built the benchmark because nobody built the system that would score well on it. If Nexus can demonstrate updated-state reasoning, conflict detection, and honest abstention on real student projects, we are not competing on an existing axis — **we are the reference implementation of an axis that doesn't have one yet.**

And the student-facing version of that same capability is the sentence in §4.4, which is the only claim in this space I've seen that is simultaneously specific, checkable, and true of nobody else.

# Mind Graph — The Complete Design, Explained

**Backend / 11 · Revision 3 — 2026-08-10**

**Who this is for:** teammates, mentors, professors and investors. **No prior reading required** — every term is defined on first use, and §17 is a glossary.

**What it covers:** what we're building, how it works, every significant decision, **why we chose it over the alternative**, and where the evidence came from.

**Status:** design complete, all twelve of our open questions closed, **nothing built yet** — §15 explains why that's deliberate.

## Table of Contents
- [1. The problem, in one page](#1-the-problem-in-one-page)
  - [1.1 Why a graph at all](#11-why-a-graph-at-all)
- [2. Where this design came from](#2-where-this-design-came-from)
  - [2.1 Two things the research taught us that we didn't expect](#21-two-things-the-research-taught-us-that-we-didnt-expect)
- [3. ⭐ The one idea everything else follows from](#3--the-one-idea-everything-else-follows-from)
  - [3.1 What that buys, in three consequences](#31-what-that-buys-in-three-consequences)
  - [3.2 What it costs, honestly](#32-what-it-costs-honestly)
  - [3.3 ⭐ We measured it rather than assuming](#33--we-measured-it-rather-than-assuming)
  - [3.4 The honest counter-argument](#34-the-honest-counter-argument)
- [4. What goes in the graph](#4-what-goes-in-the-graph)
  - [4.1 Six node types — a closed list, enforced in code](#41-six-node-types--a-closed-list-enforced-in-code)
  - [4.2 Edges — and one decision that matters](#42-edges--and-one-decision-that-matters)
  - [4.3 Every link records how sure we are](#43-every-link-records-how-sure-we-are)
  - [4.4 ⭐ Two rules about evidence that took us three attempts](#44--two-rules-about-evidence-that-took-us-three-attempts)
- [5. How things get in](#5-how-things-get-in)
  - [5.1 The deterministic lane is the default, not the fallback](#51-the-deterministic-lane-is-the-default-not-the-fallback)
  - [5.2 Extraction is treated as untrusted by design](#52-extraction-is-treated-as-untrusted-by-design)
  - [5.3 Entity resolution — stopping the graph from fragmenting](#53-entity-resolution--stopping-the-graph-from-fragmenting)
  - [5.4 What gets shown to the student](#54-what-gets-shown-to-the-student)
- [6. How things come out](#6-how-things-come-out)
  - [6.1 Retrieval — four stages](#61-retrieval--four-stages)
  - [6.2 ⭐ Why the cap is 50, and why it matters more than it sounds](#62--why-the-cap-is-50-and-why-it-matters-more-than-it-sounds)
  - [6.3 The ranking function](#63-the-ranking-function)
  - [6.4 Lenses](#64-lenses)
- [7. What makes it a mentor rather than a filing cabinet](#7-what-makes-it-a-mentor-rather-than-a-filing-cabinet)
  - [7.1 Gaps that generate themselves](#71-gaps-that-generate-themselves)
  - [7.2 Dead-end memory](#72-dead-end-memory)
  - [7.3 The crossover scorer](#73-the-crossover-scorer)
  - [7.4 ⭐ The Disagreement Engine](#74--the-disagreement-engine)
  - [7.5 Changing your mind — the part most systems get wrong](#75-changing-your-mind--the-part-most-systems-get-wrong)
  - [7.6 ⭐ One week, end to end](#76--one-week-end-to-end)
- [8. Erasure — the one legal constraint that shaped the architecture](#8-erasure--the-one-legal-constraint-that-shaped-the-architecture)
- [9. Where the AI sits](#9-where-the-ai-sits)
  - [9.1 ⭐ Determinism is preserved by *recording*, not by constraining](#91--determinism-is-preserved-by-recording-not-by-constraining)
  - [9.2 ⭐ Every call is context-isolated](#92--every-call-is-context-isolated)
  - [9.3 Four roles](#93-four-roles)
- [10. ⭐ Which model does what](#10--which-model-does-what)
  - [10.1 The routing rule](#101-the-routing-rule)
  - [10.2 Five tiers](#102-five-tiers)
  - [10.3 Three consequences worth stating plainly](#103-three-consequences-worth-stating-plainly)
  - [10.4 ⭐ The answer streams; the critique lands after](#104--the-answer-streams-the-critique-lands-after)
- [11. How we'll know it works](#11-how-well-know-it-works)
  - [11.1 ⭐ Calibration — and the mistake we nearly made](#111--calibration--and-the-mistake-we-nearly-made)
- [12. Storage, cost and operations — measured, not estimated](#12-storage-cost-and-operations--measured-not-estimated)
  - [12.1 The load test](#121-the-load-test)
  - [12.2 ⭐ The constraint we hadn't thought of](#122--the-constraint-we-hadnt-thought-of)
  - [12.3 Cost](#123-cost)
- [13. What we weren't sure about — all twelve, and how each was settled](#13-what-we-werent-sure-about--all-twelve-and-how-each-was-settled)
  - [13.1 ⭐ The last two are the most instructive](#131--the-last-two-are-the-most-instructive)
  - [13.2 ⚠️ And a mistake inside the fix — the best example in this document](#132--and-a-mistake-inside-the-fix--the-best-example-in-this-document)
- [14. What is still genuinely unknown](#14-what-is-still-genuinely-unknown)
  - [14.1 Needs real users, not more thinking](#141-needs-real-users-not-more-thinking)
  - [14.2 Needs domain expertise — the one concrete ask](#142-needs-domain-expertise--the-one-concrete-ask)
  - [14.3 Frontend and strategy](#143-frontend-and-strategy)
- [15. Status and what happens next](#15-status-and-what-happens-next)
- [16. Why this is different](#16-why-this-is-different)
- [17. Glossary](#17-glossary)
- [18. Where to go deeper](#18-where-to-go-deeper)

---

# 1. The problem, in one page

A student has an idea. Over six weeks they read papers, write firmware, breadboard a circuit, take measurements, get confused, change their mind, and — if it goes well — end up with something that works.

**Right now all of that lives in three places that don't talk to each other:**

| Where | What's in it | What's wrong with it |
|---|---|---|
| Their head | the actual understanding | leaks; unavailable to anyone else |
| A chat history | most of the reasoning | forgets; no structure; can't be queried |
| A folder of files | code, PDFs, CSVs, photos | inert; nothing relates to anything |

So **the measurement from week 2 never finds out it contradicts the paper from week 5**, the approach abandoned in week 3 gets suggested again in week 6, and the write-up reconstructs the reasoning from memory — the part most worth keeping.

**The Mind Graph is the connective tissue:** a living record of what the student believes, what they've built, whether it worked, and how those relate — which survives between sessions and gets *more* useful as the project goes on.

> **Atlas maps what the literature says.**
> **Obsidian maps what you wrote.**
> **Graphify maps the corpus you point it at** — code, papers and docs alike.
> ⭐ **Nexus maps what you built, whether it worked, and what to do next.**

That last clause is the entire differentiator, and §4 shows it comes down to **one node type**.

## 1.1 Why a graph at all

A fair question, and we asked it of ourselves twice (§13, doubts 7 and 12). A graph isn't there to be looked at — it's there because four things are **impossible without explicit relationships**:

**Multi-hop reasoning** (*"what depends on the assumption I just disproved?"* is a traversal; in a pile of documents it isn't answerable at all) · **provenance** (*"why do I believe this?"* walks backwards along what justified it) · **supersession** (*"I used to think X"* needs the old belief to still exist) · **crossover** (comparing structures, not text).

⭐ **All four are machine-facing** — they work whether or not anyone looks at a diagram, which is why we **lead with ranked answers, not pictures**.

> **How to read this.** It runs as a pipeline: what goes in (§4), how it gets in (§5), how it comes out (§6), what the system does with it (§7–§10). **If you read three sections, read §3** (the idea everything follows from), **§7** (what makes it a mentor), and **§13** (the twelve things we weren't sure about — four of which we got wrong first).
>
> ⭐ = the load-bearing idea · ⚠️ = a real risk. **Disagreeing is the useful output** — adding a thirteenth doubt beats agreeing with the twelve.

---

# 2. Where this design came from

Nothing here was invented from scratch. Before a line of design was written we did six teardowns — ~90 pages — on the products that exist and the academic work behind them.

| Source | What we took from it |
|---|---|
| **Graphify** — read from source, 103,166★, Apache 2.0 | the belief/structure split · the **discrete confidence rubric** (§4.3) · community stability · ⭐ **dead-end memory and the corroboration gate** (§7.2) — both already shipped in their `reflect` subsystem · surprise scoring |
| **Obsidian** — API and a real 3-year vault | **phantom nodes** from unresolved links (§7.1) · span-level citation · edge weight · co-citation · saved views |
| **Atlas** — closest direct competitor, **claims** 5,000+ researchers, $16/mo Pro | two-tier maps · **lenses** (angle prompts) · the citation-state taxonomy · and, importantly, **what they structurally cannot do** |
| **Academic prior art** | Knowledge Space Theory (Doignon & Falmagne, 1985) → the frontier engine · ATMS (de Kleer, 1986) → retraction · Degree-of-Interest (Furnas, 1986) → ranking · CiTO → the relation vocabulary · Wikidata → the rank model |
| **GraphRAG failure literature** | *how knowledge graphs rot* — and the entity-resolution and tombstoning fixes that stop it |
| **Operating reality** | the ~50-node comprehension limit · that analysis is CPU-bound, not model-bound · **that nobody has published real cost or curation data** |

## 2.1 Two things the research taught us that we didn't expect

**⚠️ Published benchmark numbers here do not survive checking.** One memory product headlines 84%; independent re-evaluation puts the corrected figure at **58.44%**. A widely-cited graph-retrieval framework concedes its own benchmarks *"fail to adequately evaluate the effectiveness of graph structures."* That shaped §11 — **we build our own measurement and pre-register what would count as failure.**

**⚠️ The obvious database choice disappeared mid-research.** KuzuDB was exactly the right shape; **Apple acquired the team and archived it in October 2025.** Not bad luck to route around — evidence for a design principle, and §3 is built on it.

---

# 3. ⭐ The one idea everything else follows from

Almost every later decision falls out of this picture.

```
   ┌──────────────────────────────────────────────────┐
   │  THE LEDGER     append-only · never edited        │  ← the asset
   │  every event, in order, permanently               │
   └──────────────────────────────────────────────────┘
                          │  deterministic replay
                          ▼
   ┌──────────────────────────────────────────────────┐
   │  THE GRAPH      a rebuilt view of the ledger      │  ← the working set
   │  throw it away and regenerate it any time         │
   └──────────────────────────────────────────────────┘
                          │  derived
                          ▼
   ┌──────────────────────────────────────────────────┐
   │  SIDECARS       clusters · centrality · scores    │  ← disposable
   └──────────────────────────────────────────────────┘
```

**In plain terms:** we never edit the graph. We record *events* — *"a node was created," "a measurement matched its prediction"* — into an append-only log, and the graph is **computed** from that log, the same way every time.

**An analogy:** a bank doesn't store your balance and edit it. It stores transactions and derives the balance. If the balance is wrong you fix the calculation and re-derive — you don't edit the number.

**What an event actually looks like**, so this stays concrete:

```
seq 1041 · 2026-03-14T09:22Z · node_created
    { id: n_8f2a, type: Artifact, kind: run }
seq 1042 · 2026-03-14T09:22Z · edge_created
    { src: n_8f2a, dst: c_impedance, relation: measured_by,
      confidence: EXTRACTED, score: 1.0, span: "measurements/03-14.csv:L18" }
seq 1043 · 2026-03-14T17:05Z · validated
    { artifact: n_8f2a, agreement: matched }
```

Three facts, in order, never edited. The graph — *"there is a run that measured skin impedance, and it matched what the student predicted"* — is **computed** from them. Delete the graph and it comes back identical; **delete the log and everything is gone**, which is why the log is the thing we back up (§12).

## 3.1 What that buys, in three consequences

**1. Every failure becomes repairable.** Bad import, wrong merge, drifted schema — all fixed by **changing the recipe and re-projecting**, not by surgery on a live database. History survives; bad structure doesn't.

**2. ⭐ The database becomes a swappable detail.** Choose wrong and we re-project into a different store in an afternoon. Given the obvious choice was archived under us mid-research (§2.1), this is the most valuable property in the design — **almost nothing else in software is that reversible.**

**3. Time comes free.** *"What did I believe in week 2, and why did I change my mind?"* is a replay, not a feature.

## 3.2 What it costs, honestly

**Every write is two writes**, and the projector — the code turning events into a graph — becomes correctness-critical. If it's wrong, everything downstream is wrong and every bug looks like it lives elsewhere. Hence §15: the projector is built *first* and tested hardest.

## 3.3 ⭐ We measured it rather than assuming

*"Re-projecting is cheap"* was an assertion for three days. We tested it:

> **Replaying 60,000 events into a full graph takes 122 milliseconds** — bound by event count, not graph size, so it doesn't degrade as a project grows.

§12.2 shows this one number solving a problem we hadn't identified yet.

## 3.4 The honest counter-argument

This isn't forced. A simpler design regenerates the graph from files and chat each time, and is **dramatically cheaper to build.** The argument for ours: it's **the only version where time, outcome and changing your mind mean anything** — and those are the differentiators. An argument, not a proof, and the premise most worth attacking.

---

# 4. What goes in the graph

## 4.1 Six node types — a closed list, enforced in code

| Type | What it is | Example |
|---|---|---|
| **Concept** | a unit of knowledge | `I²C`, `PID control`, `skin impedance` |
| **Question** | something unresolved. **The project itself is one** | *"Can skin impedance track hydration?"* |
| **Claim** | an assertion whose truth can change | *"47 kΩ at 50 kHz means hydrated"* |
| ⭐ **Artifact** | **something you made or ran** | firmware build · circuit · measurement · **method** |
| **Source** | external evidence | paper · datasheet · lecture · video |
| **Note** | unstructured prose — the escape hatch | *"5V rail felt noisy?"* |

**Two of these carry unusual weight.**

### ⭐ `Artifact` is the entire moat

**None of the three has a place for the thing you built and the number you measured.** An `Artifact` carries three fields no competitor has:

```
predicted    what you thought would happen   ← locked before you run it
measured     what actually happened
agreement    matched | partial | contradicted
```

That triple is where almost everything distinctive comes from — calibration (§11), the corroboration rule (§4.4), and the *"did it work?"* signal that makes the frontier useful. **One node type, and it's the whole differentiator.**

### `Note` is not optional

The best-evidenced finding in our research is *Formality Considered Harmful* (Shipman & Marshall, CSCW 1999): **users will not fill in structured forms** — they abandon the tool or game it. So a student can always just *write*, and the system proposes structure afterwards. ⭐ **The student never picks a node type. Ever.**

⚠️ **Does everything then become a Note, leaving us as Obsidian with extra steps?** Guarded by a **structuring nudge**: when unstructured notes exceed 40% of recent nodes, the system offers a one-pass batch structuring. **An offer, never a requirement**, and a note that resists twice is left alone permanently.

### Why six and not eight

Atlas uses eight, adding `Method`, `Limitation`, `Evidence` and `Section`. We collapsed those:

| Their type | Where it went | Why |
|---|---|---|
| `Limitation` | an **edge** (`contradicts`) | makes tension countable and resolvable, not decorative |
| `Evidence` | `Source` | it was never a different thing |
| `Section` | a span reference | structure of a document, not of knowledge |
| `Method` | ⭐ `Artifact(kind=method)` | see below |

**Fewer types means less drift.** Atlas concedes *"labels can vary by source and generation model"* — they didn't choose a loose ontology; that's what you get without enforcement.

### ⭐ `Method` — which turned out to matter more than we thought

*"4-wire Kelvin at 50 kHz, 10 mV excitation, dry Ag/AgCl electrodes, 2 cm spacing, forearm."*

Not a Concept (the general technique is; your setup isn't), not a Claim (it asserts nothing), not a run (many runs share one method). It *is* something you made — a procedure:

```
Artifact(kind=run) --uses_method_in--> Artifact(kind=method)
```

We filed this as a convenience. **It's actually an error-detector** — see §4.4.

## 4.2 Edges — and one decision that matters

Typed links: `supports` · `contradicts` · `requires` · `evidence_for` · `measured_by` · `cites` · `refutes` · `answers` · `supersedes` and ~nine more, named after **CiTO**, a published citation-typing standard — free interoperability, one less vocabulary to defend.

> ⭐ **"These two things disagree" is an EDGE, not a node.**

That single choice is why disagreement can be **counted, ranked and resolved** rather than rendered as a red dot. All of §7.4 is built on it.

**Hyperedges are first-class.** *"These five measurements **jointly** support this conclusion"* is **one** relationship, not five.

⚠️ **The difference shows up when you retract something.** With five separate edges, removing one measurement leaves four — the conclusion looks almost as well supported as before. With a hyperedge, the joint justification is either satisfied or it isn't: pull one measurement out and **the support is gone**, because the claim was never *"four of these agree"*, it was *"all five together show the trend."*

Retrofitting this later means revisiting every edge ever created to ask whether it was really part of a group — which is why it's in from day one despite costing more now.

## 4.3 Every link records how sure we are

| Tier | Meaning |
|---|---|
| `EXTRACTED` | stated right here, in this passage. **Requires a quoted span** |
| `INFERRED` | derived. **Exactly five allowed values: 0.95 / 0.85 / 0.75 / 0.65 / 0.55** |
| `AMBIGUOUS` | genuinely unclear — **flagged, never discarded** |

**What each tier looks like in practice:**

| | Example |
|---|---|
| `EXTRACTED` | the datasheet says *"typical settling time 12 ms"* — quoted, page and line recorded |
| `INFERRED 0.95` | your code sets the prescaler to 64, so the timer runs at 250 kHz — arithmetic over things we know |
| `INFERRED 0.75` | your noise problem is probably grounding, because three symptoms co-occur with it |
| `INFERRED 0.55` | this measurement *might* relate to the electrode drift you mentioned last week |
| `AMBIGUOUS` | the paper says "impedance" but never says at what frequency — **cannot be resolved without asking you** |

⭐ **Why five fixed rungs, not a 0–1 range.** Ask a model for a confidence score and it returns 0.5 or 0.9 and little else — Graphify measured **over 50% of scores at 0.5, over 40% above 0.85** in production. A continuous scale looks more precise and carries less information; five rungs force real discrimination. **A measured result from a real system, not a preference.**

## 4.4 ⭐ Two rules about evidence that took us three attempts

These are subtle, and they're where the design earns its keep.

### Rule 1: distinct is not independent

A claim becomes `ESTABLISHED` when **two separate validated results** back it — not when it's heavily cited. Five papers citing one original are **one fact repeated**, the classic citation cascade, and letting citation count drive confidence manufactures false certainty exactly where a student can least detect it.

So we first **discount any source reachable from another via `cites`**, then damp what's left. *(First version used `log₂`. At the weights we see — 1 to 5 — `log₂` says the second source **doubles** the evidence. Far too generous; it's `sqrt` now.)*

### Rule 2: ⭐ the same rule applies to your own experiments — and we missed it

Two measurements using **the same method** aren't independent corroboration either — replication that varies nothing confirms your *setup*, not your *claim*. We applied the insight to citations and completely missed it for results. The Method node makes it visible:

```
┌──────────────────────────────────────────────────────┐
│  47 kΩ at 50 kHz indicates hydrated skin              │
│  ESTABLISHED · 3 results agree                        │
│  ◑ all three used one method — 4-wire Kelvin, 2 cm →  │
└──────────────────────────────────────────────────────┘
```

⭐ **It flags; it never blocks.** Same-method replication is a legitimate reproducibility check and an undergraduate usually has one rig — blocking would punish the normal case to catch the rare one. The value is **the click**: expanding it asks *"what would a different method look like?"*, the highest-value experiment suggestion the system can make.

**A claim backed three times by one setup is the most common way a student is confidently wrong**, and nothing in the design could see it before.

---

# 5. How things get in

```
files · chat · photos · logs · transcripts
  → INTAKE (route, dedupe) → EXTRACTOR (ontology-constrained) → RESOLVER (same entity?)
  → PROPOSALS (nothing committed yet) → auto-accept | ask the student
  → LEDGER (append-only) → PROJECTOR (deterministic) → GRAPH
```

## 5.1 The deterministic lane is the default, not the fallback

| Input | How it's processed | Cost | Confidence |
|---|---|---|---|
| code (`.py .c .cpp .ino`) | AST parse (tree-sitter) | **0 tokens** | `EXTRACTED` |
| CSV / JSON measurements | direct parse | **0 tokens** | `EXTRACTED` |
| serial / scope logs | parser + heuristics | **0 tokens** | `EXTRACTED` |
| git history | direct parse | **0 tokens** | `EXTRACTED` |
| papers, datasheets (PDF) | chunk → language model | tokens | mixed |
| photos, whiteboards | vision model | tokens | mixed |

⭐ For an embedded project, **a large share of the graph never meets a language model** — files, functions, calls, commits, pin assignments, measured values. One decision, both a cost and a trust advantage.

## 5.2 Extraction is treated as untrusted by design

Measured hallucination rates on relationship extraction run **1.5–1.9%** — on a 5,000-edge graph, roughly **75–95 invented relationships**, encoded as structure that downstream code treats as fact.

So output passes three gates: **a closed ontology** (only types and relations from the fixed list), **a code validator** (schema, span existence, legal confidence values), and **quarantine** (failures held and triaged, never silently dropped).

⭐ **This is why we can run a small, cheap model here** (§10.2). The safety doesn't come from the model being good; it comes from **never having believed it in the first place.**

## 5.3 Entity resolution — stopping the graph from fragmenting

The commonest way knowledge graphs rot: one thing appearing as five nodes — `I2C`, `I²C`, `IIC`, `TWI`, `Inter-Integrated Circuit`.

**MinHash/LSH blocking** cuts millions of comparisons to thousands → **Splink (Fellegi–Sunter)** gives a match probability → **≥0.95** merge · **0.70–0.95** ⭐ `same_as` edge, *both nodes survive* · **<0.70** leave alone.

⭐ **The middle band matters most.** A wrong merge is node surgery to undo; a wrong `same_as` edge is one deletion. **When unsure, prefer the mistake that's cheap to reverse** — a principle that recurs throughout the design.

## 5.4 What gets shown to the student

⚠️ This is where we changed our minds most significantly.

**Original design:** the student reviews everything the system isn't certain about. **Problem:** professionals process thousands of items a day; a student at 1am does zero, and there was no fallback. **What changed it** was reframing the question — not *"how do we keep bad data out?"* but *"what is a human uniquely good at here?"*

| Tier | What happens |
|---|---|
| `EXTRACTED` | auto-accept |
| **all `INFERRED`** (0.95 → 0.55) | auto-accept, flagged, **one-click reversible** |
| ⭐ `AMBIGUOUS` | **always asked of the student** — never auto-accepted, never dropped |

> ⭐ **The point of Nexus is to make the student think.** So a case the system genuinely cannot resolve is not a chore to be gated — it's exactly the moment a human should be reasoning, and handing it to a model instead defeats the product.

That inverts what the queue is *for* — it stops being an integrity gate and becomes a **thinking prompt** — and fixes the volume problem too, because an `AMBIGUOUS`-only queue is small enough to get done. **One decision fixed both.**

**What protects the auto-accepted inferences:** they render faded, they rank low, ⭐ **they cannot promote anything** (only validated results can), and a nightly contradiction sweep catches the rest. A fabricated edge is inert — it decorates, it never establishes.

---

# 6. How things come out

## 6.1 Retrieval — four stages

**SEED** (embeddings + keyword find ~10 entry points) → **EXPAND** (Personalized PageRank walks outward) → **RANK** (Degree-of-Interest) → **CAP** (hard limit, 50 nodes).

**Why hybrid rather than pure vector search:** embeddings find things that *sound* similar; graph expansion finds things that are *connected*, including where the wording shares nothing. A student's phrasing rarely matches a datasheet's, and the connection is the point.

## 6.2 ⭐ Why the cap is 50, and why it matters more than it sounds

Comprehension of node-link structures degrades badly past roughly 50 nodes. Performance, meanwhile, is fine to about 25,000.

> **The limit is human, not technical — by a factor of 500.**

So there is no version of this product where *"show more"* is the answer. **The ranking function is the product**, and every "more results" affordance is a decision not to rank well.

## 6.3 The ranking function

Based on Furnas's Degree-of-Interest (1986), still the most-cited formulation in the field:

```
DOI(x) = importance(x) − distance(x, focus)
importance = w₁·centrality + w₂·recency + w₃·confidence + w₄·outcome + w₅·learnability
```

**`outcome` and `learnability` are the two nobody else has** — `outcome` uses the Artifact `agreement` field, `learnability` uses the frontier. Both exist only because of §4.1.

⚠️ **The weights are currently guesses**, set as explicit defaults that **ramp with graph age**: `learnability` starts high when there's no history to rank on and decays as outcome data arrives. Tuned from click data in weeks 2–4. **We wrote them down as decisions rather than letting them be accidents.**

## 6.4 Lenses

The same graph, asked a different question, should return different things. *Debug* wants recent failures and dependencies; *Write-up* wants established claims with citations; *Learn* wants the frontier.

**Same graph, same question, three answers:**

| Lens | *"tell me about electrode impedance"* returns |
|---|---|
| **Debug** | the three measurements that failed, what changed between them, and the two dead ends nearby |
| **Write-up** | the established claims with citations, and the one claim still marked contested |
| **Learn** | what impedance depends on, what you haven't demonstrated yet, and the next thing you're ready for |

⭐ **Lenses are inferred, then shown as a chip you can change** — `Viewing as: Debug ▾`. Forcing a dropdown is a form (§4.1); inferring silently is invisible. Propose, show, allow override — **the same shape as the structuring nudge and the method picker.** Three instances makes it the product's default interaction pattern rather than three separate decisions.

---

# 7. What makes it a mentor rather than a filing cabinet

Five features, all of which fall out of the data model rather than being bolted on.

## 7.1 Gaps that generate themselves

Two mechanisms, and neither requires anyone to *declare* a gap.

**Phantom nodes** (from Obsidian's unresolved links — the best idea in that product): if something references a concept and nothing has ever defined or validated it, that concept exists as a **hollow node**. Nobody decided it was a gap; **the gap exists because something pointed at it and nothing filled it.**

**The knowledge frontier** (Knowledge Space Theory, Doignon & Falmagne 1985): given a prerequisite structure and what you've demonstrated, KST computes your **outer fringe** — the concepts every prerequisite of which you already have. That is a formal definition of *"ready to learn next."*

**Concretely.** Suppose the skeleton records:

```
impedance      requires  capacitance, inductance, complex_numbers
bioimpedance   requires  impedance, sensor_interfacing
eis            requires  bioimpedance, frequency_response, fft
```

A student who has demonstrated `capacitance`, `inductance` and `complex_numbers` has **`impedance` in their outer fringe** — every prerequisite is met, nothing else is. `bioimpedance` is *not*: it needs `impedance` first. And `eis` is further still — it needs `bioimpedance`, `frequency_response` **and** `fft` — so suggesting it now would be noise.

⭐ **Nobody tagged `impedance` as "the next topic."** It became the next topic because of what the student has already demonstrated and what the prerequisite structure says. That's the difference between a curriculum and a frontier — **the curriculum is the same for everyone; the frontier is computed per student, per day.**

"Demonstrated" is doing real work there: a concept enters the knowledge state only when an **Artifact validates it** (§4.4), not when the student reads about it. Which is why §4.1's node type is load-bearing here too.

⚠️ **This needs a prerequisite graph, and there is nothing to download** — the research found high-quality open datasets for granular engineering curricula essentially don't exist. So we hand-built one: **213 concepts** for embedded systems with their prerequisite edges. Production systems like ALEKS do the same.

⭐ **We wrote a validator for it and ran it, which had never been done.** It found six real defects — including that the document claimed 187 concepts when there are 213. §13.1 and §13.2 tell that story, and it's a good one.

## 7.2 Dead-end memory

When something is abandoned, we record **what was tried, why it failed, and what would make it worth revisiting.**

`dead_end: "I²C at 400 kHz — bus errors under motor load"` · `resurrect_if: [shielding_added, bus_speed_reduced, motor_isolated]`

Six weeks later, when the student adds shielding, the system says *"this unblocks something you gave up on."*

⚠️ **This one is not ours, and the difference from Graphify is narrower than it looks.** Graphify's `reflect` subsystem already does this: `--outcome useful | dead_end | corrected`, signed and time-decayed with a 30-day half-life, a corroboration gate of two before anything is promoted, and dead ends stored as questions — *"don't re-derive this."* We took the mechanism from them, and §4.4's corroboration rule too.

⭐ **What we add is what the outcome attaches to.** Graphify records whether an **answer** was useful. Nexus records whether **the thing you built worked** — `predicted` / `measured` / `agreement` on an Artifact, plus explicit `resurrect_if` conditions rather than time decay alone.

**Atlas has nothing here at all** — their own gap analysis is best summarised by our teardown's observation that *"knowledge compounding"* is a blog title rather than a mechanism. A research project is mostly a record of what didn't work, and that record is what makes week 6 faster than week 1.

## 7.3 The crossover scorer

*"This bandwidth problem is the same shape as the filter problem in your other project."* Structural similarity across projects — the connection nobody makes for themselves, because the two projects live in different mental folders.

⭐ **The interesting part is how it's made affordable.** Judging every pair of concepts across every project with a frontier model is unaffordable by orders of magnitude. So:

**Free:** embeddings + graph distance generate thousands of candidates, ranked to the top ~5. **Expensive:** the best model judges five.

⭐ **Generate cheap, judge expensive** — the most reusable cost lever in the system, and it appears in three places.

## 7.4 ⭐ The Disagreement Engine

The most distinctive feature, and the one that changed most during design.

When a student's measurement disagrees with a paper, the system doesn't pick a winner — it **surfaces the disagreement, shows both sides with their evidence, and asks the student to resolve it**, which is the skill separating a student from a researcher.

**Six kinds**, because *"you contradict a paper"* is far too narrow:

| Kind | Example |
|---|---|
| `CONFLICT` | your measurement vs. a published value |
| `BOUNDARY` | the paper is right, but not in your regime |
| `SELF` | you concluded the opposite in week 2 |
| `SOURCE` | two sources disagree with each other |
| `ASSUMPTION` | your claim depends on something you never checked |
| `STALE` | something you depended on has since changed |

**Priority is computed separately from kind** — P0 (blocking current work) through P4 (resolved). A `SELF` contradiction on something you're actively using is urgent; the same one on a dormant branch isn't.

⚠️ **Why we rebuilt it.** The original trigger was roughly *"student measurement vs. published claim."* We hand-walked a real six-week biosensor project and found **8–12 genuine disagreements** — the original trigger would have caught about **2**.

⭐ **We had designed around the marketing headline instead of the frequency distribution.** A feature firing twice in six weeks isn't a product, it's a demo. Widening the trigger to any contradiction and ranking by priority makes it something a student meets weekly.

## 7.5 Changing your mind — the part most systems get wrong

**Retraction cascades**, built on ATMS (de Kleer, 1986). Every claim records the facts that justified it; retract one and the system walks forward through everything that depended on it.

> ⭐ **Conclusions lose *support*, not *truth*.**

**A worked cascade.** In week 2 the student concludes *"the 5V rail is clean"*, based on one scope reading. In week 4 they discover the probe was mis-compensated, and retract that reading:

```
retract  "scope reading, week 2"
    ↓ everything justified by it
"the 5V rail is clean"                  → UNSUPPORTED  (not deleted, not false)
    ↓ everything justified by THAT
"the ADC noise is not supply-related"   → UNSUPPORTED
    ↓
"the noise must be the electrode"       → UNSUPPORTED — and this is the one that matters,
                                          because they spent two weeks acting on it
```

A conclusion whose justification collapsed isn't false — it's **unsupported**, a different and more useful state. It stays visible, flagged, and ready to be re-justified.

⭐ **A file system cannot do this**, and neither can a chat history. The cascade only works because every claim recorded *which specific facts* it rested on at the moment it was made — which is the single strongest argument for typed edges over free text.

**Supersession.** Beliefs are never deleted, they're **ranked** — `preferred` / `normal` / `deprecated`, borrowed from Wikidata, which solved this at enormous scale. The old belief stays, linked to what replaced it.

**Two kinds of time.** *When it was true in the world*, tracked separately from *when we learned it*. Without both, *"I was wrong about this in week 2"* and *"this stopped being true in week 2"* are indistinguishable — and they demand opposite responses.

## 7.6 ⭐ One week, end to end

Everything above, as a single week of a real project. This is the section to read if the rest felt abstract.

**Monday — a paper goes in.** The student uploads Chen et al. on skin impedance. Intake hashes it and routes it to the semantic lane; the Tier 1a model extracts under the closed ontology. Out come a `Source`, several `Concept`s, and a `Claim` — *"hydrated skin measures 30–40 kΩ at 50 kHz"* — tagged `EXTRACTED 1.0` with the exact span. The resolver notices `skin impedance` already exists as a node and links to it rather than creating a second one (§5.3).

One extraction says the paper *"used a 4-wire method"*, but the passage never says so outright. That's `AMBIGUOUS`, so it goes to the review queue — **the only thing that does** (§5.4).

**Tuesday — the student predicts.** They open an Artifact, write `predicted: 45–50 kΩ`, and **lock it.** It's in the ledger and can't be edited afterwards, which is what makes Friday's number mean something.

**Wednesday — they build and measure.** `measured: 47.2 kΩ`, `agreement: matched`. The Claim it supports gains one corroboration. Not `ESTABLISHED` yet — that needs two independent results (§4.4).

⭐ **And now the interesting thing happens automatically.** The student's 47.2 kΩ and Chen's 30–40 kΩ are both live, both supported, and they disagree. The Disagreement Engine fires a **`CONFLICT`**, priority P1 because it touches active work. It doesn't pick a winner — it shows both with their evidence and asks (§7.4).

**Thursday — the student resolves it.** Chen measured with gel electrodes; they used dry. That's not a contradiction, it's a **boundary condition** — so the disagreement is reclassified `BOUNDARY` and the Claim is narrowed to *"…with dry electrodes."* **This is the whole product in one interaction:** the system found the tension, the student did the thinking, and the graph got more precise as a result.

**Friday — three things happen without being asked.**

The frontier recomputes: `bioimpedance` is now demonstrated, so `eis` enters the outer fringe — *ready to learn next* (§7.1). The `single_method` flag appears on the Claim, because both supporting results used the same rig (§4.4). And an earlier note — *"tried 400 kHz I²C, bus errors under motor load"* — is stored as a dead end with `resurrect_if: [shielding_added]`, so it stays out of the way until it's relevant again (§7.2).

**What was recorded that a folder of files would have lost:** that the prediction came *before* the measurement · that two sources disagreed and *why the disagreement dissolved* · that the claim now has a scope condition it didn't have on Monday · and that one approach is parked rather than forgotten.

⭐ **Every one of those is a link, not a document.** That is the argument for the graph, made concrete.

---

# 8. Erasure — the one legal constraint that shaped the architecture

GDPR grants a right to erasure; an append-only ledger never deletes. **Genuinely in conflict**, and the resolution is a real technique rather than a fudge:

> **Crypto-shredding.** Encrypt content under a per-user key. On erasure, **destroy the key.** The ciphertext stays in place but is mathematically noise.

Which forces every event to split into a **plaintext** half (ids, types, relations, confidence, timestamps, `agreement`) and an **encrypted** half (labels, prose, file bodies, predicted/measured values).

**What that looks like on one event.** Before erasure:

```
structural   { id: n_8f2a, type: Artifact, kind: run, agreement: matched, seq: 1043 }
content      🔒 { label: "forearm impedance sweep", predicted: "45–50 kΩ",
                  measured: "47.2 kΩ", notes: "…" }
```

After the key is destroyed, the `structural` half is untouched and the `content` half is unreadable noise. **The projector still runs, the graph still has the right shape, and nothing corrupts** — there is simply a node with no label.

⭐ **And that's why the split is where it is.** Because `agreement: matched` sits in the plaintext half, **we can still answer *"do students get better calibrated?"* across everyone who ever used the product, including people who have exercised their right to erasure** — while knowing nothing whatsoever about what they measured. The research value survives; the personal data doesn't.

⚠️ **This is also the rule easiest to break by accident.** Put a label, a note, or a measured value into `structural` "just for convenience" and erasure quietly stops working — so `Backend/02` tests for it in CI rather than trusting anyone to remember.

⚠️ **The rule that makes or breaks it:** keys and data must never be backed up together. If one restore recovers both, crypto-shredding was defeated by your own disaster recovery.

---

# 9. Where the AI sits

**AI agents read the graph and propose changes. They cannot change it.**

| Rule | Why |
|---|---|
| **Agents propose; a gate decides** | there is no code path from a model's output to a node |
| **Agents can never record an outcome** | if AI could write *"this worked"*, the record of what worked becomes fiction — and that record is the entire asset |
| **Agents can never retract** | retraction cascades and destroys support. Human judgement |
| ⭐ **Confidence tier is bound to capability** | an agent with no document access **structurally cannot** claim something was stated in a source |

**Why that last row is stronger than a rule.** Most systems ask the model to be honest about its sources, in the prompt. We don't ask. `EXTRACTED` requires both `READ_CONTENT` **and** a non-null span, and the **gate** checks that — so a reasoning call that never received any document text is rejected if it claims one, no matter what it says about itself. **A prompt is a request; a capability check is a fact about the call.**

## 9.1 ⭐ Determinism is preserved by *recording*, not by constraining

Models are non-deterministic. The projector must be deterministic. These sound incompatible; they aren't:

> `agent (unpredictable)` → `proposed event (recorded verbatim)` → `ledger` — and **the projector replays the record, never the agent.**

Rebuild the graph a year later with a completely different model and you get a **byte-identical result**, because we saved what the agent *said* rather than re-running it.

**The most important consequence of §3, and easy to break** — by letting the projector call a model, generating IDs at projection time, or re-running extraction during a replay.

## 9.2 ⭐ Every call is context-isolated

The rule above — *"an agent with no document access cannot fabricate a citation"* — is only true if it has **genuinely never seen a document.**

Run the reader and the reasoner as two messages of one conversation and the document text is still in the context window. The gate checks the *declared* capabilities, the context contains material those capabilities exclude, and **the guarantee silently becomes a lie while every test still passes.**

So each call is an **independent, stateless request with a capability-scoped payload**, never a turn in a running chat. We only found this when questioning whether we needed four agents at all — **the separation had been protecting something we'd never named.**

## 9.3 Four roles

| Role | Can see | Produces |
|---|---|---|
| **Router** | query shape, frontier state | which capabilities this turn needs. **Free — no model call** |
| **Planner** *(hard turns only)* | structure, frontier | a decomposition into sub-steps. **Cannot propose anything** |
| **Grounder** | structure + **documents** | claims tied to quoted spans |
| **Synthesiser** | structure only, **no documents** | conclusions and connections |
| **Critic** | structure + history + **one cited span** | contradictions, ambiguity, staleness |

**Three deliberate choices.** The Planner decides what happens but not what's true. The Synthesiser has no document access, so it *structurally* cannot fabricate a citation. The Critic reads history — the only role that can say *"you concluded the opposite in week 2."*

⭐ **The Critic's span access is deliberately narrow:** exactly the passage another call already quoted, no browsing, no search, and it can only **downgrade** a citation's strength, never raise it. That closes the last self-grading loop (the Grounder had been assessing its own citations) without creating a second, unaccountable Grounder.

---

# 10. ⭐ Which model does what

This is where cost is decided, and the rule is not the obvious one.

## 10.1 The routing rule

> **If a wrong answer is caught by code, use the cheapest model that passes the validator.**
> **If a wrong answer is caught only by a human — or by nobody — use the best model available.**

*"Easy tasks get cheap models"* is unfalsifiable — every task looks easy to whoever specified it. **Verifiability is a property of the contract**, so it can be checked.

## 10.2 Five tiers

| Tier | Model | What runs there | Why it's safe there |
|---|---|---|---|
| **0** | *none* | turn routing · entity blocking · PageRank, clustering, ranking · **all validation** · the projector | deterministic. Free, and zero latency |
| **1a** | ⭐ **our own open-source model** | **every embedding** · **all bulk extraction** · soft-band matching · dead-end similarity | §5.2 already treats this output as untrusted — strict schema, validator, quarantine |
| **1b** | **Haiku** | structuring nudge · map labels · quarantine triage | small, **user-visible**, needs instruction-following a 7–14B model is unreliable at |
| **2** | **Sonnet** | Grounder · routine Critic · executing planned sub-steps | **partially checkable** — span *existence* is verified by code, *relevance* isn't |
| **3** | **Opus** | Synthesiser · boundary judgments · planning hard turns | **not mechanically checkable.** Judged by a human or by nobody |

**Serve Tier 1a with grammar-constrained decoding**, enforcing the schema *while the model generates* rather than checking afterwards. A small model then satisfies the format essentially always, leaving only *wrong content* — which quarantine already handles.

⚠️ **"Our own model" doesn't need our own GPU in week one.** Start on a hosted open-source endpoint (10–30× cheaper), self-host later — identical API, so it's a config change and doesn't block the build on hardware.

**One turn, traced through the tiers.** The student asks *"does my impedance data match the Zhang paper?"*

| | Runs on | Cost |
|---|---|---|
| Router classifies the turn — needs content + history, **SIMPLE** | **Tier 0** | free |
| Query embedded; graph expanded by PPR; 50 nodes ranked and capped | **1a / Tier 0** | ~0 |
| Grounder reads the Zhang passages, emits claims tied to spans | **Sonnet** | most of the input tokens |
| Critic checks the cited span and the timeline, concurrently | **Sonnet** | small |
| Answer streams to the student while the Critic runs | — | — |

**No Opus call at all** — this turn didn't need one. Ask instead *"why does my whole hydration hypothesis keep failing?"* and the Router escalates: **Opus** plans the decomposition, **Sonnet** executes each sub-step in parallel, **Opus** composes the answer.

⭐ **The cheap path is the default and the expensive path is opt-in** — decided by a free heuristic, not by a model deciding how much to spend on itself.

## 10.3 Three consequences worth stating plainly

⭐ **The capability filter is also a cost filter.** The Synthesiser never receives document bodies — so the expensive model never carries the expensive payload. **Merging the roles into one call would cost about 70% *more*, not less**, because you'd pay frontier rates on every content token. We had assumed the opposite for weeks.

⭐ **Ingestion, not conversation, is where the tokens are.** A project ingests 300–600k tokens of source material, all of it embedded and extracted under a schema. **Moving that to our own model takes roughly a third of the bill to near zero** — and it's the one large line whose output is mechanically checked, which is exactly why it's movable.

⭐ **Generate cheap, judge expensive.** Tier 0 produces thousands of candidates for free; Tier 3 judges five. It's what makes the crossover scorer (§7.3) affordable at all — naively, that feature is unbuildable.

## 10.4 ⭐ The answer streams; the critique lands after

Run strictly in sequence, a turn is **three model round-trips before the student sees a word** — 10 to 20 seconds at a bench, mid-debug. Fatal for a companion, and nothing to do with cost.

The Critic doesn't write the prose; it produces contradiction flags — **so it doesn't need to block the text.** At `t=0.4s` the answer streams with a quiet `◌ checking`; at `t=1.6s` the badge resolves in place (*⚠ Chen et al. report 30–40 kΩ*).

**Nothing is written to the ledger until the Critic returns.** The student reads early; **the graph waits.** Every safety rule in §9 holds — only *display* moved, and **three perceived round-trips became one.**

We only found this because a teammate asked for *"the most optimal reply, efficiently."* We had divided the roles by safety and **never once by speed.**

---

# 11. How we'll know it works

Five metric families. ⚠️ **The discipline matters as much as the metrics** — we spent much of the research phase taking apart other people's benchmarks (§2.1), so ours has to survive the same treatment.

| Family | Measures |
|---|---|
| **Extraction quality** | precision/recall against hand-labelled ground truth |
| **Retrieval quality** | does the right thing surface? Baseline: **Adamic–Adar**, a 2003 algorithm — if we can't beat it, the graph isn't earning its cost |
| **Frontier quality** | are suggested next actions actually done, and do they unblock things? |
| **Calibration** | ⭐ do students get better at predicting outcomes? |
| **Cost** | dollars per accepted proposal, not per turn |

## 11.1 ⭐ Calibration — and the mistake we nearly made

The headline claim is that predicting-then-measuring makes students better calibrated. Obvious test: compare prediction accuracy in week 1 against week 6. ⚠️ **That test is broken, and we nearly shipped it.**

> **Difficulty drift.** Week-6 predictions are about *harder things*. **Flat accuracy on rising difficulty is a real improvement that a naive before/after shows as nothing.**

So we measure a **reliability curve**: *when you said 80% sure, were you right 80% of the time?* It kills the confound **by construction** — it conditions on the student's own stated confidence, so a harder prediction they were appropriately less sure about doesn't penalise them.

**What the curve actually looks like**, for a student who is systematically overconfident:

| They said | They were right | Read |
|---|---|---|
| 90% sure | 55% of the time | badly overconfident |
| 70% sure | 60% of the time | mildly overconfident |
| 50% sure | 52% of the time | well calibrated here |

**Perfect calibration is the diagonal.** The measurement is how far the curve sits from it, and improvement means the whole curve moving toward the diagonal — **which is a different question from "did they get more answers right."** A student can improve their calibration while their raw accuracy falls, if the problems got harder, and that is exactly the case difficulty drift would have hidden.

**Interval coverage moves first.** Well-calibrated 80% intervals contain the truth ~80% of the time; undergraduates land far below. **A large gap means a large effect, detectable at much smaller n.**

⭐ **We pre-registered the null:** predicted decrease ≥0.05 in mean calibration error, min 15 resolved predictions per student, 8+ students. **A null isn't fatal** — calibration is the measurement, not the mechanism. We'd lead with proof completion and publish a finding nobody has.

---

# 12. Storage, cost and operations — measured, not estimated

| Layer | Choice | Why |
|---|---|---|
| **Ledger** | SQLite, one file per user | append-only, boring, trivially backed up; **isolation is a filesystem property** |
| **Graph** | in-process, per user | 10³–10⁴ nodes fits in memory; it's a derived view, so swapping is cheap |
| **Vectors** | sqlite-vec, same file | one artifact per user, no separate service |
| **Sidecars** | JSON next to the snapshot | disposable by definition |

**Deliberately unfashionable: no graph database in v1.** For thousands of small isolated graphs, monolithic graph databases are economically unviable, and the right-shaped product was archived by Apple mid-research. Because the graph is a projection, **the decision is reversible for the cost of a re-projection** — so we defer it until real query patterns exist.

## 12.1 The load test

We ran it rather than deferring it. Synthetic graph, 60,000-event ledger, every nightly job:

| Job | 10k nodes | 25k nodes |
|---|---|---|
| **retrieval (per turn — a student is waiting)** | **27 ms** | **76 ms** |
| **full replay of 60k events** | **122 ms** | 123 ms |
| clustering | 592 ms | 1.75 s |
| approximate centrality | 3.0 s | 9.3 s |
| ⚠️ *exact* centrality | ~118 s | ~738 s |
| memory per live graph | 144 MB | 240 MB |

⭐ **27 ms against a model call of 2–8 seconds — storage is ~100× off the critical path.** There's no version of this where the database is why the product feels slow.

**The one slow job shouldn't be exact.** Betweenness centrality feeds a *ranking* function, not a truth claim, so sampling is correct on the merits rather than a compromise: **118 seconds becomes 3.**

## 12.2 ⭐ The constraint we hadn't thought of

The load test didn't confirm our worry — it found a different one. **CPU was never close to a limit. Memory was.** 144–240 MB per live graph means ten concurrent students ≈ 2.4 GB, and the design said *"one graph per user, in memory"* without ever asking **how many fit at once.**

⭐ **The fix was already in the table.** A 122 ms replay makes eviction free — drop a user's graph, rebuild on their next request in a tenth of a second. *The property that makes the storage reversible is the same one that makes it multi-tenant*, and we had only ever argued the first.

## 12.3 Cost

The original estimate was **≈$8–10 per six-week project** at flat mid-tier rates. Model tiering changes the shape: extraction moves to our own model and falls to cents, leaving roughly **60% of what remains on Opus**, concentrated in three places.

⚠️ **We won't quote a final number we haven't measured.** Every turn writes a cost row from day one, including which tier ran, so the estimate gets *replaced* rather than defended. **Nobody in this field has published real cost data** — which is why we're careful, and why measuring it is worth something on its own.

---

# 13. What we weren't sure about — all twelve, and how each was settled

The most useful section for a reviewer. Each was a design call we were **not confident in**, written down before it was resolved. **All twelve are now closed and none were deleted** — the reasoning is the point. **Four we got wrong first time**, marked ⚠️.

| # | The doubt | How it resolved |
|---|---|---|
| **1** | ⚠️ Will the student actually do the review? | **Reframed from integrity to pedagogy.** Auto-accept everything except `AMBIGUOUS`; ask only what nobody but the student can settle (§5.4) |
| **2** | ⚠️ Are four agent roles worth the cost? | **The cost analysis was backwards** — merging costs ~70% *more* (§10.3). The real property being protected was **context isolation** (§9.2) |
| **3** | Will `Note` swallow the graph? | Threshold-triggered **structuring nudge**. An offer, never a requirement |
| **4** | Should concepts be global or project-local? | **Neither — scope follows provenance.** Curated concepts are global; extracted ones start local and get promoted on a second appearance |
| **5** | Should `Claim` be three separate types? | **No — the kind is derived from structure**, never stored. A claim with no support is a hypothesis; that's readable off the graph |
| **6** | ⚠️ Is the evidence-damping curve right? | Wrong twice over. `sqrt`, not `log₂` — **and the real error was upstream**: distinct sources aren't independent sources (§4.4) |
| **7** | Is the graph the right primary artifact? | **Graph as engine, map as secondary view.** Lead with ranked answers, not a diagram |
| **8** | ⚠️ Does the Disagreement Engine fire often enough? | **No — the original trigger would have caught 2 of 8–12 real cases.** Widened to six kinds with priority computed separately (§7.4) |
| **9** | ⚠️ Will calibration actually improve? | The measurement was confounded by **difficulty drift**. Switched to a reliability curve and pre-registered the null (§11.1) |
| **10** | Is the concept skeleton at the right granularity? | **Structurally fine; `verify` is the real gap** — §14.2 |
| **11** | Will SQLite + in-process hold at 10⁴ nodes? | **Yes, by a factor of ~100** (§12.1) |
| **12** | Is six node types right? | Yes. `Method` becomes a kind of `Artifact` — and it caught an evidence bug (§4.4) |

## 13.1 ⭐ The last two are the most instructive

Both had been filed as *"needs a later phase."* Both took **under an hour.** Doubt 11 was answered by writing the load test we'd been deferring; doubt 10 by writing the CI validator this design had *specified since day one and never run* — which immediately found six real defects, including that the document claimed **187 concepts when there are 213**.

> ⭐ **They weren't hard questions. They were unrun measurements.**

Worth internalising as a habit, because it will happen again.

## 13.2 ⚠️ And a mistake inside the fix — the best example in this document

The validator found 34 redundant prerequisite edges — `A → C` where `A → B → C` already exists. The obvious move is to delete all 34. **We nearly did.** Then we checked what the redundancy actually was:

> `fft requires complex_numbers` is redundant — but **only via `impedance → ac_analysis → frequency_response → sampling_theorem`.**

Delete it and a CS student who knows complex numbers but has never done circuits is told the FFT is **blocked on electrical material they don't need.** The direct edge is load-bearing *precisely because* the implied path detours through another domain.

⭐ So the validator splits redundancies by domain: same or adjacent → dropped (26, applied); crossing three or more → **flagged and kept** (8).

**A blind, technically-correct transitive reduction would have quietly damaged the learning path for exactly the interdisciplinary students this product exists for** — the failure the check was supposed to prevent.

---

# 14. What is still genuinely unknown

Being explicit about this is the point of §13 existing.

## 14.1 Needs real users, not more thinking

**Retrieval weights** — defaults set, tuned from click data in weeks 2–4. **Real cost** — instrumented from turn one. **Whether an `AMBIGUOUS`-only queue gets cleared** — ⭐ if it doesn't, the signal isn't volume, it's that students don't value the question, which is far more serious.

## 14.2 Needs domain expertise — the one concrete ask

**86% of the 213 concepts have no `verify` statement** — the field that says *what would count as knowing this*. It's the seed for an Artifact's `predicted`, so without it the frontier can name what to learn next but not what would demonstrate having learned it.

Coverage is worst exactly where it should be best: **0% in maths, 0% in digital, 0% in hardware.**

> ⭐ **The ask is deliberately small: write `verify` for the ~50 concepts on the biosensor path.** Not "review 213 concepts" — an unbounded review returns nothing.
>
> **A `verify` statement is one line saying what would demonstrate the concept**, e.g. `rc_circuit → "predict settling time and confirm on a scope"` · `decoupling → "show supply ripple before and after adding decoupling"` · `voltage_divider → "design a divider for a target voltage and measure the error"`. Those three are real entries from the skeleton — the other ~184 are blank.
>
> **And the granularity judgement arrives as a side effect**, because you cannot write *"predict settling time and confirm on a scope"* for something that isn't about an afternoon of work. The task tests the property by requiring it, rather than asking for an opinion about it.

## 14.3 Frontend and strategy

Eleven open doubts in `Frontend/04`; **one blocks UI work** — do six desaturated colours still separate under colour-blindness at small sizes? Half a day to test; if it fails we collapse to four or five node types.

Strategically open, and not ours alone to settle: the data-flywheel consent and IP terms (**explicit and student-favourable from user one**, never retrofitted), the B2B thesis, and the one-paragraph problem statement.

---

# 15. Status and what happens next

| | |
|---|---|
| **Design** | complete. Twelve of twelve open questions closed |
| **Code** | **none.** Zero lines of production code exist |
| **Next action** | **Phase 0** — the ledger, the projector, the retraction cascade, and the tests that prove they're trustworthy |
| **Phase 0 needs** | no accounts, no API keys, no models. ~1–2 days |

⭐ **Why Phase 0 is so narrow.** Everything downstream — retrieval, frontier, agents, UI — is a **pure function of a correct graph.** If replay isn't deterministic and retraction doesn't cascade, **every bug you find later will be misdiagnosed as a bug in the layer you happen to be looking at.** So Phase 0 ships with a test that replays a frozen ledger and asserts the graph hash is identical, forever.

**After that:** extraction → retrieval and frontier → the agent layer and the tiering experiment → the frontend. Weeks, not months, because the design work is done.

---

# 16. Why this is different

Not "better" — **structurally different**, in ways a competitor cannot copy without changing what they are.

> ⚠️ **Read this table honestly: the Nexus column is a *design*, not a shipped product.** The other three are real software you can use today. Every ✅ on our side is a commitment we intend to meet, and every one of them is unproven until Phase 0 ships. The table is here to show *where the gap is*, not to claim we've already closed it.

| | Atlas | Obsidian | Graphify | **Nexus** *(designed)* |
|---|---|---|---|---|
| Holds papers | ✅ | as attachments | ✅ — PDF, and pulls arXiv directly | ✅ |
| Holds your notes | ✅ | ✅ | ✅ — `.md`, Office, Google Docs | ✅ |
| Holds your code | ❌ | as plain text | ✅ — AST, 0 tokens | ✅ |
| ⭐ **Holds what you built and measured** | ❌ | ❌ | ❌ | ✅ |
| **Records whether it worked** | ❌ | ❌ | partial — on *answers*, via `reflect` | ✅ on **artifacts** |
| **Remembers what failed** | ❌ | ❌ | ✅ — `dead_end`, time-decayed | ✅ + `resurrect_if` triggers |
| **Suggests what to do next** | ❌ | community plugin only | ✅ — from graph deficiencies | ✅ from **prerequisites + outcomes** |
| Survives changing your mind | ❌ | file history only | partial — `corrected` + decay | ✅ supersession + retraction cascade |

⭐ **One row is untouched by all three, and everything else descends from it.** Only Nexus has a place for *the thing you built and the number you measured* — which our Atlas teardown puts bluntly: that node type is **"a category Atlas cannot enter without becoming a different product."**

**And the rows where Graphify is strong are good news, not bad.** Dead-end memory and outcome-weighted confidence are not speculative — **a 103k-star project already shipped them and they work.** What nobody has done is attach those mechanisms to a **build loop** instead of a Q&A loop. That's a much better position to be in than claiming to have invented the mechanism.

⭐ **And it compounds.** A note-taking app is equally useful in month one and month twelve. This one is most useful in week six of the *second* project — because that's when it can say *"you tried this before, here's why it failed, and here's what changed."*

---

# 17. Glossary

| Term | Plain meaning |
|---|---|
| **Ledger** | the append-only log of everything that happened. The truth |
| **Projector** | the code that turns the ledger into a graph. Must be perfectly repeatable |
| **Sidecar** | anything computed from the graph and safe to throw away |
| **Hyperedge** | one relationship connecting more than two things |
| **Artifact** | something the student made or ran. Carries predicted / measured / agreement |
| **Frontier / outer fringe** | what you're ready to learn or do next, computed rather than declared (from Knowledge Space Theory) |
| **Phantom node** | a concept that exists only because something pointed at it |
| **Retraction cascade** | withdrawing a belief and following what depended on it |
| **Supersession** | replacing a belief while keeping the old one, linked |
| **Bitemporal** | tracking *when it was true* separately from *when we learned it* |
| **Entity resolution** | deciding whether two names refer to the same thing |
| **Crypto-shredding** | erasing data by destroying its encryption key |
| **Capability** | a permission granted to an AI call — what it may read and assert |
| **Context isolation** | each AI call is a fresh request, never a turn in a running chat |
| **Calibration** | how well your stated confidence matches how often you're right |
| **DOI** | Degree of Interest — the ranking function |

---

# 18. Where to go deeper

| Document | Read it if you want |
|---|---|
| `Backend/01` Design | the full architecture with every tradeoff named |
| `Backend/02` Implementation Spec | actual code — schema, projector, cascade, tests |
| `Backend/03` Extraction Contract | the exact prompt, validator and quarantine rules |
| `Backend/04` Concept Skeleton | the 213 concepts. ⭐ **This is the one that needs domain review** |
| `Backend/05` Agent Contract | permissions, model tiering, the full execution map |
| `Backend/06` Evaluation | the metrics and the pre-registered nulls |
| `Backend/07` Operational Contracts | cold start, schema evolution, auth, cost |
| `Backend/09` Uncertainty Register | ⭐ **all twelve doubts with full reasoning** |
| `Backend/10` Build Plan | phases and timeline |
| `Frontend/01–06` | the interface design and its own eleven doubts |
| `Research/01–07` | the teardowns everything above came from |
| `tools/` | the skeleton validator and the load test |

---

# 💡 The smallest version that would already be worth using

Strip everything speculative and what remains is:

> **A student writes what they think will happen. They build it. They record what actually happened. The system remembers — including the failures — and tells them what to do next.**

That is buildable in about three weeks. **Everything else in this document makes it better; nothing else makes it work.**

If the design ever needs cutting, that paragraph is what survives.

# Start Here — The Mind Graph in Plain English

**Backend / 00.** What the Mind Graph is, how it works, and how to read the rest.
**Written for a first read.** No prior documents needed. Everything technical is explained.
**Date:** 2026-08-09

---

# 1. What problem it solves

A student has an idea. Over six weeks they read papers, write firmware, take measurements, get confused, change their mind, and — if it goes well — end up with something that works.

Right now, all of that lives in three places: their head, a chat history that forgets, and a folder of files. **Nothing connects.** The measurement they took in week 2 doesn't know it contradicts the paper they read in week 5. The concept they gave up on in week 3 gets suggested again in week 6.

The Mind Graph is the thing that connects them. It's a **record of what the student believes, what they've built, and how those two relate** — that survives between sessions and gets richer as the project goes.

**The one-line version:**

> Atlas maps what the literature says. Obsidian maps what you wrote. **Nexus maps what you built, whether it worked, and what to do next.**

---

# 2. The core idea, in three layers

Almost every design decision follows from this one picture:

```
   ┌───────────────────────────────────────────────┐
   │  THE LEDGER                                    │
   │  A list of everything that ever happened,      │
   │  in order, that we never edit or delete.       │
   │                                                │
   │  "student uploaded a datasheet"                │
   │  "system proposed 4 new concepts"              │
   │  "student accepted 3, rejected 1"              │
   │  "student measured 47.2 kΩ"                    │
   └───────────────────────────────────────────────┘
                        │
                        │  we replay the list to build...
                        ▼
   ┌───────────────────────────────────────────────┐
   │  THE GRAPH                                     │
   │  The current picture: concepts, claims,        │
   │  measurements, and how they connect.           │
   │                                                │
   │  Throw it away and rebuild it any time.        │
   └───────────────────────────────────────────────┘
                        │
                        ▼
   ┌───────────────────────────────────────────────┐
   │  SIDECARS                                      │
   │  Calculated extras: what's important, what's   │
   │  connected to what, what you've looked at.     │
   │  Recomputed whenever we like.                  │
   └───────────────────────────────────────────────┘
```

**Why this matters, in one sentence each:**

- **The ledger is never edited**, so you can always answer *"what did I believe in week 2, and why did I change my mind?"*
- **The graph is rebuildable**, so if something goes wrong — a bad import, a wrong merge — we fix the recipe and rebuild, rather than surgically repairing a broken database.
- **Because the graph is disposable, the database choice barely matters.** If we pick the wrong one we swap it in an afternoon. Very little else in software is that reversible.

---

# 3. What's in the graph

## Six kinds of node

| | What it is | Example |
|---|---|---|
| **Concept** | a thing you can know | `I²C`, `PID control` |
| **Question** | something unresolved. *The project itself is one* | *"Can skin impedance track hydration?"* |
| **Claim** | a statement that could be true or false | *"47 kΩ means hydrated"* |
| ⭐ **Artifact** | **something you made or ran** | a firmware build, a circuit, a measurement |
| **Source** | something external | a paper, a datasheet, a lecture |
| **Note** | your own writing, unstructured | *"the 5V rail felt noisy?"* |

**Two of these are doing special work:**

**`Artifact` is why this is different from everything else.** Atlas, Obsidian, and every research tool can hold papers and notes. None of them has a place to put *the thing you built and the number you measured*. That's the whole differentiator, and it's one node type.

**`Note` is the escape hatch, and it's not optional.** There's strong evidence that people simply won't fill in structured forms — they abandon the tool or fill it in badly. So you can always just write, and the system *offers* structure later. The student never picks a node type. Ever.

## Edges — and one important choice

Nodes connect with typed links: `supports`, `contradicts`, `requires`, `measured_by`, `cites`, and about a dozen more.

**The important choice:** *"these two things disagree"* is an **edge**, not a node. That means disagreements are countable, rankable, and resolvable — rather than just being a red dot on a diagram. Section 6 is built entirely on this.

## Every link carries how sure we are

| | Meaning |
|---|---|
| `EXTRACTED` | it says this, right here, in this document. Certain |
| `INFERRED` | the system worked it out. Five confidence levels, no others allowed |
| `AMBIGUOUS` | genuinely unclear — **flagged, never thrown away** |

Why the fixed levels: when you ask an AI for a confidence between 0 and 1, it returns 0.5 or 0.9 and nothing else. Give it five defined rungs and it actually discriminates. That's a measured result, not a preference.

---

# 4. How things get in — and why there's a gate

```
a file arrives
   ↓
route it       PDF? image? code? Each gets handled differently
   ↓
seen it?       identical file → skip entirely
   ↓
extract        AI reads it, must use our fixed vocabulary
   ↓
check          code validates the output; anything odd is quarantined
   ↓
is this new?   "PPG" and "photoplethysmography" are the same thing
   ↓
PROPOSE        ← nothing is in the graph yet
   ↓
   ├─ certain, with a quoted passage  → accepted automatically
   └─ anything less                    → you review it
```

**Why the gate exists:** about **1.5–1.9% of what an AI extracts is invented.** On a graph with 5,000 links that's roughly 75–95 fabricated facts — and because they're stored as structure, everything downstream treats them as verified. A wrong search result is obviously wrong. A wrong *link* is invisible.

⚠️ **This is also my biggest worry about the design.** It assumes you'll actually do the reviewing. See `Backend/09` Q1.

---

# 5. How things come out

```
you ask a question
   ↓
find a few starting points     (meaning-based + word-based search)
   ↓
walk outward from them          (following the links, weighted)
   ↓
rank what you found             (see below)
   ↓
keep about 50                   ← hard limit, and it's not arbitrary
```

**Why 50:** a controlled experiment — with EEG and pupil measurement — found people **can't reliably use a node diagram beyond about 50 nodes.** Past that, measured mental effort actually *drops*, because participants give up.

The software doesn't struggle until about 25,000 nodes. **So the display becomes useless roughly 250× before it becomes slow** — which means almost every instinct to "make the graph faster" is solving the wrong problem.

**The ranking is the actual product.** If only fifty things fit on screen, choosing *which* fifty is the most valuable calculation in the system:

```
importance  =  how connected it is
            +  how recently you touched it
            +  whether things built on it worked
            +  how sure we are
            +  whether you're ready for it now
            −  whether it's gone stale
```

minus how far it is from what you're currently doing — where "far" can be re-weighted by a lens, so *"show me this project as a power problem"* rearranges everything without deleting anything.

---

# 6. The two things that make it a mentor rather than a filing cabinet

## Gaps — what you don't know yet

If something points at a concept and nothing has ever validated it, that concept exists in the graph as a **hollow node**. Nobody *decided* it was a gap; the gap simply exists because something referred to it and nothing filled it.

Then: which gaps can you actually tackle *now*? A gap whose prerequisites you've already met is reachable. One whose prerequisites you haven't isn't. That's a 40-year-old piece of mathematics (Knowledge Space Theory) and it's what powers "learn this next."

**Plus two things that stop it being annoying:**
- **Dead ends.** If you tried something and abandoned it, it stops being suggested. Nothing destroys trust in a recommender faster than re-suggesting the thing that wasted your Tuesday.
- **Resurrection.** If the reason it failed later changes, it comes back — *"you tried this before it was possible; the blocker has gone."*

## ⭐ Tensions — when things disagree

This is the feature I'd put at the centre of the product.

The graph holds three kinds of claim, and it knows which is which:

- what **a paper** says
- what **you believe**
- what **your bench measured**

**When those disagree, that's the most valuable moment in any research project** — and no other tool can see it, because no other tool holds all three.

A contradiction between a paper and your own measurement is exactly one of three things, and the system can work out which:

| What it looks like | What it probably means |
|---|---|
| one measurement, low confidence, solid paper | **you made a mistake** → measure again |
| two solid measurements, paper was about different conditions | **the paper doesn't apply here** → that's a real finding |
| two solid measurements, solid paper, same conditions | ⭐ **you might have something** → tell someone |

> **Nexus tells you when your bench disagrees with the literature — and whether that means you're wrong, the paper doesn't apply, or you've found something.**

⚠️ **My worry:** it needs both a solid paper claim *and* a repeated measurement on the same question. That might be rare early on. See `Backend/09` Q8 — and it's checkable in an afternoon.

---

# 7. Changing your mind

The part most systems get wrong.

Say you measured something, concluded something from it, and then realise the measurement was bad — a loose electrode.

```
you retract the measurement
   ↓
it's marked deprecated — NOT deleted, still in the history
   ↓
the system follows what depended on it
   ↓
the conclusion becomes UNSUPPORTED
```

**The subtlety that matters:** the conclusion doesn't become *false*. It becomes **unsupported** — it might still be true, you just no longer have a reason to believe it. Those are different, and a system that deletes conclusions when evidence is withdrawn will quietly destroy things that were right.

And a conclusion only loses support when its **last** remaining evidence goes. Retract one of five measurements and it stands.

**Nothing is ever deleted**, which is what makes *"what did I think in week 2?"* answerable.

*(Deleting your account is the exception — and it works by destroying the encryption key rather than the records, so the shape of the graph survives while the content becomes unreadable.)*

---

# 8. Where the AI sits

**AI agents can read the graph and suggest changes. They cannot change it.**

Two rules that make everything else safe:

1. **Agents propose; a gate decides.** No path exists from a model's output straight into the graph.
2. **Agents can never record an outcome.** Only you can say what you measured. If an AI could write *"this worked"*, the record of what actually worked becomes fiction — and that record is the most valuable thing we have.

There's a neat consequence of the ledger design: **AI is unpredictable, but the system stays reproducible**, because we save what the AI *said* and replay the saved version. Rebuild the graph a year later with a different model and you get exactly the same result.

---

# 9. How to read the rest

**In this order:**

| | Doc | Why | Time |
|---|---|---|---|
| 1 | **this document** | the whole picture | — |
| 2 | **`09_Uncertainty_Register`** | the twelve things I'm not sure about, and the alternatives I rejected | 20 min |
| 3 | **`01_Backend_Design_Draft`** | the real architecture. Everything here, in detail, with the reasoning | 45 min |
| 4 | **`10_Build_Plan`** | how we actually build it, phase by phase | 20 min |
| 5 | **`02_Implementation_Spec`** | the code. Read only if you want to check the reasoning | — |
| 6 | 03, 04, 05, 06, 07 | reference — read when you need them | — |
| 7 | `08_Design_Revisions` | history: an audit I ran on my own design and the eleven things it caught | — |

**While reading 01–07, you'll hit boxes like this:**

> ### ❓ OPEN QUESTION — Q4
> …a thing I'm unsure about, right where it's relevant.

Those are the twelve entries from `09`, placed at the exact section they concern. **When you hit one, that's a place to tell me what you think.**

**Your annotation scheme:** 🔵 want to use · 🟢 like it, don't know how to build it · 🟡 disagree. Don't over-blue — the yellows and greens are the useful signal.

---

# 10. Honest status

| | |
|---|---|
| **Designed** | ✅ everything above |
| **Built** | ❌ **nothing.** Zero lines of production code |
| **Next** | Phase 0 — the ledger and the replay machinery, ~1–2 days |
| **To something that runs** | ~5 weeks |
| **To something proven to help anyone** | ~3 months, because that part needs a real student and a real project |

**The single most important thing to understand:** everything in these documents is a **proposal**. It's my best judgement from six research teardowns, and I've flagged twelve places where I could be wrong. Where you disagree, say so — that's more useful than agreement.

---

# 💡 Visionary Vector — the smallest version of this that would already be worth using

Everything above describes the full system. But there's a much smaller thing hiding inside it that would be useful **on its own, in week one**, and it's worth naming because it de-risks everything else.

Strip away the graph, the AI, the retrieval, the frontier. Keep exactly one loop:

```
before you build:   write down what you expect to happen, and how sure you are
after you build:    write down what actually happened
```

That's the Artifact node, and nothing else. A command-line tool, two days of work, no AI involved.

Do that for six weeks and you can compute something no student has ever been shown about themselves: **how accurate their engineering intuition actually is, and whether it's improving.** Not what they know — whether their predictions survive contact with hardware. Which is close to the real definition of engineering skill, and is invisible to every grade, transcript, and résumé line that currently exists.

Everything else in this design — the graph, the retrieval, the disagreement detection — exists to make that loop *easier and smarter*. But the loop is the thing that has value. And it's testable in week one, with one student, before a single graph node is drawn.

**If that loop doesn't feel valuable to a real student in two weeks, the rest of this document is an expensive way to be wrong** — which is exactly why the build plan puts it second, before the ingestion pipeline and long before anything visual.

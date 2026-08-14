# Nexus — Integration Guide

For anyone joining the build. Read this before touching code.

---

## What the Mind Graph is

The Mind Graph is the structured memory system for both the project and the builder.

Inspired by graph-based research and knowledge environments, it represents the project as an evolving network of concepts, requirements, assumptions, design decisions, artifacts, experiments, results, dependencies, evidence, and unresolved questions — while preserving the relationships and provenance between them.

Alongside the project graph, Nexus builds a representation of the student's knowledge: what concepts they understand, their level of mastery, relevant prior experience, knowledge gaps, and how that understanding changes throughout the project. This allows Nexus to reason simultaneously about what the project requires and what the builder currently knows, enabling personalized learning and technically coherent long-term project memory.

Everything below exists in service of that.

---

## System status

| | State |
|---|---|
| Backend | 342 tests passing. All 22 API routes live. |
| Frontend | Typechecks clean, builds clean, conformance green. |
| Uncertainty register | 23 total doubts across both registers — 20 closed, 3 open (watch-only, non-blocking). |
| Repo | `mind-graph/Backend_build`, `mind-graph/Frontend_build`. Design docs in `mind-graph/_src`. |

Nothing below is a "coming soon" — it is either shipped or explicitly marked open.

---

## Architecture, in one pass

```
Ledger (append-only event log, the source of truth)
   ↓ projector
Graph (materialised state: nodes, edges, confidence, support)
   ↓
Sidecars (derived, disposable: rankings, embeddings, vectors)
```

- **Ledger** — every action is an event. Nothing is ever mutated in place; corrections and retractions are new events, not edits. This is what makes the record verifiable (`log`/`Share` routes replay it and check a hash chain).
- **Graph** — the current materialised state, six node types (`Concept`, `Question`, `Claim`, `Note`, `Artifact`, `Source`), typed edges (`supports`, `contradicts`, `requires`, `measured_by`, …).
- **Sidecars** — rankings, embeddings, the portable payload. Computed, cached, and safe to throw away and recompute.

**One graph, two runtimes.** Ranking (Degree-of-Interest) is computed once in Python and shipped to the client as components; the client does a ten-line weighted sum to re-rank offline. A conformance test (`npm run conformance`) pins both runtimes to identical output — if you touch ranking math on either side, run it.

---

## Model tiers

| Tier | Model | Used for |
|---|---|---|
| T0 | none (deterministic) | retrieval, ranking, frontier, graph traversal — no model call |
| T1a | open-source (Together/Fireworks/Groq, default `Llama-3.3-70B`) | high-volume extraction, routine capture routing |
| T1b | Haiku | classification, cheap structured tasks |
| T2 | Sonnet | grounding, most agent roles |
| T3 | Opus | planning and synthesis on hard/escalated turns only |

Capability-bound, not developer-chosen at call time — each role (`grounder`, `critic`, `planner`, `synthesiser`) has a fixed tier and a fixed capability set, enforced server-side. A client cannot request a higher tier by asking.

`ask`/`turn` is the only route that needs a model. Everything else — including the whole Bench, Map, Log, Share, and predict/measure loop — is deterministic and works with **no API key configured**. Set `MG_ENDPOINT` + `MG_API_KEY` to enable it; without them the route returns a clean `503`, not a broken feature.

---

## Design tokens

### Colour — four families, not six

Six colours failed our accessibility gate (F4): two node types were indistinguishable under colour-vision deficiency. The fix — **type is carried by hue AND glyph together**, never hue alone. This is what lets the palette be chosen for how the graph looks rather than purely for what survives a colour-blindness simulator.

| Family | Hex | Node types | Glyph |
|---|---|---|---|
| `lattice` | `#7BF4FC` | Concept, Question | ◆ / ? |
| `thinking` | `#BB99FA` | Claim, Note | ▲ / · |
| `yours` | `#E5C14A` | Artifact | ■ |
| `outside` | `#B79400` | Source | ▪ |

Colour = **type family**. Never use colour for project identity — that's carried by graph position. Do not introduce a fifth colour without re-running the accessibility gate (`Frontend_build/scripts/f4_gate.py`).

### The "pre-registration" framing

The predict → lock → measure loop is described, in copy and UI, as **pre-registration** — the same concept used in clinical trials and psychology research: declare your prediction before you see the result, so the record can't be quietly rewritten afterward.

Use this term consistently in UI strings, onboarding copy, and positioning. It is now the canonical name for that mechanism — don't invent a second one.

---

## What's stable vs. what's still moving

**Stable — build against this now:**
- Ledger/graph/sidecar architecture
- All 22 API routes, capability model, token bundles
- Six node types, edge vocabulary
- Colour system and glyphs (above)
- Predict/measure/pre-registration loop
- Log, Share (with export), Map, Dashboard, Bench

**Still open — non-blocking, but don't hard-code around these:**
- F2 (dashboard layout), F5 (spatial clustering), F10 (animation timing) — shipped implementations, want real-usage confirmation before being called final
- The external verifier for calibration-as-credential (visionary vector ⑤) — shape not decided
- Extraction accuracy, cost envelope, retrieval baseline — all currently measured against synthetic data, not real student work

---

## What's blocked on Aryav (not on you)

These don't block integration — they block a handful of downstream experiments. Listed so nobody waits on them by accident.

1. Model API endpoint + key
2. 10–20 real project files (for extraction testing)
3. ~50 falsifiable `verify` statements from a domain teammate
4. One observation: does browsing the graph suffice at 1am, or does it need to surface unprompted
5. Consent/IP terms for the data flywheel, B2B thesis

None of these gate your work. Build against the stable list above.

---

## Where to start

- Read `_src/B00_Start_Here.md` and `_src/F05_Summary.md` for full design rationale.
- Backend routes: `Backend_build/mindgraph/api.py`.
- Frontend surfaces: `Frontend_build/src/components/`.
- Run the test suite (`pytest` in `Backend_build`) and conformance check (`npm run conformance` in `Frontend_build`) before any PR.

# Mind Graph — Extraction Contract

**Companion to `08` (architecture) and `09` (implementation).**
**Scope:** how raw input becomes candidate nodes and edges. The prompt, the validators, the quarantine rules, and the metric that tells us whether it's working.
**Date:** 2026-08-07

> **Why this is the highest-risk component.** Measured hallucination rates for LLM triple extraction run **1.5–1.9%** (05 §1.1). On a 5,000-edge student graph that's 75–95 fabricated relationships, structurally encoded so everything downstream treats them as fact. Schema drift and entity fragmentation compound from the same place. **Every failure mode in report 05 is born here.** A week spent on this document saves months of graph rot.

---

# 1. Design rules

| # | Rule | Consequence if broken |
|---|---|---|
| 1 | **The ontology goes IN the prompt, and is re-checked in code** | schema drift (Atlas's "labels vary by generation model") |
| 2 | **Deterministic paths never touch an LLM** | wasted money, worse results, non-reproducibility |
| 3 | **Prose is never a node label** | the graph becomes a transcript with edges |
| 4 | **IDs are deterministic from content, never from position** | ghost duplicates on every re-run |
| 5 | **Confidence is a discrete rung, never a continuous guess** | bimodal collapse to 0.5/0.9 (measured) |
| 6 | **AMBIGUOUS is emitted, never suppressed** | uncertainty silently becomes fact |
| 7 | **Extraction proposes; it never commits** | no human gate on a 2% fabrication rate |
| 8 | **Every claim carries a source span** | provenance can't be reconstructed later |

---

# 2. Routing — what gets extracted how

```
INPUT
 ├─ code (.py .c .cpp .ino .rs …)      → AST (tree-sitter)        0 tokens  EXTRACTED
 ├─ structured measurement (CSV/JSON)  → direct parse             0 tokens  EXTRACTED
 ├─ serial/scope log                   → parser + heuristics      0 tokens  EXTRACTED
 ├─ git history                        → direct parse             0 tokens  EXTRACTED
 ├─ transcript / audio                 → whisper → semantic pass  local+LLM
 ├─ paper / datasheet (PDF)            → chunk → semantic pass    LLM
 ├─ image / whiteboard / breadboard    → vision pass              LLM
 └─ chat / notes                       → semantic pass            LLM
```

**The deterministic lane is the default, not the fallback.** For an embedded project, a large share of the graph — files, functions, calls, commits, pin assignments, measured values — arrives with `confidence: EXTRACTED, score: 1.0` and never meets a model. That is a cost advantage and a trust advantage simultaneously.

## 2.1 ⭐ Which model runs the semantic lane — **Tier 1a, our own** *(added 2026-08-10, Backend/09 Q2)*

Every `LLM` row above runs on the **self-hosted / OSS-endpoint model**, not a hosted frontier model.

**The justification is this document.** §4 validates every field in code, §4.1 quarantines anything that fails, and §5 routes the survivors. **Extraction output was never trusted** — which is precisely the condition under which a small model is safe. The failure mode a 7–14B model introduces is *worse content*, which quarantine already handles, not *unsafe content*.

⭐ **Serve it with grammar-constrained decoding** (XGrammar / outlines under vLLM), so the JSON schema in §3 is enforced **at decode time** rather than checked after generation. Malformed output stops being possible, and §4's schema checks become a second line rather than the first.

**This is the single largest cost line in the system** — a project ingests ~300–600k tokens of source material, all of it chunked, embedded and extracted. Moving it off a hosted frontier model takes it from roughly a third of the bill to cents (`Backend/07 §6.2a`).

**Two things that do *not* move to Tier 1a:**

| | Tier | Why |
|---|---|---|
| **quarantine triage** — *why did this chunk fail?* | **1b — Haiku** | low volume, and it writes prose a human reads |
| **vision pass** (§3.1) | **Sonnet** | image grounding is materially weaker in small open models, and a misread scope trace is not caught by any schema check |

> ⚠️ **The metric that guards this decision is the quarantine rate (§7).** Constrained decoding guarantees shape, never content. If quarantine rises materially against the hosted-model baseline, the model is too small — and that is a config change, not a redesign.

---

# 3. The extraction prompt

Substitute `{{ }}` at call time. Emit **only** JSON.

````text
You are a Mind Graph extraction worker. Read the provided material and emit a
knowledge-graph fragment as JSON. Output ONLY valid JSON — no prose, no markdown
fences, no preamble.

MATERIAL
  project:   {{PROJECT_TITLE}}
  question:  {{PROJECT_QUESTION}}          # the project's driving question
  chunk:     {{CHUNK_INDEX}} of {{CHUNK_TOTAL}}
  file:      {{SOURCE_PATH}}
  known concepts already in this graph (use these ids if you mean these things):
{{KNOWN_CONCEPTS}}                          # id · label · aliases, top 200 by relevance

────────────────────────── NODE TYPES ──────────────────────────
Exactly six. Any other value is invalid and the fragment will be rejected.

Concept   a unit of knowledge that exists independently of this project.
          "I2C", "PID control", "electrochemical impedance spectroscopy".
          NOT project-specific. NOT an assertion. NOT a task.
          kind: null

Question  an open problem. May be the project itself or a sub-question.
          "Can skin impedance track hydration?"  "Why does the ADC saturate?"
          kind: project | investigation | blocker

Claim     an assertion whose truth could change.
          ⭐ `kind` here is a HINT ONLY. The system derives the real value from
             graph structure after resolution (Backend/01 §3.2a). Give your best
             guess; it is recorded as provenance, never as truth.
          kind: observation  — something seen/measured/read
                              "the ADC saturates above 3.1 V"
                conclusion   — something inferred from observations
                              "the 5V rail is unsuitable for this sensor"
                hypothesis   — something proposed but untested
                              "impedance at 50 kHz should track hydration"

Artifact  something the author MADE or RAN. This is the highest-value type;
          never miss one.
          kind: code | circuit | run | measurement | document
          If the material describes building, testing, measuring, or running
          anything, that is an Artifact.

Source    external evidence. kind: paper | datasheet | video | course | web

Note      author prose that is genuinely unstructured and does not fit above.
          Use this rather than inventing a node type. It is not a failure.

────────────────────────── RELATIONS ──────────────────────────
Exactly these. Any other value is invalid.

  contains, part_of
  supports, contradicts, refutes, confirms, extends
  evidence_for, measured_by, cites, uses_method_in
  requires, relates_to, same_as
  answers, raises, supersedes, derived_from

DIRECTION RULES — violating these produces a wrong graph, not a noisy one:
  A --supports--> B          A is the evidence, B is the thing supported
  A --evidence_for--> B      A is an Artifact/Source, B is a Claim
  A --requires--> B          A cannot be understood until B is understood.
                             ONLY between two Concept nodes. Never anything else.
  A --answers--> B           A is a Claim, B is a Question
  A --raises--> B            A raised B. B is a Question.
  A --measured_by--> B       A is a Claim, B is the Artifact that measured it
  A --contradicts--> B       symmetric in meaning; emit ONE direction only,
                             from the newer/more specific to the older/general

────────────────────────── CONFIDENCE ──────────────────────────
Every edge needs `confidence` and `score`. Pick a score from THIS LIST ONLY.
Do not interpolate. Do not use 0.5. If nothing fits, mark it AMBIGUOUS.

EXTRACTED  1.0    stated explicitly in the material. A citation, a measured
                  value, an import, "as shown in section 3", "we used X".

INFERRED   0.95   direct structural evidence — a named cross-reference, an
                  explicitly shared quantity, same variable in both places
           0.85   strong inference — clear functional alignment, unambiguous
                  from context, but not spelled out
           0.75   reasonable inference — same problem domain, similar shape,
                  requires interpretation
           0.65   weak inference — thematically related, no structural evidence
           0.55   speculative but plausible — surface co-occurrence only

AMBIGUOUS  0.3    likely real, cannot determine direction or endpoints
           0.2    something is here but the material is unclear
           0.1    flagged for a human because it might matter

NEVER omit an uncertain relationship. AMBIGUOUS edges are surfaced for review,
not discarded. A missed contradiction is worse than a flagged guess.

────────────────────────── WHAT IS NOT A NODE ──────────────────────────
This is the most common failure. Read it twice.

A node label is a NAME, not a SENTENCE.

  ✗ "the sensor was too noisy at 5V so we switched to 3.3V"
  ✓ Claim(kind=observation, label="ADC noise at 5V rail")
     with body carrying the full sentence

  ✗ Concept("we should probably use a lower rail voltage")
  ✓ Note(label="rail voltage decision", body="we should probably…")

Rules:
  - A label is < 60 characters and contains no finite verb phrase.
  - Reasoning, rationale, caveats, and justification go in `body`, never
    into a new node.
  - If it reads like something a person said, it is a Note or a body.
  - If you cannot name it in a noun phrase, it is not a Concept.

────────────────────────── ID RULES ──────────────────────────
  - If the entity matches a KNOWN CONCEPT above, reuse that exact id.
  - Otherwise emit `id: null` and a `key`: a lowercase, [a-z0-9_] slug of the
    canonical name. The resolver assigns the UUID.
  - The same entity must produce the same `key` in every chunk.
  - NEVER append chunk numbers, indices, or suffixes to a key.
  - Emit `aliases` for every surface form you saw for the same thing
    ("I2C", "I²C", "IIC", "TWI"). This is how duplicates get merged later.

────────────────────────── SOURCE SPANS ──────────────────────────
Every node and edge carries `span`: {file, start, end} where start/end are
character offsets, or {file, page} for PDFs, or {file, t_start, t_end} for
audio/video. If you cannot locate it, set span to null and drop confidence
one rung. Never invent a span.

────────────────────────── ARTIFACTS AND OUTCOMES ──────────────────────────
When the material describes something built, run, or measured, populate:

  "predicted": {quantity, value, unit, range}   what was expected BEFOREHAND
  "measured":  {quantity, value, unit}          what actually happened
  "agreement": "matched" | "diverged" | "inconclusive" | "not_run"

If a prediction is stated but no measurement, agreement = "not_run".
If a measurement exists with no prior prediction, leave predicted null and
set agreement = "inconclusive". NEVER back-fill a prediction from the result.

────────────────────────── HYPEREDGES ──────────────────────────
If 3+ nodes jointly support or jointly contradict one thing — and the pairwise
edges would lose that — emit a hyperedge. Maximum 3 per chunk. Use sparingly.

────────────────────────── OUTPUT SCHEMA ──────────────────────────
{
 "nodes":[{"id":null,"key":"i2c","type":"Concept","kind":null,
           "label":"I2C","aliases":["I²C","IIC","TWI"],"body":null,
           "span":{"file":"...","start":0,"end":0}}],
 "edges":[{"src_key":"adc_saturation","dst_key":"rail_5v_unsuitable",
           "relation":"supports","confidence":"INFERRED","score":0.85,
           "justification_keys":["scope_trace_run"],
           "span":{"file":"...","start":0,"end":0}}],
 "hyperedges":[{"relation":"jointly_support","member_keys":["a","b","c"],
                "target_key":"d","confidence":"INFERRED","score":0.75}],
 "unresolved":[{"text":"...","why":"could not determine endpoints"}]
}

`unresolved` is where you put things you noticed but could not confidently
structure. It is read by a human. Using it is correct behaviour, not failure.
````

## 3.1 Vision addendum (images)

Appended when the chunk is an image:

```text
This is an image. Understand what it IS, do not merely OCR it.
  breadboard / circuit photo → components, connections, likely Artifact(circuit)
  scope trace / plot         → what is measured, the axes, the reading,
                               likely Artifact(measurement) + Claim(observation)
  whiteboard / handwriting   → ideas and arrows. Mark uncertain readings
                               AMBIGUOUS. Never guess at unclear handwriting.
  datasheet page             → the parameter and its value, Source(datasheet)
  screenshot of an error     → Claim(observation) with the error text in body
If you cannot read something, say so in `unresolved`. Do not invent values.
Never fabricate a numeric measurement from an image.
```

That last line matters more than it looks: a hallucinated number read off a scope photo enters the graph as `EXTRACTED` truth and poisons a calibration record.

---

# 4. Validation — the code gate

Runs on every fragment before anything reaches the proposal queue. **Rejection is normal, not exceptional.**

```python
def validate(fragment: dict, ctx: Context) -> tuple[list[Node], list[Edge], list[Reject]]:
    rejects = []

    # HARD — the fragment dies
    require(isinstance(fragment, dict), "not an object")
    require(len(canonical(fragment)) < MAX_FRAGMENT_BYTES, "oversize")

    for n in fragment.get("nodes", []):
        if n["type"] not in NodeType:
            rejects.append(R(n, "unknown type"))
            continue
        if n.get("kind") not in KINDS[n["type"]]:
            rejects.append(R(n, "bad kind"))
            continue
        if not KEY_RE.fullmatch(n["key"]):
            rejects.append(R(n, "malformed key"))
            continue

        # SOFT — demote rather than discard
        if is_sentence_like(n["label"]):
            n = demote_to_note(n)  # ⭐ rule 3
        if len(n["label"]) > 60:
            n["body"] = n["label"]
            n["label"] = truncate_to_noun_phrase(n["label"])
        if n["type"] == "Concept" and n.get("project_id"):
            n["project_id"] = None  # Concepts are global

    for e in fragment.get("edges", []):
        if e["relation"] not in Relation:
            rejects.append(R(e, "unknown relation"))
            continue
        if e["score"] not in LEGAL_SCORES:
            rejects.append(R(e, "off-rubric score"))
            continue
        if e["confidence"] == "EXTRACTED" and e["score"] != 1.0:
            rejects.append(R(e, "false certainty"))
            continue

        # ⭐ added 2026-08-07 (Backend/08 §5.1) — citation state gates the tier
        cs = e.get("citation_state")
        if e["confidence"] == "EXTRACTED" and cs != "present_relevant":
            rejects.append(R(e, "EXTRACTED requires a directly-supporting passage"))
            continue
        if cs in ("present_weak", "anchor_unavailable") and e["score"] > 0.75:
            e["score"] = 0.75  # demote, don't discard
        if cs == "missing" and e["score"] > 0.65:
            e["score"] = 0.65
        if cs == "wrong_source":
            e["confidence"], e["score"] = "AMBIGUOUS", 0.3
        if e["relation"] == "requires" and not both_concepts(e, ctx):
            rejects.append(R(e, "requires is Concept→Concept only"))
            continue
        if e["src_key"] == e["dst_key"]:
            rejects.append(R(e, "self-loop"))
            continue
        if unknown_key(e, fragment, ctx):
            rejects.append(R(e, "dangling endpoint"))
            continue
        if e.get("span") is None:
            e["score"] = demote_one_rung(e["score"])

    return nodes, edges, rejects
```

```python
SENTENCE_MARKERS = re.compile(
    r"\b(is|are|was|were|has|have|should|would|could|will|did|does|because|"
    r"therefore|so that|which|that we|we |i )\b",
    re.I,
)


def is_sentence_like(label: str) -> bool:
    """A label is a name, not a sentence. Ported from Graphify's hard-won heuristic."""
    return (
        len(label) > 60
        or label.rstrip().endswith((".", "!", "?"))
        or label.count(" ") > 7
        or bool(SENTENCE_MARKERS.search(label))
    )
```

## 4.1 Quarantine

Anything rejected is **kept**, not dropped:

```python
Quarantine: {id, fragment_ref, reason, raw, created_seq, resolved: bool}
```

Visible in a review queue; invisible to retrieval. Two reasons this matters — a spike in one rejection reason is the earliest signal that a prompt has regressed, and a student asking *"why didn't it pick up X?"* deserves an answer better than silence.

---

# 5. Routing to the human

| Signal | Route |
|---|---|
| `EXTRACTED` (AST, parse, direct citation) | **auto-accept** |
| **all `INFERRED`** (0.95 → 0.55) | auto-accept, **flagged**, one-click undo |
| ⭐ **`AMBIGUOUS`** | **always asked of the student** — never auto-accepted, never dropped |
| any `contradicts` edge | **always review** — cheap to check, expensive to get wrong |
| any Artifact `agreement` | **always confirm with the student** — this is the flywheel datum |
| entity merge, 0.7–0.95 similarity | ⭐ **`same_as` edge — both nodes survive, no merge** (`Backend/09` Q4) |
| quarantined | review queue, low priority |

**The 0.85 threshold is a starting guess and must be calibrated in week one** against the actual accept rate. R3 gives an independent reference point: production annotation systems route to humans below roughly an **80% agreement threshold** and bypass review above it.

**Batch, never interrupt.** Proposals accumulate into one review surface with bulk accept/reject and multi-select (R3 §3). Interrupting a student mid-build to confirm an edge is how the feature gets turned off.

> ⭐ **Revised 2026-08-10 (`Backend/09` Q1).** The queue used to hold everything below 0.85. It now holds **only `AMBIGUOUS`** — the cases where the system genuinely cannot tell. That is a much smaller queue, and every item in it is a real question worth a student's judgement rather than a rubber-stamp. Auto-accepted `INFERRED` edges are protected by desaturation, low ranking, inability to promote anything to `established`, and the nightly contradiction sweep.

⚠️ **Review is far more expensive than it looks.** R3 §3 reports that trained professional reviewer pods manage 2,000–12,000 AI outputs/day, and true operating cost runs **4–6× the platform sticker price**. Our reviewer is one unpaid undergraduate with a project due. **Budget them 20–30 decisions per session, not hundreds** — which makes aggressive, well-calibrated auto-accept a requirement rather than an optimisation.

---

# 6. Worked examples

> ⚠️ **Synthetic.** Written to specify behaviour, not drawn from real student data. Replace with real inputs before treating the accept rates as meaningful.

## 6.1 Lab note

**Input:** *"Tried the MAX30100 on the 5V rail today — ADC pegged at full scale above about 3.1V so the readings were garbage. Moved to 3.3V and it behaved. I think the ADC reference is tied to VDD."*

```json
{"nodes":[
 {"key":"max30100","type":"Source","kind":"datasheet","label":"MAX30100","aliases":["MAX30100"]},
 {"key":"adc_reference","type":"Concept","label":"ADC reference voltage","aliases":["Vref","ADC ref"]},
 {"key":"rail_voltage","type":"Concept","label":"Supply rail voltage","aliases":["VDD","rail"]},
 {"key":"adc_saturation_5v","type":"Claim","kind":"observation",
  "label":"ADC saturates above 3.1 V on 5 V rail",
  "body":"ADC pegged at full scale above about 3.1V so the readings were garbage."},
 {"key":"run_3v3","type":"Artifact","kind":"run","label":"MAX30100 on 3.3 V rail",
  "predicted":null,"measured":{"quantity":"behaviour","value":"nominal","unit":null},
  "agreement":"inconclusive"},
 {"key":"ref_tied_to_vdd","type":"Claim","kind":"hypothesis",
  "label":"ADC reference tied to VDD","body":"I think the ADC reference is tied to VDD."}],
 "edges":[
 {"src_key":"adc_saturation_5v","dst_key":"ref_tied_to_vdd","relation":"supports",
  "confidence":"INFERRED","score":0.85},
 {"src_key":"run_3v3","dst_key":"adc_saturation_5v","relation":"evidence_for",
  "confidence":"EXTRACTED","score":1.0},
 {"src_key":"ref_tied_to_vdd","dst_key":"adc_reference","relation":"relates_to",
  "confidence":"EXTRACTED","score":1.0},
 {"src_key":"adc_reference","dst_key":"rail_voltage","relation":"requires",
  "confidence":"INFERRED","score":0.75}],
 "unresolved":[]}
```

**What this demonstrates:** *"I think"* → `hypothesis`, not `conclusion`. The observation is a named Claim with the sentence in `body`, not a node label. `agreement: inconclusive` because there was a measurement but no prior prediction — and **`predicted` is left null rather than back-filled**, which is the rule that keeps the calibration record honest.

## 6.2 Paper abstract

**Input:** *"…we show that bioimpedance measured at 50 kHz correlates with total body water (r = 0.81, n = 42), though the relationship weakens in subjects with BMI > 30."*

```json
{"nodes":[
 {"key":"bioimpedance_50khz","type":"Concept","label":"Bioimpedance at 50 kHz","aliases":["BIA 50kHz"]},
 {"key":"total_body_water","type":"Concept","label":"Total body water","aliases":["TBW"]},
 {"key":"bia_tbw_correlation","type":"Claim","kind":"observation",
  "label":"50 kHz bioimpedance correlates with TBW (r=0.81, n=42)"},
 {"key":"bmi30_limitation","type":"Claim","kind":"observation",
  "label":"Correlation weakens above BMI 30"}],
 "edges":[
 {"src_key":"bia_tbw_correlation","dst_key":"bioimpedance_50khz","relation":"relates_to",
  "confidence":"EXTRACTED","score":1.0},
 {"src_key":"bmi30_limitation","dst_key":"bia_tbw_correlation","relation":"contradicts",
  "confidence":"EXTRACTED","score":1.0}]}
```

**Note the `contradicts`.** A stated limitation becomes a relation, not a node type and not a colour — which is what makes tension countable, surfaceable, and resolvable. It also routes to review automatically under §5.

## 6.3 A hallucination the validator must catch

A model, given the lab note above, plausibly emits:

```json
{"src_key":"max30100","dst_key":"i2c_protocol","relation":"requires",
 "confidence":"INFERRED","score":0.85}
```

It's *true in the world* — the MAX30100 does use I²C — and **nothing in the material says so.** The model supplied it from pre-training. This is exactly the 1.5–1.9% class.

Caught by: `requires` is Concept→Concept only, and `max30100` is a Source → **hard reject**. Had both been Concepts, the missing `span` would demote it a rung to 0.75 → review queue.

**Design point:** we get two independent defences — a type constraint and a span requirement — and neither depends on the model behaving. That's the pattern to replicate for every high-risk relation.

---

# 7. The metric that matters

```
accept_rate = accepted_proposals / total_proposals     ← by confidence tier
```

Measure from day one, split by tier, source type, and relation.

| Reading | Meaning |
|---|---|
| `AMBIGUOUS` queue **not being cleared** | ⭐ the signal is about *value*, not volume — students don't think the question is worth answering |
| `INFERRED` edges frequently retracted after the fact | the rubric is mis-calibrated; tighten the prompt, not the gate |
| `AMBIGUOUS` accept rate **> 50%** | the model is under-confident; the rubric needs re-anchoring |
| quarantine rate **> 10%** | the prompt has drifted or the input type is unsupported |
| queue depth growing | auto-accept is too tight; the student will abandon review |

**This single number is our real hallucination rate, our real review burden, and the calibration for every threshold in the system** — from one screen, in week one. It is the reason Phase 0 step 3 exists.

---

# 8. What is deliberately not here

Chunking strategy (needs real documents to tune), model selection and prompt-caching (cost work, not correctness), multilingual handling, and incremental re-extraction on file change. All are downstream of the contract being right.

---

# 💡 Visionary Vector — `unresolved` is the most valuable field in the schema

Every extraction emits an `unresolved` array: things the model noticed but could not confidently structure. The obvious reading is that it's an error channel — the leftovers, to be cleaned up.

It is the opposite. **`unresolved` is a direct measurement of where a student's own thinking is not yet structured enough to be represented.**

A model can't decide whether *"felt like the 5V rail was noisy?"* is an observation or a hypothesis — because **the student hasn't decided either.** A relation whose endpoints can't be determined usually means the student wrote a connection they haven't actually made yet. The extractor's confusion is a faithful mirror of the author's.

That makes the unresolved pile the highest-signal input the tutoring layer could possibly have. Not *"here's what you don't know"* — every product claims that — but ***"here is where your own account of your work is ambiguous, quoted back to you."*** And the intervention is the cheapest one in education: *"you wrote this — did you mean you observed it, or that you suspect it?"* Answering costs the student ten seconds, sharpens their thinking, and returns a clean node to the graph.

Nobody else can build this. Atlas extracts from papers, where ambiguity is the *author's* problem and the reader can only work around it. Graphify extracts from code, which is unambiguous by construction. **We extract from a student's own half-formed account of their own work, which means our extraction failures are diagnostic rather than merely annoying.**

Concretely: don't hide the unresolved queue behind an admin flag. Surface it as *"three things you wrote this week that I couldn't quite pin down"* — and treat the rate at which a student resolves their own ambiguities as a measurable proxy for whether their thinking is getting sharper.

---

*Next: `11_Concept_Skeleton` — the prerequisite graph the frontier engine needs.*

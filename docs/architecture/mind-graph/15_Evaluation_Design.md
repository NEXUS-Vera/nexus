# Mind Graph — Evaluation Design

**Closes open question B2.** Five metric families, their baselines, their pitfalls, and what must be logged from day one.
**Date:** 2026-08-07

> **Why this can't wait.** Most of what follows is **unreconstructable retroactively.** A held-out link-prediction split needs edge timestamps that were never optional; calibration needs `predicted` recorded *before* `measured`; the review accept rate needs proposals stored even when auto-accepted. Ship without these and the first honest question — *"is this actually helping anyone?"* — is unanswerable for another six months.
>
> **And the field has no answer either.** Report 06 §1.1: no reliable independent data on cost or curation. Report 01 §10.1: the memory-benchmark scoreboard is contested and its successors note it fails to test updated state, conflict detection, or abstention — *exactly* our capabilities. **There is no good benchmark for what we're building.** That's an opening (03 §10), but only if we build the measurement.

---

# 1. The five families

| # | Measures | Answers | Ready when |
|---|---|---|---|
| **E1** | Extraction quality | *is the graph made of true things?* | week 1 |
| **E2** | Graph quality | *does the structure predict reality?* | ~month 2 |
| **E3** | Advice quality | *does the frontier point somewhere useful?* | ~month 3 |
| **E4** | Calibration | *is the student's judgement improving?* | ~week 6 |
| **E5** | Product outcome | *did they finish a working proof?* | ~month 3 |

E1 is nearly free and immediately actionable. E4 is the one nobody else can compute. E5 is the one that matters and is hardest to attribute.

---

# 2. E1 — Extraction quality

## 2.1 Primary: review accept rate

```
accept_rate(tier) = accepted / (accepted + rejected)
```

Split by confidence tier, source type, and relation. Already specified in 10 §7 — restated here as the week-one metric because it's the cheapest real signal in the system.

| Reading | Action |
|---|---|
| `INFERRED ≥0.85` accept < 80% | auto-accept threshold too low — raise it |
| `INFERRED ≥0.85` accept > 97% | too conservative — lower it, reclaim review budget |
| `AMBIGUOUS` accept > 50% | model under-confident; re-anchor the rubric |
| quarantine rate > 10% | prompt drift or unsupported input type |
| queue depth rising | auto-accept too tight; student will abandon review |

⚠️ **Accept rate measures agreement, not truth.** A student clicking accept on everything produces a beautiful number and a garbage graph.

## 2.2 Secondary: audited precision

Once a month, sample **50 auto-accepted edges**, and have a human check each against its span:

```
precision = edges whose span actually supports the claim / 50
```

Reported with a 95% Wilson interval — at n=50 that's roughly ±13pp, so it detects *disasters*, not drift. Fine: disasters are what we're looking for. Expected fabrication rate is 1.5–1.9% (05 §1.1), so anything below ~90% precision means something is structurally wrong, not noisy.

**Baseline:** the same 50 edges extracted with the ontology constraints stripped from the prompt. If constrained ≈ unconstrained, the contract in report 10 isn't earning its complexity — a genuinely falsifiable claim about our own design.

---

# 3. E2 — Graph quality via temporal link prediction

The question: **does the graph predict the connections the student goes on to make?**

## 3.1 ⭐ Temporal split, never random

Standard KG-completion practice splits triples randomly. **For us that's leakage** — a randomly held-out edge may have been created *before* edges we train on, so the model sees the future.

```
train  = all edges with created_seq ≤ T
test   = edges created in (T, T + Δ]        ← genuinely unseen future
```

`T` = end of week *k* of a project; Δ = one week. This mirrors the real task: *given what the graph knew on Monday, did it predict what got connected by Friday?*

## 3.2 Metrics — standard, with the standard corrections

**MRR** (mean reciprocal rank of the true target) and **Hits@k** (k = 1, 3, 10), computed in the **filtered setting**: when ranking candidates for `(src, relation, ?)`, mask out all *other* known-true targets so a correct alternative answer isn't scored as a miss.

Three pitfalls the literature documents, all of which we must adopt:

| Pitfall | Guard |
|---|---|
| **Test-set leakage** — WN18/FB15k gave state-of-the-art results to trivial rule-based models because inverse relations leaked; corrected versions (WN18RR, FB15k-237) exist for this reason | our temporal split plus explicit removal of inverse/symmetric duplicates from test |
| **Tie handling** — optimistic tie-breaking inflates scores | use the **BOTTOM** convention: a tied correct triple is ranked *last* among equals. Conservative, and comparable across runs |
| **Random-seed instability** — rank metrics conceal per-prediction instability | **report mean ± sd over ≥5 seeds.** Never a single run. (This is precisely the flaw that produced the disputed Zep number in 04 §1.4 — don't reproduce it) |

## 3.3 Baselines — mandatory

A hits@k with no baseline is meaningless. Three, in ascending difficulty:

1. **Random** — floor.
2. **Preferential attachment** — always predict the highest-degree node. Embarrassingly strong on real graphs; if we don't beat it, we have nothing.
3. ⭐ **Adamic–Adar** — degree-discounted common neighbours (04 §3.1). Deterministic, no model, no embeddings, ~20 lines. **This is the honest bar**, and if our full DOI + PPR stack doesn't beat plain Adamic–Adar, the stack isn't earning its cost.

## 3.4 Honest limits

Per-user graphs are 10³–10⁴ nodes and one-week test windows will hold **tens** of edges. Metrics will be noisy and mostly **descriptive**. Pool across users for anything inferential, and report per-user variance rather than hiding it in a mean.

---

# 4. E3 — Advice quality

Does the frontier engine point at things that turn out to matter?

## 4.1 Prospective outcome tracking

For every surfaced frontier item, record what happened within 14 days:

```
acted_on     student started work on it
completed    it produced an Artifact
mattered     that Artifact ended up supporting a conclusion in the project
ignored      never touched
```

```
precision@k  =  mattered / surfaced_at_rank_≤k
```

## 4.2 Baselines

| Baseline | What it tests |
|---|---|
| **Random reachable gap** | is the *ranking* doing work, or just the filtering? |
| **Highest-degree unvalidated concept** | does DOI beat plain centrality? |
| **Syllabus order** | does the graph beat a fixed curriculum sequence? ⭐ the one that matters for the product claim |

## 4.3 ⚠️ The confound, stated plainly

**Surfacing an item makes the student more likely to act on it, which makes it more likely to matter.** Precision@k is contaminated by its own recommendation.

The clean fix is a held-out arm: surface the top-*k* but silently log ranks *k+1…2k*, then compare "mattered" rates. That requires enough users to be worth it. **Until then, report E3 as descriptive and do not claim causality.** Better to say "we don't know yet" than to publish a self-fulfilling number — which is exactly the failure mode we criticised in the vendor benchmarks (05 §2).

---

# 5. E4 — ⭐ Calibration (the one nobody else can compute)

Every `Artifact` carries `predicted`, `measured`, `agreement` (08 §3.4). That is a forecast with a resolution — which makes it scoreable by standard forecasting metrics.

## 5.1 Metrics — ⭐ revised 2026-08-10 (`Backend/09` Q9)

**The headline metric is a reliability curve, not a Brier delta.** The reason is a confound I originally missed — see §5.2.

### Primary: reliability curve

Bin predictions by the student's **stated confidence** (captured on the Artifact screen — *"how sure are you?"*), then plot stated against observed:

> **When you said 80% sure, were you right 80% of the time?**

Perfect calibration is the diagonal. **Above it is over-confidence**, which is the characteristic and interesting undergraduate failure — and therefore the most likely direction of movement.

```
calibration_error = mean over bins of | stated_confidence − observed_accuracy |
```

### ⭐ Secondary, and more sensitive early: interval coverage

*Of predictions stated as a range, what fraction contained the measured value?*

Well-calibrated 80% intervals contain the truth ~80% of the time. Undergraduates typically land far below. **The gap is large, so the effect size is large, so it is detectable at much smaller n** than a fine-grained reliability curve — this is the metric that will move first.

### Retained: Brier score

```
BS = (1/N) Σ (p_i − o_i)²        lower is better; 0.25 = coin flip
```

Kept as a summary statistic, **not** as the before/after comparison. See §5.2.

## 5.2 ⭐ The design advantage — and the confound that reshaped the metric

Every other family needs a control group we won't have. **Calibration doesn't** — each student is their own control, which is the only rigorous claim available at n=10.

**But the obvious form of that claim is wrong.** The original design compared Brier in weeks 1–2 against weeks 5–6. Three problems:

| | Problem |
|---|---|
| **Sample size** | 12 predictions over six weeks makes a first-5-vs-last-5 comparison enormously noisy. A Brier delta needs ~30+ |
| **Task heterogeneity** | predicting an impedance value and predicting whether firmware compiles are different tasks; a Brier over the mixed bag is muddy |
| ⭐ **Difficulty drift** | **week-6 predictions are about harder things.** Flat calibration on rising difficulty is a *real improvement* that a naive before/after shows as nothing |

**A reliability curve kills the third confound by construction**, because it conditions on the student's *own* stated confidence. A harder prediction they were appropriately less sure about doesn't penalise them.

**The claim therefore becomes:**

> *"Across N students, calibration error fell by X (95% CI …) over a six-week project, and interval coverage moved from Y% toward the stated level."*

Still within-subject. Still needs no control group. **And now measuring the thing we actually mean.**

### Why there's reason to expect movement

Calibration is **known to be trainable**, and the mechanism that trains it is **rapid, unambiguous feedback** — which is exactly what the predict → measure loop provides. That's a real prior in our favour, and it wasn't in the original design note.

## 5.3 ⭐ Pre-registering the null

Defined **before** running, so a null result is informative rather than quietly dropped:

| | |
|---|---|
| **Primary** | mean \|stated confidence − observed accuracy\| across bins |
| **Predicted** | decrease **≥ 0.05** over six weeks |
| **Null** | no change, or an increase |
| **Minimum n** | **15 resolved predictions per student**; 8+ students |
| **Secondary** | interval coverage — expect it to move first and further |

**And if it's null, that is not fatal.** Calibration is the *measurement*, not the mechanism — the record, the frontier, and the Disagreement Engine all still work. A null means we lead with **proof completion** instead, and we'd have a genuinely publishable finding: *six weeks of predict-measure feedback does not measurably improve undergraduate calibration.* Nobody has that result either.

## 5.4 Guards

- **`predicted` must be timestamped before `measured`.** Enforced by `seq` ordering — a `validated` event whose `predicted` first appears in the same event is flagged as back-filled and excluded.
- **Exclude trivially-easy predictions** (LED blinks, code compiles) or the score is gamed by boredom. Restrict to predictions the frontier itself rated as informative.
- **Minimum ~15 resolved predictions** before reporting a per-student curve.
- **Report bins with n < 3 as unfilled**, never as a data point.

---

# 6. E5 — Product outcome

The one that actually matters, and the hardest to attribute.

```
completion_rate  = students producing a working PoC / students who started
time_to_proof    = days from project start to first Artifact(agreement=matched)
                   on the project's central Question
depth            = validated concepts on the critical path
abandonment      = last-session date, and what they were stuck on   ← ⭐
```

## 6.1 Baselines — the honest problem

There is no clean control. Options, all imperfect:

| Option | Problem |
|---|---|
| Historical departmental completion rates | different students, different projects |
| Self-report from non-users | unreliable |
| Waitlist / delayed-access cohort | ⭐ **the only clean one, and it needs ~40+ students** |
| Within-subject across two projects | slow — a year per data point |

**Recommendation: don't claim causal completion improvement until a waitlist design is possible.** Report completion descriptively and lead with E4, which *is* rigorous at small n. This is the discipline that separates our benchmark from the ones we criticised.

## 6.2 Abandonment is the sharpest early signal

With ten users, completion rate is noise. **Abandonment is not** — and report 06 §2 found the failure mode is *giving up*, silently, invisibly in analytics. Instrument it directly: last action before a 7-day gap, queue depth at abandonment, whether the frontier was empty, time-to-close on the graph view, zero-interaction sessions.

---

# 7. What to log from day one

Everything below is unreconstructable later.

| Log | For | Cost |
|---|---|---|
| every proposal, **including auto-accepted**, with tier and outcome | E1 | tiny |
| `created_seq` on every node and edge (already in schema) | E2 | free |
| frontier items surfaced, with rank and timestamp | E3 | tiny |
| ranks *k+1…2k* silently, for the future held-out arm | E3 | tiny |
| `predicted` as its own event, before `measured` | E4 | free |
| session boundaries, last action, queue depth | E5 | tiny |
| per-op cost rows (09 §8) | all | tiny |

**None of it needs a decision now. All of it needs the plumbing now.**

---

# 8. What we will not claim

Discipline, because we criticised others for exactly these (01 §10.1, 05 §2):

- ❌ *"The Mind Graph improves learning outcomes"* — no control group, and the HCI literature has null-to-negative results on graph interfaces for learning (06 §2).
- ❌ *"Students finish X% more projects"* — until a waitlist design exists.
- ❌ Any single-run benchmark number without seeds, sd, and a named baseline.
- ❌ Comparative claims against Atlas/NotebookLM without running them on the same corpus under a rubric locked in advance.
- ✅ **What we can claim, honestly:** measured extraction precision with an interval; link prediction against Adamic–Adar with seeds; **within-subject calibration improvement**; and the operating cost per project, which nobody else has published.

---

# 9. Sequencing

| When | Do |
|---|---|
| **Before user 1** | logging plumbing (§7). Everything else is downstream |
| **Week 1** | E1 accept rate live; calibrate the auto-accept threshold |
| **Month 1** | first audited-precision sample; Adamic–Adar baseline implemented |
| **Month 2** | E2 temporal split running with ≥5 seeds |
| **Month 3** | E3 descriptive; E5 abandonment instrumented |
| **After 6 weeks of a real project** | ⭐ first E4 calibration curve — the first number worth showing anyone |
| **At ~40 users** | waitlist design; E5 becomes causal |

---

# 💡 Visionary Vector — publish the benchmark before we win it

Atlas published a locked-rubric, CC-BY, fully-disclosed benchmark methodology **with no results in it** (03 §7), on axes where they compete with NotebookLM and ChatGPT. It's a credibility play, and a good one.

We can do something strictly stronger, and it costs almost nothing extra because §7 has to be built anyway: **publish the evaluation protocol for a category that has no benchmark at all.**

There is currently no accepted way to measure whether an AI research-and-build assistant *works*. LOCOMO doesn't test updated beliefs, conflict detection, or abstention. GraphRAG benchmarks openly concede they *"fail to adequately evaluate the effectiveness of graph structures."* Every product in this space makes unfalsifiable claims because no one has defined what falsifying them would look like.

So define it. Publish, dated, CC-BY, rubric locked before results:
- the temporal link-prediction protocol with Adamic–Adar as the mandatory baseline
- **the calibration protocol** — reliability curves and interval coverage over predicted/measured pairs on physical experiments, with the null pre-registered
- proof-completion with an explicit statement of why causal claims require a waitlist arm
- the operating-cost schema, since no one has published one

**Whoever defines the metric defines the category**, and there are two asymmetries here. First, the axes are ones we can measure and competitors structurally cannot — calibration and proof completion both require a build loop, and Atlas ends at understanding (03 §9). Second, and more useful: publishing the protocol *before* having results is the strongest possible signal that the numbers weren't reverse-engineered from what we wanted — which is precisely the criticism that sank the benchmark claims we spent this research picking apart.

The deepest version: the protocol is **student-facing too.** A calibration curve is not just our evaluation metric, it's the student's own progress indicator (12 vector). The thing we use to prove the product works and the thing the student uses to see themselves improving are **the same object** — which is a rare and durable alignment between a company's north-star metric and its user's actual interest.

---

*Closes B2. With 14, the backend first draft is complete.*

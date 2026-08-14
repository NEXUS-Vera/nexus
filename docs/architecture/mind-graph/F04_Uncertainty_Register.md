# Frontend Uncertainty Register

**Frontend / 04.** Every frontend design call I am **not** confident about — what I chose, what I rejected, why, and what would settle it.
**Companion to `Backend/09`**, same format. Q-numbers here are prefixed **F**.
**Date:** 2026-08-10 · **status merged 2026-08-13**

> **What I *am* confident about**, for contrast: the ~50-node cap, no fisheye/focus+context distortion, VSUP for uncertainty, ghost nodes for absence, staged transitions, debounced spatial undo, arrows-by-default with Vim opt-in, no streaks or time-in-tool metrics, and the hidden accessible table. Those are evidence-backed or the alternative is demonstrably worse.

---

## 📊 STATUS — read this first

There are **two** registers.

| Register | Count | State |
|---|---|---|
| `B09_Uncertainty_Register.md` — backend | 12 | ✅ **all 12 closed** (10–11 Aug) |
| `F04_Uncertainty_Register.md` — frontend | 11 | **8 closed · 3 open** |

**Total: 23 doubts · 20 closed · 3 open.** All three open ones are
"watch during real use"; none blocks anything.

### The eleven frontend doubts

| # | The doubt | Status | How it was settled |
|---|---|---|---|
| **F1** | Is graph-as-engine right, or over-corrected? | ✅ **closed** | Aryav 08-13: the Map is a **storage mechanism**, so fifth in the sidebar is correct. Not a front door. |
| **F2** | Overview: state dashboard or minimap? | 🟡 **open — watch** | Needs real use. ⚠️ Sharper since F11 closed: orientation matters more in a thing you *browse* than one you plan with. Symptom: people scrolling the Map hunting rather than jumping. |
| **F3** | Does VSUP desaturation cost type legibility? | ✅ **closed** | **By F4's failure.** Hue no longer carries type alone — the glyph does, and a glyph does not desaturate. ⚠️ Reopens if labels are ever hidden at low zoom. |
| **F4** | Do six desaturated hues separate under CVD? | ✅ **closed — FAILED, then fixed** | Gate run 08-11: six hues failed at dE 0.002 (Question/Artifact, deuteranopia); 103/240 combinations below floor. Palette cut to **four families + glyphs**; gate passes. ⚠️ **Amended 08-13 — see below.** |
| **F5** | Are "projects as spatial regions" workable? | 🟡 **open — now testable** | The demo's galaxy holds (hubs on fixed directions). `Frontend_build`'s Map is untested — ForceAtlas2 with no grouping force, the exact configuration this doubts. |
| **F6** | Mobile — is "viewable" achievable? | ✅ **closed** | Share rebuilt **mobile-first** 08-13. ⚠️ The blocker was the *shell*, not the page — a mobile-first page inside a fixed 3-column grid is still unreadable. |
| **F7** | Is one capture bar enough? | ✅ **closed** | Aryav 08-13: don't chase accuracy — make a wrong guess cost one keystroke. **Watch correction rate, not routing accuracy.** |
| **F8** | Should the Artifact loop be a form? | ✅ **closed** | Aryav 08-13: keep the form, fix the **orchestration**. **Still measure week-1 predict completion.** |
| **F9** | Does Share need per-audience versions? | ✅ **closed** | Aryav 08-13: one page, collapsible depth, author controls *emphasis* not content. ✅ **shipped 08-13.** |
| **F10** | Is ~580ms too slow for expansion? | 🟡 **open — watch** | 580ms is my number, not the literature's. Try 350 vs 580 after fifty expansions. |
| **F11** | Have I designed for the wrong moment? | ✅ **closed** | Aryav 08-13: the Mind Graph is **storage and retrieval**, not a planning surface. The design was being judged against a role it was never meant to play. |

---

## ⚠️ Amendment to F4 — 2026-08-13

**Aryav's decision:** *"leave the colour-blind users, make the colours as
optimal as possible for the Mind Graph."*

**What it means:** visual quality of the graph takes priority over the CVD gate
as the *primary* constraint on hue choice.

**What it costs, stated so nobody is surprised later:** ~8% of men have
red-green colour-vision deficiency. If hue alone carries type, they cannot read
the encoding — and the gate exists because **the first palette failed it
invisibly.** It is also the kind of thing a university, grant reviewer or
investor's technical diligence notices.

⭐ **The middle path, recommended:** keep the **glyph** as a redundant channel
(◆ ? ▲ ■ ▪ ·). Type is then carried by shape, which does not fade, desaturate,
or depend on colour vision — so **hue is free to be whatever looks best.** This
is already what F3's closure depends on.

**Operationally:** keep `scripts/f4_gate.py` and keep running it, but treat a
failure as *"this pair needs a glyph or a lightness difference"*, not
*"choose different colours."*

**Status: recorded, not yet applied.** Open for discussion.

---

## ✅ Resolved by Aryav — 2026-08-13

### F11 — the Map is storage, not planning
Not something a student uses constantly while planning. It is where their data
lives — open a project's graph, browse stored knowledge, find a past decision.
**A storage and retrieval mechanism.**
**Changes:** the Map must be good at **finding**, not surveying.
**Residual:** browsing is not the same as being handed what you need. Listen for
*"I knew it was in there and couldn't find it."*

### F1 — fifth in the sidebar is right
A standout feature *and* a storage mechanism, so not a front door. Settled.

### F8 — keep the form, fix the orchestration
**Shipped:** range-only gate · lock is a timestamped moment rendered as text ·
`because`/`method` after the lock · calibration streak shown *at* lock time.
**Measure:** week-1 predict-step completion.

### F7 — make a wrong guess cost one keystroke
**Shipped:** visible guess before commit · optimistic routing · one-click
correction emitting a learning signal · confidence-gated asking below 0.5 ·
`?` `!` `>` prefixes.
**Measure:** correction rate.

### F9 — one page, collapsible depth
Three depths (Summary / Standard / Full) plus author control over title and
opening depth. ⚠️ **Content is not adjustable** — withdrawals and diverged
results cannot be hidden at any depth, and at Summary depth they are the *only*
history shown.
**Status:** ✅ **shipped 2026-08-13.** Three depths, an Adjust panel for title and opening depth, and the unhideable-failures note stated in the UI.

---

# ✅ F1 · Is graph-as-engine right — and have I gone too far?

**Chosen:** the graph is a secondary surface, opened deliberately. The Bench (a ranked list) is home. The Map is the **fifth** thing I'd build.

**Rejected:** canvas-first, graph as the home screen.

**Why:** null-to-negative learning outcomes for node-link diagrams; comprehension collapses past ~50 nodes; every genuine graph capability is machine-facing.

**Why I'm unsure — two ways I could be wrong:**
1. **The graph is the most demo-able thing we have.** Your 644-node screenshot is what makes people react. Burying it may cost more in adoption and word-of-mouth than it gains in usability.
2. **I may have over-corrected.** The research condemns *unbounded* graphs given to people with a search task. A 50-node, well-encoded, deliberately-scoped graph is a different object and might be genuinely good as a primary surface.

**What settles it:** build the Bench and the Map, instrument which one people open and what they do there. **Time-to-close on the Map is the tell** — if it's under 10 seconds, it's decoration.

---

# 🟡 F2 · Should the overview be a state dashboard or a minimap?

**Chosen:** a **state dashboard** — % established, contested count, reachable gaps, calibration strip.

**Rejected:** a conventional minimap.

**Why:** overview+detail beats focus+context, but a *shrunken hairball is still a hairball*. An abstracted state summary is more useful and **only we can build it** — it needs epistemic state no competitor records.

**Why I'm unsure:** the classic reason for a minimap is *spatial orientation* — "where am I in the whole thing?" A dashboard answers a different question and doesn't provide that. If users get lost in the Map, I've solved the wrong problem.

**Alternative:** both — dashboard by default, toggle to spatial minimap.

---

# ✅ F3 · Does VSUP desaturation cost too much type legibility?

**Chosen:** saturation encodes confidence; low-confidence nodes trend grey.

**Why:** it physically prevents drawing confident conclusions from uncertain data — the single best-evidenced uncertainty encoding available.

**Why I'm unsure:** a low-confidence `Concept` and a low-confidence `Source` both go grey, so **type becomes hardest to read exactly where confidence is lowest.** I decided "you shouldn't trust this" matters more there than "what kind of thing is it." That's a judgement, not a finding.

**Alternative:** confidence on the inner ring (currently corroboration), corroboration moved to a numeric badge. Preserves hue, weakens the perceptual force of the uncertainty signal.

**What settles it:** show both to five students and ask them to find the least trustworthy node.

---

# ✅ F4 · Six hues — are they distinguishable when desaturated?

**Chosen:** six desaturated pastels in Oklab (teal / amber / lavender / green / slate / grey).

**Why I'm unsure:** desaturation is required for dark mode (halation), but it also **compresses the distance between hues.** Six *saturated* hues are clearly distinguishable; six *desaturated* ones might not be — especially at small node sizes, and especially under CVD.

I've mitigated with redundant encoding, but I haven't verified the palette actually separates.

**What settles it:** render the six at 8px, 16px, 32px, on the real background, through a CVD simulator. **Half a day, and it should happen before any UI is built** — if it fails, node types collapse to four or five.

---

# 🟡 F5 · Is "projects as spatial regions" workable?

**Chosen:** hue is reserved for node *type*; **project membership becomes spatial region tinting.**

**Why:** hue can carry one categorical variable, and the current design has it doing two jobs at once (the screenshot's legend shows four projects *and* four kinds).

**Why I'm unsure:** spatial region is the strongest identity channel — but **the force layout controls position, and it clusters by connectivity, not by project.** If a project's nodes don't end up spatially adjacent, region tinting produces incoherent blobs.

**Alternative:** constrain the layout to group by project (a grouping force), accepting a less honest topology. Or drop cross-project views from the Map entirely and switch projects instead.

**What settles it:** run ForceAtlas2 with a grouping force on real multi-project data and see whether the regions hold.

---

# ✅ F6 · Mobile — is "viewable" actually achievable?

**Chosen:** desktop-only for work; Share, Bench, and Log responsive and readable; one Quick Capture affordance.

**Why I'm unsure:** *"viewable on a phone"* is easy to say and hard to do for a graph. The Map degrades to a top-10 list, which may make the shared view feel gutted precisely when an investor opens it on a phone — **the most likely way it will actually be seen.**

**What settles it:** design the Share page **mobile-first**, since that's its likely primary context, and let desktop be the enhanced version. That inverts my current assumption and might be correct.

---

# ✅ F7 · Is one capture bar enough?

**Chosen:** a single always-present input; the system routes whatever you type.

**Why:** the "organisational tax" is the primary driver of PKM churn, and any *"where does this go?"* decision is that tax.

**Why I'm unsure:** routing has to be right almost every time or it becomes worse than folders — a misfiled item you can't find is more frustrating than one you filed yourself. And correcting a misroute is itself a tax.

**What settles it:** measure routing accuracy in week 1. Below ~90% and it needs an explicit type picker as a fallback.

---

# ✅ F8 · Should the Artifact loop be a form?

**Chosen:** a structured two-step form — Predict, then Measure — with an explicit `Lock prediction`.

**Why:** the structure *is* the value. Free text can't be scored, and calibration is the metric that matters.

**Why I'm unsure:** it's the most **form-like** thing in a product otherwise designed to eliminate friction, and it appears at the exact moment a student is impatient to go and build something. **If it feels like paperwork, it won't get filled in — and it's the moat.**

**Alternatives:** capture the prediction conversationally and let the system extract the structure (risks accuracy); or make only the range mandatory and everything else optional.

**What settles it:** week-1 completion rate on the predict step. This is probably the single most important early UX number in the product.

---

# ✅ F9 · Does the Share page need to be different per audience?

**Chosen:** one page, three sections (what it is / what was proven / how it got there).

**Why I'm unsure:** a professor wants rigour and method. An investor wants trajectory and ambition. A teammate wants current state and what's blocked. **One page may serve none of them well.**

But per-audience variants mean the student curates — which is exactly the "organisational tax" we're trying to eliminate, and it also invites the polishing-away of failures that makes the artifact honest.

**Alternative:** one canonical page with **collapsible depth** — everyone sees the same thing, and each reader expands what they care about.

> ✅ **RESOLVED 2026-08-13 — the alternative won, and shipped.**
>
> Three depths (Summary / Standard / Full) plus an **Adjust** panel giving the
> author the title and the opening depth. Depth is the READER's control;
> emphasis is the author's.
>
> ⚠️ **Content is not adjustable, and the UI says so out loud.** Withdrawals
> and diverged results cannot be hidden at any depth — and at Summary depth
> they are the *only* history shown. Shortening the page must never mean
> sanitising it, or "Summary" becomes the version people share when they have
> something to hide.

---

# 🟡 F10 · Is ~580ms too slow for expansion?

**Chosen:** three-stage transition totalling ~580ms.

**Why:** staged transitions measurably improve change tracking versus simultaneous.

**Why I'm unsure:** staging is measured to help, but **580ms is my number, not the literature's** — I picked stage durations by feel. A student expanding twenty nodes in a row will feel every one of them. And a cited paper questions whether *staggering* specifically helps as much as claimed.

**What settles it:** try 350ms and 580ms and see which people prefer after fifty expansions, not five.

---

# ✅ F11 · Have I designed for the wrong moment?

**The meta-doubt, and the one I'd most want you to think about.**

Everything here optimises the **working** loop: what to do next, record an outcome, review proposals. But the retention research says the abandonment cliff is **week 3 — when debugging starts and organising stops.**

At that moment the student is not planning. They're stuck on one specific thing at 1am, with a scope in one hand.

**I don't know whether any of these surfaces help then.** The Bench assumes you want to know what's next; in week 3 you already know, it just isn't working. The most valuable surface at 1am might be something I haven't designed at all — *"here is everything you know about this one component, including the thing you tried on Tuesday that failed."*

**What settles it:** watch one real student in week 3. Not a survey. One afternoon of observation would be worth more than this entire document.

# Priorities

| | |
|---|---|
| **Settle before building** | **F4** (palette legibility — half a day, could invalidate the type system) · **F1** (the premise) |
| **Settle in week 1 of use** | **F8** (predict-step completion — the moat's UX risk) · **F7** (routing accuracy) |
| **Watch, don't decide** | F2, F3, F5, F9, F10 |
| **⭐ Requires observing a real student** | **F11**, and it's the one most likely to change the design |

**None of these blocks starting.** They block *finishing*.

---

# 💡 Visionary Vector — F11 is the one worth acting on

Ten of these eleven doubts resolve by measuring something. F11 doesn't, and it's the only one that could invalidate the whole design rather than a piece of it.

Here's why it matters more than it looks. **Every surface in `Frontend/01` is designed for a student in a planning posture** — reflective, deciding what to do next, willing to review proposals. That's a real state, and it's the state a student is in during weeks 1 and 2.

**It is not the state they're in during week 3**, which is precisely when the research says they abandon the tool. At 1am, mid-debug, the question isn't *"what should I do next?"* — it's *"why is this not working, and have I already tried this?"*

If that's right, the highest-value surface in the product is one I haven't designed: a **debug companion** — not a map, not a queue, but everything the graph knows about *the one thing currently in front of you*, including your own dead ends. *"You tried a 10 kΩ pull-up on Tuesday. It didn't work. Here's why you thought it would."*

**That is the single most defensible thing this architecture could produce**, because it requires exactly the components no competitor has: dead-end memory with reasons, justification chains, and outcomes. And it fires at the precise moment every other tool loses its user.

I'd rather find that out from an afternoon watching a real student in week 3 than from another research pass — because this is a question about *when* people need help, and no amount of literature answers it for our specific user.

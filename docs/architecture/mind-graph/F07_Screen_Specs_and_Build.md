# Frontend — Screen Specs, Settings, and the Build Plan

**Frontend / 07.** The last deferred block: concrete component anatomy, the
states every surface must handle, settings/notifications/offline, and the order
things get built in.
**Companion to** `Frontend/01` (surfaces) and `Frontend/06` (tokens, stack).
**Date:** 2026-08-10

> ⚠️ **F4 still gates everything here.** If six desaturated hues do not separate
> under CVD at 16px, node types collapse to four or five and §2's anatomy, the
> palette and the encoding matrix all change. **Half a day. Do it first.**

---

# 1. The states every surface must handle

Most interfaces are specified for the success case and then improvised for the
rest. These five are the rest, and each has a rule rather than a guess.

| State | Rule |
|---|---|
| **empty** | say what would fill it, and offer the action that does. Never an illustration and a shrug |
| **loading** | skeleton at the shape of the real content. ⚠️ Never a spinner over a region that already has content — that reads as *broken*, not *busy* |
| **partial** | ⭐ show what arrived and mark what has not. The graph is a projection; a partial answer is normal, not an error |
| **error** | say what failed, what still works, and what to do. *"Something went wrong"* is a refusal to help |
| **stale** | visible age, and a way to refresh. Sidecars are recomputable — say when they were computed |

⭐ **`partial` is the one that matters here.** A retrieval that returns 12 of 50
nodes, an ingest still parsing, a Critic that has not returned — all normal
states of a system with an async analyzer, and all of them must look *deliberate*
rather than half-broken.

---

# 2. Component anatomy

Dimensions in the 4px grid from `Frontend/06 §2.2`. Every component below is
composed of tokens; none introduces a new colour or radius.

## 2.1 The node chip — the atom

Used in lists, `explain`, answers, and the review queue. **The Map's node is a
different component**; this is the one that appears 40 times a screen.

```
   ┌─────────────────────────────────────────┐
   │ ◆  skin impedance              ◑  ⚡     │   h 32px · pad 8/12
   └─────────────────────────────────────────┘
     │  │                            │  └─ rim glyphs, 12px, right-aligned
     │  └─ label, 13px/500, truncate at 1 line
     └─ type glyph, 14px, carries hue
```

| Channel | Carries | Never carries |
|---|---|---|
| **hue** | node type | confidence, support, recency |
| **fill** | support state (solid / hollow / dashed) | anything else |
| **saturation** | confidence — VSUP, desaturates toward grey | type |
| **rim glyphs** | `◑` single-method · `⚡` contested · `◷` stale | type or confidence |

⚠️ **Rim glyphs are the overflow channel and they are nearly full.** Three is
readable; five is a rash. Anything new competes for one of the three rather
than adding a fourth — and the honest fix when they collide is to drop the
weakest, not to shrink them all.

## 2.2 The action row — the Bench's unit

```
   ┌──────────────────────────────────────────────────┐
   │  ◆  Measure electrode impedance at 50 kHz         │  title 15px/600
   │     unlocks 3 · ~2h · you have the parts          │  meta 12px, 60% α
   └──────────────────────────────────────────────────┘
      h 64px · full-bleed hover · entire row is the target
```

⭐ **The meta line is the product.** *"Unlocks 3"* is the frontier, *"~2h"* is
the cost model, *"you have the parts"* is the graph knowing what you own. A row
without a meta line is a to-do item, and to-do items are not worth building
this for.

## 2.3 The prediction lock — the moat's one interaction

```
   ┌──────────────────────────────────────────────────┐
   │  I expect    [ 45 ] – [ 50 ]  [ kΩ ▾ ]            │
   │  because     ┌────────────────────────────────┐   │
   │              │ 2 cm spacing, dry electrodes   │   │
   │              └────────────────────────────────┘   │
   │  method      [ 4-wire Kelvin — same as last ▾ ]   │
   │                                                   │
   │              [ 🔒 Lock prediction ]                │
   └──────────────────────────────────────────────────┘
```

**Three deliberate choices.**

⭐ **`Lock` is a commitment, not a save.** It gets the heaviest affordance on
the screen, a confirm-on-blur if the field is dirty, and after it fires the
inputs become **text, not disabled inputs** — a greyed-out field invites you to
look for the edit button; text says the decision is made.

**The method defaults to *"same as last time"*.** The common case is the third
run on the same rig, and retyping it is how the field goes empty.

**`because` is optional and never blocks.** It is the highest-value free text in
the product and the fastest thing to abandon under friction.

## 2.4 The review card

```
   ┌──── 1 of 4 ──────────────────────────────────────┐
   │  Zhang says impedance "varies with hydration"     │  the span, verbatim
   │  ──────────────────────────────────────────────   │
   │  proposed:  skin impedance ── relates_to ──→      │
   │             hydration          AMBIGUOUS 0.3      │
   │                                                   │
   │  ⚠ the passage does not say which direction       │  ← why it's here
   │                                                   │
   │  [A]ccept   [R]eject   [E]dit   [␣]skip           │
   └───────────────────────────────────────────────────┘
```

⭐ **The *why it's here* line is mandatory.** The queue holds only `AMBIGUOUS`
— things nobody but the student can settle — so every card must say what the
system could not decide. Without it the queue is a rubber stamp, and a rubber
stamp gets clicked through.

**Counter, not a progress bar.** `1 of 4` is finite and finishable; a bar
implies a chore.

## 2.5 The tension card

Framing comes from the backend's kind; **the card shape never changes**, so a
student learns one layout and reads six situations with it.

```
   ┌─ P1 · BOUNDARY ──────────────────────────────────┐
   │  Zhang 2019                    your 14 Mar sweep  │
   │  30–40 kΩ            ⚡         47.2 kΩ            │
   │  gel electrodes                dry electrodes     │
   │  ─────────────────────────────────────────────    │
   │  The source may not apply in your conditions.     │
   │                                                   │
   │  [ narrow the claim ]  [ they're comparable ]     │
   │  [ my setup is wrong ]           [ not now ]      │
   └───────────────────────────────────────────────────┘
```

⭐ **Two columns, never a verdict.** The system holds literature, belief and
bench, and its job is to put two of them side by side — **picking a winner is
the one thing it must not do**, because the student doing that is the entire
pedagogical point.

**`not now` is always present**, and dismissals lower priority rather than
deleting the tension. It comes back when new evidence lands.

---

# 3. Settings — small, and mostly about trust

Four groups, nothing else.

| Group | Contents |
|---|---|
| **Account** | project list, export (`mg export`), ⚠️ **delete everything** — with the plain-English consequence: *"your labels and measurements become unrecoverable; the shape of the graph and whether your predictions matched will survive as anonymous data"* |
| **Accessibility** | reduced motion · high contrast · CVD-safe mode (⭐ shapes-plus-hue, not hue alone) · Vim keys |
| **Cost** | spend by tier, budget cap, what happens at the cap (§4.7b) |
| **Model** | endpoint, the four tier choices. **Hidden behind an "advanced" toggle** — it is a real setting and not a normal student's business |

⚠️ **The erasure copy is the most important sentence in settings.** Saying only
*"delete everything"* when the ledger's structural half survives is a lie a
regulator would care about, and a student would too.

---

# 4. Notifications — three, and no more

⚠️ **Interrupting a student mid-build is how the feature gets turned off.**
Research is unambiguous and the backend already batches everything it can.

| | When | How |
|---|---|---|
| **P0 tension** | active work depends on something now contested | ⭐ inline, where they already are. **Never more than one at a time** |
| **Ingest finished** | a long parse completes | a quiet count on the Sources tab. No toast |
| **Resurrection** | a dead end's blocker changed | ⭐ **next Bench visit only.** It waited six weeks; it can wait for them to look up |

**Everything else accumulates.** The review queue, crossovers, staleness and
proposals are all pull, never push.

---

# 5. Offline — the week-3 bench moment

⚠️ **The abandonment cliff is week 3, at 1am, mid-debug** — frequently somewhere
with no signal. An offline mode that only shows a cached read is a demo.

| Works offline | Needs the network |
|---|---|
| ⭐ **the frontier** — it is a pure graph computation | `ask` (the turn protocol) |
| capture — notes, files, measurements | extraction of anything captured |
| ⭐ **predict and measure** — the moat loop, entirely local | embeddings |
| explain, path, timeline, the Map | crossovers |

⭐ **This is the argument that survived for graphology on both sides** (`06 §4.4`)
— not *"share one graph model"*, but **a student at a bench with no signal
asking what to do next, and getting an answer.**

**Captured events queue in a local ledger and replay on reconnect.** They are
events; ordering by `seq` is the only ordering; the merge is an append. ⚠️ The
one thing that must **not** happen offline is a `validated` event being
reordered relative to its `predicted` — the lock timestamp is what makes
calibration honest, so a queued prediction carries its original position.

---

# 6. Build order

Ordered so that **each step produces something testable by a real student**,
and so the riskiest assumption is tested earliest.

| | What | Days | Why here |
|---|---|---|---|
| **0** | ⚠️ **Run F4** | 0.5 | It can invalidate the palette, the node chip and the encoding matrix. Everything below assumes it passed |
| **1** | Tokens, node chip, the five states (§1, §2.1) | 1 | Every surface is built from these |
| **2** | ⭐ **Artifact — predict/measure** (`01 §4.3`) | 2 | The moat, and **F8 is the biggest unknown in the product**: will anyone type a prediction before they build? Testable in week 1 with no graph at all |
| **3** | Onboarding (`01 §8`) | 1 | Cold start already works in the backend. Cheap, and it is the first impression |
| **4** | Bench + tension card (`01 §4.1`, §2.5) | 2 | Proves the ranking is worth anything |
| **5** | Ask + explain (`01 §4.0`) | 2 | ⭐ The main verb. Needs the Tier 1a key |
| **6** | Sources + review (`01 §4.4a`, §4.4) | 2 | Gives the accept rate — the most important early number |
| **7** | Log + Share (`01 §4.5`, §4.6) | 2 | The first thing worth showing anyone |
| **8** | Map (`01 §4.2`) | 3 | ⭐ **Deliberately last.** It is the secondary view, and building it early is how a graph product becomes about the graph |
| **9** | Settings, notifications, offline (§3–§5) | 2 | Real, and none of it is the product |

**≈17 days of frontend work**, and step 8 is the one to cut if anything slips.

⚠️ **Step 5 is the only one blocked on something external** — everything before
it runs against the deterministic lane with no key at all.

---

# 7. What this document does not settle

- **F4** (§0) and the ten other doubts in `Frontend/04` — **F8** and **F11** are the two that can still move the product.
- ⭐ **F11 is not answered by any of this.** Every surface here assumes a *planning* posture; if the highest-value moment is really the 1am debug companion, §6's order is wrong rather than the components. **One afternoon watching a real student settles it, and no amount of design does.**
- Motion specifics for the tension card's two-column reveal — `03 §5` covers the class, not this instance.
- The Map's own component anatomy at ≤50 nodes; `06 §1` covers the node, not the canvas. **Partly settled by the demo build — see §8.**

---

# 8. What the demo build settled about the Map

Built against a year of seeded data (four projects, 644 nodes), which is the
first time the Map was exercised at a volume where the cap actually binds.
**Four things fell out that the specs above did not say.**

**8.1 A project node is a door, not a dot.** Clicking one replaces the view
with that project's scoped subgraph. This is what makes the cap navigable
rather than restrictive — ⭐ *navigation resolves the cap instead of
compromising on it*, and it is the difference between "the graph only shows
me 50 things" and "the graph shows me the right 50."

**8.2 The cap applies to the scoped view, not just the query result.** One
hop off a year-old project reaches ~120–146 nodes. ⚠️ It is very easy to
implement scoping, watch 644 become 146, call it a win and ship a view that
still fails the comprehension limit by 3x. **`SEED → EXPAND → RANK → CAP`
(`B11 §`) is four stages, and RANK→CAP is the pair that gets skipped** — the
first two produce a visible improvement on their own, which is exactly what
makes the omission survive review.

**8.3 Exits are exempt from the cap.** Other projects' hubs always survive
ranking. A scoped view whose only way out is a back button is a dead end, and
DOI will rank the doors off the screen if you let it — they are peripheral to
the current focus *by construction*.

**8.4 A capped view must report what it held back.** *"top 50 of 122 — ranked
by relevance"*, with a control to widen. ⚠️ Reporting only what was drawn
claims the project **is** 50 nodes; a student who later finds the other 72 has
been quietly misled by their own tool. Widening is opt-in and **never sticky
across scopes** — the limit is a property of the reader, not the dataset, so
one curious click must not silently un-cap every later view.

**DOI weights that worked** (`API(x) − D(x, focus)`, Furnas 1986): core 9 ·
project 8 · sub-node 5 · risk/gap 4 · concept/source 3 · other 1, plus
`min(3, log2(1+degree))`, minus 2.2 for anything outside the project.
⭐ **The distance penalty is doing the real work** — it is what stops a
high-degree neighbour from a different build outranking this build's own
unresolved risk.

**Still unsettled:** whether ~50 is right for *this* encoding. The measured
limit is for undifferentiated node-link diagrams; a view where hue, fill,
saturation and glyph each carry a channel may support more, or fewer. **F11's
observation session is where that gets answered, not the design.**

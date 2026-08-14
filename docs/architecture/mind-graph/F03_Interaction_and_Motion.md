# Interaction and Motion

**Frontend / 03.** Direct manipulation, selection, undo, keyboard, motion, and asynchronous feedback.
**Date:** 2026-08-10

---

# 1. Direct manipulation

## 1.1 Drag-and-drop is a state machine

Not an event. Every phase needs distinct feedback and distinct system behaviour.

| Phase | Visual | System |
|---|---|---|
| **drag start** | node lifts (drop shadow), cursor changes | capture source id, init ghost |
| **drag move** | ghost follows pointer; a spring link renders back to origin | track distance vectors |
| **drag over** | **target highlights; the spring snaps to it** | validate — type match, no cycle, not self |
| **drop success** | solidifies; layout absorbs the new mass | commit + push to undo stack |
| ⭐ **drop failure** | **animates back along a reverse trajectory** | discard delta, notify |

**Snap-back must be animated.** Not instant, not a disappearance. The kinesthetic reversal is what communicates *"the system rejected this"* — a node that simply vanishes reads as a bug, and a node that teleports back reads as a glitch.

**Drop targets get expanded hitboxes** (Fitts's Law). Missed drops are the most-cited failure of drag interfaces and they destroy trust faster than almost anything else.

## 1.2 What can be dragged

| Gesture | Result |
|---|---|
| node → node | ⭐ **create an edge.** A relation picker appears at the drop point, pre-filtered by what's legal between those two types |
| node → canvas | reposition + **pin** (the pin is the exception to "don't lock coordinates") |
| edge, perpendicular drag | adjust weight — pointer distance maps to a scalar |
| source passage → canvas | create a `Source`-backed claim with the span already attached |
| file → anywhere | ingest |

**Every one of these produces a *proposal*, not a mutation** — consistent with the backend's rule that nothing enters the graph ungated (Backend/05). The difference is that user-authored proposals auto-accept, since the human is already in the loop.

## 1.3 Failure states

Illegal actions are **rejected visibly, never silently**:
- invalid drop → snap-back + a one-line reason
- would-create-cycle on a `requires` edge → target flashes and refuses
- dragging a measurement outside its parent question → snap-back

---

# 2. ⭐ Selection without channel interference

The visual channels are fully consumed by data (`Frontend/02` §2). Using a fifth channel to indicate selection **violates the expressiveness principle** — it falsely implies the underlying data changed.

**Three safe mechanisms, used together:**

| Mechanism | Implementation |
|---|---|
| **Enclosure** | concentric halo, or an animated dashed stroke — "marching ants". Adds shape and motion without touching geometry, position, or hue |
| ⭐ **Negative highlighting** | **dim luminance and saturation of everything *not* selected.** Luminance is separable from hue, so selected nodes keep their colour identity and pop out by contrast |
| **Depth** | drop shadow lifts selection in z without altering the 2D bounding box |

**Negative highlighting is the primary.** It scales to any selection size, it never competes with the VSUP encoding (because it dims *everything else*), and it produces the focus effect without the distortion that focus+context techniques are prohibited for.

## 2.1 Multi-select

- **lasso** — freeform polygon; any node whose centre falls inside is selected
- **shift-click** — extend
- **⌘A within a filter** — select all currently visible
- **select-by-query** — *"all contested claims in this project"*

⭐ **A multi-select drag must be treated as a single rigid body with aggregated mass.** If ForceAtlas2 keeps computing intra-group repulsion during the drag, **the cluster visually explodes** and destroys the spatial relationship the user just built. This is a specific, easy-to-miss implementation bug.

---

# 3. ⭐ Undo

Far harder in a graph than in a document, and this is where the frontend mirrors the backend's hardest problem.

## 3.1 Command pattern

Every discrete action is a command object with `execute()` and `undo()`. Node-based tools converge on this (Blender, Houdini, Unreal Blueprints, n8n); **Autodesk Maya's `MDGModifier` is the architectural reference.**

## 3.2 Two kinds of undo, and they behave differently

```
SPATIAL UNDO          you dragged a node
  ⚠ DEBOUNCED — capture coordinates at DRAG START,
    commit one undo state at DROP, ignore everything between.
  Without this, "undo" rewinds the physics simulation by a few pixels.

SEMANTIC UNDO         you deleted, merged, retracted, or accepted something
  ⭐ DEEP STRUCTURAL MEMENTO of the affected subgraph — not a reverse-delta.
    Deleting a foundational concept may cascade to its dependents;
    undo must resurrect the parent, every child, and every connecting
    edge in exact prior state.
  On undo: trigger a brief STAGED layout stabilisation, never an
    instant snap to historical absolute positions.
```

## 3.3 Undoing a cascade

The hardest case, and it's ours by design. Retracting a measurement cascades through justification chains and can unsupport several conclusions.

**The UI must show what a retraction is about to do, before it does it:**

```
  Retract "47.2 kΩ at 50 kHz"?

  This will affect 4 things:
    ⚠ "Impedance tracks hydration"    → becomes UNSUPPORTED
    ⚠ "Dry electrodes are sufficient"  → becomes UNSUPPORTED
    ○ 2 edges will be deprecated

  Nothing is deleted. All of it is reversible.
                              [ Cancel ]  [ Retract ]
```

**"Nothing is deleted" is the important sentence.** Users restrict their interaction when they fear destructive action; visible, comprehensive reversibility is what unlocks experimentation. And it's *true* — the ledger is append-only.

---

# 4. Keyboard

## 4.1 The dual-mode insight

⚠️ ARIA's linear traversal is unusable for spatial data — tabbing serially through hundreds of nodes to reach a structural sibling destroys context.

**Two paradigms, both needed:**

| Mode | What it does |
|---|---|
| **Structural** | move along *edges* — to parent, child, sibling — regardless of screen position |
| **Spatial** | jump to the geographically *nearest* node in a direction, regardless of edges |

## 4.2 Bindings — arrows by default, Vim opt-in

⚠️ **Vim modal bindings are detrimental as a default** for undergraduates — steep curve, accidental deletions, mode confusion. Our users are ECE students, not software engineers.

```
DEFAULT
  ← → ↑ ↓          structural traversal (along edges)
  ⌥ + arrows       spatial traversal (nearest node in that direction)
  Space            select / deselect
  ⇧ + click        extend selection
  Enter            open in the context pane
  Esc              clear selection / exit mode
  ⌘Z / ⇧⌘Z         undo / redo
  ⌘K               command palette
  ⌘\               toggle left pane
  /                focus search
  ?                shortcut overlay

REVIEW MODE
  A accept · R reject · E edit · Space skip · ⌘A bulk-accept selection

OPT-IN (settings)
  Vim bindings — h/l structural · j/k siblings · W/B spatial · v visual · d delete · u undo
```

## 4.3 Command palette — with the known failure handled

⚠️ **Recall over recognition.** A palette shows an empty box and demands the user *recall* vocabulary. GUI menus let them *recognise*. For a six-week user, learning a command vocabulary is an unacceptable tax.

**Mitigations, all required:**
- every GUI action **displays its shortcut** next to it — progressive disclosure
- **fuzzy matching** and **synonym recognition** — *"new diagram"* → `open map`
- the palette is **never the only path** to any feature
- recent and suggested commands shown on open, so it works before you know anything

---

# 5. Motion

## 5.1 ⭐ Staged, never simultaneous

Measured result: breaking a transition into discrete sequential phases **significantly improves change tracking and reduces error** versus animating everything at once.

**The expansion recipe** — expanding one node into its neighbours:

```
Stage 1  TOPOLOGY PREP     180ms   layout expands, opening a geometric void
                                   around the target; surrounding context holds
Stage 2  FOCAL EXPANSION   140ms   target scales down / fades; children fade in
                                   at the exact centre of the new void
Stage 3  DISTRIBUTION      260ms   children animate outward to their local
                                   ForceAtlas2 equilibrium
                           ────
                           ~580ms  total
```

Animating size, position, edge routing, and opacity simultaneously produces occlusion, collision, and chaos. **The staging is what makes an expansion legible.**

⭐ **New children are injected at the parent's exact x/y** so nothing flies in from the canvas origin — continuous repulsion pushes them outward organically.

## 5.2 Don't lock coordinates

Mental-map preservation is a **measured null result** — no significant effect on task performance; users preferred it but gained nothing.

**So: let the layout restructure organically** when topology changes materially. Don't warp new nodes into a rigid outdated map. The only exception is nodes the user has **explicitly pinned** — that's an intentional user statement, not an inferred preference.

*(Spend the effort on §5.1 instead, which is measured to help.)*

## 5.3 Settling feedback

⭐ **Map the layout's "swinging" value to a subtle visual indicator** — light motion blur or a low-opacity ghost trail — so the user reads the graph as *settling toward equilibrium* rather than glitching.

`Speed(n) = k / (Swinging(n) + 0.1)` — nodes repeatedly asked to change direction get slowed, preventing local chaos from rippling outward. **Strong gravity** keeps ~50 nodes inside the viewport and stops disconnected components drifting off-canvas.

## 5.4 `prefers-reduced-motion`

Continuous stabilisation can trigger vestibular discomfort.

**When the flag is set, do not render the iteration at all** — compute the layout asynchronously and **crossfade** nodes to final positions. Staged transitions become simple crossfades. Nothing is lost except the animation.

## 5.5 Durations

| Motion | Duration | Easing |
|---|---|---|
| hover feedback | 80ms | ease-out |
| selection | 120ms | ease-out |
| pane transitions | 200ms | ease-in-out |
| staged expansion | ~580ms total | per stage |
| snap-back on failure | 240ms | ease-in-back — the overshoot reads as rejection |
| label crossfade | 300ms | linear |

**Nothing exceeds ~600ms.** Beyond that it stops reading as feedback and starts reading as waiting.

---

# 6. Asynchronous feedback

Ingestion takes minutes; analysis runs nightly. The UI must never block, and it must never lie about being finished.

## 6.1 Optimistic UI

On any user-initiated change: **render the result immediately**, reconcile in the background. The local store is written first; the sync engine catches up.

On expand: a **pulsing skeleton node at the interaction site**, not a global spinner.

## 6.1a ⭐ Deferred critique — the one async case that can mislead *(added 2026-08-10, Backend/05 §4.2)*

The backend decoupled **display** from **acceptance**: an answer streams immediately while the Critic runs concurrently, and its verdict resolves about a second later. That turns three sequential model round-trips into one perceived hop.

⚠️ **It is also the only place in the product where the interface can show something that later turns out to be wrong**, so it needs stricter rules than §6.1's optimistic UI — which reconciles a change the *user* made, not a claim the *system* made.

**Three rules:**

**1. The pending state is visible from the first token.** A quiet `◌ checking` sits with the answer from the moment it starts streaming. The student is never shown a bare answer that *looks* settled and then isn't — ⭐ **the uncertainty is on screen before the certainty is.**

**2. The badge resolves in place. It never re-flows the text.** Reserve the row at stream start. Content that jumps while it's being read is the specific failure that makes people stop trusting streamed interfaces, and it is entirely avoidable.

**3. `CRITICAL` demotes the answer; it does not merely annotate it.** On a P0 verdict the prose desaturates and the tension takes visual primacy. Anything lower resolves quietly. **The ~1-second uncritiqued window is bounded by the Q8 priority tiers**, which is why widening that trigger mattered more than it appeared to at the time.

**Motion:** the badge is a §5.1 staged transition, not a simultaneous one — reserve, then fade in, never slide. And it is exempt from §6.1's optimistic pattern: **nothing is written to the ledger until the Critic returns**, so there is no local write to reconcile. The student reads early; **the graph waits.**

## 6.2 Layout in a Worker

The force simulation runs in a Web Worker, streaming coordinates back with **dampened interpolation** — never render every micro-jitter.

## 6.3 Long operations

```
ingesting a 40-page PDF     →  a card in the left pane, progress by stage
                               ("extracting… resolving… 12 proposals ready")
nightly analysis            →  silent. Results appear on the Bench next open.
                               ⭐ NEVER a live feed — continuous peripheral
                               motion is a measured negative
```

## 6.4 Truncation is always explicit

If a query is budget-limited, **say so.** A student who doesn't know a result was truncated will read it as complete — a correctness failure dressed as a performance optimisation.

---

# 7. Ambient surfacing

⚠️ **Habituation is the failure mode.** Ambient signals shown too often without high relevance get **filtered out entirely** — the fate of overactive linters and continuous ghost text.

**Rules:**

| Rule | Why |
|---|---|
| **Pseudo-ambient** — silent between events, triggered at milestones | silent periods actively mitigate habituation |
| **Medium contrast**, not maximum | high intensity is not required for peripheral visibility |
| **Standardised position** — always the same corner | position consistency does the work that intensity would |
| **~2 Hz** if a temporal cue is needed | maximises peripheral visibility without demanding central processing |
| **4.5:1 contrast reserved** for alerts that must break through habituation | rare by design |
| ⛔ **No continuous motion in the periphery** | measured negative — traveling and zooming motions are actively distracting |

**What earns an ambient signal:** a proposal queue crossing threshold; a claim you rely on going stale; a new contradiction appearing. **What doesn't:** anything routine, anything the user could find by looking.

---

# 8. Review Mode

The highest-throughput surface, and the one where interaction craft matters most.

```
┌────────────────────────────┬──────────────────────────────┐
│  local graph context       │  the claim                    │
│  (5–8 nodes, not 50)       │  the source passage, highlighted│
│                            │  confidence · citation state   │
│  the proposed edge         │  what it would change          │
│  rendered dashed           │                                │
├────────────────────────────┴──────────────────────────────┤
│  A accept   R reject   E edit inline   ␣ skip   ⌘A bulk    │
│                                        ▸ 4 of 12           │
└────────────────────────────────────────────────────────────┘
```

- **Vertical metadata sidebar**, not ephemeral tooltips — reviewers need to read without the panel vanishing
- **Bulk accept** for high-confidence clusters via lasso
- **Inline correction** — fix a value without leaving; state transitions `AI-suggested → human-corrected`, and that transition is a training signal
- **Cap the session.** Progress shown as `4 of 12`, never `4 of 340`

---

# 💡 Visionary Vector — reversibility is the feature, not the safety net

§3.3 shows a confirmation dialog before a retraction cascades. It reads like a guardrail. It's actually the most distinctive interaction in the product.

Every other tool in this space is **write-only about belief.** You add a note; you never un-believe it. Obsidian has no concept of retraction. Atlas has no concept of changing your mind. The best they offer is deleting something, which destroys the fact that you ever thought it.

We can show a student, before they act: *"retracting this will unsupport two conclusions you built on it — and here they are."* Then let them do it, reversibly, with the history intact.

**That's not error prevention. That's a visualisation of intellectual consequence.** It makes the structure of your own reasoning visible at exactly the moment it matters — when you're about to abandon something you believed.

And it inverts the usual relationship between safety and exploration. Research on tool adoption is clear that users restrict interaction when they fear destructive action, and that **"when the cost of experimentation is reduced to zero, users teach themselves the deeper capabilities."** Because our ledger is append-only, retraction is *genuinely* free — we're not promising reversibility as a UX kindness, we're exposing a property the architecture already has.

The deepest version: a student who can retract cheaply will **retract more**, which means they'll change their mind more readily, which is the actual skill we claim to be teaching. The interaction doesn't just permit good epistemic behaviour — **it makes it the path of least resistance.**

# Frontend Research — The Complete Picture

**Revision 2** — 2026-08-09. Rebuilt with R4 (visual encoding), R5 (interaction & motion), R6 (PKM UX & retention). ~97 additional citations.
**What this is:** every frontend finding from the entire research effort, in one document, so the frontend can be designed without re-reading nine sources.
**Status:** ⭐ **frontend research is now design-ready.** The remaining gaps are decisions, not unknowns.

> **The three sentences that matter most:**
> 1. A knowledge graph stops being comprehensible at **~50 nodes**; the software doesn't struggle until **25,000**. Almost every performance instinct is aimed at the wrong problem.
> 2. **The force layout consumes the two most effective visual channels** (position and region), so everything else — type, confidence, support, staleness — must be encoded on weaker channels, and the order in which you spend them is not optional.
> 3. **The abandonment cliff is week 3**, when the project shifts from research to debugging and time spent organising drops to zero. Anything requiring upkeep dies there.

---

# 1. The limits

## 1.1 Three thresholds, three orders of magnitude apart

| Limit | Threshold | Evidence |
|---|---|---|
| **Comprehension** | **~50 nodes** dense · ~100 sparse | ⭐ measured — EEG, pupil dilation, HRV |
| Community folklore | ~200 | anecdote |
| **Performance** | ~25,000 | official Obsidian team statement |

The measured study ([arXiv 2008.07944](https://arxiv.org/abs/2008.07944)) found cognitive load rose with difficulty **then fell** — participants **gave up**. The failure mode is abandonment, and it's invisible in analytics. Global layout features (edge crossings, overall size) mattered **more than the properties of the target being searched for**.

## 1.2 The bottleneck is the physics, not the pixels

Obsidian's freeze is **single-core CPU** with the GPU idle. Graph latency is asymmetric: ingest/extraction is API/GPU-bound; clustering and layout are CPU-bound. **Run layout in a Worker and render less** — don't reach for a faster renderer.

---

# 2. ⚠️ The null and negative results

The most important section. Several contradict standard advice.

| Finding | Status |
|---|---|
| **Node-link diagrams and learning outcomes** | null to negative; retention often *drops* vs linear text |
| **Mental-map preservation** | ⭐ **NULL.** 48 tasks/user. No significant effect on performance. Users *preferred* it; preference yielded no measurable benefit. Only helps when tracking rapidly moving targets in real time |
| **Focus+context vs overview+detail** | ⭐ **NEGATIVE.** Focus+context is harder at small display sizes; overview+detail superior across *all* sizes, especially for comparison. **R4 concludes fisheye distortion must be strictly prohibited** |
| **Blur / fuzziness for uncertainty** | ⭐ **NEGATIVE.** Blurring **artificially expands perceived node area**, corrupting any quantitative data encoded in size |
| **Transparency for uncertainty** | implies physical absence or backgrounding, not variance |
| **Error bars on a 50-node graph** | unreadable thicket; destroys data-ink ratio |
| **Continuous motion in the periphery** | ⭐ **NEGATIVE.** Fails to support focus; traveling and zooming motions in peripheral vision are highly distracting |
| **Streaks / gamification** | ⭐ **BACKFIRE** in hardware contexts — see §7.2 |
| **Quantified-self dashboards** | ⭐ **BACKFIRE.** Tracking "time in tool" or "notes created" rewards bureaucratic busywork and penalises real lab work |
| **Vim-style modal bindings as default** | detrimental for non-CS undergrads — opt-in only (§5.3) |
| **Evidence base itself** | ¾ of graph-visualisation evaluation studies use ≤100 nodes; one focus+context study had variance so extreme the data was discarded |

---

# 3. Visual encoding — the hard constraint

## 3.1 The channel hierarchy

| Class | Channel | Data type | Rank |
|---|---|---|---|
| Magnitude | spatial position (common scale) | quantitative/ordinal | **1** |
| Magnitude | length | quantitative/ordinal | 2 |
| Magnitude | area (2D size) | quantitative/ordinal | 3 |
| Magnitude | colour luminance / saturation | quantitative/ordinal | 4 |
| Identity | spatial region / grouping | categorical | **1** |
| Identity | colour hue | categorical | 2 |
| Identity | shape | categorical | 3 — **max ~5–7 shapes** |

**Separable vs integral:** hue and size are separable (decodable independently); width and height are integral (fused into one perceived area). Only separable pairs can carry independent variables.

## 3.2 ⭐ The constraint that decides everything

> **The force-directed layout preemptively consumes spatial position AND spatial region — the #1 magnitude and #1 identity channels — to express topology.**

Everything else must be spent on weaker channels, in a strict order:

| Our attribute | Channel | Note |
|---|---|---|
| **node type** (6 categories) | **colour hue** | best remaining identity channel |
| **support state** (4, incl. contested) | **shape** — keep to ~3 distinct forms | shape saturates fast; reserve for low cardinality |
| **importance / centrality** | **area** | best remaining magnitude channel |
| **confidence tier** (3 ordinal) | **luminance**, or a **concentric inner ring / stroke width** | an inner ring encodes an ordinal without disturbing perceived outer area |
| **edge weight** | **line width** | scales naturally with perceived structural load |
| **relation type** | **stroke-dash texture** or a highly restricted edge palette | preserves perceived geometric thickness |

**Selection must not consume a data channel** — see §4.2.

## 3.3 Uncertainty — what actually works

**Value-Suppressing Uncertainty Palettes (VSUPs).** As uncertainty rises, aggressively **desaturate toward neutral grey**. This defeats the cognitive trap where users read bright saturated colour as *significant* when it's merely noisy. ⚠️ VSUPs **collapse at low resolution, on uncalibrated monitors, and under CVD** — so they must always be paired with an explicit numeric tooltip on inspection.

**Hypothetical Outcome Plots (HOPs).** Animate a finite set of discrete draws from the distribution. Humans are poor at Bayesian reasoning and good at **natural frequencies**, so uncertainty becomes countable events. ⚠️ **Multiple-object-tracking limit is ~5 targets** (Pylyshyn & Storm) — therefore HOPs must be **strictly localised, the layout frozen during animation, and triggered on demand only** (hover or explicit selection). Never ambient.

**Sonification.** Pairing audio with visual gives measurably faster reaction times. ⚠️ **Preferred mappings ≠ effective mappings** — high pitch → high brightness is aesthetically liked but poor for variance. Use **dissonance, irregularity, tempo modulation** to convey unreliability.

## 3.4 Contradiction and absence

**Contradiction — use Scite's model, not Kialo's.** Kialo's strict pro/con hierarchy **breaks down in a non-hierarchical force-directed topology** with cycles and multi-directional dependencies. Scite's three directional vectors map cleanly:

```
supporting     solid, cool-toned directional vector       (stability)
contradicting  sharp dashed or zigzag, warm high-alert    (pre-attentive pop-out)
mentioning     thin, low-luminance grey                   (deliberately suppressed)
```

**Absence — "Ghost Nodes."** ⚠️ The dangerous anti-pattern is leaving a node blank, defaulting to zero, or omitting it — **users read a zero as a literal measurement.** Instead: **heavily dashed perimeter + completely hollow, transparent fill**, exploiting the Gestalt principle of closure so the perceptual system registers it as explicitly incomplete but necessary.

*(This is exactly our phantom node, and now it has a specification.)*

## 3.5 Colour, dark mode, CVD

- **Dark mode:** saturated colours at high luminance cause **halation** — glow/blur that accelerates eye fatigue over long sessions.
- Build palettes in **perceptually uniform spaces (Oklab / CIELAB)**, never raw RGB.
- **Categorical: 5–7 desaturated pastel hues** — distinct identity without bloom.
- **Ordinal: single-hue sequential varying by lightness, not saturation.** In dark mode invert — low values dark and receding, high values luminous and commanding.
- **~15% of users have some CVD**; red-for-bad/green-for-good is illegible to them. **Colour must always be redundantly encoded** with shape, stroke pattern, or icon.
- WCAG 2.1 AA: **3:1 for large graphical objects, 4.5:1 for text**.
- Ship a **high-contrast toggle** that strips all categorical hue and replaces it with geometric hatch patterns — diagonal striping, cross-hatching, stippling.

## 3.6 Labels

**Point-Feature Label Placement is NP-hard**; even the four-slider decision problem is NP-complete. Moving one label to resolve an overlap can cascade across the canvas.

| Algorithm | Cost | Behaviour |
|---|---|---|
| Greedy sweepline | O(n log n) | fast, suboptimal — leaves crowded clusters entirely unlabelled |
| **Force-directed labels** | medium | fluid, responds to interaction; can oscillate in constrained space |
| Simulated annealing | high | near-optimal, but computes in epochs that **freeze the UI** |

⚠️ **R4 and R5 disagree here** — see §8.1 for the resolution.

**Semantic zoom for text is mandatory.** At macro scale show only truncated identifiers (`DOC-14`, `EQ-02`, an author surname). Full titles, abstracts, and values appear only on hover or selection. Premium canvas space goes to structure and encoding, not to overlapping text.

---

# 4. Interaction

## 4.1 Direct manipulation

Drag-and-drop is a **state machine**, not an event:

| Phase | Visual | System |
|---|---|---|
| Drag start | node lifts (drop shadow), cursor changes | capture source, init ghosting |
| Drag move | ghost follows pointer, spring link renders | track vectors against target matrices |
| Drag over | **target highlights, spring snaps to port** | topological validation (acyclicity, type match) |
| Drop success | solidifies, layout absorbs new mass | commit + push to undo stack |
| **Drop failure** | ⭐ **animates back along a reverse trajectory** | discard delta, notify rejection |

**Snap-back must be animated**, not instant and not a disappearance — the kinesthetic reversal is what communicates *"the system rejected this"*. Drop targets need expanded hitboxes (Fitts's Law); collision detection must strictly reject invalid combinations.

**Parametric manipulation:** dragging an edge perpendicular to its axis to thicken it maps pointer distance directly to a scalar weight — a tactile way to edit quantitative values.

## 4.2 ⭐ Selection without channel interference

The channels are already exhausted by data (§3.2). Using a fifth channel for selection **violates the expressiveness principle** — it falsely implies the underlying data changed. Three safe mechanisms:

1. **Enclosure / stroke dynamics** — concentric halo or animated dashed stroke ("marching ants"). Adds shape and motion without touching geometry, position, or hue.
2. ⭐ **Negative highlighting** — dim the **luminance and saturation of everything *not* selected.** Luminance is separable from hue, so the selected items keep their colour identity and "pop out" by contrast.
3. **Depth / shadow (2.5D)** — an aggressive drop shadow lifts selection in z without altering the 2D bounding box.

**Multi-select drag:** ⭐ **the selection must be treated as a single rigid body with aggregated mass.** If ForceAtlas2 keeps computing intra-group repulsion during the drag, **the cluster visually explodes** and destroys the spatial relationships the user just established.

## 4.3 ⭐ Undo in a dependency graph

Far harder than linear undo. Node-based tools (Blender, Houdini, Unreal Blueprints, n8n) all use the **Command Pattern**; **Autodesk Maya's `MDGModifier` is the architectural gold standard**.

**Cascading undo:** deleting a foundational concept may prune every dependent measurement and claim. Undo must resurrect **the parent, all children, and every connecting directed edge in exact prior state** — which requires storing a **deep structural memento of the affected subgraph**, not a reverse-delta.

⭐ **Spatial and semantic undo must be separated.** ForceAtlas2 repositions continuously; recording every micro-frame would make "undo" rewind the physics by a few pixels. Therefore:

```
spatial undo    debounced — capture coordinates at DRAG START,
                commit one undo state at DROP, ignore everything between
semantic undo   full structural memento
                → on undo, trigger a brief STAGED layout stabilisation
                  rather than snapping to historical absolute positions
```

*This maps directly onto our backend's retraction cascade — the UI-side mirror of the same problem.*

## 4.4 Keyboard navigation — dual-mode

ARIA forces **strictly linear, one-dimensional traversal**. Tabbing serially through hundreds of nodes to reach a structural sibling destroys context and is unusable. The fix is two distinct paradigms:

**Structural traversal (graph-theoretic):** move along edges — to parent, child, or sibling — regardless of where the layout placed them.
**Spatial traversal (visual):** jump to the geographically nearest node in a direction, by shortest Euclidean distance, regardless of edges.

Plus a visual/multi-select mode, delete-with-cascade, and undo.

⚠️ **R5 and R6 disagree on whether these should be Vim bindings** — see §8.2.

**Dual-layer accessibility:** the visual canvas is decoupled from the screen-reader encoding. Sighted power users traverse at speed; an **invisible HTML table plus a live ARIA region** announces the focused node's properties (*"Node: Quantum Entanglement, Claim: True, 5 connections"*). Focus indicators need ≥3:1 contrast, 4.5:1 recommended.

---

# 5. Motion

## 5.1 ⭐ Staged, never simultaneous

**Heer & Robertson** measured that breaking a transition into discrete sequential phases **significantly improves change tracking and reduces error** versus animating everything at once.

The concrete recipe for expanding one node into fifteen children:

```
Stage 1  TOPOLOGY PREP    layout expands, creating a geometric void
                          around the target — surrounding context preserved
Stage 2  FOCAL EXPANSION  target scales down / fades; children fade in
                          at the exact centre of the new void
Stage 3  DISTRIBUTION     children animate outward to their local
                          ForceAtlas2 equilibrium positions
```

Without staging, animating size + position + edge routing + opacity simultaneously produces occlusion, collision, and visual chaos.

*(One caveat: a cited paper — "The Not-so-Staggering Effect of Staggered Animated Transitions" — questions **staggering** specifically. Staging ≠ staggering, but worth reading before over-investing.)*

## 5.2 Don't lock coordinates

Given the mental-map null result, R5's conclusion is explicit and **liberating**: don't obsessively lock node coordinates when a major topological change occurs. **Let ForceAtlas2 restructure organically rather than warping new nodes into a rigid outdated map.** The computational cost of forced coordinate locking is not justified by measured cognitive benefit.

*(Exception: nodes the user has explicitly pinned.)*

## 5.3 Layout feedback

⭐ **Map the ForceAtlas2 "swinging" value to a visual indicator** — subtle motion blur or a low-opacity ghost trail — so the user intuitively understands the graph is *settling* toward equilibrium rather than glitching.

`Speed(n) = k / (Swinging(n) + 0.1)` — a node asked to change direction repeatedly gets slowed, preventing local chaos from rippling outward. **Strong gravity** is critical to keep ~50 nodes inside a laptop viewport and stop disconnected islands drifting off-canvas.

## 5.4 `prefers-reduced-motion`

Continuous stabilisation can trigger vestibular discomfort. When the flag is set: **do not render the swinging iteration at all** — compute the layout asynchronously in the background and crossfade nodes to their final positions.

---

# 6. Asynchronous feedback

Ingestion takes minutes; analysis runs nightly. The UI must never block.

- **Optimistic UI**: on expand, immediately render a pulsing skeleton node *at the interaction site* while the Worker computes.
- **Dampened interpolation** when streaming intermediate coordinates — don't render every micro-jitter.
- **Two-pass labels**: render opaquely at naive fixed positions first (one-slider, top-right), then **crossfade** into optimal placements when the solver finishes. If no legible placement exists for a dense cluster, **fall back to an aggregate label** (*"Cluster: 14 claims"*) and let the user expand on demand.

---

# 7. Retention and real-time usefulness

## 7.1 ⚠️ The data doesn't exist

> **There is no publicly available, peer-reviewed retention, churn, or DAU data for leading PKM applications.** These analytics are guarded trade secrets.

What is established: knowledge workers spend ~**20% of productive time searching for information**, and post-mortems consistently identify the **"organisational tax"** — the cognitive and temporal cost of tagging, categorising, and maintaining hierarchy — as the primary driver of churn.

## 7.2 ⭐ The week-3 abandonment cliff

> In a six-week academic project, abandonment occurs at **the transition from research to execution**. Weeks 1–2, students eagerly capture datasheets and component lists. **By week 3, hardware debugging begins, stress peaks, and time spent "preparing to think" drops to zero.**

If the tool requires manual curation to stay useful, it is discarded there — in favour of chaotic but zero-friction alternatives (unformatted code snippets in a messaging app).

**Design consequence: anything that requires upkeep must survive week 3 without it.**

## 7.3 ⭐ Streaks and dashboards backfire

**Streaks:** hardware progress is nonlinear — intense lab work, then days waiting for components. A missed day breaks the streak, creating a **severe demotivation effect** that turns the tool "from a helpful assistant into a judgmental taskmaster." **Gamification measures the meta-work (using the tool) rather than the actual work (building the hardware).**

**Quantified-self dashboards:** tracking time-in-tool, notes created, or lines written **rewards bureaucratic busywork**. A student spending 40 hours at an oscilloscope and zero in the tool is *visually penalised* — inducing guilt and prompting abandonment.

**What to show instead:**
- **Uncertainty reduction** — unknowns resolved, not keystrokes logged
- **Physical component state** — ordered → in transit → received → tested → integrated
- **Document accretion** — visual diffs and time-lapse of how the project document evolved

*This validates our calibration metric and the `predicted → measured` loop: it measures the real work, not the tool usage.*

## 7.4 Ambient surfacing — calm technology

Peripheral information must require **the smallest possible attention**, using **low-bandwidth sensory channels**. If an ambient display requires cognitive decoding — reading a complex textual popup — it forces a context switch and violates the principle.

⭐ **Habituation is the failure mode.** Ambient alerts shown too often without high relevance get **filtered out entirely** — the fate of overactive linters and continuous ghost text. Counter-measures:
- **medium contrast**, not maximum
- standardised horizontal/vertical positioning
- subtle temporal change — **~2 Hz** flashing maximises peripheral visibility without demanding central processing
- **high contrast (4.5:1) reserved for alerts that must break through habituation**

⭐ **Pseudo-ambient displays** — silent or invisible for periods, triggering only at intervals or contextual milestones. The **silent periods actively mitigate habituation.** Update on a milestone (a peer committed code, a datasheet changed), never as a continuous live feed.

## 7.5 Information architecture

| Paradigm | Strength | Failure mode |
|---|---|---|
| **Document-first** | deep reading, formal docs, high-res embeds | high organisational friction; silos; linear format **violates separability** when mixing chat and code |
| **Chat-first** | zero-friction capture, fast Q&A | **severe knowledge decay** — solutions buried in history; fails at spatial organisation |
| **IDE-style** | ⭐ **separable visual channels** for distinct data types; most native to engineers | high visual complexity; window management fatigue; hard on small screens |

> **Recommended hybrid: an IDE-style desktop layout centred on a document editor, plus a chat-like input that appends to the structured document without leaving context.** Spatial separation of an IDE, zero-friction input of a chat.

## 7.6 Command palettes

⚠️ **Recall over recognition failure.** A palette presents an empty box and demands the user *recall* proprietary vocabulary; GUI menus let them *recognise* options by scanning. For a six-week user, learning a command vocabulary is an unacceptable tax.

Mitigations: **progressive disclosure** (show the keyboard shortcut next to every GUI action), **fuzzy matching**, **synonym recognition** (*"new diagram"* → `create spatial canvas`), and never rely on the palette as the only path to a feature.

## 7.7 Empty states

⚠️ A blank screen is **cognitively paralysing** and reads as "this tool requires upfront labour."

⭐ **Eradicate the empty state with functional synthetic data.** Pre-populate the workspace with a template that mirrors the real use case — a mock bill of materials, a firmware placeholder, a sample integration-test checklist. **The student learns by modifying working example data** rather than reading a manual.

**No unskippable modal tours** — universally despised by technical audiences and clicked through without comprehension.

**Safe exploration:** users restrict interaction when they fear destructive action. A visible, comprehensive undo (and an accessible history log) is what unlocks experimentation — *"when the cost of experimentation is reduced to zero, users teach themselves the deeper capabilities."*

## 7.8 Mobile — capture and review only

**Do not pursue feature parity.** Two use cases:

1. ⭐ **Ubiquitous capture** — photographing an oscilloscope trace, a burnt resistor, a whiteboard. A massive **Quick Capture affordance immediately on launch**, bypassing *all* organisational requirements: append a timestamp and location, push straight to the daily note or inbox. Tagging and linking are deferred to the desktop.
2. **Rapid review** — fast, offline-capable search and legible read-only views. Editing restricted to simple text appends.

⭐ **Pseudo-ambient haptics:** a brief localised vibration when a long compile finishes or a teammate uploads a schematic — letting the student stay focused on soldering without looking at a screen.

---

# 8. ⚠️ Contradictions between the reports, and how I'd resolve them

## 8.1 Label placement — R4 vs R5

- **R4:** use **force-directed** label placement; simulated annealing computes in epochs that briefly freeze the UI, which breaks the illusion of a reactive workspace.
- **R5:** use **simulated annealing** with a two-pass render — naive positions first, crossfade to optimum when the solver finishes.

**Resolution: take R5's staging with R4's algorithm.** Two-pass rendering is right — never let labels blink erratically while a solver runs. But the refinement pass should be **force-directed inside the Worker**, not annealed epochs, because our graph is *continuously manipulated*. Annealing assumes a static target; ours moves whenever the user drags anything.

## 8.2 Vim bindings — R5 vs R6

- **R5:** dual-mode Vim navigation (`h/l` structural, `j/k` siblings, `W/B` spatial, `v` visual, `d` delete, `u` undo).
- **R6:** ⚠️ **Vim modal bindings are "highly detrimental" as a default** for undergraduates — steep learning curve, accidental deletions, erratic navigation when users forget which mode they're in. Must be **explicitly opt-in**, with the baseline built on universally understood modifiers and arrow keys.

**Resolution: R6 wins on the key choice; R5 wins on the concept.** Our users are ECE undergraduates, not software engineers.

```
default    arrows            = structural traversal (along edges)
           alt + arrows      = spatial traversal (nearest node in direction)
           space             = select      shift+click = extend
           cmd/ctrl+z        = undo
opt-in     Vim bindings as a settings toggle for those who want them
```

The **dual-mode traversal idea is the valuable part** and is orthogonal to which keys trigger it.

## 8.3 Mental map — R4's internal inconsistency

R4 §6.2 states mental-map preservation "must be a primary objective," then cites the same null result R5 uses to argue the opposite. **The evidence wins:** don't lock coordinates except where the user has explicitly pinned. Spend the effort on staged transitions instead, which *are* measured to help.

---

# 9. Design implications — the assembled conclusion

| # | Rule | Source |
|---|---|---|
| 1 | Working view ≤ ~50 nodes. Exceeding it is a bug | measured limit |
| 2 | **Overview + detail. No fisheye, no focus+context distortion** | negative result |
| 3 | Never open on the full graph — failure is abandonment on first impression | §2 |
| 4 | Reduce edge crossings before optimising anything else | global features dominate |
| 5 | **Spend channels in order: hue→type, area→importance, shape→state (≤3), inner ring→confidence, line width→weight, dash→relation** | §3.2 |
| 6 | **Selection uses enclosure, negative highlighting, or shadow — never a data channel** | §4.2 |
| 7 | **Uncertainty via VSUP desaturation + numeric tooltip.** HOPs localised and on-demand only. **Never blur** | §3.3 |
| 8 | **Contradiction = dashed/zigzag warm vector. Absence = dashed hollow ghost node.** Never blank, never zero | §3.4 |
| 9 | Perceptually uniform colour space; 5–7 desaturated pastels; redundant encoding; high-contrast hatch toggle | §3.5 |
| 10 | Semantic zoom for text — truncated IDs at macro, full strings on hover | §3.6 |
| 11 | **Staged transitions (topology prep → focal expansion → distribution)** | Heer & Robertson |
| 12 | **Don't lock coordinates** except explicit pins | null result |
| 13 | Layout in a Worker; map swinging to a settling indicator; honour `prefers-reduced-motion` | §5 |
| 14 | **Multi-select drags as a rigid body with aggregated mass** | §4.2 |
| 15 | **Debounced spatial undo; deep structural memento for semantic undo** | §4.3 |
| 16 | Dual-mode keyboard traversal on arrows; **Vim opt-in only** | §8.2 |
| 17 | Invisible HTML table + live ARIA region alongside the canvas | §4.4 |
| 18 | **No streaks, no time-in-tool metrics.** Show uncertainty reduction and component state | §7.3 |
| 19 | **Pseudo-ambient, milestone-triggered, ~2 Hz, medium contrast.** No continuous peripheral motion | §7.4 |
| 20 | IDE-style desktop layout + chat-style zero-friction input | §7.5 |
| 21 | **Eradicate the empty state with functional synthetic data.** No modal tours | §7.7 |
| 22 | Command palette always paired with visible GUI + shortcut hints + fuzzy/synonym matching | §7.6 |
| 23 | **Mobile = Quick Capture + review only.** Haptic pseudo-ambient | §7.8 |
| 24 | **Design for week 3** — anything requiring upkeep must survive without it | §7.2 |
| 25 | Vertical metadata sidebars, bulk lasso actions, dual-pane graph↔table | Label Studio / Prodigy |

---

# 10. What's still open — decisions, not unknowns

1. Is the overview pane **structural** (a minimap) or a **state dashboard** (calibration, contradictions, reachable gaps)? *The second is more useful and only we can build it.*
2. How exactly are phantoms rendered so they read as **opportunity** rather than incompleteness?
3. Full sync engine (PowerSync/Replicache) or plain SSE for a single-user v1?
4. Does **Data Navigator** mature enough to be the accessibility answer rather than the fallback?
5. What replaces the graph when a list serves better — and who decides?
6. Does the synthetic-data onboarding conflict with our **cold-start graph** (Backend/07 §1)? *Probably complementary: skeleton seeds real structure, synthetic template seeds the workflow.*

---

# 💡 Visionary Vector — the frontend's real job is rendering doubt

Every graph UI in existence encodes exactly two things: **a node exists, and a link exists.** Colour is decorative or hand-assigned. That's true of Obsidian, Atlas, Graphify, and every PKM tool in the research.

Our backend produces something categorically richer: every node knows **how strongly it's believed, whether it's disputed, how well-grounded its evidence is, whether it's gone stale, and whether it exists at all yet.**

R4 and R5 just handed us the vocabulary for all of it — VSUP desaturation for uncertainty, dashed zigzag vectors for contradiction, hollow ghost nodes for absence, concentric rings for confidence, **and inverted physics that push a refuting source away from what it refutes.**

So the frontend's job isn't drawing a network. **It's rendering doubt** — making *"you're confident about this and shouldn't be"* visible at a glance, and *"these two things you believe are incompatible"* impossible to miss.

Two things make this defensible rather than decorative:

**It can't be copied.** A competitor could clone our layout in a week. They cannot clone the encoding, because their data model has nothing to encode — you cannot desaturate by confidence if you never recorded confidence.

**The 50-node cap becomes an advantage.** With only fifty things on screen, you can afford to spend real visual bandwidth on *each one's epistemic state*. A tool rendering 10,000 nodes structurally cannot. **The comprehension limit isn't a ceiling on ambition — it's a budget you get to spend on depth instead of breadth.**

And it lands exactly where §7.3 says progress should be shown: not streaks or keystrokes, but **uncertainty reduced.** A graph that visibly desaturates from grey toward saturated colour as a student's project resolves is a progress bar made of epistemics — measuring the real work rather than the tool usage, which is precisely what the retention research says every competitor gets wrong.

---

## Sources

**Measured / peer-reviewed** — [Cognitive load & network visualisation scalability (arXiv 2008.07944)](https://arxiv.org/abs/2008.07944) · [Limits of complexity survey (arXiv 1809.00270)](https://arxiv.org/abs/1809.00270) · [Furnas, Generalized Fisheye Views](https://dl.acm.org/doi/10.1145/22627.22342) · [Heer & Robertson, Animated Transitions in Statistical Data Graphics](https://www.researchgate.net/publication/5878335_Animated_Transitions_in_Statistical_Data_Graphics) · [Mental Map Preservation (Archambault et al.)](https://www.researchgate.net/publication/232747172_Mental_Map_Preservation_Helps_User_Orientation_in_Dynamic_Graphs) · [Hornbæk, Effects of Display Size in Focus+Context / Overview+Detail](https://www.kasperhornbaek.dk/papers/CHI2011_SizingUp.pdf) · [Yoghourdjian et al., empirical graph-vis survey](https://www.cg.tuwien.ac.at/research/publications/2019/YOGHOURDJIAN2019/YOGHOURDJIAN2019-paper.pdf) · [Dunne & Shneiderman, Motif Simplification](https://www.cs.umd.edu/~ben/papers/Dunne2013Motif.pdf) · [Contrast, habituation and sensitisation in peripheral UI (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9464255/) · [Animation in a Peripheral Display](https://faculty.cc.gatech.edu/~stasko/papers/gi07.pdf) · [Oulasvirta, Cognitive Meta-Analysis of Interruptions](https://www.interruptions.net/literature/Oulasvirta-CHI04-p1155-oulasvirta.pdf) · [Gleicher, A Differential Approach to Graphical Interaction](https://research.cs.wisc.edu/graphics/Papers/Gleicher/Thesis/Acrobat/thesis01.pdf) · [Labeling Point Features (Harvard DASH)](https://dash.harvard.edu/bitstreams/7312037d-c809-6bd4-e053-0100007fdf3b/download)

**Encoding theory** — Bertin, *Semiology of Graphics* · [Munzner, marks & channels](https://www.cs.ubc.ca/~tmm/talks/mit24/mit24.pdf) · [Visual encoding principles](https://teaching.vda.univie.ac.at/vis/22s/LectureNotes/04_visual_encoding_principles.pdf) · [Hypothetical Outcome Plots (UW IDL)](https://medium.com/hci-design-at-uw/hypothetical-outcomes-plots-experiencing-the-uncertain-b9ea60d7c740)

**Layout & rendering** — [ForceAtlas2 (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC4051631/) · [graphology-layout-forceatlas2](https://www.jsdelivr.com/package/npm/graphology-layout-forceatlas2) · [d3-force](https://d3js.org/d3-force) · [sigma.js](https://www.sigmajs.org/) · [cosmos.gl](https://github.com/cosmosgl/graph) · [apple/embedding-atlas](https://github.com/apple/embedding-atlas)

**Interaction & tooling** — Autodesk Maya `MDGModifier` · [Label Studio / HumanSignal](https://humansignal.com/changelog/categories/feature-update/) · [Prodigy & annotation tooling survey](https://futureagi.com/blog/best-llm-annotation-tools-2026/) · [Obsidian 25k graph ceiling](https://forum.obsidian.md/t/obsidian-graph-view-doesnt-work-for-a-large-vault/106287)

**Accessibility** — [W3C WAI Complex Images](https://www.w3.org/WAI/tutorials/images/complex/) · [Deque — accessible interactive charts](https://www.deque.com/blog/how-to-make-interactive-charts-accessible/) · [Data Navigator (Elavsky)](https://www.frank.computer/data-navigator/) · [WCAG for charts: ARIA + keyboard](https://www.wellally.tech/blog/accessible-health-data-visualizations-wcag-guide)

**Ambient & retention** — [Pseudo-Ambience: filling the gap between notifications and continuous displays](https://apps4cloud.bgu.ac.il/cauchard/papers/BlumWorkshop.pdf) · [Peripheral interaction: characteristics and considerations](https://pure.tue.nl/ws/files/4037884/569822775171138.pdf) · [Learning analytics dashboards](https://www.slideshare.net/slideshow/learning-analyticsdashboardsforlearninganalyticsdayatkuleuven/35003302)

# F4 — the blocking gate, run

**Date:** 2026-08-11 · **Verdict: the original palette FAILED. A four-family
palette PASSES.** `scripts/f4_gate.py`, re-runnable, wired into CI.

## What was tested

Not a screenshot. ⚠️ Eyeballing a swatch grid with normal colour vision is
precisely the test that cannot detect the failure it looks for.

sRGB → linear → LMS → dichromacy simulation → Oklab, then the pairwise
perceptual distance for every hue pair, in every condition, at every confidence
rung. Protanopia and deuteranopia via Viénot, Brettel & Mollon (1999);
tritanopia via Brettel, Viénot & Mollon (1997).

**Floor: ΔE 0.080** — four times the large-field JND, because a 16px dot is
small, dark-surrounded and read peripherally.

## The failure

| pair | ΔE | under |
|---|---|---|
| **Question / Artifact** | **0.002** | normal, deuteranopia, protanopia |
| **Claim / Source** | 0.007 | all four conditions |
| Claim / Note | 0.018 | all four |
| Source / Note | 0.018 | all four |
| Concept / Question | 0.022 | normal, deut, prot |

**103 of 240 pair-condition-confidence combinations were below the floor.**
Question/Artifact at 0.002 is not "close" — it is two node types that are the
same colour.

⭐ And note the `normal` column. This palette failed for people with **ordinary
colour vision**, at low confidence. The CVD simulation was not what broke it;
it was VSUP desaturation, which the original palette was never checked against.

## Why six hues cannot work

Protanopia and deuteranopia collapse the red–green axis. What survives is
blue–yellow and lightness. Inside the dark-mode legibility band (L 0.68–0.90)
that leaves too little room for six separable hues — a search over 80,000
candidate palettes tops out at **ΔE 0.072**, below the floor. Five reaches
0.079. **Four reaches 0.106.**

⚠️ **Grey is not available either.** VSUP desaturates *toward* grey, so grey
already means "no confidence". A grey type colour collides with every other
type at the AMBIGUOUS rung — tested, ΔE 0.064, fail.

## What shipped

**Four hue families. Six types. The glyph carries the type.**

| family | oklch | types |
|---|---|---|
| `#7BF4FC` lattice | 0.900 0.109 201 | Concept `◆` · Question `?` |
| `#BB99FA` thinking | 0.751 0.140 299 | Claim `▲` · Note `·` |
| `#E5C14A` your evidence | 0.820 0.140 92 | Artifact `■` |
| `#B79400` outside evidence | 0.680 0.140 92 | Source `▪` |

⭐ **Artifact and Source are deliberately the same hue at different lightness.**
They are the pair the Disagreement Engine puts side by side constantly, and
same-hue/different-L is the most reliable distinction that survives *every*
dichromacy — strictly better than two hues a deuteranope reads as one.

**Worst pair, worst condition, lowest confidence: ΔE 0.088.** Passes with
margin at every rung.

## What this changes

- `Frontend/02 §5.2` — the palette is replaced.
- `Frontend/02 §2.1` — hue now encodes **family**; the glyph is promoted from
  redundant to **load-bearing** for type.
- `Frontend/06 §2.1` — tokens updated.
- ⚠️ The encoding matrix keeps its rule: hue still carries exactly one thing.
  That thing is now family, not type.

**Phase 0 is closed. Phase 1 may start.**

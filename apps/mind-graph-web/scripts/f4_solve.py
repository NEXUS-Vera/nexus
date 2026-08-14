#!/usr/bin/env python3
"""Find a six-hue palette that survives F4.

⭐ The insight the failing palette missed: protanopia and deuteranopia collapse
the red-green axis, so hue ALONE cannot separate six types for ~8% of men.
Lightness survives every dichromacy intact — so the palette has to spread on
L as well as h, and the search below optimises for the worst pair in the worst
condition at the LOWEST confidence rung, because that is where the design
actually has to hold.

    python3 scripts/f4_solve.py
"""
from __future__ import annotations

import itertools
import math
import random

from f4_gate import (FLOOR, VSUP, dE, desaturate, lin_to_oklab, oklab_to_lin,
                     simulate)

TYPES = ["Concept", "Question", "Claim", "Artifact", "Source", "Note"]
CONDS = ["normal", "deuteranopia", "protanopia", "tritanopia"]

# Dark-mode legibility band from Frontend/06 §2.6 — everything must clear
# contrast against #0B0D10, which is what caps how dark a hue may go.
L_MIN, L_MAX = 0.62, 0.90
C_MIN, C_MAX = 0.04, 0.15


def lab_of(L: float, C: float, h_deg: float):
    h = math.radians(h_deg)
    return (L, C * math.cos(h), C * math.sin(h))


def in_gamut(lab) -> bool:
    r, g, b = oklab_to_lin(*lab)
    return all(-0.001 <= v <= 1.001 for v in (r, g, b))


def score(palette: list[tuple[float, float, float]]) -> float:
    """The worst pairwise distance across every condition and confidence rung.
    ⚠️ Optimising the mean would hide exactly the collision that matters."""
    worst = 9.0
    for k in VSUP.values():
        labs = [desaturate(p, k) for p in palette]
        for cond in CONDS:
            if cond == "normal":
                seen = labs
            else:
                seen = [lin_to_oklab(*simulate(oklab_to_lin(*l), cond)) for l in labs]
            for i, j in itertools.combinations(range(len(seen)), 2):
                worst = min(worst, dE(seen[i], seen[j]))
    return worst


def to_hex(lab) -> str:
    r, g, b = oklab_to_lin(*lab)
    def enc(c):
        c = min(max(c, 0.0), 1.0)
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return round(c * 255)
    return "#{:02X}{:02X}{:02X}".format(enc(r), enc(g), enc(b))


def solve(iters: int = 60000, seed: int = 7):
    rng = random.Random(seed)
    # Start from six evenly spaced hues on a lightness ramp — the ramp is the
    # part that survives dichromacy, so it is the part we seed deliberately.
    best = [lab_of(L_MIN + (L_MAX - L_MIN) * i / 5, 0.10, 60 * i) for i in range(6)]
    best_s = score(best)
    cur, cur_s = list(best), best_s
    T0 = 0.02
    for step in range(iters):
        T = T0 * (1 - step / iters) + 1e-4
        cand = list(cur)
        i = rng.randrange(6)
        L, a, b = cand[i]
        C = math.hypot(a, b)
        h = math.degrees(math.atan2(b, a))
        L = min(max(L + rng.gauss(0, 0.03), L_MIN), L_MAX)
        C = min(max(C + rng.gauss(0, 0.02), C_MIN), C_MAX)
        h = (h + rng.gauss(0, 25)) % 360
        trial = lab_of(L, C, h)
        if not in_gamut(trial):
            continue
        cand[i] = trial
        s = score(cand)
        if s > cur_s or rng.random() < math.exp((s - cur_s) / T):
            cur, cur_s = cand, s
            if s > best_s:
                best, best_s = list(cand), s
    return best, best_s


if __name__ == "__main__":
    pal, s = solve()
    print(f"\n  worst-pair dE = {s:.4f}   (floor {FLOOR:.3f})  "
          f"{'PASS' if s >= FLOOR else 'FAIL'}\n")
    for name, lab in zip(TYPES, pal):
        L, a, b = lab
        C, h = math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360
        print(f"  --type-{name.lower():<9} {to_hex(lab)}   "
              f"oklch({L:.3f} {C:.3f} {h:.1f})")
    print()

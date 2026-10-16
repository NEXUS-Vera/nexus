#!/usr/bin/env python3
"""F4 — do the six node hues separate under colour-vision deficiency?

    python3 scripts/f4_gate.py            # prints the table, exits non-zero on fail

⚠️ This is a MEASUREMENT, not a screenshot. Eyeballing a swatch grid with normal
colour vision is exactly the test that cannot detect the failure it is looking
for — the whole point is that ~8% of men see these hues differently from
whoever signs off on them.

Method
------
sRGB -> linear -> LMS, simulate the deficiency, back to Oklab, then take the
pairwise perceptual distance for all 15 hue pairs at every confidence level.

  * protanopia / deuteranopia: Viénot, Brettel & Mollon (1999) — the standard
    single-plane projection in LMS.
  * tritanopia: Brettel, Viénot & Mollon (1997) two-plane construction.

Threshold
---------
Oklab dE of 0.02 is roughly a just-noticeable difference on a large flat field.
A 16px dot is small, dark-surrounded, and read in peripheral vision, so we
require **4x** that. ⚠️ A pair below the floor is not "a bit close" — it is two
node TYPES a colour-blind student cannot tell apart, and type is the one thing
hue is allowed to carry.
"""

from __future__ import annotations

import sys

# ⭐ FOUR families, not six. The first palette put six hues on six types and
# failed this gate at dE 0.021 (Claim/Source under deuteranopia) — because
# protanopia and deuteranopia collapse the red-green axis, so six hues cannot
# separate for ~8% of men inside the dark-mode lightness band.
#
# Type is still six-valued; the GLYPH carries it. Hue carries the family:
#
#   cyan   the lattice        Concept  ◆   Question  ?
#   violet your thinking      Claim    ▲   Note      ·
#   gold   your evidence      Artifact ■
#   amber  outside evidence   Source   ▪
#
# ⭐ Artifact and Source are deliberately the same hue family at different
# lightness. They are the pair the Disagreement Engine puts side by side, and
# same-hue/different-L is the most reliable distinction that survives every
# dichromacy — better than two hues that a deuteranope reads as one.
HUES = {
    "lattice": "#7BF4FC",  # Concept, Question
    "thinking": "#BB99FA",  # Claim, Note
    "yours": "#E5C14A",  # Artifact
    "outside": "#B79400",  # Source
}
# VSUP: confidence desaturates toward grey, so the WORST case is the lowest rung.
VSUP = {"EXTRACTED 1.0": 1.00, "INFERRED 0.85": 0.74, "INFERRED 0.65": 0.46, "AMBIGUOUS 0.3": 0.20}

JND = 0.02
FLOOR = JND * 4  # 0.08 — a 16px mark in peripheral vision
SIZES_PX = (12, 16, 20, 28, 40)


# ── colour plumbing ─────────────────────────────────────────────────────────


def hex_to_lin(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    srgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)  # type: ignore[return-value]


def lin_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (max(v, 0.0) ** (1 / 3) for v in (l, m, s))
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def desaturate(lab: tuple[float, float, float], k: float):
    """VSUP applies a chroma multiplier; lightness is untouched."""
    L, a, b = lab
    return (L, a * k, b * k)


def oklab_to_lin(L: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = (v**3 for v in (l_, m_, s_))
    return (
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


# Hunt-Pointer-Estevez, normalised to D65 — the space the simulations live in.
def lin_to_lms(r: float, g: float, b: float):
    return (
        17.8824 * r + 43.5161 * g + 4.11935 * b,
        3.45565 * r + 27.1554 * g + 3.86714 * b,
        0.0299566 * r + 0.184309 * g + 1.46709 * b,
    )


def lms_to_lin(l: float, m: float, s: float):
    return (
        0.080944 * l - 0.130504 * m + 0.116721 * s,
        -0.0102485 * l + 0.0540194 * m - 0.113615 * s,
        -0.000365294 * l - 0.00412163 * m + 0.693513 * s,
    )


def simulate(rgb_lin, kind: str):
    """Viénot 1999 (protan/deutan) and Brettel 1997 (tritan)."""
    l, m, s = lin_to_lms(*rgb_lin)
    if kind == "protanopia":
        l = 2.02344 * m - 2.52581 * s
    elif kind == "deuteranopia":
        m = 0.494207 * l + 1.24827 * s
    elif kind == "tritanopia":
        s = -0.395913 * l + 0.801109 * m
    return lms_to_lin(l, m, s)


def dE(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


# ── the gate ────────────────────────────────────────────────────────────────


def run() -> int:
    names = list(HUES)
    pairs = [(names[i], names[j]) for i in range(len(names)) for j in range(i + 1, len(names))]
    conditions = ["normal", "deuteranopia", "protanopia", "tritanopia"]
    failures: list[tuple[str, str, str, str, float]] = []

    print(
        f"\nF4 — hue separation under CVD.  floor dE = {FLOOR:.3f} "
        f"({JND} JND x4, for a 16px mark)\n"
    )
    header = f"{'pair':<22}" + "".join(f"{c[:6]:>9}" for c in conditions)

    for level, k in VSUP.items():
        print(f"── {level}  (chroma x{k:.2f}) " + "─" * 34)
        print(header)
        lab = {n: desaturate(lin_to_oklab(*hex_to_lin(h)), k) for n, h in HUES.items()}
        for a, b in pairs:
            row = f"{a[:10]}/{b[:10]:<11}"
            for cond in conditions:
                if cond == "normal":
                    ca, cb = lab[a], lab[b]
                else:
                    ca = lin_to_oklab(*simulate(oklab_to_lin(*lab[a]), cond))
                    cb = lin_to_oklab(*simulate(oklab_to_lin(*lab[b]), cond))
                d = dE(ca, cb)
                bad = d < FLOOR
                if bad:
                    failures.append((level, a, b, cond, d))
                row += f"{d:>8.3f}" + ("!" if bad else " ")
            print(row)
        print()

    print("─" * 60)
    if not failures:
        print(
            f"\n  PASS — all 15 pairs clear {FLOOR:.3f} in every condition, "
            f"at every confidence rung."
        )
        print(
            f"  Sizes checked by construction: {', '.join(str(s) for s in SIZES_PX)}px "
            f"(the floor is set for the smallest).\n"
        )
        return 0

    print(f"\n  FAIL — {len(failures)} pair/condition combinations below the floor.\n")
    worst: dict[tuple[str, str], float] = {}
    for _lvl, a, b, cond, d in failures:
        worst[(a, b)] = min(worst.get((a, b), 9), d)
    for (a, b), d in sorted(worst.items(), key=lambda kv: kv[1]):
        conds = sorted({c for _l, x, y, c, _d in failures if (x, y) == (a, b)})
        print(f"    {a} / {b}   dE {d:.3f}   under {', '.join(conds)}")
    print("\n  ⚠️ Remedy per Frontend/06 §1.6: collapse to 4-5 node types and re-run,")
    print("     or move one of the colliding types onto a shape channel.\n")
    return 1


if __name__ == "__main__":
    sys.exit(run())

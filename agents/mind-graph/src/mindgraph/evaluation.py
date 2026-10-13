"""The evaluation harness. Backend/06.

⚠️ There is no accepted way to measure whether an AI research-and-build
assistant works, and the existing numbers do not survive checking — one memory
product headlines 84% where independent re-evaluation gives 58.44%. So ours has
to survive the same treatment, which means pre-registering what failure looks
like BEFORE the data arrives.

Five families:
    extraction  precision/recall against hand-labelled truth
    retrieval   vs the Adamic-Adar baseline — a 2003 algorithm
    frontier    are suggested actions done, and do they unblock anything?
    calibration ⭐ the reliability curve, not a Brier delta
    cost        dollars per ACCEPTED proposal, not per turn
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .analyzer import adamic_adar
from .projector import GraphState

# Pre-registered null (Backend/06 §5). Written down before any data exists so
# it cannot be moved afterwards.
PREREG = {
    "primary": "mean |stated - observed| across confidence bins",
    "predicted_decrease": 0.05,
    "min_predictions_per_student": 15,
    "min_students": 8,
}
BINS = ((0.0, 0.35), (0.35, 0.55), (0.55, 0.7), (0.7, 0.85), (0.85, 1.01))


# ── extraction ──────────────────────────────────────────────────────────────


def extraction_quality(predicted: list[tuple], truth: list[tuple]) -> dict:
    p, t = set(predicted), set(truth)
    tp = len(p & t)
    prec = tp / len(p) if p else 0.0
    rec = tp / len(t) if t else 0.0
    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(2 * prec * rec / (prec + rec), 4) if tp else 0.0,
        "fabricated": sorted(p - t),
        "missed": sorted(t - p),
    }


# ── retrieval, against a 2003 baseline ──────────────────────────────────────


def _dcg(rels: list[float]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ndcg(ranked: list[str], relevant: set[str], k: int = 10) -> float:
    rels = [1.0 if nid in relevant else 0.0 for nid in ranked[:k]]
    ideal = sorted(rels, reverse=True)
    return round(_dcg(rels) / _dcg(ideal), 4) if any(ideal) else 0.0


def retrieval_vs_baseline(
    state: GraphState, ranked: list[str], relevant: set[str], seed_node: str, k: int = 10
) -> dict:
    """⭐ If we cannot beat Adamic-Adar, the graph is not earning its cost.

    A hard comparison to publish and an easy one to quietly skip, which is
    exactly why it is in the harness rather than in a plan.
    """
    aa = [
        p["b"] if p["a"] == seed_node else p["a"]
        for p in adamic_adar(state, limit=200)
        if seed_node in (p["a"], p["b"])
    ]
    ours, base = ndcg(ranked, relevant, k), ndcg(aa, relevant, k)
    return {
        "ndcg": ours,
        "baseline_ndcg": base,
        "beats_baseline": ours > base,
        "margin": round(ours - base, 4),
    }


# ── frontier ────────────────────────────────────────────────────────────────


def frontier_quality(suggested: list[str], acted_on: set[str], unblocked: dict[str, int]) -> dict:
    if not suggested:
        return {"uptake": 0.0, "mean_unblocked": 0.0, "suggested": 0}
    done = [s for s in suggested if s in acted_on]
    return {
        "suggested": len(suggested),
        "uptake": round(len(done) / len(suggested), 4),
        "mean_unblocked": round(sum(unblocked.get(s, 0) for s in done) / len(done), 3)
        if done
        else 0.0,
    }


# ── calibration ─────────────────────────────────────────────────────────────


@dataclass
class Prediction:
    stated_confidence: float  # what the student said, BEFORE the result
    correct: bool
    seq: int = 0


def reliability_curve(preds: list[Prediction]) -> list[dict]:
    """⭐ "When you said 80% sure, were you right 80% of the time?"

    NOT a Brier delta between week 1 and week 6. That comparison is broken by
    DIFFICULTY DRIFT: week-6 predictions are about harder things, so flat
    accuracy on rising difficulty is a real improvement that a naive
    before/after shows as nothing. Conditioning on the student's own stated
    confidence kills the confound by construction.
    """
    out = []
    for lo, hi in BINS:
        bucket = [p for p in preds if lo <= p.stated_confidence < hi]
        if not bucket:
            continue
        stated = sum(p.stated_confidence for p in bucket) / len(bucket)
        observed = sum(p.correct for p in bucket) / len(bucket)
        out.append(
            {
                "bin": f"{lo:.2f}-{hi:.2f}",
                "n": len(bucket),
                "stated": round(stated, 4),
                "observed": round(observed, 4),
                "gap": round(observed - stated, 4),
            }
        )
    return out


def calibration_error(preds: list[Prediction]) -> float | None:
    curve = reliability_curve(preds)
    if not curve:
        return None
    return round(sum(abs(b["gap"]) for b in curve) / len(curve), 4)


def interval_coverage(intervals: list[tuple[float, float, float]], nominal: float = 0.8) -> dict:
    """⭐ Moves FIRST. Well-calibrated 80% intervals contain the truth ~80% of
    the time; undergraduates land far below — a large gap means a large effect
    size, detectable at much smaller n than the reliability curve needs."""
    if not intervals:
        return {"n": 0, "coverage": None, "nominal": nominal}
    hits = sum(1 for lo, hi, actual in intervals if lo <= actual <= hi)
    cov = hits / len(intervals)
    return {
        "n": len(intervals),
        "coverage": round(cov, 4),
        "nominal": nominal,
        "shortfall": round(nominal - cov, 4),
    }


def evaluate_prereg(before: list[Prediction], after: list[Prediction], n_students: int) -> dict:
    """⭐ A null is not a failure. Calibration is the MEASUREMENT, not the
    mechanism — we would lead with proof completion and publish a finding
    nobody currently has."""
    b, a = calibration_error(before), calibration_error(after)
    powered = (
        n_students >= PREREG["min_students"]
        and min(len(before), len(after)) >= PREREG["min_predictions_per_student"]
    )
    decrease = round(b - a, 4) if (b is not None and a is not None) else None
    return {
        "before": b,
        "after": a,
        "decrease": decrease,
        "sufficiently_powered": powered,
        "meets_prereg": bool(
            powered and decrease is not None and decrease >= PREREG["predicted_decrease"]
        ),
        "prereg": PREREG,
    }


# ── cost ────────────────────────────────────────────────────────────────────


def cost_per_accepted(cost_rows: list[dict], accepted: int) -> dict:
    """⭐ Per ACCEPTED proposal, not per turn — the one that says whether the
    graph is earning its keep."""
    rate = {"none": 0.0, "oss": 0.0002, "haiku": 0.001, "sonnet": 0.006, "opus": 0.03}
    usd = sum(
        (r.get("tokens_in", 0) + r.get("tokens_out", 0))
        / 1000
        * rate.get(r.get("model_tier", "sonnet"), 0.006)
        for r in cost_rows
    )
    by_tier: dict[str, float] = {}
    for r in cost_rows:
        t = r.get("model_tier", "sonnet")
        by_tier[t] = round(
            by_tier.get(t, 0.0)
            + ((r.get("tokens_in", 0) + r.get("tokens_out", 0)) / 1000 * rate.get(t, 0.006)),
            6,
        )
    return {
        "usd": round(usd, 6),
        "accepted": accepted,
        "usd_per_accepted": round(usd / accepted, 6) if accepted else None,
        "by_tier": dict(sorted(by_tier.items())),
    }


@dataclass
class Report:
    extraction: dict = field(default_factory=dict)
    retrieval: dict = field(default_factory=dict)
    frontier: dict = field(default_factory=dict)
    calibration: dict = field(default_factory=dict)
    cost: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "extraction": self.extraction,
            "retrieval": self.retrieval,
            "frontier": self.frontier,
            "calibration": self.calibration,
            "cost": self.cost,
        }

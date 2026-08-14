"""The Artifact loop. Backend/01 §3.4 — where the moat lives.

    predicted   BEFORE you run it, locked and immutable
    measured    AFTER
    agreement   matched | diverged | inconclusive | not_run

Built before ingestion (Phase 1) on purpose: this is the only data in the
system that cannot be reconstructed later. A PDF can be re-extracted forever;
a prediction someone forgot to lock is gone.

⚠️ Values are user content and are ENCRYPTED. `agreement` is structural, so
aggregate calibration survives an erasure request while the numbers do not
(Backend/02 §0).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .crypto import KeyStore, decrypt, encrypt
from .events import EventType
from .ids import uuid7
from .ledger import Ledger
from .projector import project
from .schema import Confidence, Relation

AGREEMENTS = ("matched", "diverged", "inconclusive", "not_run")


class ArtifactError(Exception):
    pass


@dataclass
class Session:
    """One user's ledger plus the key that unlocks its content."""
    user: str
    ledger: Ledger
    keys: KeyStore

    dir: Path | None = None
    costs: object = None
    _cached: object = None

    @classmethod
    def open(cls, user: str, root: str | Path = "users") -> Session:
        d = Path(root) / user
        d.mkdir(parents=True, exist_ok=True)
        keys = KeyStore(Path(root) / ".keys.json")   # never inside the data dir
        if not keys.exists(user):
            keys.create(user)
        from .costlog import use as use_costlog
        # A sidecar: disposable, never backed up — and owned by THIS session,
        # so one user's rows can never land in another's file.
        return cls(user=user, ledger=Ledger(d / "ledger.db"), keys=keys, dir=d,
                   costs=use_costlog(d / "costs.db"))

    def state(self):
        """Snapshot + tail, never a bare full replay.

        ⭐ The snapshot is a CACHE carrying `last_seq`, so a stale one is
        TOPPED UP from the ledger rather than trusted. A restored snapshot can
        disagree with the log; a replayed one cannot — and a corrupt cache is
        simply a cold cache.
        """
        from . import snapshot as snap
        from .costlog import for_session
        with for_session(self).measure("project", user=self.user):
            base = None
            snap_path = self.dir / "graph.snapshot" if self.dir else None
            if snap_path and snap_path.exists():
                try:
                    base = snap.load(snap_path)
                except Exception:
                    base = None
            since = base.last_seq if base else 0
            self._cached = project(self.ledger.read(since=since), base)
            return self._cached

    def checkpoint(self) -> None:
        """Persist the cache. Safe to skip, safe to delete, never authoritative."""
        from . import snapshot as snap
        if self.dir and self._cached is not None:
            snap.save(self._cached, self.dir / "graph.snapshot")

    def vectors(self):
        from .vectors import VectorStore
        return VectorStore(self.dir / "vectors.db" if self.dir else ":memory:")

    def close(self) -> None:
        self.checkpoint()
        self.ledger.close()


def _content_for(s: Session, artifact_id: str, field: str) -> dict | None:
    """Last recorded value of an encrypted field for this artifact."""
    found = None
    for e in s.ledger.read():
        if e.content is None:
            continue
        if e.structural.get("artifact_id") != artifact_id and \
                artifact_id not in [n.get("id") for n in e.structural.get("nodes", [])]:
            continue
        payload = decrypt(s.keys, s.user, e.content)
        if field in payload:
            found = payload[field]
    return found


def predict(s: Session, *, label: str, quantity: str, low: float, high: float,
            unit: str, supports: list[str] | None = None,
            method: str | None = None, spec: dict | None = None,
            artifact_id: str | None = None) -> str:
    """Lock a prediction. ⭐ The load-bearing interaction.

    Once this returns, the prediction is in the ledger and cannot be edited —
    which is what makes the calibration record real rather than self-flattering.
    """
    if low > high:
        raise ArtifactError(f"low {low} is above high {high}")
    aid = artifact_id or uuid7()
    st = s.state()
    if aid in st.nodes and _content_for(s, aid, "predicted"):
        raise ArtifactError(
            f"{aid} already has a locked prediction — predictions are immutable")

    # ⚠️ NO label here. Labels are user text and belong in the encrypted half —
    # putting one in `structural` quietly defeats crypto-shredding, which is
    # exactly the mistake Backend/02 §0 warns about and CI tests for.
    nodes = [{"id": aid, "type": "Artifact", "kind": "run"}]
    edges = []
    for cid in sorted(supports or []):
        edges.append({"id": uuid7(), "src": aid, "dst": cid,
                      "relation": Relation.MEASURED_BY.value,
                      "confidence": Confidence.EXTRACTED.value, "score": 1.0,
                      "weight_source_nodes": [aid]})
    if method:
        edges.append({"id": uuid7(), "src": aid, "dst": method,
                      "relation": Relation.USES_METHOD_IN.value,
                      "confidence": Confidence.EXTRACTED.value, "score": 1.0,
                      "weight_source_nodes": [aid]})

    blob = encrypt(s.keys, s.user, {
        "predicted": {"quantity": quantity, "low": low, "high": high,
                      "unit": unit},
        "spec": spec or {}, "label": label})
    s.ledger.append(s.user, EventType.ACCEPTED,
                    {"nodes": nodes, "edges": edges, "artifact_id": aid},
                    content=blob)
    return aid


def _agreement(pred: dict, value: float | None) -> str:
    if value is None:
        return "inconclusive"
    return "matched" if pred["low"] <= value <= pred["high"] else "diverged"


def measure(s: Session, artifact_id: str, *, value: float | None,
            unit: str | None = None, raw_ref: str | None = None,
            validates: list[str] | None = None) -> dict:
    """Record what actually happened, and derive the verdict.

    ⚠️ The verdict is computed from the locked range, never supplied. Letting a
    caller pass `agreement` would make the record self-flattering, which is the
    one thing this loop exists to prevent.
    """
    st = s.state()
    if artifact_id not in st.nodes:
        raise ArtifactError(f"no artifact {artifact_id}")
    pred = _content_for(s, artifact_id, "predicted")
    if pred is None:
        raise ArtifactError(
            f"{artifact_id} has no locked prediction — predict before you measure")
    if _content_for(s, artifact_id, "measured") is not None:
        raise ArtifactError(f"{artifact_id} already has a measurement")
    if unit and unit != pred["unit"]:
        raise ArtifactError(
            f"unit mismatch: predicted in {pred['unit']}, measured in {unit}")

    agreement = _agreement(pred, value)
    # Anything this artifact measures is corroborated by a matching outcome.
    targets = sorted(validates or [
        e.dst for e in st.edges.values()
        if e.src == artifact_id and e.relation is Relation.MEASURED_BY])

    blob = encrypt(s.keys, s.user, {
        "measured": {"quantity": pred["quantity"], "value": value,
                     "unit": pred["unit"], "raw_ref": raw_ref}})
    from .costlog import for_session
    with for_session(s).measure("validate", user=s.user, agreement=agreement):
        s.ledger.append(s.user, EventType.VALIDATED,
                        {"artifact_id": artifact_id, "agreement": agreement,
                         "validates": targets},
                        content=blob)
    return {"artifact_id": artifact_id, "agreement": agreement,
            "predicted": pred, "measured": value, "validates": targets}


def show(s: Session, artifact_id: str) -> dict:
    st = s.state()
    if (n := st.nodes.get(artifact_id)) is None:
        raise ArtifactError(f"no artifact {artifact_id}")
    return {
        "id": artifact_id, "label": _content_for(s, artifact_id, "label"),
        "kind": n.kind,
        "predicted": _content_for(s, artifact_id, "predicted"),
        "measured": _content_for(s, artifact_id, "measured"),
        "agreement": n.labels_at.get("outcome", "not_run"),
        "supports": sorted(e.dst for e in st.edges.values()
                           if e.src == artifact_id
                           and e.relation is Relation.MEASURED_BY),
    }


def calibration(s: Session) -> dict:
    """The reliability signal, computed from structural data alone.

    Survives erasure by construction — it never touches the encrypted half.
    """
    st = s.state()
    outcomes = [n.labels_at.get("outcome") for n in st.nodes.values()
                if n.labels_at.get("outcome")]
    scored = [o for o in outcomes if o in ("matched", "diverged")]
    return {
        "resolved": len(scored),
        "matched": scored.count("matched"),
        "diverged": scored.count("diverged"),
        "hit_rate": round(scored.count("matched") / len(scored), 3) if scored else None,
        "inconclusive": outcomes.count("inconclusive"),
    }

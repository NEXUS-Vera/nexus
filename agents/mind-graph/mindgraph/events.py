"""Event models and the split payload. Backend/02 §3.

The split is load-bearing for erasure (§0): `structural` is plaintext and
survives crypto-shredding, `content` is encrypted and does not. Putting user
text in `structural` silently breaks the erasure guarantee, so CI tests for it.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from .schema import SCHEMA_VERSION


class EventType(StrEnum):
    OBSERVED = "observed"; PROPOSED = "proposed"
    ACCEPTED = "accepted"; REJECTED = "rejected"
    VALIDATED = "validated"      # the outcome path
    RETRACTED = "retracted"; MERGED = "merged"; SPLIT = "split"
    ANNOTATED = "annotated"; ACCESSED = "accessed"
    DEAD_END = "dead_end"        # this approach failed
    CORRECTION = "correction"    # user fixed something; a learning signal
    SHREDDED = "shredded"


class Event(BaseModel):
    seq: int
    ts: str
    actor: str
    type: EventType
    schema_version: int = SCHEMA_VERSION
    structural: dict = Field(default_factory=dict)   # PLAINTEXT
    content: bytes | None = None                     # ENCRYPTED
    caused_by: int | None = None
    prev_hash: str
    hash: str

"""Id generation. Backend/02 §1.

UUID7 (time-ordered) for real ids, plus a deterministic generator for tests.

⚠️ Ids are generated at INGEST time and travel inside event payloads. They are
never generated inside the projector — a `uuid4()` there would make replay
non-deterministic, which is the failure mode §5.3 exists to prevent.
"""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> str:
    """Time-ordered UUID. Sorts by creation, which keeps ledger reads local."""
    ms = int(time.time() * 1000)
    rand = os.urandom(10)
    b = bytearray(ms.to_bytes(6, "big") + rand)
    b[6] = (b[6] & 0x0F) | 0x70  # version 7
    b[8] = (b[8] & 0x3F) | 0x80  # RFC 4122 variant
    return str(uuid.UUID(bytes=bytes(b)))


class DeterministicIds:
    """Reproducible ids for tests and golden fixtures.

    Golden-ledger tests compare a state hash across versions, so the ids inside
    them must not move between runs.
    """

    def __init__(self, prefix: str = "t") -> None:
        self.prefix = prefix
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"{self.prefix}_{self._n:06d}"

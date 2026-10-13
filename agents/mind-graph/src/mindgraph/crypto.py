"""Per-user keys, encrypt/decrypt, shred. Backend/02 §0.

GDPR Art. 17 grants a right to erasure; an append-only ledger never deletes.
The resolution is crypto-shredding: encrypt content under a per-user key and,
on erasure, destroy the key. The ciphertext stays in place but is noise.

⚠️ Keys must never be backed up alongside the data. If one restore recovers
both, crypto-shredding is defeated by your own disaster recovery and the
erasure guarantee was fictional (Backend/07 §4.2).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .errors import KeyDestroyed


class KeyStore:
    """Per-user keys, held OUTSIDE the data directory.

    In production this is a KMS. The file backend exists so Phase 0 can test
    the erasure path without standing up infrastructure.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._mem: dict[str, bytes] = {}
        if self.path and self.path.exists():
            self._mem = {u: k.encode() for u, k in json.loads(self.path.read_text()).items()}

    def _flush(self) -> None:
        if self.path:
            self.path.write_text(
                json.dumps({u: k.decode() for u, k in self._mem.items()}, sort_keys=True)
            )
            os.chmod(self.path, 0o600)

    def create(self, user: str) -> bytes:
        self._mem.setdefault(user, Fernet.generate_key())
        self._flush()
        return self._mem[user]

    def get(self, user: str) -> bytes:
        if user not in self._mem:
            raise KeyDestroyed(f"no key for {user!r} (never created, or shredded)")
        return self._mem[user]

    def destroy(self, user: str) -> None:
        """Erasure. After this, that user's content is unrecoverable by anyone."""
        self._mem.pop(user, None)
        self._flush()

    def exists(self, user: str) -> bool:
        return user in self._mem


def encrypt(keystore: KeyStore, user: str, payload: dict) -> bytes:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return Fernet(keystore.get(user)).encrypt(raw)


def decrypt(keystore: KeyStore, user: str, blob: bytes) -> dict:
    try:
        return json.loads(Fernet(keystore.get(user)).decrypt(blob))
    except (InvalidToken, KeyDestroyed) as exc:
        raise KeyDestroyed("content is unreadable — the key is gone") from exc

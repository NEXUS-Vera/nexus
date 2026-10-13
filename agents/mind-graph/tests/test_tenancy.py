"""Phase 7 — auth, tenancy, backup, restore, concurrency. Backend/07 §4."""
from __future__ import annotations

import pytest
from conftest import accept, edge, node
from mindgraph.errors import KeyDestroyed
from mindgraph.ledger import Ledger
from mindgraph.projector import project, state_hash
from mindgraph.tenancy import (
    GraphCache,
    TenancyError,
    backup,
    erase,
    health,
    keystore,
    provision,
    restore,
    user_dir,
    verify_key_separation,
)


def _populate(root, user):
    led = Ledger(user_dir(root, user) / "ledger.db")
    accept(led, [node("M", "Artifact"), node("C1")], [edge("M", "supports", "C1")])
    h = state_hash(project(led.read()))
    led.close()
    return h


# ── isolation is a path check ───────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["../etc", "a/b", "", "..", "x" * 80, "a b"])
def test_illegal_user_ids_are_refused(tmp_path, bad):
    """⚠️ The path check IS the isolation — a user id that escapes its
    directory reads someone else's ledger."""
    with pytest.raises(TenancyError):
        user_dir(tmp_path, bad)


def test_provision_creates_the_layout(tmp_path):
    d = provision(tmp_path, "u1")
    assert (d / "ledger.db").exists()
    assert (d / "sidecars").is_dir() and (d / "blobs").is_dir()
    assert keystore(tmp_path).exists("u1")


def test_keys_live_outside_the_data_directory(tmp_path):
    provision(tmp_path, "u1")
    assert (tmp_path / "keys.json").exists()
    assert not (tmp_path / "u1" / "keys.json").exists()


def test_two_users_cannot_see_each_other(tmp_path):
    provision(tmp_path, "u1")
    provision(tmp_path, "u2")
    h1 = _populate(tmp_path, "u1")
    led2 = Ledger(user_dir(tmp_path, "u2") / "ledger.db")
    assert state_hash(project(led2.read())) != h1
    led2.close()


# ── backup and restore ──────────────────────────────────────────────────────

def test_restore_is_a_replay_not_a_snapshot_copy(tmp_path):
    """⭐ A restored snapshot could disagree with the ledger; a replayed one
    cannot."""
    provision(tmp_path, "u1")
    expected = _populate(tmp_path, "u1")
    arc = backup(tmp_path, "u1", tmp_path / "u1.tgz")

    (user_dir(tmp_path, "u1") / "graph.snapshot").write_text('{"corrupt":1}')
    assert restore(tmp_path, "u1", arc) == expected
    assert not (user_dir(tmp_path, "u1") / "graph.snapshot").exists()


def test_a_backup_never_contains_the_keystore(tmp_path):
    """⚠️ If one restore recovers both data and key, crypto-shredding is
    defeated by your own disaster recovery."""
    provision(tmp_path, "u1")
    _populate(tmp_path, "u1")
    arc = backup(tmp_path, "u1", tmp_path / "u1.tgz")
    assert verify_key_separation(tmp_path, arc)


def test_a_tampered_backup_is_refused(tmp_path):
    provision(tmp_path, "u1")
    _populate(tmp_path, "u1")
    arc = backup(tmp_path, "u1", tmp_path / "u1.tgz")
    restore(tmp_path, "u1", arc)
    led = Ledger(user_dir(tmp_path, "u1") / "ledger.db")
    led.db.execute("UPDATE events SET structural='{\"nodes\":[]}' WHERE seq=1")
    led.db.commit()
    led.close()
    bad = backup(tmp_path, "u1", tmp_path / "bad.tgz")
    with pytest.raises(TenancyError, match="hash chain"):
        restore(tmp_path, "u1", bad)


# ── erasure ─────────────────────────────────────────────────────────────────

def test_erase_destroys_the_key_and_records_it(tmp_path):
    provision(tmp_path, "u1")
    _populate(tmp_path, "u1")
    ks = keystore(tmp_path)
    from mindgraph.crypto import encrypt
    blob = encrypt(ks, "u1", {"measured": "47.2"})

    erase(tmp_path, "u1")
    assert not keystore(tmp_path).exists("u1")
    with pytest.raises(KeyDestroyed):
        from mindgraph.crypto import decrypt
        decrypt(keystore(tmp_path), "u1", blob)

    led = Ledger(user_dir(tmp_path, "u1") / "ledger.db")
    assert any(e.type.value == "shredded" for e in led.read())
    led.close()


def test_health_reports_shredded_users(tmp_path):
    provision(tmp_path, "u1")
    provision(tmp_path, "u2")
    erase(tmp_path, "u2")
    h = health(tmp_path)
    assert h["users"] == 2 and h["keys_outside_data_dir"]
    assert h["shredded"] == ["u2"]


# ── concurrency: the constraint the load test found ────────────────────────

def test_the_cache_evicts_by_lru(tmp_path):
    """⭐ CPU was never the limit — memory was. 144-240 MB per live graph."""
    for u in ("u1", "u2", "u3"):
        provision(tmp_path, u)
        _populate(tmp_path, u)
    c = GraphCache(tmp_path, capacity=2)
    c.get("u1")
    c.get("u2")
    c.get("u1")     # u2 is now least-recent
    c.get("u3")
    assert c.resident == 2 and c.evictions == 1


def test_an_evicted_graph_rebuilds_identically(tmp_path):
    """Eviction is free because replay is 122 ms — drop it, rebuild on the
    next request."""
    provision(tmp_path, "u1")
    expected = _populate(tmp_path, "u1")
    c = GraphCache(tmp_path, capacity=1)
    first = state_hash(c.get("u1"))
    c.drop("u1")
    assert state_hash(c.get("u1")) == first == expected
    assert c.rebuilds == 2


def test_a_cache_hit_does_not_rebuild(tmp_path):
    provision(tmp_path, "u1")
    _populate(tmp_path, "u1")
    c = GraphCache(tmp_path, capacity=4)
    c.get("u1")
    c.get("u1")
    assert c.rebuilds == 1


def test_the_cache_isolates_users(tmp_path):
    for u in ("u1", "u2"):
        provision(tmp_path, u)
    _populate(tmp_path, "u1")
    c = GraphCache(tmp_path, capacity=4)
    assert len(c.get("u1").nodes) == 2 and len(c.get("u2").nodes) == 0

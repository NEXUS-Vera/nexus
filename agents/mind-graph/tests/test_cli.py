"""Regression coverage for CLI graph retrieval."""

import pytest
from conftest import edge, node
from mindgraph.artifact import Session
from mindgraph.cli import main
from mindgraph.crypto import encrypt
from mindgraph.events import EventType


@pytest.mark.parametrize(
    ("destination", "expected"),
    [("b", "Alpha -> Beta"), ("c", "no path"), ("missing", "no path")],
)
def test_path_subcommand(tmp_path, capsys, destination, expected):
    root = str(tmp_path)
    session = Session.open("local", root)
    try:
        session.ledger.append(
            session.user,
            EventType.ACCEPTED,
            {
                "nodes": [node(nid, "Concept") for nid in ("a", "b", "c")],
                "edges": [edge("a", "requires", "b")],
            },
            content=encrypt(session.keys, session.user, {"labels": {"a": "Alpha", "b": "Beta"}}),
        )
    finally:
        session.close()

    assert main(["--root", root, "path", "a", destination]) == 0
    captured = capsys.readouterr()
    assert captured.out == expected + "\n"
    assert captured.err == ""

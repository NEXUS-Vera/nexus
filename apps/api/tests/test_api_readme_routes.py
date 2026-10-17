"""The API README endpoint list must match the routes the app actually serves.

Agents discover the HTTP surface from ``apps/api/README.md`` (contract M1:
core steps run through a documented API). This keeps that list from drifting:
an undocumented route, or a documented route that no longer exists, fails.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute
from nexus_api.main import app

README = Path(__file__).resolve().parents[1] / "README.md"
WALKTHROUGH = (
    Path(__file__).resolve().parents[3] / "docs" / "operations" / "agent-http-golden-flow.md"
)
_ENTRY = re.compile(r"^- `(GET|POST|PUT|PATCH|DELETE) (/[^`?\s]*)(?:\?([^`]*))?`")
_CALL = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE) (/[a-z][^\s`?]*)")
_PARAM = re.compile(r"\{[^}]+\}")


def _normalize(path: str) -> str:
    # {project_id} in code, {projectId} in docs: compare the shape only.
    return _PARAM.sub("{}", path)


def _template_regex(path: str) -> re.Pattern[str]:
    segments = ("[^/]+" if seg.startswith("{") else re.escape(seg) for seg in path.split("/"))
    return re.compile("^" + "/".join(segments) + "$")


def _served_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods:
                routes.add((method, _normalize(route.path)))
    return routes


def _readme_entries() -> list[tuple[str, str, set[str]]]:
    entries = []
    for line in README.read_text(encoding="utf-8").splitlines():
        match = _ENTRY.match(line)
        if match:
            query = match.group(3) or ""
            names = {part.split("=", 1)[0] for part in query.split("&") if part}
            entries.append((match.group(1), _normalize(match.group(2)), names))
    return entries


def test_readme_lists_every_served_route() -> None:
    served = _served_routes()
    documented = [(method, path) for method, path, _ in _readme_entries()]
    assert len(documented) == len(set(documented)), "duplicate README endpoint entries"
    missing = sorted(served - set(documented))
    stale = sorted(set(documented) - served)
    assert not missing, f"routes missing from apps/api/README.md: {missing}"
    assert not stale, f"README lists routes the API does not serve: {stale}"


def test_readme_query_parameters_match_declared_ones() -> None:
    declared = {
        (method, _normalize(route.path)): {param.alias for param in route.dependant.query_params}
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    mismatched = [
        (method, path, sorted(names), sorted(declared[(method, path)]))
        for method, path, names in _readme_entries()
        if (method, path) in declared and names != declared[(method, path)]
    ]
    assert not mismatched, f"README query parameters (documented, declared) differ: {mismatched}"


def test_golden_walkthrough_only_names_served_routes() -> None:
    # The walkthrough uses concrete artifact types (``.../artifacts/firmware/...``),
    # so match each call against the served path templates, one segment per param.
    patterns = [
        (method, _template_regex(route.path))
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    ]
    calls = set(_CALL.findall(WALKTHROUGH.read_text(encoding="utf-8")))
    assert calls, "walkthrough names no routes"
    stale = sorted(
        (method, path)
        for method, path in calls
        if not any(m == method and pattern.match(path) for m, pattern in patterns)
    )
    assert not stale, f"walkthrough names routes the API does not serve: {stale}"

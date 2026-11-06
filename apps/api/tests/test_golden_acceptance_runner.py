"""Offline CLI regression evidence, never live acceptance evidence."""

import importlib.util
from pathlib import Path
from typing import Any

import httpx
import pytest
from nexus_api import main
from test_actionable_execution_plan import _revise_candidates
from test_golden_lifecycle_http_api import AUTH
from test_repair_full_scope_api import ticking_http_loop  # noqa: F401

spec = importlib.util.spec_from_file_location(
    "golden_runner", Path(__file__).parents[3] / "scripts/run_golden_acceptance.py"
)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_argparse() -> None:
    args = runner.parser().parse_args([])
    assert (args.api_url, args.timeout, args.require_real, args.step) == (
        "http://127.0.0.1:8000",
        240,
        False,
        None,
    )
    args = runner.parser().parse_args(["--require-real", "--timeout", "3", "--step", "2"])
    assert args.require_real and args.timeout == 3 and args.step == 2
    for flags in (["--step", "11"], ["--timeout", "0"], ["--timeout", "nan"]):
        with pytest.raises(SystemExit):
            runner.parser().parse_args(flags)


@pytest.mark.usefixtures("ticking_http_loop")
async def test_init_plan_asgi() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test", headers=AUTH
    ) as client:
        demo = runner.GoldenRunner(client)
        assert await demo.run(through=1) == 0
        # Default fixture parts need an explicit supported-pair user revision.
        await _revise_candidates(client, demo.pid, demo.actor)
        await demo.plan()
        assert demo.pid.startswith("proj_")


async def test_repair_mock(capsys: Any) -> None:
    calls = []
    states = iter(
        [
            {"status": "inspect", "revision": 1},
            {"status": "running", "stage": "compile", "runId": "run_1", "revision": 2},
            {"status": "completed", "revision": 3},
        ]
    )

    def handle(request: Any) -> Any:
        calls.append(request)
        if request.url.path.endswith("/repair"):
            return httpx.Response(200, json={"repairId": "repair_1", **next(states)})
        if "/executions/" in request.url.path:
            return httpx.Response(200, json={"executionRun": {"status": "completed"}})
        if request.url.path.endswith("/evidence-chain"):
            return httpx.Response(
                200,
                json={
                    "chains": [
                        {
                            "requirementId": rid,
                            "assessment": "PASS",
                            "executionRunId": "run_1",
                            "evidenceReferences": [{"sourceId": "run_1"}],
                            "applicability": {"state": "CURRENT"},
                        }
                        for rid in runner.DYNAMIC
                    ]
                },
            )
        cases = [
            {
                "linkedRequirementIds": [rid],
                "status": "passed",
                "assessment": "PASS",
                "assessmentAuthority": "deterministic-code",
            }
            for rid in runner.DYNAMIC
        ]
        return httpx.Response(
            200,
            json={
                "artifacts": [
                    {"artifactType": "requirement-set", "content": {"requirements": []}},
                    {"artifactType": "test-plan", "content": {"testCases": cases}},
                ]
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle), base_url="http://test"
    ) as c:
        demo = runner.GoldenRunner(c, require_real=True)
        demo.pid = "prj_mock"
        await demo.repair("run_failed")
        assert demo.run_ids == ["run_1"]
    assert all(r.url.params.get("requireReal") == "true" for r in calls if r.method == "GET")
    assert "revision=2" in capsys.readouterr().out


async def test_http_failure_triage(capsys: Any) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(422, json={"error": "blocked"})),
        base_url="http://test",
    ) as client:
        assert await runner.GoldenRunner(client).run(through=1) == 1
    output = capsys.readouterr().err
    assert "step 1" in output and "HTTP 422" in output and "blocked" in output


async def test_verify_composes_linked_runs() -> None:
    """Compiler ELF -> simulator serial -> analysis, all through HTTP."""
    import json

    promoted = []
    binding = {"artifactId": "art_1", "workspaceId": "ws_1", "baseArtifactVersion": 1}

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        path = request.url.path
        if path.endswith("/runtime"):
            data = {"binding": binding, "draft": {"draftVersion": 1}}
        elif path.endswith("/artifact-commands"):
            command = body["commandType"]
            data = {"status": "completed"}
            if command == "workspace.create-snapshot":
                data["snapshotId"] = "snap_electrical"
            elif command == "artifact.execute":
                assert body["input"]["firmwareOutputId"] == "out_elf"
                assert body["input"]["snapshotId"] == "snap_electrical"
                data["executionRunId"] = "run_sim"
        elif path.endswith("/compile"):
            assert body["requireReal"] is True
            data = {
                "toolchainProfile": {"executionMode": "platformio"},
                "executionRun": {"executionRunId": "run_compile"},
            }
        elif "/executions/" in path:
            data = {"executionRun": {"status": "completed", "executionRunId": path.split("/")[-1]}}
        elif path.endswith("/outputs"):
            rid = request.url.params["executionRunId"]
            name, oid = (
                ("firmware.elf", "out_elf")
                if rid == "run_compile"
                else ("serial.log", "out_serial")
            )
            data = {"items": [{"name": name, "outputId": oid, "executionRunId": rid}]}
        elif path.endswith("/export"):
            data = {"files": {"diagram.json": "{}", "mapping-manifest.json": "{}"}}
        elif path.endswith("/promote-execution"):
            promoted.append(body["executionRunId"])
            data = {"accepted": True}
        elif path.endswith("/import-produced-output"):
            assert body["outputId"] == "out_serial" and body["path"] == "data/serial.log"
            data = {}
        elif path.endswith("/run"):
            data = {"executionRun": {"executionRunId": "run_analysis"}}
        else:
            assert path == "/v1/projects/proj_mock"
            data = {"project": {"currentStateVersion": 4}}
        return httpx.Response(200, json=data)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle), base_url="http://test"
    ) as c:
        demo = runner.GoldenRunner(c, require_real=True)
        demo.pid = "proj_mock"
        await demo.verify()
    assert promoted == ["run_sim", "run_analysis"]
    assert demo.run_ids == ["run_compile", "run_sim", "run_analysis"]


@pytest.mark.parametrize("state", ["missing", "STALE"])
async def test_missing_or_stale_chain_rejected(state: str) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "chains": []
                    if state == "missing"
                    else [
                        {
                            "requirementId": rid,
                            "assessment": "PASS",
                            "executionRunId": "run_old",
                            "evidenceReferences": [{"sourceId": "run_old"}],
                            "applicability": {"state": state},
                        }
                        for rid in runner.DYNAMIC
                    ]
                },
            )
        ),
        base_url="http://test",
    ) as client:
        demo = runner.GoldenRunner(client)
        demo.pid = "proj_mock"

        async def cases() -> Any:
            return {
                rid: [
                    {
                        "assessment": "PASS",
                        "status": "passed",
                        "assessmentAuthority": "deterministic-code",
                    }
                ]
                for rid in runner.DYNAMIC
            }

        demo.cases = cases
        with pytest.raises(runner.AcceptanceError):
            await demo.passed()


@pytest.mark.parametrize("bad_index", [None, 0, 1])
@pytest.mark.parametrize(
    "override",
    [
        {"assessment": "FAIL"},
        {"status": "planned"},
        {"assessmentAuthority": "model"},
    ],
)
async def test_all_linked_cases_checked(bad_index: int | None, override: dict[str, str]) -> None:
    cases = [
        {
            "testCaseId": f"case_{index}",
            "linkedRequirementIds": [f"req_{rid}" for rid in runner.DYNAMIC],
            "assessment": "PASS",
            "status": "passed",
            "assessmentAuthority": "deterministic-code",
        }
        for index in range(2)
    ]
    if bad_index is not None:
        cases[bad_index].update(override)

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/evidence-chain"):
            return httpx.Response(
                200,
                json={
                    "chains": [
                        {
                            "requirementId": rid,
                            "assessment": "PASS",
                            "executionRunId": "run_1",
                            "evidenceReferences": [{"sourceId": "run_1"}],
                            "applicability": {"state": "CURRENT"},
                        }
                        for rid in runner.DYNAMIC
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "artifacts": [
                    {
                        "artifactType": "requirement-set",
                        "content": {
                            "requirements": [
                                {"requirementId": f"req_{rid}", "displayId": rid}
                                for rid in runner.DYNAMIC
                            ]
                        },
                    },
                    {"artifactType": "test-plan", "content": {"testCases": cases}},
                ]
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle), base_url="http://test"
    ) as client:
        demo = runner.GoldenRunner(client)
        linked = await demo.cases()
        assert all(linked[rid] == cases for rid in runner.DYNAMIC)
        if bad_index is None:
            await demo.passed()
        else:
            with pytest.raises(runner.AcceptanceError, match=f"case_{bad_index}"):
                await demo.passed()


async def test_missing_linked_cases_rejected() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "artifacts": [
                        {"artifactType": "requirement-set", "content": {"requirements": []}},
                        {"artifactType": "test-plan", "content": {"testCases": []}},
                    ]
                },
            )
        ),
        base_url="http://test",
    ) as client:
        with pytest.raises(runner.AcceptanceError, match="missingCases"):
            await runner.GoldenRunner(client).passed()


@pytest.mark.parametrize("length", [999, 1000, 1001, 10000])
async def test_http_failure_excerpt_bounded(
    length: int, capsys: pytest.CaptureFixture[str]
) -> None:
    body = "x" * length
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(500, text=body)),
        base_url="http://test",
    ) as client:
        demo = runner.GoldenRunner(client)
        assert await demo.run(through=1) == 1
    prefix, excerpt = demo.last_http.split("\n", 1)
    assert "HTTP 500" in prefix
    assert len(excerpt) == min(length, 1000)
    if length > 1000:
        assert excerpt.endswith("... [truncated]")
    else:
        assert excerpt == body
    stderr = capsys.readouterr().err
    assert demo.last_http in stderr
    if length > 1000:
        assert body not in stderr


async def test_successful_response_excerpt_bounded() -> None:
    payload = {"content": "x" * 2000}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
        base_url="http://test",
    ) as client:
        demo = runner.GoldenRunner(client)
        assert await demo.request("GET", "/large") == payload
        excerpt = demo.last_http.split("\n", 1)[1]
        assert len(excerpt) == 1000
        assert excerpt.endswith("... [truncated]")

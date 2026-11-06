#!/usr/bin/env python3
"""Drive the ten-step Golden Acceptance demo through the public HTTP API.

Uses NEXUS_API_SESSION_TOKEN from the environment. --step N runs prerequisites
through N on fresh projects (there is no unsafe implicit resume). Mock/fixture
runs are regression evidence only; R2/R3 always require manual inspection.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

PROMPT = (
    "Build an ESP32-based vibration monitor using an MPU6050. It should stream "
    "acceleration telemetry and analyze stationary sensor noise to verify that "
    "accel_x RMS noise stays below 0.10 g."
)
DYNAMIC = {"R1", "R4", "R5", "R6", "R7", "R8"}
STEPS = (
    "initialize",
    "accept plan and check files",
    "generate firmware",
    "baseline compile/simulate/analyze PASS",
    "F2 compile fault and repair",
    "F4 address fault and repair (fresh project)",
    "F5 sample-rate fault and repair (fresh project)",
    "mutate code and assert M5 STALE",
    "re-verify CURRENT",
    "evidence and persistence reads",
)


class AcceptanceError(RuntimeError):
    """An HTTP or semantic acceptance failure."""


def require(condition: Any, context: Any) -> None:
    if not condition:
        raise AcceptanceError(str(context))


def positive(value: str) -> float:
    number = float(value)
    if not 0 < number < float("inf"):
        raise argparse.ArgumentTypeError("must be finite and positive")
    return number


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--api-url", default="http://127.0.0.1:8000")
    result.add_argument("--require-real", action="store_true")
    result.add_argument("--timeout", type=positive, default=240, help="seconds per step")
    result.add_argument("--step", type=int, choices=range(1, 11), help="run through this step")
    return result


class GoldenRunner:
    def __init__(
        self, client: httpx.AsyncClient, *, require_real: Any = False, timeout: Any = 240
    ) -> None:
        self.client = client
        self.real = require_real
        self.timeout = timeout
        self.deadline = time.monotonic() + timeout
        self.pid = ""
        self.last_http = "no request yet"
        self.run_ids: list[str] = []
        self.runs: list[tuple[str, str]] = []
        self.actor = {
            "schemaVersion": "1.0.0",
            "actorId": "actor_" + uuid4().hex,
            "actorType": "user",
            "displayName": "Golden Acceptance Operator",
        }

    @property
    def root(self) -> Any:
        return f"/v1/projects/{self.pid}"

    def workspace(self, kind: Any) -> Any:
        return f"/artifacts/{kind}/workspace"

    async def request(self, method: Any, route: Any, body: Any = None, **params: Any) -> Any:
        remaining = self.deadline - time.monotonic()
        require(remaining > 0, "step timeout exceeded")
        if self.real:
            if method == "GET":
                params["requireReal"] = "true"
            else:
                body = {**(body or {}), "requireReal": True}
        self.last_http = f"{method} {route}: awaiting HTTP response"
        response = await self.client.request(
            method, route, json=body, params=params, timeout=remaining
        )
        self.last_http = f"{method} {route}: HTTP {response.status_code}\n{response.text}"
        require(response.is_success, self.last_http)
        return response.json()

    async def get(self, route: Any, **params: Any) -> Any:
        return await self.request("GET", self.root + route, **params)

    async def post(self, route: Any, **body: Any) -> Any:
        return await self.request("POST", self.root + route, {"requestedBy": self.actor, **body})

    async def runtime(self, kind: Any) -> Any:
        return await self.get(self.workspace(kind) + "/runtime")

    async def guards(self, kind: Any) -> Any:
        runtime = await self.runtime(kind)
        project = await self.get("")
        return {
            "expectedDraftVersion": runtime["draft"]["draftVersion"],
            "baseArtifactVersion": runtime["binding"]["baseArtifactVersion"],
            "baseProjectStateVersion": project["project"]["currentStateVersion"],
        }

    async def command(self, kind: Any, binding: Any, data: Any) -> Any:
        project = await self.get("")
        result = await self.post(
            "/artifact-commands",
            schemaVersion="1.0.0",
            commandId="cmd_" + uuid4().hex,
            commandType=kind,
            projectId=self.pid,
            artifactId=binding["artifactId"],
            workspaceId=binding["workspaceId"],
            baseArtifactVersion=binding["baseArtifactVersion"],
            baseProjectStateVersion=project["project"]["currentStateVersion"],
            requestedAt=datetime.now(UTC).isoformat(),
            input=data,
        )
        require(result.get("status") == "completed", result)
        return result

    async def lease(self, kind: Any) -> Any:
        await self.command(
            "workspace.acquire-edit-lease", (await self.runtime(kind))["binding"], {}
        )

    async def initialize(self) -> Any:
        result = await self.request(
            "POST", "/v1/projects/initialize", {"message": PROMPT, "autonomyMode": "collaborate"}
        )
        self.pid = result["project"]["projectId"]

    async def plan(self) -> Any:
        project = await self.get("")
        plan = await self.post(
            "/execution-plan/propose",
            configuration=None,
            baseProjectStateVersion=project["project"]["currentStateVersion"],
            basePlanVersion=0,
        )
        await self.command(
            "artifact.accept-revision",
            plan["workspace"],
            {"proposalId": plan["commandResult"]["proposalId"]},
        )
        for kind, names in {
            "firmware": {"platformio.ini", "src/main.cpp", "nexus/approved-plan.json"},
            "analysis": {"analysis.py", "nexus/approved-plan.json"},
        }.items():
            files = await self.get(self.workspace(kind) + "/files")
            require(names <= {f["path"] for f in files["files"]}, files)
            await self.lease(kind)
        await self.lease("electrical-architecture")

    async def apply(self, proposal_id: Any) -> Any:
        root = self.workspace("firmware")
        proposal = (await self.get(root + f"/patch/{proposal_id}"))["proposal"]
        require(proposal["status"] == "proposed", proposal)
        if self.real:
            require(proposal["generatorMetadata"]["mode"] == "llm", proposal)
        operations = proposal["operations"]
        require(
            len(operations) == 1
            and operations[0]["operationType"] == "replace-file"
            and operations[0]["path"] == "src/main.cpp",
            operations,
        )
        source = operations[0]["content"]
        require(
            all(
                s in source
                for s in ("Wire.begin(", "115200", "NEXUS_MPU_READY", "NEXUS_MPU_INIT_FAIL", "TEL,")
            ),
            source,
        )
        require("Wire.begn(" not in source, source)
        require(re.search(r"MPU_ADDR\s*=\s*0x68\b", source), "missing approved MPU_ADDR")
        require(re.search(r"SAMPLE_INTERVAL_MS\s*=\s*20\b", source), "missing 50 Hz interval")
        result = await self.post(
            root + "/patch/apply", proposalId=proposal_id, **await self.guards("firmware")
        )
        require(result["status"] == "applied", result)

    async def generate(self) -> Any:
        result = await self.post(
            self.workspace("firmware") + "/patch/propose",
            requestedChange="Implement the approved ESP32 MPU6050 monitor. "
            "Use MPU_ADDR=0x68, SAMPLE_INTERVAL_MS=20, Wire.begin, 115200 baud, "
            "NEXUS_MPU_READY/NEXUS_MPU_INIT_FAIL, time_s,accel_x_g,accel_y_g,"
            "accel_z_g header and TEL, samples at 50 Hz.",
            allowFixture=not self.real,
        )
        await self.apply(result["proposal"]["proposalId"])

    async def wait(self, run_id: Any, *, success: Any = True) -> Any:
        require(run_id, "missing executionRunId")
        self.run_ids.append(run_id)
        self.runs.append((self.pid, run_id))
        while True:
            run = (await self.get(f"/executions/{run_id}"))["executionRun"]
            if run["status"] not in {"queued", "running", "pending"}:
                if success:
                    require(run["status"] == "completed", run)
                return run
            require(time.monotonic() < self.deadline, run)
            await asyncio.sleep(min(0.5, max(0, self.deadline - time.monotonic())))

    async def compile(self, *, success: Any = True) -> Any:
        result = await self.post(self.workspace("firmware") + "/compile")
        if self.real:
            require(result["toolchainProfile"]["executionMode"] == "platformio", result)
        return await self.wait(result["executionRun"]["executionRunId"], success=success)

    async def promote(self, run_id: Any) -> Any:
        await self.post("/verify/promote-execution", executionRunId=run_id, accept=True)

    async def verify(self, *, analyze: Any = True) -> Any:
        for kind in ("firmware", "analysis", "electrical-architecture"):
            await self.lease(kind)
        run = await self.compile()
        outputs = (await self.get("/outputs", executionRunId=run["executionRunId"]))["items"]
        elf = next(o for o in outputs if o["name"].endswith("firmware.elf"))
        binding = (await self.runtime("electrical-architecture"))["binding"]
        snap = await self.command(
            "workspace.create-snapshot", binding, {"reason": "before-execution"}
        )
        sim = await self.command(
            "artifact.execute",
            binding,
            {
                "snapshotId": snap["snapshotId"],
                "capability": "circuit-simulation",
                "firmwareOutputId": elf["outputId"],
            },
        )
        await self.wait(sim["executionRunId"])
        exported = await self.get("/artifacts/electrical-architecture/circuit-simulation/export")
        require({"diagram.json", "mapping-manifest.json"} <= set(exported["files"]), exported)
        await self.promote(sim["executionRunId"])
        if not analyze:
            return sim["executionRunId"]
        outputs = (await self.get("/outputs", executionRunId=sim["executionRunId"]))["items"]
        serial = next(o for o in outputs if o["name"] == "serial.log")
        await self.post(
            self.workspace("analysis") + "/inputs/import-produced-output",
            path="data/serial.log",
            outputId=serial["outputId"],
            **await self.guards("analysis"),
        )
        analysis = await self.post(self.workspace("analysis") + "/run")
        run = await self.wait(analysis["executionRun"]["executionRunId"])
        await self.promote(run["executionRunId"])

    async def cases(self) -> Any:
        project = await self.get("")
        artifacts = project["artifacts"]
        requirements = next(
            a["content"]["requirements"]
            for a in artifacts
            if a["artifactType"] == "requirement-set"
        )
        ids = {r["requirementId"]: r["displayId"] for r in requirements}
        cases = next(
            a["content"]["testCases"] for a in artifacts if a["artifactType"] == "test-plan"
        )
        return {ids.get(r, r): c for c in cases for r in c["linkedRequirementIds"]}

    async def passed(self) -> Any:
        cases = await self.cases()
        for rid in DYNAMIC:
            case = cases.get(rid, {})
            require(
                case.get("assessment") == "PASS"
                and case.get("status") == "passed"
                and case.get("assessmentAuthority") == "deterministic-code",
                {rid: case},
            )
        chain = await self.get("/verify/evidence-chain")
        for rid in DYNAMIC:
            linked = [c for c in chain["chains"] if c.get("requirementId") == rid]
            require(linked, {"missingChain": rid})
            for link in linked:
                require(
                    link.get("assessment") == "PASS"
                    and (link.get("applicability") or {}).get("state") == "CURRENT"
                    and link.get("executionRunId")
                    and link.get("evidenceReferences"),
                    link,
                )

    async def write(self, source: Any) -> Any:
        await self.lease("firmware")
        return await self.request(
            "PUT",
            self.root + self.workspace("firmware") + "/file",
            {
                "path": "src/main.cpp",
                "content": source,
                "requestedBy": self.actor,
                "origin": "USER",
                "writePolicy": "USER_EDITABLE",
                **await self.guards("firmware"),
            },
        )

    async def source(self) -> Any:
        return (await self.get(self.workspace("firmware") + "/file", path="src/main.cpp"))[
            "content"
        ]

    async def repair(self, run_id: Any) -> Any:
        state = await self.post(
            "/repair",
            action="start",
            executionRunId=run_id,
            target="firmware",
            scope="full",
            maxAttempts=3,
        )
        while state["status"] != "completed":
            require(state["status"] in {"inspect", "review", "running"}, state)
            print(
                f"  repair={state['repairId']} revision={state['revision']} "
                f"stage={state.get('stage')} status={state['status']}"
            )
            if state["status"] == "review":
                await self.lease("firmware")
                await self.apply(state["proposalId"])
                state = await self.post("/repair", action="get", repairId=state["repairId"])
            elif state["status"] == "running":
                await self.wait(state["runId"])
            state = await self.post(
                "/repair", action="advance", repairId=state["repairId"], revision=state["revision"]
            )
        await self.passed()

    async def fault(self, fault: Any) -> Any:
        if fault != "F2":
            await self.initialize()
            await self.plan()
            await self.generate()
            await self.verify()
            await self.passed()
        source = await self.source()
        pattern, replacement = {
            "F2": (r"Wire\.begin\(", "Wire.begn("),
            "F4": (r"(MPU_ADDR\s*=\s*)0x68\b", r"\g<1>0x69"),
            "F5": (r"(SAMPLE_INTERVAL_MS\s*=\s*)20\b", r"\g<1>40"),
        }[fault]
        require(len(re.findall(pattern, source)) == 1, f"ambiguous {fault} injection")
        await self.write(re.sub(pattern, replacement, source, count=1))
        if fault == "F2":
            run = await self.compile(success=False)
            require(run["status"] == "failed", run)
            logs = await self.get(f"/executions/{run['executionRunId']}/logs")
            require("begn" in str(logs), logs)
        else:
            await self.verify(analyze=fault != "F4")
            cases = await self.cases()
            rid = "R4" if fault == "F4" else "R6"
            require(cases[rid]["assessment"] == "FAIL", cases[rid])
            chain = (await self.get("/verify/evidence-chain"))["chains"]
            failed = next(
                c for c in chain if c.get("requirementId") == rid and c.get("assessment") == "FAIL"
            )
            run = {"executionRunId": failed["executionRunId"]}
        await self.repair(run["executionRunId"])

    async def stale(self) -> Any:
        await self.write(await self.source() + "\n// Golden acceptance M5 edit\n")
        binding = (await self.runtime("firmware"))["binding"]
        snapshot = await self.command("workspace.create-snapshot", binding, {"reason": "manual"})
        proposal = await self.command(
            "artifact.propose-revision", binding, {"snapshotId": snapshot["snapshotId"]}
        )
        await self.command(
            "artifact.accept-revision", binding, {"proposalId": proposal["proposalId"]}
        )
        chain = await self.get("/verify/evidence-chain")
        require(
            any((c.get("applicability") or {}).get("state") == "STALE" for c in chain["chains"]),
            chain,
        )

    async def persistence(self) -> Any:
        # Read-after-write durability only. Restart requires operator-owned process control.
        current_pid = self.pid
        for pid, run_id in dict.fromkeys(self.runs):
            self.pid = pid
            route = f"/executions/{run_id}"
            before = await self.get(route)
            require(before == await self.get(route), route)
            run = before["executionRun"]
            snapshot_id = run.get("inputSnapshotId")
            require(snapshot_id, run)
            for output_id in run.get("outputReferences", []):
                output = await self.get(f"/outputs/{output_id}")
                require(output == await self.get(f"/outputs/{output_id}"), output)
            outputs = (await self.get("/outputs", executionRunId=run_id))["items"]
            summary_output = next((o for o in outputs if o["name"] == "outputs/summary.json"), None)
            if summary_output:
                root = self.workspace("analysis")
                preview = await self.get(root + f"/outputs/{summary_output['outputId']}/preview")
                require(not preview["truncated"], preview)
                summary = json.loads(preview["text"])
                original = await self.get(
                    root + f"/snapshots/{snapshot_id}/file", path="data/serial.log"
                )
                require(
                    summary["inputSha256"]
                    == hashlib.sha256(original["content"].encode()).hexdigest(),
                    summary,
                )
        self.pid = current_pid
        await self.passed()
        print("  Persistence: read-after-write only; restart not tested. R2/R3: manual review.")

    async def run(self, through: Any = 10) -> Any:
        async def baseline() -> Any:
            await self.verify()
            await self.passed()

        actions = [
            self.initialize,
            self.plan,
            self.generate,
            baseline,
            lambda: self.fault("F2"),
            lambda: self.fault("F4"),
            lambda: self.fault("F5"),
            self.stale,
            baseline,
            self.persistence,
        ]
        for index, action in enumerate(actions[:through], 1):
            started = time.monotonic()
            self.deadline = started + self.timeout
            try:
                await asyncio.wait_for(action(), timeout=self.timeout)
            except (
                AcceptanceError,
                httpx.HTTPError,
                TimeoutError,
                KeyError,
                ValueError,
                RuntimeError,
            ) as exc:
                print(
                    f"\033[31mFAIL step {index}: {STEPS[index - 1]} project={self.pid}\033[0m\n"
                    f"runIds={','.join(self.run_ids)} elapsed={time.monotonic() - started:.2f}s\n"
                    f"{exc}\nLast HTTP: {self.last_http}",
                    file=sys.stderr,
                )
                return 1
            print(
                f"\033[32mPASS step {index}: {STEPS[index - 1]}\033[0m "
                f"project={self.pid} runIds={','.join(self.run_ids)} "
                f"elapsed={time.monotonic() - started:.2f}s"
            )
        return 0


async def async_main(args: Any) -> Any:
    token = os.environ.get("NEXUS_API_SESSION_TOKEN", "nexus-dev-session-token")
    async with httpx.AsyncClient(
        base_url=args.api_url, headers={"Authorization": f"Bearer {token}"}
    ) as client:
        return await GoldenRunner(client, require_real=args.require_real, timeout=args.timeout).run(
            args.step or 10
        )


def main(argv: Any = None) -> Any:
    return asyncio.run(async_main(parser().parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())

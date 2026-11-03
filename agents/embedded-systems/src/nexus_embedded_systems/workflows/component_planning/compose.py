"""Assemble ComponentPlanContent and artifact envelopes."""

from __future__ import annotations

import re
from typing import Any

from nexus_embedded_systems.workflows.project_initialization.ids import (
    artifact_envelope,
    default_actor,
    new_id,
    utc_now,
)

from .coverage import compute_coverage_summary
from .derive_constraints import derive_constraints_from_requirements
from .derive_roles import derive_roles_from_architecture, is_i2c_bus
from .maturity import compute_maturity
from .propose_candidates import propose_candidates_for_roles, requests_supported_prototype


def compose_component_plan_content(
    *,
    architecture_content: dict[str, Any],
    requirement_set_content: dict[str, Any],
    include_candidates: bool = True,
    user_message: str = "",
    source: str = "inferred",
    proposed_by: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Derive a provisional Component Plan from architecture and requirements."""

    stamp = now or utc_now()
    actor = proposed_by or default_actor("vera", display_name="Vera")
    roles = derive_roles_from_architecture(architecture_content, source=source)
    # Functional compute/control/analysis nodes share the user-named MCU in the
    # bounded ESP32/MPU6050 prototype; model assumption prose is not evidence of
    # separate processors. Explicit additional platforms remain ambiguous.
    single_platform = requests_supported_prototype(user_message) and not re.search(
        r"\b(?:STM32\w*|RP2040|RP2350|ATmega\w*|Arduino|Raspberry\s+Pi|"
        r"ESP8266|ESP32[- ](?:S[23]|C[236]|H2|P4)|"
        r"(?:two|multiple|second|another|additional)\s+(?:ESP32|MCU|processor|microcontroller))\b",
        user_message,
        re.I,
    )
    if single_platform:
        # Sensor acquisition is firmware on the host, not another physical IMU.
        acquisition_nodes = {
            n["nodeId"]
            for n in architecture_content.get("nodes", [])
            if n.get("functionalType") == "input"
            and re.search(r"sensor.*acquisition|acquisition.*interface", n.get("name", ""), re.I)
        }
        for role in roles:
            if acquisition_nodes.intersection(role["architectureNodeIds"]):
                role["category"] = "compute"
    compute_roles = [r for r in roles if r.get("category") == "compute"]
    if single_platform and compute_roles:
        primary = compute_roles[0]
        for role in compute_roles[1:]:
            for key in ("architectureNodeIds", "requirementIds"):
                primary[key] = list(dict.fromkeys([*primary[key], *role[key]]))
            roles.remove(role)
        primary["name"] = "ESP32 host compute role"
        primary["description"] = "Hosts the functional compute, control, and analysis subsystems."
        primary["rationale"] += " Functional compute roles share the user-named ESP32 platform."
    requirements = list(requirement_set_content.get("requirements") or [])
    constraints = derive_constraints_from_requirements(roles=roles, requirements=requirements)
    candidates = (
        propose_candidates_for_roles(
            roles, max_per_role=2, source="fixture", prefer_first=True, user_message=user_message
        )
        if include_candidates
        else []
    )
    # The functional architecture supplies topology, not verified datasheet claims.
    bus_ids = {
        n["nodeId"]
        for n in (architecture_content.get("nodes") or [])
        if isinstance(n, dict)
        and isinstance(n.get("nodeId"), str)
        and is_i2c_bus(n, architecture_content)
    }
    i2c_nodes = {
        endpoint
        for edge in (architecture_content.get("edges") or [])
        if isinstance(edge, dict)
        and edge.get("flowType") in {"data", "control"}
        and (
            edge.get("fromNodeId") in bus_ids
            or edge.get("toNodeId") in bus_ids
            or "i2c" in str(edge.get("description") or "").casefold()
        )
        for endpoint in (edge.get("fromNodeId"), edge.get("toNodeId"))
        if isinstance(endpoint, str)
    }
    i2c_roles = {
        r["componentRoleId"] for r in roles if i2c_nodes.intersection(r["architectureNodeIds"])
    }
    sensor_nodes = {
        node_id
        for role in roles
        if role.get("category") == "sensor"
        for node_id in role["architectureNodeIds"]
        if isinstance(node_id, str)
    }
    # Do not replace an explicitly different sensor transport with the prototype
    # assumption. Missing topology still produces no usable electrical binding.
    prototype_i2c = single_platform and not any(
        edge.get("flowType") in {"data", "control"}
        and sensor_nodes.intersection((edge.get("fromNodeId"), edge.get("toNodeId")))
        and re.search(r"\b(spi|uart|serial|analog)\b", str(edge.get("description", "")), re.I)
        for edge in architecture_content.get("edges", [])
    )
    for candidate in candidates:
        if (
            candidate.get("source") == "user-provided"
            and candidate.get("partNumber") in {"ESP32-DEVKIT-V1", "MPU6050"}
            and (candidate["componentRoleId"] in i2c_roles or prototype_i2c)
        ):
            candidate["specifications"].append(
                {"specKey": "interface", "value": "I2C", "operator": "eq"}
            )
            candidate["notes"] += (
                " I2C interface inferred from supported single-platform prototype; unverified."
                if single_platform
                else " I2C interface inferred from functional architecture; unverified."
            )

    selections: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    open_questions: list[dict[str, Any]] = []

    if include_candidates and candidates:
        preferred_by_role: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            role_id = str(candidate["componentRoleId"])
            if candidate.get("candidateState") == "preferred" and role_id not in preferred_by_role:
                preferred_by_role[role_id] = candidate

        for role in roles:
            role_id = str(role["componentRoleId"])
            preferred = preferred_by_role.get(role_id)
            if preferred is None:
                role["status"] = "needs-clarification"
                continue
            check = _interface_check(role, preferred, actor=actor, now=stamp)
            checks.append(check)
            preferred["compatibilityCheckIds"] = [check["compatibilityCheckId"]]
            selections.append(
                {
                    "selectionDecisionId": new_id("sel_"),
                    "componentRoleId": role_id,
                    "selectedCandidateId": preferred["candidateId"],
                    "selectionState": "awaiting-user",
                    "rationale": (
                        f"Provisional preference for {preferred['displayName']} based on "
                        "known interface/supply assumptions pending user approval."
                    ),
                    "tradeoffs": list(preferred.get("limitations") or [])[:3]
                    or ["Evidence remains unverified"],
                    "source": "fixture" if source == "fixture" else "agent-proposed",
                    "proposedBy": actor,
                    "approvalRequirement": {
                        "schemaVersion": "1.0.0",
                        "required": True,
                        "reason": (
                            "Component selection requires user confirmation before procurement."
                        ),
                        "consequenceLevel": "high",
                        "allowedApproverKinds": ["user"],
                        "autoAcceptAllowed": False,
                    },
                    "createdAt": stamp,
                }
            )
            role["status"] = "selection-proposed"

        for role in roles:
            if not role.get("requirementIds"):
                qid = new_id("q_")
                open_questions.append(
                    {
                        "questionId": qid,
                        "summary": f"Which requirements justify the {role['name']}?",
                    }
                )
                role["openQuestionIds"] = [qid]

    content: dict[str, Any] = {
        "componentPlanId": new_id("cplan_"),
        "maturity": "roles-defined",
        "summary": _summary(roles, candidates, selections),
        "componentRoles": roles,
        "selectionConstraints": constraints,
        "candidates": candidates,
        "selectionDecisions": selections,
        "compatibilityChecks": checks,
        "openQuestions": open_questions,
        "assumptions": [
            "Candidate retrieval and datasheet grounding are deferred until constraints "
            "are confirmed."
            if not candidates
            else (
                (
                    "Provisional candidates include user-named parts and fixture placeholders. "
                    if any(c.get("source") != "fixture" for c in candidates)
                    else "Provisional candidates are fixture-backed placeholders. "
                )
                + "Pricing, availability, and datasheet claims remain unverified."
            )
        ],
        "evidenceReferences": [],
        "coverageSummary": {
            "totalArchitectureNodes": 0,
            "coveredArchitectureNodes": 0,
            "uncoveredArchitectureNodeIds": [],
            "totalRelevantRequirements": 0,
            "coveredRequirementIds": [],
            "uncoveredRequirementIds": [],
            "rolesWithoutArchitectureMapping": 0,
            "rolesWithoutRequirementMapping": 0,
            "rolesWithoutCandidates": 0,
            "rolesWithBlockedSelection": 0,
            "rolesAwaitingApproval": 0,
        },
        "validationSummary": {
            "issueCount": len(open_questions) + sum(1 for c in checks if c.get("status") != "pass"),
            "blockingIssueCount": 0,
            "warningCount": sum(
                1 for c in checks if c.get("status") in {"unknown", "conditional", "warning"}
            ),
            "status": "warnings" if checks else "ok",
        },
    }
    content["coverageSummary"] = compute_coverage_summary(
        content, architecture_content=architecture_content
    )
    content["maturity"] = compute_maturity(content)
    return content


def compose_component_plan_envelope(
    *,
    content: dict[str, Any],
    project_id: str,
    turn_id: str,
    workflow_run_id: str,
    created_by: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    return artifact_envelope(
        artifact_type="component-plan",
        content=content,
        project_id=project_id,
        turn_id=turn_id,
        workflow_run_id=workflow_run_id,
        created_by=created_by,
        now=now,
        lifecycle_status="drafted",
        evidence_status="unverified",
        approval_status="proposed",
    )


def _interface_check(
    role: dict[str, Any],
    candidate: dict[str, Any],
    *,
    actor: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    specs = candidate.get("specifications") or []
    has_interface = any(
        isinstance(s, dict) and s.get("specKey") == "interface" and not _is_unknown(s.get("value"))
        for s in specs
    )
    status = "conditional" if has_interface else "unknown"
    return {
        "compatibilityCheckId": new_id("cchk_"),
        "componentRoleId": role["componentRoleId"],
        "candidateId": candidate["candidateId"],
        "checkType": "interface-type",
        "status": status,
        "severity": "warning",
        "reason": (
            "Candidate declares an interface, but bus topology and address conflicts "
            "are not yet checked against the full architecture."
            if has_interface
            else "Interface requirement or candidate interface value is unknown."
        ),
        "inputReferences": list(role.get("architectureNodeIds") or [])[:4],
        "evidenceReferences": [],
        "performedBy": actor,
        "performedAt": now,
    }


def _is_unknown(value: Any) -> bool:
    return isinstance(value, dict) and value.get("kind") == "unknown"


def _summary(
    roles: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    selections: list[dict[str, Any]],
) -> str:
    role_count = len(roles)
    candidate_count = len(candidates)
    preferred = sum(
        1 for s in selections if s.get("selectionState") in {"proposed", "awaiting-user"}
    )
    if candidate_count:
        qualifier = "fixture " if all(c.get("source") == "fixture" for c in candidates) else ""
        return (
            f"Provisional component plan with {role_count} role(s), "
            f"{candidate_count} {qualifier}candidate(s), and {preferred} preferred "
            "proposal(s) awaiting user approval. Evidence remains unverified."
        )
    return (
        f"Initial component roles ({role_count}) derived from functional architecture "
        "for provisional sensor/compute planning."
    )

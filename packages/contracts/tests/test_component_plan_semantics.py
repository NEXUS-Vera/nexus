"""Component Plan semantic validation tests."""

from __future__ import annotations

from copy import deepcopy

from nexus_contracts.validation.semantic_validators import validate_component_plan_content


def _base_plan() -> dict:
    return {
        "maturity": "candidates-proposed",
        "summary": "Test plan",
        "componentRoles": [
            {
                "componentRoleId": "role_ABCDEFGHIJKLMNOPQRST",
                "displayId": "CR1",
                "name": "Temp sensor",
                "category": "sensor",
                "description": "Measure temperature",
                "architectureNodeIds": ["node_ABCDEFGHIJKLMNOPQRST"],
                "requirementIds": ["req_ABCDEFGHIJKLMNOPQRSTUV"],
                "requiredCapabilities": ["temperature"],
                "status": "identified",
                "priority": "high",
                "source": "fixture",
                "rationale": "Sensing node",
            }
        ],
        "selectionConstraints": [],
        "candidates": [
            {
                "candidateId": "cand_ABCDEFGHIJKLMNOPQRST",
                "componentRoleId": "role_ABCDEFGHIJKLMNOPQRST",
                "manufacturer": "Fixture",
                "partNumber": "FX-1",
                "displayName": "Fixture sensor",
                "candidateCategory": "sensor",
                "candidateState": "proposed",
                "evidenceStatus": "unverified",
                "specifications": [],
                "advantages": ["ok"],
                "limitations": ["unknown"],
                "compatibilityCheckIds": [],
                "evidenceReferences": [],
                "source": "fixture",
                "confidence": "low",
            }
        ],
        "selectionDecisions": [],
        "compatibilityChecks": [],
        "openQuestions": [],
        "assumptions": ["a"],
        "evidenceReferences": [],
        "coverageSummary": {
            "totalArchitectureNodes": 1,
            "coveredArchitectureNodes": 1,
            "uncoveredArchitectureNodeIds": [],
            "totalRelevantRequirements": 1,
            "coveredRequirementIds": ["req_ABCDEFGHIJKLMNOPQRSTUV"],
            "uncoveredRequirementIds": [],
            "rolesWithoutArchitectureMapping": 0,
            "rolesWithoutRequirementMapping": 0,
            "rolesWithoutCandidates": 0,
            "rolesWithBlockedSelection": 0,
            "rolesAwaitingApproval": 0,
        },
        "validationSummary": {
            "issueCount": 0,
            "blockingIssueCount": 0,
            "warningCount": 0,
            "status": "ok",
        },
    }


def test_valid_plan_passes() -> None:
    errors = validate_component_plan_content(
        _base_plan(),
        architecture_node_ids={"node_ABCDEFGHIJKLMNOPQRST"},
        requirement_ids={"req_ABCDEFGHIJKLMNOPQRSTUV"},
    )
    assert errors == []


def test_unknown_architecture_node() -> None:
    plan = _base_plan()
    errors = validate_component_plan_content(
        plan,
        architecture_node_ids={"node_OTHERNODE0000000001"},
        requirement_ids={"req_ABCDEFGHIJKLMNOPQRSTUV"},
    )
    assert any(e.code == "COMPONENT_UNKNOWN_ARCHITECTURE_NODE" for e in errors)


def test_blocked_candidate_cannot_be_approved() -> None:
    plan = _base_plan()
    plan["candidates"][0]["candidateState"] = "blocked"
    plan["selectionDecisions"] = [
        {
            "selectionDecisionId": "sel_ABCDEFGHIJKLMNOPQRST",
            "componentRoleId": "role_ABCDEFGHIJKLMNOPQRST",
            "selectedCandidateId": "cand_ABCDEFGHIJKLMNOPQRST",
            "selectionState": "approved",
            "rationale": "bad",
            "tradeoffs": [],
            "source": "fixture",
            "proposedBy": {
                "schemaVersion": "1.0.0",
                "actorId": "actor_ABCDEFGHIJKLMNOPQRST",
                "actorType": "vera",
            },
            "approvalRequirement": {
                "schemaVersion": "1.0.0",
                "required": True,
                "reason": "needs approval",
                "consequenceLevel": "high",
                "allowedApproverKinds": ["user"],
                "autoAcceptAllowed": False,
            },
            "createdAt": "2026-08-04T12:00:00Z",
        }
    ]
    errors = validate_component_plan_content(plan)
    assert any(e.code == "COMPONENT_SELECTION_BLOCKED_CANDIDATE_APPROVED" for e in errors)


def test_tested_evidence_rejected() -> None:
    plan = deepcopy(_base_plan())
    plan["candidates"][0]["evidenceStatus"] = "tested"
    plan["candidates"][0]["evidenceReferences"] = [
        {
            "schemaVersion": "1.0.0",
            "evidenceId": "evi_ABCDEFGHIJKLMNOPQRST",
            "sourceType": "user-turn",
            "sourceId": "turn_ABCDEFGHIJKLMNOPQRST",
            "evidenceStrength": "direct",
        }
    ]
    errors = validate_component_plan_content(plan)
    assert any(e.code == "COMPONENT_CANDIDATE_OVERSTATED_EVIDENCE" for e in errors)


def test_coverage_mismatch() -> None:
    plan = _base_plan()
    plan["coverageSummary"]["rolesWithoutCandidates"] = 99
    errors = validate_component_plan_content(plan)
    assert any(e.code == "COMPONENT_COVERAGE_MISMATCH" for e in errors)

# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing_extensions import TypedDict

class ComponentPlanCoverageSummaryV1(TypedDict, closed=True):
    coveredArchitectureNodes: int
    coveredRequirementIds: list[str]
    rolesAwaitingApproval: int
    rolesWithBlockedSelection: int
    rolesWithoutArchitectureMapping: int
    rolesWithoutCandidates: int
    rolesWithoutRequirementMapping: int
    totalArchitectureNodes: int
    totalRelevantRequirements: int
    uncoveredArchitectureNodeIds: list[str]
    uncoveredRequirementIds: list[str]

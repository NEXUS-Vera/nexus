# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Assumption(TypedDict, closed=True):
    assumptionId: str
    confidence: Literal['high', 'medium', 'low']
    confirmationStatus: Literal[
        'confirmed', 'proposed', 'needs-confirmation', 'rejected'
    ]
    sourceType: Literal[
        'user-explicit', 'user-implied', 'system-inferred', 'project-policy'
    ]
    statement: str

class Edge(TypedDict, closed=True):
    description: str
    edgeId: str
    flowType: Literal['data', 'control', 'power', 'user-input', 'physical-output']
    fromNodeId: str
    toNodeId: str

class Input(TypedDict, closed=True):
    dataType: str
    description: str

class Output(TypedDict, closed=True):
    dataType: str
    description: str

class Node(TypedDict, closed=True):
    functionalType: Literal[
        'input',
        'sensing',
        'processing',
        'control',
        'storage',
        'communication',
        'power',
        'output',
        'actuation',
        'analysis',
        'user-interface',
        'external-system',
    ]
    inputs: NotRequired[list[Input]]
    name: str
    nodeId: str
    outputs: NotRequired[list[Output]]
    responsibilities: list[str]
    satisfiesRequirementIds: list[str]

class RequirementCoverage(TypedDict, closed=True):
    coveredRequirementIds: list[str]

class UnresolvedDecision(TypedDict, closed=True):
    displayId: NotRequired[str]
    questionId: str
    schemaVersion: Literal['1.0.0']

class FunctionalArchitectureV1(TypedDict, closed=True):
    architectureId: str
    architectureMaturity: Literal['functional']
    assumptions: list[Assumption]
    edges: list[Edge]
    nodes: list[Node]
    requirementCoverage: RequirementCoverage
    systemBoundary: str
    unresolvedDecisions: list[UnresolvedDecision]

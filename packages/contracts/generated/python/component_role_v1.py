# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ComponentRoleV1(TypedDict, closed=True):
    architectureNodeIds: list[str]
    category: Literal[
        'sensor',
        'compute',
        'power',
        'communication',
        'storage',
        'interface',
        'actuation',
        'protection',
        'mechanical',
        'supporting-electronics',
    ]
    componentRoleId: str
    description: str
    displayId: str
    name: str
    openQuestionIds: NotRequired[list[str]]
    priority: Literal['low', 'medium', 'high', 'blocking']
    rationale: str
    requiredCapabilities: list[str]
    requirementIds: list[str]
    source: Literal['user-explicit', 'inferred', 'agent-proposed', 'fixture']
    status: Literal[
        'identified',
        'needs-clarification',
        'ready-for-candidates',
        'candidate-review',
        'selection-proposed',
        'selected',
        'blocked',
        'superseded',
    ]

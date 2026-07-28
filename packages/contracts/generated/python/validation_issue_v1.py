# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class ValidationIssueV1(TypedDict, closed=True):
    artifactId: NotRequired[str]
    blocking: bool
    code: str
    createdAt: str
    issueId: str
    itemId: NotRequired[str]
    message: str
    projectId: str
    resolutionStatus: Literal['open', 'resolved']
    resolutionType: Literal[
        'user-input',
        'artifact-regeneration',
        'manual-review',
        'automatic-fix',
        'not-applicable',
    ]
    resolvedAt: NotRequired[str]
    schemaVersion: Literal['1.0.0']
    severity: Literal['critical', 'high', 'medium', 'low', 'info']
    suggestedResolution: NotRequired[str]

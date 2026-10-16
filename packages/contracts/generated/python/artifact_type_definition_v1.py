# This file is GENERATED from packages/contracts/schemas.
# Do not edit manually. Re-run: make generate-contract-types
from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

class Dependency(TypedDict, closed=True):
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'code-scratch',
    ]
    relationship: Literal['depends-on', 'derives-from', 'constrains', 'covers']
    required: NotRequired[bool]

class ArtifactTypeDefinitionV1(TypedDict, closed=True):
    approvalPolicyId: str
    artifactType: Literal[
        'project-brief',
        'requirement-set',
        'functional-architecture',
        'next-action',
        'component-plan',
        'code-scratch',
    ]
    boardVisibility: Literal['primary', 'global', 'hidden']
    dependencies: list[Dependency]
    displayName: str
    editable: bool
    executable: bool
    phase: Literal['DEFINE', 'DESIGN', 'BUILD', 'VERIFY']
    requiredCapabilities: list[
        Literal[
            'structured-validation',
            'fake-execution',
            'file-workspace',
            'sandbox-execution',
            'embedded-build',
            'python-kernel',
            'circuit-simulation',
            'architecture-export',
        ]
    ]
    schemaVersion: Literal['1.0.0']
    supportedCommandTypes: list[
        Literal[
            'workspace.create',
            'workspace.update-draft',
            'workspace.acquire-edit-lease',
            'workspace.release-edit-lease',
            'workspace.discard-draft',
            'workspace.create-snapshot',
            'workspace.restore-snapshot',
            'artifact.validate-draft',
            'artifact.propose-revision',
            'artifact.accept-revision',
            'artifact.reject-revision',
            'artifact.execute',
        ]
    ]
    workspaceType: Literal[
        'structured-document',
        'graph-workspace',
        'comparison-workspace',
        'code-workspace',
        'notebook-workspace',
        'test-workspace',
        'risk-workspace',
        'focused-action',
    ]

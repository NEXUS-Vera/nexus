"""Internal generation schemas for model-owned content (no trusted runtime IDs)."""

from __future__ import annotations

from typing import Any

PROJECT_INTERPRETATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "withinBoundary",
        "supportedDomain",
        "projectStage",
        "primaryGoal",
        "physicalComputingPresent",
        "embeddedProductPresent",
        "candidateProjectTitle",
        "explicitUserClaims",
        "likelyMissingDimensions",
        "unsupportedReasons",
    ],
    "properties": {
        "withinBoundary": {"type": "boolean"},
        "supportedDomain": {"type": "boolean"},
        "projectStage": {
            "type": "string",
            "enum": ["concept", "prototype-planning", "unsupported"],
        },
        "primaryGoal": {"type": "string"},
        "physicalComputingPresent": {"type": "boolean"},
        "embeddedProductPresent": {"type": "boolean"},
        "candidateProjectTitle": {"type": "string"},
        "explicitUserClaims": {"type": "array", "items": {"type": "string"}},
        "likelyMissingDimensions": {"type": "array", "items": {"type": "string"}},
        "unsupportedReasons": {"type": "array", "items": {"type": "string"}},
    },
}

PROJECT_BRIEF_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "goal",
        "problemStatement",
        "intendedContext",
        "projectStage",
        "scope",
        "outOfScope",
        "successCriteria",
        "assumptions",
        "unknownStatements",
    ],
    "properties": {
        "goal": {"type": "string", "minLength": 1},
        "problemStatement": {"type": "string", "minLength": 1},
        "intendedContext": {"type": "string", "minLength": 1},
        "projectStage": {"type": "string", "enum": ["concept", "prototype-planning"]},
        "scope": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "outOfScope": {"type": "array", "items": {"type": "string"}},
        "successCriteria": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "assumptions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "statement",
                    "sourceType",
                    "confidence",
                    "confirmationStatus",
                ],
                "properties": {
                    "statement": {"type": "string", "minLength": 1},
                    "sourceType": {
                        "type": "string",
                        "enum": [
                            "user-explicit",
                            "user-implied",
                            "system-inferred",
                            "project-policy",
                        ],
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "confirmationStatus": {
                        "type": "string",
                        "enum": [
                            "confirmed",
                            "proposed",
                            "needs-confirmation",
                            "rejected",
                        ],
                    },
                },
            },
        },
        "unknownStatements": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}

REQUIREMENT_SET_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["requirements", "requirementSummary", "missingDimensions"],
    "properties": {
        "requirementSummary": {"type": "string", "minLength": 1},
        "missingDimensions": {"type": "array", "items": {"type": "string"}},
        "requirements": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "localRequirementKey",
                    "statement",
                    "category",
                    "priority",
                    "sourceType",
                    "confidence",
                    "confirmationStatus",
                    "verificationMethod",
                ],
                "properties": {
                    "localRequirementKey": {"type": "string", "minLength": 1},
                    "statement": {"type": "string", "minLength": 1},
                    "category": {
                        "type": "string",
                        "enum": [
                            "functional",
                            "performance",
                            "interface",
                            "environmental",
                            "resource",
                            "physical",
                            "usability",
                            "safety",
                            "verification",
                            "project-constraint",
                        ],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["must", "should", "could", "unclassified"],
                    },
                    "sourceType": {
                        "type": "string",
                        "enum": [
                            "user-explicit",
                            "user-implied",
                            "system-inferred",
                            "project-policy",
                        ],
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "confirmationStatus": {
                        "type": "string",
                        "enum": [
                            "confirmed",
                            "proposed",
                            "needs-confirmation",
                            "rejected",
                        ],
                    },
                    "verificationMethod": {"type": "string", "minLength": 1},
                    "rationale": {"type": "string"},
                    "acceptanceCriteria": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "targetQuantity": {
                        "type": ["object", "null"],
                        "additionalProperties": False,
                        "required": ["value", "unit"],
                        "properties": {
                            "value": {"type": "number"},
                            "unit": {"type": "string"},
                            "comparator": {
                                "type": "string",
                                "enum": ["eq", "gte", "lte", "approx", "range"],
                            },
                        },
                    },
                },
            },
        },
    },
}

FUNCTIONAL_ARCHITECTURE_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "systemBoundary",
        "nodes",
        "edges",
        "assumptions",
        "unresolvedDecisionStatements",
        "requirementCoverageLocalKeys",
    ],
    "properties": {
        "systemBoundary": {"type": "string", "minLength": 1},
        "nodes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "localNodeKey",
                    "name",
                    "functionalType",
                    "responsibilities",
                    "satisfiesLocalRequirementKeys",
                ],
                "properties": {
                    "localNodeKey": {"type": "string", "minLength": 1},
                    "name": {"type": "string", "minLength": 1},
                    "functionalType": {
                        "type": "string",
                        "enum": [
                            "input",
                            "sensing",
                            "processing",
                            "control",
                            "storage",
                            "communication",
                            "power",
                            "output",
                            "actuation",
                            "analysis",
                            "user-interface",
                            "external-system",
                        ],
                    },
                    "responsibilities": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "satisfiesLocalRequirementKeys": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "edges": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "localEdgeKey",
                    "fromLocalNodeKey",
                    "toLocalNodeKey",
                    "flowType",
                    "description",
                ],
                "properties": {
                    "localEdgeKey": {"type": "string", "minLength": 1},
                    "fromLocalNodeKey": {"type": "string", "minLength": 1},
                    "toLocalNodeKey": {"type": "string", "minLength": 1},
                    "flowType": {
                        "type": "string",
                        "enum": ["data", "control", "power", "user-input", "physical-output"],
                    },
                    "description": {"type": "string", "minLength": 1},
                },
            },
        },
        "assumptions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "statement",
                    "sourceType",
                    "confidence",
                    "confirmationStatus",
                ],
                "properties": {
                    "statement": {"type": "string", "minLength": 1},
                    "sourceType": {
                        "type": "string",
                        "enum": [
                            "user-explicit",
                            "user-implied",
                            "system-inferred",
                            "project-policy",
                        ],
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "confirmationStatus": {
                        "type": "string",
                        "enum": [
                            "confirmed",
                            "proposed",
                            "needs-confirmation",
                            "rejected",
                        ],
                    },
                },
            },
        },
        "unresolvedDecisionStatements": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "requirementCoverageLocalKeys": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
    },
}

REPAIR_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["repairedContent"],
    "properties": {
        "repairedContent": {"type": "object"},
    },
}

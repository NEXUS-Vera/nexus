"""Deterministic pre-checks for the embedded project initialization boundary.

These heuristics are soft, keyword-based signals only — they are cheap and
non-intelligent, in the same spirit as `fixture_router.route_fixture_family`.
They exist to catch obviously out-of-scope requests without a model call and
to give the LLM interpretation stage (`embedded.project-interpretation.v1`)
additional deterministic context. A `True` result here is not a guarantee
that the request is supported: it only means no unsupported-category
heuristic matched. Final boundary interpretation is always completed by the
LLM interpretation stage, which is additional to — not replaced by — this
module.
"""

from __future__ import annotations

import re

_NON_WORD_PATTERN = re.compile(r"[^\w\s-]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize(message: str) -> str:
    lowered = message.casefold()
    cleaned = _NON_WORD_PATTERN.sub(" ", lowered)
    return _WHITESPACE_PATTERN.sub(" ", cleaned).strip()


def _contains_keyword(normalized: str, keyword: str) -> bool:
    """Word-boundary containment check.

    Plain substring checks would let a short token like "ble" or "iot"
    falsely match inside an unrelated word (for example "wearable"). Word
    boundaries keep multi-word phrase keywords working exactly as before.
    """

    return re.search(rf"\b{re.escape(keyword)}\b", normalized) is not None


_DEBUGGING_KEYWORDS: tuple[str, ...] = (
    "debug my",
    "debugging my",
    "fix my code",
    "fix my firmware",
    "why is my",
    "not working",
    "isn't working",
    "isnt working",
    "keeps crashing",
    "stack trace",
    "traceback",
    "compile error",
    "compiler error",
    "won't compile",
    "wont compile",
    "upload failed",
    "flash failed",
    "core dump",
)

_SOFTWARE_ONLY_KEYWORDS: tuple[str, ...] = (
    "web app",
    "website",
    "mobile app",
    "ios app",
    "android app",
    "backend api",
    "rest api",
    "web service",
    "saas product",
    "web application",
    "desktop application",
    "browser extension",
    "chrome extension",
)

_PCB_KEYWORDS: tuple[str, ...] = (
    "pcb layout",
    "pcb design",
    "schematic review",
    "schematic validation",
    "gerber",
    "footprint library",
    "trace routing",
    "layer stackup",
    "kicad",
    "eagle cad",
    "altium",
)

_FIRMWARE_GENERATION_KEYWORDS: tuple[str, ...] = (
    "write the firmware",
    "generate firmware",
    "write firmware code",
    "give me the code",
    "write the code for",
    "implement the driver",
    "write a driver",
    "generate the driver code",
    "write embedded c",
    "write the embedded software",
    "generate the source code",
)

_COMPONENT_SELECTION_ONLY_KEYWORDS: tuple[str, ...] = (
    "which mcu should i use",
    "which microcontroller should i use",
    "which sensor should i use",
    "recommend a sensor",
    "recommend an mcu",
    "recommend a microcontroller",
    "best battery for",
    "which chip should i",
    "part number for",
    "bom for",
    "bill of materials for",
)

_FACTUAL_QA_KEYWORDS: tuple[str, ...] = (
    "what is the difference between",
    "what is a",
    "what does",
    "explain how",
    "how does a",
    "what voltage does",
    "what is the max current",
    "how many amps",
)

_LIFECYCLE_KEYWORDS: tuple[str, ...] = (
    "certify",
    "certification",
    "fcc approval",
    "ce marking",
    "fda approval",
    "medical device approval",
    "manufacturing plan",
    "mass production",
    "deploy to production",
    "purchase order",
    "where can i buy",
)

_UNSUPPORTED_CATEGORIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("debugging an existing implementation", _DEBUGGING_KEYWORDS),
    ("a software-only product with no embedded/physical element", _SOFTWARE_ONLY_KEYWORDS),
    ("PCB layout or schematic-level work", _PCB_KEYWORDS),
    ("firmware or driver code generation", _FIRMWARE_GENERATION_KEYWORDS),
    (
        "a component-selection-only request with no project context",
        _COMPONENT_SELECTION_ONLY_KEYWORDS,
    ),
    ("a non-project factual question", _FACTUAL_QA_KEYWORDS),
    ("a manufacturing, certification, or purchasing request", _LIFECYCLE_KEYWORDS),
)

_EMBEDDED_PRESENCE_KEYWORDS: tuple[str, ...] = (
    "sensor",
    "sensing",
    "microcontroller",
    "mcu",
    "embedded",
    "firmware",
    "circuit",
    "wearable",
    "robot",
    "actuator",
    "device",
    "board",
    "iot",
    "battery",
    "motor",
    "wireless",
    "bluetooth",
    "ble",
    "wifi module",
    "prototype",
    "hardware",
)

_MULTI_PRODUCT_CONNECTOR_PATTERN = re.compile(
    r"\b(and also build|as well as a separate|and a completely separate|"
    r"and another unrelated|in addition build a)\b"
)


def deterministic_boundary_check(message: str) -> tuple[bool, list[str]]:
    """Cheap, deterministic pre-check for the embedded initialization boundary.

    Returns `(within_boundary, reasons)`. `reasons` is always populated,
    including when `within_boundary` is True, so callers and the LLM
    interpretation stage can see why the heuristic reached its verdict. This
    check never asserts domain support with certainty — it only rules out
    prompts that clearly match an unsupported-category keyword heuristic.
    """

    normalized = _normalize(message)
    if not normalized:
        return False, ["Message is empty after normalization."]

    unsupported_hits = _match_categories(normalized, _UNSUPPORTED_CATEGORIES)
    if unsupported_hits:
        reasons = [
            f"Matched heuristic for {label}: {', '.join(sorted(matched))}."
            for label, matched in unsupported_hits
        ]
        return False, reasons

    ambiguity_reason = _multi_product_ambiguity_reason(normalized)
    if ambiguity_reason is not None:
        return False, [ambiguity_reason]

    embedded_hits = sorted(
        kw for kw in _EMBEDDED_PRESENCE_KEYWORDS if _contains_keyword(normalized, kw)
    )
    if embedded_hits:
        return True, [
            "No unsupported-category heuristic matched, and the message "
            "references embedded/physical-computing signals: " + ", ".join(embedded_hits) + "."
        ]

    return True, [
        "No unsupported-category heuristic matched, but no embedded/"
        "physical-computing signal was found either. Deterministic "
        "heuristics are inconclusive here and defer to LLM interpretation."
    ]


def _match_categories(
    normalized: str, categories: tuple[tuple[str, tuple[str, ...]], ...]
) -> list[tuple[str, set[str]]]:
    hits: list[tuple[str, set[str]]] = []
    for label, keywords in categories:
        matched = {kw for kw in keywords if _contains_keyword(normalized, kw)}
        if matched:
            hits.append((label, matched))
    return hits


def _multi_product_ambiguity_reason(normalized: str) -> str | None:
    """Very soft heuristic flagging prompts that bundle multiple unrelated products."""

    if _MULTI_PRODUCT_CONNECTOR_PATTERN.search(normalized):
        return (
            "Message appears to describe more than one unrelated product in "
            "a single request; ask the user to narrow the request to a "
            "single product before proceeding."
        )
    return None

"""Prompt catalog package for embedded project initialization."""

from __future__ import annotations

from .catalog import PROMPT_CATALOG, PromptSpec, get_prompt, list_prompt_ids

__all__ = [
    "PROMPT_CATALOG",
    "PromptSpec",
    "get_prompt",
    "list_prompt_ids",
]

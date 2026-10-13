"""Real model adapters. Backend/05 §3.2.

The tier table made concrete. Every call is a fresh HTTP request with a
capability-scoped payload — Invariant 3 falls out of statelessness rather than
being enforced on top of it.

⚠️ No key configured means these are never constructed. The system degrades to
the deterministic lane and the lexical half of the hybrid seed; it does not
fail, and nothing silently pretends to have called a model.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .agents import Cap, Role, Tier

# Which concrete model serves each tier. One place, so re-tiering is a config
# change and not a code change — which is the whole point of Q2's resolution.
TIER_MODELS = {
    Tier.T1A: os.environ.get("MG_MODEL_OSS", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    Tier.T1B: os.environ.get("MG_MODEL_HAIKU", "claude-haiku-4-5-20251001"),
    Tier.T2: os.environ.get("MG_MODEL_SONNET", "claude-sonnet-5"),
    Tier.T3: os.environ.get("MG_MODEL_OPUS", "claude-opus-5"),
}

ROLE_PROMPT = {
    "planner": """You plan. You do NOT decide what is true.
Return JSON: {"answer": "<the decomposition>", "steps": ["..."]}
Never emit `proposals` — the gate rejects them and the turn is wasted.""",
    "grounder": """You read the supplied documents and tie every claim to a span.
Return JSON:
{"answer": "<prose for the student>",
 "proposals": [{"id","src","dst","relation","confidence","score",
                "citation_state","span","basis":["node ids you used"]}]}
confidence  EXTRACTED (stated verbatim, score 1.0, span REQUIRED)
            INFERRED  (0.95 0.85 0.75 0.65 0.55 only)
            AMBIGUOUS (0.1 0.2 0.3 — genuinely unclear)
citation_state present_relevant | present_weak | missing | wrong_source
               | anchor_unavailable
Be honest about citation_state. Overstating it is the one failure the gate
cannot repair, because a confident well-cited wrong edge looks correct.""",
    "synthesiser": """You reason over STRUCTURE. You have not seen any document,
so you cannot know what a source says — emit INFERRED at most, never EXTRACTED.
Return JSON: {"answer": "...", "proposals": [{...,"basis":[...]}]}
Every proposal names the node ids it used. One that cannot is rejected.""",
    "critic": """You look for contradictions, staleness, and overstated citations.
You may DOWNGRADE a citation_state; you may never raise one.
Return JSON: {"proposals": [{"id","citation_state","confidence","score",
                             "relation","src","dst","basis":[...]}]}
You see `spans`: the exact passages another call already cited. Check them.""",
}


@dataclass
class HTTPAgent:
    """Any OpenAI-compatible endpoint, one model per tier.

    ⭐ Each role is a separate stateless request. Nothing from a previous call
    is threaded in — that is Invariant 3, and it is why a structure-only role
    genuinely has never seen a document rather than merely being told not to
    look at one.
    """

    base_url: str
    api_credential: str = ""
    models: dict = field(default_factory=lambda: dict(TIER_MODELS))
    timeout: int = 120
    max_retries: int = 2

    def _post(self, model: str, system: str, user: str) -> tuple[dict, int, int]:
        body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_credential}",
            },
        )
        last: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    out = json.loads(r.read())
                usage = out.get("usage", {})
                content = out["choices"][0]["message"]["content"]
                return (
                    json.loads(content),
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                )
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = exc
        raise RuntimeError(f"model call failed after retries: {last}")

    def run(self, role: Role, payload: dict, question: str) -> dict:
        system = ROLE_PROMPT.get(role.name, ROLE_PROMPT["synthesiser"])
        user = json.dumps({"question": question, "graph": payload}, sort_keys=True)
        try:
            out, tin, tout = self._post(self.models[role.tier], system, user)
        except RuntimeError as exc:
            # ⚠️ A failed call must not look like a call that found nothing.
            return {
                "answer": "",
                "proposals": [],
                "tokens_in": 0,
                "tokens_out": 0,
                "error": str(exc),
            }
        props = out.get("proposals") or []
        if Cap.PROPOSE not in role.caps:
            props = []  # belt and braces; the gate rejects them anyway
        return {
            "answer": out.get("answer", ""),
            "proposals": props,
            "tokens_in": tin,
            "tokens_out": tout,
        }


@dataclass
class HTTPEmbedder:
    """Tier 1a embeddings — the other half of the hybrid seed."""

    base_url: str
    model: str = os.environ.get("MG_MODEL_EMBED", "BAAI/bge-large-en-v1.5")
    api_credential: str = ""
    timeout: int = 60

    def embed(self, text: str) -> list[float]:
        body = json.dumps({"model": self.model, "input": text}).encode()
        req = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/embeddings",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_credential}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read())["data"][0]["embedding"]


def from_env(endpoint: str | None = None, api_credential: str | None = None):
    """Build the adapters from flags or the environment. Returns (agent,
    embedder, llm) — any of which may be None, and every caller must cope."""
    url = endpoint or os.environ.get("MG_ENDPOINT")
    key = api_credential or os.environ.get("MG_API_KEY", "")
    if not url:
        return None, None, None
    from .extract import HTTPLLM

    return (
        HTTPAgent(url, key),
        HTTPEmbedder(url, api_credential=key),
        HTTPLLM(url, TIER_MODELS[Tier.T1A], key),
    )

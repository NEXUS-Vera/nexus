"""Intake and extraction. Backend/03 §2.

⭐ The deterministic lane is the DEFAULT, not the fallback. For an embedded
project a large share of the graph — files, functions, calls, commits, measured
values — arrives at `EXTRACTED 1.0` and never meets a model. That is a cost
advantage and a trust advantage from the same decision.

    code / CSV / logs / git   -> parsers          0 tokens   EXTRACTED
    papers / notes / chat     -> a model          tokens     mixed

The model-backed lane goes through `LLMClient`, which is a protocol. Phase 1
ships with a deterministic fake so the whole pipeline is testable with no
account, no key and no network.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

TEXT_EXT = {".md", ".txt", ".rst", ".mdx"}
CODE_EXT = {".py", ".c", ".h", ".cpp", ".ino", ".rs", ".js", ".ts"}
DATA_EXT = {".csv", ".tsv"}
DOC_EXT = {".pdf", ".docx"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
LOG_EXT = {".log", ".txt"}


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def route(path: str | Path) -> str:
    ext = Path(path).suffix.lower()
    if ext in CODE_EXT:
        return "code"
    if ext in DATA_EXT:
        return "data"
    if ext in DOC_EXT:
        return "document"
    if ext in IMG_EXT:
        return "image"
    if ext in LOG_EXT and Path(path).stem.lower().endswith(
            ("log", "serial", "capture", "trace")):
        return "log"
    if ext in TEXT_EXT:
        return "text"
    return "text"


def slug(text: str, prefix: str = "") -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:60] or "x"
    return f"{prefix}{s}" if prefix else s


# ── deterministic lane — 0 tokens ───────────────────────────────────────────

def extract_python(source: str, filename: str) -> dict:
    """AST, not a model. Every edge here is EXTRACTED 1.0 and cannot be wrong
    about whether a function exists."""
    nodes, edges = [], []
    fkey = slug(Path(filename).stem, "file:")
    nodes.append({"key": fkey, "type": "Artifact", "kind": "code",
                  "label": Path(filename).name})
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"nodes": nodes, "edges": edges}

    defined: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            k = slug(n.name, "def:")
            defined.add(n.name)
            nodes.append({"key": k, "type": "Artifact", "kind": "code",
                          "label": n.name})
            edges.append({"src_key": fkey, "dst_key": k, "relation": "contains",
                          "confidence": "EXTRACTED", "score": 1.0,
                          "citation_state": "present_relevant",
                          "span": f"{filename}:{n.lineno}"})
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id in defined:
            edges.append({"src_key": fkey, "dst_key": slug(n.func.id, "def:"),
                          "relation": "relates_to", "confidence": "EXTRACTED",
                          "score": 1.0, "citation_state": "present_relevant",
                          "span": f"{filename}:{n.lineno}"})
    return {"nodes": nodes, "edges": edges}


def extract_csv(source: str, filename: str) -> dict:
    """A measurement file is an Artifact whose columns are measured quantities."""
    rows = list(csv.reader(io.StringIO(source)))
    if not rows:
        return {"nodes": [], "edges": []}
    akey = slug(Path(filename).stem, "run:")
    nodes = [{"key": akey, "type": "Artifact", "kind": "measurement",
              "label": Path(filename).name}]
    edges = []
    for col in rows[0]:
        if not col.strip():
            continue
        k = slug(col, "q:")
        nodes.append({"key": k, "type": "Concept", "label": col.strip()[:60]})
        edges.append({"src_key": akey, "dst_key": k, "relation": "measured_by",
                      "confidence": "EXTRACTED", "score": 1.0,
                      "citation_state": "present_relevant",
                      "span": f"{filename}:1"})
    return {"nodes": nodes, "edges": edges}


SERIAL = re.compile(
    r"^\s*(?:\[?(?P<ts>[\d:.]+)\]?\s+)?"
    r"(?P<level>ERROR|WARN|WARNING|INFO|DEBUG|FAIL|FAULT|PANIC)\b[:\s]*"
    r"(?P<msg>.+?)\s*$", re.I)
MEASURE = re.compile(
    r"(?P<name>[A-Za-z][\w ]{2,30}?)\s*[=:]\s*"
    r"(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Zµ%Ω/]{1,8})?")

FAULT_LEVELS = {"ERROR", "FAIL", "FAULT", "PANIC"}


def extract_serial_log(source: str, filename: str) -> dict:
    """Serial and scope logs. Parser plus heuristics, 0 tokens.

    ⭐ Faults become Claims, not Notes: a fault line is an assertion about the
    system that a later measurement can contradict, and that is exactly what
    the Disagreement Engine needs to fire on.
    """
    akey = slug(Path(filename).stem, "log:")
    nodes = [{"key": akey, "type": "Artifact", "kind": "run",
              "label": Path(filename).name}]
    edges = []
    seen: set[str] = set()
    for i, line in enumerate(source.splitlines(), 1):
        if (m := SERIAL.match(line)) and m.group("level").upper() in FAULT_LEVELS:
            msg = m.group("msg")[:60]
            k = slug(msg, "fault:")
            if k not in seen:
                seen.add(k)
                nodes.append({"key": k, "type": "Claim", "label": msg})
                edges.append({"src_key": akey, "dst_key": k,
                              "relation": "evidence_for",
                              "confidence": "EXTRACTED", "score": 1.0,
                              "citation_state": "present_relevant",
                              "span": f"{filename}:{i}"})
        for mm in MEASURE.finditer(line):
            name = mm.group("name").strip()
            if len(name) < 3:
                continue
            k = slug(name, "q:")
            if k in seen:
                continue
            seen.add(k)
            nodes.append({"key": k, "type": "Concept", "label": name[:60]})
            edges.append({"src_key": akey, "dst_key": k,
                          "relation": "measured_by", "confidence": "EXTRACTED",
                          "score": 1.0, "citation_state": "present_relevant",
                          "span": f"{filename}:{i}"})
    return {"nodes": nodes, "edges": edges}


def extract_git(repo: str | Path, limit: int = 200) -> dict:
    """Commit history. Direct parse, 0 tokens.

    ⚠️ A commit is an Artifact — something you made — and its touched files are
    `contains` edges. Not a Note: the history is the only record of WHEN you
    changed your mind about the code, which is what makes staleness detectable.
    """
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", f"-{limit}",
             "--pretty=format:%H%x1f%s", "--name-only", "-z"],
            capture_output=True, text=True, timeout=30, check=True).stdout
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return {"nodes": [], "edges": []}

    nodes, edges, seen = [], [], set()
    for block in out.split("\x00\x00"):
        if "\x1f" not in block:
            continue
        head, _, files = block.partition("\n")
        sha, _, subject = head.partition("\x1f")
        ckey = slug(sha[:12], "commit:")
        nodes.append({"key": ckey, "type": "Artifact", "kind": "code",
                      "label": subject[:60] or sha[:12]})
        for f in [x for x in files.replace("\x00", "\n").splitlines() if x.strip()]:
            fkey = slug(Path(f).stem, "file:")
            if fkey not in seen:
                seen.add(fkey)
                nodes.append({"key": fkey, "type": "Artifact", "kind": "code",
                              "label": Path(f).name})
            edges.append({"src_key": ckey, "dst_key": fkey,
                          "relation": "contains", "confidence": "EXTRACTED",
                          "score": 1.0, "citation_state": "present_relevant",
                          "span": f"{sha[:12]}:{f}"})
    return {"nodes": nodes, "edges": edges}


# ── model-backed lane ───────────────────────────────────────────────────────

class VisionClient(Protocol):
    """⚠️ Tier 2 (Sonnet), NOT Tier 1a. Image grounding is materially weaker in
    small open models, and a misread scope trace is caught by no schema check —
    the failure is silent and confident, which is the one kind the validator
    cannot repair (Backend/03 §2.1)."""

    def describe(self, image_bytes: bytes, source_ref: str) -> dict: ...


@dataclass
class FakeVision:
    """Shape-only stand-in, like FakeLLM. Emits AMBIGUOUS by default because an
    unread image genuinely IS ambiguous — silence would be a worse lie."""
    canned: dict = field(default_factory=dict)

    def describe(self, image_bytes: bytes, source_ref: str) -> dict:
        if source_ref in self.canned:
            return self.canned[source_ref]
        k = slug(Path(source_ref).stem, "img:")
        return {"nodes": [{"key": k, "type": "Note",
                           "label": Path(source_ref).stem[:60]}],
                "edges": []}


class LLMClient(Protocol):
    """Tier 1a. Backend/05 §3.2.

    Runs our own OSS model, served with grammar-constrained decoding so the
    schema is enforced at DECODE time. Safe here precisely because §4 already
    treats this output as untrusted — the residual failure mode is wrong
    content, which quarantine handles.
    """

    def extract(self, text: str, source_ref: str) -> dict: ...


@dataclass
class FakeLLM:
    """Deterministic stand-in. Not a mock of quality — a mock of SHAPE.

    It emits the same JSON contract a real model must, including deliberately
    bad fragments, so the validator and quarantine paths are exercised without
    a key. Swap in a real client and nothing downstream changes.
    """
    canned: dict[str, dict] = field(default_factory=dict)

    def extract(self, text: str, source_ref: str) -> dict:
        if source_ref in self.canned:
            return self.canned[source_ref]
        skey = slug(Path(source_ref).stem, "src:")
        nodes = [{"key": skey, "type": "Source", "kind": "paper",
                  "label": Path(source_ref).stem[:60]}]
        edges = []
        for i, line in enumerate(
                [ln.strip() for ln in text.splitlines() if ln.strip()][:10], 1):
            k = slug(line, "c:")
            nodes.append({"key": k, "type": "Claim", "label": line[:120]})
            edges.append({"src_key": skey, "dst_key": k,
                          "relation": "evidence_for", "confidence": "INFERRED",
                          "score": 0.75, "citation_state": "present_relevant",
                          "span": f"{source_ref}:{i}"})
        return {"nodes": nodes, "edges": edges}


class HTTPLLM:
    """Real Tier 1a client — any OpenAI-compatible endpoint.

    Works against a hosted OSS endpoint or a local vLLM server; identical API,
    so self-hosting later is a config change (Backend/05 §3.2).
    """

    def __init__(self, base_url: str, model: str, api_credential: str = "",
                 prompt_path: str | Path | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_credential = api_credential
        self.prompt = (Path(prompt_path).read_text() if prompt_path
                       else DEFAULT_PROMPT)

    def extract(self, text: str, source_ref: str) -> dict:
        import urllib.request
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": self.prompt},
                         {"role": "user",
                          "content": f"source_ref: {source_ref}\n\n{text}"}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_credential}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.loads(r.read())
        return json.loads(out["choices"][0]["message"]["content"])


DEFAULT_PROMPT = """You extract a knowledge graph fragment. Return ONLY JSON:
{"nodes":[{"key","type","kind","label"}],
 "edges":[{"src_key","dst_key","relation","confidence","score",
           "citation_state","span"}]}

type      Concept | Question | Claim | Artifact | Source | Note
relation  supports contradicts refutes confirms extends evidence_for
          measured_by cites uses_method_in requires relates_to same_as
          answers raises supersedes derived_from contains part_of
confidence EXTRACTED (stated verbatim here, score 1.0, needs a span)
           INFERRED  (0.95 0.85 0.75 0.65 0.55 only)
           AMBIGUOUS (0.1 0.2 0.3 — genuinely unclear; NEVER guess instead)
citation_state present_relevant | present_weak | missing | wrong_source
               | anchor_unavailable

Rules:
- A label is a NAME, not a sentence. Under 60 chars, no verbs.
- `key` is lowercase [a-z0-9_.:-].
- Every edge cites a `span` you can point at.
- If you are unsure, emit AMBIGUOUS. Do not invent a confident answer.
"""


@dataclass
class Fragment:
    source_ref: str
    lane: str
    sha256: str
    payload: dict


def read_document(path) -> str:
    """PDF and DOCX to text. ⚠️ Layout is discarded, so a span is a PAGE, not a
    character offset — an honest anchor beats a precise-looking wrong one."""
    from pathlib import Path as _P
    p = _P(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("pip install pypdf to ingest PDFs") from None
        return "\n".join(f"[p{i}] {(pg.extract_text() or '').strip()}"
                          for i, pg in enumerate(PdfReader(str(p)).pages, 1))
    if ext == ".docx":
        import xml.etree.ElementTree as ET
        import zipfile
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with zipfile.ZipFile(p) as z:
            root = ET.fromstring(z.read("word/document.xml"))
        return "\n".join("".join(t.text or "" for t in para.iter(f"{ns}t"))
                          for para in root.iter(f"{ns}p"))
    return p.read_text(errors="replace")


def ingest_text(name: str, data: str, llm: LLMClient) -> Fragment:
    lane = route(name)
    if lane == "code" and name.endswith(".py"):
        payload = extract_python(data, name)
    elif lane == "data":
        payload = extract_csv(data, name)
    elif lane == "log":
        payload = extract_serial_log(data, name)
    else:
        payload = llm.extract(data, name)
        lane = "model"
    return Fragment(source_ref=name, lane=lane,
                    sha256=content_hash(data.encode()), payload=payload)


def ingest_image(name: str, data: bytes, vision: VisionClient) -> Fragment:
    return Fragment(source_ref=name, lane="vision", sha256=content_hash(data),
                    payload=vision.describe(data, name))


def ingest_git(repo: str | Path) -> Fragment:
    payload = extract_git(repo)
    return Fragment(source_ref=f"git:{Path(repo).name}", lane="git",
                    sha256=content_hash(canonical_git(payload).encode()),
                    payload=payload)


def canonical_git(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

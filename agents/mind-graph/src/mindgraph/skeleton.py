"""The curated concept skeleton. Backend/04.

213 hand-authored embedded-systems concepts and their `requires` edges. There
was nothing to download — the research found that high-quality open datasets
for granular engineering curricula essentially do not exist — so this is ours,
and it is what makes the frontier computable on day one.

⭐ Curated concepts are GLOBAL by construction (Q4): they carry no project_id
and never need promoting. Only LLM-extracted concepts start project-scoped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from pathlib import Path

# Short tokens that are also ordinary English. A concept alias made of one of
# these only counts when the student wrote it in caps — otherwise "CAN bus"
# matches every sentence beginning "Can I…".
_AMBIGUOUS_SHORT = frozenset(
    {
        "can",
        "may",
        "was",
        "are",
        "has",
        "had",
        "did",
        "let",
        "set",
        "get",
        "put",
        "run",
        "use",
        "add",
        "end",
        "top",
        "low",
        "few",
        "all",
        "any",
        "one",
        "two",
        "new",
        "old",
        "big",
        "bad",
        "eis",
        "elm",
        "ram",
        "rom",
        "led",
        "map",
        "arm",
        "bus",
        "bit",
        "pin",
        "pid",
        "adc",
        "dac",
    }
)

ROW = re.compile(r"^- \{(.+)\}\s*$", re.M)
FIELD = re.compile(r'(\w+):\s*(\[[^\]]*\]|"[^"]*"|[^,\]]+)')

# Lives under docs/ (not agents/) because repo policy only allows markdown
# there; this file is both the design doc and the only copy of the seed data.
DEFAULT_PATH = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "architecture"
    / "mind-graph"
    / "11_Concept_Skeleton.md"
)


@dataclass(frozen=True)
class Concept:
    id: str
    label: str
    tier: int
    domain: str
    requires: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    verify: str | None = None


@dataclass
class Skeleton:
    concepts: dict[str, Concept] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.concepts)

    def closure(self, ids: set[str], levels: int = 2) -> set[str]:
        """The matched concepts PLUS their `requires` closure, N levels up.

        ⭐ This is the step that makes the frontier work at t=0: the prerequisite
        edges exist before the student has done anything, so the outer fringe is
        computable immediately.
        """
        out = set(ids) & set(self.concepts)
        frontier_ = set(out)
        for _ in range(levels):
            nxt: set[str] = set()
            for cid in frontier_:
                nxt |= {p for p in self.concepts[cid].requires if p in self.concepts}
            nxt -= out
            if not nxt:
                break
            out |= nxt
            frontier_ = nxt
        return out

    # Words that carry no discriminating power in a concept label.
    _STOP = frozenset(
        {
            "and",
            "or",
            "the",
            "a",
            "an",
            "of",
            "to",
            "in",
            "for",
            "with",
            "basics",
            "basic",
            "control",
            "analysis",
            "design",
            "processing",
            "techniques",
            "technique",
            "methods",
            "method",
            "systems",
            "system",
            # ⚠️ generic verbs and nouns. "build" matched *Makefiles*
            # for "I want to BUILD a robot arm", which is the kind of
            # confident-but-useless seed that makes a cold start feel
            # broken rather than empty.
            "build",
            "make",
            "test",
            "check",
            "code",
            "data",
            "model",
            "safety",
            "selection",
            "sizing",
        }
    )

    @cached_property
    def _token_df(self) -> dict[str, int]:
        """How many concepts each token appears in — a cheap IDF.

        ⭐ This is what separates *lidar* from *control*. A token in one
        concept identifies it; a token in forty identifies nothing, and
        matching on the second kind is how a question about a robot arm gets
        seeded with half the curriculum.
        """
        from .resolve import normalise

        df: dict[str, int] = {}
        for c in self.concepts.values():
            seen = set()
            for n in (c.label, *c.aliases):
                seen |= {t for t in normalise(n).split() if t not in self._STOP}
            for t in seen:
                df[t] = df.get(t, 0) + 1
        return df

    def match(self, text: str, limit: int = 20) -> list[tuple[str, float]]:
        """Label and alias matching against free text. No model call.

        ⚠️ Whole-label matching was measured and found far too strict: a
        student's question is one short sentence and a label is three words, so
        *"can a ROS lidar robot avoid obstacles"* matched **nothing** — not
        `Lidar range processing`, not `ROS nodes and topics`. A cold start that
        matches nothing recommends nothing, which is the worst possible first
        screen.

        So matching is now per-TOKEN, weighted by how distinctive the token is:
        a rare token (`lidar`, `ELISA`, `SLAM`, `kinematics`) is close to
        identifying on its own; a common one (`control`, `basics`) never is.
        """
        from .resolve import normalise, trigrams

        hay_words = set(normalise(text).split())
        hay = f" {normalise(text)} "
        qg = trigrams(text)
        df = self._token_df
        total = max(1, len(self.concepts))
        # ⚠️ Acronyms are the most identifying tokens AND the most dangerous:
        # "CAN bus" matched *"**Can** a ROS lidar robot…"* on the English verb.
        # A short token that is also an ordinary word only counts when the
        # student actually wrote it in caps.
        raw_caps = {w.strip(".,;:?!()") for w in text.split() if w.isupper()}
        hits: list[tuple[str, float]] = []

        def usable(t: str) -> bool:
            if len(t) < 3:  # "I/O" → "i", matches anything
                return False
            if len(t) <= 4 and t in _AMBIGUOUS_SHORT:
                return t.upper() in raw_caps
            return True

        for cid, c in self.concepts.items():
            names = [c.label, *c.aliases]
            if any(f" {normalise(n)} " in hay for n in names if len(normalise(n)) > 2):
                hits.append((cid, 1.0))
                continue

            best = 0.0
            for n in names:
                toks = [t for t in normalise(n).split() if t not in self._STOP]
                if not toks:
                    continue
                present = [t for t in toks if t in hay_words and usable(t)]
                if not present:
                    continue
                cover = len(present) / len(toks)
                # rarest present token drives the score — one distinctive word
                # is worth more than three generic ones
                rarity = max((1.0 - (df.get(t, total) - 1) / total) for t in present)
                # ⚠️ A single distinctive token can carry a match (an acronym
                # IS the concept), but a single generic token cannot.
                if cover >= 0.5 or rarity >= 0.985:
                    best = max(best, min(0.99, 0.55 * cover + 0.45 * rarity))
            if best == 0.0:
                best = max(
                    (len(qg & trigrams(n)) / max(1, len(trigrams(n))) for n in names), default=0.0
                )
                if best < 0.6:
                    best = 0.0
            if best:
                hits.append((cid, round(best, 4)))
        return sorted(hits, key=lambda t: (-t[1], t[0]))[:limit]


def parse(text: str) -> Skeleton:
    sk = Skeleton()
    for raw in ROW.findall(text):
        d: dict = {}
        for k, v in FIELD.findall(raw):
            v = v.strip()
            d[k] = (
                [x.strip() for x in v[1:-1].split(",") if x.strip()]
                if v.startswith("[")
                else v.strip('"')
            )
        if "id" not in d:
            continue
        sk.concepts[d["id"]] = Concept(
            id=d["id"],
            label=d.get("label", d["id"]),
            tier=int(d.get("tier", 0)),
            domain=d.get("domain", "unknown"),
            requires=tuple(d.get("requires", [])),
            aliases=tuple(d.get("aliases", [])),
            verify=d.get("verify") or None,
        )
    return sk


@lru_cache(maxsize=4)
def load(path: str | Path | None = None) -> Skeleton:
    p = Path(path) if path else DEFAULT_PATH
    return parse(p.read_text()) if p.exists() else Skeleton()

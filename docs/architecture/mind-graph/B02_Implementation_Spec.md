# Mind Graph — Implementation Spec (Phase 0)

**Revision 2** — 2026-08-07. Backend/08's schema revisions folded in; section numbers unchanged.
**Companion to Backend/01.** That's the architecture; this is what you build.
**Scope:** the ledger, the projector, the retraction cascade, and the test suite that proves the whole thing is trustworthy. Nothing else.
**Stack:** Python 3.12 · pydantic v2 · sqlite3 (stdlib) · networkx · cryptography.

> **Revision 2.2 (2026-08-10):** `Claim.kind` is **derived** from structure, not stored (`Backend/09` Q5) · `evidence_mass` damps **independent** weight with `sqrt`, discounting `cites`-reachable sources (`Backend/09` Q6).
>
> **Revision 2.1 (2026-08-10):** `Concept.scope` + `Concept.origin` — scope follows provenance (`Backend/09` Q4). Resolution bands: ≥0.95 hard merge · 0.70–0.95 `same_as` edge · <0.70 distinct.
>
> **What changed in revision 2:** `Edge.weight` + `weight_sources` · `Support.CONTESTED` · `Claim.corroboration` / `strength` · `Node.external_ids` · `citation_state` in provenance · `dead_end` and `correction` event types · weight-incrementing projector · magnitude-aware cascade · four new tests.

> **Why so little scope.** Everything downstream — retrieval, frontier, agents, UI — is a pure function of a correct graph. If replay isn't deterministic and retraction doesn't cascade, none of it can be trusted, and every bug above will be misdiagnosed as a bug in the layer you're looking at.

---

# 0. Erasure vs. immutability

GDPR Art. 17 grants a right to erasure; an append-only ledger never deletes. **Resolution: crypto-shredding with per-user key isolation.**

> Encrypt content under a per-user key. On erasure, **destroy the key.** The ciphertext stays in place but is mathematically noise.

Which forces a **split payload**:

```
Event.structural   plaintext   ids, types, relations, confidence, weight, timestamps, agreement
Event.content      encrypted   labels, prose, file bodies, predicted/measured values
```

**Consequence, and it's a good one:** the graph's *shape* survives erasure — nodes exist with null labels, so the projector never corrupts and snapshots never break. `agreement` is deliberately structural, so **aggregate calibration data outlives an erasure request** while the person's content does not.

**Rules:** never put user text in `structural` (tested in CI) · one key per user, stored outside the ledger · erasure = destroy key + append `shredded` · consent and IP remain a separate open item.

---

# 1. Repo layout

```
mindgraph/
├── mindgraph/
│   ├── ids.py            # UUID7, deterministic test ids
│   ├── schema.py         # ⭐ the closed ontology
│   ├── events.py         # ⭐ event models, split payload
│   ├── crypto.py         # per-user keys, encrypt/decrypt, shred
│   ├── ledger.py         # ⭐ append-only store, hash chain
│   ├── projector.py      # ⭐ fold(events) -> GraphState.  THE critical file
│   ├── cascade.py        # ⭐ retraction propagation via justification
│   ├── upcast.py         # schema-version migration (Backend/07 §2)
│   ├── snapshot.py       # serialise/restore
│   ├── graph.py          # networkx wrapper + indices
│   ├── costlog.py        # per-op instrumentation
│   └── errors.py
├── tests/
│   ├── test_determinism.py    ⭐  test_snapshot.py
│   ├── test_cascade.py        ⭐  test_weight.py          ⭐ new
│   ├── test_corroboration.py  ⭐ new
│   ├── test_crypto_shred.py       test_ontology.py
│   └── golden/                    # frozen ledgers per schema version
└── scripts/replay_check.py        # CI gate
```

Twelve modules. If it grows past fifteen before Phase 0 ships, something crept in.

---

# 2. Schema — `schema.py`

```python
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = 1

class NodeType(StrEnum):
    CONCEPT = "Concept"; QUESTION = "Question"; CLAIM = "Claim"
    ARTIFACT = "Artifact"; SOURCE = "Source"; NOTE = "Note"

class Relation(StrEnum):
    CONTAINS = "contains"; PART_OF = "part_of"
    SUPPORTS = "supports"; CONTRADICTS = "contradicts"
    REFUTES = "refutes"; CONFIRMS = "confirms"; EXTENDS = "extends"
    EVIDENCE_FOR = "evidence_for"; MEASURED_BY = "measured_by"
    CITES = "cites"; USES_METHOD_IN = "uses_method_in"
    REQUIRES = "requires"; RELATES_TO = "relates_to"; SAME_AS = "same_as"
    ANSWERS = "answers"; RAISES = "raises"
    SUPERSEDES = "supersedes"; DERIVED_FROM = "derived_from"

SUPPORTING = {Relation.SUPPORTS, Relation.EVIDENCE_FOR,
              Relation.CONFIRMS, Relation.MEASURED_BY}
OPPOSING   = {Relation.CONTRADICTS, Relation.REFUTES}

class Confidence(StrEnum):
    EXTRACTED = "EXTRACTED"; INFERRED = "INFERRED"; AMBIGUOUS = "AMBIGUOUS"

class Rank(StrEnum):
    PREFERRED = "preferred"; NORMAL = "normal"; DEPRECATED = "deprecated"

class Support(StrEnum):
    """Distinct from Rank. A claim can be true but unsupported."""
    SUPPORTED = "supported"; UNSUPPORTED = "unsupported"
    CONTESTED = "contested"          # ⭐ NEW — live support AND live contradiction
    UNKNOWN = "unknown"

class Strength(StrEnum):
    TENTATIVE = "tentative"; ESTABLISHED = "established"; CONTESTED = "contested"

class CitationState(StrEnum):          # ⭐ NEW
    PRESENT_RELEVANT = "present_relevant"; PRESENT_WEAK = "present_weak"
    MISSING = "missing"; WRONG_SOURCE = "wrong_source"
    ANCHOR_UNAVAILABLE = "anchor_unavailable"

MIN_CORROBORATION = 2      # ⭐ one result cannot mint a belief

class Scope(StrEnum):                  # ⭐ NEW — Concept scope
    GLOBAL = "global"; PROJECT = "project"

class Origin(StrEnum):                 # ⭐ NEW — decides scope
    CURATED   = "curated"      # from the skeleton, or carries a CASE external_id
    EXTRACTED = "extracted"    # invented by the LLM from this student's material
    PROMOTED  = "promoted"     # extracted, then seen in a 2nd project at ≥0.95

# Resolution bands — the middle one never hard-merges
MERGE_HARD  = 0.95     # one node
MERGE_SOFT  = 0.70     # `same_as` edge, both nodes survive
PROMOTE_MIN = 0.95     # extracted -> global requires this AND a 2nd project

# The ONLY legal confidence scores. Continuous ranges collapse to bimodal
# in practice (>50% at 0.5, >40% at 0.85+ measured in production).
LEGAL_SCORES = frozenset({1.0, 0.95, 0.85, 0.75, 0.65, 0.55, 0.3, 0.2, 0.1})


class Node(BaseModel):
    id: str
    type: NodeType
    kind: str | None = None          # ⭐ Artifact/Source: INTRINSIC. Claim: DERIVED (Q5)
    label: str | None = None                      # ENCRYPTED at rest
    aliases: list[str] = Field(default_factory=list)   # ENCRYPTED at rest
    body_ref: str | None = None
    project_id: str | None = None
    labels_at: dict[str, str] = Field(default_factory=dict)
    external_ids: dict[str, str] = Field(default_factory=dict)   # ⭐ NEW
    scope: Scope = Scope.PROJECT                  # ⭐ NEW — Concept only; set by provenance
    origin: Origin = Origin.EXTRACTED             # ⭐ NEW — curated | extracted | promoted
    created_seq: int
    valid_from: str | None = None
    valid_to: str | None = None
    rank: Rank = Rank.NORMAL
    support: Support = Support.UNKNOWN
    corroboration: int = 0                        # ⭐ NEW — distinct supporting results
    corroborating_methods: list[str] = Field(default_factory=list)  # ⭐ Q12 — method node ids
    single_method: bool = False                   # ⭐ Q12 — DERIVED, see _recompute_support
    strength: Strength = Strength.TENTATIVE       # ⭐ NEW
    superseded_by: str | None = None
    quarantined: bool = False

    @model_validator(mode="after")
    def _check(self):
        # ⭐ REVISED 2026-08-10 (Backend/09 Q4): Concept scope follows PROVENANCE.
        if self.type is NodeType.CONCEPT:
            if self.origin is Origin.CURATED and self.scope is not Scope.GLOBAL:
                raise ValueError("curated concepts are global by construction")
            if self.scope is Scope.GLOBAL and self.project_id is not None:
                raise ValueError("global scope requires project_id = None")
            if self.scope is Scope.PROJECT and self.project_id is None:
                raise ValueError("project scope requires a project_id")
        elif self.scope is Scope.GLOBAL:
            raise ValueError("only Concept may be globally scoped")
        return self


class Edge(BaseModel):
    id: str
    src: str
    dst: str
    relation: Relation
    confidence: Confidence
    score: float
    weight: int = 1                                        # ⭐ NEW
    weight_sources: list[int] = Field(default_factory=list)  # ⭐ contributing event seqs
    justification: list[str] = Field(default_factory=list)   # ATMS
    provenance: dict = Field(default_factory=dict)  # {actor, method, source_span, citation_state}
    created_seq: int
    valid_from: str | None = None
    valid_to: str | None = None
    rank: Rank = Rank.NORMAL
    superseded_by: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.score not in LEGAL_SCORES:
            raise ValueError(f"score {self.score} not in the discrete rubric")
        if self.confidence is Confidence.EXTRACTED:
            if self.score != 1.0:
                raise ValueError("EXTRACTED edges are always 1.0")
            # ⭐ NEW — certainty requires a directly-supporting passage
            if self.provenance.get("citation_state") not in (
                    None, CitationState.PRESENT_RELEVANT):
                raise ValueError("EXTRACTED requires citation_state=present_relevant")
        if self.confidence is Confidence.AMBIGUOUS and self.score > 0.3:
            raise ValueError("AMBIGUOUS edges score 0.1-0.3")
        if self.weight < 1:
            raise ValueError("weight is a count, minimum 1")
        return self


class Hyperedge(BaseModel):
    id: str
    relation: Literal["jointly_support", "jointly_contradict", "participate_in"]
    members: list[str]
    target: str | None = None
    confidence: Confidence
    score: float
    weight: int = 1                                # ⭐ NEW
    justification: list[str] = Field(default_factory=list)
    created_seq: int
    rank: Rank = Rank.NORMAL

    @model_validator(mode="after")
    def _check(self):
        if len(set(self.members)) < 3:
            raise ValueError("hyperedge needs 3+ distinct members")
        return self
```

**`Support` vs `Rank` vs `Strength` — the subtlety that matters.** Retracting evidence does not make a conclusion false; it makes it *unsupported*. Collapsing these is the most tempting simplification here and it's wrong — it would silently deprecate conclusions that are still true, and a student would rightly stop trusting the system. `Strength` adds the orthogonal axis: *how many independent results back this?*

---

# 3. Events — `events.py`

```python
class EventType(StrEnum):
    OBSERVED = "observed"; PROPOSED = "proposed"
    ACCEPTED = "accepted"; REJECTED = "rejected"
    VALIDATED = "validated"      # ⭐ the outcome path
    RETRACTED = "retracted"; MERGED = "merged"; SPLIT = "split"
    ANNOTATED = "annotated"; ACCESSED = "accessed"
    DEAD_END = "dead_end"        # ⭐ NEW — this approach failed
    CORRECTION = "correction"    # ⭐ NEW — user fixed something; a learning signal
    SHREDDED = "shredded"

class Event(BaseModel):
    seq: int
    ts: str
    actor: str
    type: EventType
    schema_version: int = SCHEMA_VERSION     # for upcasting (Backend/07 §2)
    structural: dict = Field(default_factory=dict)   # PLAINTEXT
    content: bytes | None = None                     # ENCRYPTED
    caused_by: int | None = None
    prev_hash: str
    hash: str
```

**Payload contract, enforced in CI:**

| `structural` (plaintext) | `content` (encrypted) |
|---|---|
| ids, types, relations, **weight**, confidence, `citation_state` | labels, aliases, prose, file text |
| justification ids, timestamps, ranks, project ids | `predicted` / `measured` payloads |
| **`agreement`** verdict, `corroboration` counts | dead-end `reason` text |

`agreement` is structural because it's the flywheel signal and isn't personal data. **The prediction and measurement are encrypted; the fact that they matched is not.**

---

# 4. Ledger — `ledger.py`

```sql
CREATE TABLE IF NOT EXISTS events (
    seq            INTEGER PRIMARY KEY,
    ts             TEXT NOT NULL,
    actor          TEXT NOT NULL,
    type           TEXT NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    structural     TEXT NOT NULL,
    content        BLOB,
    caused_by      INTEGER,
    prev_hash      TEXT NOT NULL,
    hash           TEXT NOT NULL
);
PRAGMA journal_mode = WAL;
```

```python
GENESIS = "0" * 64

def canonical(obj) -> str:
    """Byte-stable JSON. Sorted keys, no whitespace, no NaN."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)

def event_hash(prev, seq, ts, actor, etype, ver, structural, content) -> str:
    h = hashlib.sha256()
    h.update(prev.encode())
    h.update(f"{seq}|{ts}|{actor}|{etype}|{ver}|".encode())
    h.update(canonical(structural).encode())
    h.update(hashlib.sha256(content).hexdigest().encode() if content else b"-")
    return h.hexdigest()

class Ledger:
    def append(self, actor, etype, structural, content=None, caused_by=None) -> int:
        with self.db:                                # single transaction
            prev_seq, prev_hash = self.head()
            seq, ts = prev_seq + 1, self._clock()
            h = event_hash(prev_hash, seq, ts, actor, etype,
                           SCHEMA_VERSION, structural, content)
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (seq, ts, actor, str(etype), SCHEMA_VERSION,
                             canonical(structural), content, caused_by, prev_hash, h))
            return seq

    def verify_chain(self) -> bool:
        prev = GENESIS
        for e in self.read():
            if e.prev_hash != prev: return False
            if e.hash != event_hash(prev, e.seq, e.ts, e.actor, e.type,
                                    e.schema_version, e.structural, e.content):
                return False
            prev = e.hash
        return True
```

**Three properties:** tamper evidence (`verify_chain` detects any edit or reorder); **`seq` is the only ordering** — never sort by `ts`, clocks lie; and the clock is injected so tests are byte-stable.

---

# 5. Projector — `projector.py`

Pure function: `list[Event] -> GraphState`. **No I/O, no clock, no randomness, no network.**

```python
@dataclass
class GraphState:
    nodes: dict[str, Node]         = field(default_factory=dict)
    edges: dict[str, Edge]         = field(default_factory=dict)
    hyper: dict[str, Hyperedge]    = field(default_factory=dict)
    alias: dict[str, str]          = field(default_factory=dict)
    merged_into: dict[str, str]    = field(default_factory=dict)
    justified_by: dict[str, set[str]] = field(default_factory=dict)
    edge_key: dict[tuple, str]     = field(default_factory=dict)  # ⭐ (src,rel,dst)->edge_id
    dead_ends: dict[str, dict]     = field(default_factory=dict)  # ⭐
    last_seq: int = 0

def project(events, state=None) -> GraphState:
    state = state or GraphState()
    for e in events:
        if e.seq <= state.last_seq:
            continue                                  # idempotent replay
        payload = upcast(e.structural, e.schema_version)   # Backend/07 §2
        HANDLERS[e.type](state, payload, e.seq)
        state.last_seq = e.seq
    return state
```

## 5.1 Handlers

```python
def _accepted(state, p, seq):
    for nd in sorted(p.get("nodes", []), key=lambda d: d["id"]):
        node = Node(**nd, created_seq=seq)
        nid = resolve(state, node.id)
        if nid in state.nodes: _merge_attrs(state.nodes[nid], node)
        else:                  state.nodes[nid] = node
        for a in sorted(node.aliases): state.alias[a] = nid

    for ed in sorted(p.get("edges", []), key=lambda d: d["id"]):
        edge = Edge(**ed, created_seq=seq)
        edge.src, edge.dst = resolve(state, edge.src), resolve(state, edge.dst)
        if edge.src == edge.dst: continue              # self-loop after merge

        # ⭐ NEW — re-assertion increments weight rather than duplicating
        key = (edge.src, edge.relation, edge.dst)
        if (existing_id := state.edge_key.get(key)) is not None:
            ex = state.edges[existing_id]
            if seq not in ex.weight_sources:           # distinct sources only
                ex.weight += 1
                ex.weight_sources = sorted(set(ex.weight_sources) | {seq})
            ex.score = max(ex.score, edge.score)       # best evidence wins
            ex.justification = sorted(set(ex.justification) | set(edge.justification))
        else:
            edge.weight_sources = [seq]
            state.edges[edge.id] = edge
            state.edge_key[key] = edge.id

        for dep in edge.justification:
            state.justified_by.setdefault(resolve(state, dep), set()).add(
                state.edge_key[key])

    _recompute_support(state, affected_nodes(p))       # ⭐ support + strength

def _validated(state, p, seq):
    """⭐ The outcome path. agreement is structural; values are encrypted."""
    aid = resolve(state, p["artifact_id"])
    if (art := state.nodes.get(aid)) is None: return
    art.labels_at = {**art.labels_at, "outcome": p["agreement"]}
    if p["agreement"] == "matched":
        m = _method_of(state, aid)                     # ⭐ Q12 — may be None
        for cid in sorted(p.get("validates", [])):
            if (c := state.nodes.get(resolve(state, cid))):
                c.corroboration += 1                   # ⭐ distinct RESULT
                if m and m not in c.corroborating_methods:
                    c.corroborating_methods = sorted(c.corroborating_methods + [m])
                _recompute_support(state, [c.id])

def _method_of(state, artifact_id):                    # ⭐ Q12
    """The Method an Artifact was produced with, if it declared one.
       Artifact(kind=run) --uses_method_in--> Artifact(kind=method)."""
    for e in state.edges.values():
        if (e.src == artifact_id and e.relation is Relation.USES_METHOD_IN
                and e.rank is not Rank.DEPRECATED):
            return e.dst
    return None

def _dead_end(state, p, seq):                          # ⭐ NEW
    state.dead_ends[p["id"]] = {
        "question": p["question"], "nodes": sorted(p.get("nodes", [])),
        "seq": seq, "resurrect_if": sorted(p.get("resurrect_if", [])),
    }

def _correction(state, p, seq):                        # ⭐ NEW
    """User fixed something. Applied, and logged as extraction-quality signal."""
    if (n := state.nodes.get(resolve(state, p["target"]))):
        for k, v in p.get("fields", {}).items():
            setattr(n, k, v)

def _merged(state, p, seq):
    kept, absorbed = resolve(state, p["kept"]), resolve(state, p["absorbed"])
    if kept == absorbed: return
    state.merged_into[absorbed] = kept
    a = state.nodes.pop(absorbed, None)
    if a and kept in state.nodes:
        k = state.nodes[kept]
        k.aliases = sorted(set(k.aliases) | set(a.aliases) |
                           ({a.label} if a.label else set()))
        k.corroboration += a.corroboration              # ⭐ counts survive a merge
        k.corroborating_methods = sorted(set(k.corroborating_methods) |
                                         set(a.corroborating_methods))   # ⭐ Q12
        for s in k.aliases: state.alias[s] = kept
    _rebuild_edge_keys(state)                           # endpoints changed

def _shredded(state, p, seq):
    for n in state.nodes.values():
        n.label, n.aliases, n.body_ref = None, [], None
    state.alias.clear()
```

## 5.2 Support and strength — one place, derived

```python
import math

def independent_weight(state, edge) -> int:
    """⭐ REVISED 2026-08-10 (Backend/09 Q6).

    `weight` counts DISTINCT SOURCES, but distinct is not independent.
    Five papers repeating one original claim is one fact — the citation
    cascade. Where we have the `cites` graph we can measure that directly
    instead of approximating it with a curve: a source reachable from
    another source via `cites` is not independent evidence.
    """
    srcs = {s for s in edge.weight_source_nodes if s in state.nodes}
    if len(srcs) <= 1:
        return max(1, edge.weight)
    derivative = {
        b for b in srcs
        for a in srcs
        if a != b and _reaches(state, a, b, via=Relation.CITES)
    }
    return max(1, len(srcs - derivative))

def evidence_mass(state, edges) -> float:
    """Damping over INDEPENDENT weight.

    sqrt rather than log2: our weights live in the 1-5 range, and there
    log2 says the second source DOUBLES the evidence (w=2 -> 2.0), which
    is too generous when independence is uncertain. sqrt says +41%.
    """
    return sum(math.sqrt(independent_weight(state, e)) for e in edges)

# ⭐ Q5 (2026-08-10): Claim.kind is DERIVED from structure, not stored.
#   observation  supported by evidence OUTSIDE your reasoning (Artifact | Source)
#   conclusion   supported by other Claims
#   hypothesis   no live support at all
# The extractor's guess is kept in provenance["kind_hint"] — recorded, not authoritative.
# (Artifact.kind and Source.kind stay INTRINSIC — a firmware build vs a measurement
#  is not derivable from the graph. Only Claim.kind is.)
EXTERNAL_TYPES = {NodeType.ARTIFACT, NodeType.SOURCE}

def _derive_claim_kind(state, nid, live_supporting) -> str:
    if not live_supporting:
        return "hypothesis"
    srcs = [state.nodes.get(e.src) for e in live_supporting]
    if any(n and n.type in EXTERNAL_TYPES for n in srcs):
        return "observation"
    return "conclusion"

def _recompute_support(state, node_ids):
    """⭐ Support is an EXISTENCE question. Weight grades it; it never decides it.
       Also derives Claim.kind (Q5) and evidence_mass (Q6) in the same pass."""
    for nid in sorted(set(node_ids)):
        if (n := state.nodes.get(nid)) is None: continue
        live = [e for e in state.edges.values()
                if e.dst == nid and e.rank is not Rank.DEPRECATED]
        pos = [e for e in live if e.relation in SUPPORTING]
        neg = [e for e in live if e.relation in OPPOSING]

        # classification uses COUNTS, not weights — one live contradiction
        # always shows, however heavily the other side is cited
        if   pos and neg: n.support, n.strength = Support.CONTESTED, Strength.CONTESTED
        elif pos:
            n.support = Support.SUPPORTED
            # ⭐ strength depends on CORROBORATION (independent results),
            #    never on edge weight (how many sources assert the link)
            n.strength = (Strength.ESTABLISHED if n.corroboration >= MIN_CORROBORATION
                          else Strength.TENTATIVE)
        elif neg: n.support, n.strength = Support.UNSUPPORTED, Strength.TENTATIVE
        else:     n.support, n.strength = Support.UNKNOWN, Strength.TENTATIVE

        # ⭐ Q5 — Claim.kind falls out of the same pass
        if n.type is NodeType.CLAIM:
            n.kind = _derive_claim_kind(state, nid, pos)

        # ⭐ Q12 — corroborated, but every result came from ONE method.
        # Flags, never blocks: same-method replication is a legitimate
        # reproducibility check, it just isn't independent evidence.
        n.single_method = (n.corroboration >= MIN_CORROBORATION
                           and len(n.corroborating_methods) == 1)

        # magnitude is retained for RANKING only (DOI, tension_priority)
        pm, nm = evidence_mass(state, pos), evidence_mass(state, neg)
        n.evidence_mass = round(pm, 4)
        n.contest_ratio = round(nm / (pm + nm), 4) if (pos and neg) else 0.0
```

> ⭐ **`Strength.ESTABLISHED` is what admits a Concept to the knowledge state** (Backend/01 §8). `SUPPORTED` alone is not enough — one lucky measurement must not mark something learned.

### Why weight is deliberately kept out of the classification

Three separable axes, and conflating them was the bug in revision 2's first draft:

| Axis | Field | Question it answers |
|---|---|---|
| **existence** | `support` | is there any live support / contradiction? |
| **independence** | `corroboration` | how many *distinct results* back this? |
| **agreement mass** | `evidence_mass` | how many *sources assert the link*, damped |
| ⭐ **independence *quality*** | `single_method` | did all that corroboration come from **one method**? (Q12) |

### ⭐ Q12 — `single_method`, and why it flags rather than blocks

`corroboration` counts distinct validated results. But **two measurements taken with the same method are not independent corroboration** — replication that varies nothing largely confirms your setup, not your claim. This is the same *distinct ≠ independent* problem Q6 solved for citations, applied to results.

`Artifact(kind=run) --uses_method_in--> Artifact(kind=method)` makes the method a first-class node, so the projector can see it. The check is then trivial (above).

**It flags; it does not gate `ESTABLISHED`.** Requiring two *different* methods would be over-engineering — same-method replication is a legitimate reproducibility check, and an undergraduate frequently has exactly one rig. So `single_method` is surfaced (frontend badge, and an input to the Disagreement Engine's assessment of how solid a claim is) and left to the student to judge. **Surface the weakness rather than legislate against it.**

**Weight measures agreement about a link, not independent evidence for a claim.** Five papers citing one original are one fact repeated — the classic citation cascade — so letting weight drive `established` would manufacture false confidence exactly where a student is least able to detect it. `corroboration` counts validated `Artifact` results, which *are* independent by construction.

And **one live contradiction always produces `CONTESTED`**, no matter how heavily the supporting side is cited. `contest_ratio` grades how lopsided it is for ranking; it never suppresses the flag. A well-cited claim contradicted by the student's own bench is precisely the case the Disagreement Engine exists to surface — silencing it by weight would defeat the feature.

> ### ✅ RESOLVED — Q6 · *Is log₂ damping the right curve?* — **no; `sqrt`, and independence first** *(2026-08-10)*
>
> Two changes. **`sqrt` replaced log₂**, because weights live in the 1–5 range where log₂ says the *second* source doubles the evidence — far too generous at exactly the magnitudes we actually see.
>
> ⭐ **And the bigger error was upstream of the curve.** Distinct sources are not *independent* sources: five papers citing one original are one fact repeated. `independent_weight()` now discounts any source reachable from another via `cites` **before** damping is applied. Choosing a gentler curve would not have fixed a citation cascade; discounting the cascade does.
>
> **Full record: `Backend/09` Q6.**


## 5.3 Determinism rules — each is a bug waiting to happen

1. **Iterate sorted collections only.** Set iteration order isn't stable across runs.
2. **No wall-clock, no `random`, no `uuid4`** inside the projector. Ids arrive in payloads.
3. **No floats derived by arithmetic.** Scores come from the rubric; never compute one. (`weight` is an integer count — safe.)
4. **Unknown event types raise**, never silently skip.
5. **`last_seq` guards replay** so applying an event twice is a no-op.

```python
def state_hash(state) -> str:
    """Canonical fingerprint. Excludes encrypted fields so a shredded
       graph still passes its own determinism check."""
    h = hashlib.sha256()
    for nid in sorted(state.nodes):
        h.update(canonical(state.nodes[nid].model_dump(
            exclude={"label", "aliases", "body_ref"})).encode())
    for eid in sorted(state.edges):
        h.update(canonical(state.edges[eid].model_dump()).encode())
    for hid in sorted(state.hyper):
        h.update(canonical(state.hyper[hid].model_dump()).encode())
    for did in sorted(state.dead_ends):
        h.update(canonical(state.dead_ends[did]).encode())
    return h.hexdigest()
```

---

# 6. Retraction cascade — `cascade.py`

The ATMS mechanism. The part most likely to be built wrong.

```python
def cascade_retract(state, target_id, seq) -> dict:
    """
    Retract `target_id`. Anything justified by it becomes UNSUPPORTED —
    NOT deprecated, NOT deleted. A conclusion whose evidence vanished may
    still be true; it is simply no longer earned.
    """
    deprecated, touched = set(), set()

    for store in (state.nodes, state.edges):
        if (obj := store.get(target_id)) is not None:
            obj.rank, obj.valid_to = Rank.DEPRECATED, str(seq)
            deprecated.add(target_id)

    queue, seen = deque([target_id]), {target_id}
    while queue:
        dead = queue.popleft()
        for dependent in sorted(state.justified_by.get(dead, ())):
            if dependent in seen: continue
            seen.add(dependent)
            if (e := state.edges.get(dependent)) is not None:
                e.rank, e.valid_to = Rank.DEPRECATED, str(seq)
                deprecated.add(dependent); touched.add(e.dst)
                queue.append(dependent)
            elif dependent in state.nodes:
                touched.add(dependent); queue.append(dependent)

    _recompute_support(state, touched)      # ⭐ magnitude-aware, one place
    return {"deprecated": sorted(deprecated), "recomputed": sorted(touched)}
```

**Three semantics decisions worth arguing about:**

1. **Edges deprecate; claims lose support.** An edge asserting *"X supports Y"* where X is gone is simply wrong. Y may still be true.
2. **BFS with a `seen` set** — cyclic justification (A supports B supports A) is a real thing students write, and naive recursion hangs.
3. ⭐ **Support is a magnitude, not a boolean.** Retracting one of five weighted supports leaves a claim `SUPPORTED`; retracting the last leaves it `UNSUPPORTED`. Revision 1 answered this with a boolean and would have unsupported well-evidenced conclusions.

---

# 7. Test suite

The tests are the specification.

## `test_determinism.py`

```python
def test_replay_is_byte_identical(led):
    assert state_hash(project(led.read())) == state_hash(project(led.read()))

def test_replay_independent_of_batching(led):
    whole, piecewise = project(led.read()), GraphState()
    for e in led.read(): piecewise = project([e], piecewise)
    assert state_hash(whole) == state_hash(piecewise)

def test_hash_chain_detects_tampering(led):
    assert led.verify_chain()
    led.db.execute("UPDATE events SET structural='{\"x\":1}' WHERE seq=5")
    assert not led.verify_chain()

def test_projector_is_pure(led, monkeypatch):
    for mod, fn in [("time","time"), ("random","random"), ("socket","socket")]:
        monkeypatch.setattr(f"{mod}.{fn}",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    project(led.read())
```

## `test_weight.py` ⭐ new

```python
def test_reassertion_increments_weight_not_duplicates(led):
    assert_edge_once(led, "M", "supports", "C")
    g = project(led.read())
    assert len([e for e in g.edges.values() if e.relation == "supports"]) == 1
    assert g.edges[edge_id(g, "M", "supports", "C")].weight == 2

def test_same_source_does_not_double_count(led):
    """Weight counts distinct sources, not repetitions."""
    seq = led.append(...)                     # same event replayed
    g = project(list(led.read()) + list(led.read()))
    assert g.edges[...].weight == 1

def test_weight_survives_merge(led):
    g = project(led.read())                   # merge two concepts
    assert g.nodes["kept"].corroboration == 3  # 2 + 1
```

## `test_corroboration.py` ⭐ new

```python
def test_one_result_is_tentative_not_established(g_one_measurement):
    c = g_one_measurement.nodes["C"]
    assert c.support is Support.SUPPORTED
    assert c.strength is Strength.TENTATIVE      # ⭐ NOT in the knowledge state

def test_two_distinct_results_establish(g_two_measurements):
    assert g_two_measurements.nodes["C"].strength is Strength.ESTABLISHED

def test_claim_kind_is_derived_not_stored(g):                 # ⭐ Q5
    """A hypothesis becomes an observation the moment it's measured."""
    assert g.nodes["C"].kind == "hypothesis"        # no support yet
    apply_measurement(g, artifact="M", supports="C")
    assert g.nodes["C"].kind == "observation"       # Artifact-backed
    apply_support(g, claim="C2", supports="C")      # Claim-backed only
    assert g.nodes["C2"].kind == "conclusion"

def test_hypothesis_can_never_be_established(g):             # ⭐ Q5
    assert g.nodes["C"].kind == "hypothesis"
    assert g.nodes["C"].strength is Strength.TENTATIVE

def test_citing_sources_are_discounted(g_cascade):            # ⭐ Q6
    """Three papers, two citing the first: independent weight is 1, not 3."""
    e = g_cascade.edges["e1"]
    assert e.weight == 3
    assert independent_weight(g_cascade, e) == 1

def test_conflicting_evidence_is_contested(g_pos_and_neg):
    n = g_pos_and_neg.nodes["C"]
    assert n.support is Support.CONTESTED
    assert n.strength is Strength.CONTESTED      # feeds the Disagreement Engine

def test_heavy_citation_does_not_suppress_a_contradiction(g_lopsided):
    """20 papers agree; the student's bench disagrees once. Still CONTESTED."""
    n = g_lopsided.nodes["C"]
    assert n.support is Support.CONTESTED        # existence, not magnitude
    assert n.contest_ratio < 0.3                 # graded for ranking only

def test_same_method_twice_is_flagged_not_blocked(g):          # ⭐ Q12
    """Two runs, one method: still ESTABLISHED, but visibly single-method."""
    apply_method(g, method="M1")
    apply_measurement(g, artifact="R1", method="M1", supports="C")
    apply_measurement(g, artifact="R2", method="M1", supports="C")
    c = g.nodes["C"]
    assert c.corroboration == 2
    assert c.strength is Strength.ESTABLISHED      # not blocked
    assert c.single_method is True                 # but flagged

def test_two_methods_clears_the_flag(g):                       # ⭐ Q12
    apply_measurement(g, artifact="R1", method="M1", supports="C")
    apply_measurement(g, artifact="R2", method="M2", supports="C")
    assert g.nodes["C"].single_method is False

def test_methods_survive_a_merge(g):                           # ⭐ Q12
    """Merging two claims unions their method sets — a merge must not
       manufacture single-method-ness, nor hide it."""
    apply_measurement(g, artifact="R1", method="M1", supports="A")
    apply_measurement(g, artifact="R2", method="M2", supports="B")
    apply_merge(g, kept="A", absorbed="B")
    assert g.nodes["A"].corroborating_methods == ["M1", "M2"]
    assert g.nodes["A"].single_method is False

def test_weight_never_substitutes_for_corroboration(g_one_result_many_citations):
    """One measurement, cited by ten sources, is still TENTATIVE."""
    n = g_one_result_many_citations.nodes["C"]
    assert n.corroboration == 1
    assert n.strength is Strength.TENTATIVE      # ⭐ not admitted to knowledge state
```

## `test_cascade.py`

```python
def test_retracting_evidence_unsupports_the_conclusion(g):
    cascade_retract(g, "M", seq=10)
    assert g.nodes["M"].rank is Rank.DEPRECATED
    assert g.nodes["C"].support is Support.UNSUPPORTED
    assert g.nodes["C"].rank is not Rank.DEPRECATED     # ⭐ still not false

def test_claim_with_surviving_support_stays_supported(g_two):
    cascade_retract(g_two, "M1", seq=10)
    assert g_two.nodes["C"].support is Support.SUPPORTED

def test_cascade_terminates_on_cyclic_justification(g_cycle):
    cascade_retract(g_cycle, "A", seq=10)          # must not hang

def test_cascade_is_transitive(g_chain):
    out = cascade_retract(g_chain, "M", seq=10)    # M -> C1 -> C2 -> C3
    assert {"C1","C2","C3"} <= set(out["recomputed"])
```

## `test_crypto_shred.py` · `test_ontology.py`

```python
def test_structure_survives_shredding(led, keystore):
    before = project(led.read()); keystore.destroy(user)
    led.append("system", EventType.SHREDDED, {"user": user})
    after = project(led.read())
    assert set(after.nodes) == set(before.nodes)
    assert all(n.label is None for n in after.nodes.values())
    assert state_hash(after) == state_hash(before)

def test_no_user_text_in_structural(led):        # CI gate
    for e in led.read():
        assert not any(len(tok) > 40 for tok in canonical(e.structural).split('"'))

@pytest.mark.parametrize("bad", [0.5, 0.9, 0.42, 0.0])
def test_scores_outside_the_rubric_are_rejected(bad):
    with pytest.raises(ValidationError): Edge(..., score=bad)

def test_extracted_requires_a_supporting_passage():   # ⭐ new
    with pytest.raises(ValidationError):
        Edge(..., confidence=Confidence.EXTRACTED, score=1.0,
             provenance={"citation_state": CitationState.PRESENT_WEAK})

def test_curated_concepts_must_be_global():          # ⭐ revised
    with pytest.raises(ValidationError):
        Node(id="n", type=NodeType.CONCEPT, origin=Origin.CURATED,
             scope=Scope.PROJECT, project_id="p1", created_seq=1)

def test_extracted_concepts_start_project_scoped():
    n = Node(id="n", type=NodeType.CONCEPT, origin=Origin.EXTRACTED,
             scope=Scope.PROJECT, project_id="p1", created_seq=1)
    assert n.scope is Scope.PROJECT

def test_only_concepts_may_be_global():
    with pytest.raises(ValidationError):
        Node(id="n", type=NodeType.CLAIM, scope=Scope.GLOBAL, created_seq=1)

def test_soft_merge_band_does_not_merge(g_similarity_0_85):
    """0.7-0.95 creates a same_as edge; both nodes survive."""
    assert "a" in g_similarity_0_85.nodes and "b" in g_similarity_0_85.nodes
    assert any(e.relation is Relation.SAME_AS for e in g_similarity_0_85.edges.values())
```

## CI gate — `scripts/replay_check.py`

Nightly, over every user ledger: rebuild from zero, compare `state_hash` to the stored snapshot, `verify_chain()`, and run the golden-ledger fixtures for every schema version (Backend/07 §2.5). **Any divergence without a corresponding upcaster is a P0** — it means the projector changed behaviour and every downstream number is suspect.

---

# 8. Cost instrumentation — `costlog.py`

```python
@contextmanager
def measure(op_type: str, **tags):
    t0, c0 = time.perf_counter(), time.process_time()
    rec = {"op_type": op_type, **tags}
    try: yield rec
    finally:
        rec["wall_ms"] = int((time.perf_counter()-t0)*1000)
        rec["cpu_ms"]  = int((time.process_time()-c0)*1000)
        write_op(rec)
```

Wrap every extraction, projection, and query. Nobody in this field has published real cost data — this table is how we get to be the ones who can.

---

# 9. Build order and acceptance criteria

| Step | Done when |
|---|---|
| 1. `schema.py` + `test_ontology.py` | illegal scores, non-global Concepts, EXTRACTED-with-weak-citation all raise |
| 2. `ledger.py` + hash chain | `verify_chain()` passes on 1k events; tampering fails it |
| 3. `crypto.py` + payload split | `test_no_user_text_in_structural` passes in CI |
| 4. `projector.py` | ⭐ replay twice → identical hash; one-at-a-time == batch; purity passes |
| 5. **`weight` + `_recompute_support`** | ⭐ re-assertion increments; contested survives heavy citation; corroboration gate holds |
| 6. `cascade.py` | all four cascade tests pass, including the cycle |
| 7. `upcast.py` + golden fixtures | v1 ledger projects to its recorded hash |
| 8. `snapshot.py` | snapshot + tail == full replay |
| 9. `costlog.py` | every op writes a row |
| 10. `replay_check.py` in CI | nightly green |

**Phase 0 is done when a synthetic 500-event ledger replays deterministically, a retraction cascades correctly through three levels, a re-assertion increments weight instead of duplicating, a single result stays `tentative`, and a shred leaves the shape intact.** No UI, no LLM, no retrieval. ~1 week, and the only week where a mistake is unrecoverable.

---

# 10. What deliberately isn't here

Extractor, resolver, proposals, retrieval, analyzer, frontier, agents, API, UI. Every one is a pure consumer of a correct `GraphState` — and each is far easier to debug once `state_hash` is stable and the cascade is proven.

---

# 💡 Visionary Vector — the hash chain is a credential

`verify_chain()` exists for a mundane reason: catching corruption. But look at what it produces.

Every project ends up with a **tamper-evident, timestamped, cryptographically-chained record of exactly what a student predicted, what they measured, when, and in what order** — each entry's hash depending on every entry before it. Reordering, backdating, or inserting a result after the fact breaks the chain and is detectable by anyone holding the head hash.

That is, unintentionally, **a verifiable research provenance record.**

Undergraduate research has no credible provenance layer — *"built a biosensor prototype"* on a résumé is unverifiable and everyone knows it. A student who can hand over a head hash and a replayable ledger can prove **the sequence in which they actually figured something out**, including the failed attempts — which is the part that demonstrates competence and precisely the part a polished write-up destroys.

It costs nothing extra: the chain is already there for correctness. Publishing the head hash plus a verifier that replays a ledger is maybe two days of work.

And it composes with calibration: *"here is my prediction accuracy over 40 recorded experiments, and here is cryptographic proof I didn't write the predictions afterwards."* Nobody in education or hiring can currently produce that sentence — which turns the ledger from an implementation detail into **something the student owns and takes with them**, and is also the cleanest answer to the consent and ownership question still open in `Queries/00` §3.1.

---

*Revision 2. Next: the Extraction Contract (Backend/03).*

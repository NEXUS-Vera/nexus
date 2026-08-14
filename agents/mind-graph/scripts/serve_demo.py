#!/usr/bin/env python3
"""Serve the Graph API for the demo, seeded with a realistic project.

    python3 scripts/serve_demo.py           # prints a human token, serves :8787

⚠️ Wide-open CORS and an in-memory token store: correct for a localhost demo,
wrong for anything reachable.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mindgraph.api import Api, serve                    # noqa: E402
from mindgraph.artifact import Session, measure, predict  # noqa: E402
from mindgraph.coldstart import seed_project            # noqa: E402
from mindgraph.extract import FakeLLM, ingest_text      # noqa: E402
from mindgraph.proposals import ingest                  # noqa: E402

ROOT_DIR = ROOT / "demo_users"
Q = "Can skin impedance track hydration to within 10 percent?"


def seed() -> None:
    s = Session.open("local", ROOT_DIR)
    try:
        if s.ledger.head()[0] > 0:
            return
        seed_project(s, Q)
        ingest(s, ingest_text("lab_notes_wk27.md",
                              "skin impedance drops when hydrated\n"
                              "electrode drift dominates below 1 kHz\n"
                              "dry electrodes add contact impedance over gel\n",
                              FakeLLM()))
        ingest(s, ingest_text("sweep_0314.csv",
                              "freq_hz,impedance_kohm,temp_c\n50000,47.2,22.4\n", FakeLLM()))
        for lo, hi, val, label in ((45, 50, 47.2, "Forearm sweep, dry electrodes"),
                                   (45, 50, 46.5, "Forearm sweep, repeat"),
                                   (30, 40, 33.0, "Gel-electrode control"),
                                   (0, 5, 11.4, "Motion-artifact rejection")):
            aid = predict(s, label=label, quantity="impedance", low=lo, high=hi,
                          unit="kOhm")
            measure(s, aid, value=val)
    finally:
        s.close()


class ScriptedAgent:
    """⚠️ A FAKE, and it must stay obviously one.

    It exists so the Ask surface can be exercised and demoed before a real
    endpoint is configured. Its answers are canned; they are not retrieval,
    not reasoning, and not evidence of anything. The prose says so out loud
    rather than reading like a real answer — a convincing fake in a demo is
    how a stakeholder ends up believing a capability that does not exist yet.

    Enable with:  python3 scripts/serve_demo.py --fake-agent
    """

    def run(self, role, payload, question):
        n = len(payload.get("nodes", []))
        out = {"tokens_in": 400 + 20 * n, "tokens_out": 120, "proposals": [],
               "answer": (f"[scripted demo answer — no model was called] "
                          f"{role.name} saw {n} node(s) for: {question}")}
        if role.name == "grounder":
            ids = [x.get("id") for x in payload.get("nodes", [])][:2]
            if len(ids) == 2:
                out["proposals"] = [
                    {"id": "demo-1", "subject": ids[0], "relation": "supports",
                     "object": ids[1], "confidence": "EXTRACTED",
                     "basis": [ids[1]], "span": "lab_notes_wk27.md:1"},
                    # deliberately ungated so the pane has a rejection to show
                    {"id": "demo-2", "subject": ids[0], "relation": "supports",
                     "object": ids[1], "confidence": "EXTRACTED",
                     "basis": [ids[1]]},
                ]
        return out


def main() -> int:
    seed()
    fake = "--fake-agent" in sys.argv
    api = Api(root=str(ROOT_DIR), agent=ScriptedAgent() if fake else None)
    if fake:
        print("\n  ⚠️  --fake-agent: `turn` returns SCRIPTED text. Not a model.",
              flush=True)
    token = api.tokens.mint("local", "human")
    (ROOT_DIR / "token.txt").write_text(token)
    print(f"\n  Graph API on http://127.0.0.1:8787", flush=True)
    print(f"  token: {token}", flush=True)
    print(f"  also written to demo_users/token.txt\n", flush=True)
    print("  In the demo's Workbench, run in the console:")
    print(f"    WB_API.token = '{token}'; \n")
    serve(api, port=8787).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

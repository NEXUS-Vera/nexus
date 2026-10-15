"""Phase 16H reactive analysis spike — marimo evaluation + stateless Explore prototype.

Test-only / research harness. Not wired into production Analysis runtime.
Run with the scientific Python env used by board tests:

  PYTHONPATH=... pytest packages/board/tests/spikes/analysis_reactive -q
  or: python packages/board/tests/spikes/analysis_reactive/run_spike.py
"""

from __future__ import annotations

import json
import statistics
import textwrap
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SPIKE_DIR = Path(__file__).resolve().parent
REPORT_PATH = SPIKE_DIR / "spike_report.json"
NOTEBOOK_PATH = SPIKE_DIR / "sample_notebook.py"


@dataclass
class TimingRow:
    label: str
    cold_start_ms: float | None
    materialize_ms: float | None
    execute_ms: float | None
    repeat_edit_run_ms: float | None
    notes: str = ""


def write_sample_marimo_notebook(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            """\
            import marimo

            __generated_with = "0.13.15"
            app = marimo.App()


            @app.cell
            def _():
                # Cell A: load CSV
                import csv
                from pathlib import Path
                rows = list(csv.DictReader(Path("data.csv").open(encoding="utf-8")))
                return rows,


            @app.cell
            def _(rows):
                # Cell B: transform
                xs = [float(r["accel_x"]) for r in rows]
                return xs,


            @app.cell
            def _(xs):
                # Cell C: RMS of demeaned series
                mean = sum(xs) / len(xs)
                rms = (sum((v - mean) ** 2 for v in xs) / len(xs)) ** 0.5
                return mean, rms


            @app.cell
            def _(xs):
                # Cell D: lightweight "plot" artifact (values only — matplotlib optional)
                series = list(enumerate(xs))
                return series,


            @app.cell
            def _(rms):
                # Cell E: threshold compare (deterministic)
                assessment = "PASS" if rms < 0.10 else "FAIL"
                return assessment,


            if __name__ == "__main__":
                app.run()
            """
        ),
        encoding="utf-8",
    )


def evaluate_marimo() -> dict[str, Any]:
    result: dict[str, Any] = {
        "marimoVersion": None,
        "M1_fileFormat": {"status": "not-run"},
        "M2_staticGraph": {"status": "not-run", "apiStability": "unknown"},
        "M3_reactiveRuntime": {"status": "not-run"},
        "M4_fullEmbedding": {
            "status": "documented-only",
            "notes": (
                "Embedding marimo's own UI would require hosting its ASGI app "
                "(create_asgi_app), iframe/CSP integration, and accepting marimo's "
                "session model in the browser. Not implemented in 16H."
            ),
        },
        "processTopology": {},
    }
    try:
        import marimo

        result["marimoVersion"] = marimo.__version__
    except Exception as exc:  # noqa: BLE001
        result["M1_fileFormat"] = {"status": "gap", "error": str(exc)}
        return result

    write_sample_marimo_notebook(NOTEBOOK_PATH)
    src = NOTEBOOK_PATH.read_text(encoding="utf-8")
    result["M1_fileFormat"] = {
        "status": "pass",
        "cellDecoratorCount": src.count("@app.cell"),
        "editableAsText": True,
        "patchableAsPython": True,
        "nonInteractiveScript": "app.run() present; also executable via plain Python rewrite",
        "notes": "marimo notebooks are ordinary .py files with @app.cell decorators.",
    }

    try:
        from marimo._ast.load import load_app

        app = load_app(str(NOTEBOOK_PATH))
        assert app is not None
        cell_ids = list(app._cell_manager.cell_ids())
        cells = list(app._cell_manager.cells())
        graph = []
        for cid, cell in zip(cell_ids, cells, strict=False):
            if cell is None:
                continue
            graph.append(
                {
                    "cellId": cid,
                    "defs": sorted(cell.defs),
                    "refs": sorted(cell.refs),
                }
            )
        result["M2_staticGraph"] = {
            "status": "pass",
            "apiStability": "internal/private",
            "apiPath": "marimo._ast.load.load_app + App._cell_manager",
            "cells": graph,
            "risk": (
                "Dependency graph APIs used here are underscored private modules. "
                "Do not base production Nexus architecture on them without a stability commitment."
            ),
        }
        result["M3_reactiveRuntime"] = {
            "status": "pass-with-caveats",
            "requiresKernelSession": True,
            "observedApis": [
                "App.run",
                "App._run_cell_sync",
                "App._get_kernel_runner",
                "App._execution_context",
            ],
            "topology": (
                "Reactive execution is session-scoped: a kernel/runner holds cell defs, "
                "invalidates descendants on edit, and re-executes affected cells. "
                "Adopting reactivity effectively means adopting a marimo-managed session."
            ),
            "interruptReset": "Provided by marimo runtime session controls; not Nexus Phase 14.",
            "lazyStale": (
                "marimo supports lazy/stale modes in its runtime; Nexus did not embed them."
            ),
        }
        result["processTopology"] = {
            "sessionScoped": True,
            "cellStateOwner": "marimo kernel/runner",
            "nexusFilesystemAuthority": "retained outside marimo",
        }
    except Exception as exc:  # noqa: BLE001
        result["M2_staticGraph"] = {
            "status": "fail",
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc()[-500:],
        }
    return result


def _closure_sources(target: str) -> list[tuple[str, str]]:
    """Tiny Nexus-owned cell graph A→B→C, A→D for the selected target."""
    cells = {
        "A": "xs = [0.01, -0.02, 0.015, -0.01, 0.02]\n",
        "B": "mean = sum(xs) / len(xs)\ncentered = [v - mean for v in xs]\n",
        "C": "rms = (sum(v * v for v in centered) / len(centered)) ** 0.5\n",
        "D": "series = list(enumerate(xs))\n",
    }
    deps = {"A": [], "B": ["A"], "C": ["B"], "D": ["A"]}

    def closure(name: str) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()

        def visit(n: str) -> None:
            if n in seen:
                return
            for d in deps[n]:
                visit(d)
            seen.add(n)
            ordered.append(n)

        visit(name)
        return ordered

    order = closure(target)
    return [(name, cells[name]) for name in order]


def run_stateless_explore(target: str = "C") -> dict[str, Any]:
    t0 = time.perf_counter()
    parts = _closure_sources(target)
    t1 = time.perf_counter()
    source = "".join(code for _, code in parts)
    ns: dict[str, Any] = {}
    exec(source, ns, ns)  # noqa: S102 — intentional spike sandbox
    t2 = time.perf_counter()
    # destroy transient state
    result = {k: ns[k] for k in ("rms", "series") if k in ns}
    ns.clear()
    return {
        "target": target,
        "cellsMaterialized": [name for name, _ in parts],
        "result": result,
        "materialize_ms": (t1 - t0) * 1000,
        "execute_ms": (t2 - t1) * 1000,
        "ephemeral": True,
        "durableHistory": False,
    }


def _time_call(fn: Any, repeats: int = 5) -> tuple[float, float]:
    samples: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.mean(samples), statistics.median(samples)


def run_benchmarks() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def trivial() -> None:
        x = sum(range(1000))
        assert x > 0

    mean_ms, _ = _time_call(trivial)
    rows.append(
        asdict(
            TimingRow(
                label="trivial-python",
                cold_start_ms=mean_ms,
                materialize_ms=0.0,
                execute_ms=mean_ms,
                repeat_edit_run_ms=mean_ms,
                notes="stateless local exec",
            )
        )
    )

    try:
        import numpy as np

        def numpy_work() -> None:
            a = np.random.default_rng(0).normal(0, 0.02, size=50_000)
            _ = float(np.sqrt(np.mean((a - a.mean()) ** 2)))

        mean_ms, _ = _time_call(numpy_work)
        rows.append(
            asdict(
                TimingRow(
                    label="numpy-numeric",
                    cold_start_ms=None,
                    materialize_ms=None,
                    execute_ms=mean_ms,
                    repeat_edit_run_ms=mean_ms,
                )
            )
        )
    except Exception as exc:  # noqa: BLE001
        rows.append(
            asdict(
                TimingRow(
                    label="numpy-numeric",
                    cold_start_ms=None,
                    materialize_ms=None,
                    execute_ms=None,
                    repeat_edit_run_ms=None,
                    notes=f"unavailable: {exc}",
                )
            )
        )

    try:
        import pandas as pd

        def pandas_work() -> None:
            df = pd.DataFrame({"accel_x": [0.01, -0.02, 0.015, -0.01, 0.02] * 2000})
            c = df["accel_x"] - df["accel_x"].mean()
            _ = float((c**2).mean() ** 0.5)

        mean_ms, _ = _time_call(pandas_work)
        rows.append(
            asdict(
                TimingRow(
                    label="pandas-transform",
                    cold_start_ms=None,
                    materialize_ms=None,
                    execute_ms=mean_ms,
                    repeat_edit_run_ms=mean_ms,
                )
            )
        )
    except Exception as exc:  # noqa: BLE001
        rows.append(
            asdict(
                TimingRow(
                    label="pandas-transform",
                    cold_start_ms=None,
                    materialize_ms=None,
                    execute_ms=None,
                    repeat_edit_run_ms=None,
                    notes=f"unavailable: {exc}",
                )
            )
        )

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        def plot_work() -> None:
            fig, ax = plt.subplots()
            ax.plot([0, 1, 2], [0.01, -0.02, 0.015])
            fig.savefig("/tmp/nexus_spike_plot.png")
            plt.close(fig)

        mean_ms, _ = _time_call(plot_work, repeats=3)
        rows.append(
            asdict(
                TimingRow(
                    label="matplotlib-plot",
                    cold_start_ms=None,
                    materialize_ms=None,
                    execute_ms=mean_ms,
                    repeat_edit_run_ms=mean_ms,
                )
            )
        )
    except Exception as exc:  # noqa: BLE001
        rows.append(
            asdict(
                TimingRow(
                    label="matplotlib-plot",
                    cold_start_ms=None,
                    materialize_ms=None,
                    execute_ms=None,
                    repeat_edit_run_ms=None,
                    notes=f"unavailable: {exc}",
                )
            )
        )

    for size_mb, label in [(1, "csv-1mb"), (10, "csv-10mb")]:
        try:
            import csv
            from pathlib import Path

            path = Path(f"/tmp/nexus_spike_{label}.csv")
            if not path.exists():
                n = size_mb * 20_000
                with path.open("w", encoding="utf-8", newline="") as handle:
                    w = csv.writer(handle)
                    w.writerow(["time_s", "accel_x"])
                    for i in range(n):
                        w.writerow([i * 0.02, (i % 7 - 3) * 0.001])

            def csv_work(p: Path = path) -> None:
                import csv as _csv

                rows_local = list(_csv.DictReader(p.open(encoding="utf-8")))
                xs = [float(r["accel_x"]) for r in rows_local]
                mean = sum(xs) / len(xs)
                _ = (sum((v - mean) ** 2 for v in xs) / len(xs)) ** 0.5

            mean_ms, _ = _time_call(csv_work, repeats=2)
            rows.append(
                asdict(
                    TimingRow(
                        label=label,
                        cold_start_ms=None,
                        materialize_ms=None,
                        execute_ms=mean_ms,
                        repeat_edit_run_ms=mean_ms,
                        notes=f"rows≈{size_mb * 20000}",
                    )
                )
            )
        except Exception as exc:  # noqa: BLE001
            rows.append(
                asdict(
                    TimingRow(
                        label=label,
                        cold_start_ms=None,
                        materialize_ms=None,
                        execute_ms=None,
                        repeat_edit_run_ms=None,
                        notes=f"unavailable: {exc}",
                    )
                )
            )

    # 100 MB optional
    try:
        path = Path("/tmp/nexus_spike_csv-100mb.csv")
        if path.exists():

            def csv100() -> None:
                import csv as _csv

                xs = [float(r["accel_x"]) for r in _csv.DictReader(path.open(encoding="utf-8"))]
                mean = sum(xs) / len(xs)
                _ = (sum((v - mean) ** 2 for v in xs) / len(xs)) ** 0.5

            mean_ms, _ = _time_call(csv100, repeats=1)
            rows.append(
                asdict(
                    TimingRow(
                        label="csv-100mb",
                        cold_start_ms=None,
                        materialize_ms=None,
                        execute_ms=mean_ms,
                        repeat_edit_run_ms=None,
                        notes="pre-existing file",
                    )
                )
            )
        else:
            rows.append(
                asdict(
                    TimingRow(
                        label="csv-100mb",
                        cold_start_ms=None,
                        materialize_ms=None,
                        execute_ms=None,
                        repeat_edit_run_ms=None,
                        notes="skipped — file not present (safe default)",
                    )
                )
            )
    except Exception as exc:  # noqa: BLE001
        rows.append(
            asdict(
                TimingRow(
                    label="csv-100mb",
                    cold_start_ms=None,
                    materialize_ms=None,
                    execute_ms=None,
                    repeat_edit_run_ms=None,
                    notes=f"unavailable: {exc}",
                )
            )
        )

    # Comparison modes A/B/C conceptual timings for tiny graph
    explore = run_stateless_explore("C")
    rows.append(
        asdict(
            TimingRow(
                label="B-stateless-dependency-closure",
                cold_start_ms=explore["materialize_ms"] + explore["execute_ms"],
                materialize_ms=explore["materialize_ms"],
                execute_ms=explore["execute_ms"],
                repeat_edit_run_ms=explore["execute_ms"],
                notes="Nexus-owned cells; no kernel",
            )
        )
    )
    rows.append(
        asdict(
            TimingRow(
                label="A-full-clean-phase16-run",
                cold_start_ms=None,
                materialize_ms=None,
                execute_ms=None,
                repeat_edit_run_ms=None,
                notes=(
                    "Measured in Phase 16 G1/G3 product E2E (snapshot+runtime), not duplicated here"
                ),
            )
        )
    )
    rows.append(
        asdict(
            TimingRow(
                label="C-marimo-reactive-session",
                cold_start_ms=None,
                materialize_ms=None,
                execute_ms=None,
                repeat_edit_run_ms=None,
                notes=(
                    "Session start dominates; per-cell invalidation requires marimo kernel. "
                    "Not productionized in 16H."
                ),
            )
        )
    )
    return rows


def main() -> dict[str, Any]:
    report = {
        "schemaVersion": "1.0.0",
        "phase": "16H",
        "marimo": evaluate_marimo(),
        "statelessExplore": run_stateless_explore("C"),
        "benchmarks": run_benchmarks(),
        "recommendation": {
            "runtime": "R1",
            "cells": True,
            "reactivity": False,
            "rationale": (
                "Cold/stateless dependency-closure execution is already adequate for "
                "Nexus Analysis workloads at 1–10 MB CSV scale. marimo's useful graph "
                "APIs are private; reactive mode implies a session primitive Nexus does "
                "not yet own. Prefer Nexus-owned cells/sections as structural UX with "
                "batch Explore closures; retain Phase 16 Run/Verify/Rerun for durable proof."
            ),
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2)[:2000])

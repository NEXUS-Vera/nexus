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

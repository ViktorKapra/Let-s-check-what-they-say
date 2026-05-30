"""Phase 3 benchmark harness.

Times the three analysis variants (serial, multiprocessing, vectorized) across
the three corpus sizes, computes speedup and efficiency, and emits the results
table + the speedup-vs-processes graph that are the Phase 3 deliverables.

Methodology:
  - The CSV is loaded ONCE per corpus, outside every timer (we measure analysis,
    not disk I/O).
  - Each measurement is repeated REPEATS times and the MINIMUM is reported -- the
    min is the cleanest estimate of true compute time (least polluted by OS
    scheduling / GC pauses).
  - The multiprocessing pool gets one untimed warm-up run before measurement.
  - mp is swept over {1, 2, 4, all-cores}; that sweep is the speedup graph.
  - Speedup   = T_serial / T_variant
    Efficiency = Speedup / processes

Note: each run_parallel() call creates its own Pool, so the mp timings include
pool-spawn + per-worker module-import overhead. That is the realistic cost of
this implementation and is reported as-is (a production system would reuse a
pool across calls).

Run from the project root:
    python src/benchmark.py
"""
import argparse
import csv
import os
import time
from pathlib import Path

RESULTS_DIR = Path("data/results")
CORPORA = {
    "small":  Path("data/processed/speeches_small.csv"),
    "medium": Path("data/processed/speeches_medium.csv"),
    "big":    Path("data/processed/speeches_big.csv"),
}
REPEATS = 3

# Phase 1 scraping measurements (one ~270-statement session, 2024-12-18).
# See docs/phase4_notes.md section 5. Hardcoded because they are fixed
# historical results, not produced by this analysis benchmark.
SCRAPING_TIMES = {
    "serial\n(no reuse)": 28.6,
    "serial\n(session reuse)": 19.18,
    "async\n(concurrency 5)": 3.97,
}


def time_it(func, *args, repeats=REPEATS) -> float:
    """Run func(*args) `repeats` times; return the minimum elapsed seconds."""
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        func(*args)
        best = min(best, time.perf_counter() - t0)
    return best


def benchmark_corpus(name: str, csv_path: Path) -> list[dict]:
    # Lazy imports: keep this module's top level light, so the mp workers that
    # re-import it on spawn don't pull sklearn/pandas/matplotlib needlessly.
    from common import load_speeches
    from analysis_serial import run_serial
    from analysis_mp import run_parallel
    from analysis_vectorized import run_tfidf_vectorized

    df = load_speeches(csv_path)                  # load once, outside all timers
    max_cores = os.process_cpu_count() or 1
    # sample 1..16 to expose the knee around the physical-core count (hyperthreads
    # past ~8 typically add little for CPU-bound work); always include max_cores.
    candidates = (1, 2, 4, 8, 12, 16)
    process_counts = sorted({p for p in candidates if p <= max_cores} | {max_cores})

    rows: list[dict] = []

    # Serial baseline -- the denominator for every speedup.
    t_serial = time_it(run_serial, df)
    rows.append({"corpus": name, "variant": "serial", "processes": 1,
                 "time": t_serial, "speedup": 1.0, "efficiency": 1.0})

    # Vectorized (single configuration, no process axis).
    t_vec = time_it(run_tfidf_vectorized, df)
    rows.append({"corpus": name, "variant": "vectorized", "processes": "-",
                 "time": t_vec, "speedup": t_serial / t_vec, "efficiency": "-"})

    # Multiprocessing sweep.
    run_parallel(df, 1)                           # untimed warm-up
    for p in process_counts:
        t = time_it(run_parallel, df, p)
        speedup = t_serial / t
        rows.append({"corpus": name, "variant": "mp", "processes": p,
                     "time": t, "speedup": speedup, "efficiency": speedup / p})

    return rows


def print_table(rows: list[dict]) -> None:
    print(f"\n{'corpus':8} {'variant':11} {'procs':>5} {'time(s)':>10} {'speedup':>8} {'eff':>6}")
    print("-" * 52)
    for r in rows:
        eff = r["efficiency"]
        eff_s = f"{eff:.2f}" if isinstance(eff, float) else str(eff)
        print(f"{r['corpus']:8} {r['variant']:11} {str(r['processes']):>5} "
              f"{r['time']:>10.3f} {r['speedup']:>8.2f} {eff_s:>6}")


def save_results(rows: list[dict], out_csv: Path) -> None:
    fields = ["corpus", "variant", "processes", "time", "speedup", "efficiency"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def plot_speedup(rows: list[dict], out_png: Path) -> None:
    """One panel per corpus: speedup of each method vs the serial baseline.
    mp uses its best process count (the peak of the sweep). The dashed line at
    1.0 is break-even -- a bar below it means that method is slower than serial."""
    import matplotlib
    matplotlib.use("Agg")                         # no GUI needed
    import matplotlib.pyplot as plt

    corpora = list(CORPORA)
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]

    def best_mp(corpus):
        cand = [r for r in rows if r["corpus"] == corpus and r["variant"] == "mp"]
        return max(cand, key=lambda r: r["speedup"])

    def vectorized(corpus):
        return next(r for r in rows if r["corpus"] == corpus and r["variant"] == "vectorized")

    fig, axes = plt.subplots(1, len(corpora), figsize=(12, 4), sharey=True)
    for ax, corpus in zip(axes, corpora):
        mp = best_mp(corpus)
        labels = ["serial", f"mp\n(best, {mp['processes']}p)", "vectorized"]
        speedups = [1.0, mp["speedup"], vectorized(corpus)["speedup"]]
        bars = ax.bar(labels, speedups, color=colors)
        for bar, s in zip(bars, speedups):
            ax.text(bar.get_x() + bar.get_width() / 2, s, f"{s:.2f}×",
                    ha="center", va="bottom", fontsize=9)
        ax.axhline(1.0, color="k", ls="--", alpha=0.4)   # break-even with serial
        ax.set_title(f"{corpus} corpus")
        ax.set_ylabel("speedup (× serial)")
        ax.margins(y=0.18)                        # headroom for the labels
    fig.suptitle("Speedup by method (vs serial baseline)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    print(f"Saved plot to {out_png}")


def plot_runtime(rows: list[dict], out_png: Path) -> None:
    """One panel per corpus (linear y, value-labelled bars) so absolute times
    are readable. A single shared chart would need a log axis -- where bar
    heights no longer map to values -- because times span ~0.03 s .. 7 s."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    corpora = list(CORPORA)
    methods = ["serial", "mp", "vectorized"]
    labels = ["serial", "mp\n(best)", "vectorized"]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]

    def pick(corpus, variant):
        return min(r["time"] for r in rows if r["corpus"] == corpus and r["variant"] == variant)

    fig, axes = plt.subplots(1, len(corpora), figsize=(12, 4))
    for ax, corpus in zip(axes, corpora):
        times = [pick(corpus, m) for m in methods]
        bars = ax.bar(labels, times, color=colors)
        for bar, t in zip(bars, times):
            ax.text(bar.get_x() + bar.get_width() / 2, t, f"{t:.2f}s",
                    ha="center", va="bottom", fontsize=9)
        ax.set_title(f"{corpus} corpus")
        ax.set_ylabel("time (s)")
        ax.margins(y=0.18)                        # headroom for the labels
    fig.suptitle("Analysis runtime by method (separate linear scale per corpus)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    print(f"Saved plot to {out_png}")


def plot_scraping(out_png: Path) -> None:
    """Phase 1 scraping: serial vs async on one session (fixed historical data)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = list(SCRAPING_TIMES)
    times = list(SCRAPING_TIMES.values())
    plt.figure(figsize=(7, 5))
    bars = plt.bar(labels, times, color=["#cc4444", "#cc8844", "#44aa44"])
    for bar, t in zip(bars, times):
        plt.text(bar.get_x() + bar.get_width() / 2, t, f"{t:.1f}s", ha="center", va="bottom")
    plt.ylabel("time (s) — one ~270-statement session")
    plt.title("Phase 1 scraping: serial vs async")
    plt.grid(True, axis="y", alpha=0.3)
    plt.savefig(out_png, dpi=120, bbox_inches="tight")
    print(f"Saved plot to {out_png}")


def load_results(in_csv: Path) -> list[dict]:
    """Read a saved benchmark.csv back into rows (for --plot-only)."""
    rows = []
    with open(in_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["time"] = float(r["time"])
            r["speedup"] = float(r["speedup"])
            try:
                r["processes"] = int(r["processes"])
            except ValueError:
                pass                              # vectorized row: processes == "-"
            rows.append(r)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 analysis benchmark + figures.")
    parser.add_argument("--plot-only", action="store_true",
                        help="skip timing; redraw figures from data/results/benchmark.csv")
    args = parser.parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.plot_only:
        all_rows = load_results(RESULTS_DIR / "benchmark.csv")
    else:
        all_rows = []
        for corpus_name, corpus_path in CORPORA.items():
            print(f"\n=== Benchmarking {corpus_name} ({corpus_path}) ===")
            all_rows.extend(benchmark_corpus(corpus_name, corpus_path))
        print_table(all_rows)
        save_results(all_rows, RESULTS_DIR / "benchmark.csv")

    plot_speedup(all_rows, RESULTS_DIR / "speedup.png")
    plot_runtime(all_rows, RESULTS_DIR / "runtime.png")
    plot_scraping(RESULTS_DIR / "scraping.png")
    print(f"\nFigures saved to {RESULTS_DIR}")

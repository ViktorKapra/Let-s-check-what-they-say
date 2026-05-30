"""Phase 1 scraping benchmark: serial vs async, across corpus sizes.

Times the two scrapers end-to-end on the same session dates and emits a table,
a CSV, and two figures (runtime + speedup) mirroring the analysis benchmark.

Methodology:
  - Sessions are scraped sequentially in BOTH methods; the async scraper is
    internally concurrent (5 requests) within each session. So the comparison
    is "serial HTTP with keep-alive" vs "async HTTP with concurrency 5" -- the
    serial-without-session-reuse variant is intentionally not measured here.
  - Each measurement scrapes into a throwaway temp dir that is wiped first, so
    every run does the full work (no skipped/cached files) and the real
    data/raw/ dataset is never touched.
  - One run per (corpus, method): scraping time is dominated by the number of
    HTTP requests, not by jitter, so repeats add server load without insight.

Run from the project root:
    python src/benchmark_scraping.py                 # small + medium
    python src/benchmark_scraping.py --corpus big     # just big (slow!)
    python src/benchmark_scraping.py --corpus all
    python src/benchmark_scraping.py --plot-only      # redraw from CSV
"""
import argparse
import asyncio
import csv
import json
import shutil
import sys
import time
from pathlib import Path

# The scrapers live under src/collecting_data/ and import each other by bare
# name, so put that directory on the path before importing them.
sys.path.insert(0, str(Path(__file__).parent / "collecting_data"))
from scraper_serial import scrape_session_serial, SIZES, SESSION_DATES_PATHS
from scraper_async import scrape_session_async

RESULTS_DIR = Path("data/results")
BENCH_DIR = Path("data/raw/_scrape_bench")        # throwaway scrape target
DEFAULT_CORPORA = ["small", "medium"]


def _fresh_dir(path: Path) -> Path:
    """Delete `path` if it exists, then recreate it empty."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def time_serial(dates: list[str], out_dir: Path) -> float:
    t0 = time.perf_counter()
    for date in dates:
        try:
            scrape_session_serial(date, out_dir)
        except Exception as e:
            print(f"  serial {date}: FAILED ({e})")
    return time.perf_counter() - t0


def time_async(dates: list[str], out_dir: Path) -> float:
    async def run_all():
        for date in dates:                        # sessions sequential; each one
            try:                                  # is internally concurrent (5)
                await scrape_session_async(date, out_dir)
            except Exception as e:
                print(f"  async {date}: FAILED ({e})")
    t0 = time.perf_counter()
    asyncio.run(run_all())
    return time.perf_counter() - t0


def benchmark_corpus(name: str, dates: list[str]) -> list[dict]:
    print(f"\n=== Scraping benchmark: {name} ({len(dates)} sessions) ===")

    print("  serial (session reuse) ...")
    t_serial = time_serial(dates, _fresh_dir(BENCH_DIR))

    print("  async (concurrency 5) ...")
    t_async = time_async(dates, _fresh_dir(BENCH_DIR))

    shutil.rmtree(BENCH_DIR, ignore_errors=True)  # don't leave junk behind
    return [
        {"corpus": name, "sessions": len(dates), "method": "serial",
         "time": t_serial, "speedup": 1.0},
        {"corpus": name, "sessions": len(dates), "method": "async",
         "time": t_async, "speedup": t_serial / t_async},
    ]


def print_table(rows: list[dict]) -> None:
    print(f"\n{'corpus':8} {'sessions':>8} {'method':8} {'time(s)':>10} {'speedup':>8}")
    print("-" * 46)
    for r in rows:
        print(f"{r['corpus']:8} {r['sessions']:>8} {r['method']:8} "
              f"{r['time']:>10.2f} {r['speedup']:>8.2f}")


def save_results(rows: list[dict], out_csv: Path) -> None:
    """Merge with any existing CSV: rows for the corpora measured this run
    replace their old entries; corpora not measured this run are preserved. So
    running `--corpus big` later adds to the file instead of wiping small/medium."""
    existing = load_results(out_csv) if out_csv.exists() else []
    new_corpora = {r["corpus"] for r in rows}
    merged = [r for r in existing if r["corpus"] not in new_corpora] + rows
    merged.sort(key=lambda r: (r["sessions"], r["method"]))
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["corpus", "sessions", "method", "time", "speedup"])
        writer.writeheader()
        writer.writerows(merged)


def load_results(in_csv: Path) -> list[dict]:
    rows = []
    with open(in_csv, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["sessions"] = int(r["sessions"])
            r["time"] = float(r["time"])
            r["speedup"] = float(r["speedup"])
            rows.append(r)
    return rows


def plot_runtime(rows: list[dict], out_png: Path) -> None:
    """Grouped bars: serial vs async time, one group per corpus."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    corpora = sorted({r["corpus"] for r in rows}, key=lambda c: next(x["sessions"] for x in rows if x["corpus"] == c))

    def t(corpus, method):
        return next(r["time"] for r in rows if r["corpus"] == corpus and r["method"] == method)

    x = range(len(corpora))
    width = 0.38
    serial_t = [t(c, "serial") for c in corpora]
    async_t = [t(c, "async") for c in corpora]

    fig, ax = plt.subplots(figsize=(8, 5))
    b1 = ax.bar([i - width / 2 for i in x], serial_t, width, label="serial (session reuse)", color="#cc8844")
    b2 = ax.bar([i + width / 2 for i in x], async_t, width, label="async (concurrency 5)", color="#44aa44")
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f"{bar.get_height():.1f}s", ha="center", va="bottom", fontsize=9)
    labels = [f"{c}\n({next(r['sessions'] for r in rows if r['corpus'] == c)} sessions)" for c in corpora]
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("scrape time (s)")
    ax.set_title("Scraping runtime: serial vs async")
    ax.legend()
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    print(f"Saved plot to {out_png}")


def plot_speedup(rows: list[dict], out_png: Path) -> None:
    """One bar per corpus: async speedup over serial. Break-even line at 1.0."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    corpora = sorted({r["corpus"] for r in rows}, key=lambda c: next(x["sessions"] for x in rows if x["corpus"] == c))
    speedups = [next(r["speedup"] for r in rows if r["corpus"] == c and r["method"] == "async") for c in corpora]
    labels = [f"{c}\n({next(r['sessions'] for r in rows if r['corpus'] == c)} sessions)" for c in corpora]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, speedups, color="#44aa44")
    for bar, s in zip(bars, speedups):
        ax.text(bar.get_x() + bar.get_width() / 2, s, f"{s:.2f}×", ha="center", va="bottom", fontsize=9)
    ax.axhline(1.0, color="k", ls="--", alpha=0.4, label="serial baseline (break-even)")
    ax.set_ylabel("speedup (× serial)")
    ax.set_title("Async scraping speedup over serial")
    ax.legend()
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    print(f"Saved plot to {out_png}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1 scraping benchmark (serial vs async).")
    parser.add_argument("--corpus", choices=[*SIZES, "all"], action="append",
                        help="corpus size(s) to scrape; repeatable. Default: small + medium.")
    parser.add_argument("--plot-only", action="store_true",
                        help="skip scraping; redraw figures from data/results/scraping_benchmark.csv")
    args = parser.parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / "scraping_benchmark.csv"

    if args.plot_only:
        all_rows = load_results(csv_path)
    else:
        if not args.corpus:
            chosen = DEFAULT_CORPORA
        elif "all" in args.corpus:
            chosen = list(SIZES)
        else:
            chosen = args.corpus
        all_dates = json.loads(SESSION_DATES_PATHS.read_text(encoding="utf-8"))

        all_rows = []
        for corpus in chosen:
            dates = all_dates[:SIZES[corpus]]
            all_rows.extend(benchmark_corpus(corpus, dates))
        print_table(all_rows)
        save_results(all_rows, csv_path)

    plot_runtime(all_rows, RESULTS_DIR / "scraping_runtime.png")
    plot_speedup(all_rows, RESULTS_DIR / "scraping_speedup.png")
    print(f"\nFigures saved to {RESULTS_DIR}")

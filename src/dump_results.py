"""Dump the *content* findings of the analysis (not timings) to CSV for the report.

`benchmark.py` measures speed and throws the analysis result away. This script
runs the **vectorized** analysis on each corpus and persists what Section 9 of
the report needs:

  data/results/tfidf_{corpus}.csv       -- most *distinctive* words per party
                                           (high TF-IDF = characteristic of that
                                           party, not just frequent everywhere).
  data/results/similarity_{corpus}.csv  -- full party x party cosine-similarity
                                           matrix (how alike two parties' language is).

Note: the vectorized variant computes unigram TF-IDF + cosine similarity only.
It does NOT produce raw word-frequency counts or bigrams/trigrams (that lives in
the serial variant's `by_party` Counters), so those are not dumped here.

Run from the project root:
    python src/dump_results.py                 # all three corpora, top 20
    python src/dump_results.py --corpus big --top 30
"""
import argparse
import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")          # Cyrillic-safe console output on Windows

import common as cmn
from analysis_vectorized import run_tfidf_vectorized

PROC_DIR = Path("data/processed")
RESULTS_DIR = Path("data/results")
ALL_CORPORA = ["small", "medium", "big"]


def dump_tfidf(top_words: dict, out_csv: Path) -> None:
    """Most distinctive words per party (TF-IDF score), already sorted/truncated."""
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["party", "rank", "word", "tfidf_score"])
        for party, words in top_words.items():
            for rank, (word, score) in enumerate(words, start=1):
                writer.writerow([party, rank, word, f"{float(score):.4f}"])
    print(f"Saved {out_csv}")


def dump_similarity(parties: list[str], matrix, out_csv: Path) -> None:
    """Full symmetric cosine-similarity matrix (diagonal = 1.0)."""
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([""] + parties)
        for i, party in enumerate(parties):
            writer.writerow([party] + [f"{matrix[i][j]:.4f}" for j in range(len(parties))])
    print(f"Saved {out_csv}")


def dump_corpus(corpus: str, top: int) -> None:
    csv_path = PROC_DIR / f"speeches_{corpus}.csv"
    df = cmn.load_speeches(csv_path)
    print(f"\n=== {corpus}: {len(df)} speeches from {csv_path} ===")

    result = run_tfidf_vectorized(df, top_n=top)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    dump_tfidf(result["top_words"], RESULTS_DIR / f"tfidf_{corpus}.csv")
    dump_similarity(result["parties"], result["similarity_matrix"],
                    RESULTS_DIR / f"similarity_{corpus}.csv")

    # Console preview so you can eyeball the findings immediately.
    print("Most distinctive words per party (top 8 by TF-IDF):")
    for party, words in result["top_words"].items():
        preview = ", ".join(w for w, _ in words[:8])
        print(f"  {party[:40]:40s}: {preview}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dump vectorized analysis content (words, similarity) to CSV.")
    parser.add_argument("--corpus", default="all",
                        help="corpus to analyze: small/medium/big, or 'all' (default)")
    parser.add_argument("--top", type=int, default=20, help="how many words per party to keep")
    args = parser.parse_args()

    corpora = ALL_CORPORA if args.corpus == "all" else [args.corpus]
    for c in corpora:
        dump_corpus(c, args.top)

"""Correctness gate for Phase 2.

Confirms the three analysis variants (serial, multiprocessing, vectorized)
produce equivalent results before any Phase 3 timing is done. Compares the
top-N TF-IDF words per party as sets, with an 80% overlap threshold (exact
scores differ because the vectorized variant uses sklearn's TF-IDF formula).

Expectation:
  - Serial vs Multiprocessing : ~100% (same code path, just parallelized)
  - Serial vs Vectorized      : ~80-95% (different formula, robust ranking)

Run from the project root:
    python -X utf8 src/verify_correctness.py
"""
import common as cmn
from parse_and_save import PROC_DIR
from analysis_serial import run_serial
from analysis_mp import run_parallel
from analysis_vectorized import run_tfidf_vectorized


def compare_top_words(tfidf_a, tfidf_b, label, top_n=10) -> bool:
    ok = True
    for party in tfidf_a:
        words_a = {w for w, _ in tfidf_a[party][:top_n]}
        words_b = {w for w, _ in tfidf_b.get(party, [])[:top_n]}
        overlap = len(words_a & words_b) / top_n
        status = "OK " if overlap >= 0.8 else "LOW"
        print(f"  [{status}] {party[:30]:30s}: {overlap * 100:3.0f}% match with {label}")
        ok = ok and overlap >= 0.8
    return ok


def run_verification() -> bool:
    df = cmn.load_speeches(PROC_DIR / "speeches.csv")

    serial = run_serial(df)
    mp = run_parallel(df)
    vec = run_tfidf_vectorized(df)

    print("Serial vs Multiprocessing:")
    ok_mp = compare_top_words(serial["tfidf"], mp["tfidf"], "mp")

    print("\nSerial vs Vectorized:")
    ok_vec = compare_top_words(serial["tfidf"], vec["top_words"], "vectorized")

    print()
    if ok_mp and ok_vec:
        print("OVERALL: PASS - all variants agree within threshold")
    else:
        print("OVERALL: FAIL - a variant diverged; investigate before benchmarking")
    return ok_mp and ok_vec


if __name__ == "__main__":
    run_verification()

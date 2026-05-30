import os
import time
from collections import Counter, defaultdict
from multiprocessing import Pool

import common as cmn
from parse_and_save import PROC_DIR
from analysis_serial import (
    analyze_one_speech,
    aggregate_by_party,
    compute_tf_idf,
    compute_cosine_similarity,
)


def _split(seq: list, n: int) -> list[list]:
    """Split seq into n balanced contiguous chunks."""
    k, m = divmod(len(seq), n)
    out, start = [], 0
    for i in range(n):
        end = start + k + (1 if i < m else 0)
        out.append(seq[start:end])
        start = end
    return out


def _analyze_and_aggregate_chunk(speeches_chunk: list[dict]) -> dict:
    """Worker task (map-reduce): analyze AND locally aggregate one chunk.

    Returns a *partial* by_party for this chunk, so only ~n_processes small
    dicts cross the process boundary instead of one Counter per speech.
    Must stay module-level so Pool can pickle it.
    """
    results = [analyze_one_speech(s) for s in speeches_chunk]
    return aggregate_by_party(results)


def _merge_partials(partials: list[dict]) -> dict:
    """Merge the per-worker partial by_party dicts into one (serial, but only
    n_processes of them -- cheap)."""
    merged = defaultdict(lambda: {
        "unigrams": Counter(), "bigrams": Counter(), "trigrams": Counter(),
        "total_words": 0, "speech_count": 0,
    })
    for partial in partials:
        for party, data in partial.items():
            merged[party]["unigrams"].update(data["unigrams"])
            merged[party]["bigrams"].update(data["bigrams"])
            merged[party]["trigrams"].update(data["trigrams"])
            merged[party]["total_words"] += data["total_words"]
            merged[party]["speech_count"] += data["speech_count"]
    return dict(merged)


def run_parallel(df, n_processes=None) -> dict:
    """Map-reduce multiprocessing: each worker analyzes AND aggregates its own
    chunk; the parent merges n_processes partial aggregates. This pushes the
    expensive aggregation into the parallel region and shrinks return-pickling
    from one object per speech to one per worker."""
    if n_processes is None:
        n_processes = os.process_cpu_count() or 1
    speeches = df.to_dict("records")
    chunks = _split(speeches, n_processes)

    with Pool(processes=n_processes) as pool:
        partials = pool.map(_analyze_and_aggregate_chunk, chunks)

    by_party = _merge_partials(partials)
    tfidf = compute_tf_idf(by_party)
    similarity = compute_cosine_similarity(by_party)
    return {"by_party": by_party, "tfidf": tfidf, "similarity": similarity}


def run_parallel_naive(df, n_processes=None) -> dict:
    """Naive multiprocessing (kept for comparison): parallelize Step A only,
    return one result per speech, aggregate serially in the parent. This is the
    version that loses to its own overhead -- pickling one Counter per speech
    and leaving the 37%-of-runtime aggregation serial."""
    if n_processes is None:
        n_processes = os.process_cpu_count() or 1
    speeches = df.to_dict("records")
    chunksize = max(1, len(speeches) // (n_processes * 4))

    with Pool(processes=n_processes) as pool:
        results = pool.map(analyze_one_speech, speeches, chunksize=chunksize)

    by_party = aggregate_by_party(results)
    tfidf = compute_tf_idf(by_party)
    similarity = compute_cosine_similarity(by_party)
    return {"by_party": by_party, "tfidf": tfidf, "similarity": similarity}


if __name__ == "__main__":
    df = cmn.load_speeches(PROC_DIR / "speeches.csv")
    start = time.perf_counter()
    result = run_parallel(df)
    end = time.perf_counter()
    print(f"Map-reduce multiprocessing completed in {end - start:.2f} seconds")

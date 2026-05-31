# Phase 4 — Notes for the report

Running collection of the *analysis* (the "why") and concrete measurements gathered while building Phases 1–3. The rubric rewards explaining **why** each approach does or doesn't speed things up — this file is the raw material for sections 9 (results) and 10 (analysis).

> Status: accumulating. Numbers from the **small corpus** (1 session, 2024-12-18, ~138 speeches after `load_speeches` filtering). Medium/large corpus numbers to be added after scraping the full mandate.

---

## 1. Approach → parallelization strategy (the big picture)

| Pipeline step | Nature | Tool | Why this tool |
|---|---|---|---|
| Scraping (Phase 1) | I/O-bound (network waits) | `asyncio` + `aiohttp` | GIL released during I/O; single thread overlaps many requests. Processes would waste memory waiting. |
| Per-speech analysis (Step A) | CPU-bound, independent per speech | `multiprocessing.Pool` | Embarrassingly parallel; separate processes bypass the GIL. |
| TF-IDF / cosine similarity (Step B) | Data-parallel, matrix math | NumPy / scipy / sklearn | Bulk ops in compiled C/Fortran; matrix multiply uses BLAS + SIMD. |
| Aggregation (merge counters) | Inherently serial | — | Merging into shared buckets needs synchronization → **Amdahl bottleneck**. |

---

## 2. Why threads don't help the analysis (GIL)

- The analysis is **CPU-bound** (tokenizing, counting) — it executes Python bytecode the whole time.
- CPython's **GIL** lets only one thread run bytecode at a time → threads take turns, no real parallelism on CPU work. Threading would give ~zero speedup (possibly slower from lock contention).
- `multiprocessing` gives each worker its own interpreter + own GIL → true parallelism.
- Contrast with the scraper: that's I/O-bound, GIL is released during network waits, so `asyncio` (single thread) suffices.
- **Caveat for report:** on a *free-threaded* Python build (3.13t/3.14t, no GIL), `threading` would parallelize CPU work with lower overhead than processes — a viable 4th approach, but blocked in practice by sparse free-threaded wheel availability for pandas/numpy/scipy on Windows.

---

## 3. Multiprocessing has a fixed entry cost (measured)

**Small corpus, ~138 speeches:**

| Variant | Time | vs serial |
|---|---|---|
| Serial | 0.02 s | — |
| Multiprocessing | 0.97 s | **~48× slower** |

The 0.97 s is almost entirely **overhead, not work**:
- Spawning ~8 worker processes on Windows (~100 ms each).
- Each worker re-imports the chain `analysis_mp → analysis_serial → parse_and_save → pandas` (pandas import alone ~0.5 s).
- Pickling 138 speeches out to workers and results back.

Actual analysis is still ~0.02 s — buried under ~0.95 s of setup. **Lesson:** parallelism has a fixed entry fee; the workload must be large enough to amortize it. Expect mp to flip to a *win* only on the medium/large corpora. This is the concrete demonstration of overhead-dominates-small-workloads.

---

## 4. What "vectorized" actually means (two senses)

People conflate two things:

1. **Data-science sense:** operates on whole arrays in **compiled C/Fortran** instead of a Python loop. Primary win = eliminating per-element interpreter overhead (~10–100×), independent of special hardware.
2. **Hardware sense:** uses the CPU's **SIMD units** (SSE/AVX vector registers) — one instruction over many numbers.

They overlap but aren't identical. NumPy is always vectorized in sense 1; sense 2 depends on the operation and the BLAS backend. **None of this uses the GPU** (numpy/sklearn are CPU-only by default).

### Per-function classification (for `analysis_vectorized.py`)

| Function | Does | Compiled-bulk? | True SIMD? |
|---|---|---|---|
| `TfidfVectorizer.fit_transform` | tokenize, build vocab, TF-IDF matrix | partly | mostly no |
| `CountVectorizer.fit_transform` | same, raw counts (n-grams) | partly | mostly no |
| `cosine_similarity` | pairwise sim = A·Aᵀ | yes | **yes, heavily** |
| `np.argsort` | sort indices | yes (C sort) | not really |
| `scipy.sparse` (CSR) | skip-the-zeros storage | n/a (memory trick) | no |

### The precise story for the report

> The dominant speedup of the vectorized approach comes from replacing per-element Python loops with bulk operations in compiled C/Fortran, eliminating interpreter overhead. On top of that, the linear-algebra core — cosine similarity's matrix multiplication — is dispatched to a BLAS library (OpenBLAS/MKL) that exploits CPU SIMD instructions and multiple cores. The text-parsing stage (tokenization, vocabulary construction) is **not** vectorizable and forms the serial portion of this approach — its own Amdahl bottleneck. Sparse (CSR) storage is a memory optimization (most word-counts are zero), orthogonal to SIMD.

---

## 5. Phase 1 scraping speedup (measured, for completeness)

Same session, serial vs async scraper:

| Variant | Time | Speedup |
|---|---|---|
| Serial (no session reuse, 0.2 s politeness sleep) | 28.6 s | 1.0× |
| Serial (with `requests.Session` connection reuse) | 19.18 s | 1.49× |
| Async (`aiohttp`, concurrency 5) | 3.97 s | **7.21× / 4.83×** |

Decomposition for the report:
- **Connection reuse** alone: 1.49× (no parallelism — just HTTP keep-alive avoiding repeated TCP/TLS handshakes).
- **Concurrency** on top: 4.83× (this is the asyncio contribution).
- Stacked: 7.21× vs the naive baseline.
- Efficiency of concurrency-5 ≈ 0.97 — near-perfect, because the work is pure I/O with negligible Python between awaits.

---

## 6. Amdahl's Law thread (recurring talking point)

The **aggregation step stays serial in every parallel variant** (merging Counters needs synchronization). Measure what fraction of total runtime it represents — that fraction caps the maximum achievable speedup regardless of core count. This is the central Amdahl observation of the project and should appear in the analysis section.

---

## 7. Data-quality edge case: non-quorum sessions (task formulation)

Scraping the full 51st mandate (181 sessions, ~12 min) surfaced 4 sessions that 500'd: 2025-09-26 and the consecutive cluster 2025-10-15 / 10-16 / 10-17.

- The session-list endpoint flagged them `hasSteno && stenoProcessed = true`, yet the steno **pagination** endpoint (`/steno/0`) returned **500** — the metadata and the content endpoint disagree.
- Root cause is substantive, not just technical: these are **non-quorum sessions** — the chair opened, declared "Няма кворум!" (no quorum), and adjourned. Each has `statementCount == 1` (a single statement). The Oct 15–17 cluster reflects the real late-2025 inability of Parliament to convene.
- Scraper bug it exposed: for a 1-statement session the code still requested the tail URL `/steno/0` (which 500s), even though the bare `/steno` fetch already returned that statement. Fix: only request paged URLs beyond the first fetch's 0–4 window (`if statement_count - 1 >= 5`). The serial scraper was already immune (its `while len < count` loop never runs for count=1).

Report value: a concrete "real-world edge case → why it happens → how the scraper handles it" example for the task-formulation / correctness-criteria section.

---

## 8. Scrape timing (data collection, NOT a parallelism metric)

Async scraper, sessions scraped sequentially (each internally concurrent at 5):

| Corpus | Sessions | Scrape time | per session |
|--------|---------:|------------:|------------:|
| small  | 10       | 13.27 s     | 1.33 s |
| medium | 50       | 167.48 s    | 3.35 s |
| big    | 181      | 697.28 s (~11.6 min) | 3.85 s |

Per-session time rises with corpus span: the early sessions (Nov 2024, freshly convened) are shorter → fewer paged fetches; the big run also paid retry-backoff on the 4 non-quorum failures (see section 7). Per-session cost is dominated by `statementCount` (≈ statementCount/5 paged requests).

Important framing for the report: these wall-clocks are **one-time data-collection cost**, not a speedup metric. The parallelism story for scraping is the per-session serial-vs-async comparison in section 5 (7.21×). Do not present these as benchmark results.

---

## 9. Multiprocessing redesign: naive → map-reduce

**Problem (measured on big corpus):** naive mp barely beat serial (peak 1.14× @ 4 cores). Runtime breakdown showed why — it parallelized only Step A:

| Step | % of runtime | parallel? |
|------|---:|---|
| A analyze | 53% | yes (the only part mp ran in parallel) |
| B aggregate | 37% | **no — serial in parent** |
| C tf-idf + cosine | 10% | no — serial |

Parallel fraction **p = 0.53** → Amdahl ceiling **~2×** no matter how many cores. Plus 22,000 per-speech Counters pickled back to the parent (the overhead that made mp(1) *slower* than serial).

### Naive: parallelize Step A only, aggregate serially

```
speeches ──map(per speech)──>  [worker: analyze]  ──22,000 Counters──>  PARENT
                               [worker: analyze]        (pickle back)   aggregate  (SERIAL, 37%)
                               [worker: analyze]                          → tf-idf → cosine
```

### Map-reduce: each worker analyzes AND aggregates its own chunk

```
            split into N chunks         MAP (parallel)              REDUCE (parent, cheap)
speeches ──────────────────>  [worker: analyze + aggregate]  ──N partials──>  merge N dicts
                              [worker: analyze + aggregate]    (pickle back)    → tf-idf → cosine
                              [worker: analyze + aggregate]
```

**The change is not "bigger tasks" — it is relocating the aggregation (Step B) into the parallel region.** Two effects:
- Parallel fraction **0.53 → ~0.90** → Amdahl ceiling **~2× → ~6×**.
- Objects pickled back: **22,000 → N** (one partial aggregate per worker).

Correctness preserved because `Counter` merge is associative/commutative (aggregate-then-merge == aggregate-all-at-once).

Report angle: same tool (`multiprocessing.Pool`), same result — the **decomposition** (where the reduction runs, how much crosses the process boundary) is what decides whether parallelism pays off.

---

## 10. Analysis benchmark — final measured results

Measured 2026-05-26 with `src/benchmark.py`. Machine: 16 logical cores (the mp curve knees at ~8 → **8 physical cores** + hyperthreads). Methodology: CSV loaded once outside all timers; each measurement is the **min of 3 runs**; mp pool gets one untimed warm-up; mp swept over {1,2,4,8,12,16}.

**All three variants do equal work** — per-party unigram/bigram/trigram tables + TF-IDF + cosine similarity. (How this parity was reached matters; see the implementation note below.)

### Headline numbers (speedup vs serial baseline)

| corpus | serial (s) | vectorized | mp (best) |
|--------|-----------:|-----------:|-----------|
| small (354 speeches)    | 0.097 | **1.07×** | 0.23× @4 procs |
| medium (5 871 speeches) | 1.407 | **1.31×** | 1.07× @4 procs |
| big (21 907 speeches)   | 6.517 | 1.17×     | **1.56× @8 procs** |

### mp speedup vs process count (the speedup graph)

| procs | small | medium | big |
|------:|------:|-------:|----:|
| 1  | 0.19 | 0.62 | 0.64 |
| 2  | 0.22 | 0.85 | 1.04 |
| 4  | 0.23 | 1.07 | 1.39 |
| 8  | 0.19 | 1.06 | **1.56** |
| 12 | 0.16 | 0.99 | 1.52 |
| 16 | 0.13 | 0.89 | 1.47 |

### What the numbers say (the "why")

- **Vectorization wins on every corpus, modestly** (1.07–1.31×) and with **no process overhead**, so it's the only approach that helps on the small/medium corpora. Its win comes from (a) one tokenization pass reused for unigram TF-IDF + n-grams, and (b) the TF-IDF matrix + cosine running in sklearn's compiled C core. But that numerical core is a *small* slice of the pipeline, so the overall win stays modest.
- **mp wins biggest on the big corpus (1.56× @ 8 procs)** because the dominant cost — n-gram counting — is embarrassingly parallel CPU work, and separate processes bypass the GIL. It's the only approach that scales with cores.
- **mp loses on small (0.23×)** and only breaks even on medium: process spawn + per-worker module import + pickling outweigh ~0.1–1.4 s of actual work. The fixed entry cost must be amortized by a large enough workload (Gustafson).
- **The hyperthread knee:** mp peaks at 8 procs (= physical cores) and *declines* at 12/16. For CPU-bound work, logical cores past the physical count contend for the same execution units.
- The two winners win for **different reasons** (vectorization = less redundant work + compiled numerical kernels; mp = true multi-core parallelism) and at **different scales** — the core contrast for the analysis section.

### Implementation note: what "equal work" cost us (and the lesson)

Getting a *fair* vectorized comparison was the subtle part, and it's report-worthy:

1. **First attempt was unfair** — the vectorized variant only computed unigram TF-IDF, skipping the bigram/trigram tables serial/mp build. It "won" ~4.4× partly by doing **less work**.
2. **Forcing equal work via `CountVectorizer`(2,3) made it 2.4× *slower* than serial.** Profiling (not guessing) showed why: `CountVectorizer` spends ~17 s on the big corpus building a **3.4-million-entry n-gram vocabulary + CSR matrix**, just to read the top-20 per party. `max_features` didn't help (it counts everything first, and changed the top-20). **`CountVectorizer` is built for ML feature matrices, the wrong tool for "top-N frequency counts."**
3. **Fix:** count n-grams with `Counter` + `zip(tokens, tokens[1:])` (tuples, lazy — no per-n-gram string allocation; join only the survivors), the same method serial/mp use.
4. **Then make vectorized genuinely faster:** it was tokenizing the corpus **twice** (once in `TfidfVectorizer`, once in the n-gram loop). Tokenizing **once** and feeding the pre-tokenized lists to `TfidfVectorizer(analyzer=identity)` cut big from 6.68 s → 5.57 s.

Lesson for the report: *vectorization accelerates numerical/matrix work, not string counting; and a benchmark is only meaningful when every variant produces the same outputs with no variant secretly doing more or less work.*

---

## 11. Scraping benchmark — serial vs async across corpus sizes

Measured with `src/benchmark_scraping.py` (sessions scraped sequentially in both; async internally concurrent at 5; serial uses `requests.Session` keep-alive). The serial-without-session-reuse variant from section 5 is intentionally excluded here.

| corpus | sessions | serial (s) | async (s) | async speedup |
|--------|---------:|-----------:|----------:|--------------:|
| small  | 10  | 51.77  | 11.04  | 4.69× |
| medium | 50  | 887.87 | 167.47 | **5.30×** |
| big    | 181 | _not measured_ | (≈697, see §8) | _not measured_ |

> Decision: the **big serial scrape was not run** (≈45–55 min of live-server load for one more data point). small + medium already establish the trend; the report uses those two.

**The speedup grows with corpus size (4.69× → 5.30×)** — weak-scaling behaviour: longer sessions have more statement-pages, so async has more requests to overlap at concurrency 5, while the fixed per-session cost (first fetch, 0.2 s inter-session sleep) amortizes.

Side note worth a sentence in the setup section: per-session serial time jumped from 5.18 s (small) to 17.76 s (medium) — the first 10 sessions (early Nov 2024, freshly convened) are short; later sessions are full-length. So the early corpus is *not* representative of per-session cost.
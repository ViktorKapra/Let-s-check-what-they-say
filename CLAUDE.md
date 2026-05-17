# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Parallel Analysis of Political Language in the Bulgarian Parliament** — A university course project for Parallel Programming in Python.

This project implements multiple parallelization approaches to analyze parliamentary stenograms from Bulgaria's 51st National Assembly (data sourced from strazha.bg). The work is divided into four phases:

1. **Phase 1:** Data collection and preprocessing (web scraping)
2. **Phase 2:** Implementation of serial and parallel solutions
3. **Phase 3:** Benchmarking and performance measurement
4. **Phase 4:** Report writing

## Working mode: teaching, not autopilot

This is a **learning project**. The user is a student writing each function themselves to learn parallel programming. Default behavior:

- Do **not** write implementation code unprompted, even when the next step is obvious. Describe the task, let the user write it, then review what they paste.
- When reviewing, point out bugs and explain the *why* — don't just hand back a corrected version.
- Only produce full code when the user explicitly asks ("write it for me", "give me the code", "do it"). A request for an explanation or a hint is not a request for code.
- Small edits to fix a clear typo the user already identified are fine; new logic is not.

## Project Structure

**Current state (as of writing):**
- `docs/` — Bulgarian-language planning docs. The detailed Phase 1 guide is [фаза1_събиране_на_данни.md](docs/фаза1_събиране_на_данни.md); the overall plan lives in `план_за_действие*.md`.
- `src/collecting_data/scraper_serial.py` — partial; the serial scraper currently being built. Note the subdirectory — the planning docs reference `src/scraper_serial.py` but the real path is nested under `src/collecting_data/`.
- `src/main.py` — empty placeholder.
- `requirments.txt` — **note typo** (missing the `e`). Not yet renamed; install with `pip install -r requirments.txt`.
- `venv/` — local virtual environment.

**Not yet created** (referenced in planning docs but absent from the repo): `src/scraper_async.py`, `src/parse_and_save.py`, `src/analysis_*.py`, `data/raw/`, `data/processed/`, `notebooks/`, `tests/`.

## Core Technology Stack

**Data Collection Phase:**
- `requests` — synchronous HTTP requests
- `aiohttp` — asynchronous HTTP requests for concurrent fetching
- `asyncio` — async/await coordination and semaphore-based rate limiting

**Analysis Phase:**
- `numpy` — vectorized numerical operations
- `scipy.sparse` — sparse matrix operations for TF-IDF
- `pandas` — data manipulation and CSV handling
- `scikit-learn` — feature extraction (TfidfVectorizer, cosine similarity)
- `multiprocessing.Pool` — CPU-bound parallelization across cores
- `dask` or `ray` — distributed data processing (optional but recommended)
- `matplotlib`, `seaborn` — visualization for results

**Testing & Documentation:**
- `pytest` — unit testing (when added)
- Markdown reports for Phase 4 deliverable

## Key Implementation Details

### Phase 1: Web Scraping

The parliamentary data is embedded as JSON in HTML via Remix.js (`window.__remixContext`). No JavaScript execution required.

**Data structure:**
- Sessions identified by date (format: `YYYY-MM-DD`)
- Each session contains 200-300+ statements
- Statements extracted from `sessionStatements` array
- Party affiliation via `pgMemberships` table

**Known API quirks (verified against live responses — overrides the planning docs):**
- Route keys in `context["state"]["loaderData"]` are literal strings containing `$` and dots: `"routes/_front.sessions.$sessionSlug"` (session metadata) and `"routes/_front.sessions.$sessionSlug.steno"` (statements). Do not template the `$sessionSlug` — it stays literal.
- `parlSession` does **not** include a `statementCount` field, despite what [фаза1_събиране_на_данни.md](docs/фаза1_събиране_на_данни.md) implies. Determine the end of a session by paging until the response returns no new statements rather than reading a count up-front.
- Each statement page returns ~5 statements around the requested number (overlapping windows) — dedupe on statement number.
- Session metadata (`parlGroups`, `pgMemberships`) is consistent across pages of the same session — fetch once.

**Important constraints:**
- Semaphore-based concurrency limiting (recommended: 5-10 concurrent requests)
- Each statement page loads 5 statements around the requested number → deduplication required
- Session metadata (parties, memberships) consistent across all statement pages

**Performance baseline:**
- Serial scraping: ~30-90 seconds per session (~280 statements)
- This becomes `T_serial` for speedup calculations in Phase 3

### Phase 2: Parallel Analysis Approaches

Minimum 3 required implementations:

1. **Baseline (Serial):** Pure Python loop, word count, n-grams, TF-IDF by party
2. **Multiprocessing:** `Pool.map()` for embarrassingly-parallel statement analysis (GIL bypass)
3. **Vectorization:** NumPy/scipy sparse matrices for corpus-wide TF-IDF and cosine similarity
4. **Distributed (Optional):** Dask/Ray for corpus larger than RAM

Each statement is independently processable (embarrassingly parallel):
- Tokenization
- N-gram extraction
- Word frequency counting
- TF-IDF vector computation

### Phase 3: Benchmarking Requirements

**Three corpus sizes:**
- Small: 1 session (~280 statements)
- Medium: ~10 sessions, 1 month (~2,500 statements)
- Large: ~120 sessions, 1 year (~35,000 statements)

**Measurement protocol:**
- Minimum 3 repetitions per experiment
- Use `time.perf_counter()` for timing
- Calculate speedup: `Speedup(p) = T_serial / T_parallel(p)`
- Calculate efficiency: `Efficiency(p) = Speedup(p) / p`

**Required artifacts:**
- At least 1 table with results
- At least 1 graph (speedup vs. number of processes)

## Common Development Commands

### Setup (current)
```powershell
# Activate the existing venv
.\venv\Scripts\Activate.ps1

# Install dependencies (note the misspelled filename)
pip install -r requirments.txt
```

### Phase 1: Web Scraping (current)
```powershell
# Run the in-progress serial scraper
python src\collecting_data\scraper_serial.py
```

### Planned commands (not yet runnable)
The scripts below are described in the planning docs but **do not exist in the repo yet**. Do not invoke them, and do not assume they work — they're listed here only as a forward-looking map of what Phase 2 / 3 will add:

- `src/scraper_async.py` — async scraper
- `src/parse_and_save.py` — JSON → CSV
- `src/analysis_serial.py`, `analysis_mp.py`, `analysis_vectorized.py`, `analysis_dask.py` — Phase 2 analysis variants. The plan is for each to accept `--corpus {small,medium,large}` and `--runs N` (and `--processes N` where applicable) for Phase 3 benchmarking.
- `pytest`, `black`, `flake8`, `mypy` — none configured yet. Don't suggest running them until they're added to `requirments.txt`.

## Important Considerations

### Data Ethics & Legal
- All data from strazha.bg is public information (Bulgarian FOIA law)
- Concurrent request limiting via `asyncio.Semaphore` is required for server respect
- Consider contacting the Strava team for large-scale scraping

### Deduplication Strategy
- Each statement page loads 5 statements around the requested number (overlapping windows)
- Use dict with statement number as key to avoid duplicates
- Verify all statements 1 to `statementCount` are present after scraping

### GIL and Parallelization
- `multiprocessing` required for CPU-bound work (overcomes Python GIL)
- `asyncio` sufficient for I/O-bound work (network requests)
- Vectorized NumPy operations are inherently parallel at C level

### Correctness Validation (Phase 1)
Before proceeding to Phase 2, verify:
- [ ] At least one full session scraped (all ~280 statements present)
- [ ] Every statement has a non-empty `party` field (except "Неизвестна" for independent members)
- [ ] Serial and async scrapers produce identical output for the same session
- [ ] Recorded timing of serial scraping for each corpus size
- [ ] CSV loads correctly with `pandas.read_csv()` without encoding errors
- [ ] Data prepared for at least 3 corpus sizes

## Report Structure (Phase 4)

12-section format with scoring rubric (100 points total):
1. Title and metadata
2. Names, faculty number, course, date
3. Introduction (why parliamentary text suits parallelization)
4. Goals and brief plan
5. Task formulation (input, output, algorithm, correctness criteria)
6. Serial solution description
7. Parallel solutions (one subsection per approach)
8. Experimental setup (hardware, corpus sizes, repetitions)
9. Results (tables and graphs)
10. Analysis (when parallelization helps/hurts, overhead analysis)
11. Conclusions and limitations
12. Appendix (run instructions, file structure, repo link)

Key emphasis: explain **why** parallelization provides (or doesn't provide) speedup for each approach.

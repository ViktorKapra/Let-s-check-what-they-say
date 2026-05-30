import argparse
import asyncio
import json
import time
from pathlib import Path
import aiohttp

# Reuse the pure-Python pieces from the serial version
from scraper_serial import (
    BASE_URL,
    HEADERS,
    SESSION_DATES_PATHS,
    SIZES,
    parse_remix_context,
    extract_session_metadata,
    extract_statements,
)

async def fetch_html_async(session, semaphore, url, retries=4):
    for attempt in range(retries):
        try:
            async with semaphore:
                async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    response.raise_for_status()
                    return await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            if attempt == retries - 1:
                raise                       # out of retries -- let it propagate
            await asyncio.sleep(2 ** attempt)  # backoff: 1s, 2s, 4s
        
async def scrape_session_async(date: str, output_dir: Path, concurrency: int = 5) -> Path:
    base = f"{BASE_URL}/sessions/{date}/steno"
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session: # for reusing client session across multiple requests
        fetched_html = await fetch_html_async(session=session, semaphore=semaphore, url=base)
        context = parse_remix_context(fetched_html)
        first_batch = extract_statements(context)
        meta_route = context["state"]["loaderData"]["routes/_front.sessions.$sessionSlug"]
        metadata = extract_session_metadata(context)
        statement_count = int(meta_route["statementCount"])
        urls = [f"{base}/{n}" for n in range(5, statement_count, 5)]
        if statement_count - 1 >= 5:  # first fetch already covers statements 0-4
            urls.append(f"{base}/{statement_count - 1}")

        htmls = await asyncio.gather(*(fetch_html_async(session, semaphore, u) for u in urls))
        statements_by_number = {s["number"]: s for s in first_batch}
        for html in htmls:
            ctx = parse_remix_context(html)
            for s in extract_statements(ctx):
                statements_by_number[s["number"]] = s
        
        statements = sorted(statements_by_number.values(), key=lambda s: s["number"])
        for s in statements:
            s["party"] = metadata["party_by_member"].get(s["parlMemberId"], "Неизвестна")

        expected = set(range(statement_count))
        missing = sorted(expected - statements_by_number.keys())
        if missing:
            raise RuntimeError(f"Session {date}: missing {missing[:10]}{'...' if len(missing) > 10 else ''}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{date}_async.json"
    payload = {
        "session_date": metadata["session_date"],
        "expected_count": statement_count,
        "actual_count": len(statements),
        "statements": statements,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
    
async def scrape_corpus(corpus: str, base_dir: Path = Path("data/raw")) -> int:
    output_dir = base_dir / corpus
    output_dir.mkdir(parents=True, exist_ok=True)
    dates = json.loads(SESSION_DATES_PATHS.read_text(encoding="utf-8"))
    selected = dates[:SIZES[corpus]]
    for i, date in enumerate(selected, start=1):
        out_file = output_dir / f"{date}_async.json"
        if out_file.exists():
            
            continue
        try:
            await scrape_session_async(date, output_dir)
           
        except Exception as e:
            # don't let one bad session kill the batch; re-run retries it (no file written)
            print(f"[{i}/{len(selected)}] {date}: FAILED ({e}) -- will retry on re-run")
        await asyncio.sleep(0.2)  # be polite between sessions
    return len(selected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape parliament sessions asynchronously.")
    parser.add_argument("--corpus", choices=SIZES, default="small",
                        help="how many sessions to scrape (small=10, medium=50, big=181)")
    args = parser.parse_args()

    t0 = time.perf_counter()
    n = asyncio.run(scrape_corpus(args.corpus))
    elapsed = time.perf_counter() - t0
    print(f"Scraped {n} sessions ({args.corpus}) in {elapsed:.2f}s")
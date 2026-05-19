import asyncio
import json
import time
from pathlib import Path
import aiohttp

# Reuse the pure-Python pieces from the serial version
from scraper_serial import (
    BASE_URL,
    HEADERS,
    parse_remix_context,
    extract_session_metadata,
    extract_statements,
)

async def fetch_html_async(session, semaphore, url):
    async with semaphore:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as response:
            response.raise_for_status()
            return await response.text()
        
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
    
if __name__ == "__main__":
    t0= time.perf_counter()
    result = asyncio.run(scrape_session_async("2024-12-18", Path("data/raw")))
    elapsed = time.perf_counter() - t0
    print(f"Scraped {result} in {elapsed:.2f} seconds")
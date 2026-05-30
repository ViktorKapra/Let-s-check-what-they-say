"""Enumerate all session dates of one parliament and save them as a flat list.

Uses the Remix `_data` resource route to list sessions month by month:
  /sessions/?request-type=SESSIONS&year=Y&month=M&parliament-id=ID
            &_data=routes/_front.sessions._index
  -> {"sessions": [{"slug": "2025-10-15", "hasSteno": true, "stenoProcessed": true, ...}, ...]}

Only dates of sessions with a finished transcript (hasSteno and stenoProcessed)
are kept. The output is a plain flat list of date strings, which you can chunk
manually into corpora of different session counts.

Run from the project root:
    python src/collecting_data/scrape_mandate.py
"""
import asyncio
import json
from pathlib import Path

import aiohttp

from scraper_serial import BASE_URL, HEADERS

# 51st National Assembly = parliamentId 13, spanning ~2024-2026.
DEFAULT_PARLIAMENT_ID = 13
DEFAULT_YEARS = (2024, 2025, 2026)
OUTPUT_FILE = Path("data/session_dates.json")


async def fetch_session_slugs(
    http: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    parliament_id: int,
    years: tuple[int, ...],
) -> list[str]:
    """Return all session dates (slugs) that have a finished transcript."""
    slugs: list[str] = []
    for year in years:
        for month in range(1, 13):
            url = (
                f"{BASE_URL}/sessions/?request-type=SESSIONS"
                f"&year={year}&month={month}&parliament-id={parliament_id}"
                f"&_data=routes%2F_front.sessions._index"
            )
            async with semaphore:
                async with http.get(
                    url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=15)
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

            for session in data.get("sessions", []):
                if session.get("hasSteno") and session.get("stenoProcessed"):
                    slugs.append(session["slug"])

    return sorted(set(slugs))


async def save_session_dates(
    parliament_id: int = DEFAULT_PARLIAMENT_ID,
    years: tuple[int, ...] = DEFAULT_YEARS,
    output_file: Path = OUTPUT_FILE,
    concurrency: int = 5,
) -> None:
    """Enumerate session dates and write them as a flat JSON list."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as http:
        slugs = await fetch_session_slugs(http, semaphore, parliament_id, years)

    output_file.write_text(json.dumps(slugs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(slugs)} session dates to {output_file}")


if __name__ == "__main__":
    asyncio.run(save_session_dates())

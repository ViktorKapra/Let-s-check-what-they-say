
import argparse
import requests
import re
import json
import time
from pathlib import Path

SESSION_DATES_PATHS = Path("data/session_dates.json")
SMALL_INPUT_SIZE = 10
MEDIUM_INPUT_SIZE = 50
BIG_INPUT_SIZE = 181
SIZES = {"small": SMALL_INPUT_SIZE, "medium": MEDIUM_INPUT_SIZE, "big": BIG_INPUT_SIZE}


BASE_URL = "https://www.strazha.bg"
REMIX_RE = re.compile(r"window\.__remixContext\s*=\s*(\{.*?\});\s*</script>", re.DOTALL)
# The regex captures the JSON object assigned to window.__remixContext, which contains the data we need.

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bg-BG,bg;q=0.9",
}

def fetch_html(session, url):
    response = session.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()  # Check if the request was successful
    return response.text

def parse_remix_context(html):
    match = REMIX_RE.search(html)
    if not match:
        raise ValueError("Could not find the Remix context in the HTML.")
    return json.loads(match.group(1))

def extract_session_metadata(context):
    session_data = context["state"]["loaderData"]["routes/_front.sessions.$sessionSlug"]
    
    political_parties_by_id = {pg["id"]: pg["name"] for pg in session_data["parlGroups"]}
    group_by_member = {m["parlMemberId"]: m["parlGroupId"] for m in session_data["pgMemberships"]}
    party_by_member = {
        member_id: political_parties_by_id.get(group_id, "Неизвестна")
        for member_id, group_id in group_by_member.items()
    }
    return {
        "party_by_member": party_by_member,
        "party_by_id": political_parties_by_id,
        "session_date": session_data["parlSession"]["slug"]
    }

def extract_statements(context):
    statements = context["state"]["loaderData"]["routes/_front.sessions.$sessionSlug.steno"]["sessionStatements"]
    return [{
                "id": s["id"],
                "number": s["number"],
                "parlMemberId": s["parlMemberId"],
                "title": s["title"],
                "position": s["position"],
                "text": " ".join(s["paragraphs"])}
                for s in statements
            ]

def scrape_session_serial(date: str, output_dir: Path) -> Path:
    base = f"{BASE_URL}/sessions/{date}/steno"
    with requests.Session() as session:
        context = parse_remix_context(fetch_html(session, base))
        metadata = extract_session_metadata(context)
        first_batch = extract_statements(context)
        meta_route = context["state"]["loaderData"]["routes/_front.sessions.$sessionSlug"]
        statement_count = int(meta_route["statementCount"])
        statements_by_number = {s["number"]: s for s in first_batch}

        next_n = 5
        while len(statements_by_number) < statement_count:
            ctx = parse_remix_context(fetch_html(session, f"{base}/{next_n}"))
            for s in extract_statements(ctx):
                statements_by_number[s["number"]] = s
            next_n += 5
            time.sleep(0.2)

    statements = sorted(statements_by_number.values(), key=lambda s: s["number"])
    for s in statements:
        s["party"] = metadata["party_by_member"].get(s["parlMemberId"], "Неизвестна")

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{date}.json"
    payload = {
        "session_date": metadata["session_date"],
        "expected_count": statement_count,
        "actual_count": len(statements),
        "statements": statements,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape parliament sessions serially.")
    parser.add_argument("--corpus", choices=SIZES, default="small",
                        help="how many sessions to scrape (small=10, medium=50, big=181)")
    args = parser.parse_args()

    dates = json.loads(SESSION_DATES_PATHS.read_text(encoding="utf-8"))
    selected = dates[:SIZES[args.corpus]]
    output_dir = Path("data/raw") / args.corpus

    t0 = time.perf_counter()
    for date in selected:
        scrape_session_serial(date, output_dir)
    elapsed = time.perf_counter() - t0
    print(f"Scraped {len(selected)} sessions ({args.corpus}) into {output_dir} in {elapsed:.2f}s")
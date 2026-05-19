"""One-shot helper: try older session dates against /sessions/<slug>/steno
until one returns a context with sessionStatements. Saves to docs/.
Safe to delete after running."""
import json
import re
import sys
from pathlib import Path

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bg-BG,bg;q=0.9",
}
REMIX_RE = re.compile(r"window\.__remixContext\s*=\s*(\{.*?\});\s*</script>", re.DOTALL)
META_KEY = "routes/_front.sessions.$sessionSlug"
STENO_KEY = "routes/_front.sessions.$sessionSlug.steno"

OUT_DIR = Path("docs")
OUT_DIR.mkdir(exist_ok=True)

# Spread across the 51st National Assembly period (active mid-2024 onward).
CANDIDATES = [
    # 2024 dates
    "2024-12-18", "2024-12-11", "2024-12-04",
    "2024-11-27", "2024-11-20", "2024-11-13", "2024-11-06",
    "2024-10-30", "2024-10-23", "2024-10-16", "2024-10-09",
    "2024-09-25", "2024-09-11", "2024-09-04",
    # 2025 dates
    "2025-01-22", "2025-02-12", "2025-03-12", "2025-04-09",
]


def try_steno(slug):
    url = f"https://www.strazha.bg/sessions/{slug}/steno"
    r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    if r.status_code != 200:
        return None, f"http {r.status_code}"
    m = REMIX_RE.search(r.text)
    if not m:
        return None, "no remix context"
    ctx = json.loads(m.group(1))
    routes = ctx.get("state", {}).get("loaderData", {})
    if META_KEY not in routes or STENO_KEY not in routes:
        return None, f"missing route key (have: {list(routes)[:4]})"
    statements = (routes[STENO_KEY] or {}).get("sessionStatements") or []
    if not statements:
        return None, "0 statements"
    return (ctx, routes, statements), "ok"


for slug in CANDIDATES:
    url = f"https://www.strazha.bg/sessions/{slug}/steno"
    print(f"GET {url}", end=" -> ")
    try:
        result, why = try_steno(slug)
    except Exception as e:
        print(f"failed: {e}")
        continue
    print(why)
    if result is None:
        continue

    ctx, routes, statements = result
    n = len(statements)

    full_path = OUT_DIR / "sample_remix_context_full.json"
    trim_path = OUT_DIR / "sample_remix_context.json"
    full_path.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    trimmed_steno = {
        **routes[STENO_KEY],
        "sessionStatements": statements[:3],
        "_note": f"trimmed to first 3 of {n} statements; see *_full.json for everything",
    }
    trimmed = {
        "_source_url": url,
        "_statement_count_actual": n,
        META_KEY: routes[META_KEY],
        STENO_KEY: trimmed_steno,
    }
    trim_path.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  OK: {n} statements")
    print(f"  wrote {full_path} ({full_path.stat().st_size:,} bytes)")
    print(f"  wrote {trim_path} ({trim_path.stat().st_size:,} bytes)")
    sys.exit(0)

print("No date produced statements. Pull manually — see instructions.")
sys.exit(1)

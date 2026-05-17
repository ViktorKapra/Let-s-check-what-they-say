import requests
import re
import json
import time
from pathlib import Path

BASE_URL = "https://www.strazha.bg"
REMIX_RE = re.compile(r"window\.__remixContext\s*=\s*(\{.*?\});\s*</script>", re.DOTALL)
# The regex captures the JSON object assigned to window.__remixContext, which contains the data we need.

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "bg-BG,bg;q=0.9",
}

def fetch_html(url):
    response = requests.get(url, headers=HEADERS, timeout=15)
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

def extract_statement(context):
    )
    
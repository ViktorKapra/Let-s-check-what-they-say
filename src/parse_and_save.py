import argparse
import json
import csv
from pathlib import Path
from common import clean_text, tokenize_and_remove_stopwords

RAW_DIR = Path("data/raw")
PROC_DIR = Path("data/processed")

FIELDNAMES = [
    "session_date", "statement_id", "statement_number",
    "mp_id", "speaker", "position", "party", "text", "word_count",
]


def process_all_sessions(corpus: str) -> None:
    raw_dir = RAW_DIR / corpus
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    party_stats: dict[str, int] = {}
    skipped = 0
    seen_dates: set[str] = set()

    for json_path in sorted(raw_dir.glob("*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if data["session_date"] in seen_dates:
            continue  # dedup serial/async copies of the same session
        seen_dates.add(data["session_date"])
        for statement in data["statements"]:
            cleaned = clean_text(statement["text"])
            tokens = tokenize_and_remove_stopwords(cleaned)
            if len(tokens) < 5:
                skipped += 1
                continue

            party = statement.get("party", "Неизвестна")
            party_stats[party] = party_stats.get(party, 0) + 1

            rows.append({
                "session_date":     data["session_date"],
                "statement_id":     statement["id"],
                "statement_number": statement["number"],
                "mp_id":            statement["parlMemberId"],
                "speaker":          statement["title"],
                "position":         statement["position"],
                "party":            party,
                "text":             cleaned,
                "word_count":       len(tokens),
            })

    csv_path = PROC_DIR / f"speeches_{corpus}.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {csv_path}")
    print(f"Skipped (< 5 tokens): {skipped}")
    print("\nSpeeches per party:")
    for party, count in sorted(party_stats.items(), key=lambda x: -x[1]):
        print(f"  {party:55s}  {count:5d}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a CSV corpus from scraped sessions.")
    parser.add_argument("--corpus", default="small",
                        help="corpus folder under data/raw/ to process (e.g. small, medium, big)")
    args = parser.parse_args()
    process_all_sessions(args.corpus)
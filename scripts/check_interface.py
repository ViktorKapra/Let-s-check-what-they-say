"""Sanity check for the Phase 1 -> Phase 2 interface.

Run after parse_and_save.py to verify that data/processed/speeches.csv
meets the contract Phase 2 analysis scripts depend on.

Usage:
    python scripts/check_interface.py

Exit code is 0 on pass, 1 on any failed check.
"""
import sys
from pathlib import Path

import pandas as pd

CSV_PATH = Path("data/processed/speeches.csv")

EXPECTED_COLS = [
    "session_date", "statement_id", "statement_number",
    "mp_id", "speaker", "position", "party", "text", "word_count",
]


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found. Run parse_and_save.py first.")
        return 1

    df = pd.read_csv(CSV_PATH, encoding="utf-8")
    failures = 0

    print("=== Phase 1 -> Phase 2 interface check ===\n")

    # 1. Schema
    missing = set(EXPECTED_COLS) - set(df.columns)
    extra = set(df.columns) - set(EXPECTED_COLS)
    if missing:
        print(f"FAIL columns: missing {missing}")
        failures += 1
    else:
        print("PASS columns: all 9 present")
    if extra:
        print(f"  note: extra columns present: {extra}")

    # 2. Shape and nulls
    print(f"\nShape: {df.shape[0]} rows x {df.shape[1]} cols")
    nulls = df.isnull().sum()
    if nulls.sum() > 0:
        print(f"FAIL nulls: {nulls.sum()} total")
        for col, n in nulls.items():
            if n > 0:
                print(f"  {col}: {n}")
        failures += 1
    else:
        print("PASS nulls: none")

    # 3. Party distribution
    unknown = int((df["party"] == "Неизвестна").sum())
    unknown_pct = 100 * unknown / len(df) if len(df) else 0
    print(f"\nParties: {df['party'].nunique()} unique")
    if unknown_pct > 10:
        print(f"WARN 'Неизвестна': {unknown} rows ({unknown_pct:.1f}%) -- high, check pgMemberships")
    else:
        print(f"PASS 'Неизвестна': {unknown} rows ({unknown_pct:.1f}%)")
    print()
    print(df["party"].value_counts().to_string())

    # 4. Text cleanliness
    avg_len = df["text"].str.len().mean()
    stray_parens = int(df["text"].str.contains(r"\(", na=False).sum())
    print(f"\nText avg length: {avg_len:.0f} chars")
    if stray_parens > 0:
        print(f"FAIL stray '(' in text: {stray_parens} rows -- clean_text should have removed them")
        failures += 1
    else:
        print("PASS no stray parens in text")

    # 5. word_count distribution
    print("\nword_count distribution:")
    print(df["word_count"].describe().to_string())
    short = int((df["word_count"] < 10).sum())
    print(f"\nRows with word_count < 10: {short} (will be dropped by load_speeches)")

    print()
    if failures == 0:
        print("OVERALL: PASS")
    else:
        print(f"OVERALL: FAIL ({failures} check(s) failed)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""Print a data-quality summary for a MERX tenders database without scraping.

Reads an existing SQLite database produced by scrape_merx.py, runs the same
quality_report() used by the scraper, prints a human-readable summary, and
(optionally) writes the full JSON report.

Usage:
    python scripts/merx_report.py --db data/merx_tenders.sqlite
    python scripts/merx_report.py --db data/merx_tenders.sqlite --json data/merx_report.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from scrape_merx import quality_report  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/merx_tenders.sqlite"))
    parser.add_argument("--json", type=Path, help="Optional path to write the full JSON report.")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"Database not found: {args.db}")
        return 1

    conn = sqlite3.connect(args.db)
    report = quality_report(conn)
    conn.close()

    def section(title: str) -> None:
        print(f"\n=== {title} ===")

    print(f"MERX tenders data-quality report for {args.db}")
    section("Totals")
    print(f"total tenders:            {report['total_tenders']}")
    print(f"with contacts:            {report['number_with_contacts']}")
    print(f"with documents metadata:  {report['number_with_documents_metadata']}")
    print(f"with bid results:         {report['number_with_bid_results']}")
    print(f"with award results:       {report['number_with_award_results']}")

    section("Tenders by year")
    for row in report["tenders_by_year"]:
        print(f"  {row.get('year') or 'unknown':10} {row['count']}")

    section("Tenders by status")
    for row in report["tenders_by_status"]:
        print(f"  {row['status'] or 'unknown':22} {row['count']}")

    section("Tenders by province")
    for row in report["tenders_by_province"]:
        print(f"  {row['province']:10} {row['count']}")

    section("Top categories")
    for row in report["tenders_by_category"][:15]:
        print(f"  {row['count']:5}  {row['category_name']}")

    section("Top issuing organizations")
    for row in report["top_issuing_organizations"][:15]:
        print(f"  {row['count']:5}  {row['organization']}")

    section("Top awarded suppliers")
    for row in report["top_awarded_suppliers"][:15]:
        print(f"  {row['count']:5}  {row['supplier']}")

    section("Access limitations (not publicly visible)")
    for row in report["access_limitations"]:
        print(f"  {row['section']:14} {row['access_level']:24} {row['count']}")

    section("Scrape errors")
    if report["scrape_errors"]:
        for row in report["scrape_errors"]:
            print(f"  {row['error_type']:30} {row['count']}")
    else:
        print("  none")

    section("Data-quality checks (all should be 0)")
    failures = 0
    for key, value in report["quality_checks"].items():
        flag = "" if value == 0 else "  <-- CHECK"
        if value != 0:
            failures += 1
        print(f"  {key:34} {value}{flag}")
    print(f"\nsuspicious/missing dates flagged: {len(report['suspicious_or_missing_dates'])}")
    print(f"quality-check failures: {failures}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nFull JSON report written to {args.json}")

    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

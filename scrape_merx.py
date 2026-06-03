#!/usr/bin/env python3
"""Compatibility wrapper for the production MERX scraper."""

from scripts.scrape_merx import main


if __name__ == "__main__":
    raise SystemExit(main())

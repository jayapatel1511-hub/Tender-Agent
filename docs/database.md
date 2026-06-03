# Tender Agent Database

SQLite is the long-term local history store. JSON stays in place as the
human-readable export and agent handoff format.

## Files

- `db/schema.sql`: tracked schema source of truth.
- `data/tender-agent.sqlite`: generated local database, ignored by git.
- `data/bid-results.sqlite`: generated MERX bid-result and award intelligence
  database, ignored by git.
- `db/merx_tenders_schema.sql`: normalized all-Canada MERX public tender
  intelligence schema.
- `data/merx_tenders.sqlite`: generated normalized MERX public tender database,
  ignored by git.
- `data/open-tenders/*.json`: readable latest/runs snapshots.
- `data/triage/triage-latest.json`: readable latest triage result.

## Intended Flow

Tier 1 collector:

1. Fetch every open tender and detail page.
2. Write JSON snapshots for inspection.
3. Upsert tender facts into `tenders`.
4. Insert run membership into `open_tender_snapshots`.

Tier 2 triage:

1. Read latest JSON snapshot or SQLite snapshot history.
2. Write `data/triage/triage-latest.json`.
3. Insert decisions into `triage_results`.
4. Log Notion and email outcomes in `notion_sync_log` and `email_log`.

## Why Both JSON And SQLite

JSON is easy to inspect, diff, attach to agent runs, and recover from.
SQLite handles growth: history, dedupe, trend queries, re-triage comparisons,
sync logs, and “what changed since last run?” checks.

Do not commit generated `.sqlite` files. Commit schema and migration scripts.

## Bid Results Database

The bid-results database is intentionally separate from the live opportunity
intake database. It is populated by:

```powershell
python .\scripts\scrape_bid_results.py --max-pages 1 --detail-limit 10
```

Schema source of truth: `db/bid_results_schema.sql`.
Notion target config: `config/bid-results-notion.json`.

Tables:

- `result_runs`: scrape run metadata.
- `result_notices`: MERX bid-result and awarded-notice summaries, plus public
  buyer award-feed notices matched back to their MERX notice IDs when possible.
- `award_details`: supplier, awarded value, award date, and contract dates when
  MERX detail pages or public buyer award feeds expose them.
- `bidder_results`: bidder/price rows when public bid-result detail pages expose
  parseable bidder pricing.

MERX states that award notices are discretionary, so summary-only rows are valid
data: they mean a result/award notice exists, but supplier or price details were
not public in the scraped page or any configured buyer award feed.

## MERX Tender Intelligence Database

The normalized MERX public tender database is populated by:

```powershell
python .\scrape_merx.py --db data\merx_tenders.sqlite --since 2023-01-01 --province all --category all --max-pages 40 --resume --delay-seconds 2
```

Schema source of truth: `db/merx_tenders_schema.sql`.

Tables:

- `scrape_runs` and `scrape_errors`: resumable run metadata and non-fatal error
  logging.
- `tenders`: one row per MERX public notice, deduped by MERX reference/source
  URL.
- `organizations` and `companies`: normalized buyers, owners, bidders, plan
  holders, and awarded suppliers.
- `tender_categories`, `contacts`, `documents`, `amendments`, `plan_holders`,
  `bids`, and `awards`: child facts linked back to `tenders`.
- `raw_pages`: traceability store for source URLs, section names, access level,
  raw text, and raw HTML hashes.

The scraper records login, registration, paid, or restricted tabs as access
limitations. It does not bypass access controls or download protected documents.

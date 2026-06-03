# Tender Agent Database

SQLite is the long-term local history store. JSON stays in place as the
human-readable export and agent handoff format.

## Files

- `db/schema.sql`: tracked schema source of truth.
- `data/tender-agent.sqlite`: generated local database, ignored by git.
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

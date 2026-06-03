# Run Log

Purpose: record monitor run outcomes locally.

## Location

```text
proposals\outputs\ns-tenders\run-logs\
```

Create the folder if needed.

## Required Fields

For JSON logs, include:

- `started_at`
- `completed_at`
- `repo_root`
- `repo_status`
- `git_remote`
- `pull_result`
- `commands`
- `summary_path`
- `open_tender_count`
- `open_tender_snapshot_path`
- `open_tender_latest_path`
- `candidate_bucket_counts`
- `new_matches`
- `duplicates`
- `email_sent`
- `email_recipient`
- `notion_database_updated`
- `notion_database_id`
- `notion_records_created`
- `notion_records_updated`
- `errors`
- `follow_up`

## Rules

- Log what actually happened.
- Include skipped email decisions.
- Include duplicate reasons.
- Include Notion sync status after every run, even when no records changed.
- Keep private data out of logs unless it is already local and required for debugging.

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
- `tenders_checked`
- `new_matches`
- `duplicates`
- `email_sent`
- `email_recipient`
- `errors`
- `follow_up`

## Rules

- Log what actually happened.
- Include skipped email decisions.
- Include duplicate reasons.
- Keep private data out of logs unless it is already local and required for debugging.

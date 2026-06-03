# Downstream Run

Purpose: generate Tier 2 handoff artifacts from `data/triage/triage-latest.json`
without re-scraping the portal.

## Command

```powershell
python scripts/run_downstream.py `
  --triage data/triage/triage-latest.json `
  --snapshot data/open-tenders/open-tenders-latest.json `
  --state data/seen_tenders_state.json
```

## Outputs

- Prime-fit YAML briefs under `proposals/active/ns-tenders/`.
- Email drafts and payloads under `proposals/outputs/ns-tenders/email-*` when
  new relevant leads are found.
- Public-safe Notion upsert payload at
  `proposals/outputs/ns-tenders/notion-sync/notion-upsert-latest.json`.
- Tier 2 run log under `proposals/outputs/ns-tenders/run-logs/`.
- Updated `data/seen_tenders_state.json` for emitted relevant leads.
- SQLite triage import into `data/tender-agent.sqlite` unless `--no-database` is
  used.
- SQLite Notion/email log rows that record exported payloads and unsent email
  payloads.

## Rules

Email payloads are created only for newly relevant `prime-consultant-fit` and
`partner-or-subconsultant-fit` items. The script does not send email directly;
it creates public-safe evidence that can be sent or inspected.

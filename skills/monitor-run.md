# Monitor Run

Purpose: run Nova Scotia tender discovery across the open tender population and generate a raw Tier 1 snapshot.

## Architecture

The run model is staged:

1. Collect every open tender from the portal/API.
2. Fetch the detail endpoint for every open tender.
3. Save an open-tender snapshot and import it into SQLite.

Do not filter out tenders during collection. Early filtering makes misses hard to audit.

The local open-tender database is written on every run:

```text
data\open-tenders\open-tenders-latest.json
data\open-tenders\runs\open-tenders-YYYYMMDD-HHMMSS.json
```

## Domain Filter

The monitor does not filter. Tier 2 narrows results to Englobe-relevant civil, municipal, and transportation engineering work using `scripts/run_tier2.ps1`.

## Preferred Command

```powershell
.\scripts\run_daily.ps1
```

## Direct Fallback

```powershell
.\tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1 `
  -ProposalRepo "C:\Users\jpate\Tender-Agent" `
  -PageSize 100 `
  -MaxPages 80
```

## Notion Sync

After Tier 2, update Notion `Tender Tracker` from:

```text
proposals\outputs\ns-tenders\notion-sync\notion-upsert-latest.json
```

- Database ID: `3734df31-b176-80d5-a260-ff090665cc7c`
- Data source: `collection://3734df31-b176-8056-a4fb-000b525fc94e`
- Config file: `config\notion-tracker.json`
- All Tenders view URL: `https://app.notion.com/p/3734df31b17680d5a260ff090665cc7c?v=3734df31b17680c3ae24000c8d51e408&source=copy_link`
- Dedupe key: `Tender ID`

Update existing tender records first. Create records only for tender IDs that are absent. Sync only public-safe fields and record the sync outcome in the local run log.

## Rules

- Tier 1 does not update `seen_tenders_state.json`; Tier 2 owns duplicate state.
- Do not use a small recent-page sample for normal runs. `run_daily.ps1` defaults to `PageSize=100` and `MaxPages=80` to cover the current open tender population before filtering.
- The monitor writes a complete open-tender snapshot. If a domain-relevant item is missing from triage output, inspect `data\open-tenders\open-tenders-latest.json` before adjusting criteria or classification logic.
- Treat `proposals\active\ns-tenders\` as the current active tender brief folder.
- Treat `proposals\outputs\ns-tenders\ns-tender-monitor-*.json` as monitor summary output.
- Use `-DryRun` only when checking collector behavior.
- After monitor output is generated, run `scripts\run_tier2.ps1`.

## Output

Report command used, snapshot path, open tender count, database import status, and errors.

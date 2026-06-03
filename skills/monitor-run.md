# Monitor Run

Purpose: run Nova Scotia tender discovery across the open tender population and generate current active tender inputs.

## Architecture

The run model is staged:

1. Collect every open tender from the portal/API and save an open-tender snapshot.
2. Run targeted stream filtering and domain triage against that snapshot.
3. Revisit detail pages/documents only for candidates where the listing does not contain enough context.

Do not filter out tenders during collection. Early filtering makes misses hard to audit.

The local open-tender database is written on every run:

```text
data\open-tenders\open-tenders-latest.json
data\open-tenders\runs\open-tenders-YYYYMMDD-HHMMSS.json
```

## Domain Filter

The monitor can produce broad public-sector matches. Normal runs must scan and cache the open tender population first, then narrow results to Englobe-relevant civil, municipal, and transportation engineering work. Treat generic consulting, vehicles/equipment, goods supply, and unrelated advisory services as off-profile during triage, not during collection.

## Preferred Command

```powershell
.\scripts\run_daily.ps1
```

## Direct Fallback

```powershell
.\tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1 `
  -ProposalRepo "C:\Users\jpate\Tender-Agent" `
  -State "C:\Users\jpate\Tender-Agent\data\seen_tenders_state.json"
```

## Notion Sync

After each run, update Notion `Tender Tracker`:

- Database ID: `3734df31-b176-80d5-a260-ff090665cc7c`
- Data source: `collection://3734df31-b176-8056-a4fb-000b525fc94e`
- Config file: `config\notion-tracker.json`
- All Tenders view URL: `https://app.notion.com/p/3734df31b17680d5a260ff090665cc7c?v=3734df31b17680c3ae24000c8d51e408&source=copy_link`
- Dedupe key: `Tender ID`

Update existing tender records first. Create records only for tender IDs that are absent. Sync only public-safe fields and record the sync outcome in the local run log.

## Rules

- Preserve the state file. Do not delete or reset `seen_tenders_state.json`.
- Do not use a small recent-page sample for normal runs. `run_daily.ps1` defaults to `PageSize=100` and `MaxPages=80` to cover the current open tender population before filtering.
- The monitor writes a complete open-tender snapshot first, then filtered candidate buckets. If a domain-relevant item is missing from candidate output, inspect `data\open-tenders\open-tenders-latest.json` before adjusting criteria or classification logic.
- Treat `proposals\active\ns-tenders\` as the current active tender brief folder.
- Treat `proposals\outputs\ns-tenders\ns-tender-monitor-*.json` as monitor summary output.
- Use `-DryRun` only when checking behavior without updating state.
- After monitor output is generated, apply `opportunity-triage.md` before deciding what is email-worthy.
- After monitor output is generated, sync the public-safe result set to Notion before reporting the run complete.

## Output

Report command used, summary path, match count, generated briefs, and errors.

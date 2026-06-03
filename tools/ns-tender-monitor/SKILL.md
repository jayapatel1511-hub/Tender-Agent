---
name: ns-tender-monitor
description: Monitor the Nova Scotia Procurement Portal for open public tenders and snapshot them locally as a raw Tender Agent mirror.
---

# Nova Scotia Tender Monitor

Use this skill when the user wants to inspect, monitor, or automate collection of Nova Scotia public tenders on `https://procurement-portal.novascotia.ca/tenders`. This skill is Tier 1 only: collect every open tender, fetch details for every tender, write raw JSON snapshots, and leave judgment to Tier 2.

## Workflow

1. Work from the Tender Agent repo root. Default:
   `C:\Users\jpate\Tender-Agent`
2. Use `tools/ns-tender-monitor/scripts/Invoke-NsTenderMonitor.ps1` or `scripts/run_daily.ps1` to fetch public tenders through the same guest-auth API flow used by the portal.
3. Do not read criteria, update seen state, classify, email, or write active briefs in Tier 1.
4. Write `data/open-tenders/open-tenders-latest.json` and a timestamped snapshot under `data/open-tenders/runs/`.
5. Import snapshots into SQLite through `scripts/database_store.py` when using `scripts/run_daily.ps1`.
6. Run `scripts/run_tier2.ps1` after collection to triage, dedupe, write briefs, create email/Notion payloads, and update state.

## Commands

Preview a small raw collection sample:

```powershell
.\tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1 -DryRun
```

Run the collector directly:

```powershell
.\tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1
```

Register a scheduled routine, defaulting to every 4 hours:

```powershell
.\tools\ns-tender-monitor\scripts\Register-NsTenderMonitorTask.ps1
```

By default the task uses the current interactive Windows user. Use
`-LogonType S4U` only on machines where policy allows passwordless scheduled
tasks to run while the user is logged off.

## Criteria And Classification

Criteria and classification belong to Tier 2. Update
`config/targeted-stream-criteria.json`, `scripts/run_triage.py`, and
`skills/opportunity-triage.md` when relevance rules change.

## Notes

- The portal public API requires a guest token. Do not scrape rendered table text unless the API flow fails.
- Prefer the PowerShell script on this Windows machine.
- The list endpoint often has sparse tender details. The script fetches tender details by `tenderId` for every open row before writing the raw snapshot.
- If the API starts rejecting requests, rerun a real browser network check against the portal and update the script's headers or endpoint flow.

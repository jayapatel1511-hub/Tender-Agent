# Tender Agent Demo

This demo shows the script-driven Tender Agent workflow: run Nova Scotia tender discovery, import targeted civil/municipal/transportation opportunities into YAML briefs, and preserve run evidence locally.

## Demo Flow

1. Run the daily wrapper.

```powershell
.\scripts\run_daily.ps1
```

2. Review the run log.

```powershell
Get-ChildItem proposals\outputs\ns-tenders\run-logs | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

3. Review current active tender briefs.

```powershell
Get-ChildItem proposals\active\ns-tenders
```

## What To Show

- Active tender YAML briefs in `proposals/active/ns-tenders`.
- Targeted stream criteria in `config/targeted-stream-criteria.json`.
- Monitor summary JSON under `proposals/outputs/ns-tenders`.
- Run logs under `proposals/outputs/ns-tenders/run-logs`.
- Email briefs and payloads when relevant tenders are selected for handoff.
- Explicit portal-verification warning before any real pursuit action.

## Verification

Expected:

- `run_daily.ps1` completes using the local monitor script.
- The external monitor state file remains preserved.
- Duplicate tender IDs are skipped unless `-IncludeSeen` is used.
- New relevant tenders, if any, are imported as YAML briefs.

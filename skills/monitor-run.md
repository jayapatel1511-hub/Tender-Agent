# Monitor Run

Purpose: run Nova Scotia tender discovery and generate current active tender inputs.

## Preferred Command

```powershell
.\scripts\run_daily.ps1
```

## Direct Fallback

```powershell
C:\Users\jpate\.codex\skills\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1 `
  -ProposalRepo "C:\Users\jpate\Tender-Agent" `
  -State "C:\Users\jpate\.codex\skills\ns-tender-monitor\references\seen_tenders_state.json"
```

## Rules

- Preserve the state file. Do not delete or reset `seen_tenders_state.json`.
- Treat `proposals\active\ns-tenders\` as the current active tender brief folder.
- Treat `proposals\outputs\ns-tenders\ns-tender-monitor-*.json` as monitor summary output.
- Use `-DryRun` only when checking behavior without updating state.

## Output

Report command used, summary path, match count, generated briefs, and errors.

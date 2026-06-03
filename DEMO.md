# Tender Agent Demo

This demo shows the standalone tender workflow: monitor Nova Scotia public tender data, import consulting-fit opportunities, and run local pursuit review over cached tender briefs.

## Demo Flow

1. Build and test.

```powershell
dotnet build TenderAgent.sln
dotnet test TenderAgent.sln
```

2. Import a captured Nova Scotia monitor snapshot into a temporary folder.

```powershell
dotnet run --project dotnet\ProposalAgent.Cli\ProposalAgent.Cli.csproj -- import-ns-monitor proposals\outputs\ns-tenders\monitor-snapshots\ns-tender-monitor-20260602-184442.json --out-dir $env:TEMP\tender-agent-import-smoke
```

3. Run brain reports over the active tender briefs.

```powershell
dotnet run --project dotnet\ProposalAgent.Cli\ProposalAgent.Cli.csproj -- brain proposals\active\ns-tenders --out-dir proposals\outputs\v1-demo
```

4. Optionally attempt live Nova Scotia portal discovery with fallback.

```powershell
dotnet run --project dotnet\ProposalAgent.Cli\ProposalAgent.Cli.csproj -- watch-ns-live --fallback proposals\outputs\ns-tenders\monitor-snapshots\ns-tender-monitor-20260602-184442.json --out $env:TEMP\tender-agent-live-smoke.json
```

5. Launch the desktop shell.

```powershell
dotnet run --project dotnet\ProposalAgent.Desktop\ProposalAgent.Desktop.csproj
```

## What To Show

- Active tender YAML briefs in `proposals/active/ns-tenders`.
- Captured monitor snapshots in `proposals/outputs/ns-tenders/monitor-snapshots`.
- Four consultant-fit opportunities narrowed from broader portal findings.
- Markdown analyses and email payloads prepared for review.
- Document-backed compliance review where local extracts are attached.
- Explicit portal-verification warning before any real pursuit action.

## Verification

```powershell
dotnet test TenderAgent.sln
dotnet run --project dotnet\ProposalAgent.Cli\ProposalAgent.Cli.csproj -- import-ns-monitor proposals\outputs\ns-tenders\monitor-snapshots\ns-tender-monitor-20260602-184442.json --out-dir $env:TEMP\tender-agent-import-smoke
dotnet run --project dotnet\ProposalAgent.Cli\ProposalAgent.Cli.csproj -- brain proposals\active\ns-tenders --out-dir proposals\outputs\v1-demo
```

Expected:

- .NET tests pass.
- Import smoke writes four tender YAML briefs.
- Brain command writes/refreshes four active tender review reports.

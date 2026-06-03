# Tender Agent

Tender Agent is the standalone tender-monitoring and pursuit-intake repo. It currently focuses on the Nova Scotia Procurement Portal workflow:

- fetch or fall back to captured tender monitor JSON
- filter for professional-services / consulting-fit opportunities
- import matching public notices into structured YAML tender briefs
- run deterministic proposal-brain review over cached tenders
- keep generated analyses, email payloads, monitor snapshots, and run logs organized

This repo is separate from `C:\Users\jpate\Proposal-Agents-`. Proposal Agent is the reusable proposal-analysis workspace; Tender Agent is the tender source, screening, and intake workflow.

## Quick Start

```powershell
dotnet build TenderAgent.sln
dotnet test TenderAgent.sln
```

Run the tender brain over active Nova Scotia tender briefs:

```powershell
dotnet run --project dotnet\ProposalAgent.Cli\ProposalAgent.Cli.csproj -- brain proposals\active\ns-tenders --out-dir proposals\outputs\v1-demo
```

Try live Nova Scotia tender discovery, with a captured fallback snapshot:

```powershell
dotnet run --project dotnet\ProposalAgent.Cli\ProposalAgent.Cli.csproj -- watch-ns-live --fallback proposals\outputs\ns-tenders\monitor-snapshots\ns-tender-monitor-20260602-184442.json --analyze
```

Import a captured monitor snapshot into active tender YAML:

```powershell
dotnet run --project dotnet\ProposalAgent.Cli\ProposalAgent.Cli.csproj -- import-ns-monitor proposals\outputs\ns-tenders\monitor-snapshots\ns-tender-monitor-20260602-184442.json --out-dir proposals\active\ns-tenders
```

Launch the desktop review shell:

```powershell
dotnet run --project dotnet\ProposalAgent.Desktop\ProposalAgent.Desktop.csproj
```

## Repo Layout

```text
dotnet/
  ProposalAgent.Core/        Tender cache, NS watcher/importer, proposal brain support
  ProposalAgent.Cli/         CLI commands for watch/import/brain/extract
  ProposalAgent.Desktop/     Local tender review shell
  ProposalAgent.Core.Tests/  .NET tests
knowledge/
  people.yaml                Demo roster used for tender team-fit review
  company_structure.yaml     Demo operating-centre/company rules
proposals/
  active/ns-tenders/         Current tender YAML briefs
  documents/ns-tenders/      Local tender document extracts
  outputs/ns-tenders/        Tender workflow evidence by artifact type
  outputs/v1-demo/           Brain report outputs
docs/
  *.md                       Supporting org and workflow notes
```

## Tender Output Structure

```text
proposals/outputs/ns-tenders/
  analyses/           Markdown analysis for active tender briefs
  monitor-snapshots/  Captured or live monitor JSON snapshots
  email-briefs/       Human-readable email brief drafts
  email-payloads/     JSON payloads prepared for email automation
  run-logs/           Automation run logs and smoke evidence
```

## Current Active Opportunities

- `TOK202614` Stormwater Management Project Feasibility and Design Study.
- `RFP-MCC-2608` Maccan Wastewater Treatment Plant System Assessment Report.
- `PROJECT2608-1485` French River Hydraulic and Assimilative Capacity Study.
- `INF18-2026-2027` Sludge Holding Tank Design.

Always verify scope, addenda, closing date, mandatory meetings, submission rules, and eligibility directly in the Nova Scotia Procurement Portal before acting.

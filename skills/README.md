# Tender Agent Run Skills

These repo-level skill notes define the staged agent workflow for Tender Agent runs. They are plain Markdown handoff contracts for agents working in this repo.

Use them in order:

1. [repo-refresh.md](repo-refresh.md)
2. [monitor-run.md](monitor-run.md)
3. [duplicate-review.md](duplicate-review.md)
4. [opportunity-triage.md](opportunity-triage.md)
5. [email-handoff.md](email-handoff.md)
6. [run-log.md](run-log.md)

The local Codex skill script used by this repo remains:

```text
C:\Users\jpate\.codex\skills\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1
```

Keep `seen_tenders_state.json` outside the repo so duplicate-prevention survives repo cleanup and commits.

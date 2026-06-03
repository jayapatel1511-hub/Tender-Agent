# Tender Agent Run Skills

These repo-level skill notes define the staged agent workflow for Tender Agent runs. They are plain Markdown handoff contracts for agents working in this repo.

The domain focus is Englobe-relevant civil, municipal, and transportation engineering work. Normal qualified-opportunity emails should focus on municipal streets, roads, highways, corridors, intersections, active transportation, traffic, transit, and related planning or design studies. Generic consulting and supplier-style tenders are off-profile unless there is a clear civil/municipal/transportation angle.

Use [../docs/service-area-explainer.md](../docs/service-area-explainer.md) whenever the agent is confused about domain or service-area fit. The explainer is the domain-first triage guide; keyword lists are only discovery helpers.

Use them in order:

1. [repo-refresh.md](repo-refresh.md)
2. [monitor-run.md](monitor-run.md)
3. [duplicate-review.md](duplicate-review.md)
4. [opportunity-triage.md](opportunity-triage.md)
5. [email-handoff.md](email-handoff.md)
6. [run-log.md](run-log.md)

Use [test-prompts.md](test-prompts.md) after changing criteria or triage rules.

The monitor script used by this repo is local:

```text
tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1
```

Keep `data\seen_tenders_state.json` in the repo so duplicate prevention is visible and portable with this workflow.

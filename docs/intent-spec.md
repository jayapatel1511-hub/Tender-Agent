# Tender Agent Intent Spec

Purpose: define what this repo is meant to do, what the agent-run prompt should accomplish, and what remains for fully autonomous daily operation.

## Product Intent

Tender Agent is a local-first pursuit-intake workflow for Nova Scotia public tenders. It should help find civil, municipal, transportation, water, wastewater, stormwater, planning, design, study, assessment, and engineering-services opportunities that may be relevant to company pursuit work.

The system should not behave like a generic tender search. It must collect all open tenders first, then reason about domain and service-area fit before deciding what deserves action.

## Current Operating Intent

The current workflow is an agent-run workflow. A human or agent starts the run, then the repo scripts and connected tools handle the workflow.

Expected behavior:

1. Verify git/repo state without overwriting local work.
2. Run live Nova Scotia tender discovery using `scripts\run_daily.ps1`.
   This collects the Nova Scotia Procurement Portal and public MERX Nova Scotia
   tender summary pages by default.
3. Collect every currently `OPEN` tender before filtering.
4. Persist the full all-open-tender database locally.
5. Triage collected tenders using criteria plus domain reasoning.
6. Preserve duplicate-prevention state.
7. Generate active YAML briefs only for newly matched prime-fit tenders.
8. Write a public-safe Notion upsert payload after every Tier 2 run.
9. Email the user only when newly matched relevant tenders are found.
10. Write a local run log with counts, paths, sync status, and errors.

## Data Intent

The repo keeps local evidence so each run can be audited later.

Primary local data:

- `data\open-tenders\open-tenders-latest.json`: latest all-open-tender database.
- `data\open-tenders\runs\open-tenders-YYYYMMDD-HHMMSS.json`: per-run all-open-tender snapshots.
- `data\tender-agent.sqlite`: generated local SQLite history store for runs,
  tenders, snapshots, triage results, and sync logs.
- `data\seen_tenders_state.json`: duplicate-prevention state for emitted prime-fit tenders.
- `proposals\active\ns-tenders\`: current active tender briefs.
- `proposals\outputs\ns-tenders\run-logs\`: run evidence.

The JSON database is intentionally human-readable and remains the handoff/export
format. SQLite is the durable local history store so snapshots, triage decisions,
Notion sync results, and email outcomes can grow without making JSON the only
database.

## Triage Intent

Triage must be domain-first, not keyword-first.

Use `docs\service-area-explainer.md` before making final skip/keep decisions. Keywords are discovery signals only. A tender should be kept for review when the asset/domain is relevant even if the exact target keyword is absent.

Primary buckets:

- `prime-consultant-fit`: direct professional-services opportunity.
- `partner-or-subconsultant-fit`: contractor-led or adjacent work where engineering support may be useful.
- `needs-review`: relevant domain is plausible but service role is unclear.
- `off-profile-consulting`: consulting work outside the target engineering/public-infrastructure domain.
- `likely-skip`: goods, equipment, supplier, vendor, construction-only, or unrelated work.

## Notion Intent

Notion is the pursuit tracker, not the raw evidence store.

Source config:

- `config\notion-tracker.json`
- Database: `Tender Tracker`
- Dedupe key: `Tender ID`

Sync only public-safe fields:

- Tender ID
- Opportunity
- Procurement Entity
- Closing Date
- Portal URL
- Pursuit Type
- Bid Fit
- Priority
- Status
- Next Action
- Last Checked

Do not sync raw internal context, company strategy, redaction maps, private proposal material, or non-public pursuit notes.

## Email Intent

Email is a concise alert channel, not the database.

Send email only when a run finds newly matched relevant tenders that are not duplicates. The email must contain public-safe briefs and public links only.

Default recipient:

```text
jpatel1511@outlook.com
```

Default subject:

```text
New Tender Opportunities - YYYY-MM-DD
```

If no new relevant tenders are found, do not email unless there is an error that needs attention.

## Privacy Intent

The system must keep raw client/company/proposal material local. Optional LLM or connector steps should receive only public-safe or redacted context.

Never send externally:

- internal roster or staffing notes
- company strategy
- private proposal content
- redaction maps
- non-public pursuit assumptions
- raw local run internals that are not needed for user-facing action

## Automation Intent

There are two distinct automation levels.

### Current Level: Agent-Run Automation

This is working now. The agent can run the prompt, execute the local monitor,
triage the stored snapshot, create public-safe Notion upsert payloads, decide
whether email payloads are needed, and report results.

### Target Level: Fully Unattended Daily Automation

This is not complete yet. To make the system run every day without Codex intervention, add:

1. A Windows Scheduled Task or persistent runner.
2. A repo-local Notion sync mechanism or durable connector runner.
3. A repo-local email send mechanism or durable connector runner.
4. A scheduled-run log that records external sync/email outcomes.
5. A verification routine proving scheduled runs work when Codex is not open.

## SQLite Intent

SQLite is the local system of record for history and queryability. JSON remains
the easy-to-read export.

Generated database:

```text
data\tender-agent.sqlite
```

Tracked schema:

```text
db\schema.sql
```

Core tables:

- `runs`
- `tenders`
- `open_tender_snapshots`
- `triage_results`
- `notion_sync_log`
- `email_log`

Generated SQLite files should not be committed. Schema and migration scripts
should be committed.

## Success Criteria

The workflow is healthy when:

- every run stores all open tenders before filtering
- duplicate state is preserved
- known target-domain items are not lost because of narrow keyword matching
- obvious goods/equipment false positives stay out of action buckets
- Notion is updated after every run
- email is sent only for newly matched relevant tenders
- run logs contain enough evidence to explain what happened
- local and external outputs contain only public-safe data

# Tender Agent — Implementation Plan

Companion to `docs/workflow.md` (the spec). This is the actionable build plan:
phased, file-level, with acceptance checks. Work top to bottom; each phase is
shippable on its own.

Decisions locked: **agent judges each run · enrich every tender · two-tier run
model (cron collects, scheduled agent triages) · SQLite is the growing history
store while JSON remains the inspectable exchange format.**

---

## Phase 0 — Baseline & safety (before changing anything)

- [x] Confirm repo status and commit current state as a restore point.
      (This repo is already initialized and tracks `origin/main`; do not run
      `git init`.)
- [x] Snapshot the current `open-tenders-latest.json` to compare before/after.
- [x] Note current real run params: `run_daily.ps1` already uses
      `-PageSize 100 -MaxPages 80` (so all 211 are fetched) and
      `min_days_until_close: 0`. The `--max-pages 2` concern only applies to
      direct calls of the monitor, not the daily wrapper.

**Acceptance:** a clean restore point exists; we know exactly what today's output
looks like.

---

## Phase 1 — Tier 1: gut the collector to a raw mirror

File: `tools/ns-tender-monitor/scripts/Invoke-NsTenderMonitor.ps1`

- [x] Remove judgment functions: `Test-TenderMatch`,
      `Get-OpportunityClassification`, `Get-CandidateBucket`.
- [x] In the page loop, drop the keyword gate, the `min_days_until_close` drop,
      and the seen-state skip. Collect **every** `OPEN` tender.
- [x] Fetch the detail page for **every** tender (not only ones that passed a
      gate). Merge detail into the record so `description` is always present.
- [x] Rewrite `New-OpenTenderRecord` to emit raw fields only — remove
      `triage_bucket`, `match_reasons`, `pursuit_type`, `bid_fit`,
      `classification_*`. Keep: `tender_id, title, status, solicitation_type,
      procurement_entity, end_user_entity, post_date, closing_date, description,
      portal_url, last_seen_at, source, raw`.
- [x] Remove `candidate_bucket_counts` from the snapshot payload (it is a
      judgment artifact). Keep `ran_at`, `source`, `open_tender_count`,
      `tenders`.
- [x] Move brief-writing (`Write-TenderBrief`) out of the collector — Tier 1 no
      longer decides matches. (Briefs become a Tier 2 output; park the function
      or delete it here.)
- [x] Keep `data/seen_tenders_state.json` untouched by the collector (state
      belongs to Tier 2).
- [x] Retire `tools/ns-tender-monitor/scripts/ns_tender_monitor.py` — rename to
      `ns_tender_monitor.py.parked` or move to an `archive/` folder so there is
      one collector.

**Acceptance:**
- `open-tenders-latest.json` contains all open tenders, each with a non-empty
  `description`, and **no** opinion fields anywhere.
- Re-running the collector twice yields the same tender set (idempotent mirror).
- `run_daily.ps1` still runs end to end (it will just produce a raw snapshot and
  no matches until Tier 2 exists).

---

## Phase 2 — Interests profile (single source of truth)

File: `config/targeted-stream-criteria.json` (+ `docs/service-area-explainer.md`)

- [x] Reframe the file from gate-keywords to an **interests profile**: domain
      taxonomy (asset types, service roles, target buyers) plus `surface_hints`
      (keywords that *prioritize* review) and `noise_hints` (keywords that
      *deprioritize*, never exclude).
- [x] Decide naming: keep `targeted-stream-criteria.json` with new semantics, or
      rename to `interests-profile.json`. Update references in `run_daily.ps1`,
      `Invoke-NsTenderMonitor.ps1`, skills, and docs.
- [x] Add a `criteria_version` string so triage output can record which profile
      it used.
- [x] Ensure the collector no longer reads this file at all (it is Tier 2 only).

**Acceptance:** the profile reads as "what we care about," not "what to delete";
exactly one file defines relevance; nothing in Tier 1 consumes it.

---

## Phase 3 — Tier 2: triage artifact + the agent as judge

Files: `skills/opportunity-triage.md`, new `data/triage/triage-latest.json`,
new triage run prompt/skill.

- [x] Define the triage artifact schema in `data/triage/triage-latest.json`:
      `ran_at, snapshot_path, criteria_version, results[]` where each result is
      `tender_id, bucket, pursuit_type, bid_fit, confidence, reason, next_action,
      urgent, triaged_at`.
- [x] Update `opportunity-triage.md` to be the operating judge: input is the raw
      snapshot + interests profile; output is the triage artifact. Add the
      domain-first test as the decision path and keywords as hints only.
- [x] Add an explicit **re-triage mode**: judge an existing snapshot without
      re-scraping (used when the profile changes).
- [x] Add a triage run prompt/skill (e.g. `skills/triage-run.md`) that the agent
      executes: read latest snapshot → judge → write `triage-latest.json`.
- [x] Sanity check against last week's miss list (INF18, MOCR202607, 2627-04,
      T11-2026, P05-2026, PROJECT2601-2524, CBRM-P03/P02, PROJECT2504-1504):
      these must land in `prime-consultant-fit` / `partner-or-subconsultant-fit`
      / `needs-review`, not `likely-skip`.

**Acceptance:** running triage over a stored snapshot produces a complete,
explained `triage-latest.json`; the known misses are recovered; re-running with
a tweaked profile changes results without any portal calls.

---

## Phase 4 — SQLite history store (JSON stays as export)

Files: `db/schema.sql`, `scripts/initialize_database.py`, local generated
database `data/tender-agent.sqlite`.

- [x] Treat JSON snapshots as human-readable exports and handoff artifacts, not
      the only long-term store.
- [x] Add a SQLite schema for `runs`, `tenders`, `open_tender_snapshots`,
      `triage_results`, `notion_sync_log`, and `email_log`.
- [x] Add a repo-local initializer that creates/updates
      `data/tender-agent.sqlite` from the tracked schema.
- [x] Ignore generated SQLite files in git (`*.sqlite`, `*.sqlite-wal`,
      `*.sqlite-shm`) while tracking schema/migration files.
- [x] After Tier 1 runs, upsert tender facts and snapshot membership into
      SQLite while still writing `open-tenders-latest.json`.
- [x] After Tier 2 runs, write triage results to SQLite while still writing
      `data/triage/triage-latest.json`.

**Acceptance:** the database can be initialized from a clean checkout; repeated
runs append run/snapshot/triage history without duplicating tender identities;
JSON outputs remain available for inspection and agent handoff.

---

## Phase 5 — Downstream: Notion, email, briefs (off the triage artifact)

- [x] Notion payload: write public-safe upsert rows keyed by `Tender ID` from
      `triage-latest.json`.
- [ ] Notion live sync: upsert by `Tender ID` (update existing rows, do not
      append duplicates). Public-safe fields only per `intent-spec.md`.
- [x] Email payload: create public-safe email briefs/payloads only for newly
      matched relevant tenders after dedupe against `seen_tenders_state.json`.
- [x] Email live send/draft handoff: send or create a Gmail draft only when the
      latest run has new relevant tenders; no email when nothing new (except on
      error).
- [x] Briefs: write YAML under `proposals/active/ns-tenders/` only for
      `prime-consultant-fit` tenders, driven by triage output.
- [x] Update `seen_tenders_state.json` here (Tier 2 owns state).
- [x] Run log records counts, paths, Notion/email outcomes, and errors.

**Acceptance:** a triage run updates Notion in place, emails or drafts only new
fits, and writes briefs for prime fits; re-runs keep Notion stable.

---

## Phase 6 — Scheduling (two tiers)

- [x] Tier 1 cron: register the collector as a Windows Scheduled Task via
      `Register-NsTenderMonitorTask.ps1`, daily, headless. No LLM.
- [x] Tier 2 agent routine: schedule a daily agent run that triages the latest
      snapshot and runs downstream. (Needs an LLM/agent, not a plain cron.)
- [ ] Verify both fire on schedule and leave evidence in run logs when the agent
      is not interactively open.

**Acceptance:** raw data refreshes daily on its own; triage + tracking + alerts
fire on schedule; logs prove unattended runs worked.

---

## Phase 7 — Docs & cleanup

- [x] Make the two-tier model explicit in `docs/intent-spec.md`.
- [x] Update `docs/agent_flow.md` if any stage names drift from the build.
- [x] Refresh `tools/ns-tender-monitor/SKILL.md` to describe collect-only.
- [x] Update `skills/monitor-run.md` / `README.md` to point collect → triage.
- [x] Remove or update `tools/ns-tender-monitor/references/default_criteria.json`
      (stale keyword gate; the live profile is the config file).

**Acceptance:** docs match the built workflow; no stale gate-criteria files
mislead a future run.

---

## Open items to resolve in-flight

1. Triage store: local `triage-latest.json` **and** Notion (default: both).
2. Interests profile filename: keep vs rename (Phase 2).
3. Live Notion upsert remains connector-dependent: the repo writes the payload,
   but the current Notion SQL query tool failed at runtime, so full automatic
   update-vs-create proof is still pending.
4. SQLite migration style after v1: single `db/schema.sql` is enough now; move
   to timestamped migrations only when schema churn starts.
5. Logged-off Windows scheduling: current tasks are registered as `Interactive`
   because `S4U` registration returned access denied on this machine. Tier 2 has
   a successful scheduled run; Tier 1 has direct-run proof and scheduled failure
   logs when the portal rejects guest authentication.
6. Email handoff is complete for the current run state: latest Tier 2 log has
   `new_relevant_count: 0`, `email_decision: no-new-relevant-tenders`, and no
   email draft/payload files were generated.

## Suggested commit boundaries

1. `docs: add workflow blueprint + implementation plan` (this + workflow.md)
2. `collector: reduce Tier 1 to a raw, fully-enriched mirror`
3. `config: reframe criteria as an interests profile`
4. `triage: add triage artifact + agent-as-judge`
5. `db: add sqlite history store`
6. `downstream: drive Notion/email/briefs from triage output`
7. `ops: schedule Tier 1 cron and Tier 2 agent routine`

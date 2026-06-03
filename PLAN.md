# Tender Agent — Implementation Plan

Companion to `docs/workflow.md` (the spec). This is the actionable build plan:
phased, file-level, with acceptance checks. Work top to bottom; each phase is
shippable on its own.

Decisions locked: **agent judges each run · enrich every tender · two-tier run
model (cron collects, scheduled agent triages).**

---

## Phase 0 — Baseline & safety (before changing anything)

- [ ] Confirm repo status and commit current state as a restore point.
      (This repo is already initialized and tracks `origin/main`; do not run
      `git init`.)
- [ ] Snapshot the current `open-tenders-latest.json` to compare before/after.
- [ ] Note current real run params: `run_daily.ps1` already uses
      `-PageSize 100 -MaxPages 80` (so all 211 are fetched) and
      `min_days_until_close: 0`. The `--max-pages 2` concern only applies to
      direct calls of the monitor, not the daily wrapper.

**Acceptance:** a clean restore point exists; we know exactly what today's output
looks like.

---

## Phase 1 — Tier 1: gut the collector to a raw mirror

File: `tools/ns-tender-monitor/scripts/Invoke-NsTenderMonitor.ps1`

- [ ] Remove judgment functions: `Test-TenderMatch`,
      `Get-OpportunityClassification`, `Get-CandidateBucket`.
- [ ] In the page loop, drop the keyword gate, the `min_days_until_close` drop,
      and the seen-state skip. Collect **every** `OPEN` tender.
- [ ] Fetch the detail page for **every** tender (not only ones that passed a
      gate). Merge detail into the record so `description` is always present.
- [ ] Rewrite `New-OpenTenderRecord` to emit raw fields only — remove
      `triage_bucket`, `match_reasons`, `pursuit_type`, `bid_fit`,
      `classification_*`. Keep: `tender_id, title, status, solicitation_type,
      procurement_entity, end_user_entity, post_date, closing_date, description,
      portal_url, last_seen_at, source, raw`.
- [ ] Remove `candidate_bucket_counts` from the snapshot payload (it is a
      judgment artifact). Keep `ran_at`, `source`, `open_tender_count`,
      `tenders`.
- [ ] Move brief-writing (`Write-TenderBrief`) out of the collector — Tier 1 no
      longer decides matches. (Briefs become a Tier 2 output; park the function
      or delete it here.)
- [ ] Keep `data/seen_tenders_state.json` untouched by the collector (state
      belongs to Tier 2).
- [ ] Retire `tools/ns-tender-monitor/scripts/ns_tender_monitor.py` — rename to
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

- [ ] Reframe the file from gate-keywords to an **interests profile**: domain
      taxonomy (asset types, service roles, target buyers) plus `surface_hints`
      (keywords that *prioritize* review) and `noise_hints` (keywords that
      *deprioritize*, never exclude).
- [ ] Decide naming: keep `targeted-stream-criteria.json` with new semantics, or
      rename to `interests-profile.json`. Update references in `run_daily.ps1`,
      `Invoke-NsTenderMonitor.ps1`, skills, and docs.
- [ ] Add a `criteria_version` string so triage output can record which profile
      it used.
- [ ] Ensure the collector no longer reads this file at all (it is Tier 2 only).

**Acceptance:** the profile reads as "what we care about," not "what to delete";
exactly one file defines relevance; nothing in Tier 1 consumes it.

---

## Phase 3 — Tier 2: triage artifact + the agent as judge

Files: `skills/opportunity-triage.md`, new `data/triage/triage-latest.json`,
new triage run prompt/skill.

- [ ] Define the triage artifact schema in `data/triage/triage-latest.json`:
      `ran_at, snapshot_path, criteria_version, results[]` where each result is
      `tender_id, bucket, pursuit_type, bid_fit, confidence, reason, next_action,
      urgent, triaged_at`.
- [ ] Update `opportunity-triage.md` to be the operating judge: input is the raw
      snapshot + interests profile; output is the triage artifact. Add the
      domain-first test as the decision path and keywords as hints only.
- [ ] Add an explicit **re-triage mode**: judge an existing snapshot without
      re-scraping (used when the profile changes).
- [ ] Add a triage run prompt/skill (e.g. `skills/triage-run.md`) that the agent
      executes: read latest snapshot → judge → write `triage-latest.json`.
- [ ] Sanity check against last week's miss list (INF18, MOCR202607, 2627-04,
      T11-2026, P05-2026, PROJECT2601-2524, CBRM-P03/P02, PROJECT2504-1504):
      these must land in `prime-consultant-fit` / `partner-or-subconsultant-fit`
      / `needs-review`, not `likely-skip`.

**Acceptance:** running triage over a stored snapshot produces a complete,
explained `triage-latest.json`; the known misses are recovered; re-running with
a tweaked profile changes results without any portal calls.

---

## Phase 4 — Downstream: Notion, email, briefs (off the triage artifact)

- [ ] Notion sync: upsert by `Tender ID` (update existing rows, do not append
      duplicates). Public-safe fields only per `intent-spec.md`. Source the rows
      from `triage-latest.json`.
- [ ] Email: send only newly matched relevant tenders (dedup against
      `seen_tenders_state.json`); public-safe briefs and links only; no email
      when nothing new (except on error).
- [ ] Briefs: write YAML under `proposals/active/ns-tenders/` only for
      `prime-consultant-fit` tenders, driven by triage output.
- [ ] Update `seen_tenders_state.json` here (Tier 2 owns state).
- [ ] Run log records counts, paths, Notion/email outcomes, and errors.

**Acceptance:** a triage run updates Notion in place, emails only new fits, and
writes briefs for prime fits; re-runs keep Notion stable.

---

## Phase 5 — Scheduling (two tiers)

- [ ] Tier 1 cron: register the collector as a Windows Scheduled Task via
      `Register-NsTenderMonitorTask.ps1`, daily, headless. No LLM.
- [ ] Tier 2 agent routine: schedule a daily agent run that triages the latest
      snapshot and runs downstream. (Needs an LLM/agent, not a plain cron.)
- [ ] Verify both fire on schedule and leave evidence in run logs when the agent
      is not interactively open.

**Acceptance:** raw data refreshes daily on its own; triage + tracking + alerts
fire on schedule; logs prove unattended runs worked.

---

## Phase 6 — Docs & cleanup

- [ ] Make the two-tier model explicit in `docs/intent-spec.md`.
- [ ] Update `docs/agent_flow.md` if any stage names drift from the build.
- [ ] Refresh `tools/ns-tender-monitor/SKILL.md` to describe collect-only.
- [ ] Update `skills/monitor-run.md` / `README.md` to point collect → triage.
- [ ] Remove or update `tools/ns-tender-monitor/references/default_criteria.json`
      (stale keyword gate; the live profile is the config file).

**Acceptance:** docs match the built workflow; no stale gate-criteria files
mislead a future run.

---

## Open items to resolve in-flight

1. Triage store: local `triage-latest.json` **and** Notion (default: both).
2. Interests profile filename: keep vs rename (Phase 2).
3. Notion upsert semantics confirmed before first scheduled run (Phase 4).
4. Where git version control should live (Phase 0).

## Suggested commit boundaries

1. `docs: add workflow blueprint + implementation plan` (this + workflow.md)
2. `collector: reduce Tier 1 to a raw, fully-enriched mirror`
3. `config: reframe criteria as an interests profile`
4. `triage: add triage artifact + agent-as-judge`
5. `downstream: drive Notion/email/briefs from triage output`
6. `ops: schedule Tier 1 cron and Tier 2 agent routine`

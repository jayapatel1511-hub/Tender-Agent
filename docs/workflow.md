# Tender Agent Workflow (Target Design)

This is the blueprint we build to. It supersedes the fused collect-and-triage
behavior currently in the scripts. Read alongside `intent-spec.md`,
`agent_flow.md`, `service-area-explainer.md`, and `skills/opportunity-triage.md`.

## Design Decisions

Three decisions fix the architecture and resolve the misclassification problem
where civil/municipal/transportation tenders were dropped to `likely-skip` by a
keyword gate before any reasoning happened.

1. **Judgment owner: the agent, each run.** A daily agent run makes the
   keep/skip/bucket call using domain-first reasoning. Keywords are only a
   sort/surface hint, never a gate.
2. **Enrichment: everything.** The collector fetches the detail page for every
   open tender. The raw database is always complete, so any tender can be
   re-judged later with full context.
3. **Run model: two tiers.** A headless cron keeps the raw data fresh; a
   scheduled agent run does the judging, tracking, and alerting.

## Core Principle

There are two kinds of work, and they must stay separate:

- **DATA** — what tenders are open, in full. Dumb, factual, no opinions.
- **JUDGMENT** — which ones matter and how. All opinions live here, in one place.

> Collect everything raw. Judge in one place. Never let a keyword delete a
> tender — only sort it.

## Two-Tier Architecture

```
TIER 1 — DATA (headless cron, no LLM, always-on)
  NS portal + MERX ─▶ collect ─▶ open-tenders-latest.json
                          (raw mirror: all open, all detail-enriched, zero opinions)

TIER 2 — JUDGMENT (scheduled agent run)
  open-tenders-latest.json ─▶ [agent: domain-first triage] ─▶ triage-latest.json
                                                            ├─▶ Notion sync (public-safe)
                                                            ├─▶ email (new relevant only)
                                                            └─▶ prime-fit YAML briefs
```

### Tier 1 — Collector (dumb, deterministic)

Responsibilities:

- Authenticate to the Nova Scotia procurement portal as guest.
- Page through **every** currently `OPEN` tender (no `--max-pages` cap that
  truncates the list).
- Fetch the **detail page for every** tender.
- Fetch public MERX Nova Scotia/category/search summary pages and normalize
  notices into the same raw record schema with `MERX-` prefixed IDs.
- Write a raw snapshot. No keyword gate, no `min_days_until_close` drop, no
  seen-state filtering. A mirror includes everything currently open.

Must **not** contain any of: keyword include/exclude gating, opportunity
classification, candidate bucketing, or opinion fields. Those move to Tier 2.

Outputs:

- `data/open-tenders/open-tenders-latest.json` — latest raw mirror.
- `data/open-tenders/runs/open-tenders-YYYYMMDD-HHMMSS.json` — per-run snapshot.

Scheduling: Windows Scheduled Task via `Register-NsTenderMonitorTask.ps1`.
Use `-SkipMerx` for a portal-only run if MERX is unavailable, rate-limited, or
temporarily too slow.

#### Raw snapshot record schema

Opinion fields (`triage_bucket`, `match_reasons`, `pursuit_type`, `bid_fit`,
`classification_*`) are **removed**. Each record keeps only facts:

```
tender_id
title
status
solicitation_type
procurement_entity
end_user_entity
post_date
closing_date
description          # from the detail page (now always fetched)
portal_url
last_seen_at
source
raw                 # full portal payload for audit / re-triage
```

### Tier 2 — Triage (agent, domain-first)

Responsibilities:

1. Read the latest raw snapshot.
2. Read the **interests profile** (the reframed criteria file) and
   `service-area-explainer.md` as context.
3. Apply `skills/opportunity-triage.md` domain-first reasoning to assign a
   bucket and fit per tender. Keywords surface candidates; the asset + service
   role + buyer combination decides.
4. Write `data/triage/triage-latest.json` (new artifact).
5. Dedup against `data/seen_tenders_state.json` (only for emitted/tracked items).
6. Sync to Notion `Tender Tracker` (public-safe fields; update by `Tender ID`).
7. Email only newly matched relevant tenders.
8. Write prime-fit YAML briefs under `proposals/active/ns-tenders/`.
9. Write a run log.

Re-triage mode: because Tier 1 preserves complete raw data, Tier 2 can be re-run
over an existing snapshot when the interests profile changes — no re-scrape, no
data loss.

Scheduling: a daily agent routine (the judgment layer needs an LLM, so it cannot
be a plain cron).

#### Triage artifact schema (`triage-latest.json`)

```
ran_at
snapshot_path            # which raw snapshot was judged
criteria_version         # which interests profile was used
results:
  - tender_id
    bucket               # prime-consultant-fit | partner-or-subconsultant-fit |
                         #   needs-review | off-profile-consulting | likely-skip
    pursuit_type
    bid_fit
    confidence
    reason               # why, in domain terms (asset + role + buyer)
    next_action
    urgent               # true when strong fit but closing soon
    triaged_at
```

## Buckets

Unchanged from `intent-spec.md`:

- `prime-consultant-fit` — direct professional-services opportunity.
- `partner-or-subconsultant-fit` — contractor-led or adjacent; engineering
  support may be useful.
- `needs-review` — relevant domain plausible, service role unclear.
- `off-profile-consulting` — consulting outside the target domain.
- `likely-skip` — goods, equipment, supplier, vendor, construction-only, or
  unrelated.

A tender is only `likely-skip` after domain reasoning, never because a keyword
fired during collection.

## What Changes In The Repo

- `tools/ns-tender-monitor/scripts/Invoke-NsTenderMonitor.ps1` — gut the
  judgment code (`Test-TenderMatch`, `Get-OpportunityClassification`,
  `Get-CandidateBucket`) and the opinion fields; keep auth, paginate-all,
  detail-fetch-all, raw dump.
- `config/targeted-stream-criteria.json` — reframe from keyword gate to an
  interests/domain profile read by the agent. Single source of truth.
- `skills/opportunity-triage.md` — becomes the actual judge; add an explicit
  "re-triage from raw snapshot" mode.
- New: `data/triage/triage-latest.json` and a triage run prompt/skill.
- Retire `tools/ns-tender-monitor/scripts/ns_tender_monitor.py` (a duplicate
  collector with its own divergent logic) so there is one collector.
- `docs/intent-spec.md` — make the two-tier model explicit.

## Open Items (decide during build)

1. **Triage store:** keep both local `triage-latest.json` (audit + re-run fuel)
   and Notion (working view). Default: both.
2. **Interests profile naming:** keep `targeted-stream-criteria.json` with new
   semantics, or rename to `interests-profile.json`. To be decided.
3. **Notion on re-triage:** update existing rows by `Tender ID` rather than
   appending, to keep the tracker stable across re-runs.

## Build Order

1. Write this blueprint (done).
2. Tier 1: gut the collector to a raw mirror; remove the page cap; enrich all.
3. Tier 2: define the triage artifact and make `opportunity-triage.md` the judge.
4. Wire Notion sync / email / briefs off the triage artifact.
5. Scheduling: cron for Tier 1, agent routine for Tier 2.

## Success Criteria

- Every run stores all open tenders, fully enriched, with no opinions baked in.
- No target-domain tender is lost to keyword matching.
- Triage is re-runnable over a stored snapshot without re-scraping.
- Notion is updated after every triage run; rows are stable across re-runs.
- Email fires only for newly matched relevant tenders.
- Local and external outputs contain only public-safe data.

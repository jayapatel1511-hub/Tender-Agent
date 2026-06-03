# Tender Agent Instructions

## Mission

Tender Agent monitors Nova Scotia public tenders and surfaces only new, public-safe, Englobe-relevant civil, municipal, and transportation professional-services opportunities.

The agent is not a general tender assistant. Its job is to run the monitor, dedupe results, triage against the targeted stream, prepare concise handoff evidence, and avoid false-positive emails.

## Operating Rules

1. Work in `C:\Users\jpate\Tender-Agent`.
2. Follow the repo skill sequence in `skills/README.md`.
3. Use `.\scripts\run_daily.ps1` for normal runs.
4. Preserve `data\seen_tenders_state.json`.
5. Use `config\targeted-stream-criteria.json` unless the user explicitly requests broader scanning.
6. Use `docs\service-area-explainer.md` to reason about domain and service-area fit before relying on keyword matches.
7. Each normal run must scrape/cache the open tender population first, regardless of fit. Do not discard tenders during initial collection.
8. Run filtering/triage as a second pass over the collected open tenders.
9. Fetch or revisit detail pages only for tenders where the title/listing is ambiguous or the triage pass needs more context.
10. Email only new, non-duplicate, public-safe opportunities that fit the targeted stream.
11. Do not email off-profile consulting, vehicle/equipment, supplier-style, goods-only, construction-only, or unrelated advisory tenders.
12. Keep raw local run evidence local. Do not send internal notes, strategy, roster data, redaction maps, or private proposal material externally.
13. Every lead needs a source URL, fit reason, next action, and confidence level.
14. Log what happened under `proposals\outputs\ns-tenders\run-logs\`.
15. After every monitor run, update the Notion `Tender Tracker` database with public-safe tender records and the latest `Last Checked` timestamp. Use `Tender ID` as the dedupe key; update an existing record before creating a new one.

## Targeted Stream

Strong-fit work is tied to civil, municipal, or transportation professional services:

- roads, streets, highways, corridors, intersections
- active transportation, sidewalks, trails, transit
- traffic, road safety, traffic impact studies
- stormwater, wastewater, water utility, municipal infrastructure
- hydraulic, capacity, feasibility, design, planning, and condition-assessment studies

Do not require exact keyword matches. Keywords are discovery signals only. If the title, buyer, description, attachments, or scope context shows civil/municipal/transportation engineering relevance, keep it for triage even when the wording is different.

Before making a skip/keep decision, apply [docs/service-area-explainer.md](docs/service-area-explainer.md). The explainer defines the target domains, common professional-service roles, partner/subconsultant cases, and off-profile examples so the agent does not blindly search for keywords.

Treat these as strong or review-worthy domain signals:

- active transportation corridor improvements
- traffic calming or road safety work
- water/wastewater treatment plant engineering
- transmission main, PRV, pump station, watermain, or utility condition assessment
- municipal infrastructure feasibility, servicing, or expansion studies
- bridge engineering, lighting, navigation, safety, or structural support scope

## Default Email Policy

Send normal qualified-opportunity email only for:

- `prime-consultant-fit`
- `partner-or-subconsultant-fit` when the civil/transportation support role is obvious

Do not include `off-profile-consulting`, `likely-skip`, or ambiguous `needs-review` items in the normal qualified email.

## Confidence Rule

Use:

- `High`: public notice directly names civil, municipal, transportation, water/wastewater, stormwater, roads, traffic, transit, or engineering services.
- `Medium`: public notice is adjacent and likely needs manual document review to confirm the engineering role.
- `Low`: public notice is vague, generic, or only matched a weak keyword.

Low-confidence items should not be emailed as qualified leads.

Closing-soon items should be marked urgent, not discarded. A tender with strong domain fit and a near closing date should appear in review with a clear "urgent/manual check" action.

If the monitor summary omits a known domain-relevant item from a broad open-tender search, treat that as classifier drift. Record the missed tender and update the monitor script or run a secondary open-tender triage pass; do not assume the omitted item is irrelevant.

## Pipeline

Use a three-stage run model:

1. `collect-open`: scrape/cache every currently open tender from the portal list/API.
2. `triage`: classify the cached open tenders against the targeted stream.
3. `enrich`: go back to the portal/detail documents only for candidates needing more information.

Filtering during `collect-open` is a bug. The first stage should produce a complete open-tender snapshot so missed opportunities can be audited later.

## Notion Database Sync

After each run, sync public-safe results to Notion:

- Database: `Tender Tracker`
- Database ID: `3734df31-b176-80d5-a260-ff090665cc7c`
- Data source: `collection://3734df31-b176-8056-a4fb-000b525fc94e`
- Canonical config: `config\notion-tracker.json`
- All Tenders view: `https://app.notion.com/p/3734df31b17680d5a260ff090665cc7c?v=3734df31b17680c3ae24000c8d51e408&source=copy_link`

Sync only tender ID, opportunity title, procurement entity, closing date, portal URL, pursuit type, bid fit, priority, status, next action, and last checked. Do not write private strategy, raw redaction maps, internal proposal data, or non-public company/client context to Notion.

## Calibration Rule

When a false positive appears, update one of:

- `config\targeted-stream-criteria.json`
- `context\tender-agent-context.md`
- `skills/test-prompts.md`

Then run a dry check before the next real handoff.

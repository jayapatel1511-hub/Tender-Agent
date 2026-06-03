# Backlog

## Collect-Then-Triage Monitor Refactor

Status: implemented as a two-tier JSON + SQLite workflow. Remaining work is live scheduled-task proof and any future calibration from real review feedback.

Implemented behavior:

1. Fetch all currently open tenders from the Nova Scotia Procurement Portal.
2. Save a complete open-tender snapshot under `data\open-tenders\runs\` and refresh `data\open-tenders\open-tenders-latest.json`.
3. Import snapshots into `data\tender-agent.sqlite`.
4. Run Tier 2 triage against that snapshot and `config\targeted-stream-criteria.json`.
5. Produce candidate buckets:
   - `prime-consultant-fit`
   - `partner-or-subconsultant-fit`
   - `needs-review`
   - `off-profile-consulting`
   - `likely-skip`
6. Update duplicate state only for items that are emitted as relevant leads, not for every open tender.
7. Write prime-fit briefs, public-safe email payloads, public-safe Notion upsert payloads, and Tier 2 run logs.

Acceptance checks:

- `TOA2026-02ATCIMprovements` appears at least as `needs-review` or `partner-or-subconsultant-fit`.
- `HRM-2026-1029` appears at least as `needs-review` or `partner-or-subconsultant-fit`.
- CSR consulting remains `off-profile-consulting`.
- Vehicle/equipment RFQs remain `likely-skip`.
- Wastewater, stormwater, hydraulic, traffic, active transportation, and water treatment engineering remain eligible.

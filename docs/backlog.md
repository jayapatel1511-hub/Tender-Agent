# Backlog

## Collect-Then-Triage Monitor Refactor

Status: implemented for local JSON snapshots in `data\open-tenders\`. Remaining work is calibration and richer bucket review.

Implemented behavior:

1. Fetch all currently open tenders from the Nova Scotia Procurement Portal.
2. Save a complete open-tender snapshot under `data\open-tenders\runs\` and refresh `data\open-tenders\open-tenders-latest.json`.
3. Run targeted stream filtering against that snapshot.
4. Produce candidate buckets:
   - `prime-consultant-fit`
   - `partner-or-subconsultant-fit`
   - `needs-review`
   - `off-profile-consulting`
   - `likely-skip`
5. Fetch detail pages/documents only for candidates that need more context.
6. Update duplicate state only for items that are actually emitted as new/reviewed candidates, not for every open tender.
7. Log open tender count, bucket counts, summary path, and snapshot path.

Acceptance checks:

- `TOA2026-02ATCIMprovements` appears at least as `needs-review` or `partner-or-subconsultant-fit`.
- `HRM-2026-1029` appears at least as `needs-review` or `partner-or-subconsultant-fit`.
- CSR consulting remains `off-profile-consulting`.
- Vehicle/equipment RFQs remain `likely-skip`.
- Wastewater, stormwater, hydraulic, traffic, active transportation, and water treatment engineering remain eligible.

---
name: ns-tender-monitor
description: Monitor the Nova Scotia Procurement Portal for open public tenders, snapshot them locally, and filter them against the Tender Agent targeted-stream criteria.
---

# Nova Scotia Tender Monitor

Use this skill when the user wants to inspect, monitor, filter, or automate follow-up for Nova Scotia public tenders on `https://procurement-portal.novascotia.ca/tenders`, especially when design, study, assessment, planning, modelling, hydraulic, stormwater, wastewater, transportation, active transportation, traffic, or engineering-services opportunities should create local Tender Agent briefs.

## Workflow

1. Work from the Tender Agent repo root. Default:
   `C:\Users\jpate\Tender-Agent`
2. Use `tools/ns-tender-monitor/scripts/Invoke-NsTenderMonitor.ps1` or `scripts/run_daily.ps1` to fetch public tenders through the same guest-auth API flow used by the portal.
3. Collect currently open tenders first, then triage against `config/targeted-stream-criteria.json`. Keywords are discovery signals; domain relevance is the deciding factor.
4. Classify every matching tender before recommending action. Direct consultant-fit `design-study-consulting` tenders should become active findings by default:
   - `design-study-consulting`: likely prime consultant fit.
   - `construction-contractor-led`: not active by default; skip unless the user explicitly wants partner/subconsultant leads.
   - `mixed-consulting-and-delivery`: not active by default; review only when the user asks for broader scanning.
   - `supply-equipment-services`: skip unless acting as supplier/vendor.
   - `needs-review`: skip until enough public notice signal exists.
5. For each newly seen matching tender, write:
   - a YAML brief under `proposals/active/ns-tenders/`
   - a run summary JSON under `proposals/outputs/ns-tenders/`
6. Keep `data/seen_tenders_state.json` in place so future runs do not resend the same tender IDs.
7. If a known relevant tender is absent, treat that as classifier drift and update the repo criteria or monitor logic.

## Commands

Preview current matching tenders without updating state:

```powershell
.\tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1 -DryRun
```

Run the monitor and create Tender Agent briefs for new matches:

```powershell
.\tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1
```

Register a scheduled routine, defaulting to every 4 hours:

```powershell
.\tools\ns-tender-monitor\scripts\Register-NsTenderMonitorTask.ps1
```

Use a custom criteria file:

```powershell
.\tools\ns-tender-monitor\scripts\Invoke-NsTenderMonitor.ps1 -Criteria path\to\criteria.json
```

## Criteria

Read `config/targeted-stream-criteria.json` when the user asks to change matching rules. The matcher supports:

- `include_keywords`: at least one must appear in the tender ID, title, solicitation type, procurement entity, end-user entity, or description.
- `exclude_keywords`: any match rejects the tender.
- `statuses`: defaults to `OPEN`.
- `solicitation_types`: optional filter by tender type.
- `min_days_until_close`: optional minimum response window.

## Classification

The monitor records `pursuit_type`, `bid_fit`, `classification_confidence`, and `classification_reasons` in generated briefs and JSON summaries. When reporting examples to the user, lead with `design-study-consulting` direct consultant opportunities. Separate contractor-led construction from consultant-led work clearly, even when both match infrastructure keywords, and do not keep contractor-led or supplier-style items in active findings unless explicitly requested.

Common examples:

- Stormwater feasibility/design study: `design-study-consulting`, high priority.
- Hydraulic or assimilative capacity study: `design-study-consulting`, high priority.
- Wastewater system assessment report: `design-study-consulting`, high priority.
- Asphalt repaving, gravelling, bridge rehabilitation/replacement: `construction-contractor-led` unless seeking a contractor partner role.
- Supply, equipment, radios, vehicles, tools, materials: `supply-equipment-services`, usually skip for consulting.

## Notes

- The portal public API requires a guest token. Do not scrape rendered table text unless the API flow fails.
- Prefer the PowerShell script on this Windows machine. The bundled Python script is useful reference logic, but the portal may reject Python's HTTP client while accepting PowerShell/.NET requests.
- The list endpoint often has sparse tender details. The script fetches tender details by `tenderId` for matched rows before writing briefs.
- If the API starts rejecting requests, rerun a real browser network check against the portal and update the script's headers or endpoint flow.

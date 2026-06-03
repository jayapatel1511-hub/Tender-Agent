# Triage Run

Purpose: re-triage a stored open tender snapshot without calling the portal.

Use this when Tier 1 has already written `data/open-tenders/open-tenders-latest.json`
or when an older snapshot under `data/open-tenders/runs/` needs to be judged against
an updated interests profile.

## Command

```powershell
python scripts/run_triage.py `
  --snapshot data/open-tenders/open-tenders-latest.json `
  --profile config/targeted-stream-criteria.json `
  --output data/triage/triage-latest.json
```

All arguments are optional. The defaults are the paths shown above.

## Output

The runner writes `data/triage/triage-latest.json` with:

- `ran_at`
- `snapshot_path`
- `criteria_version`
- `result_count`
- `bucket_counts`
- `results[]`

Each result follows the Tier 2 schema: `tender_id`, `bucket`, `pursuit_type`,
`bid_fit`, `confidence`, `reason`, `next_action`, `urgent`, and `triaged_at`.

## Decision Notes

The runner is deterministic and standard-library only. It reads the raw snapshot
and criteria/profile file, uses the criteria keywords as hints, and applies a
domain-first pass for civil, water/wastewater, stormwater, municipal, and
transportation work.

If a tender has a target-domain asset but the service role is unclear, keep it in
`needs-review` or `partner-or-subconsultant-fit`; do not drop it as
`likely-skip` just because an older collector keyword excluded it.

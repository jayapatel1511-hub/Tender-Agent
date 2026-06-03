# Duplicate Review

Purpose: prevent duplicate tender emails.

## Check Sources

- `data\seen_tenders_state.json`
- `proposals\active\ns-tenders\`
- `proposals\outputs\ns-tenders\`
- `proposals\outputs\ns-tenders\email-briefs\`
- `proposals\outputs\ns-tenders\email-payloads\`
- `proposals\outputs\ns-tenders\run-logs\`

## Rules

- Tender ID is the primary dedupe key.
- Exact tender ID matches are duplicates even when titles change.
- Already-seen items with material changes are updates, not new opportunities.
- Do not email duplicates.

## Output

Return three buckets:

- `new`
- `duplicate`
- `update/review`

Include evidence for each duplicate decision.

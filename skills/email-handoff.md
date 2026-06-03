# Email Handoff

Purpose: send concise public-safe tender opportunity emails only when new relevant civil, municipal, or transportation opportunities exist.

## Privacy Rule

Email only public-safe content:

- tender title
- public buyer/organization
- closing date
- public source URL
- relevance rationale
- recommended next action

Do not email internal roster data, private company strategy, proposal text, redaction maps, or non-public pursuit notes.

## Steps

1. Run duplicate review first.
2. Run opportunity triage second.
3. If no relevant new tenders exist, do not send an email unless there was an error.
4. Email only `prime-consultant-fit` opportunities by default.
5. Include `partner-or-subconsultant-fit` only when the civil/transportation support role is obvious.
6. Do not include `off-profile-consulting`, `likely-skip`, supplier-style, vehicle/equipment, or generic advisory tenders in the normal qualified-opportunity email.
7. Send to `jpatel1511@outlook.com` unless the user specifies otherwise.
8. Use subject:

```text
Tender Leads - YYYY-MM-DD - N Strong / N Review
```

9. Store generated handoff evidence, when created, under:

```text
proposals\outputs\ns-tenders\email-briefs\
proposals\outputs\ns-tenders\email-payloads\
```

## Email Structure

Use a concise plain-text executive-summary format. Keep the normal qualified-opportunity email focused on `prime-consultant-fit` and clearly separate anything that is only adjacent, partner-led, or skip-worthy.

```text
Subject: Tender Leads - YYYY-MM-DD - N Strong / N Review

Summary
N tender matches found.
N strong-fit engineering pursuits.
N partner/subconsultant leads.
N adjacent or review-only opportunities.
N supplier-style or skip items.

Priority Leads
[Strong Fit] Tender title
Buyer: Public buyer or organization
Tender ID: Tender ID
Closes: YYYY-MM-DD, H:MM AM/PM Atlantic
Link: Public source URL

Fit: One-line fit classification.
Why it surfaced: Matched keyword, service type, or public notice signal.
Action: Specific next action.

Partner / Subconsultant Leads
[Partner Lead] Tender title
Buyer: Public buyer or organization
Tender ID: Tender ID
Closes: YYYY-MM-DD, H:MM AM/PM Atlantic
Link: Public source URL

Fit: Contractor-led or mixed opportunity with a possible civil/transportation support role.
Why it surfaced: Matched keyword, service type, or public notice signal.
Action: Specific next action.

Review / Adjacent Opportunities
[Review] Tender title
Buyer: Public buyer or organization
Tender ID: Tender ID
Closes: YYYY-MM-DD, H:MM AM/PM Atlantic
Link: Public source URL

Fit: Adjacent or off-profile classification.
Why it surfaced: Matched keyword, service type, or public notice signal.
Action: Specific next action.

Skipped / False Positives
[Skip] Tender title
Buyer: Public buyer or organization
Tender ID: Tender ID
Closes: YYYY-MM-DD, H:MM AM/PM Atlantic
Link: Public source URL

Fit: Supplier, goods-only, vehicle/equipment, generic advisory, or unrelated scope.
Why it surfaced: Matched keyword, service type, or public notice signal.
Action: Skip reason or narrow condition for manual review.

Notes
Only public tender information is included.
Verify scope, addenda, closing date, mandatory meetings, submission rules, and eligibility directly in the Nova Scotia Procurement Portal before acting.
```

## Labels

- `[Strong Fit]`: direct civil, municipal, transportation, planning, design, study, or assessment professional-services opportunity.
- `[Partner Lead]`: contractor-led or mixed opportunity where a civil/transportation support role is plausible.
- `[Review]`: adjacent consulting or ambiguous public-sector work that is not a normal qualified pursuit.
- `[Skip]`: supplier-style, vehicle/equipment, goods-only, generic advisory, or otherwise off-profile item.

## Content Rules

- Start with counts so the recipient can decide in a few seconds whether to read further.
- Put `Priority Leads` before lower-fit sections.
- Include `Why it surfaced` so false positives and matcher drift are visible over time.
- Use `Action` as a concrete decision cue, not a restatement of the tender description.
- Omit empty sections unless the user explicitly asked for a full audit-style email.
- For one-off off-profile emails, keep the same structure but make the subject and summary clearly say `off-profile`.

## Output

Report whether email was sent, recipient, subject, tender IDs included, and local evidence paths.

# Email Handoff

Purpose: send concise public-safe tender opportunity emails only when new relevant opportunities exist.

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
4. Send to `jpatel1511@outlook.com` unless the user specifies otherwise.
5. Use subject:

```text
New Tender Opportunities - YYYY-MM-DD
```

6. Store generated handoff evidence, when created, under:

```text
proposals\outputs\ns-tenders\email-briefs\
proposals\outputs\ns-tenders\email-payloads\
```

## Output

Report whether email was sent, recipient, subject, tender IDs included, and local evidence paths.

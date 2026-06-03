# Tender Workspace

Use this folder for tender inputs, documents, and generated workflow evidence.

```text
proposals/
  active/ns-tenders/         Current tender YAML briefs
  outputs/ns-tenders/
    email-briefs/            Human-readable email brief drafts
    email-payloads/          JSON email payloads
    run-logs/                Automation logs
    ns-tender-monitor-*.json Monitor summary JSON
```

Keep active tender source YAML in `active/ns-tenders`. Keep generated monitor summaries and email handoff evidence under `outputs/ns-tenders`. Routine run logs and monitor summaries are ignored by default; commit generated files only when they are useful review or demo evidence.

# Tender Agent Flow

Tender Agent owns the public tender source, screening, import, and intake evidence workflow. It stores artifacts produced by the local `ns-tender-monitor` skill script; it does not include a compiled app.

```mermaid
flowchart TD
    A["Nova Scotia Procurement Portal"] --> B["Tier 1 Collect<br/>all open + all details"]
    B --> C["Raw Open Tender Snapshot<br/>JSON latest + runs"]
    C --> DB["SQLite History<br/>data/tender-agent.sqlite"]
    D["Interests Profile<br/>config/targeted-stream-criteria.json"] --> E["Tier 2 Triage"]
    M["Persistent Context<br/>context/tender-agent-context.md"] --> E
    C --> E
    E --> F["Triage Artifact<br/>data/triage/triage-latest.json"]
    F --> DB
    F --> I["Duplicate Review"]
    S["Seen tender state<br/>data/seen_tenders_state.json"] --> I
    T["Calibration Tests<br/>skills/test-prompts.md"] --> E
    I --> J["Active Tender YAML<br/>proposals/active/ns-tenders"]
    I --> K["Email Brief / Payload<br/>when new relevant tenders exist"]
    I --> L["Notion Upsert Payload<br/>public-safe fields"]
```

## Workflow Contracts

| Stage | Owns | Output |
| --- | --- | --- |
| Collect open | Fetch every currently open tender listing without filtering by fit. | Complete open-tender snapshot under `data/open-tenders/runs/` and latest database at `data/open-tenders/open-tenders-latest.json`. |
| Triage | Apply the interests profile and domain-relevance rules to the snapshot. | `data/triage/triage-latest.json` plus SQLite triage history. |
| State file | Preserve emitted relevant tender IDs across Tier 2 runs. | Duplicate-prevention history in `data/seen_tenders_state.json`. |
| Run wrappers | Capture repo state, commands, summary paths, counts, and errors. | JSON run logs. |
| Human review | Confirm scope, addenda, eligibility, mandatory meetings, and submission rules. | Go/no-go decision and next action. |
| Email handoff | Send only public-safe concise briefs for newly relevant tenders. | Email brief/payload evidence. |

## Working Rule

Every real pursuit still requires human verification in the live procurement portal. The public notice and generated analysis are intake evidence, not a substitute for downloading tender documents, addenda, submission instructions, forms, and eligibility requirements.

Optional LLM use must receive only public-safe or redacted context. Do not send internal roster, company strategy, redaction maps, private proposal content, or non-public pursuit notes externally.

## Targeted Stream

The normal stream is civil, municipal, and transportation professional services. Strong examples include roads, streets, highways, corridors, intersections, active transportation, traffic, transit, stormwater, wastewater, municipal infrastructure, hydraulic studies, feasibility studies, design studies, and condition assessments.

Generic consulting, corporate advisory work, vehicles, equipment, supplier-style tenders, goods-only procurement, and unrelated services are off-profile and should not enter the normal qualified-opportunity email.

# Tender Agent Flow

Tender Agent owns the public tender source, screening, import, and intake evidence workflow. It stores artifacts produced by the local `ns-tender-monitor` skill script; it does not include a compiled app.

```mermaid
flowchart TD
    A["Nova Scotia Procurement Portal"] --> B["Local ns-tender-monitor script"]
    C["Seen tender state<br/>outside repo"] --> B
    D["Targeted Stream Criteria<br/>config/targeted-stream-criteria.json"] --> B
    M["Persistent Context<br/>context/tender-agent-context.md"] --> G
    B --> E["Monitor Summary JSON<br/>proposals/outputs/ns-tenders"]
    B --> F["Active Tender YAML<br/>proposals/active/ns-tenders"]
    E --> G["Duplicate Review"]
    F --> H["Human Portal Verification"]
    G --> I["Email Brief / Payload<br/>when new relevant tenders exist"]
    H --> I
    T["Calibration Tests<br/>skills/test-prompts.md"] --> G
```

## Workflow Contracts

| Stage | Owns | Output |
| --- | --- | --- |
| Local monitor script | Fetch current portal data, apply targeted stream criteria, skip seen IDs, and write active briefs. | Monitor summary JSON and tender YAML. |
| State file | Preserve seen tender IDs across runs. | Duplicate-prevention history outside the repo. |
| Run wrapper | Capture repo state, monitor command, summary path, matches, and errors. | JSON run log. |
| Human review | Confirm scope, addenda, eligibility, mandatory meetings, and submission rules. | Go/no-go decision and next action. |
| Email handoff | Send only public-safe concise briefs for newly relevant tenders. | Email brief/payload evidence. |

## Working Rule

Every real pursuit still requires human verification in the live procurement portal. The public notice and generated analysis are intake evidence, not a substitute for downloading tender documents, addenda, submission instructions, forms, and eligibility requirements.

Optional LLM use must receive only public-safe or redacted context. Do not send internal roster, company strategy, redaction maps, private proposal content, or non-public pursuit notes externally.

## Targeted Stream

The normal stream is civil, municipal, and transportation professional services. Strong examples include roads, streets, highways, corridors, intersections, active transportation, traffic, transit, stormwater, wastewater, municipal infrastructure, hydraulic studies, feasibility studies, design studies, and condition assessments.

Generic consulting, corporate advisory work, vehicles, equipment, supplier-style tenders, goods-only procurement, and unrelated services are off-profile and should not enter the normal qualified-opportunity email.

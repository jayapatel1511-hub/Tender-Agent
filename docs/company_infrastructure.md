# Company Infrastructure

The proposal brain uses company knowledge before it recommends people.

## Knowledge Files

```text
knowledge/
  company_structure.yaml
  people.yaml
```

`company_structure.yaml` defines:

- home company
- regions
- offices
- operating centres
- service lines
- OC managers
- sister companies
- executive approval threshold

`people.yaml` defines:

- person role
- company
- region
- office
- operating centre
- seniority
- proposal leadership eligibility
- skills
- industries
- past projects
- client relationships
- availability

## Decision Order

1. Determine project level: local, regional, or national.
2. Determine project region and service line.
3. Build eligible operating centres.
4. Build eligible company pool.
5. Flag approval requirements.
6. Rank people inside the eligible pool first.
7. Keep restricted people visible with exception reasons.

This lets the agent explain why a local project should stay in a local OC, why a national project can use sister-company support, and when leadership approval is required.

## Data Protection Layer

```mermaid
flowchart TD
    A["Raw Proposal Markdown"] --> B["Toby Flenderson Data Protection Agent"]
    B --> C["Detect sensitive entities"]
    C --> D["Clients / people / emails / phones / addresses / OCs / values"]
    D --> E["Replace with stable placeholders"]
    E --> F["Safe Markdown Package"]
    E --> G["Local Redaction Map<br/>Never sent to LLM"]

    F --> H{"Optional LLM enabled?"}
    H -->|"Yes"| I["LLM sees placeholders only"]
    H -->|"No"| J["Skip LLM"]

    I --> K["Extracted requirements / summaries"]
    J --> L["Deterministic company logic"]
    K --> L
    G --> M["Restore original names locally if needed"]
    L --> M
```

## Team Selection Chart

```mermaid
flowchart TD
    A["ProposalBrief"] --> B["Read project metadata"]
    B --> C["Project level<br/>local / regional / national"]
    B --> D["Project region"]
    B --> E["Service line"]
    B --> F["Preferred PM / proposal lead"]

    G["knowledge/company_structure.yaml"] --> H["Dwight Schrute Org Rules Agent"]
    C --> H
    D --> H
    E --> H
    F --> H

    H --> I{"Project level?"}

    I -->|"Local"| J["Restrict to local region OCs"]
    J --> K["Eligible local OCs"]
    K --> L["Eligible home-company people"]

    I -->|"Regional"| M["Prefer regional OC"]
    M --> N["Allow limited cross-region support"]
    N --> O["Flag regional director approval if needed"]

    I -->|"National"| P["Allow national practice support"]
    P --> Q["Add eligible sister companies"]
    Q --> R["Flag national practice lead approval"]

    L --> S["Build eligible candidate pool"]
    O --> S
    R --> S

    T["knowledge/people.yaml"] --> U["Load people profiles"]
    U --> V["Check each person"]

    S --> V
    V --> W{"Eligible?"}
    W -->|"Yes"| X["Score normally"]
    W -->|"No"| Y["Keep visible but mark restrictions"]

    X --> Z["Michael Scott Staffing Agent<br/>Rank by role, keywords, client relationship, region, OC, availability"]
    Y --> Z

    Z --> AA["Recommended Team"]
    Z --> AB["Exception / approval notes"]
```

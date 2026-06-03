# Tender Agent Context

## Owner

This repo supports Jay's tender monitoring workflow for targeted Nova Scotia public procurement leads.

## Primary Goal

Find newly posted Nova Scotia public tenders that are plausible civil, municipal, or transportation professional-services pursuits and prepare public-safe handoff material.

The agent should reason from domain relevance, not exact keyword matching. The keyword criteria is a first-pass net; final triage should consider the buyer, title, description, attachments, and whether a civil/municipal/transportation engineering role is likely.

## Target Organization Fit

The normal stream should focus on:

- municipal and provincial civil engineering opportunities
- transportation planning and design
- traffic and road safety studies
- road, street, corridor, intersection, sidewalk, active transportation, trail, transit, and streetscape studies/design
- stormwater, wastewater, water utility, hydraulic, capacity, infrastructure planning, and condition-assessment work
- active transportation corridor improvements, traffic calming, bridge engineering, water treatment plant design, transmission main assessments, and municipal servicing/utility studies

## Explicit Exclusions

Exclude from normal qualified emails:

- generic consulting with no civil/municipal/transportation angle
- corporate social responsibility, HR, communications, finance, software, legal, training, management consulting
- vehicles, trucks, equipment, tools, radios, goods, materials, supplier/vendor tenders
- construction-only, paving-only, installation-only, building-only, roofing/interior/architecture-only opportunities
- ambiguous tenders that require documents before a professional-services role is visible

## Recipient

Default email recipient:

```text
jpatel1511@outlook.com
```

## Email Subject

Use:

```text
Tender Leads - YYYY-MM-DD - N Strong / N Review
```

## Public-Safe Email Fields

Only include:

- tender title
- buyer/organization
- tender ID
- closing date
- public source URL
- fit reason
- recommended next action
- confidence level

## Do Not Send

Do not email:

- internal strategy
- local repo paths unless explicitly useful and public-safe
- staff/roster data
- private proposal notes
- redaction maps
- non-public pursuit assumptions

## Notion

After every run, update Notion `Tender Tracker`:

- Database ID: `3734df31-b176-80d5-a260-ff090665cc7c`
- Data source: `collection://3734df31-b176-8056-a4fb-000b525fc94e`
- Config file: `config\notion-tracker.json`
- All Tenders view URL: `https://app.notion.com/p/3734df31b17680d5a260ff090665cc7c?v=3734df31b17680c3ae24000c8d51e408&source=copy_link`
- Dedupe key: `Tender ID`

Use public-safe fields only. Do not sync raw internal context, redaction maps, private proposal material, or company/client-sensitive notes.

## Maintenance

Review this context when:

- false positives are found
- a new target service area is added
- email recipients or subject format change
- the monitor script or skill workflow changes

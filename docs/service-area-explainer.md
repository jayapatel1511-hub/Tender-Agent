# Service Area Explainer

Purpose: help the agent reason about domain fit before using keywords. Keywords are discovery hints, not the decision rule.

Use this document during triage whenever a tender title is broad, uses unfamiliar procurement wording, or matches a keyword without clearly showing whether the work belongs in the targeted stream.

## Core Test

Ask these questions in order:

1. What physical public asset, system, corridor, utility, or site is being planned, assessed, designed, or improved?
2. Is the likely professional role civil, municipal, transportation, water/wastewater, stormwater, traffic, infrastructure planning, or closely adjacent engineering?
3. Is the buyer a municipality, utility, transportation/public works body, bridge authority, provincial department, or public infrastructure owner?
4. Is the requested work a study, assessment, design, planning, modelling, engineering service, standing offer, or technical review?
5. If it is construction-led, is there an obvious partner/subconsultant engineering role?

If the answer to 1 and 2 is yes, keep the tender for triage even if the exact keyword was not in the criteria file. If the answer is unclear but plausible, mark it `needs-review` and fetch more detail.

## Target Domains

### Municipal Civil Infrastructure

Includes roads, streets, sidewalks, intersections, culverts, drainage, site servicing, municipal assets, public works infrastructure, subdivisions, business parks, and community infrastructure where civil engineering judgment is likely needed.

Strong signals:

- road, street, sidewalk, curb, gutter, intersection, corridor, culvert, drainage, grading, servicing, municipal infrastructure
- feasibility, design, assessment, condition review, asset management, engineering services
- public works or municipal engineering buyer

Usually relevant:

- business park expansion feasibility if servicing, roads, drainage, grading, or infrastructure planning is part of the scope
- municipal infrastructure plans, asset management plans, servicing studies, and utility extension studies

Usually skip:

- asphalt supply, paving-only, gravel supply, line painting-only, snow clearing, building renovation with no civil scope

### Transportation And Traffic

Includes transportation planning, road safety, traffic calming, active transportation, transit-supportive infrastructure, traffic operations, impact studies, corridor studies, road diets, intersections, trails, sidewalks, and multi-use paths.

Strong signals:

- traffic calming, road safety, traffic impact, active transportation, corridor improvements, pedestrian, cycling, sidewalk, trail, transit, intersection, streetscape
- study, design, assessment, planning, operations review, safety review

Important rule:

Active transportation corridor improvements and traffic calming may sound like construction, but they are domain-relevant. Keep them at least as `needs-review` unless the notice clearly says supply-only or construction-only with no design/support role.

Usually relevant:

- active transportation corridor improvements
- traffic calming programs
- road safety audits or implementation studies
- intersection/corridor planning and design

Usually skip:

- sign supply only, vehicle purchases, traffic signal hardware supply only, pavement marking supply only, equipment rentals

### Water And Wastewater

Includes treatment plants, watermains, transmission mains, pump stations, PRVs, lift stations, storage tanks, wastewater systems, collection/distribution systems, utility planning, and condition assessments.

Strong signals:

- water treatment plant, wastewater treatment plant, transmission main, watermain, pump station, lift station, PRV, sewer, utility, condition assessment
- hydraulic, capacity, assimilative capacity, modelling, design, engineering services

Usually relevant:

- treatment plant assessment or design
- water/wastewater standing offer for engineering services
- transmission main condition assessment
- hydraulic and assimilative capacity studies

Usually skip:

- chemical supply, pipe supply only, hydrant supply only, utility construction-only with no engineering role

### Stormwater And Flood Resilience

Includes stormwater management, drainage, flood mitigation, watershed planning, hydrologic/hydraulic modelling, climate resilience tied to public infrastructure, and erosion or drainage assessments.

Strong signals:

- stormwater, drainage, flood, watershed, hydrologic, hydraulic, climate resilience, erosion, culvert, outfall
- feasibility, design study, model, assessment, concept design, implementation planning

Usually relevant:

- stormwater feasibility/design studies
- watershed flood mitigation plans
- hydraulic modelling for municipal infrastructure

Usually skip:

- drainage construction-only, culvert replacement construction-only, supply of drainage materials

### Bridges And Structures Adjacent To Transportation

Includes bridges, retaining structures, navigation or safety systems attached to transportation infrastructure, structural assessments, and engineering services for transportation assets.

Strong signals:

- bridge, overpass, retaining wall, structural assessment, navigation lighting, safety system, design, engineering services

Usually relevant:

- bridge engineering services
- navigation/aviation lighting engineering on a bridge when assessment/design/tender documents are required

Usually skip:

- bridge rehabilitation or replacement construction-only unless engineering support is explicitly requested
- lighting equipment supply only

## Service Types

### Prime Consultant Fit

Use when the public notice asks for professional services and the asset/domain is in scope.

Examples:

- feasibility study
- design study
- engineering design services
- system assessment report
- condition assessment
- hydraulic/capacity study
- standing offer for engineering services

### Partner Or Subconsultant Fit

Use when the tender is contractor-led but the work may need civil, transportation, water/wastewater, traffic, or specialist engineering support.

Examples:

- active transportation corridor construction with design support, inspection, or contract administration needs
- traffic calming implementation where engineering review, layout, or safety support may be needed
- utility construction where assessment, design verification, or resident engineering may be needed

Do not email these as qualified leads unless the support role is obvious. Otherwise keep them for manual review.

### Off-Profile Consulting

Use when it is consulting but not in the engineering/public-infrastructure target domain.

Examples:

- corporate social responsibility
- HR, finance, legal, communications, training
- software, web, IT, cybersecurity
- business strategy with no infrastructure asset

### Likely Skip

Use when the tender is goods, equipment, vendor supply, or construction-only with no professional-services role.

Examples:

- trucks, radios, rescue tools, office supplies
- supply and installation with no design/engineering requirement
- paving-only, roofing-only, window replacement-only

## Ambiguity Handling

Do not make a final skip decision from a short title if the asset/domain looks relevant. Use this pattern:

- `prime-consultant-fit`: public notice clearly asks for professional services in target domain.
- `partner-or-subconsultant-fit`: construction-led but likely useful for partner/support pursuit.
- `needs-review`: domain looks relevant but the service role is unclear.
- `off-profile-consulting`: consulting, but outside target domain.
- `likely-skip`: clear supply/goods/construction-only or unrelated service.

When unsure, preserve the tender in `needs-review` and fetch the detail page or documents. Missing a domain-relevant tender is worse than carrying an extra review item.

## Calibration Examples

Keep or review:

- `Active Transportation Corridor Improvements`: transportation/public-works domain; likely review or partner fit even if construction-led.
- `Traffic Calming Phase 2`: transportation/road-safety domain; likely review or partner fit.
- `Pockwock Transmission Main Condition Assessment`: water utility condition assessment; prime consultant fit.
- `Engineering Design Services & Water Treatment Plant Design`: water/wastewater engineering design; prime consultant fit.
- `Stormwater Feasibility and Design Study`: stormwater/flood-resilience professional services; prime consultant fit.

Skip:

- `Corporate Social Responsibility Consulting`: off-profile consulting.
- `Truck Supply`: goods/equipment.
- `Asphalt Repaving`: construction-only unless engineering services are separately requested.
- `Roof Replacement`: building construction only unless structural/civil engineering services are explicitly requested.

# Opportunity Triage

Purpose: classify new tender matches for Englobe-relevant civil, municipal, and transportation pursuit relevance.

Triage should run after open-tender collection. It should not depend only on tenders that survived an earlier keyword/classifier filter.

Before using keyword criteria, read `docs/service-area-explainer.md` and classify the tender by asset/domain and likely service role. Keywords are only a search aid.

## Domain Focus

Englobe-fit tenders should be tied to civil, municipal, or transportation professional services. Prioritize work that fits a civil/transportation role: municipal streets, roads, highways, corridors, intersections, active transportation, traffic, transit, and related planning or design studies.

Do not treat generic consulting as relevant just because it is an RFP. Consulting must connect back to civil, municipal, transportation, or public works engineering.

Do not require exact keyword matches. Keywords are discovery signals only. If the title, buyer, description, attachments, or scope context shows a likely engineering role in the target domain, keep it in triage. If the listing is ambiguous but domain-adjacent, mark `needs-review` and enrich from the detail page instead of dropping it.

Use this domain-first test:

1. Identify the asset or system: road, corridor, utility, stormwater system, bridge, site servicing, public works asset, or other physical infrastructure.
2. Identify the service role: study, design, assessment, modelling, planning, engineering services, standing offer, review, or contractor support.
3. Identify the buyer/context: municipality, utility, bridge authority, public works owner, transportation body, or provincial infrastructure owner.
4. Decide fit from the combination of asset plus service role. Do not decide from a single word.

## Prefer

- civil engineering services
- municipal engineering services
- transportation engineering, traffic, roads, highways, streets, intersections, corridors, active transportation
- road safety, corridor studies, intersection studies, traffic impact studies
- municipal public works engineering tied to roads, streets, sidewalks, trails, transit, or active transportation
- civil/municipal/transportation feasibility studies, design studies, planning studies, and assessments
- active transportation corridor improvements
- traffic calming, road safety, intersection, and traffic operations work
- water/wastewater treatment plant engineering and utility condition assessments
- watermain, transmission main, PRV, pump station, and municipal servicing studies

## Separate Or Skip

- corporate social responsibility, HR, communications, finance, software, training, legal, general management, or generic advisory consulting
- construction-heavy tenders
- supply, equipment, vendor, or goods-only procurements
- installation-only work
- items with no professional-services scope
- building-only architecture/interior/roofing items unless there is a clear civil, municipal, or transportation angle

## Categories

- `prime-consultant-fit`
- `partner-or-subconsultant-fit`
- `off-profile-consulting`
- `likely-skip`
- `needs-review`

## Decision Rules

- Mark as `prime-consultant-fit` only when the public notice shows civil, municipal, or transportation engineering or closely adjacent professional services.
- Mark as `partner-or-subconsultant-fit` when the work is contractor-led but may need civil, municipal, or transportation engineering support.
- Mark as `off-profile-consulting` when it is consulting but outside the civil/municipal/transportation domain.
- Mark as `likely-skip` for goods, vehicles, equipment, vendor supply, or services with no professional engineering role.
- If a tender is ambiguous, keep it in `needs-review` and do not email it as qualified.
- If a tender is strong domain fit but closes soon, keep it and mark it `urgent-review`; do not drop it only because the response window is short.
- If a tender has a target-domain asset but unclear service role, do not skip it from the title alone. Mark `needs-review` and fetch details.
- If a tender has a consulting service role but no target-domain asset, mark `off-profile-consulting` even if it is an RFP.

## Output

For each relevant tender, include title, buyer, closing date, source URL, relevance reason, and recommended next action.

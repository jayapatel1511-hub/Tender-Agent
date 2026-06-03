# Fake Organization Seed Data

This repository uses a fictional 100-person organization named `Northstar Englobe Demo` for proposal-agent testing.

The dataset is inspired only by public, high-level information about Englobe's business footprint:

- environmental management, environmental sciences, and engineering services
- geosciences, geotechnical engineering, materials testing, inspection, and quality assessment
- asset integrity, building science, pavement, transportation, climate resilience, sustainability, and power-sector support
- a broad Canadian office/lab footprint

No real employee names are used. Staff names are fictional movie/cartoon-style names for safe demo data.

## Public Reference Points

- https://www.englobecorp.com/en-ca/services/
- https://www.englobecorp.com/en-ca/services/engineering-design-inspection/materials-engineering-inspection/
- https://www.englobecorp.com/en-ca/services/engineering-design-inspection/geosciences-geotechnical-engineering/
- https://www.englobecorp.com/en-ca/
- https://oecm.ca/supplier-partners/englobe-corp/

## Generated Files

- `knowledge/company_structure.yaml`
- `knowledge/people.yaml`

Regenerate with:

```powershell
python tools/generate_fake_org.py
```

## Design Notes

- Keep `Halifax Civil OC`, `Moncton Civil OC`, and `Toronto Civil OC` because tests and examples use them.
- Keep `atlantic`, `ontario`, and other lowercase region keys because the rules engine compares those values directly.
- Keep service lines broad enough to support proposal examples across civil, environmental, geotechnical, materials, building science, transportation, power, asset integrity, digital delivery, and climate resilience.

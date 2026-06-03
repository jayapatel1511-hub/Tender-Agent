# Tender Agent Calibration Tests

Use these tests after changing criteria, triage rules, email rules, or the monitor wrapper. The expected result is the classification the agent should apply before sending any email.

## Test Cases

### 1. CSR Consulting

Input:

```text
Corporate Social Responsibility Consulting Services for a public gaming corporation.
```

Expected:

```text
off-profile-consulting
Do not include in normal qualified email.
Reason: generic advisory / CSR consulting, no civil, municipal, or transportation engineering angle.
```

### 2. Truck RFQ

Input:

```text
One new model 19,500 GVWR 4WD regular cab truck with dump box and liftgate for a town public works department.
```

Expected:

```text
likely-skip
Do not include in normal qualified email.
Reason: vehicle/equipment procurement, no professional-services role.
```

### 3. Wastewater Assessment

Input:

```text
Maccan Wastewater Treatment Plant System Assessment Report for a municipality.
```

Expected:

```text
prime-consultant-fit
Include if new and not duplicate.
Reason: municipal wastewater system assessment is a targeted civil/municipal professional-services opportunity.
Confidence: High.
```

### 4. Stormwater Feasibility And Design

Input:

```text
Stormwater Management Project feasibility and design study for a town watershed.
```

Expected:

```text
prime-consultant-fit
Include if new and not duplicate.
Reason: stormwater feasibility/design study is a targeted civil/municipal engineering opportunity.
Confidence: High.
```

### 5. Road Safety Study

Input:

```text
Road safety review and intersection improvement study for a municipal corridor.
```

Expected:

```text
prime-consultant-fit
Include if new and not duplicate.
Reason: transportation/traffic/intersection study fits the targeted stream.
Confidence: High.
```

### 6. Active Transportation Corridor Improvements

Input:

```text
Active Transportation Corridor Improvements - Highland to Church Street for a town.
```

Expected:

```text
prime-consultant-fit or needs-review
Include for review if new and not duplicate.
Reason: active transportation corridor work is in the targeted transportation/municipal stream even if the notice says improvements rather than study/design.
Confidence: Medium to High depending whether professional-services scope is visible.
```

### 7. Traffic Calming

Input:

```text
Traffic Calming Phase 2 at various municipal locations.
```

Expected:

```text
prime-consultant-fit or partner-or-subconsultant-fit
Include for review if new and not duplicate.
Reason: traffic calming is transportation engineering/public works domain. Confirm whether it is design/engineering services or contractor-led implementation.
Confidence: Medium until documents confirm role.
```

### 8. Water Treatment Plant Engineering

Input:

```text
Engineering Design Services and Plant Management for a municipal water treatment plant design.
```

Expected:

```text
prime-consultant-fit
Include if new and not duplicate, even if closing soon.
Reason: municipal water treatment plant engineering design is in the targeted infrastructure stream.
Confidence: High.
```

### 9. Asphalt Repaving

Input:

```text
Asphalt repaving and gravelling tender for municipal roads.
```

Expected:

```text
partner-or-subconsultant-fit or likely-skip
Do not include in normal qualified email unless the public notice clearly requests engineering inspection, design, or contract administration.
Reason: contractor-led construction work.
Confidence: Medium if professional-services role is visible, otherwise Low.
```

### 10. Building Roof Replacement

Input:

```text
Roof replacement and building envelope repairs at a public facility.
```

Expected:

```text
likely-skip
Do not include in normal qualified email.
Reason: building-only work with no civil, municipal, or transportation angle.
```

## Dry-Run Check

After criteria changes, run:

```powershell
.\scripts\run_daily.ps1 -DryRun -IncludeSeen -MaxPages 1
```

Expected behavior:

- CSR consulting does not appear as a qualified match.
- Vehicle/equipment tenders do not appear as qualified matches.
- Wastewater, stormwater, traffic, traffic calming, active transportation, road safety, municipal infrastructure, water treatment plant, and transportation studies remain eligible.
- If active transportation or traffic calming tenders appear in a broad open-tender search but not in monitor matches, flag classifier drift rather than treating them as irrelevant.

For a full open-population dry check, run:

```powershell
.\scripts\run_daily.ps1 -DryRun -IncludeSeen
```

This should scan the broad open-tender window before filtering. Use the `summary_path` in the output to inspect what was matched.

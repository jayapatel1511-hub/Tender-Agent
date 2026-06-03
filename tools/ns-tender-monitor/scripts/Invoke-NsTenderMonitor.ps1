param(
    [string]$Criteria = "",
    [string]$State = "",
    [string]$ProposalRepo = "",
    [string]$Keyword = "",
    [int]$PageSize = 25,
    [int]$MaxPages = 2,
    [switch]$IncludeSeen,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
if ([string]::IsNullOrWhiteSpace($Criteria)) {
    $Criteria = Join-Path $RepoRoot "config\targeted-stream-criteria.json"
}
if ([string]::IsNullOrWhiteSpace($State)) {
    $State = Join-Path $RepoRoot "data\seen_tenders_state.json"
}
if ([string]::IsNullOrWhiteSpace($ProposalRepo)) {
    $ProposalRepo = $RepoRoot
}
$BaseUrl = "https://procurement-portal.novascotia.ca"
$Headers = @{
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    "Accept" = "application/json"
    "Referer" = "$BaseUrl/tenders"
}

function Read-JsonFile($Path, $Default) {
    if (Test-Path -LiteralPath $Path) {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    return $Default
}

function Write-JsonFile($Path, $Value) {
    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    $Value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function ConvertTo-Hashtable($Object) {
    $hash = @{}
    if ($null -eq $Object) {
        return $hash
    }
    foreach ($property in $Object.PSObject.Properties) {
        $hash[$property.Name] = $property.Value
    }
    return $hash
}

function Get-TextBlob($Tender) {
    $fields = @("tenderId", "title", "solicitationType", "procurementEntity", "endUserEntity", "description", "memo", "contactDetails")
    $parts = foreach ($field in $fields) {
        if ($Tender.PSObject.Properties.Name -contains $field -and $null -ne $Tender.$field) {
            [string]$Tender.$field
        }
    }
    return ($parts -join " ").ToLowerInvariant()
}

function Get-DateOrNull($Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }
    $parsed = [datetime]::MinValue
    if ([datetime]::TryParse([string]$Value, [ref]$parsed)) {
        return $parsed
    }
    return $null
}

function Test-TenderMatch($Tender, $CriteriaData, [datetime]$Now) {
    $reasons = New-Object System.Collections.Generic.List[string]
    $blob = Get-TextBlob $Tender

    $statuses = @($CriteriaData.statuses | ForEach-Object { ([string]$_).ToLowerInvariant() })
    if ($statuses.Count -eq 0) {
        $statuses = @("open")
    }
    $status = ([string]$Tender.tenderStatus).ToLowerInvariant()
    if ($statuses -notcontains $status) {
        return [pscustomobject]@{ Match = $false; Reasons = @("status $status not in criteria") }
    }

    $solicitationTypes = @($CriteriaData.solicitation_types | ForEach-Object { ([string]$_).ToLowerInvariant() })
    $solicitation = ([string]$Tender.solicitationType).ToLowerInvariant()
    if ($solicitationTypes.Count -gt 0) {
        $solicitationHit = $false
        foreach ($type in $solicitationTypes) {
            if ($solicitation.Contains($type)) {
                $solicitationHit = $true
            }
        }
        if (-not $solicitationHit) {
            return [pscustomobject]@{ Match = $false; Reasons = @("solicitation type not in criteria") }
        }
    }

    if ($null -ne $CriteriaData.min_days_until_close) {
        $closing = Get-DateOrNull $Tender.closingDate
        if ($null -ne $closing) {
            $days = ($closing - $Now).TotalDays
            if ($days -lt [double]$CriteriaData.min_days_until_close) {
                return [pscustomobject]@{ Match = $false; Reasons = @("closing window $([math]::Round($days, 1)) days is below minimum") }
            }
        }
    }

    foreach ($keyword in @($CriteriaData.exclude_keywords)) {
        if ($blob.Contains(([string]$keyword).ToLowerInvariant())) {
            return [pscustomobject]@{ Match = $false; Reasons = @("excluded keyword: $keyword") }
        }
    }

    $hits = New-Object System.Collections.Generic.List[string]
    foreach ($keyword in @($CriteriaData.include_keywords)) {
        if ($blob.Contains(([string]$keyword).ToLowerInvariant())) {
            $hits.Add([string]$keyword)
        }
    }
    if (@($CriteriaData.include_keywords).Count -gt 0 -and $hits.Count -eq 0) {
        return [pscustomobject]@{ Match = $false; Reasons = @("no include keyword matched") }
    }
    if ($hits.Count -gt 0) {
        $reasons.Add("matched keywords: " + ($hits -join ", "))
    }
    return [pscustomobject]@{ Match = $true; Reasons = @($reasons) }
}

function Get-OpportunityClassification($Tender) {
    $blob = Get-TextBlob $Tender
    $title = ([string]$Tender.title).ToLowerInvariant()
    $strongConsultingPatterns = @(
        "feasibility",
        "study",
        "assessment",
        "system assessment",
        "capacity study",
        "assimilative capacity",
        "design study",
        "design services",
        "engineering services",
        "consulting",
        "consultant",
        "report",
        "master plan",
        "planning",
        "model",
        "modelling",
        "stormwater management project",
        "inspection services",
        "condition assessment"
    )
    $technicalContextPatterns = @(
        "hydraulic"
    )
    $constructionPatterns = @(
        "asphalt repaving",
        "paving",
        "gravelling",
        "bridge rehabilitation",
        "bridge replacement",
        "window replacement",
        "recladding",
        "sprinkler work",
        "construction",
        "utility extensions",
        "supply & installation",
        "supply and installation",
        "replacement - waterline",
        "street recapitalization",
        "traffic signal improvements",
        "tender -"
    )
    $supplyPatterns = @(
        "supply of",
        "supply & programming",
        "articulating municipal tractor",
        "vehicle",
        "radios",
        "rescue tools",
        "electrical supplies",
        "lamps and ballasts",
        "media destruction",
        "goods and services",
        "vendor"
    )

    $consultingHits = @($strongConsultingPatterns | Where-Object { $blob.Contains($_) })
    $technicalContextHits = @($technicalContextPatterns | Where-Object { $blob.Contains($_) })
    if ($title -match '\bdesign\b') {
        $consultingHits += "design"
    }
    $constructionHits = @($constructionPatterns | Where-Object { $blob.Contains($_) })
    $supplyHits = @($supplyPatterns | Where-Object { $blob.Contains($_) })

    $type = "needs-review"
    $bidFit = "review-documents"
    $confidence = "low"
    $note = "Not enough signal in the public notice to classify without opening the tender documents."

    if ($supplyHits.Count -gt 0 -and $consultingHits.Count -eq 0) {
        $type = "supply-equipment-services"
        $bidFit = "likely-skip-unless-supplier"
        $confidence = "high"
        $note = "Looks like supply, equipment, goods, or vendor procurement rather than professional consulting."
    }
    elseif ($consultingHits.Count -gt 0 -and $supplyHits.Count -eq 0) {
        $type = "design-study-consulting"
        $bidFit = "prime-consultant-fit"
        $confidence = if ($constructionHits.Count -gt 0) { "medium" } else { "high" }
        $note = "Looks like a consulting, design, study, assessment, or engineering-services opportunity."
    }
    elseif ($consultingHits.Count -gt 0 -and $supplyHits.Count -gt 0) {
        $type = "mixed-consulting-and-delivery"
        $bidFit = "review-for-prime-or-subconsultant-role"
        $confidence = "medium"
        $note = "Has consulting/design language plus supply, vendor, installation, or delivery language."
    }
    elseif ($constructionHits.Count -gt 0) {
        $type = "construction-contractor-led"
        $bidFit = "partner-or-subconsultant-fit"
        $confidence = "high"
        $note = "Looks construction or contractor led; bid directly only with construction capacity or a contractor partner."
    }
    return [pscustomobject]@{
        pursuit_type = $type
        bid_fit = $bidFit
        confidence = $confidence
        note = $note
        consulting_signals = @($consultingHits)
        technical_context_signals = @($technicalContextHits)
        construction_signals = @($constructionHits)
        supply_signals = @($supplyHits)
    }
}

function Get-CandidateBucket($Match, $Classification, $Tender) {
    $blob = Get-TextBlob $Tender
    $clearSkipSignals = @(
        "tractor",
        "trailer",
        "trailers",
        "heavy equipment",
        "vehicle",
        "supply of",
        "articulating municipal tractor",
        "student transportation services",
        "notice of intent to participate canoe"
    )
    foreach ($signal in $clearSkipSignals) {
        if ($blob.Contains($signal)) {
            return "likely-skip"
        }
    }

    if (-not $Match.Match) {
        $reasonText = (@($Match.Reasons) -join " ").ToLowerInvariant()
        $transportationDomainSignals = @(
            "active transportation",
            "traffic calming",
            "road safety",
            "corridor improvements",
            "sidewalk",
            "street",
            "intersection",
            "traffic"
        )
        foreach ($signal in $transportationDomainSignals) {
            if ($blob.Contains($signal)) {
                return "partner-or-subconsultant-fit"
            }
        }
        if ($reasonText.Contains("excluded keyword")) {
            if ($blob.Contains("consulting") -or $blob.Contains("consultant") -or $blob.Contains("advisory")) {
                return "off-profile-consulting"
            }
            return "likely-skip"
        }
        return "likely-skip"
    }

    if ($null -eq $Classification) {
        return "needs-review"
    }
    if ($Classification.pursuit_type -eq "design-study-consulting" -and $Classification.bid_fit -eq "prime-consultant-fit") {
        return "prime-consultant-fit"
    }
    if ($Classification.pursuit_type -eq "construction-contractor-led" -or $Classification.bid_fit -eq "partner-or-subconsultant-fit") {
        return "partner-or-subconsultant-fit"
    }
    if ($Classification.pursuit_type -eq "mixed-consulting-and-delivery") {
        return "needs-review"
    }
    if ($Classification.pursuit_type -eq "supply-equipment-services") {
        return "likely-skip"
    }
    return "needs-review"
}

function New-OpenTenderRecord($Tender, [datetime]$RunAt, [string]$Bucket, $Match, $Classification) {
    $tenderId = [string]$Tender.tenderId
    if ([string]::IsNullOrWhiteSpace($tenderId)) {
        $tenderId = [string]$Tender.id
    }
    [pscustomobject]@{
        tender_id = $tenderId
        title = [string]$Tender.title
        status = [string]$Tender.tenderStatus
        solicitation_type = [string]$Tender.solicitationType
        procurement_entity = [string]$Tender.procurementEntity
        end_user_entity = [string]$Tender.endUserEntity
        post_date = [string]$Tender.postDate
        closing_date = [string]$Tender.closingDate
        portal_url = "$BaseUrl/tenders/$([uri]::EscapeDataString($tenderId))"
        triage_bucket = $Bucket
        match_reasons = @($Match.Reasons)
        pursuit_type = if ($Classification) { $Classification.pursuit_type } else { $null }
        bid_fit = if ($Classification) { $Classification.bid_fit } else { $null }
        classification_confidence = if ($Classification) { $Classification.confidence } else { $null }
        classification_note = if ($Classification) { $Classification.note } else { $null }
        last_seen_at = $RunAt.ToString("o")
        source = "nova-scotia-procurement-portal"
        raw = $Tender
    }
}

function Write-OpenTenderSnapshot($Repo, [datetime]$RunAt, $Records, $BucketCounts) {
    $dbDir = Join-Path $Repo "data\open-tenders"
    $runsDir = Join-Path $dbDir "runs"
    New-Item -ItemType Directory -Force -Path $runsDir | Out-Null
    $payload = [pscustomobject]@{
        ran_at = $RunAt.ToString("s")
        source = "https://procurement-portal.novascotia.ca/tenders"
        open_tender_count = @($Records).Count
        candidate_bucket_counts = $BucketCounts
        tenders = @($Records)
    }
    $snapshotPath = Join-Path $runsDir ("open-tenders-" + $RunAt.ToString("yyyyMMdd-HHmmss") + ".json")
    $latestPath = Join-Path $dbDir "open-tenders-latest.json"
    Write-JsonFile $snapshotPath $payload
    Write-JsonFile $latestPath $payload
    return [pscustomobject]@{
        snapshot_path = $snapshotPath
        latest_path = $latestPath
    }
}

function ConvertTo-Slug($Value) {
    $slug = ([string]$Value).ToLowerInvariant() -replace "[^a-z0-9]+", "-"
    $slug = $slug.Trim("-")
    if ($slug.Length -gt 80) {
        return $slug.Substring(0, 80)
    }
    if ($slug.Length -eq 0) {
        return "tender"
    }
    return $slug
}

function ConvertTo-YamlScalar($Value) {
    if ($null -eq $Value -or [string]$Value -eq "") {
        return '""'
    }
    $text = ([string]$Value).Replace("\", "\\").Replace('"', '\"')
    return '"' + $text + '"'
}

function ConvertTo-BlockText($Value) {
    if ($null -eq $Value) {
        return ""
    }
    return (([string]$Value) -replace "\r?\n", " " -replace "\s+", " ").Trim()
}

function Write-TenderBrief($Tender, [string[]]$Reasons, $Classification, $Repo) {
    $activeDir = Join-Path $Repo "proposals\active\ns-tenders"
    New-Item -ItemType Directory -Force -Path $activeDir | Out-Null
    $tenderId = [string]$Tender.tenderId
    if ([string]::IsNullOrWhiteSpace($tenderId)) {
        $tenderId = [string]$Tender.id
    }
    $path = Join-Path $activeDir ((ConvertTo-Slug "$tenderId-$($Tender.title)") + ".yaml")
    $expectedTenderIdLine = "tender_id: $(ConvertTo-YamlScalar $tenderId)"
    Get-ChildItem -LiteralPath $activeDir -Filter "*.yaml" | ForEach-Object {
        $existingPath = $_.FullName
        if ($existingPath -ne $path -and (Select-String -LiteralPath $existingPath -SimpleMatch $expectedTenderIdLine -Quiet)) {
            Remove-Item -LiteralPath $existingPath
        }
    }
    $closing = Get-DateOrNull $Tender.closingDate
    $dueDate = if ($null -ne $closing) { $closing.ToString("yyyy-MM-dd") } else { "" }
    $portalUrl = "$BaseUrl/tenders/$([uri]::EscapeDataString($tenderId))"
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("client: $(ConvertTo-YamlScalar ($Tender.procurementEntity ?? $Tender.endUserEntity ?? 'Nova Scotia public sector'))")
    $lines.Add("opportunity: $(ConvertTo-YamlScalar ($Tender.title ?? $tenderId))")
    $lines.Add("due_date: $(ConvertTo-YamlScalar $dueDate)")
    $lines.Add('industry: "Civil engineering"')
    $lines.Add('service_line: "infrastructure"')
    $lines.Add('project_region: "atlantic"')
    $lines.Add("rfp_text: >")
    $lines.Add("  Tender ${tenderId}: $(ConvertTo-BlockText $Tender.title).")
    $lines.Add("  Solicitation type: $(ConvertTo-BlockText $Tender.solicitationType).")
    $lines.Add("  Procurement entity: $(ConvertTo-BlockText $Tender.procurementEntity).")
    $lines.Add("  End-user entity: $(ConvertTo-BlockText $Tender.endUserEntity).")
    $lines.Add("  Status: $(ConvertTo-BlockText $Tender.tenderStatus).")
    $lines.Add("  Posted: $(ConvertTo-BlockText $Tender.postDate).")
    $lines.Add("  Closing: $(ConvertTo-BlockText $Tender.closingDate).")
    $lines.Add("  Portal URL: $portalUrl.")
    $lines.Add("  Description: $(ConvertTo-BlockText $Tender.description).")
    $lines.Add("pursuit_type: $(ConvertTo-YamlScalar $Classification.pursuit_type)")
    $lines.Add("bid_fit: $(ConvertTo-YamlScalar $Classification.bid_fit)")
    $lines.Add("classification_confidence: $(ConvertTo-YamlScalar $Classification.confidence)")
    $lines.Add("classification_note: $(ConvertTo-YamlScalar $Classification.note)")
    $lines.Add("goals:")
    $lines.Add("  - Review tender notice and documents for fit.")
    $lines.Add("  - Confirm eligibility, submission method, schedule, and compliance requirements.")
    $lines.Add("scope:")
    $lines.Add("  - Capture tender requirements.")
    $lines.Add("  - Prepare pursue/no-pursue recommendation.")
    $lines.Add("  - Draft proposal response outline if qualified.")
    $lines.Add("constraints:")
    $lines.Add("  - Verify all tender documents directly in the Nova Scotia Procurement Portal before bidding.")
    $lines.Add("decision_criteria:")
    $lines.Add("  - Strategic fit.")
    $lines.Add("  - Technical capability.")
    $lines.Add("  - Available response time.")
    $lines.Add("  - Compliance requirements.")
    $lines.Add("source:")
    $lines.Add("  portal_url: $(ConvertTo-YamlScalar $portalUrl)")
    $lines.Add("  tender_id: $(ConvertTo-YamlScalar $tenderId)")
    $lines.Add("match_reasons:")
    foreach ($reason in $Reasons) {
        $lines.Add("  - $(ConvertTo-YamlScalar $reason)")
    }
    $lines.Add("classification_reasons:")
    foreach ($signal in @($Classification.consulting_signals)) {
        $lines.Add("  - $(ConvertTo-YamlScalar "consulting signal: $signal")")
    }
    foreach ($signal in @($Classification.technical_context_signals)) {
        $lines.Add("  - $(ConvertTo-YamlScalar "technical context signal: $signal")")
    }
    foreach ($signal in @($Classification.construction_signals)) {
        $lines.Add("  - $(ConvertTo-YamlScalar "construction signal: $signal")")
    }
    foreach ($signal in @($Classification.supply_signals)) {
        $lines.Add("  - $(ConvertTo-YamlScalar "supply signal: $signal")")
    }
    $lines | Set-Content -LiteralPath $path -Encoding UTF8
    return $path
}

$criteriaData = Read-JsonFile $Criteria ([pscustomobject]@{})
$stateData = Read-JsonFile $State ([pscustomobject]@{ seen_tender_ids = @() })
$seen = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($id in @($stateData.seen_tender_ids)) {
    [void]$seen.Add([string]$id)
}

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-WebRequest -Uri "$BaseUrl/tenders" -UseBasicParsing -WebSession $session -Headers $Headers | Out-Null
$auth = Invoke-RestMethod -Uri "$BaseUrl/procurementui/authenticate" -Method Post -Body '{"rpid":"GUEST"}' -ContentType "application/json" -WebSession $session -Headers $Headers
$token = $auth.jwttoken
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Guest authentication did not return a token."
}
$Headers["Authorization"] = "Bearer $token"

$now = Get-Date
$matches = New-Object System.Collections.Generic.List[object]
$openTenderRecords = New-Object System.Collections.Generic.List[object]
$openTenderIds = New-Object 'System.Collections.Generic.HashSet[string]'
$candidateBucketCounts = [ordered]@{
    "prime-consultant-fit" = 0
    "partner-or-subconsultant-fit" = 0
    "needs-review" = 0
    "off-profile-consulting" = 0
    "likely-skip" = 0
}
for ($page = 1; $page -le $MaxPages; $page++) {
    $query = [uri]::EscapeDataString($Keyword)
    $url = "$BaseUrl/procurementui/tenders?page=$page&numberOfRecords=$PageSize&sortType=POSTED_DATE_DESC&keyword=$query"
    $data = Invoke-RestMethod -Uri $url -Method Post -Body "null" -ContentType "application/json" -WebSession $session -Headers $Headers
    $rows = @($data.tenderDataList)
    if ($rows.Count -eq 0) {
        break
    }
    foreach ($row in $rows) {
        $tenderId = [string]$row.tenderId
        if ([string]::IsNullOrWhiteSpace($tenderId)) {
            continue
        }
        if (([string]$row.tenderStatus).ToLowerInvariant() -ne "open") {
            continue
        }
        if ($openTenderIds.Contains($tenderId)) {
            continue
        }
        [void]$openTenderIds.Add($tenderId)

        $match = Test-TenderMatch $row $criteriaData $now
        $recordTender = $row
        $classification = $null
        $bucket = "likely-skip"
        if (-not $match.Match) {
            $bucket = Get-CandidateBucket $match $classification $row
            $candidateBucketCounts[$bucket] = [int]$candidateBucketCounts[$bucket] + 1
            $openTenderRecords.Add((New-OpenTenderRecord $recordTender $now $bucket $match $classification))
            continue
        }
        $detailUrl = "$BaseUrl/procurementui/tenders?tenderId=$([uri]::EscapeDataString($tenderId))"
        $detailData = Invoke-RestMethod -Uri $detailUrl -Method Post -Body "null" -ContentType "application/json" -WebSession $session -Headers $Headers
        $detail = @($detailData.tenderDataList)[0]
        if ($null -eq $detail) {
            $detail = $row
        }
        $detailMatch = Test-TenderMatch $detail $criteriaData $now
        $recordTender = $detail
        if ($detailMatch.Match) {
            $classification = Get-OpportunityClassification $detail
            $bucket = Get-CandidateBucket $detailMatch $classification $detail
            if ($bucket -eq "prime-consultant-fit" -and (-not $seen.Contains($tenderId) -or $IncludeSeen)) {
                $matches.Add([pscustomobject]@{ tender = $detail; reasons = @($detailMatch.Reasons); classification = $classification })
            }
        }
        else {
            $bucket = Get-CandidateBucket $detailMatch $classification $detail
        }
        $candidateBucketCounts[$bucket] = [int]$candidateBucketCounts[$bucket] + 1
        $openTenderRecords.Add((New-OpenTenderRecord $recordTender $now $bucket $detailMatch $classification))
    }
}

$summaryDir = Join-Path $ProposalRepo "proposals\outputs\ns-tenders"
New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null
$snapshot = Write-OpenTenderSnapshot $ProposalRepo $now @($openTenderRecords.ToArray()) $candidateBucketCounts
$generatedBriefs = New-Object System.Collections.Generic.List[string]

foreach ($item in $matches) {
    if (-not $DryRun) {
        $brief = Write-TenderBrief $item.tender ([string[]]$item.reasons) $item.classification $ProposalRepo
        $generatedBriefs.Add([string]$brief)
        [void]$seen.Add([string]$item.tender.tenderId)
    }
}

$summary = [pscustomobject]@{
    ran_at = $now.ToString("s")
    dry_run = [bool]$DryRun
    open_tender_count = $openTenderRecords.Count
    open_tender_snapshot_path = $snapshot.snapshot_path
    open_tender_latest_path = $snapshot.latest_path
    candidate_bucket_counts = $candidateBucketCounts
    matches = @($matches.ToArray())
    generated_briefs = @($generatedBriefs.ToArray())
    generated_analyses = @()
}
$summaryPath = Join-Path $summaryDir ("ns-tender-monitor-" + $now.ToString("yyyyMMdd-HHmmss") + ".json")
Write-JsonFile $summaryPath $summary

if (-not $DryRun) {
    $stateOut = [pscustomobject]@{
        seen_tender_ids = @($seen | Sort-Object)
        last_run_at = $now.ToString("s")
    }
    Write-JsonFile $State $stateOut
}

[pscustomobject]@{
    matches = $matches.Count
    open_tender_count = $openTenderRecords.Count
    open_tender_snapshot_path = $snapshot.snapshot_path
    open_tender_latest_path = $snapshot.latest_path
    candidate_bucket_counts = $candidateBucketCounts
    generated_briefs = @($generatedBriefs.ToArray())
    generated_analyses = @()
    summary_path = $summaryPath
    dry_run = [bool]$DryRun
} | ConvertTo-Json -Depth 8

using System.Text;
using System.Text.Json;

namespace ProposalAgent.Core;

public sealed class NsTenderMonitorImporter
{
    public IReadOnlyList<string> Import(string monitorJsonPath, string outputDirectory)
    {
        Directory.CreateDirectory(outputDirectory);
        using var stream = File.OpenRead(monitorJsonPath);
        using var document = JsonDocument.Parse(stream);
        if (!document.RootElement.TryGetProperty("matches", out var matches) ||
            matches.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        var written = new List<string>();
        foreach (var match in matches.EnumerateArray())
        {
            if (!match.TryGetProperty("tender", out var tender))
            {
                continue;
            }

            var tenderId = GetString(tender, "tenderId");
            var title = GetString(tender, "title");
            if (string.IsNullOrWhiteSpace(tenderId) || string.IsNullOrWhiteSpace(title))
            {
                continue;
            }

            var buyer = GetNestedString(tender, "procumentEntityData", "name");
            var description = GetString(tender, "description");
            var closing = GetString(tender, "closingDate");
            var posted = GetString(tender, "createdDate");
            var solicitationType = GetString(tender, "solicitationType");
            var portalUrl = $"https://procurement-portal.novascotia.ca/tenders/{tenderId}";
            var classification = Classify(title, description, solicitationType);
            if (!classification.IsActionable)
            {
                continue;
            }

            var outputPath = Path.Combine(outputDirectory, $"{Slug(tenderId + "-" + title)}.yaml");
            var existingPaths = FindExistingBriefsForTender(outputDirectory, tenderId).ToList();
            var existingDocumentPaths = existingPaths
                .SelectMany(path => SimpleYaml.ReadList(path, "document_paths"))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();
            foreach (var existingPath in existingPaths.Where(path => !string.Equals(path, outputPath, StringComparison.OrdinalIgnoreCase)))
            {
                File.Delete(existingPath);
            }
            File.WriteAllText(outputPath, RenderYaml(
                tenderId,
                title,
                buyer,
                closing,
                posted,
                solicitationType,
                description,
                portalUrl,
                classification,
                existingDocumentPaths));
            written.Add(outputPath);
        }

        return written;
    }

    private static IEnumerable<string> FindExistingBriefsForTender(string outputDirectory, string tenderId)
    {
        if (!Directory.Exists(outputDirectory))
        {
            yield break;
        }

        var expectedLine = $"tender_id: \"{Escape(tenderId)}\"";
        foreach (var path in Directory.EnumerateFiles(outputDirectory, "*.yaml"))
        {
            if (File.ReadLines(path).Any(line => string.Equals(line.Trim(), expectedLine, StringComparison.OrdinalIgnoreCase)))
            {
                yield return path;
            }
        }
    }

    private static TenderClassification Classify(string title, string description, string solicitationType)
    {
        var text = $"{title} {description} {solicitationType}";
        var constructionSignals = new[]
        {
            "construction", "asphalt", "repaving", "bridge replacement", "window replacement",
            "recladding", "culvert", "gravelling", "utility extensions", "sprinkler work",
            "supply and installation", "supply & installation", "materials, labour and equipment"
        };
        var supplySignals = new[]
        {
            "supply of", "supply & programming", "radios", "rescue tools", "vehicle",
            "tractor", "electrical supplies", "lamps and ballasts", "media destruction", "vendor"
        };
        var consultingSignals = new[]
        {
            "feasibility", "study", "assessment", "capacity study", "assimilative capacity",
            "design study", "design services", "engineering services", "consulting",
            "consultant", "report", "master plan", "planning", "model", "modelling",
            "stormwater management project", "condition assessment", "hydraulic"
        };
        var constructionHits = constructionSignals
            .Where(signal => text.Contains(signal, StringComparison.OrdinalIgnoreCase))
            .ToList();
        var supplyHits = supplySignals
            .Where(signal => text.Contains(signal, StringComparison.OrdinalIgnoreCase))
            .ToList();
        var consultingHits = consultingSignals
            .Where(signal => text.Contains(signal, StringComparison.OrdinalIgnoreCase))
            .ToList();
        if (title.Contains("design", StringComparison.OrdinalIgnoreCase))
        {
            consultingHits.Add("design");
        }

        if (supplyHits.Count > 0 && consultingHits.Count == 0)
        {
            return new TenderClassification(
                "supply-equipment-services",
                "likely-skip-unless-supplier",
                "high",
                "Looks like supply, equipment, goods, or vendor procurement rather than professional consulting.",
                supplyHits.Select(hit => $"supply signal: {hit}").ToList(),
                false);
        }

        if (constructionHits.Count > 0 && consultingHits.Count == 0)
        {
            return new TenderClassification(
                "construction-contractor-led",
                "partner-or-subconsultant-fit",
                "high",
                "Looks construction or contractor led; bid directly only with construction capacity or a contractor partner.",
                constructionHits.Select(hit => $"construction signal: {hit}").ToList(),
                false);
        }

        if (consultingHits.Count > 0 && supplyHits.Count == 0)
        {
            return new TenderClassification(
                "design-study-consulting",
                "prime-consultant-fit",
                constructionHits.Count > 0 ? "medium" : "high",
                "Looks like a consulting, design, study, assessment, or engineering-services opportunity.",
                consultingHits.Select(hit => $"consulting signal: {hit}").ToList(),
                true);
        }

        if (consultingHits.Count > 0)
        {
            return new TenderClassification(
                "mixed-consulting-and-delivery",
                "review-for-prime-or-subconsultant-role",
                "medium",
                "Has consulting/design language plus supply, vendor, installation, or delivery language.",
                consultingHits.Select(hit => $"consulting signal: {hit}")
                    .Concat(supplyHits.Select(hit => $"supply signal: {hit}"))
                    .ToList(),
                false);
        }

        return new TenderClassification(
            "unknown",
            "review-required",
            "low",
            "Insufficient text to classify bid fit; manually review tender documents.",
            [],
            false);
    }

    private static string RenderYaml(
        string tenderId,
        string title,
        string buyer,
        string closing,
        string posted,
        string solicitationType,
        string description,
        string portalUrl,
        TenderClassification classification,
        IReadOnlyList<string> documentPaths)
    {
        var closeDate = closing.Length >= 10 ? closing[..10] : "";
        var builder = new StringBuilder();
        builder.AppendLine($"client: \"{Escape(buyer)}\"");
        builder.AppendLine($"opportunity: \"{Escape(title)}\"");
        if (!string.IsNullOrWhiteSpace(closeDate))
        {
            builder.AppendLine($"due_date: \"{closeDate}\"");
        }
        builder.AppendLine("industry: \"Civil engineering\"");
        builder.AppendLine("service_line: \"infrastructure\"");
        builder.AppendLine("project_region: \"atlantic\"");
        builder.AppendLine("rfp_text: >");
        builder.AppendLine($"  Tender {Escape(tenderId)}: {Escape(title)}.");
        builder.AppendLine($"  Solicitation type: {Escape(solicitationType)}.");
        builder.AppendLine($"  Procurement entity: {Escape(buyer)}.");
        builder.AppendLine("  Status: OPEN.");
        builder.AppendLine($"  Posted: {Escape(posted)}.");
        builder.AppendLine($"  Closing: {Escape(closing)}.");
        builder.AppendLine($"  Portal URL: {Escape(portalUrl)}.");
        builder.AppendLine($"  Description: {Escape(description)}.");
        builder.AppendLine($"pursuit_type: \"{classification.PursuitType}\"");
        builder.AppendLine($"bid_fit: \"{classification.BidFit}\"");
        builder.AppendLine($"classification_confidence: \"{classification.Confidence}\"");
        builder.AppendLine($"classification_note: \"{Escape(classification.Note)}\"");
        builder.AppendLine("goals:");
        builder.AppendLine("  - Review tender notice and documents for fit.");
        builder.AppendLine("  - Confirm eligibility, submission method, schedule, and compliance requirements.");
        builder.AppendLine("scope:");
        builder.AppendLine("  - Capture tender requirements.");
        builder.AppendLine("  - Prepare pursue/no-pursue recommendation.");
        builder.AppendLine("  - Draft proposal response outline if qualified.");
        builder.AppendLine("constraints:");
        builder.AppendLine("  - Verify all tender documents directly in the Nova Scotia Procurement Portal before bidding.");
        builder.AppendLine("decision_criteria:");
        builder.AppendLine("  - Strategic fit.");
        builder.AppendLine("  - Technical capability.");
        builder.AppendLine("  - Available response time.");
        builder.AppendLine("  - Compliance requirements.");
        builder.AppendLine("source:");
        builder.AppendLine($"  portal_url: \"{Escape(portalUrl)}\"");
        builder.AppendLine($"  tender_id: \"{Escape(tenderId)}\"");
        builder.AppendLine("classification_reasons:");
        foreach (var reason in classification.Reasons)
        {
            builder.AppendLine($"  - \"{Escape(reason)}\"");
        }
        if (documentPaths.Count > 0)
        {
            builder.AppendLine("document_paths:");
            foreach (var documentPath in documentPaths)
            {
                builder.AppendLine($"  - {Escape(documentPath)}");
            }
        }
        return builder.ToString();
    }

    private static string GetString(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out var value) && value.ValueKind != JsonValueKind.Null
            ? value.ToString()
            : "";

    private static string GetNestedString(JsonElement element, string objectProperty, string propertyName) =>
        element.TryGetProperty(objectProperty, out var child) ? GetString(child, propertyName) : "";

    private static string Escape(string value) =>
        value.Replace("\"", "'", StringComparison.Ordinal).ReplaceLineEndings(" ").Trim();

    private static string Slug(string value)
    {
        var chars = value.ToLowerInvariant().Select(ch => char.IsLetterOrDigit(ch) ? ch : '-').ToArray();
        return string.Join('-', new string(chars).Split('-', StringSplitOptions.RemoveEmptyEntries));
    }

    private sealed record TenderClassification(
        string PursuitType,
        string BidFit,
        string Confidence,
        string Note,
        IReadOnlyList<string> Reasons,
        bool IsActionable);
}

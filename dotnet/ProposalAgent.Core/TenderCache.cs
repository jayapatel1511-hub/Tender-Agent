using System.Globalization;

namespace ProposalAgent.Core;

public sealed class TenderCache
{
    private readonly IDocumentTextExtractor _documentTextExtractor;

    public TenderCache(IDocumentTextExtractor? documentTextExtractor = null)
    {
        _documentTextExtractor = documentTextExtractor ?? new DocumentTextExtractor();
    }

    public IReadOnlyList<BrainRequest> LoadActiveTenderBriefs(string directory)
    {
        if (!Directory.Exists(directory))
        {
            return [];
        }

        return Directory
            .EnumerateFiles(directory, "*.yaml", SearchOption.AllDirectories)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .Select(LoadYamlBrief)
            .ToList();
    }

    public BrainRequest LoadYamlBrief(string path)
    {
        var fields = SimpleYaml.Read(path);
        var documentPaths = ResolveDocumentPaths(path, SimpleYaml.ReadList(path, "document_paths"));
        var documentText = string.Join(
            "\n\n",
            documentPaths.Select(documentPath => _documentTextExtractor.ExtractText(documentPath))
                .Where(text => !string.IsNullOrWhiteSpace(text)));
        var tender = new TenderNotice
        {
            TenderId = fields.GetValueOrDefault("source.tender_id", ""),
            Title = fields.GetValueOrDefault("opportunity", Path.GetFileNameWithoutExtension(path)),
            Buyer = fields.GetValueOrDefault("client", ""),
            Status = ExtractAfter(fields.GetValueOrDefault("rfp_text", ""), "Status:"),
            ClosingDate = ParseDate(fields.GetValueOrDefault("due_date", "")),
            Category = fields.GetValueOrDefault("service_line", ""),
            SourceUrl = fields.GetValueOrDefault("source.portal_url", ""),
            Description = JoinText(fields.GetValueOrDefault("rfp_text", ""), documentText),
            SourcePath = path,
            PursuitType = fields.GetValueOrDefault("pursuit_type", ""),
            BidFit = fields.GetValueOrDefault("bid_fit", ""),
            ClassificationConfidence = fields.GetValueOrDefault("classification_confidence", ""),
            ClassificationNote = fields.GetValueOrDefault("classification_note", ""),
            DocumentPaths = documentPaths,
        };

        var brief = new ProposalBrief
        {
            Client = tender.Buyer,
            Opportunity = tender.Title,
            DueDate = tender.ClosingDate,
            Industry = fields.GetValueOrDefault("industry", ""),
            ServiceLine = fields.GetValueOrDefault("service_line", ""),
            ProjectRegion = fields.GetValueOrDefault("project_region", ""),
            ProjectLevel = fields.GetValueOrDefault("project_level", "local"),
            RfpText = tender.Description,
            Goals = SimpleYaml.ReadList(path, "goals"),
            Scope = SimpleYaml.ReadList(path, "scope"),
            Constraints = SimpleYaml.ReadList(path, "constraints"),
            DecisionCriteria = SimpleYaml.ReadList(path, "decision_criteria"),
        };

        return new BrainRequest { Tender = tender, Brief = brief };
    }

    private static IReadOnlyList<string> ResolveDocumentPaths(string yamlPath, IReadOnlyList<string> paths)
    {
        var yamlDirectory = Path.GetDirectoryName(Path.GetFullPath(yamlPath)) ?? Directory.GetCurrentDirectory();
        var repoRoot = FindRepoRoot(yamlDirectory);
        return paths
            .Select(path => path.Trim())
            .Where(path => path.Length > 0)
            .Select(path =>
            {
                if (Path.IsPathRooted(path))
                {
                    return path;
                }

                var relativeToYaml = Path.GetFullPath(Path.Combine(yamlDirectory, path));
                if (File.Exists(relativeToYaml))
                {
                    return relativeToYaml;
                }

                return Path.GetFullPath(Path.Combine(repoRoot, path));
            })
            .ToList();
    }

    private static string FindRepoRoot(string startDirectory)
    {
        var directory = new DirectoryInfo(startDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "TenderAgent.sln")) ||
                File.Exists(Path.Combine(directory.FullName, "ProposalAgent.sln")) ||
                Directory.Exists(Path.Combine(directory.FullName, ".git")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        return Directory.GetCurrentDirectory();
    }

    private static string JoinText(string first, string second)
    {
        var parts = new[] { first, second }.Where(part => !string.IsNullOrWhiteSpace(part));
        return string.Join("\n\n", parts);
    }

    private static DateOnly? ParseDate(string value)
    {
        if (DateOnly.TryParse(value, CultureInfo.InvariantCulture, out var date))
        {
            return date;
        }

        return null;
    }

    private static string ExtractAfter(string text, string label)
    {
        var index = text.IndexOf(label, StringComparison.OrdinalIgnoreCase);
        if (index < 0)
        {
            return "";
        }

        var start = index + label.Length;
        var end = text.IndexOf('.', start);
        return (end > start ? text[start..end] : text[start..]).Trim();
    }
}

internal static class SimpleYaml
{
    public static Dictionary<string, string> Read(string path)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var lines = File.ReadAllLines(path);
        string? blockKey = null;
        string? parent = null;
        var block = new List<string>();

        foreach (var rawLine in lines)
        {
            var line = rawLine.TrimEnd();
            if (blockKey is not null)
            {
                if (rawLine.StartsWith("  ", StringComparison.Ordinal) || string.IsNullOrWhiteSpace(rawLine))
                {
                    block.Add(line.Trim());
                    continue;
                }

                result[blockKey] = string.Join(" ", block).Trim();
                blockKey = null;
                block.Clear();
            }

            if (string.IsNullOrWhiteSpace(line) || line.TrimStart().StartsWith("-", StringComparison.Ordinal))
            {
                continue;
            }

            var trimmed = line.Trim();
            if (!rawLine.StartsWith(" ", StringComparison.Ordinal) && trimmed.EndsWith(":", StringComparison.Ordinal))
            {
                parent = trimmed.TrimEnd(':');
                continue;
            }

            var separator = trimmed.IndexOf(':');
            if (separator <= 0)
            {
                continue;
            }

            var key = trimmed[..separator].Trim();
            var value = trimmed[(separator + 1)..].Trim();
            if (rawLine.StartsWith("  ", StringComparison.Ordinal) && parent is not null)
            {
                key = $"{parent}.{key}";
            }

            if (value is ">" or "|")
            {
                blockKey = key;
                continue;
            }

            result[key] = Unquote(value);
        }

        if (blockKey is not null)
        {
            result[blockKey] = string.Join(" ", block).Trim();
        }

        return result;
    }

    public static IReadOnlyList<string> ReadList(string path, string key)
    {
        var lines = File.ReadAllLines(path);
        var items = new List<string>();
        var inList = false;
        foreach (var rawLine in lines)
        {
            var trimmed = rawLine.Trim();
            if (!rawLine.StartsWith(" ", StringComparison.Ordinal) &&
                trimmed.Equals($"{key}:", StringComparison.OrdinalIgnoreCase))
            {
                inList = true;
                continue;
            }

            if (inList && !rawLine.StartsWith(" ", StringComparison.Ordinal) && trimmed.Length > 0)
            {
                break;
            }

            if (inList && trimmed.StartsWith("- ", StringComparison.Ordinal))
            {
                items.Add(Unquote(trimmed[2..].Trim()));
            }
        }

        return items;
    }

    private static string Unquote(string value) => value.Trim().Trim('"').Trim('\'');
}

using System.Text.RegularExpressions;

namespace ProposalAgent.Core;

public sealed partial class ProposalAnalyzer
{
    private static readonly HashSet<string> Stopwords = new(StringComparer.OrdinalIgnoreCase)
    {
        "about", "after", "also", "and", "are", "for", "from", "into", "must", "our",
        "shall", "that", "the", "this", "with", "will", "your"
    };

    private static readonly Dictionary<string, string[]> RoleRules = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Project Manager"] = ["schedule", "budget", "stakeholder", "coordination", "delivery"],
        ["Technical Lead"] = ["design", "model", "analysis", "engineering", "technical"],
        ["Subject Matter Expert"] = ["specialist", "expert", "review", "compliance", "standard"],
        ["Proposal Manager"] = ["rfp", "submission", "proposal", "compliance", "forms"],
        ["Quality Reviewer"] = ["quality", "qa", "qc", "risk", "review"],
    };

    public ProposalAnalysis Analyze(ProposalBrief brief)
    {
        var text = CombinedText(brief);
        var keywords = Keywords(text);
        var requiredRoles = RequiredRoles(text, keywords);
        return new ProposalAnalysis
        {
            Keywords = keywords,
            RequiredRoles = requiredRoles,
            WinThemes = WinThemes(brief, keywords),
            Risks = Risks(brief, text),
        };
    }

    private static string CombinedText(ProposalBrief brief)
    {
        var parts = new List<string?>
        {
            brief.Client,
            brief.Opportunity,
            brief.Industry,
            brief.RfpText,
        };
        parts.AddRange(brief.Goals);
        parts.AddRange(brief.Scope);
        parts.AddRange(brief.Constraints);
        parts.AddRange(brief.DecisionCriteria);
        return string.Join(" ", parts.Where(part => !string.IsNullOrWhiteSpace(part)));
    }

    private static IReadOnlyList<string> Keywords(string text)
    {
        return WordPattern()
            .Matches(text.ToLowerInvariant())
            .Select(match => match.Value)
            .Where(word => !Stopwords.Contains(word))
            .GroupBy(word => word)
            .OrderByDescending(group => group.Count())
            .ThenBy(group => group.Key)
            .Take(12)
            .Select(group => group.Key)
            .ToList();
    }

    private static IReadOnlyList<string> RequiredRoles(string text, IReadOnlyList<string> keywords)
    {
        var signalWords = WordPattern()
            .Matches(text.ToLowerInvariant())
            .Select(match => match.Value)
            .Concat(keywords)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var roles = RoleRules
            .Where(rule => rule.Value.Any(signalWords.Contains))
            .Select(rule => rule.Key)
            .ToList();

        return roles.Count > 0
            ? roles
            : ["Project Manager", "Technical Lead", "Proposal Manager"];
    }

    private static IReadOnlyList<string> WinThemes(ProposalBrief brief, IReadOnlyList<string> keywords)
    {
        var themes = new List<string>();
        if (brief.DecisionCriteria.Count > 0)
        {
            themes.Add("Directly answer evaluator criteria: " + string.Join("; ", CleanItems(brief.DecisionCriteria)) + ".");
        }

        if (brief.Goals.Count > 0)
        {
            themes.Add("Anchor the proposal around the client's outcomes: " + string.Join("; ", CleanItems(brief.Goals)) + ".");
        }

        if (keywords.Count > 0)
        {
            themes.Add("Use client language consistently: " + string.Join(", ", keywords.Take(5)) + ".");
        }

        return themes;
    }

    private static IReadOnlyList<string> Risks(ProposalBrief brief, string text)
    {
        var risks = new List<string>();
        if (brief.AvailablePeople.Count == 0)
        {
            risks.Add("No team roster was provided, so staffing recommendations are role-based only.");
        }

        if (brief.Scope.Count == 0)
        {
            risks.Add("Scope is incomplete; confirm inclusions, exclusions, and deliverables.");
        }

        if (text.Contains("mandatory", StringComparison.OrdinalIgnoreCase) ||
            text.Contains("shall", StringComparison.OrdinalIgnoreCase))
        {
            risks.Add("Mandatory requirements may exist; run a compliance review before submission.");
        }

        if (brief.DecisionCriteria.Count == 0)
        {
            risks.Add("Evaluation criteria are missing; win themes may need refinement.");
        }

        return risks;
    }

    private static IReadOnlyList<string> CleanItems(IEnumerable<string> items) =>
        items.Select(item => item.Trim().TrimEnd('.')).Where(item => item.Length > 0).ToList();

    [GeneratedRegex("[A-Za-z][A-Za-z0-9-]{2,}")]
    private static partial Regex WordPattern();
}

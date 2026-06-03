using System.Globalization;

namespace ProposalAgent.Core;

public sealed record ProposalBrief
{
    public string Client { get; init; } = "";
    public string Opportunity { get; init; } = "";
    public string RfpText { get; init; } = "";
    public DateOnly? DueDate { get; init; }
    public decimal? Budget { get; init; }
    public string Industry { get; init; } = "";
    public string ServiceLine { get; init; } = "";
    public string ProjectRegion { get; init; } = "";
    public string ProjectLevel { get; init; } = "local";
    public decimal? EstimatedValue { get; init; }
    public string ProposalLead { get; init; } = "";
    public string PreferredPm { get; init; } = "";
    public string ClientRelationshipOwner { get; init; } = "";
    public IReadOnlyList<string> Goals { get; init; } = [];
    public IReadOnlyList<string> Scope { get; init; } = [];
    public IReadOnlyList<string> Constraints { get; init; } = [];
    public IReadOnlyList<string> DecisionCriteria { get; init; } = [];
    public IReadOnlyList<PersonProfile> AvailablePeople { get; init; } = [];
}

public sealed record PersonProfile
{
    public string Name { get; init; } = "";
    public string Role { get; init; } = "";
    public string Company { get; init; } = "";
    public string Region { get; init; } = "";
    public string Office { get; init; } = "";
    public string OperatingCentre { get; init; } = "";
    public string Seniority { get; init; } = "";
    public bool CanLeadProposals { get; init; }
    public IReadOnlyList<string> Skills { get; init; } = [];
    public IReadOnlyList<string> Industries { get; init; } = [];
    public IReadOnlyList<string> PastProjects { get; init; } = [];
    public IReadOnlyList<string> ClientRelationships { get; init; } = [];
    public string Availability { get; init; } = "unknown";
}

public sealed record ProposalAnalysis
{
    public IReadOnlyList<string> Keywords { get; init; } = [];
    public IReadOnlyList<string> RequiredRoles { get; init; } = [];
    public IReadOnlyList<string> WinThemes { get; init; } = [];
    public IReadOnlyList<string> Risks { get; init; } = [];
}

public sealed record TeamRecommendation
{
    public required PersonProfile Person { get; init; }
    public int Score { get; init; }
    public IReadOnlyList<string> Reasons { get; init; } = [];
    public bool Eligible { get; init; } = true;
    public IReadOnlyList<string> Restrictions { get; init; } = [];
}

public sealed record PursuitDecision
{
    public string Recommendation { get; init; } = "Pursue with conditions";
    public int Score { get; init; }
    public IReadOnlyList<string> Reasons { get; init; } = [];
    public IReadOnlyList<string> Conditions { get; init; } = [];
}

public sealed record OrgRecommendation
{
    public string ProjectLevel { get; init; } = "local";
    public string ProjectRegion { get; init; } = "";
    public IReadOnlyList<string> EligibleOperatingCentres { get; init; } = [];
    public IReadOnlyList<string> EligibleCompanies { get; init; } = [];
    public IReadOnlyList<string> ApprovalsRequired { get; init; } = [];
    public IReadOnlyList<string> Rationale { get; init; } = [];
}

public sealed record ProposalSection
{
    public required string Heading { get; init; }
    public IReadOnlyList<string> Bullets { get; init; } = [];
}

public sealed record AgentRun
{
    public required string AgentName { get; init; }
    public required string SkillName { get; init; }
    public required string Summary { get; init; }
}

public sealed record ProposalDraft
{
    public required string Title { get; init; }
    public IReadOnlyList<string> Questions { get; init; } = [];
    public required ProposalAnalysis Analysis { get; init; }
    public PursuitDecision? PursuitDecision { get; init; }
    public OrgRecommendation? OrgRecommendation { get; init; }
    public IReadOnlyList<TeamRecommendation> RecommendedTeam { get; init; } = [];
    public IReadOnlyList<ProposalSection> Sections { get; init; } = [];
    public IReadOnlyList<AgentRun> AgentRuns { get; init; } = [];

    public string ToMarkdown()
    {
        var lines = new List<string> { $"# {Title}", "" };

        if (AgentRuns.Count > 0)
        {
            lines.AddRange(["## Agent Workflow", ""]);
            lines.AddRange(AgentRuns.Select(run => $"- {run.AgentName} ({run.SkillName}): {run.Summary}"));
            lines.Add("");
        }

        if (Questions.Count > 0)
        {
            lines.AddRange(["## Follow-up Questions", ""]);
            lines.AddRange(Questions.Select(question => $"- {question}"));
            lines.Add("");
        }

        lines.AddRange(["## Opportunity Analysis", ""]);
        if (PursuitDecision is not null)
        {
            lines.Add($"- Pursuit decision: {PursuitDecision.Recommendation} (score {PursuitDecision.Score})");
            lines.AddRange(PursuitDecision.Reasons.Select(reason => $"- Pursuit reason: {reason}"));
            lines.AddRange(PursuitDecision.Conditions.Select(condition => $"- Pursuit condition: {condition}"));
        }

        if (OrgRecommendation is not null)
        {
            if (OrgRecommendation.EligibleOperatingCentres.Count > 0)
            {
                lines.Add("- Eligible OCs: " + string.Join(", ", OrgRecommendation.EligibleOperatingCentres));
            }

            if (OrgRecommendation.EligibleCompanies.Count > 0)
            {
                lines.Add("- Eligible companies: " + string.Join(", ", OrgRecommendation.EligibleCompanies));
            }

            lines.AddRange(OrgRecommendation.ApprovalsRequired.Select(approval => $"- Approval required: {approval}"));
        }

        if (Analysis.Keywords.Count > 0)
        {
            lines.Add("- Keywords: " + string.Join(", ", Analysis.Keywords));
        }

        if (Analysis.RequiredRoles.Count > 0)
        {
            lines.Add("- Required roles: " + string.Join(", ", Analysis.RequiredRoles));
        }

        lines.AddRange(Analysis.WinThemes.Select(theme => $"- Win theme: {theme}"));
        lines.AddRange(Analysis.Risks.Select(risk => $"- Risk: {risk}"));
        lines.Add("");

        if (RecommendedTeam.Count > 0)
        {
            lines.AddRange(["## Recommended Team", ""]);
            foreach (var recommendation in RecommendedTeam)
            {
                var reasons = string.Join("; ", recommendation.Reasons);
                var restrictions = recommendation.Restrictions.Count > 0
                    ? $" Restrictions: {string.Join("; ", recommendation.Restrictions)}."
                    : "";
                lines.Add(
                    $"- {recommendation.Person.Name} ({recommendation.Person.Role}) - score {recommendation.Score}: {reasons}.{restrictions}");
            }

            lines.Add("");
        }

        foreach (var section in Sections)
        {
            lines.AddRange([$"## {section.Heading}", ""]);
            lines.AddRange(section.Bullets.Select(bullet => $"- {bullet}"));
            lines.Add("");
        }

        return string.Join('\n', lines).TrimEnd() + "\n";
    }
}

public static class MoneyFormat
{
    public static string Format(decimal value) => value.ToString("C0", CultureInfo.GetCultureInfo("en-US"));
}

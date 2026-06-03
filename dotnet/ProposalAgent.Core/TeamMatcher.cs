namespace ProposalAgent.Core;

public sealed class TeamMatcher
{
    public IReadOnlyList<TeamRecommendation> Recommend(ProposalBrief brief, ProposalAnalysis analysis)
    {
        var keywords = analysis.Keywords.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var requiredRoles = analysis.RequiredRoles.ToHashSet(StringComparer.OrdinalIgnoreCase);
        var industry = brief.Industry;

        return brief.AvailablePeople
            .Select(person => ScorePerson(person, keywords, requiredRoles, industry, brief.Client))
            .Where(recommendation => recommendation.Score > 0)
            .OrderByDescending(recommendation => recommendation.Score)
            .ThenBy(recommendation => recommendation.Person.Name)
            .Take(5)
            .ToList();
    }

    private static TeamRecommendation ScorePerson(
        PersonProfile person,
        HashSet<string> keywords,
        HashSet<string> requiredRoles,
        string industry,
        string client)
    {
        var score = 0;
        var reasons = new List<string>();

        if (requiredRoles.Contains(person.Role))
        {
            score += 25;
            reasons.Add($"matches required role {person.Role}");
        }

        var skillText = string.Join(" ", person.Skills);
        var skillMatches = keywords.Count(keyword => skillText.Contains(keyword, StringComparison.OrdinalIgnoreCase));
        if (skillMatches > 0)
        {
            score += skillMatches * 10;
            reasons.Add($"matches {skillMatches} proposal keyword(s)");
        }

        if (!string.IsNullOrWhiteSpace(industry) &&
            person.Industries.Any(item => item.Equals(industry, StringComparison.OrdinalIgnoreCase)))
        {
            score += 10;
            reasons.Add($"has {industry} experience");
        }

        if (!string.IsNullOrWhiteSpace(client) &&
            person.ClientRelationships.Any(item => item.Contains(client, StringComparison.OrdinalIgnoreCase)))
        {
            score += 15;
            reasons.Add("has a relevant client relationship");
        }

        if (person.Availability.Equals("available", StringComparison.OrdinalIgnoreCase))
        {
            score += 10;
            reasons.Add("is available");
        }
        else if (person.Availability.Equals("limited", StringComparison.OrdinalIgnoreCase))
        {
            score += 3;
            reasons.Add("has limited availability");
        }

        return new TeamRecommendation
        {
            Person = person,
            Score = score,
            Reasons = reasons,
        };
    }
}

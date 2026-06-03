namespace ProposalAgent.Core;

public sealed class PursuitEvaluator
{
    public PursuitDecision Evaluate(ProposalBrief brief)
    {
        var score = 50;
        var reasons = new List<string>();
        var conditions = new List<string>();

        if (brief.ClientRelationshipOwner.Length > 0)
        {
            score += 15;
            reasons.Add($"Known client relationship owner: {brief.ClientRelationshipOwner}.");
        }
        else
        {
            conditions.Add("Confirm client relationship owner.");
        }

        if (brief.DecisionCriteria.Count > 0)
        {
            score += 10;
            reasons.Add("Evaluation criteria are available.");
        }
        else
        {
            score -= 10;
            conditions.Add("Clarify evaluation criteria before committing major effort.");
        }

        if (brief.Scope.Count > 0)
        {
            score += 10;
            reasons.Add("Initial scope is defined.");
        }
        else
        {
            score -= 10;
            conditions.Add("Define scope, exclusions, and deliverables.");
        }

        if (brief.AvailablePeople.Count > 0)
        {
            score += 10;
            reasons.Add("Team roster is available for matching.");
        }

        if (brief.DueDate is null)
        {
            score -= 10;
            conditions.Add("Confirm submission deadline.");
        }

        score = Math.Clamp(score, 0, 100);
        var recommendation = score switch
        {
            >= 75 => "Pursue",
            >= 45 => "Pursue with conditions",
            _ => "Do not pursue yet",
        };

        return new PursuitDecision
        {
            Recommendation = recommendation,
            Score = score,
            Reasons = reasons,
            Conditions = conditions,
        };
    }
}

namespace ProposalAgent.Core;

public sealed class ProposalAgent
{
    private readonly ProposalAnalyzer _analyzer = new();
    private readonly PursuitEvaluator _pursuitEvaluator = new();
    private readonly TeamMatcher _teamMatcher = new();

    public ProposalDraft Draft(ProposalBrief brief)
    {
        var analysis = _analyzer.Analyze(brief);
        var pursuit = _pursuitEvaluator.Evaluate(brief);
        var org = BuildOrgRecommendation(brief);
        var team = _teamMatcher.Recommend(brief, analysis);
        var sections = BuildSections(brief, analysis, team, pursuit, org);

        return new ProposalDraft
        {
            Title = Title(brief),
            Questions = Questions(brief),
            Analysis = analysis,
            PursuitDecision = pursuit,
            OrgRecommendation = org,
            RecommendedTeam = team,
            Sections = sections,
            AgentRuns =
            [
                Run("Oscar Martinez Analysis Agent", "Opportunity Analysis",
                    $"Found {analysis.Keywords.Count} keywords, {analysis.RequiredRoles.Count} required roles, and {analysis.Risks.Count} risks."),
                Run("David Wallace Executive Review Agent", "Pursuit Review",
                    $"Recommended '{pursuit.Recommendation}' with score {pursuit.Score}."),
                Run("Dwight Schrute Org Rules Agent", "Company Rules",
                    "Prepared first-pass region and service-line routing."),
                Run("Michael Scott Staffing Agent", "Team Matching",
                    $"Ranked {team.Count} people for the opportunity."),
                Run("Dwight Schrute Structure Agent", "Proposal Structure",
                    $"Built {sections.Count} proposal sections."),
            ],
        };
    }

    private static string Title(ProposalBrief brief)
    {
        if (!string.IsNullOrWhiteSpace(brief.Client) && !string.IsNullOrWhiteSpace(brief.Opportunity))
        {
            return $"Proposal for {brief.Client}: {brief.Opportunity}";
        }

        return !string.IsNullOrWhiteSpace(brief.Opportunity) ? $"Proposal: {brief.Opportunity}" : "Proposal Draft";
    }

    private static IReadOnlyList<string> Questions(ProposalBrief brief)
    {
        var questions = new List<string>();
        if (string.IsNullOrWhiteSpace(brief.Client)) questions.Add("Who is the client or buying organization?");
        if (brief.DueDate is null) questions.Add("What is the submission deadline?");
        if (brief.Budget is null) questions.Add("Is there a target budget or fee range?");
        if (brief.Goals.Count == 0) questions.Add("What outcomes matter most to the client?");
        if (brief.DecisionCriteria.Count == 0) questions.Add("How will the client score or compare proposals?");
        if (brief.Scope.Count == 0) questions.Add("What work should be included or excluded from scope?");
        if (string.IsNullOrWhiteSpace(brief.ProjectRegion)) questions.Add("What region owns the project?");
        if (string.IsNullOrWhiteSpace(brief.ServiceLine)) questions.Add("Which service line should own the pursuit?");
        return questions;
    }

    private static OrgRecommendation BuildOrgRecommendation(ProposalBrief brief)
    {
        var rationale = new List<string>();
        if (!string.IsNullOrWhiteSpace(brief.ProjectRegion))
        {
            rationale.Add($"Route through the {brief.ProjectRegion} region first.");
        }

        if (!string.IsNullOrWhiteSpace(brief.ServiceLine))
        {
            rationale.Add($"Assign ownership to the {brief.ServiceLine} service line.");
        }

        var approvals = new List<string>();
        if (brief.ProjectLevel.Equals("national", StringComparison.OrdinalIgnoreCase))
        {
            approvals.Add("National practice lead approval");
        }

        if (brief.EstimatedValue is >= 100000)
        {
            approvals.Add("Executive approval for high-value pursuit");
        }

        return new OrgRecommendation
        {
            ProjectLevel = brief.ProjectLevel,
            ProjectRegion = brief.ProjectRegion,
            EligibleOperatingCentres = string.IsNullOrWhiteSpace(brief.ProjectRegion) ? [] : [$"{brief.ProjectRegion} operating centre"],
            EligibleCompanies = [],
            ApprovalsRequired = approvals,
            Rationale = rationale,
        };
    }

    private static IReadOnlyList<ProposalSection> BuildSections(
        ProposalBrief brief,
        ProposalAnalysis analysis,
        IReadOnlyList<TeamRecommendation> team,
        PursuitDecision pursuit,
        OrgRecommendation org)
    {
        return
        [
            new ProposalSection
            {
                Heading = "Pursuit Strategy",
                Bullets = BuildPursuitBullets(pursuit, org),
            },
            new ProposalSection
            {
                Heading = "Executive Summary",
                Bullets = BuildExecutiveSummary(brief, analysis),
            },
            new ProposalSection
            {
                Heading = "Understanding of Need",
                Bullets = BuildUnderstanding(brief, analysis),
            },
            new ProposalSection
            {
                Heading = "Proposed Approach",
                Bullets = BuildApproach(brief, analysis),
            },
            new ProposalSection
            {
                Heading = "Team Structure",
                Bullets = BuildTeamSection(analysis, team, org),
            },
            new ProposalSection
            {
                Heading = "Schedule and Budget",
                Bullets = BuildScheduleAndBudget(brief),
            },
            new ProposalSection
            {
                Heading = "Why This Team",
                Bullets = BuildWhyUs(brief, analysis),
            },
        ];
    }

    private static IReadOnlyList<string> BuildPursuitBullets(PursuitDecision pursuit, OrgRecommendation org)
    {
        var bullets = new List<string> { $"Decision: {pursuit.Recommendation} with score {pursuit.Score}." };
        bullets.AddRange(pursuit.Conditions);
        if (org.EligibleOperatingCentres.Count > 0)
        {
            bullets.Add($"Eligible OCs: {string.Join(", ", org.EligibleOperatingCentres)}.");
        }

        if (org.ApprovalsRequired.Count > 0)
        {
            bullets.Add($"Approvals required: {string.Join(", ", org.ApprovalsRequired)}.");
        }

        bullets.AddRange(org.Rationale);
        return bullets;
    }

    private static IReadOnlyList<string> BuildExecutiveSummary(ProposalBrief brief, ProposalAnalysis analysis)
    {
        var client = string.IsNullOrWhiteSpace(brief.Client) ? "the client" : brief.Client;
        var opportunity = string.IsNullOrWhiteSpace(brief.Opportunity) ? "this opportunity" : brief.Opportunity;
        var bullets = new List<string>
        {
            $"We understand that {client} needs support for {opportunity}.",
            "Our proposed work focuses on clear outcomes, practical delivery, and visible decision support.",
        };
        if (brief.Goals.Count > 0)
        {
            bullets.Add($"The main objective is to {brief.Goals[0].TrimEnd('.').ToLowerInvariant()}.");
        }

        if (analysis.Keywords.Count > 0)
        {
            bullets.Add($"The proposal should echo priority client language: {string.Join(", ", analysis.Keywords.Take(5))}.");
        }

        return bullets;
    }

    private static IReadOnlyList<string> BuildUnderstanding(ProposalBrief brief, ProposalAnalysis analysis)
    {
        var bullets = new List<string>();
        bullets.AddRange(brief.Goals.Select(goal => $"Client goal: {goal}"));
        bullets.AddRange(brief.Constraints.Select(constraint => $"Constraint to manage: {constraint}"));
        bullets.AddRange(analysis.WinThemes);
        if (bullets.Count == 0)
        {
            bullets.Add("Confirm project drivers, constraints, stakeholders, and success measures.");
        }

        return bullets;
    }

    private static IReadOnlyList<string> BuildApproach(ProposalBrief brief, ProposalAnalysis analysis)
    {
        var bullets = brief.Scope.Count > 0
            ? brief.Scope.Select(item => $"Task: {item}").ToList()
            :
            [
                "Confirm requirements and available background information.",
                "Develop a delivery plan with assumptions, risks, and responsibilities.",
                "Prepare proposal-ready scope, schedule, and fee language.",
            ];

        if (analysis.Risks.Count > 0)
        {
            bullets.Add("Add a compliance checkpoint before final review.");
        }

        return bullets;
    }

    private static IReadOnlyList<string> BuildTeamSection(
        ProposalAnalysis analysis,
        IReadOnlyList<TeamRecommendation> team,
        OrgRecommendation org)
    {
        var bullets = analysis.RequiredRoles.Select(role => $"Assign a {role}.").ToList();
        if (team.Count > 0)
        {
            bullets.Add($"Shortlist recommended people: {string.Join(", ", team.Take(3).Select(item => item.Person.Name))}.");
        }

        if (org.EligibleOperatingCentres.Count > 0)
        {
            bullets.Add($"Keep PM and OC selection inside: {string.Join(", ", org.EligibleOperatingCentres)}.");
        }

        bullets.Add("Map each named person to the RFP keywords, required experience, and evaluator criteria.");
        return bullets;
    }

    private static IReadOnlyList<string> BuildScheduleAndBudget(ProposalBrief brief)
    {
        var deadline = brief.DueDate is { } dueDate
            ? $"Submission target: {dueDate:yyyy-MM-dd}."
            : "Submission target: to be confirmed.";
        var budget = brief.Budget is { } value
            ? $"Budget alignment: prepare a scope suitable for approximately {MoneyFormat.Format(value)}."
            : "Budget alignment: confirm target fee range before final pricing.";
        return [deadline, budget];
    }

    private static IReadOnlyList<string> BuildWhyUs(ProposalBrief brief, ProposalAnalysis analysis)
    {
        var bullets = new List<string>
        {
            "We will keep the proposal specific, evidence-based, and easy for evaluators to score.",
            "We will make assumptions, exclusions, and handoffs explicit.",
        };
        if (brief.DecisionCriteria.Count > 0)
        {
            bullets.Add("Evaluator priorities addressed: " + string.Join("; ", brief.DecisionCriteria.Select(item => item.Trim().TrimEnd('.'))) + ".");
        }

        if (analysis.RequiredRoles.Count > 0)
        {
            bullets.Add($"The team structure covers: {string.Join(", ", analysis.RequiredRoles)}.");
        }

        return bullets;
    }

    private static AgentRun Run(string agentName, string skillName, string summary) =>
        new() { AgentName = agentName, SkillName = skillName, Summary = summary };
}

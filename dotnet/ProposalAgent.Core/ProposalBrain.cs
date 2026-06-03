namespace ProposalAgent.Core;

public sealed class ProposalBrain(ILocalAiClient? localAiClient = null)
{
    private readonly ILocalAiClient _localAiClient = localAiClient ?? new NullLocalAiClient();
    private readonly ProposalAgent _proposalAgent = new();

    public async Task<BrainResult> AnalyzeAsync(BrainRequest request, CancellationToken cancellationToken = default)
    {
        var draft = _proposalAgent.Draft(request.Brief);
        var requirements = ExtractRequirements(request);
        var compliance = BuildCompliance(request, requirements);
        var risks = BuildRisks(request, requirements, compliance);
        var questions = BuildQuestions(request, requirements, risks);
        var ai = request.UseLocalAi
            ? await _localAiClient.CompleteAsync(BuildAiRequest(request, requirements, risks), cancellationToken)
            : new LocalAiResponse("", Available: false, Status: "local AI not requested");

        return new BrainResult
        {
            Tender = request.Tender,
            Draft = draft,
            Requirements = requirements,
            ComplianceChecklist = compliance,
            Risks = risks,
            QuestionsForClient = questions,
            LocalAiSummary = ai.Text,
            AiStatus = ai.Status,
        };
    }

    private static IReadOnlyList<RequirementItem> ExtractRequirements(BrainRequest request)
    {
        var text = request.Brief.RfpText;
        var items = new List<RequirementItem>();
        AddIf(items, request.Tender.ClosingDate is not null, "Schedule", "Submission deadline identified.", true,
            request.Tender.ClosingDate?.ToString("yyyy-MM-dd") ?? "");
        AddIf(items, text.Contains("portal", StringComparison.OrdinalIgnoreCase), "Submission",
            "Verify submission method and portal access before committing.", true, SentenceWith(text, "portal"));
        AddIf(items, text.Contains("mandatory", StringComparison.OrdinalIgnoreCase) ||
                     text.Contains("must", StringComparison.OrdinalIgnoreCase) ||
                     text.Contains("shall", StringComparison.OrdinalIgnoreCase), "Mandatory",
            "Mandatory language appears in tender/RFP text.", true, FirstSignal(text, ["mandatory", "must", "shall"]));
        AddIf(items, text.Contains("addenda", StringComparison.OrdinalIgnoreCase), "Addenda",
            "Monitor addenda and incorporate all issued changes.", true, SentenceWith(text, "addenda"));
        AddIf(items, text.Contains("signed addenda acknowledgement", StringComparison.OrdinalIgnoreCase), "Mandatory Forms",
            "Include signed addenda acknowledgement.", true, SentenceWith(text, "signed addenda acknowledgement"));
        AddIf(items, text.Contains("submission form", StringComparison.OrdinalIgnoreCase), "Mandatory Forms",
            "Include completed submission form.", true, SentenceWith(text, "submission form"));
        AddIf(items, text.Contains("conflict of interest declaration", StringComparison.OrdinalIgnoreCase), "Mandatory Forms",
            "Include conflict of interest declaration.", true, SentenceWith(text, "conflict of interest declaration"));
        AddIf(items, text.Contains("safety plan", StringComparison.OrdinalIgnoreCase), "Mandatory Forms",
            "Include safety plan.", true, SentenceWith(text, "safety plan"));
        AddIf(items, text.Contains("project schedule", StringComparison.OrdinalIgnoreCase), "Mandatory Forms",
            "Include project schedule.", true, SentenceWith(text, "project schedule"));
        AddIf(items, text.Contains("pricing", StringComparison.OrdinalIgnoreCase) ||
                     text.Contains("price", StringComparison.OrdinalIgnoreCase), "Pricing",
            "Pricing instructions or scored price criteria are present.", true, FirstSignal(text, ["pricing", "price"]));
        AddIf(items, text.Contains("pricing form", StringComparison.OrdinalIgnoreCase), "Mandatory Forms",
            "Include pricing form.", true, SentenceWith(text, "pricing form"));
        AddIf(items, text.Contains("conflict", StringComparison.OrdinalIgnoreCase), "Legal",
            "Conflict-of-interest declaration may be required.", true, SentenceWith(text, "conflict"));
        AddIf(items, text.Contains("quality", StringComparison.OrdinalIgnoreCase) ||
                     text.Contains("qa", StringComparison.OrdinalIgnoreCase), "Quality",
            "Quality review or QA approach is relevant.", false, FirstSignal(text, ["quality", "qa"]));
        AddIf(items, text.Contains("rated criteria", StringComparison.OrdinalIgnoreCase) ||
                     text.Contains("evaluation will consider", StringComparison.OrdinalIgnoreCase), "Evaluation",
            "Rated criteria must be mapped to proposal sections.", true, FirstSignal(text, ["rated criteria", "evaluation will consider"]));

        if (items.Count == 0)
        {
            items.Add(new RequirementItem
            {
                Category = "Review",
                Requirement = "Tender notice requires manual document review before bid decision.",
                Mandatory = true,
                Evidence = request.Tender.Description,
            });
        }

        return items;
    }

    private static IReadOnlyList<ComplianceItem> BuildCompliance(
        BrainRequest request,
        IReadOnlyList<RequirementItem> requirements)
    {
        var checklist = new List<ComplianceItem>
        {
            new()
            {
                Item = "Confirm live portal notice and all documents",
                Status = string.IsNullOrWhiteSpace(request.Tender.SourceUrl) ? "Needs source URL" : "Ready to verify",
                Evidence = request.Tender.SourceUrl,
            },
            new()
            {
                Item = "Confirm closing date and time zone",
                Status = request.Tender.ClosingDate is null ? "Missing" : "Captured",
                Evidence = request.Tender.ClosingDate?.ToString("yyyy-MM-dd") ?? "",
            },
            new()
            {
                Item = "Build response compliance matrix",
                Status = requirements.Any(item => item.Mandatory) ? "Required" : "Recommended",
                Evidence = $"{requirements.Count(item => item.Mandatory)} mandatory signal(s)",
            },
        };

        foreach (var item in requirements.Where(item => item.Mandatory))
        {
            checklist.Add(new ComplianceItem
            {
                Item = item.Requirement,
                Status = "Open",
                Evidence = item.Evidence,
            });
        }

        return checklist;
    }

    private static IReadOnlyList<RiskItem> BuildRisks(
        BrainRequest request,
        IReadOnlyList<RequirementItem> requirements,
        IReadOnlyList<ComplianceItem> compliance)
    {
        var risks = new List<RiskItem>();
        if (request.Tender.ClosingDate is null)
        {
            risks.Add(new RiskItem
            {
                Level = "High",
                Risk = "Closing date was not extracted.",
                Mitigation = "Open the portal notice and confirm deadline before pursuing.",
            });
        }

        if (request.Tender.SourceUrl.Contains("procurement-portal.novascotia.ca", StringComparison.OrdinalIgnoreCase))
        {
            risks.Add(new RiskItem
            {
                Level = "Medium",
                Risk = "Portal access may be blocked or require manual verification.",
                Mitigation = "Cache public documents and keep a human portal verification step.",
            });
        }

        if (requirements.Any(item => item.Mandatory) && compliance.Any(item => item.Status == "Open"))
        {
            risks.Add(new RiskItem
            {
                Level = "Medium",
                Risk = "Mandatory requirements are not yet assigned to proposal owners.",
                Mitigation = "Assign each open compliance item before bid/no-bid approval.",
            });
        }

        return risks;
    }

    private static IReadOnlyList<string> BuildQuestions(
        BrainRequest request,
        IReadOnlyList<RequirementItem> requirements,
        IReadOnlyList<RiskItem> risks)
    {
        var questions = new List<string>
        {
            "Have all tender documents and addenda been downloaded from the live portal?",
            "What submission method and file naming rules apply?",
            "Who owns each mandatory compliance item?",
        };
        if (request.Tender.ClosingDate is null)
        {
            questions.Add("What is the exact closing date, time, and time zone?");
        }
        if (risks.Any(risk => risk.Risk.Contains("Portal access", StringComparison.OrdinalIgnoreCase)))
        {
            questions.Add("Can the team access the procurement portal from the bidding account?");
        }
        if (!requirements.Any(item => item.Category.Equals("Pricing", StringComparison.OrdinalIgnoreCase)))
        {
            questions.Add("Where are pricing instructions located in the tender package?");
        }

        return questions;
    }

    private static LocalAiRequest BuildAiRequest(
        BrainRequest request,
        IReadOnlyList<RequirementItem> requirements,
        IReadOnlyList<RiskItem> risks)
    {
        var prompt = $"""
        Summarize this tender for a proposal manager in 6 concise bullets.
        Include fit, deadline, mandatory requirements, risks, and next actions.

        Tender: {request.Tender.TenderId} - {request.Tender.Title}
        Buyer: {request.Tender.Buyer}
        Closing: {request.Tender.ClosingDate?.ToString("yyyy-MM-dd") ?? "unknown"}
        Description: {request.Tender.Description}
        Requirements: {string.Join("; ", requirements.Select(item => item.Requirement))}
        Risks: {string.Join("; ", risks.Select(item => item.Risk))}
        """;
        return new LocalAiRequest(prompt);
    }

    private static void AddIf(
        List<RequirementItem> items,
        bool condition,
        string category,
        string requirement,
        bool mandatory,
        string evidence)
    {
        if (!condition)
        {
            return;
        }

        items.Add(new RequirementItem
        {
            Category = category,
            Requirement = requirement,
            Mandatory = mandatory,
            Evidence = evidence,
        });
    }

    private static string FirstSignal(string text, IReadOnlyList<string> signals)
    {
        foreach (var signal in signals)
        {
            var sentence = SentenceWith(text, signal);
            if (!string.IsNullOrWhiteSpace(sentence))
            {
                return sentence;
            }
        }

        return "";
    }

    private static string SentenceWith(string text, string signal)
    {
        var sentences = text.Split(['.', '\n'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return sentences.FirstOrDefault(sentence => sentence.Contains(signal, StringComparison.OrdinalIgnoreCase)) ?? "";
    }
}

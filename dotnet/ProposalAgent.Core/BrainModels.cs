using System.Text;

namespace ProposalAgent.Core;

public sealed record TenderNotice
{
    public string TenderId { get; init; } = "";
    public string Title { get; init; } = "";
    public string Buyer { get; init; } = "";
    public string Status { get; init; } = "";
    public DateOnly? ClosingDate { get; init; }
    public string Category { get; init; } = "";
    public string SourceUrl { get; init; } = "";
    public string Description { get; init; } = "";
    public string SourcePath { get; init; } = "";
    public string PursuitType { get; init; } = "";
    public string BidFit { get; init; } = "";
    public string ClassificationConfidence { get; init; } = "";
    public string ClassificationNote { get; init; } = "";
    public IReadOnlyList<string> DocumentPaths { get; init; } = [];
}

public sealed record BrainRequest
{
    public required TenderNotice Tender { get; init; }
    public required ProposalBrief Brief { get; init; }
    public bool UseLocalAi { get; init; }
}

public sealed record RequirementItem
{
    public required string Category { get; init; }
    public required string Requirement { get; init; }
    public bool Mandatory { get; init; }
    public string Evidence { get; init; } = "";
}

public sealed record ComplianceItem
{
    public required string Item { get; init; }
    public required string Status { get; init; }
    public string Evidence { get; init; } = "";
}

public sealed record RiskItem
{
    public required string Level { get; init; }
    public required string Risk { get; init; }
    public string Mitigation { get; init; } = "";
}

public sealed record BrainResult
{
    public required TenderNotice Tender { get; init; }
    public required ProposalDraft Draft { get; init; }
    public IReadOnlyList<RequirementItem> Requirements { get; init; } = [];
    public IReadOnlyList<ComplianceItem> ComplianceChecklist { get; init; } = [];
    public IReadOnlyList<RiskItem> Risks { get; init; } = [];
    public IReadOnlyList<string> QuestionsForClient { get; init; } = [];
    public string LocalAiSummary { get; init; } = "";
    public string AiStatus { get; init; } = "not requested";

    public string ToMarkdown()
    {
        var lines = new List<string>
        {
            $"# Tender Brain Analysis: {Tender.Title}",
            "",
            "## Tender Snapshot",
            "",
            $"- Tender ID: {ValueOrUnknown(Tender.TenderId)}",
            $"- Buyer: {ValueOrUnknown(Tender.Buyer)}",
            $"- Status: {ValueOrUnknown(Tender.Status)}",
            $"- Closing date: {(Tender.ClosingDate?.ToString("yyyy-MM-dd") ?? "unknown")}",
            $"- Source: {ValueOrUnknown(Tender.SourceUrl)}",
            $"- Pursuit type: {ValueOrUnknown(Tender.PursuitType)}",
            $"- Bid fit: {ValueOrUnknown(Tender.BidFit)}",
            $"- Classification confidence: {ValueOrUnknown(Tender.ClassificationConfidence)}",
            $"- Attached documents: {Tender.DocumentPaths.Count}",
            $"- AI status: {AiStatus}",
            "",
        };

        if (!string.IsNullOrWhiteSpace(Tender.ClassificationNote))
        {
            lines.AddRange(["## Pursuit Classification", "", Tender.ClassificationNote, ""]);
        }

        if (!string.IsNullOrWhiteSpace(LocalAiSummary))
        {
            lines.AddRange(["## Local AI Summary", "", LocalAiSummary.Trim(), ""]);
        }

        lines.AddRange(["## Bid / No-Bid", ""]);
        lines.Add($"- Recommendation: {Draft.PursuitDecision?.Recommendation ?? "unknown"}");
        lines.Add($"- Score: {Draft.PursuitDecision?.Score.ToString() ?? "unknown"}");
        foreach (var reason in Draft.PursuitDecision?.Reasons ?? [])
        {
            lines.Add($"- Reason: {reason}");
        }
        foreach (var condition in Draft.PursuitDecision?.Conditions ?? [])
        {
            lines.Add($"- Condition: {condition}");
        }
        lines.Add("");

        lines.AddRange(["## Requirement Matrix", ""]);
        lines.Add("| Category | Mandatory | Requirement | Evidence |");
        lines.Add("| --- | --- | --- | --- |");
        foreach (var item in Requirements)
        {
            lines.Add($"| {Escape(item.Category)} | {(item.Mandatory ? "Yes" : "No")} | {Escape(item.Requirement)} | {Escape(item.Evidence)} |");
        }
        lines.Add("");

        lines.AddRange(["## Compliance Checklist", ""]);
        lines.Add("| Item | Status | Evidence |");
        lines.Add("| --- | --- | --- |");
        foreach (var item in ComplianceChecklist)
        {
            lines.Add($"| {Escape(item.Item)} | {Escape(item.Status)} | {Escape(item.Evidence)} |");
        }
        lines.Add("");

        lines.AddRange(["## Risk Register", ""]);
        foreach (var risk in Risks)
        {
            lines.Add($"- {risk.Level}: {risk.Risk} Mitigation: {risk.Mitigation}");
        }
        lines.Add("");

        lines.AddRange(["## Questions For Client / Portal", ""]);
        foreach (var question in QuestionsForClient)
        {
            lines.Add($"- {question}");
        }
        lines.Add("");

        lines.Add(Draft.ToMarkdown());
        return string.Join('\n', lines).TrimEnd() + "\n";
    }

    private static string ValueOrUnknown(string value) => string.IsNullOrWhiteSpace(value) ? "unknown" : value;

    private static string Escape(string value) =>
        value.Replace("|", "/", StringComparison.Ordinal).ReplaceLineEndings(" ").Trim();
}

public sealed record LocalAiRequest(string Prompt, string Model = "llama3.1:8b");

public sealed record LocalAiResponse(string Text, bool Available, string Status);

public interface ILocalAiClient
{
    Task<LocalAiResponse> CompleteAsync(LocalAiRequest request, CancellationToken cancellationToken = default);
}

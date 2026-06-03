using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace ProposalAgent.Core;

public sealed record NsTenderWatchOptions
{
    public int Page { get; init; } = 1;
    public int NumberOfRecords { get; init; } = 6;
    public string SortType { get; init; } = "POSTED_DATE_DESC";
    public IReadOnlyList<string> Keywords { get; init; } = [];
    public string? FallbackMonitorJsonPath { get; init; }
}

public sealed record NsTenderWatchResult
{
    public required string MonitorJson { get; init; }
    public required string SourceMode { get; init; }
    public required string Status { get; init; }
    public int MatchCount { get; init; }
}

public sealed class NsTenderLiveWatcher
{
    private readonly HttpClient _httpClient;

    public NsTenderLiveWatcher(HttpClient? httpClient = null)
    {
        _httpClient = httpClient ?? new HttpClient
        {
            BaseAddress = new Uri("https://procurement-portal.novascotia.ca/procurementui/")
        };
    }

    public async Task<NsTenderWatchResult> WatchAsync(
        NsTenderWatchOptions options,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var live = await TryFetchLiveAsync(options, cancellationToken);
            if (live is not null)
            {
                return live;
            }
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or JsonException)
        {
            return LoadFallback(options, $"Live portal request failed: {ex.Message}");
        }

        return LoadFallback(options, "Live portal response did not include tenderDataList.");
    }

    private async Task<NsTenderWatchResult?> TryFetchLiveAsync(
        NsTenderWatchOptions options,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(
            HttpMethod.Post,
            $"tenders?page={options.Page}&numberOfRecords={options.NumberOfRecords}&sortType={Uri.EscapeDataString(options.SortType)}");
        request.Headers.TryAddWithoutValidation("User-Agent", "Mozilla/5.0 ProposalAgent/1.0");
        request.Headers.TryAddWithoutValidation("Accept", "application/json, text/plain, */*");
        request.Headers.TryAddWithoutValidation("Origin", "https://procurement-portal.novascotia.ca");
        request.Headers.TryAddWithoutValidation("Referer", "https://procurement-portal.novascotia.ca/tenders");
        request.Content = JsonContent.Create(new { });

        using var response = await _httpClient.SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            throw new HttpRequestException(
                $"Nova Scotia portal returned {(int)response.StatusCode} {response.ReasonPhrase}".Trim());
        }

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
        if (!document.RootElement.TryGetProperty("tenderDataList", out var tenders) ||
            tenders.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        var monitor = BuildMonitorJson(tenders, options, "live");
        return new NsTenderWatchResult
        {
            MonitorJson = monitor.Json,
            SourceMode = "live",
            Status = "Fetched live tenders from the Nova Scotia Procurement Portal.",
            MatchCount = monitor.MatchCount,
        };
    }

    private NsTenderWatchResult LoadFallback(NsTenderWatchOptions options, string liveStatus)
    {
        if (string.IsNullOrWhiteSpace(options.FallbackMonitorJsonPath) ||
            !File.Exists(options.FallbackMonitorJsonPath))
        {
            return new NsTenderWatchResult
            {
                MonitorJson = RenderEmptyMonitor("none", liveStatus),
                SourceMode = "none",
                Status = liveStatus,
                MatchCount = 0,
            };
        }

        var fallbackJson = File.ReadAllText(options.FallbackMonitorJsonPath);
        var monitor = FilterMonitorJson(fallbackJson);
        return new NsTenderWatchResult
        {
            MonitorJson = monitor.Json,
            SourceMode = "fallback",
            Status = $"{liveStatus} Used fallback monitor JSON: {options.FallbackMonitorJsonPath}",
            MatchCount = monitor.MatchCount,
        };
    }

    private static (string Json, int MatchCount) BuildMonitorJson(
        JsonElement tenderDataList,
        NsTenderWatchOptions options,
        string sourceMode)
    {
        var matches = new JsonArray();
        foreach (var tender in tenderDataList.EnumerateArray())
        {
            var searchable = SearchableText(tender);
            if (options.Keywords.Count > 0 &&
                !options.Keywords.Any(keyword => searchable.Contains(keyword, StringComparison.OrdinalIgnoreCase)))
            {
                continue;
            }
            if (!IsActionableConsultingOpportunity(searchable))
            {
                continue;
            }

            matches.Add(new JsonObject
            {
                ["tender"] = JsonNode.Parse(tender.GetRawText()),
                ["match_reasons"] = BuildReasons(options, searchable),
            });
        }

        var root = new JsonObject
        {
            ["ran_at"] = DateTimeOffset.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
            ["dry_run"] = false,
            ["source_mode"] = sourceMode,
            ["source_url"] = "https://procurement-portal.novascotia.ca/tenders",
            ["matches"] = matches,
        };
        return (root.ToJsonString(), matches.Count);
    }

    private static (string Json, int MatchCount) FilterMonitorJson(string monitorJson)
    {
        using var document = JsonDocument.Parse(monitorJson);
        var matches = new JsonArray();
        if (document.RootElement.TryGetProperty("matches", out var sourceMatches) &&
            sourceMatches.ValueKind == JsonValueKind.Array)
        {
            foreach (var match in sourceMatches.EnumerateArray())
            {
                if (!match.TryGetProperty("tender", out var tender))
                {
                    continue;
                }

                if (!IsActionableConsultingOpportunity(SearchableText(tender)))
                {
                    continue;
                }

                matches.Add(JsonNode.Parse(match.GetRawText()));
            }
        }

        var root = new JsonObject
        {
            ["ran_at"] = DateTimeOffset.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
            ["dry_run"] = false,
            ["source_mode"] = "fallback-filtered",
            ["source_url"] = "https://procurement-portal.novascotia.ca/tenders",
            ["matches"] = matches,
        };
        return (root.ToJsonString(), matches.Count);
    }

    private static bool IsActionableConsultingOpportunity(string searchable)
    {
        var lower = searchable.ToLowerInvariant();
        var consultingSignals = new[]
        {
            "feasibility", "study", "assessment", "capacity study", "assimilative capacity",
            "design", "design study", "design services", "engineering services", "consulting",
            "consultant", "report", "master plan", "planning", "model", "modelling",
            "stormwater management project", "condition assessment", "hydraulic"
        };
        var constructionSignals = new[]
        {
            "asphalt repaving", "paving", "gravelling", "bridge rehabilitation",
            "bridge replacement", "window replacement", "recladding", "culvert",
            "sprinkler work", "utility extensions", "supply & installation",
            "supply and installation", "materials, labour and equipment"
        };
        var supplySignals = new[]
        {
            "supply of", "supply & programming", "radios", "rescue tools", "vehicle",
            "tractor", "electrical supplies", "lamps and ballasts", "media destruction", "vendor"
        };

        var hasConsultingSignal = consultingSignals.Any(signal => lower.Contains(signal, StringComparison.OrdinalIgnoreCase));
        var hasConstructionSignal = constructionSignals.Any(signal => lower.Contains(signal, StringComparison.OrdinalIgnoreCase));
        var hasSupplySignal = supplySignals.Any(signal => lower.Contains(signal, StringComparison.OrdinalIgnoreCase));
        return hasConsultingSignal && !hasSupplySignal && !hasConstructionSignal;
    }

    private static JsonArray BuildReasons(NsTenderWatchOptions options, string searchable)
    {
        var reasons = new JsonArray();
        if (options.Keywords.Count == 0)
        {
            reasons.Add("no keyword filter");
            return reasons;
        }

        foreach (var keyword in options.Keywords.Where(keyword =>
                     searchable.Contains(keyword, StringComparison.OrdinalIgnoreCase)))
        {
            reasons.Add($"keyword: {keyword}");
        }

        return reasons;
    }

    private static string RenderEmptyMonitor(string sourceMode, string status)
    {
        var root = new JsonObject
        {
            ["ran_at"] = DateTimeOffset.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
            ["dry_run"] = false,
            ["source_mode"] = sourceMode,
            ["status"] = status,
            ["matches"] = new JsonArray(),
        };
        return root.ToJsonString();
    }

    private static int CountMatches(string monitorJson)
    {
        using var document = JsonDocument.Parse(monitorJson);
        return document.RootElement.TryGetProperty("matches", out var matches) &&
               matches.ValueKind == JsonValueKind.Array
            ? matches.GetArrayLength()
            : 0;
    }

    private static string GetString(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out var value) && value.ValueKind != JsonValueKind.Null
            ? value.ToString()
            : "";

    private static string SearchableText(JsonElement tender) =>
        string.Join(
            ' ',
            GetString(tender, "tenderId"),
            GetString(tender, "title"),
            GetString(tender, "description"),
            GetString(tender, "solicitationType"),
            GetString(tender, "procurementEntity"),
            GetString(tender, "endUserEntity"));
}

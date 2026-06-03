using System.Text.Json;
using System.Text.Json.Serialization;
using ProposalAgent.Core;

try
{
    if (args.Length > 0 && args[0].Equals("brain", StringComparison.OrdinalIgnoreCase))
    {
        return await RunBrainAsync(args[1..]);
    }

    if (args.Length > 0 && args[0].Equals("import-ns-monitor", StringComparison.OrdinalIgnoreCase))
    {
        return RunImportNsMonitor(args[1..]);
    }

    if (args.Length > 0 && args[0].Equals("watch-ns-live", StringComparison.OrdinalIgnoreCase))
    {
        return await RunWatchNsLiveAsync(args[1..]);
    }

    if (args.Length > 0 && args[0].Equals("extract-doc", StringComparison.OrdinalIgnoreCase))
    {
        return RunExtractDoc(args[1..]);
    }

    return RunDraft(args);
}
catch (Exception ex) when (ex is ArgumentException or JsonException or IOException or InvalidOperationException)
{
    Console.Error.WriteLine(ex.Message);
    return 1;
}

static int RunDraft(string[] args)
{
    var parseResult = Arguments.Parse(args);
    if (parseResult.HelpRequested)
    {
        Arguments.PrintUsage();
        return 0;
    }

    if (parseResult.BriefPath is null)
    {
        Console.Error.WriteLine("Missing required brief path.");
        Arguments.PrintUsage();
        return 2;
    }

    var rawJson = File.ReadAllText(parseResult.BriefPath);
    var brief = JsonSerializer.Deserialize<ProposalBrief>(rawJson, Json.Options)
        ?? throw new InvalidOperationException("Could not deserialize proposal brief.");

    var draft = new ProposalAgent.Core.ProposalAgent().Draft(brief);
    WriteOutput(draft.ToMarkdown(), parseResult.OutputPath);
    return 0;
}

static async Task<int> RunBrainAsync(string[] args)
{
    var parseResult = BrainArguments.Parse(args);
    if (parseResult.HelpRequested)
    {
        BrainArguments.PrintUsage();
        return 0;
    }

    var input = parseResult.InputPath ?? "proposals/active/ns-tenders";
    var outputDir = parseResult.OutputDirectory ?? "proposals/outputs/v1-demo";
    var cache = new TenderCache();
    var requests = Directory.Exists(input)
        ? cache.LoadActiveTenderBriefs(input)
        : [cache.LoadYamlBrief(input)];
    var people = new PeopleRoster().LoadYaml("knowledge/people.yaml");
    if (people.Count > 0)
    {
        requests = requests
            .Select(request => request with
            {
                Brief = request.Brief with { AvailablePeople = people },
            })
            .ToList();
    }

    Directory.CreateDirectory(outputDir);
    ILocalAiClient aiClient = parseResult.UseLocalAi ? new OllamaLocalAiClient() : new NullLocalAiClient();
    var brain = new ProposalBrain(aiClient);
    foreach (var request in requests)
    {
        var enriched = request with { UseLocalAi = parseResult.UseLocalAi };
        var result = await brain.AnalyzeAsync(enriched);
        var slug = Slug(result.Tender.TenderId.Length > 0 ? result.Tender.TenderId : result.Tender.Title);
        var outputPath = Path.Combine(outputDir, $"{slug}-brain.md");
        File.WriteAllText(outputPath, result.ToMarkdown());
        Console.WriteLine(outputPath);
    }

    return 0;
}

static int RunImportNsMonitor(string[] args)
{
    var parseResult = ImportArguments.Parse(args);
    if (parseResult.HelpRequested)
    {
        ImportArguments.PrintUsage();
        return 0;
    }

    if (parseResult.MonitorJsonPath is null)
    {
        Console.Error.WriteLine("Missing monitor JSON path.");
        ImportArguments.PrintUsage();
        return 2;
    }

    var outputDirectory = parseResult.OutputDirectory ?? "proposals/active/ns-tenders";
    var written = new NsTenderMonitorImporter().Import(parseResult.MonitorJsonPath, outputDirectory);
    foreach (var path in written)
    {
        Console.WriteLine(path);
    }

    Console.WriteLine($"Imported {written.Count} tender brief(s).");
    return 0;
}

static async Task<int> RunWatchNsLiveAsync(string[] args)
{
    var parseResult = WatchNsLiveArguments.Parse(args);
    if (parseResult.HelpRequested)
    {
        WatchNsLiveArguments.PrintUsage();
        return 0;
    }

    var outputDirectory = parseResult.OutputDirectory ?? "proposals/outputs/ns-tenders/monitor-snapshots";
    Directory.CreateDirectory(outputDirectory);
    var monitorPath = parseResult.OutputPath ??
        Path.Combine(outputDirectory, $"ns-tender-monitor-live-{DateTime.Now:yyyyMMdd-HHmmss}.json");

    var result = await new NsTenderLiveWatcher().WatchAsync(new NsTenderWatchOptions
    {
        FallbackMonitorJsonPath = parseResult.FallbackMonitorJsonPath,
        Keywords = parseResult.Keywords,
    });

    File.WriteAllText(monitorPath, result.MonitorJson);
    Console.WriteLine($"Monitor: {monitorPath}");
    Console.WriteLine($"Source: {result.SourceMode}");
    Console.WriteLine($"Status: {result.Status}");
    Console.WriteLine($"Matches: {result.MatchCount}");

    if (parseResult.Import)
    {
        var activeDirectory = parseResult.ActiveTenderDirectory ?? "proposals/active/ns-tenders";
        var written = new NsTenderMonitorImporter().Import(monitorPath, activeDirectory);
        foreach (var path in written)
        {
            Console.WriteLine(path);
        }

        Console.WriteLine($"Imported {written.Count} tender brief(s).");
    }

    if (parseResult.Analyze)
    {
        var activeDirectory = parseResult.ActiveTenderDirectory ?? "proposals/active/ns-tenders";
        var brainOutputDirectory = parseResult.BrainOutputDirectory ?? "proposals/outputs/v1-demo";
        return await RunBrainAsync([activeDirectory, "--out-dir", brainOutputDirectory]);
    }

    return result.MatchCount > 0 ? 0 : 1;
}

static int RunExtractDoc(string[] args)
{
    var parseResult = ExtractDocArguments.Parse(args);
    if (parseResult.HelpRequested)
    {
        ExtractDocArguments.PrintUsage();
        return 0;
    }

    if (parseResult.DocumentPath is null)
    {
        Console.Error.WriteLine("Missing document path.");
        ExtractDocArguments.PrintUsage();
        return 2;
    }

    var text = new DocumentTextExtractor().ExtractText(parseResult.DocumentPath);
    WriteOutput(text, parseResult.OutputPath);
    if (parseResult.OutputPath is not null)
    {
        Console.WriteLine(parseResult.OutputPath);
    }

    return string.IsNullOrWhiteSpace(text) ? 1 : 0;
}

static void WriteOutput(string markdown, string? outputPath)
{
    if (outputPath is null)
    {
        Console.Write(markdown);
    }
    else
    {
        File.WriteAllText(outputPath, markdown);
    }
}

static string Slug(string value)
{
    var chars = value
        .ToLowerInvariant()
        .Select(ch => char.IsLetterOrDigit(ch) ? ch : '-')
        .ToArray();
    return string.Join('-', new string(chars).Split('-', StringSplitOptions.RemoveEmptyEntries));
}

internal static class Json
{
    public static readonly JsonSerializerOptions Options = CreateOptions();

    private static JsonSerializerOptions CreateOptions()
    {
        var options = new JsonSerializerOptions(JsonSerializerDefaults.Web)
        {
            PropertyNameCaseInsensitive = true,
        };
        options.Converters.Add(new DateOnlyJsonConverter());
        return options;
    }
}

internal sealed record Arguments(string? BriefPath, string? OutputPath, bool HelpRequested)
{
    public static Arguments Parse(string[] args)
    {
        string? briefPath = null;
        string? outputPath = null;
        var help = false;

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];
            if (arg is "-h" or "--help")
            {
                help = true;
            }
            else if (arg == "--out")
            {
                if (index + 1 >= args.Length)
                {
                    throw new ArgumentException("--out requires a path.");
                }

                outputPath = args[++index];
            }
            else if (briefPath is null)
            {
                briefPath = arg;
            }
            else
            {
                throw new ArgumentException($"Unexpected argument: {arg}");
            }
        }

        return new Arguments(briefPath, outputPath, help);
    }

    public static void PrintUsage()
    {
        Console.WriteLine("Usage: proposal-agent-dotnet <brief.json> [--out output.md]");
        Console.WriteLine("Usage: proposal-agent-dotnet brain [input-yaml-or-directory] [--out-dir output-dir] [--ai]");
        Console.WriteLine("Usage: proposal-agent-dotnet watch-ns-live [--fallback monitor.json] [--out monitor.json] [--keyword text] [--import] [--analyze]");
        Console.WriteLine("Usage: proposal-agent-dotnet import-ns-monitor <monitor.json> [--out-dir active-tender-dir]");
        Console.WriteLine("Usage: proposal-agent-dotnet extract-doc <document.txt|document.md|document.pdf> [--out output.txt]");
    }
}

internal sealed record WatchNsLiveArguments(
    string? OutputPath,
    string? OutputDirectory,
    string? FallbackMonitorJsonPath,
    string? ActiveTenderDirectory,
    string? BrainOutputDirectory,
    IReadOnlyList<string> Keywords,
    bool Import,
    bool Analyze,
    bool HelpRequested)
{
    public static WatchNsLiveArguments Parse(string[] args)
    {
        string? outputPath = null;
        string? outputDirectory = null;
        string? fallbackMonitorJsonPath = null;
        string? activeTenderDirectory = null;
        string? brainOutputDirectory = null;
        var keywords = new List<string>();
        var import = false;
        var analyze = false;
        var help = false;

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];
            if (arg is "-h" or "--help")
            {
                help = true;
            }
            else if (arg == "--out")
            {
                outputPath = RequireValue(args, ref index, "--out");
            }
            else if (arg == "--out-dir")
            {
                outputDirectory = RequireValue(args, ref index, "--out-dir");
            }
            else if (arg == "--fallback")
            {
                fallbackMonitorJsonPath = RequireValue(args, ref index, "--fallback");
            }
            else if (arg == "--active-dir")
            {
                activeTenderDirectory = RequireValue(args, ref index, "--active-dir");
            }
            else if (arg == "--brain-out-dir")
            {
                brainOutputDirectory = RequireValue(args, ref index, "--brain-out-dir");
            }
            else if (arg == "--keyword")
            {
                keywords.Add(RequireValue(args, ref index, "--keyword"));
            }
            else if (arg == "--import")
            {
                import = true;
            }
            else if (arg == "--analyze")
            {
                import = true;
                analyze = true;
            }
            else
            {
                throw new ArgumentException($"Unexpected argument: {arg}");
            }
        }

        return new WatchNsLiveArguments(
            outputPath,
            outputDirectory,
            fallbackMonitorJsonPath,
            activeTenderDirectory,
            brainOutputDirectory,
            keywords,
            import,
            analyze,
            help);
    }

    public static void PrintUsage()
    {
        Console.WriteLine("Usage: proposal-agent-dotnet watch-ns-live [--fallback monitor.json] [--out monitor.json] [--keyword text] [--import] [--analyze]");
        Console.WriteLine("  --fallback       Captured monitor JSON to use if the public portal rejects the live request.");
        Console.WriteLine("  --import         Import monitor matches into proposals/active/ns-tenders.");
        Console.WriteLine("  --analyze        Import and run brain reports into proposals/outputs/v1-demo.");
    }

    private static string RequireValue(string[] args, ref int index, string name)
    {
        if (index + 1 >= args.Length)
        {
            throw new ArgumentException($"{name} requires a path.");
        }

        return args[++index];
    }
}

internal sealed record ExtractDocArguments(string? DocumentPath, string? OutputPath, bool HelpRequested)
{
    public static ExtractDocArguments Parse(string[] args)
    {
        string? documentPath = null;
        string? outputPath = null;
        var help = false;

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];
            if (arg is "-h" or "--help")
            {
                help = true;
            }
            else if (arg == "--out")
            {
                if (index + 1 >= args.Length)
                {
                    throw new ArgumentException("--out requires a path.");
                }

                outputPath = args[++index];
            }
            else if (documentPath is null)
            {
                documentPath = arg;
            }
            else
            {
                throw new ArgumentException($"Unexpected argument: {arg}");
            }
        }

        return new ExtractDocArguments(documentPath, outputPath, help);
    }

    public static void PrintUsage()
    {
        Console.WriteLine("Usage: proposal-agent-dotnet extract-doc <document.txt|document.md|document.pdf> [--out output.txt]");
    }
}

internal sealed record ImportArguments(string? MonitorJsonPath, string? OutputDirectory, bool HelpRequested)
{
    public static ImportArguments Parse(string[] args)
    {
        string? monitorJsonPath = null;
        string? outputDirectory = null;
        var help = false;

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];
            if (arg is "-h" or "--help")
            {
                help = true;
            }
            else if (arg == "--out-dir")
            {
                if (index + 1 >= args.Length)
                {
                    throw new ArgumentException("--out-dir requires a path.");
                }

                outputDirectory = args[++index];
            }
            else if (monitorJsonPath is null)
            {
                monitorJsonPath = arg;
            }
            else
            {
                throw new ArgumentException($"Unexpected argument: {arg}");
            }
        }

        return new ImportArguments(monitorJsonPath, outputDirectory, help);
    }

    public static void PrintUsage()
    {
        Console.WriteLine("Usage: proposal-agent-dotnet import-ns-monitor <monitor.json> [--out-dir active-tender-dir]");
    }
}

internal sealed record BrainArguments(
    string? InputPath,
    string? OutputDirectory,
    bool UseLocalAi,
    bool HelpRequested)
{
    public static BrainArguments Parse(string[] args)
    {
        string? inputPath = null;
        string? outputDirectory = null;
        var useLocalAi = false;
        var help = false;

        for (var index = 0; index < args.Length; index++)
        {
            var arg = args[index];
            if (arg is "-h" or "--help")
            {
                help = true;
            }
            else if (arg == "--ai")
            {
                useLocalAi = true;
            }
            else if (arg == "--out-dir")
            {
                if (index + 1 >= args.Length)
                {
                    throw new ArgumentException("--out-dir requires a path.");
                }

                outputDirectory = args[++index];
            }
            else if (inputPath is null)
            {
                inputPath = arg;
            }
            else
            {
                throw new ArgumentException($"Unexpected argument: {arg}");
            }
        }

        return new BrainArguments(inputPath, outputDirectory, useLocalAi, help);
    }

    public static void PrintUsage()
    {
        Console.WriteLine("Usage: proposal-agent-dotnet brain [input-yaml-or-directory] [--out-dir output-dir] [--ai]");
    }
}

internal sealed class DateOnlyJsonConverter : JsonConverter<DateOnly>
{
    public override DateOnly Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options) =>
        DateOnly.Parse(reader.GetString() ?? "");

    public override void Write(Utf8JsonWriter writer, DateOnly value, JsonSerializerOptions options) =>
        writer.WriteStringValue(value.ToString("yyyy-MM-dd"));
}

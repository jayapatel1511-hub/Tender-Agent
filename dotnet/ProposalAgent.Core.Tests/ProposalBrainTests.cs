namespace ProposalAgent.Core.Tests;

public sealed class ProposalBrainTests
{
    [Fact]
    public void TenderCacheLoadsCachedNovaScotiaTenderBriefs()
    {
        var root = RepoRoot();
        var requests = new TenderCache().LoadActiveTenderBriefs(
            Path.Combine(root, "proposals", "active", "ns-tenders"));

        Assert.Equal(4, requests.Count);
        Assert.Contains(requests, request => request.Tender.TenderId == "TOK202614");
        Assert.All(requests, request => Assert.False(string.IsNullOrWhiteSpace(request.Tender.SourceUrl)));
        Assert.All(requests, request => Assert.Equal("design-study-consulting", request.Tender.PursuitType));
    }

    [Fact]
    public void PeopleRosterLoadsFakeOrganization()
    {
        var root = RepoRoot();
        var people = new PeopleRoster().LoadYaml(Path.Combine(root, "knowledge", "people.yaml"));

        Assert.Equal(100, people.Count);
        Assert.Contains(people, person => person.Role == "Proposal Manager");
        Assert.Contains(people, person => person.Region == "atlantic");
    }

    [Fact]
    public async Task ProposalBrainBuildsComplianceAndRiskReport()
    {
        var root = RepoRoot();
        var request = new TenderCache().LoadYamlBrief(Path.Combine(
            root,
            "proposals",
            "active",
            "ns-tenders",
            "inf18-2026-2027-sludge-holding-tank-design.yaml"));
        var people = new PeopleRoster().LoadYaml(Path.Combine(root, "knowledge", "people.yaml"));
        request = request with { Brief = request.Brief with { AvailablePeople = people } };

        var result = await new ProposalBrain().AnalyzeAsync(request);

        Assert.Equal("INF18-2026-2027", result.Tender.TenderId);
        Assert.Contains(result.Requirements, item => item.Category == "Schedule");
        Assert.Contains(result.ComplianceChecklist, item => item.Item.Contains("portal", StringComparison.OrdinalIgnoreCase));
        Assert.NotEmpty(result.Draft.RecommendedTeam);
        Assert.Contains("Requirement Matrix", result.ToMarkdown());
    }

    [Fact]
    public void TenderCacheLoadsPursuitClassificationFields()
    {
        var root = RepoRoot();
        var request = new TenderCache().LoadYamlBrief(Path.Combine(
            root,
            "proposals",
            "active",
            "ns-tenders",
            "inf18-2026-2027-sludge-holding-tank-design.yaml"));

        Assert.Equal("design-study-consulting", request.Tender.PursuitType);
        Assert.Equal("prime-consultant-fit", request.Tender.BidFit);
        Assert.Equal("medium", request.Tender.ClassificationConfidence);
        Assert.Empty(request.Tender.DocumentPaths);
        Assert.Contains("Sludge Holding Tank Design", request.Brief.RfpText);
    }

    [Fact]
    public void DocumentTextExtractorReadsPlainTextFixture()
    {
        var root = RepoRoot();
        var text = new DocumentTextExtractor().ExtractText(Path.Combine(
            root,
            "proposals",
            "documents",
            "ns-tenders",
            "hrce-4299-rfp-extract.txt"));

        Assert.Contains("Mandatory submission forms", text);
        Assert.Contains("pricing form", text);
    }

    [Fact]
    public void NsTenderMonitorImporterWritesTenderBriefsFromCapturedMonitorJson()
    {
        var root = RepoRoot();
        var outputDirectory = Path.Combine(Path.GetTempPath(), $"tender-agent-import-{Guid.NewGuid():N}");
        try
        {
            var written = new NsTenderMonitorImporter().Import(
                Path.Combine(root, "proposals", "outputs", "ns-tenders", "monitor-snapshots", "ns-tender-monitor-20260602-184442.json"),
                outputDirectory);

            Assert.Equal(4, written.Count);
            var imported = File.ReadAllText(written.First(path => path.Contains("inf18", StringComparison.OrdinalIgnoreCase)));
            Assert.Contains("classification_confidence", imported);
            Assert.Contains("source:", imported);
            Assert.Contains("tender_id: \"INF18-2026-2027\"", imported);
        }
        finally
        {
            if (Directory.Exists(outputDirectory))
            {
                Directory.Delete(outputDirectory, recursive: true);
            }
        }
    }

    [Fact]
    public void NsTenderMonitorImporterReplacesOlderSlugForSameTenderId()
    {
        var outputDirectory = Path.Combine(Path.GetTempPath(), $"tender-agent-import-{Guid.NewGuid():N}");
        var monitorJsonPath = Path.Combine(outputDirectory, "monitor.json");
        try
        {
            Directory.CreateDirectory(outputDirectory);
            File.WriteAllText(
                Path.Combine(outputDirectory, "test-001-old-title.yaml"),
                """
                client: "Demo Buyer"
                opportunity: "Old title"
                source:
                  tender_id: "TEST-001"
                document_paths:
                  - proposals/documents/demo.txt
                """);
            File.WriteAllText(
                monitorJsonPath,
                """
                {
                  "matches": [
                    {
                      "tender": {
                        "tenderId": "TEST-001",
                        "title": "New Engineering Study",
                        "description": "Consulting support for assessment.",
                        "closingDate": "2026-06-30T00:00-0300",
                        "createdDate": "2026-06-01",
                        "solicitationType": "Request for Proposal",
                        "procumentEntityData": { "name": "Demo Buyer" }
                      }
                    }
                  ]
                }
                """);

            var written = new NsTenderMonitorImporter().Import(monitorJsonPath, outputDirectory);

            Assert.Single(written);
            Assert.False(File.Exists(Path.Combine(outputDirectory, "test-001-old-title.yaml")));
            var activeBriefs = Directory.GetFiles(outputDirectory, "*.yaml");
            Assert.Single(activeBriefs);
            var imported = File.ReadAllText(activeBriefs[0]);
            Assert.Contains("tender_id: \"TEST-001\"", imported);
            Assert.Contains("proposals/documents/demo.txt", imported);
        }
        finally
        {
            if (Directory.Exists(outputDirectory))
            {
                Directory.Delete(outputDirectory, recursive: true);
            }
        }
    }

    [Fact]
    public async Task NsTenderLiveWatcherWrapsPortalTenderListAsMonitorJson()
    {
        using var client = new HttpClient(new StubHandler(_ => new HttpResponseMessage(System.Net.HttpStatusCode.OK)
        {
            Content = new StringContent(
                """
                {
                  "tenderDataList": [
                    {
                      "tenderId": "TEST-001",
                      "title": "Regional engineering design study",
                      "description": "Consulting support for design and assessment.",
                      "solicitationType": "Request for Proposal",
                      "procumentEntityData": { "name": "Demo Buyer" }
                    }
                  ],
                  "paginationData": { "totalRecords": 1 }
                }
                """,
                System.Text.Encoding.UTF8,
                "application/json")
        }))
        {
            BaseAddress = new Uri("https://procurement-portal.novascotia.ca/procurementui/")
        };

        var result = await new NsTenderLiveWatcher(client).WatchAsync(new NsTenderWatchOptions
        {
            Keywords = ["engineering"],
        });

        Assert.Equal("live", result.SourceMode);
        Assert.Equal(1, result.MatchCount);
        Assert.Contains("\"matches\"", result.MonitorJson);
        Assert.Contains("\"tenderId\":\"TEST-001\"", result.MonitorJson);
        Assert.Contains("keyword: engineering", result.MonitorJson);
    }

    [Fact]
    public async Task NsTenderLiveWatcherUsesFallbackWhenPortalRejectsRequest()
    {
        var root = RepoRoot();
        using var client = new HttpClient(new StubHandler(_ => new HttpResponseMessage(System.Net.HttpStatusCode.BadRequest)))
        {
            BaseAddress = new Uri("https://procurement-portal.novascotia.ca/procurementui/")
        };

        var result = await new NsTenderLiveWatcher(client).WatchAsync(new NsTenderWatchOptions
        {
            FallbackMonitorJsonPath = Path.Combine(root, "proposals", "outputs", "ns-tenders", "monitor-snapshots", "ns-tender-monitor-20260602-184442.json"),
        });

        Assert.Equal("fallback", result.SourceMode);
        Assert.Equal(4, result.MatchCount);
        Assert.Contains("Used fallback monitor JSON", result.Status);
        Assert.Contains("TOK202614", result.MonitorJson);
        Assert.DoesNotContain("NSPW2026-080", result.MonitorJson);
    }

    private static string RepoRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            if (File.Exists(Path.Combine(directory.FullName, "TenderAgent.sln")))
            {
                return directory.FullName;
            }

            directory = directory.Parent;
        }

        throw new DirectoryNotFoundException("Could not locate TenderAgent.sln.");
    }

    private sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> handler) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(handler(request));
    }
}

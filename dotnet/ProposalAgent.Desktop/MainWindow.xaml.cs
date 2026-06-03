using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using ProposalAgent.Core;

namespace ProposalAgent.Desktop;

public partial class MainWindow : Window
{
    private readonly TenderCache _cache = new();
    private readonly PeopleRoster _peopleRoster = new();
    private List<TenderViewModel> _tenders = [];
    private string? _lastOutputPath;

    public MainWindow()
    {
        InitializeComponent();
        LoadTenders();
    }

    private void RefreshButton_Click(object sender, RoutedEventArgs e) => LoadTenders();

    private void TenderList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (TenderList.SelectedItem is not TenderViewModel selected)
        {
            return;
        }

        SelectedTitle.Text = selected.Title;
        SelectedMeta.Text = $"{selected.TenderId} | {selected.Buyer} | closes {selected.ClosingLabel}";
        ReportText.Text = selected.Request.Tender.Description;
        StatusText.Text = "Tender loaded from local cache.";
    }

    private async void AnalyzeButton_Click(object sender, RoutedEventArgs e)
    {
        if (TenderList.SelectedItem is not TenderViewModel selected)
        {
            StatusText.Text = "Select a tender first.";
            return;
        }

        AnalyzeButton.IsEnabled = false;
        StatusText.Text = "Analyzing tender...";
        try
        {
            ILocalAiClient aiClient = UseAiCheckBox.IsChecked == true
                ? new OllamaLocalAiClient()
                : new NullLocalAiClient();
            var brain = new ProposalBrain(aiClient);
            var result = await brain.AnalyzeAsync(selected.Request with { UseLocalAi = UseAiCheckBox.IsChecked == true });
            var outputDirectory = ResolveRepoPath("proposals", "outputs", "v1-demo");
            Directory.CreateDirectory(outputDirectory);
            _lastOutputPath = Path.Combine(outputDirectory, $"{Slug(result.Tender.TenderId)}-desktop-brain.md");
            File.WriteAllText(_lastOutputPath, result.ToMarkdown());
            ReportText.Text = result.ToMarkdown();
            StatusText.Text = $"Analysis written to {_lastOutputPath}";
        }
        catch (Exception ex) when (ex is IOException or InvalidOperationException)
        {
            StatusText.Text = ex.Message;
        }
        finally
        {
            AnalyzeButton.IsEnabled = true;
        }
    }

    private void OpenOutputButton_Click(object sender, RoutedEventArgs e)
    {
        var path = _lastOutputPath ?? ResolveRepoPath("proposals", "outputs", "v1-demo");
        if (!File.Exists(path) && !Directory.Exists(path))
        {
            StatusText.Text = "No output has been generated yet.";
            return;
        }

        Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
    }

    private void LoadTenders()
    {
        var activeDirectory = ResolveRepoPath("proposals", "active", "ns-tenders");
        var people = _peopleRoster.LoadYaml(ResolveRepoPath("knowledge", "people.yaml"));
        _tenders = _cache.LoadActiveTenderBriefs(activeDirectory)
            .Select(request => request with { Brief = request.Brief with { AvailablePeople = people } })
            .Select(request => new TenderViewModel(request))
            .ToList();
        TenderList.ItemsSource = _tenders;
        StatusText.Text = _tenders.Count == 0
            ? $"No tenders found in {activeDirectory}"
            : $"Loaded {_tenders.Count} cached tender(s).";

        if (_tenders.Count > 0)
        {
            TenderList.SelectedIndex = 0;
        }
    }

    private static string ResolveRepoPath(params string[] parts)
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null)
        {
            var candidate = Path.Combine([directory.FullName, .. parts]);
            if (File.Exists(candidate) || Directory.Exists(candidate))
            {
                return candidate;
            }

            if (File.Exists(Path.Combine(directory.FullName, "TenderAgent.sln")))
            {
                return candidate;
            }

            directory = directory.Parent;
        }

        return Path.Combine([Environment.CurrentDirectory, .. parts]);
    }

    private static string Slug(string value)
    {
        var safe = value.Length > 0 ? value : "tender";
        var chars = safe.ToLowerInvariant().Select(ch => char.IsLetterOrDigit(ch) ? ch : '-').ToArray();
        return string.Join('-', new string(chars).Split('-', StringSplitOptions.RemoveEmptyEntries));
    }
}

public sealed class TenderViewModel(BrainRequest request)
{
    public BrainRequest Request { get; } = request;
    public string TenderId => string.IsNullOrWhiteSpace(Request.Tender.TenderId) ? "unknown" : Request.Tender.TenderId;
    public string Title => Request.Tender.Title;
    public string Buyer => Request.Tender.Buyer;
    public string ClosingLabel => Request.Tender.ClosingDate?.ToString("yyyy-MM-dd") ?? "unknown";
}

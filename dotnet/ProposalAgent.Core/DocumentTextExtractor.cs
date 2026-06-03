using System.Text;
using UglyToad.PdfPig;

namespace ProposalAgent.Core;

public interface IDocumentTextExtractor
{
    string ExtractText(string path);
}

public sealed class DocumentTextExtractor : IDocumentTextExtractor
{
    public string ExtractText(string path)
    {
        if (!File.Exists(path))
        {
            return "";
        }

        var extension = Path.GetExtension(path).ToLowerInvariant();
        return extension switch
        {
            ".txt" or ".md" or ".markdown" => File.ReadAllText(path),
            ".pdf" => ExtractPdf(path),
            _ => "",
        };
    }

    private static string ExtractPdf(string path)
    {
        var builder = new StringBuilder();
        using var document = PdfDocument.Open(path);
        foreach (var page in document.GetPages())
        {
            builder.AppendLine(page.Text);
            builder.AppendLine();
        }

        return builder.ToString();
    }
}

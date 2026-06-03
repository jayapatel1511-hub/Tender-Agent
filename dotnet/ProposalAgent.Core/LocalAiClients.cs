using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace ProposalAgent.Core;

public sealed class NullLocalAiClient : ILocalAiClient
{
    public Task<LocalAiResponse> CompleteAsync(
        LocalAiRequest request,
        CancellationToken cancellationToken = default) =>
        Task.FromResult(new LocalAiResponse("", Available: false, Status: "local AI disabled"));
}

public sealed class OllamaLocalAiClient(HttpClient? httpClient = null, string endpoint = "http://localhost:11434")
    : ILocalAiClient
{
    private readonly HttpClient _httpClient = httpClient ?? new HttpClient { BaseAddress = new Uri(endpoint) };

    public async Task<LocalAiResponse> CompleteAsync(
        LocalAiRequest request,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var payload = new OllamaGenerateRequest(request.Model, request.Prompt, Stream: false);
            using var response = await _httpClient.PostAsJsonAsync("/api/generate", payload, cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                return new LocalAiResponse("", Available: false, Status: $"Ollama returned {(int)response.StatusCode}");
            }

            var body = await response.Content.ReadFromJsonAsync<OllamaGenerateResponse>(
                cancellationToken: cancellationToken);
            return new LocalAiResponse(body?.Response?.Trim() ?? "", Available: true, Status: "Ollama summary generated");
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or JsonException)
        {
            return new LocalAiResponse("", Available: false, Status: $"Ollama unavailable: {ex.Message}");
        }
    }

    private sealed record OllamaGenerateRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("prompt")] string Prompt,
        [property: JsonPropertyName("stream")] bool Stream);

    private sealed record OllamaGenerateResponse([property: JsonPropertyName("response")] string Response);
}

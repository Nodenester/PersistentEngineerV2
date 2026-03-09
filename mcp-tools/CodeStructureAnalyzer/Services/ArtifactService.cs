using System;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using CodeStructureAnalyzer.Models;

namespace CodeStructureAnalyzer.Services;

public class ArtifactService
{
    private readonly string _artifactsDir;
    
    // Regex to match ::: artifact ... ::: blocks
    // Format: ::: artifact title="My Page" type="text/html"
    private static readonly Regex _artifactHeaderRegex = new Regex(@"^::: artifact\s+title=""([^""]+)""\s+type=""([^""]+)""", RegexOptions.Compiled);

    public ArtifactService(string outputFolder)
    {
        _artifactsDir = Path.Combine(outputFolder, "artifacts");
        if (!Directory.Exists(_artifactsDir))
        {
            Directory.CreateDirectory(_artifactsDir);
        }
    }

    public async Task<Artifact?> SaveArtifactAsync(string title, string content, string typeStr)
    {
        var artifact = new Artifact
        {
            Title = title,
            Content = content,
            Type = ParseType(typeStr)
        };

        string extension = GetExtension(artifact.Type, typeStr);
        string safeTitle = string.Join("_", title.Split(Path.GetInvalidFileNameChars()));
        string fileName = $"{DateTime.Now:yyyyMMdd_HHmmss}_{safeTitle}{extension}";
        string fullPath = Path.Combine(_artifactsDir, fileName);

        await File.WriteAllTextAsync(fullPath, content);
        artifact.FilePath = fullPath;

        // AnsiConsole.MarkupLine($"[green]Artifact Saved:[/] [link]{fullPath}[/]");
        return artifact;
    }

    private ArtifactType ParseType(string typeStr)
    {
        if (typeStr.Contains("html")) return ArtifactType.Html;
        if (typeStr.Contains("mermaid")) return ArtifactType.Mermaid;
        if (typeStr.Contains("javascript") || typeStr.Contains("python") || typeStr.Contains("csharp")) return ArtifactType.Code;
        return ArtifactType.Text;
    }

    private string GetExtension(ArtifactType type, string rawType)
    {
        return type switch
        {
            ArtifactType.Html => ".html",
            ArtifactType.Mermaid => ".mermaid",
            ArtifactType.Code => rawType.Contains("python") ? ".py" : rawType.Contains("csharp") ? ".cs" : ".js",
            _ => ".txt"
        };
    }
    
    // Simple state machine to parse stream could go here, 
    // but for now let's rely on the Orchestrator to detect blocks 
    // or implement a simple block parser if needed.
}

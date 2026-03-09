using System;

namespace CodeStructureAnalyzer.Models;

public enum ArtifactType
{
    Code,
    Html,
    Mermaid,
    Text
}

public class Artifact
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Title { get; set; } = "Untitled";
    public string Content { get; set; } = "";
    public ArtifactType Type { get; set; } = ArtifactType.Text;
    public string? Language { get; set; }
    public string? FilePath { get; set; }
}

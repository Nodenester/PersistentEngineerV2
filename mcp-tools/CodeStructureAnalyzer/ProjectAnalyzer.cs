using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using CodeStructureAnalyzer.Parsers;

namespace CodeStructureAnalyzer;

public class ProjectAnalyzer
{
    // Folders to skip entirely
    private static readonly HashSet<string> IgnoredFolders = new(StringComparer.OrdinalIgnoreCase)
    {
        "bin", "obj", "node_modules", ".git", ".vs", ".idea", 
        "packages", "TestResults", ".playwright", "wwwroot/lib",
        "dist", "build", "out", "target", ".nuget"
    };

    // Extensions we parse in detail
    private static readonly HashSet<string> ParsedExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".cs", ".js", ".ts", ".jsx", ".tsx", ".py", ".json", 
        ".csproj", ".sln", ".xml", ".razor", ".cshtml"
    };

    // Extensions we just list (no parsing needed, but good to know they exist)
    private static readonly Dictionary<string, string> KnownExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        // Code (parsed in detail)
        { ".cs", "C#" }, { ".js", "JavaScript" }, { ".ts", "TypeScript" },
        { ".jsx", "React" }, { ".tsx", "React TS" }, { ".py", "Python" },
        { ".java", "Java" }, { ".go", "Go" }, { ".rs", "Rust" },
        { ".cpp", "C++" }, { ".c", "C" }, { ".h", "Header" },
        { ".php", "PHP" }, { ".rb", "Ruby" }, { ".swift", "Swift" },
        { ".kt", "Kotlin" }, { ".scala", "Scala" },
        
        // Web
        { ".html", "HTML" }, { ".htm", "HTML" }, { ".css", "CSS" },
        { ".scss", "SCSS" }, { ".sass", "Sass" }, { ".less", "Less" },
        { ".vue", "Vue" }, { ".svelte", "Svelte" },
        
        // Config/Data
        { ".json", "JSON" }, { ".xml", "XML" }, { ".yaml", "YAML" },
        { ".yml", "YAML" }, { ".toml", "TOML" }, { ".ini", "INI" },
        { ".env", "Env" }, { ".config", "Config" },
        
        // .NET
        { ".csproj", "C# Project" }, { ".vbproj", "VB Project" },
        { ".fsproj", "F# Project" }, { ".sln", "Solution" },
        { ".razor", "Razor" }, { ".cshtml", "Razor View" },
        { ".xaml", "XAML" }, { ".resx", "Resources" },
        
        // Docs
        { ".md", "Markdown" }, { ".txt", "Text" }, { ".rst", "RST" },
        
        // Data
        { ".sql", "SQL" }, { ".graphql", "GraphQL" }, { ".proto", "Protobuf" },
        
        // Assets (just list, don't parse)
        { ".png", "Image" }, { ".jpg", "Image" }, { ".jpeg", "Image" },
        { ".gif", "Image" }, { ".svg", "SVG" }, { ".ico", "Icon" },
        { ".webp", "Image" }, { ".bmp", "Image" },
        { ".woff", "Font" }, { ".woff2", "Font" }, { ".ttf", "Font" },
        { ".eot", "Font" }, { ".otf", "Font" },
        { ".mp3", "Audio" }, { ".wav", "Audio" }, { ".ogg", "Audio" },
        { ".mp4", "Video" }, { ".webm", "Video" },
        { ".pdf", "PDF" }, { ".zip", "Archive" }, { ".rar", "Archive" },
        
        // Build/Scripts
        { ".sh", "Shell" }, { ".bat", "Batch" }, { ".ps1", "PowerShell" },
        { ".dockerfile", "Docker" }, { ".dockerignore", "Docker" },
        { ".gitignore", "Git" }, { ".editorconfig", "EditorConfig" },
    };

    public async Task<string> AnalyzeAsync(string folderPath)
    {
        var sb = new StringBuilder();
        var rootName = Path.GetFileName(folderPath.TrimEnd(Path.DirectorySeparatorChar));
        
        sb.AppendLine($"# Project: {rootName}");
        sb.AppendLine();

        var allFiles = GetAllFiles(folderPath).ToList();
        sb.AppendLine($"Total files: {allFiles.Count}");
        sb.AppendLine();

        // First: Show folder structure overview
        sb.AppendLine("## Structure");
        sb.AppendLine("```");
        BuildFolderTree(folderPath, sb, "", allFiles);
        sb.AppendLine("```");
        sb.AppendLine();

        // Second: Show file type summary
        var byExtension = allFiles
            .GroupBy(f => Path.GetExtension(f).ToLowerInvariant())
            .OrderByDescending(g => g.Count())
            .ToList();

        sb.AppendLine("## File Types");
        foreach (var group in byExtension.Take(15)) // Top 15 extensions
        {
            var ext = string.IsNullOrEmpty(group.Key) ? "(no ext)" : group.Key;
            var typeName = KnownExtensions.TryGetValue(group.Key, out var name) ? name : "Other";
            sb.AppendLine($"  {ext}: {group.Count()} ({typeName})");
        }
        if (byExtension.Count > 15)
            sb.AppendLine($"  ...and {byExtension.Count - 15} other types");
        sb.AppendLine();

        // Third: Parse code files in detail
        var codeFiles = allFiles
            .Where(f => ParsedExtensions.Contains(Path.GetExtension(f)))
            .GroupBy(f => Path.GetExtension(f).ToLowerInvariant())
            .OrderByDescending(g => g.Key == ".cs")
            .ThenByDescending(g => g.Key == ".csproj")
            .ThenBy(g => g.Key);

        foreach (var group in codeFiles)
        {
            var ext = group.Key;
            var typeName = KnownExtensions.TryGetValue(ext, out var name) ? name : ext;
            var fileList = group.OrderBy(f => f).ToList();
            
            sb.AppendLine($"## {typeName} ({fileList.Count})");
            sb.AppendLine();

            foreach (var file in fileList)
            {
                var relativePath = Path.GetRelativePath(folderPath, file);
                var parser = GetParser(ext);
                
                if (parser != null)
                {
                    try
                    {
                        var content = await File.ReadAllTextAsync(file);
                        var parsed = parser.Parse(content, relativePath);
                        
                        if (!string.IsNullOrWhiteSpace(parsed))
                        {
                            sb.AppendLine($"### {relativePath}");
                            sb.AppendLine(parsed);
                            sb.AppendLine();
                        }
                    }
                    catch (Exception ex)
                    {
                        sb.AppendLine($"### {relativePath}");
                        sb.AppendLine($"[Error: {ex.Message}]");
                        sb.AppendLine();
                    }
                }
                else
                {
                    // No parser, just list the file
                    var size = new FileInfo(file).Length;
                    sb.AppendLine($"### {relativePath} ({FormatSize(size)})");
                    sb.AppendLine();
                }
            }
        }
        
        return sb.ToString();
    }

    private void BuildFolderTree(string rootPath, StringBuilder sb, string indent, List<string> allFiles)
    {
        var rootName = Path.GetFileName(rootPath.TrimEnd(Path.DirectorySeparatorChar));
        if (string.IsNullOrEmpty(indent))
            sb.AppendLine(rootName + "/");

        try
        {
            // Get directories
            var dirs = Directory.GetDirectories(rootPath)
                .Select(d => Path.GetFileName(d))
                .Where(d => !IgnoredFolders.Contains(d) && !d.StartsWith("."))
                .OrderBy(d => d)
                .ToList();

            // Get files in this directory
            var files = Directory.GetFiles(rootPath)
                .Select(f => Path.GetFileName(f))
                .Where(f => !f.StartsWith(".")) // Skip hidden files
                .OrderBy(f => f)
                .ToList();

            // Count items for formatting
            var totalItems = dirs.Count + files.Count;
            var currentItem = 0;

            // Show directories first (always recurse fully)
            foreach (var dir in dirs)
            {
                currentItem++;
                var isLastItem = currentItem == totalItems;
                var prefix = isLastItem ? "└── " : "├── ";
                var childIndent = indent + (isLastItem ? "    " : "│   ");
                
                var dirPath = Path.Combine(rootPath, dir);
                
                sb.AppendLine($"{indent}{prefix}{dir}/");
                
                // Always recurse into subdirectories
                BuildFolderTree(dirPath, sb, childIndent, allFiles);
            }

            // Show all files
            foreach (var file in files)
            {
                currentItem++;
                var isLastItem = currentItem == totalItems;
                var prefix = isLastItem ? "└── " : "├── ";
                sb.AppendLine($"{indent}{prefix}{file}");
            }
        }
        catch (UnauthorizedAccessException)
        {
            sb.AppendLine($"{indent}└── [access denied]");
        }
    }

    private IEnumerable<string> GetAllFiles(string folder)
    {
        var files = new List<string>();
        
        try
        {
            files.AddRange(Directory.GetFiles(folder));

            foreach (var dir in Directory.GetDirectories(folder))
            {
                var dirName = Path.GetFileName(dir);
                if (!IgnoredFolders.Contains(dirName) && !dirName.StartsWith("."))
                {
                    files.AddRange(GetAllFiles(dir));
                }
            }
        }
        catch (UnauthorizedAccessException)
        {
            // Skip folders we can't access
        }

        return files;
    }

    private ICodeParser? GetParser(string extension)
    {
        return extension.ToLowerInvariant() switch
        {
            ".cs" => new CSharpParser(),
            ".js" or ".jsx" => new JavaScriptParser(),
            ".ts" or ".tsx" => new TypeScriptParser(),
            ".py" => new PythonParser(),
            ".json" => new JsonParser(),
            ".csproj" or ".xml" => new XmlParser(),
            ".razor" or ".cshtml" => new RazorParser(),
            _ => null
        };
    }

    private string FormatSize(long bytes)
    {
        if (bytes < 1024) return $"{bytes}B";
        if (bytes < 1024 * 1024) return $"{bytes / 1024}KB";
        return $"{bytes / (1024 * 1024)}MB";
    }
}

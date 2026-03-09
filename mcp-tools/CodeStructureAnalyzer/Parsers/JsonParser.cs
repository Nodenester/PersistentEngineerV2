using System.Text;
using System.Text.Json;

namespace CodeStructureAnalyzer.Parsers;

public class JsonParser : ICodeParser
{
    public string Parse(string content, string filePath)
    {
        try
        {
            using var doc = JsonDocument.Parse(content);
            var sb = new StringBuilder();
            
            var root = doc.RootElement;
            ParseElement(root, sb, 0, maxDepth: 2);
            
            return sb.ToString().TrimEnd();
        }
        catch (JsonException)
        {
            return "[invalid JSON]";
        }
    }

    private void ParseElement(JsonElement element, StringBuilder sb, int depth, int maxDepth)
    {
        var indent = new string(' ', depth * 2);

        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                var props = element.EnumerateObject().ToList();
                if (depth >= maxDepth && props.Any())
                {
                    sb.AppendLine($"{indent}{{...{props.Count} props}}");
                    return;
                }
                
                foreach (var prop in props)
                {
                    var valueDesc = GetValueDescription(prop.Value, depth + 1, maxDepth);
                    sb.AppendLine($"{indent}{prop.Name}: {valueDesc}");
                }
                break;

            case JsonValueKind.Array:
                var items = element.EnumerateArray().ToList();
                if (items.Count == 0)
                {
                    sb.AppendLine($"{indent}[]");
                }
                else if (depth >= maxDepth)
                {
                    sb.AppendLine($"{indent}[...{items.Count} items]");
                }
                else
                {
                    // Show first few items
                    var sample = items.Take(3);
                    foreach (var item in sample)
                    {
                        var itemDesc = GetValueDescription(item, depth + 1, maxDepth);
                        sb.AppendLine($"{indent}- {itemDesc}");
                    }
                    if (items.Count > 3)
                    {
                        sb.AppendLine($"{indent}...and {items.Count - 3} more");
                    }
                }
                break;
        }
    }

    private string GetValueDescription(JsonElement element, int depth, int maxDepth)
    {
        return element.ValueKind switch
        {
            JsonValueKind.Object => depth >= maxDepth 
                ? $"{{...{element.EnumerateObject().Count()} props}}"
                : "{...}",
            JsonValueKind.Array => $"[{element.GetArrayLength()} items]",
            JsonValueKind.String => TruncateString(element.GetString() ?? "", 40),
            JsonValueKind.Number => element.ToString(),
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            JsonValueKind.Null => "null",
            _ => "?"
        };
    }

    private string TruncateString(string s, int maxLen)
    {
        if (s.Length <= maxLen)
            return $"\"{s}\"";
        return $"\"{s.Substring(0, maxLen - 3)}...\"";
    }
}

using System.Text;
using System.Text.RegularExpressions;

namespace CodeStructureAnalyzer.Parsers;

public class TypeScriptParser : ICodeParser
{
    private readonly JavaScriptParser _jsParser = new();

    public string Parse(string content, string filePath)
    {
        var sb = new StringBuilder();

        // Get base JS parsing
        var jsResult = _jsParser.Parse(content, filePath);

        // Extract interfaces
        var interfaces = ExtractInterfaces(content);
        foreach (var iface in interfaces)
        {
            sb.AppendLine(iface);
        }

        // Extract type aliases
        var types = ExtractTypeAliases(content);
        foreach (var type in types)
        {
            sb.AppendLine(type);
        }

        // Extract enums
        var enums = ExtractEnums(content);
        foreach (var e in enums)
        {
            sb.AppendLine(e);
        }

        // Add the JS-parsed content
        sb.Append(jsResult);

        return sb.ToString().TrimEnd();
    }

    private List<string> ExtractInterfaces(string content)
    {
        var interfaces = new List<string>();
        
        var matches = Regex.Matches(content, 
            @"interface\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+([^{]+))?\s*\{([^}]*)\}",
            RegexOptions.Singleline);
        
        foreach (Match m in matches)
        {
            var name = m.Groups[1].Value;
            var extends = m.Groups[2].Success ? $" : {m.Groups[2].Value.Trim()}" : "";
            var body = m.Groups[3].Value;
            
            var members = ExtractInterfaceMembers(body);
            var memberStr = members.Any() ? $" [{string.Join(", ", members)}]" : "";
            
            interfaces.Add($"interface {name}{extends}{memberStr}");
        }

        return interfaces;
    }

    private List<string> ExtractInterfaceMembers(string body)
    {
        var members = new List<string>();
        
        // Match property declarations
        var propMatches = Regex.Matches(body, @"(\w+)\??:\s*([^;,\n]+)");
        foreach (Match m in propMatches)
        {
            members.Add(m.Groups[1].Value);
        }

        // Match method declarations
        var methodMatches = Regex.Matches(body, @"(\w+)\s*\([^)]*\)\s*:");
        foreach (Match m in methodMatches)
        {
            if (!members.Contains(m.Groups[1].Value))
                members.Add(m.Groups[1].Value + "()");
        }

        return members;
    }

    private List<string> ExtractTypeAliases(string content)
    {
        var types = new List<string>();
        
        var matches = Regex.Matches(content, @"type\s+(\w+)(?:<[^>]+>)?\s*=\s*([^;]+);");
        foreach (Match m in matches)
        {
            var name = m.Groups[1].Value;
            var definition = m.Groups[2].Value.Trim();
            
            // Simplify the type definition
            if (definition.Length > 50)
                definition = definition.Substring(0, 47) + "...";
            
            types.Add($"type {name} = {definition}");
        }

        return types;
    }

    private List<string> ExtractEnums(string content)
    {
        var enums = new List<string>();
        
        var matches = Regex.Matches(content, @"enum\s+(\w+)\s*\{([^}]*)\}");
        foreach (Match m in matches)
        {
            var name = m.Groups[1].Value;
            var body = m.Groups[2].Value;
            
            var values = Regex.Matches(body, @"(\w+)")
                .Cast<Match>()
                .Select(v => v.Groups[1].Value)
                .Distinct()
                .ToList();
            
            enums.Add($"enum {name} [{string.Join(", ", values)}]");
        }

        return enums;
    }
}

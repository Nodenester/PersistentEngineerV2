using System.Text;
using System.Text.RegularExpressions;

namespace CodeStructureAnalyzer.Parsers;

public class PythonParser : ICodeParser
{
    public string Parse(string content, string filePath)
    {
        var sb = new StringBuilder();
        var lines = content.Split('\n');

        // Extract imports
        var imports = ExtractImports(lines);
        if (imports.Any())
        {
            sb.AppendLine($"imports: {string.Join(", ", imports)}");
        }

        // Extract classes with their methods
        var classes = ExtractClasses(content);
        foreach (var cls in classes)
        {
            sb.AppendLine(cls);
        }

        // Extract standalone functions (not in classes)
        var functions = ExtractStandaloneFunctions(content);
        foreach (var func in functions)
        {
            sb.AppendLine($"def {func}");
        }

        // Extract global variables/constants (ALL_CAPS)
        var globals = ExtractGlobals(lines);
        if (globals.Any())
        {
            sb.AppendLine($"globals: {string.Join(", ", globals)}");
        }

        return sb.ToString().TrimEnd();
    }

    private List<string> ExtractImports(string[] lines)
    {
        var imports = new List<string>();
        
        foreach (var line in lines)
        {
            var trimmed = line.Trim();
            
            // import x, y, z
            var importMatch = Regex.Match(trimmed, @"^import\s+(.+)$");
            if (importMatch.Success)
            {
                var modules = importMatch.Groups[1].Value.Split(',')
                    .Select(m => m.Trim().Split(' ')[0]);
                imports.AddRange(modules);
                continue;
            }

            // from x import y
            var fromMatch = Regex.Match(trimmed, @"^from\s+(\S+)\s+import");
            if (fromMatch.Success)
            {
                imports.Add(fromMatch.Groups[1].Value);
            }
        }

        return imports.Distinct().ToList();
    }

    private List<string> ExtractClasses(string content)
    {
        var classes = new List<string>();
        
        // Match class definitions
        var classMatches = Regex.Matches(content, 
            @"^class\s+(\w+)(?:\(([^)]*)\))?:", 
            RegexOptions.Multiline);
        
        foreach (Match m in classMatches)
        {
            var className = m.Groups[1].Value;
            var bases = m.Groups[2].Success && !string.IsNullOrWhiteSpace(m.Groups[2].Value) 
                ? $" : {m.Groups[2].Value.Trim()}" 
                : "";
            
            // Find methods in this class
            var classStart = m.Index + m.Length;
            var methods = ExtractClassMethods(content, classStart);
            var methodStr = methods.Any() ? $" [{string.Join(", ", methods)}]" : "";
            
            classes.Add($"class {className}{bases}{methodStr}");
        }

        return classes;
    }

    private List<string> ExtractClassMethods(string content, int startIndex)
    {
        var methods = new List<string>();
        var remaining = content.Substring(startIndex);
        var lines = remaining.Split('\n');
        
        bool inClass = true;
        foreach (var line in lines)
        {
            // Check if we've exited the class (non-indented, non-empty line)
            if (!string.IsNullOrWhiteSpace(line) && !char.IsWhiteSpace(line[0]) && !line.TrimStart().StartsWith("#"))
            {
                if (!line.TrimStart().StartsWith("@"))  // not a decorator
                    break;
            }

            // Match method definition
            var methodMatch = Regex.Match(line, @"^\s+def\s+(\w+)\s*\(([^)]*)\)");
            if (methodMatch.Success)
            {
                var name = methodMatch.Groups[1].Value;
                var paramsText = methodMatch.Groups[2].Value;
                
                // Simplify params (remove self, type hints, defaults)
                var simplifiedParams = SimplifyParams(paramsText);
                methods.Add($"{name}({simplifiedParams})");
            }
        }

        return methods;
    }

    private List<string> ExtractStandaloneFunctions(string content)
    {
        var functions = new List<string>();
        
        // Match top-level function definitions (no leading whitespace)
        var funcMatches = Regex.Matches(content, 
            @"^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)", 
            RegexOptions.Multiline);
        
        foreach (Match m in funcMatches)
        {
            // Check that it's not indented (not a method)
            var lineStart = content.LastIndexOf('\n', m.Index) + 1;
            var prefix = content.Substring(lineStart, m.Index - lineStart);
            
            if (string.IsNullOrWhiteSpace(prefix) || prefix.TrimStart().StartsWith("@"))
            {
                var name = m.Groups[1].Value;
                var paramsText = SimplifyParams(m.Groups[2].Value);
                functions.Add($"{name}({paramsText})");
            }
        }

        return functions;
    }

    private string SimplifyParams(string paramsText)
    {
        if (string.IsNullOrWhiteSpace(paramsText))
            return "";

        var parts = paramsText.Split(',')
            .Select(p => p.Trim())
            .Select(p => p.Split(':')[0].Trim())  // Remove type hints
            .Select(p => p.Split('=')[0].Trim())  // Remove defaults
            .Where(p => p != "self" && p != "cls" && !string.IsNullOrEmpty(p));

        return string.Join(", ", parts);
    }

    private List<string> ExtractGlobals(string[] lines)
    {
        var globals = new List<string>();
        
        foreach (var line in lines)
        {
            var trimmed = line.Trim();
            
            // Match CONSTANT = value pattern
            var match = Regex.Match(trimmed, @"^([A-Z][A-Z0-9_]+)\s*=");
            if (match.Success)
            {
                globals.Add(match.Groups[1].Value);
            }
        }

        return globals.Distinct().ToList();
    }
}

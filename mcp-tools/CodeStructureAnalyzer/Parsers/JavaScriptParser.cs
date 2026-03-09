using System.Text;
using System.Text.RegularExpressions;

namespace CodeStructureAnalyzer.Parsers;

public class JavaScriptParser : ICodeParser
{
    public string Parse(string content, string filePath)
    {
        var sb = new StringBuilder();

        // Remove comments and strings to avoid false matches
        var cleanContent = RemoveCommentsAndStrings(content);

        // Extract imports
        var imports = ExtractImports(content);
        if (imports.Any())
        {
            sb.AppendLine($"imports: {string.Join(", ", imports)}");
        }

        // Extract exports
        var exports = ExtractExports(content);
        if (exports.Any())
        {
            sb.AppendLine($"exports: {string.Join(", ", exports)}");
        }

        // Extract classes
        var classes = ExtractClasses(cleanContent);
        foreach (var cls in classes)
        {
            sb.AppendLine(cls);
        }

        // Extract standalone functions
        var functions = ExtractFunctions(cleanContent);
        foreach (var func in functions)
        {
            sb.AppendLine($"fn {func}");
        }

        // Extract const/let function expressions (arrow functions, etc.)
        var constFuncs = ExtractConstFunctions(cleanContent);
        foreach (var func in constFuncs)
        {
            sb.AppendLine($"const {func}");
        }

        return sb.ToString().TrimEnd();
    }

    private string RemoveCommentsAndStrings(string content)
    {
        // Remove multi-line comments
        content = Regex.Replace(content, @"/\*[\s\S]*?\*/", " ");
        // Remove single-line comments
        content = Regex.Replace(content, @"//.*$", " ", RegexOptions.Multiline);
        // Remove template literals (simplified)
        content = Regex.Replace(content, @"`[^`]*`", "\"\"");
        // Remove strings
        content = Regex.Replace(content, @"""[^""\\]*(?:\\.[^""\\]*)*""", "\"\"");
        content = Regex.Replace(content, @"'[^'\\]*(?:\\.[^'\\]*)*'", "''");
        return content;
    }

    private List<string> ExtractImports(string content)
    {
        var imports = new List<string>();
        
        // ES6 imports: import X from 'module'
        var es6Matches = Regex.Matches(content, @"import\s+.*?\s+from\s+['""]([^'""]+)['""]");
        foreach (Match m in es6Matches)
        {
            imports.Add(m.Groups[1].Value);
        }

        // Side-effect imports: import 'module'
        var sideEffectMatches = Regex.Matches(content, @"import\s+['""]([^'""]+)['""]");
        foreach (Match m in sideEffectMatches)
        {
            imports.Add(m.Groups[1].Value);
        }

        // require(): require('module')
        var requireMatches = Regex.Matches(content, @"require\s*\(\s*['""]([^'""]+)['""]\s*\)");
        foreach (Match m in requireMatches)
        {
            if (!imports.Contains(m.Groups[1].Value))
                imports.Add(m.Groups[1].Value);
        }

        return imports.Distinct().ToList();
    }

    private List<string> ExtractExports(string content)
    {
        var exports = new List<string>();

        // Named exports: export { x, y }
        var namedMatches = Regex.Matches(content, @"export\s*\{\s*([^}]+)\s*\}");
        foreach (Match m in namedMatches)
        {
            var names = m.Groups[1].Value.Split(',').Select(n => n.Trim().Split(' ')[0]);
            exports.AddRange(names);
        }

        // export const/let/var/function/class
        var directMatches = Regex.Matches(content, @"export\s+(?:default\s+)?(?:const|let|var|function|class|async\s+function)\s+(\w+)");
        foreach (Match m in directMatches)
        {
            exports.Add(m.Groups[1].Value);
        }

        // export default
        if (Regex.IsMatch(content, @"export\s+default\s+"))
        {
            if (!exports.Contains("default"))
                exports.Add("default");
        }

        // module.exports
        if (Regex.IsMatch(content, @"module\.exports\s*="))
        {
            exports.Add("module.exports");
        }

        return exports.Distinct().ToList();
    }

    private List<string> ExtractClasses(string content)
    {
        var classes = new List<string>();
        
        // Match class declarations
        var classMatches = Regex.Matches(content, 
            @"class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{");
        
        foreach (Match m in classMatches)
        {
            var className = m.Groups[1].Value;
            var extends = m.Groups[2].Success ? $" : {m.Groups[2].Value}" : "";
            
            // Try to find methods in the class (simplified)
            var classStart = m.Index + m.Length;
            var classBody = ExtractBraceContent(content, classStart - 1);
            var methods = ExtractClassMethods(classBody);
            
            var methodStr = methods.Any() ? $" [{string.Join(", ", methods)}]" : "";
            classes.Add($"class {className}{extends}{methodStr}");
        }

        return classes;
    }

    private List<string> ExtractClassMethods(string classBody)
    {
        var methods = new List<string>();
        
        // Match method declarations (including async, static, get, set)
        var methodPattern = @"(?:(?:async|static|get|set)\s+)*(\w+)\s*\([^)]*\)\s*\{";
        var matches = Regex.Matches(classBody, methodPattern);
        
        foreach (Match m in matches)
        {
            var methodName = m.Groups[1].Value;
            if (methodName != "if" && methodName != "for" && methodName != "while" && 
                methodName != "switch" && methodName != "catch" && methodName != "function")
            {
                methods.Add(methodName);
            }
        }

        return methods.Distinct().ToList();
    }

    private List<string> ExtractFunctions(string content)
    {
        var functions = new List<string>();
        
        // function declarations
        var funcMatches = Regex.Matches(content, 
            @"(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)");
        
        foreach (Match m in funcMatches)
        {
            var name = m.Groups[1].Value;
            var paramText = SimplifyParams(m.Groups[2].Value);
            functions.Add($"{name}({paramText})");
        }

        return functions;
    }

    private List<string> ExtractConstFunctions(string content)
    {
        var functions = new List<string>();
        
        // const x = () => {} or const x = function() {}
        var constFuncMatches = Regex.Matches(content, 
            @"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>");
        
        foreach (Match m in constFuncMatches)
        {
            functions.Add(m.Groups[1].Value);
        }

        // const x = function
        var constFuncExprMatches = Regex.Matches(content, 
            @"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function");
        
        foreach (Match m in constFuncExprMatches)
        {
            if (!functions.Contains(m.Groups[1].Value))
                functions.Add(m.Groups[1].Value);
        }

        return functions;
    }

    private string SimplifyParams(string params_)
    {
        if (string.IsNullOrWhiteSpace(params_))
            return "";
        
        var parts = params_.Split(',')
            .Select(p => p.Trim().Split('=')[0].Trim())
            .Where(p => !string.IsNullOrEmpty(p));
        
        return string.Join(", ", parts);
    }

    private string ExtractBraceContent(string content, int startIndex)
    {
        if (startIndex < 0 || startIndex >= content.Length || content[startIndex] != '{')
            return "";

        int depth = 0;
        int endIndex = startIndex;
        
        for (int i = startIndex; i < content.Length; i++)
        {
            if (content[i] == '{') depth++;
            else if (content[i] == '}') depth--;
            
            if (depth == 0)
            {
                endIndex = i;
                break;
            }
        }

        return content.Substring(startIndex, endIndex - startIndex + 1);
    }
}

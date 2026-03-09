using System.Text;
using System.Text.RegularExpressions;

namespace CodeStructureAnalyzer.Parsers;

public class RazorParser : ICodeParser
{
    public string Parse(string content, string filePath)
    {
        var sb = new StringBuilder();

        // Extract @page directive
        var pageMatch = Regex.Match(content, @"@page\s+""([^""]+)""");
        if (pageMatch.Success)
        {
            sb.AppendLine($"route: {pageMatch.Groups[1].Value}");
        }

        // Extract @using directives
        var usings = Regex.Matches(content, @"@using\s+(\S+)")
            .Cast<Match>()
            .Select(m => m.Groups[1].Value)
            .ToList();
        if (usings.Any())
        {
            sb.AppendLine($"using: {string.Join(", ", usings)}");
        }

        // Extract @inject directives
        var injects = Regex.Matches(content, @"@inject\s+(\S+)\s+(\S+)")
            .Cast<Match>()
            .Select(m => $"{m.Groups[2].Value}:{m.Groups[1].Value}")
            .ToList();
        if (injects.Any())
        {
            sb.AppendLine($"inject: {string.Join(", ", injects)}");
        }

        // Extract @inherits
        var inheritsMatch = Regex.Match(content, @"@inherits\s+(\S+)");
        if (inheritsMatch.Success)
        {
            sb.AppendLine($"inherits: {inheritsMatch.Groups[1].Value}");
        }

        // Extract @implements
        var implements = Regex.Matches(content, @"@implements\s+(\S+)")
            .Cast<Match>()
            .Select(m => m.Groups[1].Value)
            .ToList();
        if (implements.Any())
        {
            sb.AppendLine($"implements: {string.Join(", ", implements)}");
        }

        // Extract @attribute
        var attributes = Regex.Matches(content, @"@attribute\s+\[([^\]]+)\]")
            .Cast<Match>()
            .Select(m => m.Groups[1].Value)
            .ToList();
        if (attributes.Any())
        {
            sb.AppendLine($"attributes: {string.Join(", ", attributes)}");
        }

        // Extract @code or @functions block
        var codeMatch = Regex.Match(content, @"@(?:code|functions)\s*\{", RegexOptions.Singleline);
        if (codeMatch.Success)
        {
            var codeBlock = ExtractBraceContent(content, codeMatch.Index + codeMatch.Length - 1);
            var codeInfo = ParseCodeBlock(codeBlock);
            if (!string.IsNullOrEmpty(codeInfo))
            {
                sb.AppendLine("@code:");
                sb.Append(codeInfo);
            }
        }

        // Extract component parameters from markup (simplified)
        var components = ExtractComponentUsage(content);
        if (components.Any())
        {
            sb.AppendLine($"uses: {string.Join(", ", components)}");
        }

        return sb.ToString().TrimEnd();
    }

    private string ParseCodeBlock(string codeBlock)
    {
        var sb = new StringBuilder();

        // Extract parameters [Parameter]
        var paramMatches = Regex.Matches(codeBlock, 
            @"\[Parameter[^\]]*\]\s*(?:public|private|protected|internal)?\s*(\w+(?:<[^>]+>)?)\s+(\w+)");
        foreach (Match m in paramMatches)
        {
            sb.AppendLine($"  [P] {m.Groups[1].Value} {m.Groups[2].Value}");
        }

        // Extract [Inject] properties
        var injectMatches = Regex.Matches(codeBlock,
            @"\[Inject[^\]]*\]\s*(?:public|private|protected|internal)?\s*(\w+(?:<[^>]+>)?)\s+(\w+)");
        foreach (Match m in injectMatches)
        {
            sb.AppendLine($"  [I] {m.Groups[1].Value} {m.Groups[2].Value}");
        }

        // Extract methods
        var methodMatches = Regex.Matches(codeBlock,
            @"(?:public|private|protected|internal|async|static|override|virtual|\s)+\s*(\w+(?:<[^>]+>)?)\s+(\w+)\s*\(([^)]*)\)");
        foreach (Match m in methodMatches)
        {
            var returnType = m.Groups[1].Value;
            var methodName = m.Groups[2].Value;
            var paramsRaw = m.Groups[3].Value;
            
            // Skip property accessors and common keywords
            if (methodName == "get" || methodName == "set" || methodName == "if" || 
                methodName == "for" || methodName == "while" || methodName == "switch")
                continue;

            var paramsSimple = SimplifyParams(paramsRaw);
            sb.AppendLine($"  {returnType} {methodName}({paramsSimple})");
        }

        return sb.ToString();
    }

    private List<string> ExtractComponentUsage(string content)
    {
        var components = new HashSet<string>();
        
        // Match PascalCase component tags
        var matches = Regex.Matches(content, @"<([A-Z][a-zA-Z0-9]+)[\s/>]");
        foreach (Match m in matches)
        {
            var name = m.Groups[1].Value;
            // Filter out HTML elements that happen to be capitalized
            if (!IsHtmlElement(name))
            {
                components.Add(name);
            }
        }

        return components.ToList();
    }

    private bool IsHtmlElement(string name)
    {
        var htmlElements = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "A", "Abbr", "Address", "Area", "Article", "Aside", "Audio",
            "B", "Base", "Bdi", "Bdo", "Blockquote", "Body", "Br", "Button",
            "Canvas", "Caption", "Cite", "Code", "Col", "Colgroup",
            "Data", "Datalist", "Dd", "Del", "Details", "Dfn", "Dialog", "Div", "Dl", "Dt",
            "Em", "Embed", "Fieldset", "Figcaption", "Figure", "Footer", "Form",
            "H1", "H2", "H3", "H4", "H5", "H6", "Head", "Header", "Hr", "Html",
            "I", "Iframe", "Img", "Input", "Ins", "Kbd", "Label", "Legend", "Li", "Link",
            "Main", "Map", "Mark", "Meta", "Meter", "Nav", "Noscript",
            "Object", "Ol", "Optgroup", "Option", "Output", "P", "Picture", "Pre", "Progress",
            "Q", "Rp", "Rt", "Ruby", "S", "Samp", "Script", "Section", "Select", "Small",
            "Source", "Span", "Strong", "Style", "Sub", "Summary", "Sup", "Svg",
            "Table", "Tbody", "Td", "Template", "Textarea", "Tfoot", "Th", "Thead", "Time",
            "Title", "Tr", "Track", "U", "Ul", "Var", "Video", "Wbr"
        };
        return htmlElements.Contains(name);
    }

    private string SimplifyParams(string paramsText)
    {
        if (string.IsNullOrWhiteSpace(paramsText))
            return "";

        var parts = paramsText.Split(',')
            .Select(p => p.Trim())
            .Select(p =>
            {
                // Extract type and name
                var tokens = p.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                if (tokens.Length >= 2)
                {
                    var type = tokens[tokens.Length - 2];
                    var name = tokens[tokens.Length - 1].Split('=')[0];
                    return $"{type} {name}";
                }
                return p.Split('=')[0].Trim();
            })
            .Where(p => !string.IsNullOrEmpty(p));

        return string.Join(", ", parts);
    }

    private string ExtractBraceContent(string content, int startIndex)
    {
        if (startIndex < 0 || startIndex >= content.Length)
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

        if (endIndex > startIndex)
            return content.Substring(startIndex + 1, endIndex - startIndex - 1);
        
        return "";
    }
}

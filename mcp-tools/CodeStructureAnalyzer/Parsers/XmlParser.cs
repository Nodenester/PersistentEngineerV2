using System.Text;
using System.Xml.Linq;

namespace CodeStructureAnalyzer.Parsers;

public class XmlParser : ICodeParser
{
    public string Parse(string content, string filePath)
    {
        try
        {
            var doc = XDocument.Parse(content);
            var sb = new StringBuilder();
            
            if (doc.Root == null)
                return "[empty XML]";

            // Check if it's a .csproj file
            if (filePath.EndsWith(".csproj", StringComparison.OrdinalIgnoreCase))
            {
                ParseCsproj(doc.Root, sb);
            }
            else
            {
                ParseGenericXml(doc.Root, sb, 0, maxDepth: 2);
            }
            
            return sb.ToString().TrimEnd();
        }
        catch (Exception)
        {
            return "[invalid XML]";
        }
    }

    private void ParseCsproj(XElement root, StringBuilder sb)
    {
        // Extract SDK
        var sdk = root.Attribute("Sdk")?.Value;
        if (!string.IsNullOrEmpty(sdk))
            sb.AppendLine($"SDK: {sdk}");

        // Extract target framework
        var targetFramework = root.Descendants()
            .FirstOrDefault(e => e.Name.LocalName == "TargetFramework")?.Value;
        var targetFrameworks = root.Descendants()
            .FirstOrDefault(e => e.Name.LocalName == "TargetFrameworks")?.Value;
        
        if (!string.IsNullOrEmpty(targetFramework))
            sb.AppendLine($"Target: {targetFramework}");
        else if (!string.IsNullOrEmpty(targetFrameworks))
            sb.AppendLine($"Targets: {targetFrameworks}");

        // Extract output type
        var outputType = root.Descendants()
            .FirstOrDefault(e => e.Name.LocalName == "OutputType")?.Value;
        if (!string.IsNullOrEmpty(outputType))
            sb.AppendLine($"Output: {outputType}");

        // Extract nullable setting
        var nullable = root.Descendants()
            .FirstOrDefault(e => e.Name.LocalName == "Nullable")?.Value;
        if (!string.IsNullOrEmpty(nullable))
            sb.AppendLine($"Nullable: {nullable}");

        // Extract PackageReferences
        var packages = root.Descendants()
            .Where(e => e.Name.LocalName == "PackageReference")
            .Select(e => new { 
                Name = e.Attribute("Include")?.Value ?? "", 
                Version = e.Attribute("Version")?.Value ?? "" 
            })
            .Where(p => !string.IsNullOrEmpty(p.Name))
            .ToList();

        if (packages.Any())
        {
            sb.AppendLine("Packages:");
            foreach (var pkg in packages)
            {
                var version = string.IsNullOrEmpty(pkg.Version) ? "" : $" ({pkg.Version})";
                sb.AppendLine($"  - {pkg.Name}{version}");
            }
        }

        // Extract ProjectReferences
        var projectRefs = root.Descendants()
            .Where(e => e.Name.LocalName == "ProjectReference")
            .Select(e => e.Attribute("Include")?.Value)
            .Where(p => !string.IsNullOrEmpty(p))
            .ToList();

        if (projectRefs.Any())
        {
            sb.AppendLine("Project refs:");
            foreach (var proj in projectRefs)
            {
                sb.AppendLine($"  - {proj}");
            }
        }
    }

    private void ParseGenericXml(XElement element, StringBuilder sb, int depth, int maxDepth)
    {
        var indent = new string(' ', depth * 2);
        var name = element.Name.LocalName;
        var attrs = element.Attributes()
            .Where(a => !a.IsNamespaceDeclaration)
            .Select(a => $"{a.Name.LocalName}={TruncateString(a.Value, 20)}")
            .ToList();
        
        var attrStr = attrs.Any() ? $" [{string.Join(", ", attrs)}]" : "";
        
        if (depth >= maxDepth)
        {
            var childCount = element.Elements().Count();
            if (childCount > 0)
            {
                sb.AppendLine($"{indent}<{name}>{attrStr} ...{childCount} children");
            }
            else if (!string.IsNullOrWhiteSpace(element.Value))
            {
                sb.AppendLine($"{indent}<{name}>{attrStr} = {TruncateString(element.Value.Trim(), 50)}");
            }
            else
            {
                sb.AppendLine($"{indent}<{name}>{attrStr}");
            }
            return;
        }

        var hasChildren = element.Elements().Any();
        if (hasChildren)
        {
            sb.AppendLine($"{indent}<{name}>{attrStr}");
            foreach (var child in element.Elements())
            {
                ParseGenericXml(child, sb, depth + 1, maxDepth);
            }
        }
        else if (!string.IsNullOrWhiteSpace(element.Value))
        {
            sb.AppendLine($"{indent}<{name}>{attrStr} = {TruncateString(element.Value.Trim(), 50)}");
        }
        else
        {
            sb.AppendLine($"{indent}<{name}>{attrStr}");
        }
    }

    private string TruncateString(string s, int maxLen)
    {
        s = s.Replace("\n", " ").Replace("\r", "");
        if (s.Length <= maxLen)
            return s;
        return s.Substring(0, maxLen - 3) + "...";
    }
}

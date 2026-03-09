using System.Text;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace CodeStructureAnalyzer.Parsers;

public class CSharpParser : ICodeParser
{
    public string Parse(string content, string filePath)
    {
        var tree = CSharpSyntaxTree.ParseText(content);
        var root = tree.GetCompilationUnitRoot();
        var sb = new StringBuilder();

        // Extract usings (compact format)
        var usings = root.Usings.Select(u => u.Name?.ToString()).Where(u => u != null).ToList();
        if (usings.Any())
        {
            sb.AppendLine($"using: {string.Join(", ", usings!)}");
        }

        // Process all type declarations (classes, interfaces, structs, records)
        var types = root.DescendantNodes()
            .OfType<TypeDeclarationSyntax>()
            .Where(t => t.Parent is NamespaceDeclarationSyntax || 
                       t.Parent is FileScopedNamespaceDeclarationSyntax ||
                       t.Parent is CompilationUnitSyntax);

        foreach (var type in types)
        {
            ParseType(type, sb, 0);
        }

        // Process enums separately (they're not TypeDeclarationSyntax)
        var enums = root.DescendantNodes()
            .OfType<EnumDeclarationSyntax>()
            .Where(e => e.Parent is NamespaceDeclarationSyntax || 
                       e.Parent is FileScopedNamespaceDeclarationSyntax ||
                       e.Parent is CompilationUnitSyntax);

        foreach (var enumDecl in enums)
        {
            ParseEnum(enumDecl, sb);
        }

        // Top-level statements (for minimal APIs, etc.)
        var topLevelStatements = root.Members.OfType<GlobalStatementSyntax>().ToList();
        if (topLevelStatements.Any())
        {
            sb.AppendLine("[top-level code]");
        }

        return sb.ToString().TrimEnd();
    }

    private void ParseEnum(EnumDeclarationSyntax enumDecl, StringBuilder sb)
    {
        var ns = GetNamespace(enumDecl);
        var modifiers = GetModifiers(enumDecl.Modifiers);
        
        if (!string.IsNullOrEmpty(ns))
        {
            sb.AppendLine($"ns: {ns}");
        }
        
        sb.AppendLine($"{modifiers}enum {enumDecl.Identifier}");
        var values = enumDecl.Members.Select(m => m.Identifier.Text);
        sb.AppendLine($"  values: {string.Join(", ", values)}");
    }

    private void ParseType(TypeDeclarationSyntax type, StringBuilder sb, int indent)
    {
        var prefix = new string(' ', indent * 2);
        var ns = GetNamespace(type);
        
        // Type declaration
        var typeKind = type switch
        {
            ClassDeclarationSyntax => "class",
            InterfaceDeclarationSyntax => "interface",
            RecordDeclarationSyntax r => r.ClassOrStructKeyword.Text == "struct" ? "record struct" : "record",
            StructDeclarationSyntax => "struct",
            _ => "type"
        };

        var modifiers = GetModifiers(type.Modifiers);
        var baseTypes = type.BaseList?.Types.Select(t => t.ToString()).ToList() ?? new List<string>();
        var baseStr = baseTypes.Any() ? $" : {string.Join(", ", baseTypes)}" : "";
        var genericParams = type.TypeParameterList?.ToString() ?? "";

        if (!string.IsNullOrEmpty(ns) && indent == 0)
        {
            sb.AppendLine($"{prefix}ns: {ns}");
        }

        sb.AppendLine($"{prefix}{modifiers}{typeKind} {type.Identifier}{genericParams}{baseStr}");

        // Fields (only public/important ones)
        var fields = type.Members.OfType<FieldDeclarationSyntax>()
            .Where(f => f.Modifiers.Any(m => m.IsKind(SyntaxKind.PublicKeyword) || 
                                             m.IsKind(SyntaxKind.ProtectedKeyword) ||
                                             m.IsKind(SyntaxKind.StaticKeyword)));
        
        foreach (var field in fields)
        {
            var fieldMods = GetModifiers(field.Modifiers);
            var fieldType = field.Declaration.Type.ToString();
            var names = string.Join(", ", field.Declaration.Variables.Select(v => v.Identifier.Text));
            sb.AppendLine($"{prefix}  {fieldMods}{fieldType} {names}");
        }

        // Properties
        var properties = type.Members.OfType<PropertyDeclarationSyntax>();
        foreach (var prop in properties)
        {
            var propMods = GetModifiers(prop.Modifiers);
            var accessors = GetAccessors(prop);
            sb.AppendLine($"{prefix}  {propMods}{prop.Type} {prop.Identifier} {accessors}");
        }

        // Constructors
        var ctors = type.Members.OfType<ConstructorDeclarationSyntax>();
        foreach (var ctor in ctors)
        {
            var ctorMods = GetModifiers(ctor.Modifiers);
            var parameters = GetParameters(ctor.ParameterList);
            sb.AppendLine($"{prefix}  {ctorMods}{ctor.Identifier}({parameters})");
        }

        // Methods
        var methods = type.Members.OfType<MethodDeclarationSyntax>();
        foreach (var method in methods)
        {
            var methodMods = GetModifiers(method.Modifiers);
            var genericMethodParams = method.TypeParameterList?.ToString() ?? "";
            var parameters = GetParameters(method.ParameterList);
            sb.AppendLine($"{prefix}  {methodMods}{method.ReturnType} {method.Identifier}{genericMethodParams}({parameters})");
        }

        // Events
        var events = type.Members.OfType<EventDeclarationSyntax>();
        foreach (var evt in events)
        {
            sb.AppendLine($"{prefix}  event {evt.Type} {evt.Identifier}");
        }

        var eventFields = type.Members.OfType<EventFieldDeclarationSyntax>();
        foreach (var evt in eventFields)
        {
            var names = string.Join(", ", evt.Declaration.Variables.Select(v => v.Identifier.Text));
            sb.AppendLine($"{prefix}  event {evt.Declaration.Type} {names}");
        }

        // Nested types
        var nestedTypes = type.Members.OfType<TypeDeclarationSyntax>();
        foreach (var nested in nestedTypes)
        {
            ParseType(nested, sb, indent + 1);
        }
    }

    private string GetNamespace(SyntaxNode node)
    {
        var parent = node.Parent;
        while (parent != null)
        {
            if (parent is NamespaceDeclarationSyntax ns)
                return ns.Name.ToString();
            if (parent is FileScopedNamespaceDeclarationSyntax fsns)
                return fsns.Name.ToString();
            parent = parent.Parent;
        }
        return "";
    }

    private string GetModifiers(SyntaxTokenList modifiers)
    {
        if (!modifiers.Any()) return "";
        
        var relevant = modifiers
            .Where(m => m.IsKind(SyntaxKind.PublicKeyword) ||
                       m.IsKind(SyntaxKind.PrivateKeyword) ||
                       m.IsKind(SyntaxKind.ProtectedKeyword) ||
                       m.IsKind(SyntaxKind.InternalKeyword) ||
                       m.IsKind(SyntaxKind.StaticKeyword) ||
                       m.IsKind(SyntaxKind.AbstractKeyword) ||
                       m.IsKind(SyntaxKind.VirtualKeyword) ||
                       m.IsKind(SyntaxKind.OverrideKeyword) ||
                       m.IsKind(SyntaxKind.AsyncKeyword) ||
                       m.IsKind(SyntaxKind.SealedKeyword) ||
                       m.IsKind(SyntaxKind.PartialKeyword))
            .Select(m => m.Text);

        var result = string.Join(" ", relevant);
        return string.IsNullOrEmpty(result) ? "" : result + " ";
    }

    private string GetParameters(ParameterListSyntax? paramList)
    {
        if (paramList == null || !paramList.Parameters.Any())
            return "";

        var parameters = paramList.Parameters.Select(p =>
        {
            var mods = p.Modifiers.Any() ? string.Join(" ", p.Modifiers.Select(m => m.Text)) + " " : "";
            var defaultVal = p.Default != null ? " = ..." : "";
            return $"{mods}{p.Type} {p.Identifier}{defaultVal}";
        });

        return string.Join(", ", parameters);
    }

    private string GetAccessors(PropertyDeclarationSyntax prop)
    {
        if (prop.ExpressionBody != null)
            return "=> ...";
        
        if (prop.AccessorList == null)
            return "";

        var accessors = new List<string>();
        foreach (var accessor in prop.AccessorList.Accessors)
        {
            var keyword = accessor.Keyword.Text;
            var mods = accessor.Modifiers.Any() 
                ? string.Join(" ", accessor.Modifiers.Select(m => m.Text)) + " " 
                : "";
            accessors.Add($"{mods}{keyword}");
        }
        
        return $"{{ {string.Join("; ", accessors)} }}";
    }
}

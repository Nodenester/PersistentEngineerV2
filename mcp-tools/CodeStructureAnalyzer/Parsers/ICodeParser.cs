namespace CodeStructureAnalyzer.Parsers;

public interface ICodeParser
{
    string Parse(string content, string filePath);
}

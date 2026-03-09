using System;
using System.Threading.Tasks;
using StreamJsonRpc;
using Nerdbank.Streams;

namespace GitPublisher;

class Program
{
    static async Task<int> Main(string[] args)
    {
        try
        {
            Console.Error.WriteLine("[GitPublisher] Starting MCP server...");

            // Setup streams using pipe reader/writer
            var stream = Console.OpenStandardOutput().UsePipeWriter();
            var input = Console.OpenStandardInput().UsePipeReader();

            // Setup Message Handler - NewLineDelimited is standard for MCP
            var formatter = new JsonMessageFormatter();
            formatter.JsonSerializer.ContractResolver = new Newtonsoft.Json.Serialization.CamelCasePropertyNamesContractResolver();
            formatter.JsonSerializer.NullValueHandling = Newtonsoft.Json.NullValueHandling.Ignore;
            var handler = new NewLineDelimitedMessageHandler(stream, input, formatter);

            var server = new McpServer();
            using var jsonRpc = new JsonRpc(handler, server);

            jsonRpc.StartListening();
            Console.Error.WriteLine("[GitPublisher] MCP server ready");

            await jsonRpc.Completion;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[GitPublisher] Error: {ex.Message}");
            return 1;
        }
        return 0;
    }
}

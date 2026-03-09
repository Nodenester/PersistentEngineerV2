using System;
using System.IO;
using System.Threading.Tasks;
using StreamJsonRpc;
using Nerdbank.Streams;

namespace CodeStructureAnalyzer
{
    class Program
    {
        static async Task<int> Main(string[] args)
        {
            try 
            {
                // 1. Setup streams
                var stream = Console.OpenStandardOutput().UsePipeWriter();
                var input = Console.OpenStandardInput().UsePipeReader();

                // 2. Setup Message Handler (NewLine is standard for many simple MCP clients)
                var formatter = new JsonMessageFormatter();
                formatter.JsonSerializer.ContractResolver = new Newtonsoft.Json.Serialization.CamelCasePropertyNamesContractResolver();
                formatter.JsonSerializer.NullValueHandling = Newtonsoft.Json.NullValueHandling.Ignore;
                var handler = new NewLineDelimitedMessageHandler(stream, input, formatter);

                var server = new McpServer();
                using var jsonRpc = new JsonRpc(handler, server);
                
                // 4. Start
                jsonRpc.StartListening();
                await jsonRpc.Completion;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"MCP Server Error: {ex.Message}");
                return 1;
            }
            return 0;
        }
    }
}

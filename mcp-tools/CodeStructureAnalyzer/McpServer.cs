using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using StreamJsonRpc;
using Newtonsoft.Json.Linq;
using VllmChat.Models;

namespace CodeStructureAnalyzer
{
    public class McpServer
    {
        private readonly ProjectAnalyzer _analyzer;

        public McpServer()
        {
            _analyzer = new ProjectAnalyzer();
        }

        [JsonRpcMethod("initialize")]
        public object Initialize(object clientInfo, string protocolVersion, object capabilities)
        {
            return new
            {
                protocolVersion = "2025-06-18",
                capabilities = new
                {
                    tools = new { listChanged = false }
                },
                serverInfo = new
                {
                    name = "CodeStructureAnalyzer",
                    version = "1.0.0"
                }
            };
        }

        [JsonRpcMethod("ping")]
        public object Ping()
        {
            return new { };
        }

        [JsonRpcMethod("tools/list")]
        public object ToolsList()
        {
            return new
            {
                tools = new[]
                {
                    new McpTool
                    {
                        Name = "analyze_codebase",
                        Description = "Analyzes the file structure and contents of a codebase directory.",
                        InputSchema = new McpInputSchema
                        {
                            Type = "object",
                            Properties = new Dictionary<string, McpPropertySchema>
                            {
                                ["path"] = new McpPropertySchema { Type = "string", Description = "Absolute path." }
                            },
                            Required = new List<string> { "path" }
                        }
                    }
                }
            };
        }

        // MCP tools/call accepts: name, arguments, and optionally _meta
        [JsonRpcMethod("tools/call")]
        public async Task<McpToolResult> ToolsCallAsync(string name, JToken arguments, JToken _meta = null)
        {
            if (name != "analyze_codebase")
            {
                throw new Exception($"Unknown tool: {name}");
            }

            string path = null;

            // Robust JToken parsing
            if (arguments != null)
            {
                if (arguments.Type == JTokenType.Object)
                {
                    path = arguments["path"]?.ToString();
                }
            }

            if (string.IsNullOrWhiteSpace(path))
            {
                throw new Exception("Missing 'path' argument.");
            }

            try 
            {
                var analysis = await _analyzer.AnalyzeAsync(path);
                return new McpToolResult
                {
                    Content = new List<McpContent>
                    {
                        new McpContent { Type = "text", Text = analysis }
                    },
                    IsError = false
                };
            }
            catch (Exception ex)
            {
                return new McpToolResult
                {
                    Content = new List<McpContent>
                    {
                        new McpContent { Type = "text", Text = $"Error analyzing path: {ex.Message}" }
                    },
                    IsError = true
                };
            }
        }
    }
}

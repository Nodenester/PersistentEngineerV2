using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using StreamJsonRpc;
using Newtonsoft.Json.Linq;

namespace AgentMemory;

public class McpServer
{
    private readonly string _memoryDir;
    private readonly string _memoryFile;
    private Dictionary<string, object> _memory = new();

    public McpServer()
    {
        _memoryDir = Environment.GetEnvironmentVariable("AGENT_MEMORY_PATH") 
            ?? "/workspace/.agent-memory";
        _memoryFile = Path.Combine(_memoryDir, "memory.json");
        
        LoadMemory();
    }

    private void LoadMemory()
    {
        try
        {
            if (File.Exists(_memoryFile))
            {
                var json = File.ReadAllText(_memoryFile);
                _memory = JsonSerializer.Deserialize<Dictionary<string, object>>(json) ?? new();
                Console.Error.WriteLine($"[AgentMemory] Loaded {_memory.Count} memory entries");
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[AgentMemory] Failed to load memory: {ex.Message}");
            _memory = new();
        }
    }

    private void SaveMemory()
    {
        try
        {
            Directory.CreateDirectory(_memoryDir);
            var json = JsonSerializer.Serialize(_memory, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(_memoryFile, json);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[AgentMemory] Failed to save memory: {ex.Message}");
        }
    }

    [JsonRpcMethod("initialize")]
    public object Initialize(JToken? clientInfo = null, JToken? protocolVersion = null, JToken? capabilities = null)
    {
        Console.Error.WriteLine("[AgentMemory] Initialize called");
        return new
        {
            protocolVersion = "2024-11-05",
            capabilities = new
            {
                tools = new { listChanged = false }
            },
            serverInfo = new
            {
                name = "agent-memory",
                version = "1.0.0"
            }
        };
    }

    [JsonRpcMethod("notifications/initialized")]
    public void Initialized()
    {
        Console.Error.WriteLine("[AgentMemory] Initialized notification received");
    }

    [JsonRpcMethod("ping")]
    public object Ping() => new { };

    [JsonRpcMethod("tools/list")]
    public object ToolsList()
    {
        var tools = new List<object>
        {
            new
            {
                name = "memory_read",
                description = "Read a value from agent memory. Use this to recall information saved earlier in this session or by sub-agents.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["key"] = new { type = "string", description = "The key to read" }
                    },
                    required = new[] { "key" }
                }
            },
            new
            {
                name = "memory_write",
                description = "Write a value to agent memory. Use this to save important context, decisions, or findings for other agents or future reference.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["key"] = new { type = "string", description = "The key to write" },
                        ["value"] = new { type = "string", description = "The value to store" }
                    },
                    required = new[] { "key", "value" }
                }
            },
            new
            {
                name = "memory_append",
                description = "Append to an existing memory value. Useful for adding to lists or logs.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["key"] = new { type = "string", description = "The key to append to" },
                        ["value"] = new { type = "string", description = "The value to append" }
                    },
                    required = new[] { "key", "value" }
                }
            },
            new
            {
                name = "memory_list",
                description = "List all keys in agent memory.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>(),
                    required = Array.Empty<string>()
                }
            },
            new
            {
                name = "memory_delete",
                description = "Delete a key from agent memory.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["key"] = new { type = "string", description = "The key to delete" }
                    },
                    required = new[] { "key" }
                }
            },
            new
            {
                name = "memory_clear",
                description = "Clear all agent memory. Use with caution!",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>(),
                    required = Array.Empty<string>()
                }
            }
        };

        return new { tools };
    }

    [JsonRpcMethod("tools/call")]
    public object ToolsCall(string name, JToken arguments, JToken? _meta = null)
    {
        try
        {
            return name switch
            {
                "memory_read" => MemoryRead(arguments["key"]?.ToString() ?? ""),
                "memory_write" => MemoryWrite(arguments["key"]?.ToString() ?? "", arguments["value"]?.ToString() ?? ""),
                "memory_append" => MemoryAppend(arguments["key"]?.ToString() ?? "", arguments["value"]?.ToString() ?? ""),
                "memory_list" => MemoryList(),
                "memory_delete" => MemoryDelete(arguments["key"]?.ToString() ?? ""),
                "memory_clear" => MemoryClear(),
                _ => Error($"Unknown tool: {name}")
            };
        }
        catch (Exception ex)
        {
            return Error(ex.Message);
        }
    }

    private object MemoryRead(string key)
    {
        if (string.IsNullOrEmpty(key))
            return Error("Key is required");

        if (_memory.TryGetValue(key, out var value))
        {
            return Success($"{value}");
        }
        return Success($"(no value for key '{key}')");
    }

    private object MemoryWrite(string key, string value)
    {
        if (string.IsNullOrEmpty(key))
            return Error("Key is required");

        _memory[key] = value;
        SaveMemory();
        
        Console.Error.WriteLine($"[AgentMemory] Wrote: {key}");
        return Success($"Saved '{key}'");
    }

    private object MemoryAppend(string key, string value)
    {
        if (string.IsNullOrEmpty(key))
            return Error("Key is required");

        if (_memory.TryGetValue(key, out var existing))
        {
            _memory[key] = $"{existing}\n{value}";
        }
        else
        {
            _memory[key] = value;
        }
        SaveMemory();
        
        Console.Error.WriteLine($"[AgentMemory] Appended to: {key}");
        return Success($"Appended to '{key}'");
    }

    private object MemoryList()
    {
        if (_memory.Count == 0)
            return Success("(memory is empty)");

        var lines = new List<string> { $"Memory contains {_memory.Count} entries:\n" };
        foreach (var key in _memory.Keys)
        {
            var preview = _memory[key]?.ToString() ?? "";
            if (preview.Length > 50) preview = preview[..50] + "...";
            lines.Add($"• {key}: {preview}");
        }
        return Success(string.Join("\n", lines));
    }

    private object MemoryDelete(string key)
    {
        if (string.IsNullOrEmpty(key))
            return Error("Key is required");

        if (_memory.Remove(key))
        {
            SaveMemory();
            return Success($"Deleted '{key}'");
        }
        return Success($"Key '{key}' not found");
    }

    private object MemoryClear()
    {
        _memory.Clear();
        SaveMemory();
        return Success("Memory cleared");
    }

    private static object Success(string text) => new
    {
        content = new[] { new { type = "text", text } },
        isError = false
    };

    private static object Error(string message) => new
    {
        content = new[] { new { type = "text", text = $"Error: {message}" } },
        isError = true
    };
}

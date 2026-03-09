using System.Text.Json.Serialization;

namespace VllmChat.Models;

// MCP (Model Context Protocol) Models
public class McpServer
{
    public string Id { get; set; } = Guid.NewGuid().ToString();
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string Endpoint { get; set; } = string.Empty;
    public McpServerStatus Status { get; set; } = McpServerStatus.Disconnected;
    public List<McpTool> Tools { get; set; } = new();
    public List<McpResource> Resources { get; set; } = new();
}

public enum McpServerStatus
{
    Disconnected,
    Connecting,
    Connected,
    Error
}

public class McpTool
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
    
    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;
    
    [JsonPropertyName("inputSchema")]
    public McpInputSchema InputSchema { get; set; } = new();
}

public class McpInputSchema
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "object";
    
    [JsonPropertyName("properties")]
    public Dictionary<string, McpPropertySchema> Properties { get; set; } = new();
    
    [JsonPropertyName("required")]
    public List<string> Required { get; set; } = new();
}

public class McpPropertySchema
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "string";
    
    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;
    
    [JsonPropertyName("enum")]
    public List<string>? Enum { get; set; }
}

public class McpResource
{
    [JsonPropertyName("uri")]
    public string Uri { get; set; } = string.Empty;
    
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
    
    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;
    
    [JsonPropertyName("mimeType")]
    public string MimeType { get; set; } = "text/plain";
}

public class McpToolCallRequest
{
    [JsonPropertyName("jsonrpc")]
    public string JsonRpc { get; set; } = "2.0";
    
    [JsonPropertyName("id")]
    public string Id { get; set; } = Guid.NewGuid().ToString();
    
    [JsonPropertyName("method")]
    public string Method { get; set; } = "tools/call";
    
    [JsonPropertyName("params")]
    public McpToolCallParams Params { get; set; } = new();
}

public class McpToolCallParams
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
    
    [JsonPropertyName("arguments")]
    public Dictionary<string, object> Arguments { get; set; } = new();
}

public class McpToolCallResponse
{
    [JsonPropertyName("jsonrpc")]
    public string JsonRpc { get; set; } = "2.0";
    
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;
    
    [JsonPropertyName("result")]
    public McpToolResult? Result { get; set; }
    
    [JsonPropertyName("error")]
    public McpError? Error { get; set; }
}

public class McpToolResult
{
    [JsonPropertyName("content")]
    public List<McpContent> Content { get; set; } = new();
    
    [JsonPropertyName("isError")]
    public bool IsError { get; set; }
}

public class McpContent
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = "text";
    
    [JsonPropertyName("text")]
    public string? Text { get; set; }
}

public class McpError
{
    [JsonPropertyName("code")]
    public int Code { get; set; }
    
    [JsonPropertyName("message")]
    public string Message { get; set; } = string.Empty;
}

// Settings model
public class ChatSettings
{
    public string SystemPrompt { get; set; } = "You are a professional AI assistant with full agentic capabilities. You have access to various tools and MCP servers. Always follow this workflow: 1. Think through the problem in <think></think> tags. 2. If you need to use a tool, explain it briefly and then IMMEDIATELY output the tool call. 3. Do not stop until you have provided a final answer. Be technical, precise, and favor tool use whenever appropriate.";
    public float Temperature { get; set; } = 0.7f;
    public int MaxTokens { get; set; } = 32768;
    public string ModelName { get; set; } = "default";
    public bool ShowThinking { get; set; } = true;
    public bool EnableTools { get; set; } = true;
    public bool EnableMcp { get; set; } = true;
    public bool RequirePythonApproval { get; set; } = false;
}

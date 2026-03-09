#!/usr/bin/env python3
"""
Agent Network MCP Server

Provides tools for agents to interact with the Agent Network:
- Connect/disconnect from the network
- Send and receive direct messages
- Participate in group chats
- Access shared filesystem
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any, Optional

import httpx

# MCP protocol imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP package not installed. Installing...", file=sys.stderr)
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "mcp"], check=True)
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent


class AgentNetworkClient:
    """HTTP client for Agent Network API."""

    def __init__(self, base_url: str, agent_name: str):
        self.base_url = base_url.rstrip('/')
        self.agent_name = agent_name
        self.connected = False

    async def request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make HTTP request to Agent Network."""
        url = f"{self.base_url}/api/network{endpoint}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, **kwargs)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": response.text, "status": response.status_code}

    async def connect(self) -> dict:
        """Connect to the agent network."""
        result = await self.request("POST", "/connect", json={"AgentName": self.agent_name})
        if result.get("success"):
            self.connected = True
        return result

    async def disconnect(self) -> dict:
        """Disconnect from the agent network."""
        result = await self.request("POST", "/disconnect", json={"AgentName": self.agent_name})
        self.connected = False
        return result

    async def get_status(self) -> dict:
        """Get network status."""
        return await self.request("GET", "/status")

    async def get_agents(self) -> dict:
        """Get list of connected agents."""
        return await self.request("GET", "/agents")

    async def send_dm(self, to: str, message: str) -> dict:
        """Send direct message."""
        return await self.request("POST", "/dm", json={
            "From": self.agent_name,
            "To": to,
            "Message": message
        })

    async def get_inbox(self, limit: int = 50) -> dict:
        """Get inbox messages."""
        return await self.request("GET", f"/inbox?agentName={self.agent_name}&limit={limit}")

    async def create_group(self, name: str) -> dict:
        """Create a group."""
        return await self.request("POST", "/group/create", json={"Name": name})

    async def send_group_message(self, group: str, message: str) -> dict:
        """Send message to group."""
        return await self.request("POST", "/group/send", json={
            "From": self.agent_name,
            "Group": group,
            "Message": message
        })

    async def get_group_messages(self, group: str, limit: int = 50) -> dict:
        """Get group messages."""
        return await self.request("GET", f"/group/read?group={group}&limit={limit}")

    async def get_groups(self) -> dict:
        """Get list of groups."""
        return await self.request("GET", "/groups")

    async def write_file(self, path: str, content: str) -> dict:
        """Write file to shared filesystem."""
        return await self.request("POST", "/file/write", json={
            "Path": path,
            "Content": content
        })

    async def read_file(self, path: str) -> dict:
        """Read file from shared filesystem."""
        return await self.request("GET", f"/file/read?path={path}")

    async def list_files(self, folder: str = "") -> dict:
        """List files in shared filesystem."""
        return await self.request("GET", f"/file/list?folder={folder}")

    async def search_files(self, query: str) -> dict:
        """Search files in shared filesystem."""
        return await self.request("GET", f"/file/search?query={query}")


# Initialize server and client
server = Server("agent-network")
network_url = os.environ.get("AGENT_NETWORK_URL", "http://host.docker.internal:5050")
agent_name = os.environ.get("AGENT_NAME", "unknown-agent")
client = AgentNetworkClient(network_url, agent_name)


@server.list_tools()
async def list_tools():
    """List available Agent Network tools."""
    return [
        Tool(
            name="network_connect",
            description="Connect to the Agent Network. Call this first before using other network tools.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="network_disconnect",
            description="Disconnect from the Agent Network.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="network_status",
            description="Get connection status and network info.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="network_agents",
            description="List all agents currently connected to the network.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="network_dm",
            description="Send a direct message to another agent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Name of the agent to message"},
                    "message": {"type": "string", "description": "The message content"}
                },
                "required": ["to", "message"]
            }
        ),
        Tool(
            name="network_inbox",
            description="Read received direct messages.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "number", "description": "Maximum messages to retrieve (default: 50)"}
                },
                "required": []
            }
        ),
        Tool(
            name="network_group_create",
            description="Create a new group chat.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the group"}
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="network_group_send",
            description="Send a message to a group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group": {"type": "string", "description": "Name of the group"},
                    "message": {"type": "string", "description": "The message content"}
                },
                "required": ["group", "message"]
            }
        ),
        Tool(
            name="network_group_read",
            description="Read messages from a group.",
            inputSchema={
                "type": "object",
                "properties": {
                    "group": {"type": "string", "description": "Name of the group"},
                    "limit": {"type": "number", "description": "Maximum messages to retrieve (default: 50)"}
                },
                "required": ["group"]
            }
        ),
        Tool(
            name="network_groups",
            description="List all available groups.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="network_file_write",
            description="Write/upload a file to the shared filesystem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (e.g., 'docs/readme.md')"},
                    "content": {"type": "string", "description": "File content"}
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="network_file_read",
            description="Read a file from the shared filesystem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="network_file_list",
            description="List files in the shared filesystem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "Folder path (optional, lists root if not specified)"}
                },
                "required": []
            }
        ),
        Tool(
            name="network_file_search",
            description="Search for files by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "network_connect":
            result = await client.connect()
        elif name == "network_disconnect":
            result = await client.disconnect()
        elif name == "network_status":
            result = await client.get_status()
            result["agent_name"] = client.agent_name
            result["connected"] = client.connected
        elif name == "network_agents":
            result = await client.get_agents()
        elif name == "network_dm":
            result = await client.send_dm(arguments["to"], arguments["message"])
        elif name == "network_inbox":
            result = await client.get_inbox(arguments.get("limit", 50))
        elif name == "network_group_create":
            result = await client.create_group(arguments["name"])
        elif name == "network_group_send":
            result = await client.send_group_message(arguments["group"], arguments["message"])
        elif name == "network_group_read":
            result = await client.get_group_messages(arguments["group"], arguments.get("limit", 50))
        elif name == "network_groups":
            result = await client.get_groups()
        elif name == "network_file_write":
            result = await client.write_file(arguments["path"], arguments["content"])
        elif name == "network_file_read":
            result = await client.read_file(arguments["path"])
        elif name == "network_file_list":
            result = await client.list_files(arguments.get("folder", ""))
        elif name == "network_file_search":
            result = await client.search_files(arguments["query"])
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    """Run the MCP server."""
    print(f"Agent Network MCP Server starting...", file=sys.stderr)
    print(f"  Network URL: {network_url}", file=sys.stderr)
    print(f"  Agent Name: {agent_name}", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

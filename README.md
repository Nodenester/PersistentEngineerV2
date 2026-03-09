# Persistent Engineer V2

> **February 2025** | Archived

An always-on AI coding agent that runs continuously inside a Docker container, receiving tasks via Redis, executing them with Claude Code, and streaming results back through a Blazor Server web UI. Unlike ephemeral one-shot containers, this agent persists across tasks with full desktop control, multiple workspaces, and an encrypted credential vault.

## Evolution

```
v1 (PersistentEngineer)  -->  v2 (this repo)  -->  v3  -->  AgentCore
     Basic daemon              Docker + Blazor       Multi-agent       Production
     Single workspace          Redis pub/sub         Agent teams       framework
                               VNC desktop
                               MCP tools
                               Credential vault
```

This is **v2** in the Persistent Engineer lineage. It introduced Docker orchestration, a Blazor Server web UI, Redis-based communication, desktop control via VNC, and custom MCP tool servers -- laying the groundwork for the multi-agent capabilities in v3 and the eventual AgentCore framework.

## Architecture

```
+---------------------+     WebSocket / Redis     +----------------------+
|   Web Platform      |<------------------------->|  Persistent Agent    |
|   (Blazor Server)   |                           |     Container        |
|                     |                           |                      |
|  - Chat UI          |                           |  - Daemon Process    |
|  - Workspace Mgmt   |                           |  - Claude Code CLI   |
|  - Credential Mgmt  |                           |  - Desktop Control   |
|  - VNC Viewer       |                           |  - MCP Tools         |
+---------------------+                           +----------------------+
         |                                                 |
         v                                                 v
+---------------------+                           +----------------------+
|  Redis              |                           |  Persistent Storage  |
|  (message queue)    |                           |  - /workspace/       |
+---------------------+                           +----------------------+
```

## Tech Stack

- **Container**: Docker (Ubuntu 24.04 + Windows Server variants)
- **Daemon**: Python 3 (asyncio, Redis pub/sub)
- **Web UI**: Blazor Server (.NET 8)
- **Message Queue**: Redis 7
- **Database**: PostgreSQL 16, SQL Server 2022 (for testing)
- **MCP Tools**: .NET 8 (AgentMemory, CodeStructureAnalyzer, GitPublisher), Python (desktop-control, agent-network)
- **Desktop**: VNC + noVNC, Openbox, Chromium
- **Credential Vault**: Fernet (AES-128-CBC) encrypted per-workspace storage
- **Autonomous Loops**: build-test-loop and project-loop plugins for multi-hour unattended operation

## Key Features

- **Persistent operation** -- runs continuously, receives tasks via Redis, never exits
- **Full desktop control** -- screenshots, mouse, keyboard, window management via VNC
- **Multiple workspaces** -- manage independent Git repositories side by side
- **Encrypted credential vault** -- per-workspace secret storage (Fernet/AES)
- **Autonomous dev loops** -- build-test-loop and project-loop for hours-long unattended coding
- **MCP tool ecosystem** -- filesystem, code analysis, git, browser automation, memory, docs lookup
- **Cross-platform** -- Linux and Windows container support

## Quick Start

```bash
# Set up (or mount ~/.claude for credential passthrough)
export ANTHROPIC_API_KEY="your-key-here"

# Start the stack
docker-compose up -d

# Access
# VNC:          http://localhost:6081
# Health check: http://localhost:8081/health
```

## Project Structure

```
PersistentEngineerV2/
├── Dockerfile.linux / .windows / .kali / .minimal
├── docker-compose.yml / .windows.yml
├── daemon-entrypoint.sh / .ps1
├── supervisor.conf
├── daemon/                  # Python daemon (main loop, workspace mgr, loops)
├── credentials/             # Encrypted credential vault
├── mcp-tools/               # MCP servers (.NET + Python)
│   ├── AgentMemory/
│   ├── CodeStructureAnalyzer/
│   ├── GitPublisher/
│   ├── desktop-control/
│   └── agent-network/
├── plugins/                 # Claude Code plugins
│   └── build-test-loop/
└── CLAUDE.md                # Agent instructions
```

## License

MIT

#!/usr/bin/env python3
"""
Persistent Engineer Agent - Daemon Process

This daemon runs continuously, listening for commands via Redis pub/sub,
managing Claude Code subprocesses, and streaming events back to the web UI.

Supports autonomous development loops (project-loop, build-test-loop) that can be:
1. Explicitly triggered by user with /project-loop or /build-test-loop commands
2. Self-triggered by the agent using <start-project-loop> or <start-build-test-loop> signals
"""

import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

import redis.asyncio as redis
import httpx

from workspace_manager import WorkspaceManager
from loop_handler import LoopHandler, LoopType
import shutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/workspace/.state/daemon.log')
    ]
)
logger = logging.getLogger('PersistentEngineer')


class PersistentEngineerDaemon:
    """Main daemon process for the Persistent Engineer Agent."""

    def __init__(self):
        self.agent_id = os.environ.get('AGENT_ID', 'default')
        self.agent_name = os.environ.get('AGENT_NAME', 'default')
        self.redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')

        # Agent Network configuration
        self.agent_network_url = os.environ.get('AGENT_NETWORK_URL', 'http://host.docker.internal:5050')
        self.agent_network_connected = False
        self.last_inbox_check = 0
        self.last_group_check = 0
        self.processed_message_ids: set = set()  # Track processed messages
        self.subscribed_groups: List[str] = []

        # Channels
        self.command_channel = f'agent:{self.agent_id}:commands'
        self.event_channel = f'agent:{self.agent_id}:events'
        self.state_channel = f'agent:{self.agent_id}:state'

        # State
        self.running = True
        self.claude_process: Optional[subprocess.Popen] = None
        self.current_task: Optional[str] = None
        self.task_queue: list = []
        self.session_id: Optional[str] = None

        # Loop handler (initialized per workspace)
        self.loop_handler: Optional[LoopHandler] = None
        self.loop_output_buffer: List[str] = []  # Buffer to collect output for signal detection

        # Credential refresh tracking
        self.credential_refresh_attempts = 0
        self.max_credential_refresh_attempts = 3
        self.last_credential_refresh = 0

        # Task retry tracking (prevents endless loops)
        self.task_retry_count = 0
        self.max_task_retries = 3
        self.task_stopped = False  # Flag to prevent retry after manual stop

        # Components
        self.workspace_manager = WorkspaceManager()
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None

        # State file
        self.state_file = Path('/workspace/.state/daemon_state.json')
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False

    async def connect_redis(self):
        """Connect to Redis server."""
        logger.info(f"Connecting to Redis at {self.redis_url}")
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe(self.command_channel)
        logger.info(f"Subscribed to channel: {self.command_channel}")

    async def connect_agent_network(self):
        """Connect to the Agent Network."""
        logger.info(f"Connecting to Agent Network at {self.agent_network_url}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.agent_network_url}/api/network/connect",
                    json={"AgentName": self.agent_name}
                )
                if response.status_code == 200:
                    self.agent_network_connected = True
                    logger.info(f"Connected to Agent Network as '{self.agent_name}'")
                    await self.publish_event('agent_network_connected', {
                        'agent_name': self.agent_name,
                        'network_url': self.agent_network_url
                    })
                else:
                    logger.warning(f"Failed to connect to Agent Network: {response.text}")
        except Exception as e:
            logger.warning(f"Could not connect to Agent Network: {e}")
            self.agent_network_connected = False

    async def poll_agent_network(self):
        """Poll Agent Network for new messages."""
        if not self.agent_network_connected:
            return

        current_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Check inbox for direct messages
                if current_time - self.last_inbox_check >= 2:  # Check every 2 seconds
                    self.last_inbox_check = current_time
                    response = await client.get(
                        f"{self.agent_network_url}/api/network/inbox",
                        params={"agentName": self.agent_name, "limit": 20}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        messages = data.get('messages', [])
                        await self._process_network_messages(messages, is_group=False)

                # Check group messages
                if current_time - self.last_group_check >= 2:
                    self.last_group_check = current_time
                    # First get list of groups
                    response = await client.get(f"{self.agent_network_url}/api/network/groups")
                    if response.status_code == 200:
                        data = response.json()
                        groups = data.get('groups', [])
                        # Check each group for new messages
                        for group in groups:
                            response = await client.get(
                                f"{self.agent_network_url}/api/network/group/read",
                                params={"group": group, "limit": 20}
                            )
                            if response.status_code == 200:
                                data = response.json()
                                messages = data.get('messages', [])
                                await self._process_network_messages(messages, is_group=True, group_name=group)
        except Exception as e:
            logger.debug(f"Agent Network poll error: {e}")

    async def _process_network_messages(self, messages: List[Dict], is_group: bool = False, group_name: str = None):
        """Process messages from Agent Network and trigger tasks."""
        for msg in messages:
            # Create unique message ID based on content and timestamp
            msg_id = f"{msg.get('From', '')}:{msg.get('Timestamp', '')}:{msg.get('Content', '')[:50]}"
            if msg_id in self.processed_message_ids:
                continue

            self.processed_message_ids.add(msg_id)

            # Skip messages from self
            if msg.get('From') == self.agent_name:
                continue

            content = msg.get('Content', '')
            sender = msg.get('From', 'unknown')

            # Log the message
            if is_group:
                logger.info(f"[Agent Network] Group '{group_name}' message from {sender}: {content[:100]}")
            else:
                logger.info(f"[Agent Network] DM from {sender}: {content[:100]}")

            # Publish event to UI
            await self.publish_event('network_message', {
                'from': sender,
                'content': content,
                'is_group': is_group,
                'group': group_name,
                'timestamp': msg.get('Timestamp')
            })

            # Check if this is a task trigger (messages directed at this agent)
            if self._should_trigger_task(content, sender, is_group, group_name):
                task_content = f"[Message from {sender}"
                if is_group:
                    task_content += f" in group '{group_name}'"
                task_content += f"]: {content}"

                # Queue as a task
                logger.info(f"Triggering task from network message: {task_content[:100]}...")
                await self.handle_task({
                    'type': 'task',
                    'parameters': {'task': task_content},
                    'source': 'agent_network'
                })

        # Trim processed message IDs to prevent memory growth
        if len(self.processed_message_ids) > 1000:
            # Keep only the last 500
            self.processed_message_ids = set(list(self.processed_message_ids)[-500:])

    def _should_trigger_task(self, content: str, sender: str, is_group: bool, group_name: str) -> bool:
        """Determine if a message should trigger a task."""
        content_lower = content.lower()

        # Direct messages always trigger tasks (unless it's just a greeting)
        if not is_group:
            # Skip simple greetings/acknowledgments
            simple_responses = ['ok', 'okay', 'thanks', 'thank you', 'hi', 'hello', 'hey', 'yes', 'no', 'sure']
            if content_lower.strip() in simple_responses:
                return False
            return True

        # Group messages: trigger if agent is mentioned or if it's a command
        agent_name_lower = self.agent_name.lower()
        if f"@{agent_name_lower}" in content_lower:
            return True
        if agent_name_lower in content_lower:
            return True

        # Check for command-like patterns
        command_patterns = [
            'please', 'can you', 'could you', 'would you', 'help',
            'create', 'build', 'fix', 'update', 'implement', 'write',
            'analyze', 'check', 'review', 'test', 'run'
        ]
        for pattern in command_patterns:
            if pattern in content_lower:
                return True

        return False

    async def send_network_response(self, message: str, to: str = None, group: str = None):
        """Send a response via Agent Network."""
        if not self.agent_network_connected:
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if group:
                    await client.post(
                        f"{self.agent_network_url}/api/network/group/send",
                        json={"From": self.agent_name, "Group": group, "Message": message}
                    )
                elif to:
                    await client.post(
                        f"{self.agent_network_url}/api/network/dm",
                        json={"From": self.agent_name, "To": to, "Message": message}
                    )
        except Exception as e:
            logger.warning(f"Failed to send network response: {e}")

    async def publish_event(self, event_type: str, data: Dict[str, Any]):
        """Publish an event to the web UI."""
        event = {
            'type': event_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'agent_id': self.agent_id,
            'data': data
        }
        await self.redis_client.publish(self.event_channel, json.dumps(event))
        logger.debug(f"Published event: {event_type}")

    async def update_state(self, state: str, details: Optional[Dict] = None):
        """Update agent state in Redis."""
        state_data = {
            'state': state,
            'workspace': str(self.workspace_manager.base_path),  # Always the projects folder
            'task': self.current_task,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': details or {}
        }

        # Add loop status if active
        if self.loop_handler and self.loop_handler.is_active():
            state_data['loop'] = self.loop_handler.get_status()

        # Store state for polling (GET)
        await self.redis_client.set(self.state_channel, json.dumps(state_data))
        # Also PUBLISH on the state channel so WebSocket subscribers get notified
        await self.redis_client.publish(self.state_channel, json.dumps(state))
        # Publish state_change event on the events channel
        await self.publish_event('state_change', state_data)
        self.save_state()

    def save_state(self):
        """Save current state to local file for persistence."""
        state = {
            'agent_id': self.agent_id,
            'current_task': self.current_task,
            'session_id': self.session_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.state_file.write_text(json.dumps(state, indent=2))

    def load_state(self):
        """Load state from local file if it exists."""
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text())
                self.current_task = state.get('current_task')
                self.session_id = state.get('session_id')
                logger.info(f"Loaded state: session={self.session_id}")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    def _get_workspace_path(self) -> Path:
        """Get the workspace path - always the projects folder where all repos live."""
        return self.workspace_manager.base_path

    def _detect_auth_error(self, output: str) -> bool:
        """Detect if output contains OAuth/authentication errors."""
        # Be specific to avoid false positives
        auth_error_patterns = [
            'OAuth token has expired',
            '"type":"authentication_error"',
            'Please run /login',
            'API Error: 401',
            'invalid_api_key',
            'Please obtain a new token',
            'refresh your existing token'
        ]
        return any(pattern.lower() in output.lower() for pattern in auth_error_patterns)

    def _detect_invalid_session(self, output: str) -> bool:
        """Detect if output contains invalid/expired session errors."""
        session_error_patterns = [
            'No conversation found with session ID',
            'session not found',
            'invalid session',
            'session has expired',
            'conversation not found'
        ]
        return any(pattern.lower() in output.lower() for pattern in session_error_patterns)

    async def _refresh_credentials(self) -> bool:
        """
        Refresh Claude Code credentials by re-copying from the mounted source.
        Returns True if refresh was successful, False otherwise.
        """
        # Rate limit refresh attempts
        current_time = time.time()
        if current_time - self.last_credential_refresh < 30:  # Min 30 seconds between refreshes
            logger.warning("Credential refresh rate limited - waiting...")
            return False

        self.credential_refresh_attempts += 1
        self.last_credential_refresh = current_time

        if self.credential_refresh_attempts > self.max_credential_refresh_attempts:
            logger.error(f"Max credential refresh attempts ({self.max_credential_refresh_attempts}) exceeded")
            await self.publish_event('credential_refresh_failed', {
                'message': 'Max refresh attempts exceeded. Manual re-login required on parent machine.',
                'attempts': self.credential_refresh_attempts
            })
            return False

        logger.info(f"Attempting credential refresh (attempt {self.credential_refresh_attempts}/{self.max_credential_refresh_attempts})...")
        await self.publish_event('credential_refresh_started', {
            'attempt': self.credential_refresh_attempts,
            'max_attempts': self.max_credential_refresh_attempts
        })

        agent_claude_dir = Path('/home/agent/.claude')
        source_dirs = [
            Path('/claude-credentials'),  # Primary mount point
            Path('/host-claude'),          # Alternative mount point
        ]

        for source_dir in source_dirs:
            if source_dir.exists() and source_dir.is_dir():
                try:
                    # Check if source has newer credentials
                    source_creds = list(source_dir.glob('*'))
                    if not source_creds:
                        logger.warning(f"Source {source_dir} is empty")
                        continue

                    # Create backup of current credentials
                    backup_dir = Path('/workspace/.state/claude_backup')
                    if agent_claude_dir.exists():
                        backup_dir.mkdir(parents=True, exist_ok=True)
                        for item in agent_claude_dir.iterdir():
                            if item.name not in ['settings.json', 'plugins']:  # Preserve container-specific config
                                dest = backup_dir / item.name
                                if item.is_dir():
                                    shutil.copytree(item, dest, dirs_exist_ok=True)
                                else:
                                    shutil.copy2(item, dest)

                    # Copy fresh credentials from source
                    for item in source_dir.iterdir():
                        dest = agent_claude_dir / item.name
                        # Skip container-specific files that shouldn't be overwritten
                        if item.name in ['settings.json']:
                            continue
                        try:
                            if item.is_dir():
                                if dest.exists():
                                    shutil.rmtree(dest)
                                shutil.copytree(item, dest)
                            else:
                                shutil.copy2(item, dest)
                            logger.debug(f"Copied {item.name} from {source_dir}")
                        except Exception as e:
                            logger.warning(f"Failed to copy {item.name}: {e}")

                    # Fix permissions
                    subprocess.run(['chown', '-R', 'agent:agent', str(agent_claude_dir)], capture_output=True)

                    logger.info(f"Credentials refreshed successfully from {source_dir}")
                    await self.publish_event('credential_refresh_success', {
                        'source': str(source_dir),
                        'attempt': self.credential_refresh_attempts
                    })

                    # Reset attempt counter on success
                    self.credential_refresh_attempts = 0
                    return True

                except Exception as e:
                    logger.error(f"Failed to refresh credentials from {source_dir}: {e}")
                    continue

        logger.error("No valid credential source found for refresh")
        await self.publish_event('credential_refresh_failed', {
            'message': 'No valid credential source found. Ensure ~/.claude is mounted.',
            'attempts': self.credential_refresh_attempts
        })
        return False

    def _init_loop_handler(self):
        """Initialize loop handler for current workspace."""
        workspace_path = self._get_workspace_path()
        self.loop_handler = LoopHandler(workspace_path)
        # Try to load existing loop state
        self.loop_handler.load_state()

    async def handle_command(self, command: Dict[str, Any]):
        """Handle a command from the web UI."""
        cmd_type = command.get('type') or command.get('Type')
        logger.info(f"Received command: {cmd_type}")

        try:
            if cmd_type == 'task':
                await self.handle_task(command)
            elif cmd_type == 'stop':
                await self.handle_stop()
            elif cmd_type == 'workspace_create':
                await self.handle_workspace_create(command)
            elif cmd_type == 'workspace_switch':
                await self.handle_workspace_switch(command)
            elif cmd_type == 'workspace_delete':
                await self.handle_workspace_delete(command)
            elif cmd_type == 'screenshot':
                await self.handle_screenshot()
            elif cmd_type == 'ping':
                await self.publish_event('pong', {'message': 'Agent is alive'})
            elif cmd_type == 'status':
                await self.handle_status()
            elif cmd_type == 'reload_system_prompt':
                await self.handle_reload_system_prompt(command)
            elif cmd_type == 'reload_mcp_config':
                await self.handle_reload_mcp_config(command)
            elif cmd_type == 'update_claude':
                await self.handle_update_claude(command)
            elif cmd_type == 'set_agent_name':
                await self.handle_set_agent_name(command)
            elif cmd_type == 'get_teams':
                await self.handle_get_teams(command)
            elif cmd_type == 'get_team_tasks':
                await self.handle_get_team_tasks(command)
            elif cmd_type == 'enable_agent_teams':
                await self.handle_enable_agent_teams(command)
            else:
                logger.warning(f"Unknown command type: {cmd_type}")
                await self.publish_event('error', {'message': f'Unknown command: {cmd_type}'})
        except Exception as e:
            logger.error(f"Error handling command {cmd_type}: {e}", exc_info=True)
            await self.publish_event('error', {'message': str(e), 'command': cmd_type})

    async def handle_task(self, command: Dict[str, Any]):
        """Handle a task command - start Claude Code with the given task."""
        params = command.get('parameters') or command.get('Parameters') or {}
        task = params.get('task', '') if params else command.get('task', '')

        logger.info(f"Task received: {task[:100]}..." if len(task) > 100 else f"Task received: {task}")

        if not task:
            await self.publish_event('error', {'message': 'No task provided'})
            return

        # Reset retry tracking for new tasks
        self.task_stopped = False
        self.task_retry_count = 0
        self.credential_refresh_attempts = 0

        if self.claude_process and self.claude_process.poll() is None:
            self.task_queue.append(task)
            await self.publish_event('task_queued', {
                'task': task,
                'position': len(self.task_queue),
                'message': f'Task queued (position {len(self.task_queue)}). Will run after current task completes.'
            })
            logger.info(f"Task queued (position {len(self.task_queue)}): {task[:50]}...")
            return

        # Initialize loop handler
        self._init_loop_handler()

        # Check for explicit loop commands (now returns 3 values including target workspaces)
        loop_type, extracted_task, target_workspaces = self.loop_handler.detect_loop_command(task)

        if loop_type:
            # User explicitly requested a loop
            logger.info(f"Detected {loop_type.value} command")
            if target_workspaces:
                logger.info(f"Target workspaces: {target_workspaces}")
            await self._start_loop(loop_type, extracted_task, target_workspaces)
        else:
            # Regular task - run normally, but watch for agent-triggered loops
            self.current_task = task
            await self.update_state('running', {'task': task})
            await self._run_claude(task)

    async def _start_loop(self, loop_type: LoopType, task: str, target_workspaces: List[str] = None):
        """Start a development loop."""
        # For cross-workspace loops, validate that all workspaces (repos) exist
        if loop_type == LoopType.CROSS_WORKSPACE_LOOP and target_workspaces:
            missing = [ws for ws in target_workspaces if not self.workspace_manager.workspace_exists(ws)]
            if missing:
                await self.publish_event('error', {
                    'message': f'Repos not found: {", ".join(missing)}. Clone them first.'
                })
                return
            logger.info(f"Cross-repo loop targeting: {target_workspaces}")

        self.current_task = task
        await self.update_state('running', {
            'task': task,
            'loop_type': loop_type.value,
            'message': f'Starting {loop_type.value}...'
        })

        await self.publish_event('loop_started', {
            'type': loop_type.value,
            'task': task,
            'target_repos': target_workspaces or [],
            'is_cross_repo': loop_type == LoopType.CROSS_WORKSPACE_LOOP
        })

        # Re-initialize loop handler for the correct workspace
        self._init_loop_handler()

        # Initialize the loop (with target workspaces for cross-workspace loops)
        self.loop_handler.initialize_loop(loop_type, task, target_workspaces=target_workspaces or [])

        # Get the first phase prompt
        prompt = self.loop_handler.get_phase_prompt()

        # Run Claude with the loop prompt
        await self._run_claude(prompt, is_loop=True)

    async def _run_claude(self, prompt: str, is_loop: bool = False):
        """Run Claude Code with a prompt."""
        workspace_path = self._get_workspace_path()

        # Inject system prompt into CLAUDE.md at the projects root level
        claude_md_path = workspace_path / 'CLAUDE.md'
        await self._inject_claude_md_content(claude_md_path, {})

        await self.publish_event('task_started', {
            'task': self.current_task,
            'is_loop': is_loop
        })

        # Build Claude command
        max_turns = os.environ.get('MAX_CODING_ITERATIONS', '500')
        mcp_config = os.environ.get('CLAUDE_MCP_CONFIG', '/opt/mcp-tools/mcp.json')
        plugins_path = os.environ.get('CLAUDE_PLUGINS_PATH', '/opt/plugins')

        cmd = [
            'claude',
            '--dangerously-skip-permissions',
            '--allowedTools', 'all',
            '--output-format', 'stream-json',
            '--verbose',
            '--max-turns', max_turns,
            '--mcp-config', mcp_config,
            '--plugin-dir', plugins_path,
        ]

        # Resume session if we have one (but not for new loop phases)
        if self.session_id and not is_loop:
            cmd.extend(['--resume', self.session_id])
            logger.info(f"Resuming session: {self.session_id}")

        cmd.extend(['-p', prompt])

        logger.info(f"Starting Claude Code: {' '.join(cmd[:10])}...")

        # Build environment
        env = os.environ.copy()
        env['CLAUDE_PLUGINS_PATH'] = plugins_path
        env['DISPLAY'] = os.environ.get('DISPLAY', ':0')
        env['HOME'] = '/home/agent'

        # Clear output buffer for loop signal detection
        self.loop_output_buffer = []

        # Start the process
        self.claude_process = subprocess.Popen(
            cmd,
            cwd=str(workspace_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )

        # Stream output asynchronously
        await self._stream_claude_output(is_loop)

    async def _stream_claude_output(self, is_loop: bool = False):
        """Stream Claude Code output to the web UI."""
        if not self.claude_process:
            return

        full_output = []

        try:
            while True:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, self.claude_process.stdout.readline
                )

                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                # Collect output for signal detection
                full_output.append(line)

                # Try to parse as JSON
                try:
                    event = json.loads(line)

                    # Debug: log event types for troubleshooting
                    event_type = event.get('type', 'unknown')
                    if event_type not in ['content_block_delta', 'ping']:  # Skip noisy events
                        logger.debug(f"JSON event type: {event_type}")

                    # Capture session ID
                    if 'session_id' in event:
                        self.session_id = event['session_id']
                        logger.info(f"Captured session ID: {self.session_id}")
                    elif event.get('type') == 'system' and 'session_id' in event.get('data', {}):
                        self.session_id = event['data']['session_id']
                        logger.info(f"Captured session ID from system event: {self.session_id}")

                    # Extract text content for signal detection from various JSON formats
                    # Format 1: {"type": "assistant", "content": [{"type": "text", "text": "..."}]}
                    if event.get('type') == 'assistant' and 'content' in event:
                        for block in event.get('content', []):
                            if block.get('type') == 'text':
                                self.loop_output_buffer.append(block.get('text', ''))

                    # Format 2: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "..."}}
                    if event.get('type') == 'content_block_delta':
                        delta = event.get('delta', {})
                        if delta.get('type') == 'text_delta' and 'text' in delta:
                            self.loop_output_buffer.append(delta['text'])

                    # Format 3: {"type": "text", "text": "..."} - direct text block
                    if event.get('type') == 'text' and 'text' in event:
                        self.loop_output_buffer.append(event['text'])

                    # Format 4: {"message": "..."} or {"content": "..."} - simple message
                    if 'message' in event and isinstance(event['message'], str):
                        self.loop_output_buffer.append(event['message'])
                    if 'content' in event and isinstance(event['content'], str):
                        self.loop_output_buffer.append(event['content'])

                    await self.publish_event('claude_output', event)
                    await self.redis_client.publish(f'agent:{self.agent_id}:cli_output', line)
                except json.JSONDecodeError:
                    self.loop_output_buffer.append(line)
                    await self.publish_event('claude_output', {'text': line})
                    await self.redis_client.publish(f'agent:{self.agent_id}:cli_output', line)

            # Process completed
            return_code = self.claude_process.wait()
            logger.info(f"Claude Code exited with code {return_code}")

            # Combine output for signal detection - use BOTH full_output and loop_output_buffer
            # full_output captures all raw lines (guaranteed to have everything)
            # loop_output_buffer captures parsed text (may be incomplete depending on JSON format)
            combined_output = '\n'.join(full_output)

            # Also add loop_output_buffer content if it has different parsed text
            if self.loop_output_buffer:
                combined_output += '\n' + '\n'.join(self.loop_output_buffer)

            # Check if task was manually stopped - don't retry
            if self.task_stopped:
                logger.info("Task was stopped by user - not retrying")
                self.current_task = None
                self.claude_process = None
                await self.update_state('idle')
                return

            # Check retry limit to prevent endless loops
            if self.task_retry_count >= self.max_task_retries:
                logger.error(f"Max task retries ({self.max_task_retries}) exceeded - stopping")
                await self.publish_event('task_failed', {
                    'message': f'Task failed after {self.max_task_retries} retries',
                    'task': self.current_task
                })
                self.current_task = None
                self.claude_process = None
                self.task_retry_count = 0
                await self.update_state('idle')
                return

            # Check for invalid session errors (session not found after container restart)
            if self._detect_invalid_session(combined_output):
                self.task_retry_count += 1
                logger.warning(f"Invalid session detected - clearing and retrying (attempt {self.task_retry_count}/{self.max_task_retries})...")
                await self.publish_event('session_invalid', {
                    'message': 'Session not found. Starting fresh session...',
                    'old_session': self.session_id,
                    'retry_attempt': self.task_retry_count
                })

                # Clear the invalid session and retry
                self.session_id = None
                self.claude_process = None
                self.save_state()

                # Small delay before retry
                await asyncio.sleep(1)

                # Retry without session resume
                if is_loop and self.loop_handler:
                    retry_prompt = self.loop_handler.get_phase_prompt()
                    await self._run_claude(retry_prompt, is_loop=True)
                else:
                    await self._run_claude(self.current_task, is_loop=False)
                return

            # Check for authentication errors (401, token expired, etc.)
            if self._detect_auth_error(combined_output):
                self.task_retry_count += 1
                logger.warning(f"Authentication error detected (attempt {self.task_retry_count}/{self.max_task_retries})!")
                await self.publish_event('auth_error_detected', {
                    'message': 'OAuth token expired. Attempting to refresh credentials...',
                    'retry_attempt': self.task_retry_count
                })

                # Try to refresh credentials
                refresh_success = await self._refresh_credentials()

                if refresh_success:
                    # Clear session (it's invalid now) and retry the task
                    self.session_id = None
                    self.claude_process = None

                    logger.info("Credentials refreshed, retrying task...")
                    await self.publish_event('task_retry', {
                        'task': self.current_task,
                        'reason': 'Credentials refreshed after OAuth expiration',
                        'retry_attempt': self.task_retry_count
                    })

                    # Small delay before retry
                    await asyncio.sleep(2)

                    # Retry with the same prompt
                    if is_loop and self.loop_handler:
                        retry_prompt = self.loop_handler.get_phase_prompt()
                        await self._run_claude(retry_prompt, is_loop=True)
                    else:
                        await self._run_claude(self.current_task, is_loop=False)
                    return
                else:
                    # Refresh failed - notify user
                    await self.publish_event('auth_error_fatal', {
                        'message': 'Failed to refresh credentials. Please run /login on the parent machine and restart the container.',
                        'task': self.current_task
                    })
                    self.current_task = None
                    self.claude_process = None
                    await self.update_state('auth_error')
                    return

            # Check for agent-triggered loops (only if not already in a loop)
            if not is_loop and self.loop_handler:
                trigger_type, trigger_task = self.loop_handler.detect_agent_trigger(combined_output)
                if trigger_type and trigger_task:
                    logger.info(f"Agent triggered {trigger_type.value}: {trigger_task[:50]}...")
                    await self.publish_event('agent_triggered_loop', {
                        'type': trigger_type.value,
                        'task': trigger_task
                    })
                    # Start the loop
                    self.claude_process = None
                    await self._start_loop(trigger_type, trigger_task)
                    return

            # Handle loop continuation
            if is_loop and self.loop_handler and self.loop_handler.is_active():
                signals = self.loop_handler.detect_signals(combined_output)

                # Log output summary for debugging
                output_length = len(combined_output)
                logger.info(f"Loop output total length: {output_length} chars, full_output lines: {len(full_output)}, buffer items: {len(self.loop_output_buffer)}")

                # Look for promise tags specifically
                import re
                promise_matches = re.findall(r'<promise>[^<]+</promise>', combined_output)
                logger.info(f"Found promise tags in output: {promise_matches}")

                output_preview = combined_output[-1000:] if len(combined_output) > 1000 else combined_output
                logger.info(f"Loop output preview (last 1000 chars): {output_preview}")
                logger.info(f"Looking for signals in output, found: {signals}")

                if signals:
                    logger.info(f"Detected loop signals: {signals}")
                    await self.publish_event('loop_signals', {'signals': signals})

                    # If ANALYZE_COMPLETE, extract stages from output
                    if 'ANALYZE_COMPLETE' in signals:
                        stages_json = self._extract_stages_json(combined_output)
                        if stages_json:
                            self.loop_handler.update_stages(stages_json)
                            logger.info(f"Extracted stages: {self.loop_handler.state.stages}")
                            await self.publish_event('stages_defined', {
                                'stages': self.loop_handler.state.stages,
                                'build_command': self.loop_handler.state.build_command,
                                'test_url': self.loop_handler.state.test_url
                            })

                    # If MORE_WORK_NEEDED during REANALYZE, extract new stages
                    if 'MORE_WORK_NEEDED' in signals:
                        stages_json = self._extract_stages_json(combined_output)
                        if stages_json:
                            self.loop_handler.update_stages(stages_json)
                            logger.info(f"Re-analyze found more work. New stages: {self.loop_handler.state.stages}")
                            await self.publish_event('stages_added', {
                                'stages': self.loop_handler.state.stages,
                                'reason': 'Re-analysis found additional work needed'
                            })

                    # Process signals and get next action
                    should_continue, next_prompt = self.loop_handler.process_signals(signals)

                    if should_continue:
                        logger.info(f"Loop continuing - phase: {self.loop_handler.state.phase.value}")

                        # For cross-repo loops, track which repo is the focus (but agent has access to all)
                        current_repo = None
                        if self.loop_handler.state.is_cross_workspace:
                            current_repo = self.loop_handler.get_current_stage_workspace()
                            if current_repo:
                                logger.info(f"Loop focusing on repo: {current_repo}")

                        await self.publish_event('loop_phase', {
                            'phase': self.loop_handler.state.phase.value,
                            'iteration': self.loop_handler.state.iteration,
                            'stage': self.loop_handler.state.current_stage,
                            'current_repo': current_repo
                        })
                        # Clear session to start fresh phase
                        self.session_id = None
                        self.claude_process = None
                        # Small delay between loop iterations
                        await asyncio.sleep(2)
                        await self._run_claude(next_prompt, is_loop=True)
                        return
                    else:
                        logger.info("Loop completed!")
                        await self.publish_event('loop_completed', {
                            'type': self.loop_handler.state.loop_type.value,
                            'task': self.loop_handler.state.original_prompt,
                            'iterations': self.loop_handler.state.iteration
                        })
                else:
                    # No signals detected - Claude may have exited without completing the phase
                    logger.warning(f"No signals detected in loop output. Phase: {self.loop_handler.state.phase.value}")
                    logger.warning("Claude may not have output the required signal. Retrying phase...")

                    # Increment iteration to prevent infinite loops
                    self.loop_handler.state.iteration += 1
                    if self.loop_handler.state.iteration < 3:  # Max 3 retries per phase
                        await self.publish_event('loop_retry', {
                            'phase': self.loop_handler.state.phase.value,
                            'iteration': self.loop_handler.state.iteration,
                            'reason': 'No completion signal detected'
                        })
                        # Clear session and retry the same phase
                        self.session_id = None
                        self.claude_process = None
                        await asyncio.sleep(2)
                        retry_prompt = self.loop_handler.get_phase_prompt()
                        retry_prompt += "\n\n**IMPORTANT:** You must output the completion signal when done!"
                        await self._run_claude(retry_prompt, is_loop=True)
                        return
                    else:
                        logger.error(f"Max retries reached for phase {self.loop_handler.state.phase.value}")
                        await self.publish_event('loop_error', {
                            'phase': self.loop_handler.state.phase.value,
                            'error': 'Max retries reached - no completion signal received'
                        })

            # Task/loop completed
            await self.publish_event('task_completed', {
                'task': self.current_task,
                'return_code': return_code,
                'success': return_code == 0
            })

            self.current_task = None
            self.claude_process = None

            # Check for queued tasks
            if self.task_queue:
                next_task = self.task_queue.pop(0)
                remaining = len(self.task_queue)
                logger.info(f"Processing queued task ({remaining} remaining): {next_task[:50]}...")
                await self.publish_event('task_dequeued', {
                    'task': next_task,
                    'remaining': remaining
                })
                await self.handle_task({'type': 'task', 'parameters': {'task': next_task}})
            else:
                await self.update_state('idle')

        except Exception as e:
            logger.error(f"Error streaming Claude output: {e}", exc_info=True)
            await self.publish_event('error', {'message': f'Stream error: {e}'})
            self.claude_process = None
            if self.task_queue:
                next_task = self.task_queue.pop(0)
                await self.handle_task({'type': 'task', 'parameters': {'task': next_task}})

    def _extract_stages_json(self, output: str) -> Optional[str]:
        """Extract stages JSON from Claude's ANALYZE output."""
        # First, try to extract text content from JSON API responses
        # The output might contain JSON lines like {"type": "result", "message": "..."}
        extracted_text = output

        # Try to extract message/text content from JSON lines
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                # Extract text from various JSON formats
                if isinstance(obj, dict):
                    for key in ['message', 'text', 'content']:
                        if key in obj and isinstance(obj[key], str):
                            extracted_text += '\n' + obj[key]
                    # Also check nested content array
                    if 'content' in obj and isinstance(obj['content'], list):
                        for item in obj['content']:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                extracted_text += '\n' + item.get('text', '')
            except (json.JSONDecodeError, TypeError):
                pass

        # Now search for stages JSON in the extracted text
        # Pattern: ```json followed by JSON content followed by ```
        json_pattern = r'```json\s*(\{[\s\S]*?"stages"[\s\S]*?\})\s*```'
        match = re.search(json_pattern, extracted_text)
        if match:
            logger.info(f"Found stages JSON in code block")
            return match.group(1)

        # Try to find raw JSON with stages array
        raw_pattern = r'(\{\s*"stages"\s*:\s*\[[\s\S]*?\]\s*(?:,\s*"[^"]+"\s*:\s*"[^"]*"\s*)*\})'
        match = re.search(raw_pattern, extracted_text)
        if match:
            logger.info(f"Found stages JSON in raw text")
            return match.group(1)

        # Try escaped JSON (for when it's inside a JSON string)
        escaped_pattern = r'"stages"\s*:\s*\[(.*?)\]'
        match = re.search(escaped_pattern, extracted_text, re.DOTALL)
        if match:
            # Try to reconstruct the JSON
            stages_content = match.group(1)
            try:
                # Unescape and parse
                reconstructed = '{"stages": [' + stages_content + ']}'
                json.loads(reconstructed)  # Validate
                logger.info(f"Found stages JSON from escaped content")
                return reconstructed
            except json.JSONDecodeError:
                pass

        logger.warning("Could not extract stages JSON from ANALYZE output")
        logger.debug(f"Searched in text (last 500 chars): {extracted_text[-500:]}")
        return None

    async def _inject_claude_md_content(self, claude_md_path: Path, credentials: Dict[str, str]):
        """Inject system prompt, credentials, and project CLAUDE.md files into root CLAUDE.md."""
        # Get system prompt from Redis
        system_prompt = await self.get_system_prompt()

        # Read existing content or create default
        if claude_md_path.exists():
            content = claude_md_path.read_text()
            # Strip out any previous auto-injected sections
            if '## Agent Instructions (Auto-injected)' in content:
                parts = content.split('## Agent Instructions (Auto-injected)')
                content = parts[0].rstrip()
            if '## Credentials (Auto-injected)' in content:
                parts = content.split('## Credentials (Auto-injected)')
                content = parts[0].rstrip()
            if '## Project Instructions (Auto-injected from repos)' in content:
                parts = content.split('## Project Instructions (Auto-injected from repos)')
                content = parts[0].rstrip()
        else:
            content = "# Project Instructions\n"

        injected_content = ""

        # Add system prompt section if present
        if system_prompt:
            injected_content += "\n\n## Agent Instructions (Auto-injected)\n\n"
            injected_content += system_prompt
            injected_content += "\n"
            logger.info(f"Injected system prompt ({len(system_prompt)} chars) into CLAUDE.md")

        # Add credentials section if present
        if credentials:
            injected_content += "\n\n## Credentials (Auto-injected)\n\n"
            injected_content += "The following credentials are available for this workspace:\n\n"
            for name, value in credentials.items():
                masked = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
                injected_content += f"- **{name}**: `{masked}` (use env var `{name}`)\n"

        # Collect CLAUDE.md files from all cloned repos
        project_instructions = self._collect_project_claude_md_files()
        if project_instructions:
            injected_content += "\n\n## Project Instructions (Auto-injected from repos)\n\n"
            injected_content += "The following instructions were found in the cloned repositories:\n\n"
            for repo_name, repo_content in project_instructions.items():
                injected_content += f"### {repo_name}/CLAUDE.md\n\n"
                injected_content += repo_content
                injected_content += "\n\n---\n\n"
            logger.info(f"Injected CLAUDE.md from {len(project_instructions)} repos into root CLAUDE.md")

        # Write the updated content
        claude_md_path.write_text(content + injected_content)

    def _collect_project_claude_md_files(self) -> Dict[str, str]:
        """Collect CLAUDE.md content from all cloned repos."""
        project_instructions = {}

        for workspace in self.workspace_manager.list_workspaces():
            workspace_path = Path(workspace['path'])
            claude_md = workspace_path / 'CLAUDE.md'

            if claude_md.exists():
                try:
                    content = claude_md.read_text()
                    # Skip if it's mostly empty or just a placeholder
                    if content.strip() and len(content.strip()) > 50:
                        project_instructions[workspace['name']] = content
                        logger.debug(f"Found CLAUDE.md in {workspace['name']} ({len(content)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to read CLAUDE.md from {workspace['name']}: {e}")

        return project_instructions

    def _inject_credentials(self, claude_md_path: Path, credentials: Dict[str, str]):
        """Legacy sync wrapper - use _inject_claude_md_content instead."""
        # This is kept for backwards compatibility but won't inject system prompt
        if not credentials:
            return

        cred_section = "\n\n## Credentials (Auto-injected)\n\n"
        cred_section += "The following credentials are available for this workspace:\n\n"
        for name, value in credentials.items():
            masked = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
            cred_section += f"- **{name}**: `{masked}` (use env var `{name}`)\n"

        if claude_md_path.exists():
            content = claude_md_path.read_text()
            if '## Credentials (Auto-injected)' in content:
                parts = content.split('## Credentials (Auto-injected)')
                content = parts[0].rstrip()
        else:
            content = "# Project Instructions\n"

        claude_md_path.write_text(content + cred_section)

    async def handle_reload_mcp_config(self, command):
        """Reload MCP configuration from web UI."""
        try:
            config = command.get('parameters', {}).get('config_json', {})
            mcp_config_path = os.path.join(os.path.expanduser('~'), '.claude', 'mcp.json')
            os.makedirs(os.path.dirname(mcp_config_path), exist_ok=True)
            with open(mcp_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            await self.publish_event('mcp_config_reloaded', {'status': 'success'})
            logger.info("MCP config reloaded successfully")
        except Exception as e:
            await self.publish_event('mcp_config_reload_failed', {'error': str(e)})
            logger.error(f"Failed to reload MCP config: {e}")

    async def handle_update_claude(self, command):
        """Update Claude Code to latest version."""
        try:
            await self.publish_event('claude_update_started', {})
            proc = await asyncio.create_subprocess_exec(
                'npm', 'update', '-g', '@anthropic-ai/claude-code',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            # Get new version
            version_proc = await asyncio.create_subprocess_exec(
                'claude', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            version_out, _ = await version_proc.communicate()
            new_version = version_out.decode().strip() if version_out else 'unknown'

            if proc.returncode == 0:
                await self.publish_event('claude_updated', {
                    'version': new_version,
                    'output': stdout.decode()
                })
                logger.info(f"Claude Code updated to {new_version}")
            else:
                await self.publish_event('claude_update_failed', {
                    'error': stderr.decode(),
                    'returncode': proc.returncode
                })
                logger.error(f"Claude Code update failed: {stderr.decode()}")
        except Exception as e:
            await self.publish_event('claude_update_failed', {'error': str(e)})
            logger.error(f"Failed to update Claude Code: {e}")

    async def handle_set_agent_name(self, command):
        """Set the agent's display name."""
        try:
            name = command.get('parameters', {}).get('name', '')
            if name:
                await self.redis_client.hset(f'agent:{self.agent_id}:state', 'name', name)
                await self.publish_event('agent_name_set', {'name': name})
                logger.info(f"Agent name set to: {name}")
        except Exception as e:
            logger.error(f"Failed to set agent name: {e}")

    async def handle_get_teams(self, command):
        """List active Claude Code agent teams."""
        try:
            teams_dir = os.path.expanduser('~/.claude/teams')
            teams = []
            if os.path.exists(teams_dir):
                for team_name in os.listdir(teams_dir):
                    config_path = os.path.join(teams_dir, team_name, 'config.json')
                    if os.path.isfile(config_path):
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                        teams.append({
                            'name': team_name,
                            'config': config,
                            'members': config.get('members', [])
                        })
            await self.publish_event('teams_list', {'teams': teams})
        except Exception as e:
            await self.publish_event('teams_list_error', {'error': str(e)})
            logger.error(f"Failed to list teams: {e}")

    async def handle_get_team_tasks(self, command):
        """Get tasks for a specific agent team."""
        try:
            team_name = command.get('parameters', {}).get('team_name', '')
            tasks_dir = os.path.expanduser(f'~/.claude/tasks/{team_name}')
            tasks = []
            if os.path.exists(tasks_dir):
                for filename in os.listdir(tasks_dir):
                    if filename.endswith('.json'):
                        filepath = os.path.join(tasks_dir, filename)
                        with open(filepath, 'r') as f:
                            task_data = json.load(f)
                        tasks.append(task_data)
            await self.publish_event('team_tasks', {
                'team_name': team_name,
                'tasks': tasks
            })
        except Exception as e:
            await self.publish_event('team_tasks_error', {'error': str(e)})
            logger.error(f"Failed to get team tasks: {e}")

    async def handle_enable_agent_teams(self, command):
        """Enable or disable Claude Code Agent Teams feature."""
        try:
            enabled = command.get('parameters', {}).get('enabled', True)
            settings_path = os.path.expanduser('~/.claude/settings.json')

            settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)

            settings.setdefault('env', {})
            settings['env']['CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'] = '1' if enabled else '0'

            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

            # Also ensure directories exist
            if enabled:
                os.makedirs(os.path.expanduser('~/.claude/teams'), exist_ok=True)
                os.makedirs(os.path.expanduser('~/.claude/tasks'), exist_ok=True)

            await self.publish_event('agent_teams_toggled', {
                'enabled': enabled,
                'status': 'success'
            })
            logger.info(f"Agent Teams {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            await self.publish_event('agent_teams_toggle_failed', {'error': str(e)})
            logger.error(f"Failed to toggle agent teams: {e}")

    async def handle_stop(self):
        """Stop the currently running Claude process."""
        logger.info("Stop command received!")

        # Set flag to prevent retry loops
        self.task_stopped = True

        # Also stop any active loop
        if self.loop_handler and self.loop_handler.is_active():
            self.loop_handler.state.enabled = False
            logger.info("Loop stopped by user")

        if self.claude_process and self.claude_process.poll() is None:
            logger.info("Stopping Claude Code process...")
            self.claude_process.terminate()
            try:
                self.claude_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Process didn't terminate, killing...")
                self.claude_process.kill()

            await self.publish_event('task_stopped', {'task': self.current_task})
            self.current_task = None
            self.task_retry_count = 0  # Reset retry counter
            self.credential_refresh_attempts = 0  # Reset credential counter
            await self.update_state('idle')
            logger.info("Task stopped successfully")
        else:
            await self.publish_event('info', {'message': 'No task is running'})

    def _get_param(self, command: Dict[str, Any], key: str, default: str = '') -> str:
        """Extract parameter from command."""
        params = command.get('parameters') or command.get('Parameters') or {}
        return params.get(key, command.get(key, default))

    async def handle_workspace_create(self, command: Dict[str, Any]):
        """Clone a Git repository into the projects folder."""
        repo_url = self._get_param(command, 'repo_url')
        workspace_name = self._get_param(command, 'name')
        branch = self._get_param(command, 'branch', 'main')
        github_token = self._get_param(command, 'github_token')

        if not repo_url or not workspace_name:
            await self.publish_event('error', {'message': 'repo_url and name are required'})
            return

        await self.update_state('cloning_repo', {'name': workspace_name})

        try:
            workspace_path = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.workspace_manager.create_workspace(workspace_name, repo_url, branch, github_token)
            )

            await self.publish_event('workspace_created', {
                'name': workspace_name,
                'path': str(workspace_path),
                'repo_url': repo_url,
                'branch': branch,
                'message': f'Repo cloned to projects/{workspace_name}/. Agent has access to all repos.'
            })

            await self.update_state('idle')

        except Exception as e:
            await self.publish_event('error', {'message': f'Failed to clone repo: {e}'})
            await self.update_state('idle')

    async def handle_workspace_switch(self, command: Dict[str, Any]):
        """Legacy command - workspaces are now all accessible from the projects folder."""
        workspace_name = self._get_param(command, 'name')

        if not workspace_name:
            await self.publish_event('error', {'message': 'Workspace name is required'})
            return

        if not self.workspace_manager.workspace_exists(workspace_name):
            await self.publish_event('error', {'message': f'Workspace not found: {workspace_name}'})
            return

        # Just acknowledge - agent can access all workspaces from the projects folder
        await self.publish_event('info', {
            'message': f'Workspace "{workspace_name}" is available at projects/{workspace_name}/. Agent has access to all workspaces.'
        })

    async def handle_workspace_delete(self, command: Dict[str, Any]):
        """Delete a workspace (repo folder)."""
        workspace_name = self._get_param(command, 'name')

        if not workspace_name:
            await self.publish_event('error', {'message': 'Workspace name is required'})
            return

        if self.claude_process and self.claude_process.poll() is None:
            await self.publish_event('error', {'message': 'Cannot delete workspace while task is running'})
            return

        try:
            self.workspace_manager.delete_workspace(workspace_name)
            await self.publish_event('workspace_deleted', {'name': workspace_name})
        except Exception as e:
            await self.publish_event('error', {'message': f'Failed to delete workspace: {e}'})

    async def handle_screenshot(self):
        """Capture a screenshot of the desktop."""
        try:
            screenshot_path = f'/tmp/screenshot_{int(time.time())}.png'

            result = subprocess.run(
                ['scrot', screenshot_path],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                import base64
                with open(screenshot_path, 'rb') as f:
                    screenshot_data = base64.b64encode(f.read()).decode('utf-8')

                await self.publish_event('screenshot', {
                    'data': screenshot_data,
                    'format': 'png'
                })

                os.remove(screenshot_path)
            else:
                await self.publish_event('error', {'message': f'Screenshot failed: {result.stderr}'})

        except Exception as e:
            await self.publish_event('error', {'message': f'Screenshot error: {e}'})

    async def handle_status(self):
        """Send current agent status."""
        status = {
            'agent_id': self.agent_id,
            'state': 'running' if self.claude_process and self.claude_process.poll() is None else 'idle',
            'current_task': self.current_task,
            'projects_path': str(self.workspace_manager.base_path),
            'repos': self.workspace_manager.list_workspaces()
        }

        if self.loop_handler and self.loop_handler.is_active():
            status['loop'] = self.loop_handler.get_status()

        await self.publish_event('status', status)

    async def handle_reload_system_prompt(self, command: Dict[str, Any]):
        """Handle system prompt reload command."""
        system_prompt = self._get_param(command, 'system_prompt')
        logger.info(f"Received system prompt update for agent {self.agent_id}")

        # Store locally for reference
        self._cached_system_prompt = system_prompt if system_prompt else None

        await self.publish_event('system_prompt_updated', {
            'has_prompt': bool(system_prompt),
            'preview': system_prompt[:100] + '...' if system_prompt and len(system_prompt) > 100 else system_prompt
        })

    async def get_system_prompt(self) -> Optional[str]:
        """Get the system prompt for this agent from Redis."""
        if not self.redis_client:
            return None

        try:
            key = f'agent:{self.agent_id}:system_prompt'
            value = await self.redis_client.get(key)
            return value if value else None
        except Exception as e:
            logger.warning(f"Failed to get system prompt from Redis: {e}")
            return None

    async def run(self):
        """Main daemon loop."""
        logger.info(f"Starting Persistent Engineer Daemon (agent_id={self.agent_id}, agent_name={self.agent_name})")

        self.load_state()
        await self.connect_redis()

        # Connect to Agent Network
        await self.connect_agent_network()

        await self.update_state('idle')
        await self.publish_event('daemon_started', {
            'agent_id': self.agent_id,
            'agent_name': self.agent_name,
            'agent_network_connected': self.agent_network_connected,
            'workspaces': self.workspace_manager.list_workspaces()
        })

        logger.info("Daemon is ready and listening for commands...")

        while self.running:
            try:
                # Check Redis for commands
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=0.5  # Reduced timeout for faster Agent Network polling
                )

                if message and message.get('type') == 'message':
                    try:
                        command = json.loads(message['data'])
                        await self.handle_command(command)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in message: {message['data']}")

                # Poll Agent Network for messages (only if not busy with a task)
                if not self.claude_process or self.claude_process.poll() is not None:
                    await self.poll_agent_network()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("Shutting down daemon...")
        await self.handle_stop()
        self.save_state()

        # Disconnect from Agent Network
        if self.agent_network_connected:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{self.agent_network_url}/api/network/disconnect",
                        json={"AgentName": self.agent_name}
                    )
            except:
                pass

        await self.publish_event('daemon_stopped', {'agent_id': self.agent_id})
        await self.pubsub.unsubscribe(self.command_channel)
        await self.redis_client.close()

        logger.info("Daemon shutdown complete")


async def main():
    """Entry point."""
    daemon = PersistentEngineerDaemon()
    await daemon.run()


if __name__ == '__main__':
    asyncio.run(main())

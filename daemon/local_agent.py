#!/usr/bin/env python3
"""
Local Agent Daemon - Lightweight daemon for running agents on the host machine.

This is a stripped-down version of the PersistentEngineerDaemon that:
- Runs Claude Code directly on the host (no container, no Xvfb/VNC/Openbox)
- Uses the same Redis protocol as container agents
- Can be started/stopped as a simple Python process
- Takes agent_id and redis_url as arguments

Usage:
    python local_agent.py --agent-id my-local-agent --redis-url redis://localhost:6381
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

import redis.asyncio as redis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('LocalAgent')


class LocalAgentDaemon:
    """Lightweight daemon for running Claude Code agents on the host."""

    def __init__(self, agent_id: str, redis_url: str, workspace_dir: Optional[str] = None):
        self.agent_id = agent_id
        self.redis_url = redis_url
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()

        # Channels (same protocol as container agents)
        self.command_channel = f'agent:{self.agent_id}:commands'
        self.event_channel = f'agent:{self.agent_id}:events'
        self.state_channel = f'agent:{self.agent_id}:state'

        # State
        self.running = True
        self.claude_process: Optional[subprocess.Popen] = None
        self.current_task: Optional[str] = None
        self.task_queue: list = []
        self.session_id: Optional[str] = None

        # Redis
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None

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
            'workspace': str(self.workspace_dir),
            'task': self.current_task,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': details or {},
            'mode': 'local'
        }
        await self.redis_client.set(self.state_channel, json.dumps(state_data))
        await self.publish_event('state_change', state_data)

    async def handle_command(self, command: Dict[str, Any]):
        """Handle a command from the web UI."""
        cmd_type = command.get('type') or command.get('Type')
        logger.info(f"Received command: {cmd_type}")

        try:
            if cmd_type == 'task':
                await self.handle_task(command)
            elif cmd_type == 'stop':
                await self.handle_stop()
            elif cmd_type == 'ping':
                await self.publish_event('pong', {'message': 'Local agent is alive'})
            elif cmd_type == 'status':
                await self.handle_status()
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

        if self.claude_process and self.claude_process.poll() is None:
            self.task_queue.append(task)
            await self.publish_event('task_queued', {
                'task': task,
                'position': len(self.task_queue),
                'message': f'Task queued (position {len(self.task_queue)}).'
            })
            return

        self.current_task = task
        await self.update_state('running', {'task': task})
        await self._run_claude(task)

    async def _run_claude(self, prompt: str):
        """Run Claude Code with a prompt on the host."""
        await self.publish_event('task_started', {'task': self.current_task})

        cmd = [
            'claude',
            '--dangerously-skip-permissions',
            '--output-format', 'stream-json',
            '--verbose',
            '--max-turns', '500',
        ]

        if self.session_id:
            cmd.extend(['--resume', self.session_id])

        cmd.extend(['-p', prompt])

        logger.info(f"Starting Claude Code in {self.workspace_dir}")

        env = os.environ.copy()

        self.claude_process = subprocess.Popen(
            cmd,
            cwd=str(self.workspace_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )

        await self._stream_claude_output()

    async def _stream_claude_output(self):
        """Stream Claude Code output to Redis."""
        if not self.claude_process:
            return

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

                try:
                    event = json.loads(line)

                    # Capture session ID
                    if 'session_id' in event:
                        self.session_id = event['session_id']
                    elif event.get('type') == 'system' and 'session_id' in event.get('data', {}):
                        self.session_id = event['data']['session_id']

                    await self.publish_event('claude_output', event)
                    await self.redis_client.publish(f'agent:{self.agent_id}:cli_output', line)
                except json.JSONDecodeError:
                    await self.publish_event('claude_output', {'text': line})
                    await self.redis_client.publish(f'agent:{self.agent_id}:cli_output', line)

            return_code = self.claude_process.wait()
            logger.info(f"Claude Code exited with code {return_code}")

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
                await self.handle_task({'type': 'task', 'parameters': {'task': next_task}})
            else:
                await self.update_state('idle')

        except Exception as e:
            logger.error(f"Error streaming Claude output: {e}", exc_info=True)
            await self.publish_event('error', {'message': f'Stream error: {e}'})
            self.claude_process = None
            await self.update_state('idle')

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

        if self.claude_process and self.claude_process.poll() is None:
            logger.info("Stopping Claude Code process...")
            self.claude_process.terminate()
            try:
                self.claude_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.claude_process.kill()

            await self.publish_event('task_stopped', {'task': self.current_task})
            self.current_task = None
            await self.update_state('idle')
        else:
            await self.publish_event('info', {'message': 'No task is running'})

    async def handle_status(self):
        """Send current agent status."""
        status = {
            'agent_id': self.agent_id,
            'state': 'running' if self.claude_process and self.claude_process.poll() is None else 'idle',
            'current_task': self.current_task,
            'workspace': str(self.workspace_dir),
            'mode': 'local'
        }
        await self.publish_event('status', status)

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

    async def run(self):
        """Main daemon loop."""
        logger.info(f"Starting Local Agent Daemon (agent_id={self.agent_id})")
        logger.info(f"Workspace: {self.workspace_dir}")

        await self.connect_redis()
        await self.update_state('idle')
        await self.publish_event('daemon_started', {
            'agent_id': self.agent_id,
            'mode': 'local',
            'workspace': str(self.workspace_dir)
        })

        logger.info("Local agent daemon is ready and listening for commands...")

        while self.running:
            try:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=0.5
                )

                if message and message.get('type') == 'message':
                    try:
                        command = json.loads(message['data'])
                        await self.handle_command(command)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in message: {message['data']}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("Shutting down local agent daemon...")
        await self.handle_stop()
        await self.publish_event('daemon_stopped', {'agent_id': self.agent_id})
        await self.pubsub.unsubscribe(self.command_channel)
        await self.redis_client.close()
        logger.info("Local agent daemon shutdown complete")


async def main():
    parser = argparse.ArgumentParser(description='Local Agent Daemon')
    parser.add_argument('--agent-id', required=True, help='Unique agent identifier')
    parser.add_argument('--redis-url', default='redis://localhost:6381', help='Redis URL')
    parser.add_argument('--workspace', default=None, help='Working directory for Claude Code')
    args = parser.parse_args()

    daemon = LocalAgentDaemon(
        agent_id=args.agent_id,
        redis_url=args.redis_url,
        workspace_dir=args.workspace
    )
    await daemon.run()


if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python3
"""
Desktop Control MCP Server for Linux

Provides full OS desktop control capabilities including:
- Screen capture (full desktop or region)
- Mouse control (move, click, drag)
- Keyboard input (type text, press keys)
- Window management (list, focus, move, resize)
- Clipboard access (read, write)
- Command execution

Uses Linux tools: xdotool, scrot, xclip, wmctrl, xwininfo
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

# MCP protocol imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        Tool,
        TextContent,
        ImageContent,
        CallToolResult,
    )
except ImportError:
    print("MCP library not found. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)


# Initialize MCP server
server = Server("desktop-control")


def run_command(cmd: List[str], capture_output: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(
        cmd,
        capture_output=capture_output,
        text=True,
        env={**os.environ, 'DISPLAY': os.environ.get('DISPLAY', ':0')}
    )


def get_screen_size() -> tuple:
    """Get the screen dimensions."""
    result = run_command(['xdotool', 'getdisplaygeometry'])
    if result.returncode == 0:
        parts = result.stdout.strip().split()
        return int(parts[0]), int(parts[1])
    return 1920, 1080  # Default fallback


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available desktop control tools."""
    return [
        Tool(
            name="screen_capture",
            description="Capture a screenshot of the full desktop or a specific region",
            inputSchema={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Optional region to capture (x, y, width, height)",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"}
                        }
                    },
                    "window_id": {
                        "type": "string",
                        "description": "Optional window ID to capture"
                    }
                }
            }
        ),
        Tool(
            name="mouse_move",
            description="Move the mouse cursor to specified coordinates",
            inputSchema={
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                    "relative": {"type": "boolean", "description": "If true, move relative to current position"}
                },
                "required": ["x", "y"]
            }
        ),
        Tool(
            name="mouse_click",
            description="Click the mouse button at current position or specified coordinates",
            inputSchema={
                "type": "object",
                "properties": {
                    "button": {
                        "type": "string",
                        "enum": ["left", "middle", "right"],
                        "default": "left"
                    },
                    "x": {"type": "integer", "description": "Optional X coordinate"},
                    "y": {"type": "integer", "description": "Optional Y coordinate"},
                    "double_click": {"type": "boolean", "default": False}
                }
            }
        ),
        Tool(
            name="mouse_drag",
            description="Drag the mouse from one position to another",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_x": {"type": "integer"},
                    "start_y": {"type": "integer"},
                    "end_x": {"type": "integer"},
                    "end_y": {"type": "integer"},
                    "button": {"type": "string", "enum": ["left", "middle", "right"], "default": "left"}
                },
                "required": ["start_x", "start_y", "end_x", "end_y"]
            }
        ),
        Tool(
            name="keyboard_type",
            description="Type text using the keyboard",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                    "delay": {"type": "integer", "description": "Delay between keystrokes in ms", "default": 12}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="keyboard_key",
            description="Press a specific key or key combination",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key to press (e.g., 'Return', 'Tab', 'ctrl+c', 'alt+F4')"
                    }
                },
                "required": ["key"]
            }
        ),
        Tool(
            name="window_list",
            description="List all open windows",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="window_focus",
            description="Focus a window by ID or name",
            inputSchema={
                "type": "object",
                "properties": {
                    "window_id": {"type": "string", "description": "Window ID to focus"},
                    "name": {"type": "string", "description": "Window name (partial match)"}
                }
            }
        ),
        Tool(
            name="window_move",
            description="Move a window to specified position",
            inputSchema={
                "type": "object",
                "properties": {
                    "window_id": {"type": "string"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                },
                "required": ["window_id", "x", "y"]
            }
        ),
        Tool(
            name="window_resize",
            description="Resize a window",
            inputSchema={
                "type": "object",
                "properties": {
                    "window_id": {"type": "string"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"}
                },
                "required": ["window_id", "width", "height"]
            }
        ),
        Tool(
            name="window_close",
            description="Close a window",
            inputSchema={
                "type": "object",
                "properties": {
                    "window_id": {"type": "string"}
                },
                "required": ["window_id"]
            }
        ),
        Tool(
            name="clipboard_read",
            description="Read the current clipboard contents",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="clipboard_write",
            description="Write text to the clipboard",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="run_command",
            description="Run a shell command",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"},
                    "working_dir": {"type": "string", "description": "Working directory"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="get_mouse_position",
            description="Get the current mouse cursor position",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_active_window",
            description="Get information about the currently active window",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="scroll",
            description="Scroll the mouse wheel",
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                    "amount": {"type": "integer", "default": 3}
                },
                "required": ["direction"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls."""
    try:
        if name == "screen_capture":
            return await screen_capture(arguments)
        elif name == "mouse_move":
            return await mouse_move(arguments)
        elif name == "mouse_click":
            return await mouse_click(arguments)
        elif name == "mouse_drag":
            return await mouse_drag(arguments)
        elif name == "keyboard_type":
            return await keyboard_type(arguments)
        elif name == "keyboard_key":
            return await keyboard_key(arguments)
        elif name == "window_list":
            return await window_list(arguments)
        elif name == "window_focus":
            return await window_focus(arguments)
        elif name == "window_move":
            return await window_move(arguments)
        elif name == "window_resize":
            return await window_resize(arguments)
        elif name == "window_close":
            return await window_close(arguments)
        elif name == "clipboard_read":
            return await clipboard_read(arguments)
        elif name == "clipboard_write":
            return await clipboard_write(arguments)
        elif name == "run_command":
            return await run_shell_command(arguments)
        elif name == "get_mouse_position":
            return await get_mouse_position(arguments)
        elif name == "get_active_window":
            return await get_active_window(arguments)
        elif name == "scroll":
            return await scroll(arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True
            )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {str(e)}")],
            isError=True
        )


async def screen_capture(args: Dict[str, Any]) -> CallToolResult:
    """Capture a screenshot."""
    # Check prerequisites
    display = os.environ.get('DISPLAY', ':0')

    # Check if scrot is available
    scrot_check = subprocess.run(['which', 'scrot'], capture_output=True, text=True)
    if scrot_check.returncode != 0:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: scrot is not installed. Install with: apt-get install scrot")],
            isError=True
        )

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        screenshot_path = f.name

    try:
        cmd = ['scrot', screenshot_path]

        region = args.get('region')
        window_id = args.get('window_id')

        if region:
            # Capture specific region
            x, y = region.get('x', 0), region.get('y', 0)
            w, h = region.get('width', 100), region.get('height', 100)
            cmd = ['scrot', '-a', f'{x},{y},{w},{h}', screenshot_path]
        elif window_id:
            # Capture specific window
            cmd = ['scrot', '-u', screenshot_path]
            # Focus window first
            run_command(['xdotool', 'windowactivate', window_id])
            time.sleep(0.2)

        result = run_command(cmd)

        if result.returncode != 0:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Screenshot command failed (DISPLAY={display}): {result.stderr or result.stdout or 'Unknown error'}")],
                isError=True
            )

        if not os.path.exists(screenshot_path):
            return CallToolResult(
                content=[TextContent(type="text", text=f"Screenshot file not created at {screenshot_path}")],
                isError=True
            )

        file_size = os.path.getsize(screenshot_path)
        if file_size == 0:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Screenshot file is empty (0 bytes). DISPLAY={display}")],
                isError=True
            )

        with open(screenshot_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        if not image_data:
            return CallToolResult(
                content=[TextContent(type="text", text="Screenshot captured but base64 encoding failed")],
                isError=True
            )

        return CallToolResult(
            content=[
                ImageContent(
                    type="image",
                    data=image_data,
                    mimeType="image/png"
                ),
                TextContent(type="text", text=f"Screenshot captured successfully ({file_size} bytes)")
            ]
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Screenshot exception: {str(e)}")],
            isError=True
        )
    finally:
        if os.path.exists(screenshot_path):
            os.unlink(screenshot_path)


async def mouse_move(args: Dict[str, Any]) -> CallToolResult:
    """Move the mouse cursor."""
    x, y = args['x'], args['y']
    relative = args.get('relative', False)

    if relative:
        result = run_command(['xdotool', 'mousemove_relative', '--', str(x), str(y)])
    else:
        result = run_command(['xdotool', 'mousemove', str(x), str(y)])

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Mouse moved to ({x}, {y})")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to move mouse: {result.stderr}")],
            isError=True
        )


async def mouse_click(args: Dict[str, Any]) -> CallToolResult:
    """Click the mouse button."""
    button_map = {'left': '1', 'middle': '2', 'right': '3'}
    button = button_map.get(args.get('button', 'left'), '1')
    double_click = args.get('double_click', False)

    # Move to position if specified
    x, y = args.get('x'), args.get('y')
    if x is not None and y is not None:
        run_command(['xdotool', 'mousemove', str(x), str(y)])

    # Click
    cmd = ['xdotool', 'click']
    if double_click:
        cmd.extend(['--repeat', '2', '--delay', '50'])
    cmd.append(button)

    result = run_command(cmd)

    if result.returncode == 0:
        click_type = "Double-clicked" if double_click else "Clicked"
        pos = f" at ({x}, {y})" if x is not None else ""
        return CallToolResult(
            content=[TextContent(type="text", text=f"{click_type} {args.get('button', 'left')} button{pos}")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Click failed: {result.stderr}")],
            isError=True
        )


async def mouse_drag(args: Dict[str, Any]) -> CallToolResult:
    """Drag the mouse from one position to another."""
    start_x, start_y = args['start_x'], args['start_y']
    end_x, end_y = args['end_x'], args['end_y']

    # Move to start, hold button, move to end, release
    run_command(['xdotool', 'mousemove', str(start_x), str(start_y)])
    run_command(['xdotool', 'mousedown', '1'])
    run_command(['xdotool', 'mousemove', str(end_x), str(end_y)])
    result = run_command(['xdotool', 'mouseup', '1'])

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Drag failed: {result.stderr}")],
            isError=True
        )


async def keyboard_type(args: Dict[str, Any]) -> CallToolResult:
    """Type text using the keyboard."""
    text = args['text']
    delay = args.get('delay', 12)

    result = run_command(['xdotool', 'type', '--delay', str(delay), text])

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Typed {len(text)} characters")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Type failed: {result.stderr}")],
            isError=True
        )


async def keyboard_key(args: Dict[str, Any]) -> CallToolResult:
    """Press a specific key or key combination."""
    key = args['key']

    result = run_command(['xdotool', 'key', key])

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Pressed key: {key}")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Key press failed: {result.stderr}")],
            isError=True
        )


async def window_list(args: Dict[str, Any]) -> CallToolResult:
    """List all open windows."""
    result = run_command(['wmctrl', '-l'])

    if result.returncode == 0:
        windows = []
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split(None, 3)
                if len(parts) >= 4:
                    windows.append({
                        'id': parts[0],
                        'desktop': parts[1],
                        'host': parts[2],
                        'title': parts[3]
                    })
                elif len(parts) >= 1:
                    windows.append({'id': parts[0], 'title': 'Unknown'})

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(windows, indent=2))]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to list windows: {result.stderr}")],
            isError=True
        )


async def window_focus(args: Dict[str, Any]) -> CallToolResult:
    """Focus a window by ID or name."""
    window_id = args.get('window_id')
    name = args.get('name')

    if window_id:
        result = run_command(['xdotool', 'windowactivate', window_id])
    elif name:
        result = run_command(['xdotool', 'search', '--name', name, 'windowactivate'])
    else:
        return CallToolResult(
            content=[TextContent(type="text", text="Must provide window_id or name")],
            isError=True
        )

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Focused window: {window_id or name}")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to focus window: {result.stderr}")],
            isError=True
        )


async def window_move(args: Dict[str, Any]) -> CallToolResult:
    """Move a window to specified position."""
    window_id = args['window_id']
    x, y = args['x'], args['y']

    result = run_command(['xdotool', 'windowmove', window_id, str(x), str(y)])

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Moved window {window_id} to ({x}, {y})")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to move window: {result.stderr}")],
            isError=True
        )


async def window_resize(args: Dict[str, Any]) -> CallToolResult:
    """Resize a window."""
    window_id = args['window_id']
    width, height = args['width'], args['height']

    result = run_command(['xdotool', 'windowsize', window_id, str(width), str(height)])

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Resized window {window_id} to {width}x{height}")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to resize window: {result.stderr}")],
            isError=True
        )


async def window_close(args: Dict[str, Any]) -> CallToolResult:
    """Close a window."""
    window_id = args['window_id']

    result = run_command(['xdotool', 'windowclose', window_id])

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Closed window {window_id}")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to close window: {result.stderr}")],
            isError=True
        )


async def clipboard_read(args: Dict[str, Any]) -> CallToolResult:
    """Read clipboard contents."""
    result = run_command(['xclip', '-selection', 'clipboard', '-o'])

    if result.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=result.stdout)]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to read clipboard: {result.stderr}")],
            isError=True
        )


async def clipboard_write(args: Dict[str, Any]) -> CallToolResult:
    """Write text to clipboard."""
    text = args['text']

    # Use echo and pipe to xclip
    process = subprocess.Popen(
        ['xclip', '-selection', 'clipboard'],
        stdin=subprocess.PIPE,
        env={**os.environ, 'DISPLAY': os.environ.get('DISPLAY', ':0')}
    )
    process.communicate(input=text.encode())

    if process.returncode == 0:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Copied {len(text)} characters to clipboard")]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text="Failed to write to clipboard")],
            isError=True
        )


async def run_shell_command(args: Dict[str, Any]) -> CallToolResult:
    """Run a shell command."""
    command = args['command']
    working_dir = args.get('working_dir')
    timeout = args.get('timeout', 30)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=working_dir,
            timeout=timeout,
            env={**os.environ, 'DISPLAY': os.environ.get('DISPLAY', ':0')}
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"

        return CallToolResult(
            content=[TextContent(type="text", text=output or "(no output)")],
            isError=result.returncode != 0
        )
    except subprocess.TimeoutExpired:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Command timed out after {timeout}s")],
            isError=True
        )


async def get_mouse_position(args: Dict[str, Any]) -> CallToolResult:
    """Get current mouse position."""
    result = run_command(['xdotool', 'getmouselocation'])

    if result.returncode == 0:
        # Parse: x:123 y:456 screen:0 window:123456
        parts = result.stdout.strip().split()
        pos = {}
        for part in parts:
            if ':' in part:
                key, value = part.split(':')
                pos[key] = int(value)

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(pos))]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to get mouse position: {result.stderr}")],
            isError=True
        )


async def get_active_window(args: Dict[str, Any]) -> CallToolResult:
    """Get information about the active window."""
    # Get active window ID
    result = run_command(['xdotool', 'getactivewindow'])

    if result.returncode == 0:
        window_id = result.stdout.strip()

        # Get window info
        info_result = run_command(['xdotool', 'getwindowname', window_id])
        title = info_result.stdout.strip() if info_result.returncode == 0 else 'Unknown'

        geom_result = run_command(['xdotool', 'getwindowgeometry', window_id])
        geometry = geom_result.stdout.strip() if geom_result.returncode == 0 else ''

        info = {
            'id': window_id,
            'title': title,
            'geometry': geometry
        }

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(info, indent=2))]
        )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to get active window: {result.stderr}")],
            isError=True
        )


async def scroll(args: Dict[str, Any]) -> CallToolResult:
    """Scroll the mouse wheel."""
    direction = args['direction']
    amount = args.get('amount', 3)

    # xdotool click: 4=up, 5=down, 6=left, 7=right
    button_map = {'up': '4', 'down': '5', 'left': '6', 'right': '7'}
    button = button_map.get(direction, '5')

    for _ in range(amount):
        run_command(['xdotool', 'click', button])

    return CallToolResult(
        content=[TextContent(type="text", text=f"Scrolled {direction} {amount} times")]
    )


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

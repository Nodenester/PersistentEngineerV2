#!/usr/bin/env python3
"""
Desktop Control MCP Server for Windows

Provides full OS desktop control capabilities including:
- Screen capture (full desktop or region)
- Mouse control (move, click, drag)
- Keyboard input (type text, press keys)
- Window management (list, focus, move, resize)
- Clipboard access (read, write)
- Command execution

Uses Windows tools: pyautogui, pywin32, pillow
"""

import asyncio
import base64
import ctypes
import io
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

# Windows-specific imports
try:
    import pyautogui
    import win32gui
    import win32con
    import win32clipboard
    import win32process
    from PIL import ImageGrab
    pyautogui.FAILSAFE = False
except ImportError:
    print("Required packages not found. Install with: pip install pyautogui pywin32 pillow", file=sys.stderr)
    sys.exit(1)

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
server = Server("desktop-control-windows")


def get_screen_size() -> tuple:
    """Get the screen dimensions."""
    return pyautogui.size()


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
                    "window_handle": {
                        "type": "integer",
                        "description": "Optional window handle to capture"
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
                    "relative": {"type": "boolean", "description": "If true, move relative to current position"},
                    "duration": {"type": "number", "description": "Duration of movement in seconds", "default": 0}
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
                    "button": {"type": "string", "enum": ["left", "middle", "right"], "default": "left"},
                    "duration": {"type": "number", "description": "Duration of drag in seconds", "default": 0.5}
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
                    "interval": {"type": "number", "description": "Interval between keystrokes in seconds", "default": 0.01}
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
                        "description": "Key to press (e.g., 'enter', 'tab', 'ctrl+c', 'alt+f4')"
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
            description="Focus a window by handle or title",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "integer", "description": "Window handle to focus"},
                    "title": {"type": "string", "description": "Window title (partial match)"}
                }
            }
        ),
        Tool(
            name="window_move",
            description="Move a window to specified position",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "integer"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"}
                },
                "required": ["handle", "x", "y"]
            }
        ),
        Tool(
            name="window_resize",
            description="Resize a window",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"}
                },
                "required": ["handle", "width", "height"]
            }
        ),
        Tool(
            name="window_close",
            description="Close a window",
            inputSchema={
                "type": "object",
                "properties": {
                    "handle": {"type": "integer"}
                },
                "required": ["handle"]
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
            description="Run a shell command (PowerShell)",
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
    try:
        region = args.get('region')
        window_handle = args.get('window_handle')

        if region:
            x, y = region.get('x', 0), region.get('y', 0)
            w, h = region.get('width', 100), region.get('height', 100)
            screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        elif window_handle:
            # Get window rectangle and capture
            try:
                rect = win32gui.GetWindowRect(window_handle)
                screenshot = ImageGrab.grab(bbox=rect)
            except Exception as e:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Failed to capture window: {e}")],
                    isError=True
                )
        else:
            screenshot = ImageGrab.grab()

        # Convert to base64
        buffer = io.BytesIO()
        screenshot.save(buffer, format='PNG')
        image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return CallToolResult(
            content=[
                ImageContent(
                    type="image",
                    data=image_data,
                    mimeType="image/png"
                ),
                TextContent(type="text", text="Screenshot captured successfully")
            ]
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Screenshot failed: {e}")],
            isError=True
        )


async def mouse_move(args: Dict[str, Any]) -> CallToolResult:
    """Move the mouse cursor."""
    x, y = args['x'], args['y']
    relative = args.get('relative', False)
    duration = args.get('duration', 0)

    if relative:
        pyautogui.move(x, y, duration=duration)
    else:
        pyautogui.moveTo(x, y, duration=duration)

    return CallToolResult(
        content=[TextContent(type="text", text=f"Mouse moved to ({x}, {y})")]
    )


async def mouse_click(args: Dict[str, Any]) -> CallToolResult:
    """Click the mouse button."""
    button = args.get('button', 'left')
    x, y = args.get('x'), args.get('y')
    double_click = args.get('double_click', False)

    clicks = 2 if double_click else 1

    if x is not None and y is not None:
        pyautogui.click(x, y, button=button, clicks=clicks)
    else:
        pyautogui.click(button=button, clicks=clicks)

    click_type = "Double-clicked" if double_click else "Clicked"
    pos = f" at ({x}, {y})" if x is not None else ""
    return CallToolResult(
        content=[TextContent(type="text", text=f"{click_type} {button} button{pos}")]
    )


async def mouse_drag(args: Dict[str, Any]) -> CallToolResult:
    """Drag the mouse from one position to another."""
    start_x, start_y = args['start_x'], args['start_y']
    end_x, end_y = args['end_x'], args['end_y']
    button = args.get('button', 'left')
    duration = args.get('duration', 0.5)

    pyautogui.moveTo(start_x, start_y)
    pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)

    return CallToolResult(
        content=[TextContent(type="text", text=f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")]
    )


async def keyboard_type(args: Dict[str, Any]) -> CallToolResult:
    """Type text using the keyboard."""
    text = args['text']
    interval = args.get('interval', 0.01)

    pyautogui.typewrite(text, interval=interval)

    return CallToolResult(
        content=[TextContent(type="text", text=f"Typed {len(text)} characters")]
    )


async def keyboard_key(args: Dict[str, Any]) -> CallToolResult:
    """Press a specific key or key combination."""
    key = args['key']

    # Handle key combinations like ctrl+c
    if '+' in key:
        pyautogui.hotkey(*key.split('+'))
    else:
        pyautogui.press(key)

    return CallToolResult(
        content=[TextContent(type="text", text=f"Pressed key: {key}")]
    )


def enum_windows_callback(hwnd, windows):
    """Callback for EnumWindows to collect window info."""
    if win32gui.IsWindowVisible(hwnd):
        title = win32gui.GetWindowText(hwnd)
        if title:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                rect = win32gui.GetWindowRect(hwnd)
                windows.append({
                    'handle': hwnd,
                    'title': title,
                    'pid': pid,
                    'rect': {
                        'x': rect[0],
                        'y': rect[1],
                        'width': rect[2] - rect[0],
                        'height': rect[3] - rect[1]
                    }
                })
            except:
                pass


async def window_list(args: Dict[str, Any]) -> CallToolResult:
    """List all open windows."""
    windows = []
    win32gui.EnumWindows(enum_windows_callback, windows)

    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(windows, indent=2))]
    )


async def window_focus(args: Dict[str, Any]) -> CallToolResult:
    """Focus a window by handle or title."""
    handle = args.get('handle')
    title = args.get('title')

    if handle:
        try:
            win32gui.SetForegroundWindow(handle)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Focused window handle: {handle}")]
            )
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to focus window: {e}")],
                isError=True
            )
    elif title:
        # Find window by title
        def find_window(hwnd, target_title):
            if target_title.lower() in win32gui.GetWindowText(hwnd).lower():
                return hwnd
            return None

        found_hwnd = None
        def callback(hwnd, _):
            nonlocal found_hwnd
            if title.lower() in win32gui.GetWindowText(hwnd).lower():
                found_hwnd = hwnd
                return False  # Stop enumeration
            return True

        win32gui.EnumWindows(callback, None)

        if found_hwnd:
            win32gui.SetForegroundWindow(found_hwnd)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Focused window: {title}")]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Window not found: {title}")],
                isError=True
            )
    else:
        return CallToolResult(
            content=[TextContent(type="text", text="Must provide handle or title")],
            isError=True
        )


async def window_move(args: Dict[str, Any]) -> CallToolResult:
    """Move a window to specified position."""
    handle = args['handle']
    x, y = args['x'], args['y']

    try:
        rect = win32gui.GetWindowRect(handle)
        width = rect[2] - rect[0]
        height = rect[3] - rect[1]
        win32gui.MoveWindow(handle, x, y, width, height, True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Moved window to ({x}, {y})")]
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to move window: {e}")],
            isError=True
        )


async def window_resize(args: Dict[str, Any]) -> CallToolResult:
    """Resize a window."""
    handle = args['handle']
    width, height = args['width'], args['height']

    try:
        rect = win32gui.GetWindowRect(handle)
        x, y = rect[0], rect[1]
        win32gui.MoveWindow(handle, x, y, width, height, True)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Resized window to {width}x{height}")]
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to resize window: {e}")],
            isError=True
        )


async def window_close(args: Dict[str, Any]) -> CallToolResult:
    """Close a window."""
    handle = args['handle']

    try:
        win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
        return CallToolResult(
            content=[TextContent(type="text", text=f"Closed window {handle}")]
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to close window: {e}")],
            isError=True
        )


async def clipboard_read(args: Dict[str, Any]) -> CallToolResult:
    """Read clipboard contents."""
    try:
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return CallToolResult(
                content=[TextContent(type="text", text=data)]
            )
        except:
            return CallToolResult(
                content=[TextContent(type="text", text="(clipboard is empty or contains non-text data)")]
            )
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to read clipboard: {e}")],
            isError=True
        )


async def clipboard_write(args: Dict[str, Any]) -> CallToolResult:
    """Write text to clipboard."""
    text = args['text']

    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return CallToolResult(
            content=[TextContent(type="text", text=f"Copied {len(text)} characters to clipboard")]
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to write to clipboard: {e}")],
            isError=True
        )


async def run_shell_command(args: Dict[str, Any]) -> CallToolResult:
    """Run a PowerShell command."""
    command = args['command']
    working_dir = args.get('working_dir')
    timeout = args.get('timeout', 30)

    try:
        result = subprocess.run(
            ['powershell', '-Command', command],
            capture_output=True,
            text=True,
            cwd=working_dir,
            timeout=timeout
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
    x, y = pyautogui.position()
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps({'x': x, 'y': y}))]
    )


async def get_active_window(args: Dict[str, Any]) -> CallToolResult:
    """Get information about the active window."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        rect = win32gui.GetWindowRect(hwnd)

        info = {
            'handle': hwnd,
            'title': title,
            'rect': {
                'x': rect[0],
                'y': rect[1],
                'width': rect[2] - rect[0],
                'height': rect[3] - rect[1]
            }
        }

        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(info, indent=2))]
        )
    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Failed to get active window: {e}")],
            isError=True
        )


async def scroll(args: Dict[str, Any]) -> CallToolResult:
    """Scroll the mouse wheel."""
    direction = args['direction']
    amount = args.get('amount', 3)

    if direction == 'up':
        pyautogui.scroll(amount)
    elif direction == 'down':
        pyautogui.scroll(-amount)
    elif direction == 'left':
        pyautogui.hscroll(-amount)
    elif direction == 'right':
        pyautogui.hscroll(amount)

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

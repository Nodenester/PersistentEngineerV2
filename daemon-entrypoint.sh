#!/bin/bash
# =============================================================================
# Persistent Engineer Agent - Linux Daemon Entrypoint
# =============================================================================
# Starts all required services:
# - Xvfb (virtual display)
# - X11VNC (VNC server)
# - noVNC (web VNC)
# - Openbox (window manager)
# - Daemon process (Python)
# =============================================================================

set -e

echo "=========================================="
echo "Persistent Engineer Agent - Starting..."
echo "=========================================="

# -----------------------------------------------------------------------------
# Environment validation
# -----------------------------------------------------------------------------

echo "[INFO] Validating environment..."

# Required environment variables
if [ -z "$AGENT_ID" ]; then
    export AGENT_ID="default"
    echo "[INFO] AGENT_ID not set, using: $AGENT_ID"
fi

if [ -z "$REDIS_URL" ]; then
    export REDIS_URL="redis://redis:6379"
    echo "[INFO] REDIS_URL not set, using: $REDIS_URL"
fi

# Set display
export DISPLAY=:0

# -----------------------------------------------------------------------------
# Auto-update Claude Code
# -----------------------------------------------------------------------------

echo "[entrypoint] Checking for Claude Code updates..."
npm update -g @anthropic-ai/claude-code 2>&1 | tail -3 || true

# -----------------------------------------------------------------------------
# Create required directories
# -----------------------------------------------------------------------------

echo "[INFO] Creating directories..."

mkdir -p /workspace/projects
mkdir -p /workspace/.state
mkdir -p /workspace/.creds
mkdir -p /workspace/.agent-memory
mkdir -p /tmp/.X11-unix
mkdir -p /var/log/supervisor
mkdir -p /var/run

# Set permissions
chown -R agent:agent /workspace || true
chmod 1777 /tmp/.X11-unix

# -----------------------------------------------------------------------------
# Apply ad-blocking hosts
# -----------------------------------------------------------------------------

echo "[INFO] Applying ad-blocking hosts..."
if [ -f /opt/adblock-hosts.txt ]; then
    cat /opt/adblock-hosts.txt >> /etc/hosts 2>/dev/null || true
    echo "[INFO] Ad-blocking hosts applied ($(wc -l < /opt/adblock-hosts.txt) entries)"
fi

# -----------------------------------------------------------------------------
# Pre-configure Chrome to skip first-run dialogs
# -----------------------------------------------------------------------------

echo "[INFO] Configuring Chrome to skip first-run..."

# Create Chrome config directory for agent user
CHROME_CONFIG_DIR=/home/agent/.config/google-chrome
mkdir -p "$CHROME_CONFIG_DIR/Default"

# Create "First Run" sentinel file - tells Chrome to skip welcome dialog
touch "$CHROME_CONFIG_DIR/First Run"

# Create preferences with telemetry disabled
cat > "$CHROME_CONFIG_DIR/Default/Preferences" << 'CHROMEPREFS'
{
    "browser": {
        "has_seen_welcome_page": true,
        "check_default_browser": false
    },
    "default_search_provider_data": {
        "template_url_data": {
            "keyword": "google.com"
        }
    },
    "distribution": {
        "skip_first_run_ui": true,
        "make_chrome_default": false,
        "make_chrome_default_for_user": false,
        "suppress_first_run_default_browser_prompt": true
    },
    "first_run_tabs": [],
    "profile": {
        "default_content_setting_values": {},
        "exited_cleanly": true
    },
    "privacy": {
        "send_spelling_feedback_enabled": false
    },
    "safebrowsing": {
        "enabled": true,
        "scout_reporting_enabled": false
    },
    "sync": {
        "has_setup_completed": false
    },
    "signin": {
        "allowed": false
    }
}
CHROMEPREFS

# Set ownership
chown -R agent:agent "$CHROME_CONFIG_DIR"

echo "[INFO] Chrome configured to skip first-run dialogs"

# -----------------------------------------------------------------------------
# Start Xvfb (Virtual Display)
# -----------------------------------------------------------------------------

echo "[INFO] Starting Xvfb virtual display..."

# Kill any existing Xvfb and clean up lock files
pkill Xvfb || true
rm -f /tmp/.X0-lock /tmp/.X11-unix/X0 2>/dev/null || true
sleep 1

# Get resolution
VNC_RESOLUTION=${VNC_RESOLUTION:-1920x1080x24}

# Start Xvfb
Xvfb :0 -screen 0 $VNC_RESOLUTION -ac +extension GLX +render -noreset &
XVFB_PID=$!

# Wait for Xvfb to start
sleep 2

if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "[ERROR] Failed to start Xvfb"
    exit 1
fi

echo "[INFO] Xvfb started (PID: $XVFB_PID)"

# -----------------------------------------------------------------------------
# Start Openbox (Window Manager)
# -----------------------------------------------------------------------------

echo "[INFO] Starting Openbox window manager..."

openbox &
OPENBOX_PID=$!
sleep 1

echo "[INFO] Openbox started (PID: $OPENBOX_PID)"

# -----------------------------------------------------------------------------
# Start X11VNC (VNC Server)
# -----------------------------------------------------------------------------

echo "[INFO] Starting X11VNC server..."

# Create VNC password file
mkdir -p /home/agent/.vnc
x11vnc -storepasswd "${VNC_PASSWORD:-agentpwd}" /home/agent/.vnc/passwd

# Start X11VNC
x11vnc -display :0 \
    -rfbport 5900 \
    -rfbauth /home/agent/.vnc/passwd \
    -forever \
    -shared \
    -noxdamage \
    -bg \
    -o /var/log/x11vnc.log

echo "[INFO] X11VNC started on port 5900"

# -----------------------------------------------------------------------------
# Start noVNC (Web VNC)
# -----------------------------------------------------------------------------

echo "[INFO] Starting noVNC web server..."

# Start websockify with noVNC
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
NOVNC_PID=$!

echo "[INFO] noVNC started on port 6080 (PID: $NOVNC_PID)"

# -----------------------------------------------------------------------------
# Wait for Redis
# -----------------------------------------------------------------------------

echo "[INFO] Waiting for Redis..."

# Extract host and port from REDIS_URL
REDIS_HOST=$(echo $REDIS_URL | sed -e 's|redis://||' -e 's|:.*||')
REDIS_PORT=$(echo $REDIS_URL | sed -e 's|.*:||' -e 's|/.*||')
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

# Wait for Redis to be ready
MAX_RETRIES=30
RETRY_COUNT=0

while ! redis-cli -h $REDIS_HOST -p $REDIS_PORT ping > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "[ERROR] Redis not available after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "[INFO] Waiting for Redis... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 1
done

echo "[INFO] Redis is ready"

# -----------------------------------------------------------------------------
# Configure Claude Code
# -----------------------------------------------------------------------------

echo "[INFO] Configuring Claude Code..."

# Copy credentials from mounted read-only location to writable ~/.claude (same as CoderAgentz)
AGENT_CLAUDE_DIR=/home/agent/.claude
mkdir -p $AGENT_CLAUDE_DIR

if [ -d "/claude-credentials" ]; then
    echo "[INFO] Copying Claude credentials to ~/.claude..."
    # Copy all files except settings.json (which we'll create with container-specific config)
    for item in /claude-credentials/*; do
        if [ -e "$item" ]; then
            basename=$(basename "$item")
            if [ "$basename" != "settings.json" ]; then
                cp -r "$item" "$AGENT_CLAUDE_DIR/" 2>/dev/null || true
            fi
        fi
    done
    # Copy hidden files
    for item in /claude-credentials/.*; do
        if [ -e "$item" ]; then
            basename=$(basename "$item")
            if [ "$basename" != "." ] && [ "$basename" != ".." ]; then
                cp -r "$item" "$AGENT_CLAUDE_DIR/" 2>/dev/null || true
            fi
        fi
    done
    chown -R agent:agent $AGENT_CLAUDE_DIR
    echo "[INFO] Claude credentials copied successfully"

    # Log credential status for debugging
    if [ -f "$AGENT_CLAUDE_DIR/credentials.json" ]; then
        echo "[INFO] Found credentials.json"
    elif [ -f "$AGENT_CLAUDE_DIR/.credentials.json" ]; then
        echo "[INFO] Found .credentials.json"
    else
        echo "[WARN] No credentials.json found in ~/.claude"
    fi
else
    echo "[WARN] No Claude credentials mounted at /claude-credentials"
    echo "[WARN] Claude Code will require /login or ANTHROPIC_API_KEY"
fi

# Create local Claude config directory for MCP tools
LOCAL_CLAUDE_DIR=/opt/claude-local
mkdir -p $LOCAL_CLAUDE_DIR/plugins

# Copy MCP config to local directory
cp /opt/mcp-tools/mcp.json $LOCAL_CLAUDE_DIR/mcp.json

# Link plugins directory for Claude Code to find /build-test-loop and /project-loop
# These plugins allow long-running autonomous loops (3+ hours)
if [ -d "/opt/plugins" ]; then
    echo "[INFO] Setting up Claude Code plugins..."
    for plugin in /opt/plugins/*; do
        if [ -d "$plugin" ]; then
            plugin_name=$(basename "$plugin")
            ln -sf "$plugin" "$LOCAL_CLAUDE_DIR/plugins/$plugin_name"
            echo "[INFO] Linked plugin: $plugin_name"
        fi
    done
fi

# Create proper settings.json with Linux container paths and enabled plugins
# This overrides Windows settings from the mounted host directory
cat > "$AGENT_CLAUDE_DIR/settings.json" << 'SETTINGSJSON'
{
  "enabledPlugins": {
    "build-test-loop@local-plugins": true
  },
  "extraKnownMarketplaces": {
    "local-plugins": {
      "source": {
        "source": "directory",
        "path": "/opt/plugins"
      }
    }
  }
}
SETTINGSJSON
echo "[INFO] Created settings.json with enabled plugins and local marketplace"

# Create proper installed_plugins.json with Linux container paths
PLUGINS_JSON_DIR="$AGENT_CLAUDE_DIR/plugins"
mkdir -p "$PLUGINS_JSON_DIR"
cat > "$PLUGINS_JSON_DIR/installed_plugins.json" << 'PLUGINSJSON'
{
  "version": 2,
  "plugins": {
    "build-test-loop@local-plugins": [
      {
        "scope": "user",
        "installPath": "/opt/plugins/build-test-loop",
        "version": "1.6.0",
        "installedAt": "2026-01-01T00:00:00.000Z",
        "lastUpdated": "2026-01-21T00:00:00.000Z"
      }
    ]
  }
}
PLUGINSJSON
echo "[INFO] Created installed_plugins.json with container paths"

# Export the MCP config location for daemon to use
export CLAUDE_MCP_CONFIG=$LOCAL_CLAUDE_DIR/mcp.json
export CLAUDE_PLUGINS_DIR=$LOCAL_CLAUDE_DIR/plugins
export CLAUDE_PLUGINS_PATH=/opt/plugins

# Set ownership
chown -R agent:agent $LOCAL_CLAUDE_DIR

# Accept Claude terms (non-interactive)
su - agent -c "claude --dangerously-skip-permissions --version" || true

echo "[INFO] Claude Code configured with max turns: ${MAX_CODING_ITERATIONS:-500}"
echo "[INFO] MCP config at: $CLAUDE_MCP_CONFIG"

# -----------------------------------------------------------------------------
# Enable Claude Code Agent Teams (experimental)
# -----------------------------------------------------------------------------

echo "[INFO] Configuring Claude Code Agent Teams..."

CLAUDE_SETTINGS_DIR="/home/agent/.claude"
CLAUDE_SETTINGS_FILE="$CLAUDE_SETTINGS_DIR/settings.json"

# Create or update settings.json to enable agent teams
if [ -f "$CLAUDE_SETTINGS_FILE" ]; then
    # If settings.json exists, merge agent teams setting
    if command -v python3 &> /dev/null; then
        python3 -c "
import json, os
settings_file = '$CLAUDE_SETTINGS_FILE'
with open(settings_file, 'r') as f:
    settings = json.load(f)
settings.setdefault('env', {})
settings['env']['CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'] = '1'
# Enable dangerouslySkipPermissions for teammates to work autonomously
with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)
"
    fi
else
    mkdir -p "$CLAUDE_SETTINGS_DIR"
    cat > "$CLAUDE_SETTINGS_FILE" << 'SETTINGS_EOF'
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
SETTINGS_EOF
    chown agent:agent "$CLAUDE_SETTINGS_FILE"
fi

# Ensure teams and tasks directories exist
mkdir -p "$CLAUDE_SETTINGS_DIR/teams"
mkdir -p "$CLAUDE_SETTINGS_DIR/tasks"
chown -R agent:agent "$CLAUDE_SETTINGS_DIR/teams" "$CLAUDE_SETTINGS_DIR/tasks"

echo "Claude Code Agent Teams: enabled"

# -----------------------------------------------------------------------------
# Start Health Check Server
# -----------------------------------------------------------------------------

echo "[INFO] Starting health check server..."

# Simple health check server using Python
cat > /tmp/health_server.py << 'EOF'
import http.server
import socketserver
import json

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "healthy", "agent_id": "${AGENT_ID}"}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging

if __name__ == "__main__":
    with socketserver.TCPServer(("", 8080), HealthHandler) as httpd:
        httpd.serve_forever()
EOF

python3 /tmp/health_server.py &
HEALTH_PID=$!

echo "[INFO] Health check server started on port 8080 (PID: $HEALTH_PID)"

# -----------------------------------------------------------------------------
# Credential Refresh Loop
# -----------------------------------------------------------------------------

# Re-copy credentials every 5 minutes in case they are refreshed on the host
(while true; do
  sleep 300
  if [ -d "/claude-credentials" ]; then
    cp -r /claude-credentials/* /home/agent/.claude/ 2>/dev/null || true
    chown -R agent:agent /home/agent/.claude 2>/dev/null || true
    echo "[INFO] Claude credentials refreshed at $(date)"
  fi
done) &
CRED_REFRESH_PID=$!
echo "[INFO] Credential refresh loop started (PID: $CRED_REFRESH_PID, interval: 300s)"

# -----------------------------------------------------------------------------
# Start Daemon Process
# -----------------------------------------------------------------------------

echo "[INFO] Starting Persistent Engineer daemon..."

# Set Python path
export PYTHONPATH="/opt:/opt/daemon:/opt/credentials:$PYTHONPATH"

# Start daemon as agent user
cd /opt/daemon
exec su - agent -c "
    export DISPLAY=:0
    export AGENT_ID='$AGENT_ID'
    export REDIS_URL='$REDIS_URL'
    export CLAUDE_MCP_CONFIG='$CLAUDE_MCP_CONFIG'
    export CLAUDE_PLUGINS_DIR='$CLAUDE_PLUGINS_DIR'
    export CLAUDE_PLUGINS_PATH='/opt/plugins'
    export MAX_CODING_ITERATIONS='${MAX_CODING_ITERATIONS:-500}'
    export PYTHONPATH='/opt:/opt/daemon:/opt/credentials'
    cd /opt/daemon
    python3 daemon.py
"

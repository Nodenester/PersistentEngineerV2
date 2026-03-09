#!/bin/bash
set -e

echo "=========================================="
echo "Persistent Engineer Agent (Minimal)"
echo "=========================================="

# Environment
if [ -z "$AGENT_ID" ]; then export AGENT_ID="default"; fi
if [ -z "$REDIS_URL" ]; then export REDIS_URL="redis://redis:6379"; fi

# Directories
mkdir -p /workspace/projects /workspace/.state /workspace/.creds /workspace/.agent-memory
chown -R agent:agent /workspace || true

# Update Claude Code
echo "[entrypoint] Checking for Claude Code updates..."
npm update -g @anthropic-ai/claude-code 2>&1 | tail -3 || true

# Wait for Redis
REDIS_HOST=$(echo $REDIS_URL | sed -e 's|redis://||' -e 's|:.*||')
REDIS_PORT=$(echo $REDIS_URL | sed -e 's|.*:||' -e 's|/.*||')
REDIS_HOST=${REDIS_HOST:-localhost}
REDIS_PORT=${REDIS_PORT:-6379}

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

# Claude credentials
AGENT_CLAUDE_DIR=/home/agent/.claude
mkdir -p $AGENT_CLAUDE_DIR
if [ -d "/claude-credentials" ]; then
    echo "[INFO] Copying Claude credentials..."
    for item in /claude-credentials/*; do
        [ -e "$item" ] && cp -r "$item" "$AGENT_CLAUDE_DIR/" 2>/dev/null || true
    done
    for item in /claude-credentials/.*; do
        basename=$(basename "$item")
        [ "$basename" != "." ] && [ "$basename" != ".." ] && [ -e "$item" ] && cp -r "$item" "$AGENT_CLAUDE_DIR/" 2>/dev/null || true
    done
    chown -R agent:agent $AGENT_CLAUDE_DIR
fi

# Claude config
LOCAL_CLAUDE_DIR=/opt/claude-local
mkdir -p $LOCAL_CLAUDE_DIR/plugins
[ -f /opt/mcp-tools/mcp.json ] && cp /opt/mcp-tools/mcp.json $LOCAL_CLAUDE_DIR/mcp.json
if [ -d "/opt/plugins" ]; then
    for plugin in /opt/plugins/*; do
        [ -d "$plugin" ] && ln -sf "$plugin" "$LOCAL_CLAUDE_DIR/plugins/$(basename "$plugin")"
    done
fi
chown -R agent:agent $LOCAL_CLAUDE_DIR

export CLAUDE_MCP_CONFIG=$LOCAL_CLAUDE_DIR/mcp.json
export CLAUDE_PLUGINS_DIR=$LOCAL_CLAUDE_DIR/plugins
export CLAUDE_PLUGINS_PATH=/opt/plugins

# Accept terms
su - agent -c "claude --dangerously-skip-permissions --version" || true

# Health check server
cat > /tmp/health_server.py << 'EOF'
import http.server, socketserver, json
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, *a): pass
if __name__ == "__main__":
    with socketserver.TCPServer(("", 8080), H) as s: s.serve_forever()
EOF
python3 /tmp/health_server.py &

# Credential refresh loop
(while true; do
  sleep 300
  if [ -d "/claude-credentials" ]; then
    cp -r /claude-credentials/* /home/agent/.claude/ 2>/dev/null || true
    chown -R agent:agent /home/agent/.claude 2>/dev/null || true
  fi
done) &

# Start daemon
export PYTHONPATH="/opt:/opt/daemon:/opt/credentials:$PYTHONPATH"
cd /opt/daemon
exec su - agent -c "
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

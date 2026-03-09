# =============================================================================
# Persistent Engineer Agent - Windows Daemon Entrypoint
# =============================================================================
# Starts the daemon process on Windows
# =============================================================================

Write-Host "=========================================="
Write-Host "Persistent Engineer Agent - Starting..."
Write-Host "=========================================="

# -----------------------------------------------------------------------------
# Environment validation
# -----------------------------------------------------------------------------

Write-Host "[INFO] Validating environment..."

if (-not $env:AGENT_ID) {
    $env:AGENT_ID = "default"
    Write-Host "[INFO] AGENT_ID not set, using: $env:AGENT_ID"
}

if (-not $env:REDIS_URL) {
    $env:REDIS_URL = "redis://redis:6379"
    Write-Host "[INFO] REDIS_URL not set, using: $env:REDIS_URL"
}

# -----------------------------------------------------------------------------
# Create required directories
# -----------------------------------------------------------------------------

Write-Host "[INFO] Creating directories..."

$dirs = @(
    "C:\workspace\projects",
    "C:\workspace\.state",
    "C:\workspace\.creds",
    "C:\workspace\.agent-memory"
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
}

# -----------------------------------------------------------------------------
# Wait for Redis
# -----------------------------------------------------------------------------

Write-Host "[INFO] Waiting for Redis..."

$redisUrl = $env:REDIS_URL -replace "redis://", ""
$parts = $redisUrl -split ":"
$redisHost = $parts[0]
$redisPort = if ($parts.Length -gt 1) { $parts[1] } else { "6379" }

$maxRetries = 30
$retryCount = 0

while ($retryCount -lt $maxRetries) {
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.Connect($redisHost, [int]$redisPort)
        $tcpClient.Close()
        Write-Host "[INFO] Redis is ready"
        break
    }
    catch {
        $retryCount++
        if ($retryCount -ge $maxRetries) {
            Write-Host "[ERROR] Redis not available after $maxRetries attempts"
            exit 1
        }
        Write-Host "[INFO] Waiting for Redis... ($retryCount/$maxRetries)"
        Start-Sleep -Seconds 1
    }
}

# -----------------------------------------------------------------------------
# Configure Claude Code
# -----------------------------------------------------------------------------

Write-Host "[INFO] Configuring Claude Code..."

$claudeDir = "$env:USERPROFILE\.claude"
if (-not (Test-Path $claudeDir)) {
    New-Item -ItemType Directory -Force -Path $claudeDir | Out-Null
}

# Copy MCP config
Copy-Item "C:\opt\mcp-tools\mcp.json" "$claudeDir\mcp.json" -Force

# -----------------------------------------------------------------------------
# Start Health Check Server
# -----------------------------------------------------------------------------

Write-Host "[INFO] Starting health check server..."

$healthJob = Start-Job -ScriptBlock {
    $listener = New-Object System.Net.HttpListener
    $listener.Prefixes.Add("http://+:8080/")
    $listener.Start()

    while ($true) {
        $context = $listener.GetContext()
        $response = $context.Response

        if ($context.Request.Url.AbsolutePath -eq "/health") {
            $json = '{"status": "healthy", "agent_id": "' + $env:AGENT_ID + '"}'
            $buffer = [System.Text.Encoding]::UTF8.GetBytes($json)
            $response.ContentType = "application/json"
            $response.ContentLength64 = $buffer.Length
            $response.OutputStream.Write($buffer, 0, $buffer.Length)
        }
        else {
            $response.StatusCode = 404
        }

        $response.Close()
    }
}

Write-Host "[INFO] Health check server started on port 8080"

# -----------------------------------------------------------------------------
# Start Daemon Process
# -----------------------------------------------------------------------------

Write-Host "[INFO] Starting Persistent Engineer daemon..."

# Set Python path
$env:PYTHONPATH = "C:\opt;C:\opt\daemon;C:\opt\credentials"

# Start daemon
Set-Location "C:\opt\daemon"
python daemon.py

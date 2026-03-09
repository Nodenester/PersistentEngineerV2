#!/bin/bash
# Build all MCP tools for the coding agent
# This runs inside the Docker container during build

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Building MCP tools in $SCRIPT_DIR ==="

# Build all .NET projects
for dir in "$SCRIPT_DIR"/*/; do
    if [ -f "$dir"/*.csproj ]; then
        name=$(basename "$dir")
        csproj=$(ls "$dir"/*.csproj | head -1)

        echo ""
        echo "=== Building: $name ==="
        cd "$dir"

        # Restore and build
        dotnet restore "$csproj"
        dotnet build -c Release "$csproj"

        # Verify the DLL was created
        dll_path="$dir/bin/Release/net8.0/$name.dll"
        if [ -f "$dll_path" ]; then
            echo "✓ Built: $dll_path"
        else
            echo "✗ ERROR: DLL not found at $dll_path"
            ls -la "$dir/bin/Release/net8.0/" 2>/dev/null || echo "  (bin/Release/net8.0 does not exist)"
        fi
    fi
done

# Special handling for CodeStructureAnalyzer (it outputs codeparse.dll not CodeStructureAnalyzer.dll)
if [ -f "$SCRIPT_DIR/CodeStructureAnalyzer/bin/Release/net8.0/codeparse.dll" ]; then
    echo "✓ CodeStructureAnalyzer built as codeparse.dll"
fi

echo ""
echo "=== MCP Tools Build Complete ==="
echo ""
echo "Built tools:"
find "$SCRIPT_DIR" -name "*.dll" -path "*/bin/Release/*" 2>/dev/null | head -20

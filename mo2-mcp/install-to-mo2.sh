#!/bin/bash
# Deploy the bundled FNV MO2 MCP plugin into a Mod Organizer 2 install.
#
#   bash mo2-mcp/install-to-mo2.sh "<your MO2 folder>"
#
# The target is the folder that contains ModOrganizer.exe and a `plugins/` subfolder.
# For a PORTABLE instance that's the instance folder itself; for a GLOBAL instance it's
# the MO2 installation directory (plugins are shared across global instances).
#
# This is the manual/standalone deploy — the YesMan AI installer normally does this for you.
# The MCP adds live MO2 VFS + load-order + conflict awareness while MO2 is open; when MO2 is
# closed the toolbox falls back to the AutoMod CLI, so it keeps working either way.
set -e

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_SRC="$SRC_DIR/fnv_mo2_mcp"

MO2="$1"
if [ -z "$MO2" ]; then
    echo "Usage: bash mo2-mcp/install-to-mo2.sh \"<path to your MO2 folder>\""
    echo "  (the folder with ModOrganizer.exe + a 'plugins' subfolder; for a portable"
    echo "   instance, that's the instance folder itself)"
    exit 1
fi
if [ ! -d "$PLUGIN_SRC" ]; then
    echo "ERROR: plugin source not found at $PLUGIN_SRC"
    exit 1
fi
if [ ! -d "$MO2" ]; then
    echo "ERROR: not a folder: $MO2"
    exit 1
fi

PLUGINS="$MO2/plugins"
if [ ! -d "$PLUGINS" ]; then
    if [ -f "$MO2/ModOrganizer.exe" ]; then
        mkdir -p "$PLUGINS"
    else
        echo "ERROR: no 'plugins' folder and no ModOrganizer.exe under: $MO2"
        echo "Point this at your MO2 installation (or portable instance) folder."
        exit 1
    fi
fi

DEST="$PLUGINS/fnv_mo2_mcp"
[ -d "$DEST" ] && echo "NOTE: $DEST exists — updating files (your MO2 plugin settings are preserved)."

cp -r "$PLUGIN_SRC" "$PLUGINS/"
rm -rf "$DEST/__pycache__" 2>/dev/null || true

echo ""
echo "Deployed FNV MO2 MCP -> $DEST"
echo "Next:"
echo "  1. (Re)start MO2. Settings -> Plugins -> 'FNV MO2 MCP Server' should appear; tick it enabled."
echo "  2. Auto-start is ON by default: while MO2 is open the server listens on 127.0.0.1:49200."
echo "  3. The plugin registers itself with Claude Code (writes mcpServers.mo2 in ~/.claude.json)."
echo "     Restart Claude Code once after the first install."
echo "  4. Verify from a Claude session: call mo2_ping (expect game 'New Vegas')."
echo ""
echo "To remove later: delete $DEST and the mcpServers.mo2 entry in ~/.claude.json."

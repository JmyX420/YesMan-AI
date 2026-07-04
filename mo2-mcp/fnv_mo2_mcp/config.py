# fnv_mo2_mcp — Configuration defaults
#
# Fallout: New Vegas port of the MO2 MCP Server.
# Derived from "MO2 MCP Server" v2.9.5 by Aaronavich (MIT License). See NOTICE.md.

DEFAULT_PORT = 49200      # FNV/NVMP-aware: avoid 27015 (Source/Steam dedicated-server + NVMP co-op)
DEFAULT_OUTPUT_MOD = "Claude Output"
DEFAULT_LOG_LEVEL = "info"
# Default-AVAILABLE (not default-required): once the plugin is enabled in MO2, the
# server starts itself on MO2 launch so the toolbox "just works" while MO2 is open.
# The toolbox still functions fully without it — skills detect-and-prefer, never require.
DEFAULT_AUTO_START = True

PLUGIN_NAME = "FNV MO2 MCP Server"
PLUGIN_VERSION = (1, 0, 0)
PLUGIN_AUTHOR = "JmyX"
PLUGIN_DESCRIPTION = (
    "Connects AI assistants to a Fallout: New Vegas Mod Organizer 2 setup — "
    "modlist queries, VFS file access, conflict detection, BSA, NIF, and "
    "NVSE-DLL tools. Record reading/patching is backed by xEditLib (FNV), not "
    "Mutagen. Port of Aaronavich's MO2 MCP Server."
)

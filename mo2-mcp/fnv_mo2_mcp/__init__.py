# fnv_mo2_mcp - MCP server plugin for Mod Organizer 2 (Fallout: New Vegas)
# Derived from "MO2 MCP Server" by Aaronavich (MIT). FNV port (c) 2026 JmyX.
# See LICENSE and NOTICE.md.
#
# A component of YesMan AI, installed with the toolbox. When MO2 is open with this
# plugin enabled, it gives Claude live VFS, load-order, and conflict awareness; when
# MO2 is closed the skills fall back to the AutoMod CLI. Records/assets are re-backed
# on that AutoMod CLI (xEditLib / BSArch -fnv / oggenc2), NOT Mutagen (no FNV support).

import json
import os
import re

from PyQt6.QtCore import qInfo, qWarning
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMessageBox

import mobase

from .config import (
    DEFAULT_PORT,
    DEFAULT_OUTPUT_MOD,
    DEFAULT_AUTO_START,
    PLUGIN_NAME,
    PLUGIN_VERSION,
    PLUGIN_AUTHOR,
    PLUGIN_DESCRIPTION,
)
from .mcp_server import MCPServer
from .tools_modlist import register_modlist_tools
from .tools_filesystem import register_filesystem_tools
from .tools_write import register_write_tools
from .tools_dll import register_dll_tools
from .tools_archive import register_archive_tools
from .tools_nif import register_nif_tools
from .tools_audio import register_audio_tools
from .tools_records import register_record_tools

# Phase 2b — conflict/override analysis + patch creation on xEditLib (AutoMod `esp`):
#   from .tools_patching import register_patching_tools
# Dropped for FNV: Papyrus compilation (FNV has no Papyrus — GECK script lives in-plugin).


def _ensure_mcp_config(port: int) -> None:
    """Register this server (`mo2`) with every AI agent installed on this machine.

    The server's port is a plugin setting the user can change, so the registration must
    track the LIVE port. We therefore (re)write it on each MO2 start into whichever agent
    config files exist — Claude Code's `~/.claude.json` and/or Codex's
    `~/.codex/config.toml`. Registering with "whatever is present" keeps the plugin
    agent-agnostic (a machine with both agents gets both). Each writer is best-effort and
    must NEVER raise — server startup can't fail because of this.
    """
    _ensure_claude_json(port)
    _ensure_codex_toml(port)


def _ensure_claude_json(port: int) -> None:
    """Register mo2 (http) under `mcpServers` in ~/.claude.json (JSON). Skips if the file
    is absent (Claude Code not installed). Atomic write; never raises. The key is "mo2"
    so the toolbox's skills can detect-and-prefer it."""
    try:
        config_path = os.path.expanduser("~/.claude.json")
        if not os.path.isfile(config_path):
            return
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        entry = {"type": "http", "url": f"http://127.0.0.1:{port}/mcp"}
        servers = config.setdefault("mcpServers", {})
        if servers.get("mo2") == entry:
            return
        servers["mo2"] = entry
        tmp_path = config_path + ".mo2-tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, config_path)
        qInfo(f"{PLUGIN_NAME}: registered MCP server with Claude Code in {config_path}")
    except Exception as exc:
        qWarning(f"{PLUGIN_NAME}: failed to update Claude Code MCP config: {exc}")


def _ensure_codex_toml(port: int) -> None:
    """Register mo2 (http) as `[mcp_servers.mo2]` in ~/.codex/config.toml (TOML). Skips if
    the file is absent (Codex not installed / the toolbox's Codex variant not configured —
    the installer creates it). Text-based upsert of just our table, so the rest of the
    user's config (comments, other servers, project trust) is preserved. Atomic; never raises.
    """
    try:
        config_path = os.path.expanduser("~/.codex/config.toml")
        if not os.path.isfile(config_path):
            return
        with open(config_path, "r", encoding="utf-8") as f:
            text = f.read()
        url_line = f'url = "http://127.0.0.1:{port}/mcp"'
        block = f"[mcp_servers.mo2]\n{url_line}\n"
        # our table = the header line through to just before the next top-level table or EOF
        pat = re.compile(r'(?ms)^[ \t]*\[mcp_servers\.mo2\][ \t]*$.*?(?=^[ \t]*\[|\Z)')
        existing = pat.search(text)
        if existing:
            if url_line in existing.group(0):
                return  # already registered with the current port
            new_text = pat.sub(lambda _m: block, text, count=1)
        else:
            new_text = text
            if new_text and not new_text.endswith("\n"):
                new_text += "\n"
            if new_text:
                new_text += "\n"
            new_text += block
        tmp_path = config_path + ".mo2-tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        os.replace(tmp_path, config_path)
        qInfo(f"{PLUGIN_NAME}: registered MCP server with Codex in {config_path}")
    except Exception as exc:
        qWarning(f"{PLUGIN_NAME}: failed to update Codex MCP config: {exc}")


# Executables exempt from the auto-stop-before-launch behavior.
#
# The auto-stop in `_on_about_to_run` prevents an MO2 hang caused by the HTTP server
# thread conflicting with MO2's VFS setup during game launch. xEdit/FNVEdit are
# exempted so the server stays alive while the user has xEdit open for interactive
# viewing (Claude reads records via the AutoMod backend concurrently). Matches the
# FNV-relevant xEdit family with any version/build suffix, case-insensitive against
# os.path.basename(app_path).
_AUTOSTOP_EXEMPT_PATTERN = re.compile(
    r'^(fnvedit|fo3edit|tes4edit|xedit)[\w \-]*\.exe$',
    re.IGNORECASE,
)


class Mo2McpPlugin(mobase.IPluginTool):

    def __init__(self):
        super().__init__()
        self._organizer = None
        self._parent_widget = None
        self._server = None
        # _restart_pending latches that we stopped a running server for a launch and
        # owe it a restart. SET in _on_about_to_run, cleared ONLY in _on_finished_run.
        # A launcher that spawns a separate game process (e.g. NVMP's launcher) makes
        # MO2 fire multiple onAboutToRun/onFinishedRun cycles per launch; the latch must
        # survive the extra onAboutToRun events. The server is brought back on the first
        # onFinishedRun after a stop. See PORT_PLAN.md / upstream LOCAL_CHANGES.
        self._restart_pending = False

    # ── IPlugin interface ────────────────────────────────────────────

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        organizer.onAboutToRun(self._on_about_to_run)
        organizer.onFinishedRun(self._on_finished_run)
        organizer.onUserInterfaceInitialized(self._on_ui_initialized)
        qInfo(f"{PLUGIN_NAME}: plugin loaded")
        return True

    def _on_ui_initialized(self, main_window) -> None:
        """Start the server automatically on MO2 startup if auto-start is set.

        Runs once the main window is ready (not in init(), which fires too early to
        safely spin up the HTTP server thread). Starts quietly — no message box —
        since this happens every launch. Failure is logged, not popped, so a busy
        port can't block MO2 startup with a modal dialog.
        """
        if not self._organizer.pluginSetting(self.name(), "auto-start"):
            return
        if self._server and self._server.is_running():
            return
        if self._start_server_core():
            port = self._organizer.pluginSetting(self.name(), "port")
            _ensure_mcp_config(port)
            qInfo(f"{PLUGIN_NAME}: auto-started server on port {port}")
        else:
            qWarning(f"{PLUGIN_NAME}: auto-start failed (port in use?)")

    def name(self) -> str:
        return PLUGIN_NAME

    def author(self) -> str:
        return PLUGIN_AUTHOR

    def description(self) -> str:
        return PLUGIN_DESCRIPTION

    def version(self) -> mobase.VersionInfo:
        major, minor, patch = PLUGIN_VERSION
        return mobase.VersionInfo(major, minor, patch, mobase.ReleaseType.FINAL)

    def settings(self) -> list[mobase.PluginSetting]:
        return [
            mobase.PluginSetting(
                "port",
                "TCP port for the MCP server",
                DEFAULT_PORT,
            ),
            mobase.PluginSetting(
                "output-mod",
                "Name of the mod folder for Claude's file output",
                DEFAULT_OUTPUT_MOD,
            ),
            mobase.PluginSetting(
                "auto-start",
                "Start the MCP server automatically when MO2 launches",
                DEFAULT_AUTO_START,
            ),
            mobase.PluginSetting(
                "automod-path",
                "Path to YesMan AI (for BSA/NIF/audio tools). "
                "Empty = auto-detect in the game folder.",
                "",
            ),
        ]

    def requirements(self) -> list[mobase.IPluginRequirement]:
        return [
            mobase.PluginRequirementFactory.gameDependency({
                "New Vegas",
            })
        ]

    # ── IPluginTool interface ────────────────────────────────────────

    def displayName(self) -> str:
        return "Start/Stop Claude Server"

    def tooltip(self) -> str:
        return "Toggle the MCP server for Claude integration"

    def icon(self) -> QIcon:
        return QIcon()

    def setParentWidget(self, widget) -> None:
        self._parent_widget = widget

    def display(self) -> None:
        if self._server and self._server.is_running():
            self._stop_server()
        else:
            self._start_server()

    # ── Server lifecycle ─────────────────────────────────────────────

    def _start_server_core(self) -> bool:
        """Start the MCP server. Returns True on success, False on failure."""
        port = self._organizer.pluginSetting(self.name(), "port")
        self._server = MCPServer(port)
        self._register_tools()
        try:
            self._server.start()
        except OSError as e:
            qWarning(f"{PLUGIN_NAME}: failed to start server: {e}")
            self._server = None
            return False
        return True

    def _start_server(self) -> None:
        port = self._organizer.pluginSetting(self.name(), "port")
        if not self._start_server_core():
            QMessageBox.critical(
                self._parent_widget,
                PLUGIN_NAME,
                f"Failed to start MCP server on port {port}.",
            )
            return
        _ensure_mcp_config(port)
        QMessageBox.information(
            self._parent_widget,
            PLUGIN_NAME,
            f"MCP server started on localhost:{port}\n\n"
            f"Claude Code MCP config updated automatically.\n"
            f"Restart Claude Code if this is the first time.",
        )

    def _stop_server(self) -> None:
        if self._server:
            self._server.stop()
            self._server = None
        QMessageBox.information(
            self._parent_widget,
            PLUGIN_NAME,
            "MCP server stopped.",
        )

    # ── Auto-stop/restart around executable launches ────────────────

    def _on_about_to_run(self, app_path: str) -> bool:
        """Called by MO2 before launching any executable.

        Exempts xEdit/FNVEdit (interactive viewer) from the auto-stop so the MCP
        server stays alive during its lifetime. Game launches still trigger the
        auto-stop. See `_AUTOSTOP_EXEMPT_PATTERN` for rationale + scope.
        """
        exe_name = os.path.basename(app_path)
        if _AUTOSTOP_EXEMPT_PATTERN.match(exe_name):
            qInfo(f"{PLUGIN_NAME}: keeping server alive across launch of {app_path} (exempt)")
            return True

        if self._server and self._server.is_running():
            qInfo(f"{PLUGIN_NAME}: stopping server before launch of {app_path}")
            self._server.stop()
            self._server = None
            self._restart_pending = True
        # NOTE: do NOT clear _restart_pending here. A launcher that spawns a child
        # process fires a second onAboutToRun with the server already stopped;
        # clearing the latch in that case is the original bug.
        return True

    def _on_finished_run(self, app_path: str, exit_code: int) -> None:
        """Called by MO2 after a launched executable finishes.

        Restarts the server on the FIRST finished-run after we stopped it for a
        launch. The entry log line records every invocation and the latch/running
        state so the launch sequence is always traceable in mo_interface.log.
        """
        running = bool(self._server and self._server.is_running())
        qInfo(
            f"{PLUGIN_NAME}: finished-run hook for {os.path.basename(app_path)} "
            f"(restart_pending={self._restart_pending}, running={running}, exit={exit_code})"
        )
        if not self._restart_pending or running:
            return

        self._restart_pending = False
        qInfo(f"{PLUGIN_NAME}: restarting server after {app_path} exited (code {exit_code})")
        if self._start_server_core():
            port = self._organizer.pluginSetting(self.name(), "port")
            _ensure_mcp_config(port)
            qInfo(f"{PLUGIN_NAME}: server restarted successfully")
        else:
            qWarning(f"{PLUGIN_NAME}: failed to restart server after launch")

    # ── Tool registration ────────────────────────────────────────────

    def _register_tools(self) -> None:
        reg = self._server.registry
        organizer = self._organizer

        reg.register(
            name="mo2_ping",
            description="Check if the FNV MO2 MCP server is running. Returns server version and MO2 info.",
            input_schema={
                "type": "object",
                "properties": {},
            },
            handler=lambda args: json.dumps({
                "status": "ok",
                "server": PLUGIN_NAME,
                "version": ".".join(str(v) for v in PLUGIN_VERSION),
                "mo2_version": str(organizer.appVersion()),
                "game": organizer.managedGame().gameName(),
                "profile": organizer.profile().name(),
            }, indent=2),
        )

        # Phase 1: mod/plugin queries, VFS filesystem, and sandboxed write — all
        # pure mobase (game-agnostic), working on FNV today.
        register_modlist_tools(reg, organizer)
        register_filesystem_tools(reg, organizer)
        register_write_tools(reg, organizer)
        register_dll_tools(reg, organizer)
        register_archive_tools(reg, organizer)  # BSA via AutoMod `bsa` (BSArch -fnv)
        register_nif_tools(reg, organizer)       # NIF via AutoMod `nif`
        register_audio_tools(reg, organizer)     # ogg/wav via AutoMod `audio` (oggenc2)
        register_record_tools(reg, organizer)    # Phase 2a: query/detail via AutoMod `esp` (xEditLib)

        # Phase 2b — conflict/override analysis + patch creation on xEditLib:
        #   register_record_tools(reg, organizer)
        #   register_patching_tools(reg, organizer)


def createPlugin() -> mobase.IPlugin:
    return Mo2McpPlugin()

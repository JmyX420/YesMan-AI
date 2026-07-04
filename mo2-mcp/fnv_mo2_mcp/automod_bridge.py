"""Bridge from the MO2 plugin to YesMan AI's AutoMod CLI.

The asset/record tools do NOT reimplement BSA/NIF/audio/record logic — they shell
out to the toolbox's validated AutoMod CLI:

    node <toolbox>/tools/automod/cli.js <module> <command> <args...> --json

The plugin lives in MO2's plugins/ folder; the toolbox lives in the FNV game folder.
We locate cli.js via the 'automod-path' plugin setting, else the managed game's
install directory (where the toolbox extracts).
"""

import json
import os
import shutil
import subprocess
import tempfile

from .config import PLUGIN_NAME


def _find_node():
    return shutil.which("node") or shutil.which("node.exe")


def find_automod_cli(organizer) -> str | None:
    """Locate tools/automod/cli.js.

    Order: the explicit 'automod-path' plugin setting (toolbox root, tools/automod,
    or a direct cli.js path), then the managed game's install directory.
    """
    setting = organizer.pluginSetting(PLUGIN_NAME, "automod-path")
    if setting:
        s = str(setting)
        if s.lower().endswith("cli.js") and os.path.isfile(s):
            return s
        for cand in (
            os.path.join(s, "tools", "automod", "cli.js"),
            os.path.join(s, "automod", "cli.js"),
            os.path.join(s, "cli.js"),
        ):
            if os.path.isfile(cand):
                return cand

    try:
        game_dir = organizer.managedGame().gameDirectory().absolutePath()
        cand = os.path.join(game_dir, "tools", "automod", "cli.js")
        if os.path.isfile(cand):
            return cand
    except Exception:
        pass
    return None


def automod_available(organizer) -> dict:
    """Return {'ok': bool, ...} describing whether the bridge can run.

    Lets tools give a precise 'why not' (no node / toolbox not found) instead of a
    generic failure — and lets the MCP degrade gracefully when the CLI is absent.
    """
    if not _find_node():
        return {"ok": False, "reason": "node-missing",
                "error": "Node.js not found on PATH. The AutoMod-backed tools (BSA/NIF/audio) "
                         "need Node; install it from https://nodejs.org/."}
    cli = find_automod_cli(organizer)
    if not cli:
        return {"ok": False, "reason": "toolkit-missing",
                "error": "AutoMod CLI (tools/automod/cli.js) not found. Set the 'automod-path' "
                         "plugin setting to your YesMan AI folder, or extract the "
                         "toolbox into your FNV game folder."}
    return {"ok": True, "cli": cli}


def run_automod(organizer, module: str, command: str, args=None, timeout: int = 120) -> dict:
    """Invoke `node cli.js <module> <command> <args...> --json`; return parsed JSON.

    On any failure returns {'ok': False, 'error': ...} so callers uniformly check
    result.get('ok'). The CLI itself emits {'ok': true/false, ...}.
    """
    avail = automod_available(organizer)
    if not avail["ok"]:
        return {"ok": False, "error": avail["error"]}
    node = _find_node()
    cli = avail["cli"]

    cmd = [node, cli, module, command] + [str(a) for a in (args or [])] + ["--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"AutoMod {module} {command} timed out after {timeout}s"}
    except Exception as exc:
        return {"ok": False, "error": f"Failed to run AutoMod CLI: {exc}"}

    out = (proc.stdout or "").strip()
    if not out:
        return {"ok": False,
                "error": f"AutoMod returned no output (exit {proc.returncode}).",
                "stderr": (proc.stderr or "").strip()[:1000]}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # If any stray logging leaked before the JSON, recover the last JSON object.
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return {"ok": False, "error": "AutoMod output was not valid JSON.", "raw": out[:1000]}


def run_automod_vfs(organizer, module: str, command: str, args=None, timeout: int = 180) -> dict:
    """Run the AutoMod CLI THROUGH MO2 so Node inherits MO2's virtual file system.

    Plain subprocess (`run_automod`) does NOT inherit usvfs, so xEditLib sees only the
    real Data folder — fine for asset tools (which pass already-resolved absolute paths)
    but not for record tools, which load a plugin + its masters BY NAME and so need the
    modded order visible. `IOrganizer.startApplication` launches Node inside the VFS.

    startApplication doesn't expose stdout, so the CLI writes its JSON to a `--out` temp
    file (outside the VFS-mapped game dir → a real write) which we read back.

    NOTE: `timeout` is advisory — `waitForApplication` blocks until the process exits and
    mobase exposes no timeout on it. The CLI is bounded, so this is acceptable.
    """
    avail = automod_available(organizer)
    if not avail["ok"]:
        return {"ok": False, "error": avail["error"]}
    node = _find_node()
    cli = avail["cli"]
    # cli = <toolbox>/tools/automod/cli.js  →  toolbox root two levels up
    toolkit_root = os.path.dirname(os.path.dirname(os.path.dirname(cli)))

    fd, out_path = tempfile.mkstemp(suffix=".json", prefix="automod_vfs_")
    os.close(fd)
    try:
        cli_args = [cli, module, command] + [str(a) for a in (args or [])] + ["--json", "--out", out_path]
        try:
            handle = organizer.startApplication(node, cli_args, toolkit_root, "", "", False)
        except Exception as exc:
            return {"ok": False, "error": f"startApplication failed to launch Node through MO2: {exc}"}
        if not handle:
            return {"ok": False, "error": "startApplication returned no handle (Node failed to launch through MO2)."}
        try:
            ok, exit_code = organizer.waitForApplication(handle)
        except Exception as exc:
            return {"ok": False, "error": f"waitForApplication failed: {exc}"}

        try:
            with open(out_path, "r", encoding="utf-8") as f:
                txt = f.read().strip()
        except OSError:
            txt = ""
        if not txt:
            return {"ok": False,
                    "error": f"AutoMod (via MO2) produced no output (exit {exit_code}). The CLI may have "
                             f"crashed before writing its result, or Node could not be launched through MO2."}
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return {"ok": False, "error": "AutoMod output was not valid JSON.", "raw": txt[:1000]}
    finally:
        try:
            os.remove(out_path)
        except OSError:
            pass

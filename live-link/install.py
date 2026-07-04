#!/usr/bin/env python3
"""YesMan AI Live Link — installer.

A component of YesMan AI, installed with the toolbox (this script is invoked by the
unified installer/configurator, and can also be run standalone). Re-architecture of the
SkyLink AI concept by Jarvann (MIT). See LICENSE / NOTICE.md.

What it does (idempotent — safe to re-run):
  1. Creates the bridge dir  <game-root>\\FNVLink\\  and seeds the relay-owned batch
     files (dispatch/state_write/evt_*, plus the chat batches + injectable UI) so the
     in-game scripts work on first launch.
  2. Deploys the in-game mod (the eight ln_ scripts) — either as a Mod Organizer 2
     mod folder (--deploy mo2 --mo2-mods <dir>) or straight into Data (--deploy data).
  3. Registers the relay as a stdio MCP server "fnv-link" in ~/.claude.json so Claude
     Code can talk to it from any project.

Run:  python install.py --game-root "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Fallout New Vegas" \
                        --deploy mo2 --mo2-mods "<your MO2 instance>\\mods"
      python install.py --uninstall        (reverse steps 2-3; leaves the bridge dir)
"""

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_SRC = os.path.join(HERE, "game", "NVSE", "plugins", "scripts")
MOD_NAME = "YesMan AI Live Link"
MCP_KEY = "fnv-link"

# Make the relay package importable so we can seed the bridge dir during install.
sys.path.insert(0, HERE)


def _log(msg):
    print("  " + msg)


def find_game_root(explicit):
    """Resolve + validate the FNV install dir (must contain FalloutNV.exe)."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    else:
        for base in (r"C:\Program Files (x86)\Steam", r"D:\SteamLibrary", r"E:\SteamLibrary",
                     r"C:\SteamLibrary"):
            candidates.append(os.path.join(base, "steamapps", "common", "Fallout New Vegas"))
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "FalloutNV.exe")):
            return os.path.abspath(c)
    return None


def seed_bridge(game_root):
    """Create <game-root>\\FNVLink\\ and materialise the relay-owned batch files."""
    from fnv_link_server.config import BRIDGE_SUBFOLDER
    from fnv_link_server.bridge import Bridge
    bridge_dir = os.path.join(game_root, BRIDGE_SUBFOLDER)
    Bridge(bridge_dir).seed()
    _log("bridge dir seeded: %s" % bridge_dir)
    return bridge_dir


def deploy_mod(target_scripts_dir):
    os.makedirs(target_scripts_dir, exist_ok=True)
    for fn in sorted(os.listdir(SCRIPTS_SRC)):
        if fn.lower().endswith(".txt"):
            shutil.copy2(os.path.join(SCRIPTS_SRC, fn), os.path.join(target_scripts_dir, fn))
            _log("deployed %s" % fn)


def deploy(args, game_root):
    if args.deploy == "mo2":
        if not args.mo2_mods or not os.path.isdir(args.mo2_mods):
            sys.exit("ERROR: --deploy mo2 requires --mo2-mods <existing MO2 mods dir>")
        mod_root = os.path.join(args.mo2_mods, MOD_NAME)
        scripts = os.path.join(mod_root, "NVSE", "plugins", "scripts")
        deploy_mod(scripts)
        meta = os.path.join(mod_root, "meta.ini")
        if not os.path.isfile(meta):
            with open(meta, "w", encoding="utf-8") as f:
                f.write("[General]\nmodid=0\nversion=1.0.0\n"
                        "comments=YesMan AI live link\n")
        _log("MO2 mod: %s  (enable it in MO2's left pane)" % mod_root)
    elif args.deploy == "data":
        scripts = os.path.join(game_root, "Data", "NVSE", "plugins", "scripts")
        deploy_mod(scripts)
        _log("deployed into Data (non-MO2): %s" % scripts)
    else:
        _log("skipped mod deploy (--deploy none); deploy the ln_ scripts yourself")


def register_mcp(bridge_dir, python_exe):
    """Add/update mcpServers['fnv-link'] in ~/.claude.json (atomic, best-effort)."""
    cfg_path = os.path.expanduser("~/.claude.json")
    if not os.path.isfile(cfg_path):
        _log("~/.claude.json not found — skipping MCP registration (is Claude Code installed?)")
        return
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (ValueError, OSError) as e:
        _log("could not read ~/.claude.json (%s) — skipping MCP registration" % e)
        return
    entry = {
        "type": "stdio",
        "command": python_exe,
        "args": ["-m", "fnv_link_server", "--bridge", bridge_dir],
        "cwd": HERE,
        # Claude Code does not reliably honor "cwd" when spawning stdio MCP servers,
        # so "-m fnv_link_server" can't find the package by cwd alone. PYTHONPATH makes
        # the import work regardless of the spawn directory.
        "env": {"PYTHONPATH": HERE},
    }
    servers = cfg.setdefault("mcpServers", {})
    if servers.get(MCP_KEY) == entry:
        _log("MCP server '%s' already registered" % MCP_KEY)
        return
    servers[MCP_KEY] = entry
    tmp = cfg_path + ".fnvlink-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    os.replace(tmp, cfg_path)
    _log("registered MCP server '%s' in %s" % (MCP_KEY, cfg_path))


def uninstall(args, game_root):
    # remove MCP registration
    cfg_path = os.path.expanduser("~/.claude.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("mcpServers", {}).pop(MCP_KEY, None) is not None:
                tmp = cfg_path + ".fnvlink-tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2); f.write("\n")
                os.replace(tmp, cfg_path)
                _log("removed MCP server '%s'" % MCP_KEY)
        except (ValueError, OSError) as e:
            _log("could not edit ~/.claude.json: %s" % e)
    # remove MO2 mod folder if present
    if args.mo2_mods:
        mod_root = os.path.join(args.mo2_mods, MOD_NAME)
        if os.path.isdir(mod_root):
            shutil.rmtree(mod_root, ignore_errors=True)
            _log("removed MO2 mod: %s" % mod_root)
    _log("left the bridge dir in place (delete <game-root>\\FNVLink manually if desired)")


def main(argv=None):
    p = argparse.ArgumentParser(description="YesMan AI Live Link installer")
    p.add_argument("--game-root", help="FNV install dir (auto-detected if omitted)")
    p.add_argument("--deploy", choices=["mo2", "data", "none"], default="mo2")
    p.add_argument("--mo2-mods", help="MO2 instance 'mods' dir (for --deploy mo2)")
    p.add_argument("--python", default=sys.executable,
                   help="Python interpreter to run the MCP server (default: this one)")
    p.add_argument("--no-mcp", action="store_true", help="skip ~/.claude.json registration")
    p.add_argument("--uninstall", action="store_true")
    args = p.parse_args(argv)

    game_root = find_game_root(args.game_root)
    if not game_root:
        sys.exit("ERROR: could not find Fallout New Vegas (FalloutNV.exe). Pass --game-root.")
    print("YesMan AI Live Link %s" % ("uninstall" if args.uninstall else "install"))
    _log("game root: %s" % game_root)

    if args.uninstall:
        uninstall(args, game_root)
        print("Done.")
        return

    bridge_dir = seed_bridge(game_root)
    deploy(args, game_root)
    if not args.no_mcp:
        register_mcp(bridge_dir, args.python)

    print("\nNext steps:")
    print("  1. Install the NVSE stack:")
    print("       Required: xNVSE 6.21+, JIP PP LN (NOT plain JIP LN 57.30 — needed for the")
    print("                 fnv_console catch-all). These alone give the snapshot, commands, chat,")
    print("                 and most events.")
    print("       Recommended (each unlocks more of the 38 event types; the link degrades")
    print("                 gracefully without them): JohnnyGuitar NVSE, ShowOff NVSE, ITR NVSE.")
    if args.deploy == "mo2":
        print("  2. Enable the '%s' mod in MO2 and launch FNV via xNVSE." % MOD_NAME)
    else:
        print("  2. Launch FNV via xNVSE.")
    print("  3. (Optional, for hands-free use) OneTweak BRU with [Active in background] Active=true")
    print("     keeps the game live while you talk to Claude in another window.")
    print("  4. Restart Claude Code so it picks up the new MCP server, then load a save.")
    print("  5. (Optional, for true live feedback) Ask Claude to \"arm the live feed\" so it")
    print("     reacts to events + your in-game chat in real time instead of only when polled.")
    print("     It's per-session: re-arm it each time you start a new Claude Code session.")
    print("Done.")


if __name__ == "__main__":
    main()

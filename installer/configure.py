#!/usr/bin/env python3
r"""YesMan AI - A FNV Modding Toolbox for Claude and Codex -- unified configurator.

One idempotent flow that replaces the three legacy installers (setup.sh,
mo2-mcp/install-to-mo2.sh, live-link/install.py). It is invoked by the Inno Setup
installer AFTER it copies the toolbox files into the Fallout: New Vegas game folder,
and can also be run standalone for testing / re-configuration.

What it does (safe to re-run):
  1. Validates the FNV install and fills the deterministic placeholders (game root, user,
     docs, jq, MO2) in the chosen agent's instruction file + safety hooks.
  2. Auto-detects the Mod Organizer 2 instance + active profile that manages this game
     folder and fills {{MO2_INSTANCE}} / {{MO2_PROFILE}}.
  3. Installs the Node xEditLib backbone (npm install).
  4. Deploys the bundled MO2 MCP plugin into <MO2>/plugins/.
  5. Deploys the YesMan AI Live Link (seeds <game>\FNVLink\, deploys the ln_ scripts as an
     MO2 mod) and registers the "fnv-link" (+ "mo2") MCP servers with the chosen agent(s).

--agent selects the AI coding agent to wire up:
  claude  -> CLAUDE.md, .claude/hooks, .claude/skills, ~/.claude.json  (default)
  codex   -> AGENTS.md, .codex/hooks, .agents/skills, ~/.codex/config.toml + project trust
  both    -> wire up both

All components are installed together -- they are no longer optional add-ons. At RUNTIME
the toolbox still degrades gracefully (skills fall back to the AutoMod CLI when MO2 or the
game is not running); "bundled" means "always installed", not "always running".

Usage (normally the .exe passes these):
  python configure.py --game-root "<FNV folder>" [--agent claude|codex|both]
  python configure.py --game-root "<FNV folder>" --mo2-instance "<MO2 folder>" --agent both
  python configure.py --game-root "<FNV folder>" --uninstall
"""

import argparse
import configparser
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLBOX_ROOT = os.path.dirname(HERE)  # the game folder once installed; dev repo when testing
LIVE_LINK_DIR = os.path.join(TOOLBOX_ROOT, "live-link")
MO2_PLUGIN_SRC = os.path.join(TOOLBOX_ROOT, "mo2-mcp", "fnv_mo2_mcp")
CODEX_SRC = os.path.join(TOOLBOX_ROOT, "codex")
SKILLS_SRC = os.path.join(TOOLBOX_ROOT, ".claude", "skills")
MO2_DEFAULT_PORT = 49200


# --------------------------------------------------------------------------- #
# small utils
# --------------------------------------------------------------------------- #
def log(msg=""):
    print(("  " + msg) if msg else "")


def section(title):
    print("\n" + title)


def _fill_placeholders(path, mapping):
    """Replace {{TOKEN}} occurrences in a text file. Returns True if it changed."""
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    orig = text
    for token, value in mapping.items():
        if value is not None:
            text = text.replace(token, value)
    if text != orig:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    return False


# --------------------------------------------------------------------------- #
# game root
# --------------------------------------------------------------------------- #
def find_game_root(explicit):
    candidates = []
    if explicit:
        candidates.append(explicit)
    # the configurator normally lives IN the game folder (installed there by the .exe)
    candidates.append(TOOLBOX_ROOT)
    for base in (r"C:\Program Files (x86)\Steam", r"D:\SteamLibrary",
                 r"E:\SteamLibrary", r"C:\SteamLibrary"):
        candidates.append(os.path.join(base, "steamapps", "common", "Fallout New Vegas"))
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "FalloutNV.exe")):
            return os.path.abspath(c)
    return None


# --------------------------------------------------------------------------- #
# jq / documents / node
# --------------------------------------------------------------------------- #
def detect_jq(userhome):
    p = shutil.which("jq")
    if p:
        return p
    for cand in (
        os.path.join(userhome, "AppData", "Local", "Microsoft", "WinGet", "Links", "jq.exe"),
        r"C:\ProgramData\chocolatey\bin\jq.exe",
        "/usr/bin/jq",
    ):
        if os.path.isfile(cand):
            return cand
    return None


def detect_documents(userhome):
    for cand in (os.path.join(userhome, "Documents"),
                 os.path.join(userhome, "OneDrive", "Documents")):
        if os.path.isdir(os.path.join(cand, "My Games", "FalloutNV")):
            return cand
    return os.path.join(userhome, "Documents")


def run_npm_install(game_root):
    npm = shutil.which("npm")
    if not npm:
        log("Node.js/npm not found -- install from https://nodejs.org/ then run 'npm install' "
            "in the game folder to enable the xEditLib ESP backbone.")
        return False
    log("Installing xeditlib (bundles XEditLib.dll + FalloutNV.Hardcoded.dat)...")
    try:
        subprocess.run([npm, "install"], cwd=game_root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("xeditlib installed.")
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        log("npm install failed (%s) -- run it manually in the game folder later." % e)
        return False


# --------------------------------------------------------------------------- #
# real python (avoid the Windows Store stub aliases that exit 49)
# --------------------------------------------------------------------------- #
def detect_real_python(explicit):
    """Resolve a real python.exe for the live-link MCP server command.

    The `python`/`py` on PATH may be Windows Store execution-alias stubs that just
    exit 49. Prefer this interpreter (if it is the real one), then the registry
    InstallPath, then PATH candidates that actually run.
    """
    def works(exe):
        if not exe:
            return False
        try:
            r = subprocess.run([exe, "-c", "import sys;print(sys.executable)"],
                               capture_output=True, text=True, timeout=10)
            return r.returncode == 0 and r.stdout.strip().lower().endswith(".exe")
        except (OSError, subprocess.SubprocessError):
            return False

    if explicit and works(explicit):
        return explicit
    if works(sys.executable) and "windowsapps" not in sys.executable.lower():
        return sys.executable
    # registry InstallPath (HKCU then HKLM)
    try:
        import winreg
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(root, r"SOFTWARE\Python\PythonCore") as pc:
                    i = 0
                    while True:
                        ver = winreg.EnumKey(pc, i); i += 1
                        try:
                            with winreg.OpenKey(pc, ver + r"\InstallPath") as ip:
                                base = winreg.QueryValueEx(ip, "")[0]
                                exe = os.path.join(base, "python.exe")
                                if works(exe):
                                    return exe
                        except OSError:
                            continue
            except OSError:
                continue
    except (ImportError, OSError):
        pass
    for name in ("python.exe", "python3.exe"):
        cand = shutil.which(name)
        if works(cand) and "windowsapps" not in (cand or "").lower():
            return cand
    return sys.executable  # last resort


# --------------------------------------------------------------------------- #
# MO2 auto-detection: find the instance whose managed game == this FNV folder
# --------------------------------------------------------------------------- #
def _read_ini(path):
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, OSError):
        try:
            cp.read(path, encoding="utf-8-sig")
        except (configparser.Error, OSError):
            return None
    return cp


def _norm(p):
    return os.path.normcase(os.path.normpath(p)) if p else p


def _unbytearray(val):
    """Decode an MO2 ini value: strip quotes and the @ByteArray(...) wrapper, and
    collapse the doubled backslashes MO2 writes (D:\\\\SteamLibrary -> D:\\SteamLibrary)."""
    if val is None:
        return ""
    val = val.strip().strip('"')
    if val.startswith("@ByteArray(") and val.endswith(")"):
        val = val[len("@ByteArray("):-1]
    elif val.startswith("ByteArray(") and val.endswith(")"):
        val = val[len("ByteArray("):-1]
    return val.replace("\\\\", "\\")


def detect_mo2_instances(game_root, userhome, explicit_instance):
    """Return a list of {instance, profile, mods} dicts -- every MO2 instance whose
    managed game resolves to this FNV install. Multiple instances can point at the same
    game folder (e.g. separate DUST / NVMP / TTW setups), so the caller disambiguates.
    """
    ini_candidates = []
    if explicit_instance:
        ini_candidates.append(os.path.join(explicit_instance, "ModOrganizer.ini"))
    localappdata = os.environ.get("LOCALAPPDATA", os.path.join(userhome, "AppData", "Local"))
    ini_candidates += glob.glob(os.path.join(localappdata, "ModOrganizer", "*", "ModOrganizer.ini"))
    for base in (r"C:\\", r"D:\\", r"E:\\", os.path.dirname(game_root)):
        ini_candidates += glob.glob(os.path.join(base, "*", "ModOrganizer.ini"))
        ini_candidates += glob.glob(os.path.join(base, "*", "*", "ModOrganizer.ini"))

    target = _norm(game_root)
    matches, seen = [], set()
    for ini in ini_candidates:
        ini = os.path.abspath(ini)
        if ini in seen or not os.path.isfile(ini):
            continue
        seen.add(ini)
        cp = _read_ini(ini)
        if not cp or not cp.has_section("General"):
            continue
        gen = cp["General"]
        gamepath = _unbytearray(gen.get("gamePath", ""))
        if not gamepath or _norm(gamepath) != target:
            continue
        instance_dir = os.path.dirname(ini)
        base_dir = _unbytearray(gen.get("base_directory", "")) or instance_dir
        profile = _unbytearray(gen.get("selected_profile", "")) or None
        matches.append({
            "instance": os.path.abspath(base_dir),
            "ini_dir": instance_dir,
            "profile": profile,
            "mods": os.path.abspath(os.path.join(base_dir, "mods")),
        })
    return matches


def resolve_mo2(game_root, userhome, explicit_instance):
    """Pick a single MO2 instance. Returns (match_dict_or_None, all_matches).

    Uses the explicit instance if given; else auto-uses the sole match; else returns
    None with the full list so the caller can present the choice.
    """
    matches = detect_mo2_instances(game_root, userhome, explicit_instance)
    if explicit_instance:
        want = _norm(explicit_instance)
        for m in matches:
            if _norm(m["instance"]) == want or _norm(m["ini_dir"]) == want:
                return m, matches
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def find_mo2_plugins_dir(instance_dir, userhome):
    """MO2 plugins live next to ModOrganizer.exe. For a portable instance that is the
    instance dir; for a global instance it is the MO2 program install dir. Best-effort."""
    if instance_dir and os.path.isfile(os.path.join(instance_dir, "ModOrganizer.exe")):
        return os.path.join(instance_dir, "plugins")
    # global: search for the program dir
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 userhome):
        for cand in glob.glob(os.path.join(base, "**", "ModOrganizer.exe"), recursive=False):
            return os.path.join(os.path.dirname(cand), "plugins")
    return None


# --------------------------------------------------------------------------- #
# TOML helpers (write MCP servers + project trust into ~/.codex/config.toml)
# --------------------------------------------------------------------------- #
def _toml_val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_val(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join('"%s" = %s' % (k, _toml_val(x)) for k, x in v.items()) + " }"
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % s


def _toml_table(header, table):
    lines = ["[%s]" % header]
    for k, v in table.items():
        lines.append("%s = %s" % (k, _toml_val(v)))
    return "\n".join(lines) + "\n"


def upsert_toml_table(path, header, table):
    """Insert or replace a single [header] table in a TOML file, preserving the rest of
    the file (text-based -- no full re-serialization, so comments/formatting survive)."""
    block = _toml_table(header, table)
    text = ""
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    # match the header line through to just before the next top-level table or EOF
    pat = re.compile(r'(?ms)^[ \t]*' + re.escape("[" + header + "]") + r'[ \t]*$.*?(?=^[ \t]*\[|\Z)')
    if pat.search(text):
        text = pat.sub(lambda _m: block, text, count=1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        if text:
            text += "\n"
        text += block
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".yesman-tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def set_codex_trust(codex_config, game_root):
    """Mark the game folder as a trusted Codex project so project-scoped .codex/ config,
    hooks, and skills load. Append-if-missing to avoid disturbing existing trust."""
    esc = game_root.replace("\\", "\\\\")
    marker = 'projects."%s"' % esc
    existing = ""
    if os.path.isfile(codex_config):
        with open(codex_config, "r", encoding="utf-8") as f:
            existing = f.read()
    if marker in existing or ('projects."%s"' % game_root) in existing:
        log("Codex project trust already set.")
        return
    upsert_toml_table(codex_config, marker, {"trust_level": "trusted"})
    log("marked project trusted in %s" % codex_config)


# --------------------------------------------------------------------------- #
# MO2 plugin + Live Link (shared) deploys
# --------------------------------------------------------------------------- #
def deploy_mo2_plugin(plugins_dir):
    if not plugins_dir:
        log("MO2 plugins folder not resolved -- skipping MO2 MCP deploy. "
            "Re-run with --mo2-instance \"<MO2 folder>\" to install it.")
        return False
    if not os.path.isdir(MO2_PLUGIN_SRC):
        log("MO2 plugin source missing (%s) -- skipping." % MO2_PLUGIN_SRC)
        return False
    os.makedirs(plugins_dir, exist_ok=True)
    dest = os.path.join(plugins_dir, "fnv_mo2_mcp")
    if os.path.isdir(dest):
        log("Updating existing MO2 plugin (settings preserved): %s" % dest)
    shutil.copytree(MO2_PLUGIN_SRC, dest, dirs_exist_ok=True)
    shutil.rmtree(os.path.join(dest, "__pycache__"), ignore_errors=True)
    log("MO2 MCP plugin -> %s" % dest)
    log("  (enable 'FNV MO2 MCP Server' in MO2 Settings->Plugins)")
    return True


def deploy_live_link_shared(game_root, mods_dir):
    """Seed the bridge dir and deploy the ln_ scripts (agent-agnostic). Returns the bridge
    dir, or None if the live-link source is missing. MCP registration is done per-agent."""
    if not os.path.isdir(LIVE_LINK_DIR):
        log("live-link source missing (%s) -- skipping." % LIVE_LINK_DIR)
        return None
    sys.path.insert(0, LIVE_LINK_DIR)
    try:
        import install as ll  # live-link/install.py
    except ImportError as e:
        log("could not import live-link installer (%s) -- skipping." % e)
        return None
    bridge_dir = ll.seed_bridge(game_root)
    deploy_mode = "mo2" if mods_dir and os.path.isdir(mods_dir) else "data"
    ll.deploy(types.SimpleNamespace(deploy=deploy_mode, mo2_mods=mods_dir), game_root)
    return bridge_dir


# --------------------------------------------------------------------------- #
# per-agent MCP registration
# --------------------------------------------------------------------------- #
def register_claude_mcp(bridge_dir, python_exe, no_mcp):
    """Claude: fnv-link via live-link/install.py (~/.claude.json). The mo2 server
    self-registers into ~/.claude.json when MO2 starts the plugin."""
    if no_mcp or not bridge_dir:
        return
    sys.path.insert(0, LIVE_LINK_DIR)
    try:
        import install as ll
        ll.register_mcp(bridge_dir, python_exe)
    except ImportError as e:
        log("fnv-link registration skipped (%s)" % e)


def register_codex_mcp(game_root, bridge_dir, python_exe, include_mo2, no_mcp):
    """Codex: write fnv-link (stdio) + mo2 (http) into ~/.codex/config.toml, and mark the
    project trusted. Unlike Claude, the MO2 plugin does not (yet) self-register into TOML,
    so we write the mo2 entry here using the default port."""
    if no_mcp:
        return
    cfg = os.path.expanduser("~/.codex/config.toml")
    if bridge_dir:
        upsert_toml_table(cfg, "mcp_servers.fnv-link", {
            "command": python_exe,
            "args": ["-m", "fnv_link_server", "--bridge", bridge_dir],
            "cwd": LIVE_LINK_DIR,
            "env": {"PYTHONPATH": LIVE_LINK_DIR},
        })
        log("registered 'fnv-link' (stdio) in %s" % cfg)
    if include_mo2:
        upsert_toml_table(cfg, "mcp_servers.mo2", {
            "url": "http://127.0.0.1:%d/mcp" % MO2_DEFAULT_PORT,
        })
        log("registered 'mo2' (http :%d) in %s" % (MO2_DEFAULT_PORT, cfg))
    set_codex_trust(cfg, game_root)


# --------------------------------------------------------------------------- #
# per-agent file config (instruction file + hooks + skills + placeholders)
# --------------------------------------------------------------------------- #
def _placeholder_map(game_root, jq, docs, username, mo2_instance, mo2_profile):
    m = {"{{GAME_ROOT}}": game_root, "{{USERNAME}}": username,
         "{{DOCUMENTS_DIR}}": docs, "{{JQ_PATH}}": jq}
    if mo2_instance:
        m["{{MO2_INSTANCE}}"] = mo2_instance
    if mo2_profile:
        m["{{MO2_PROFILE}}"] = mo2_profile
    return m


def configure_claude_files(game_root, jq, docs, username, mo2_instance, mo2_profile):
    section("Configuring Claude Code files (CLAUDE.md, .claude/hooks, .claude/skills)...")
    mapping = _placeholder_map(game_root, jq, docs, username, mo2_instance, mo2_profile)
    _fill_placeholders(os.path.join(game_root, "CLAUDE.md"), mapping)
    for hook in ("protect-bash.sh", "protect-files.sh", "backup-before-edit.sh"):
        _fill_placeholders(os.path.join(game_root, ".claude", "hooks", hook), mapping)
    os.makedirs(os.path.join(game_root, ".claude", "backups"), exist_ok=True)
    log("CLAUDE.md + hooks configured; skills already at .claude/skills/.")


def deploy_codex_files(game_root, jq, docs, username, mo2_instance, mo2_profile):
    section("Deploying Codex files (AGENTS.md, .codex/hooks, .agents/skills)...")
    if not os.path.isdir(CODEX_SRC):
        log("codex/ source missing (%s) -- skipping Codex deploy." % CODEX_SRC)
        return
    # AGENTS.md -> game root
    shutil.copy2(os.path.join(CODEX_SRC, "AGENTS.md"), os.path.join(game_root, "AGENTS.md"))
    # hooks -> .codex/hooks + .codex/hooks.json
    hooks_dst = os.path.join(game_root, ".codex", "hooks")
    os.makedirs(hooks_dst, exist_ok=True)
    for fn in ("protect-bash.sh", "protect-files.sh", "backup-before-edit.sh"):
        shutil.copy2(os.path.join(CODEX_SRC, "hooks", fn), os.path.join(hooks_dst, fn))
    shutil.copy2(os.path.join(CODEX_SRC, "hooks", "hooks.json"),
                 os.path.join(game_root, ".codex", "hooks.json"))
    # skills -> .agents/skills (the shared, agent-neutral set)
    skills_dst = os.path.join(game_root, ".agents", "skills")
    if os.path.isdir(SKILLS_SRC):
        for name in os.listdir(SKILLS_SRC):
            s = os.path.join(SKILLS_SRC, name)
            if os.path.isdir(s):
                shutil.copytree(s, os.path.join(skills_dst, name), dirs_exist_ok=True)
    # fill placeholders in AGENTS.md, the .codex hooks, and hooks.json
    mapping = _placeholder_map(game_root, jq, docs, username, mo2_instance, mo2_profile)
    _fill_placeholders(os.path.join(game_root, "AGENTS.md"), mapping)
    for fn in ("protect-bash.sh", "protect-files.sh", "backup-before-edit.sh"):
        _fill_placeholders(os.path.join(hooks_dst, fn), mapping)
    _fill_placeholders(os.path.join(game_root, ".codex", "hooks.json"), mapping)
    os.makedirs(os.path.join(game_root, ".codex", "backups"), exist_ok=True)
    log("AGENTS.md + .codex/hooks + .agents/skills deployed and configured.")


# --------------------------------------------------------------------------- #
# uninstall
# --------------------------------------------------------------------------- #
def _pop_json_mcp(cfg, key):
    if not os.path.isfile(cfg):
        return
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("mcpServers", {}).pop(key, None) is not None:
            tmp = cfg + ".yesman-tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2); f.write("\n")
            os.replace(tmp, cfg)
            log("removed '%s' from %s" % (key, cfg))
    except (ValueError, OSError) as e:
        log("could not edit %s: %s" % (cfg, e))


def _pop_toml_mcp(cfg, header):
    if not os.path.isfile(cfg):
        return
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            text = f.read()
        pat = re.compile(r'(?ms)^[ \t]*' + re.escape("[" + header + "]") + r'[ \t]*$.*?(?=^[ \t]*\[|\Z)')
        if pat.search(text):
            tmp = cfg + ".yesman-tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(pat.sub("", text, count=1))
            os.replace(tmp, cfg)
            log("removed '[%s]' from %s" % (header, cfg))
    except OSError as e:
        log("could not edit %s: %s" % (cfg, e))


def uninstall(game_root, mo2_instance, userhome):
    section("Uninstalling YesMan AI components...")
    m, _ = resolve_mo2(game_root, userhome, mo2_instance)
    if os.path.isdir(LIVE_LINK_DIR):
        sys.path.insert(0, LIVE_LINK_DIR)
        try:
            import install as ll
            mods_dir = m["mods"] if m else None
            ll.uninstall(types.SimpleNamespace(mo2_mods=mods_dir), game_root)  # removes fnv-link from ~/.claude.json
        except ImportError as e:
            log("live-link uninstall skipped (%s)" % e)
    # MO2 plugin
    ini_dir = m["ini_dir"] if m else None
    plugins_dir = find_mo2_plugins_dir(ini_dir, userhome) if ini_dir else None
    if plugins_dir:
        dest = os.path.join(plugins_dir, "fnv_mo2_mcp")
        if os.path.isdir(dest):
            shutil.rmtree(dest, ignore_errors=True)
            log("removed MO2 plugin: %s" % dest)
    # MCP registrations (both agents)
    _pop_json_mcp(os.path.expanduser("~/.claude.json"), "mo2")
    codex_cfg = os.path.expanduser("~/.codex/config.toml")
    _pop_toml_mcp(codex_cfg, "mcp_servers.mo2")
    _pop_toml_mcp(codex_cfg, "mcp_servers.fnv-link")
    log("core toolbox files left in the game folder (uninstall via the .exe / delete manually).")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None):
    p = argparse.ArgumentParser(description="YesMan AI unified configurator")
    p.add_argument("--game-root", help="FNV install dir (auto-detected if omitted)")
    p.add_argument("--agent", choices=["claude", "codex", "both"], default="claude",
                   help="which AI coding agent to wire up (default: claude)")
    p.add_argument("--mo2-instance", help="MO2 instance/base folder (auto-detected if omitted)")
    p.add_argument("--mo2-mods", help="MO2 mods dir (auto-detected from the instance if omitted)")
    p.add_argument("--python", help="real python.exe for the live-link MCP server (auto-detected)")
    p.add_argument("--skip-mo2", action="store_true", help="do not deploy the MO2 MCP plugin")
    p.add_argument("--no-mo2", action="store_true",
                   help="user has no MO2: skip the MO2 plugin and deploy the live link into Data")
    p.add_argument("--skip-live-link", action="store_true", help="do not deploy the YesMan AI Live Link")
    p.add_argument("--no-mcp", action="store_true", help="do not touch agent MCP config files")
    p.add_argument("--uninstall", action="store_true")
    args = p.parse_args(argv)

    agents = {"claude", "codex"} if args.agent == "both" else {args.agent}

    userhome = (os.environ.get("USERPROFILE") or os.path.expanduser("~")).replace("\\", "/")
    username = os.environ.get("USERNAME") or os.path.basename(userhome)

    game_root = find_game_root(args.game_root)
    if not game_root:
        sys.exit("ERROR: Fallout New Vegas (FalloutNV.exe) not found. Pass --game-root.")

    print("=" * 60)
    print(" YesMan AI - A FNV Modding Toolbox -- %s (agent: %s)"
          % (("uninstall" if args.uninstall else "setup"), args.agent))
    print("=" * 60)
    log("game root: %s" % game_root)

    if args.uninstall:
        uninstall(game_root, args.mo2_instance, userhome)
        print("\nDone.")
        return

    # sanity: the toolbox must be present in the game folder
    have_claude = os.path.isfile(os.path.join(game_root, "CLAUDE.md"))
    have_codex = os.path.isdir(CODEX_SRC)
    if "claude" in agents and not have_claude:
        sys.exit("ERROR: CLAUDE.md not found in the game folder. Did the installer copy the toolbox?")
    if "codex" in agents and not have_codex:
        sys.exit("ERROR: codex/ not found in the toolbox. Did the installer copy it?")

    # 1. shared detection
    section("Detecting prerequisites...")
    jq = detect_jq(userhome)
    if jq:
        log("jq: %s" % jq)
    else:
        log("jq not found -- the safety hooks need it. Install: winget install jqlang.jq")
        jq = "jq"  # fall back to PATH lookup at hook runtime
    docs = detect_documents(userhome)
    log("documents: %s" % docs)
    section("Installing the xEditLib ESP backbone...")
    run_npm_install(game_root)

    # 2. MO2 detection
    section("Detecting Mod Organizer 2...")
    if args.no_mo2:
        mo2, matches = None, []
        log("--no-mo2: skipping MO2 components; the live link will deploy into Data.")
    else:
        mo2, matches = resolve_mo2(game_root, userhome, args.mo2_instance)
    if mo2 is None and len(matches) > 1:
        log("multiple MO2 instances manage this game folder -- pass one via --mo2-instance:")
        for m in matches:
            log("  --mo2-instance \"%s\"   (profile: %s)" % (m["ini_dir"], m["profile"] or "?"))
        log("MO2-dependent steps are skipped until you choose one.")
    mo2_instance = mo2["instance"] if mo2 else None
    mo2_ini_dir = mo2["ini_dir"] if mo2 else None
    mo2_profile = mo2["profile"] if mo2 else None
    mo2_mods = args.mo2_mods or (mo2["mods"] if mo2 else None)
    if mo2_instance:
        log("MO2 instance: %s" % mo2_instance)
        log("MO2 profile:  %s" % (mo2_profile or "(not resolved)"))
        log("MO2 mods:     %s" % (mo2_mods or "(not resolved)"))
    elif not matches:
        log("no MO2 instance managing this game folder was found (Vortex/manual, or pass --mo2-instance).")

    # 3. per-agent file config (instruction file + hooks + skills + placeholders)
    if "claude" in agents:
        configure_claude_files(game_root, jq, docs, username, mo2_instance, mo2_profile)
    if "codex" in agents:
        deploy_codex_files(game_root, jq, docs, username, mo2_instance, mo2_profile)

    # 4. MO2 MCP plugin (shared)
    section("Deploying the MO2 MCP plugin...")
    if args.skip_mo2:
        log("skipped (--skip-mo2).")
    elif not mo2_instance:
        log("no chosen MO2 instance -- skipping MO2 MCP deploy.")
    else:
        deploy_mo2_plugin(find_mo2_plugins_dir(mo2_ini_dir, userhome))

    # 5. Live Link (shared deploy) + per-agent MCP registration
    section("Deploying the YesMan AI Live Link + registering MCP servers...")
    bridge_dir = None
    if args.skip_live_link:
        log("live link skipped (--skip-live-link).")
    else:
        bridge_dir = deploy_live_link_shared(game_root, mo2_mods)
    python_exe = detect_real_python(args.python)
    log("python for relay: %s" % python_exe)
    include_mo2 = bool(mo2_instance) and not args.skip_mo2
    if "claude" in agents:
        register_claude_mcp(bridge_dir, python_exe, args.no_mcp)
    if "codex" in agents:
        register_codex_mcp(game_root, bridge_dir, python_exe, include_mo2, args.no_mcp)

    # summary
    print("\n" + "=" * 60)
    print(" Setup complete.")
    print("=" * 60)
    print("Next steps:")
    if "claude" in agents:
        print("  - Restart Claude Code so it picks up the MCP servers.")
    if "codex" in agents:
        print("  - Restart Codex so it picks up ~/.codex/config.toml (MCP servers + project trust).")
    print("  - If you use MO2: enable 'FNV MO2 MCP Server' and the 'YesMan AI Live Link' mod, restart MO2.")
    print("  - Live Link needs the NVSE stack incl. JIP PP LN -- see live-link/README.md.")
    print("  - Open your agent in the game folder and start modding.")


if __name__ == "__main__":
    main()

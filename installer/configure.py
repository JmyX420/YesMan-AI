#!/usr/bin/env python3
r"""YesMan AI - A FNV Modding Toolbox for Claude -- unified configurator.

One idempotent flow that replaces the three legacy installers (setup.sh,
mo2-mcp/install-to-mo2.sh, live-link/install.py). It is invoked by the Inno Setup
installer AFTER it copies the toolbox files into the Fallout: New Vegas game folder,
and can also be run standalone for testing / re-configuration.

What it does (safe to re-run):
  1. Validates the FNV install (FalloutNV.exe) and fills the deterministic
     placeholders in CLAUDE.md and the safety hooks (game root, user, docs, jq).
  2. Auto-detects the Mod Organizer 2 instance + active profile that manages this
     game folder and fills {{MO2_INSTANCE}} / {{MO2_PROFILE}}.
  3. Installs the Node xEditLib backbone (npm install).
  4. Deploys the bundled MO2 MCP plugin into <MO2>/plugins/ (it self-registers with
     Claude Code at MO2 startup; automod-path auto-detects the toolbox in the game folder).
  5. Deploys the YesMan AI Live Link (seeds <game>\FNVLink\, deploys the ln_ scripts as an
     MO2 mod, registers the "fnv-link" stdio MCP server in ~/.claude.json).

All three components are installed together -- they are no longer optional add-ons.
At RUNTIME the toolbox still degrades gracefully (skills fall back to the AutoMod CLI
when MO2 or the game is not running); "bundled" means "always installed", not
"always running".

Usage (normally the .exe passes these):
  python configure.py --game-root "<FNV folder>"
  python configure.py --game-root "<FNV folder>" --mo2-instance "<MO2 folder>" \
                      --mo2-mods "<MO2 mods dir>" --python "<real python.exe>"
  python configure.py --game-root "<FNV folder>" --uninstall
"""

import argparse
import configparser
import glob
import json
import os
import shutil
import subprocess
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLBOX_ROOT = os.path.dirname(HERE)  # the game folder once installed; dev repo when testing
LIVE_LINK_DIR = os.path.join(TOOLBOX_ROOT, "live-link")
MO2_PLUGIN_SRC = os.path.join(TOOLBOX_ROOT, "mo2-mcp", "fnv_mo2_mcp")


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
# component deploys
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
    log("  (enable 'FNV MO2 MCP Server' in MO2 Settings->Plugins; it self-registers with Claude Code)")
    return True


def deploy_live_link(game_root, mods_dir, python_exe, no_mcp):
    """Reuse the tested live-link installer functions."""
    if not os.path.isdir(LIVE_LINK_DIR):
        log("live-link source missing (%s) -- skipping." % LIVE_LINK_DIR)
        return False
    sys.path.insert(0, LIVE_LINK_DIR)
    try:
        import install as ll  # live-link/install.py
    except ImportError as e:
        log("could not import live-link installer (%s) -- skipping." % e)
        return False
    bridge_dir = ll.seed_bridge(game_root)
    deploy_mode = "mo2" if mods_dir and os.path.isdir(mods_dir) else "data"
    args = types.SimpleNamespace(deploy=deploy_mode, mo2_mods=mods_dir)
    ll.deploy(args, game_root)
    if not no_mcp:
        ll.register_mcp(bridge_dir, python_exe)
    return True


# --------------------------------------------------------------------------- #
# core wiring (placeholders, jq, docs, node)
# --------------------------------------------------------------------------- #
def configure_core(game_root, userhome, username):
    section("Configuring core toolbox...")
    # jq
    jq = detect_jq(userhome)
    if jq:
        log("jq: %s" % jq)
    else:
        log("jq not found -- the safety hooks need it. Install: winget install jqlang.jq")
        jq = "jq"  # fall back to PATH lookup at hook runtime
    for hook in ("protect-bash.sh", "protect-files.sh", "backup-before-edit.sh"):
        if _fill_placeholders(os.path.join(game_root, ".claude", "hooks", hook), {"{{JQ_PATH}}": jq}):
            log("configured .claude/hooks/%s" % hook)
    docs = detect_documents(userhome)
    log("documents: %s" % docs)
    changed = _fill_placeholders(os.path.join(game_root, "CLAUDE.md"), {
        "{{GAME_ROOT}}": game_root,
        "{{USERNAME}}": username,
        "{{DOCUMENTS_DIR}}": docs,
    })
    log("CLAUDE.md game/user/docs paths %s" % ("filled" if changed else "already set"))
    section("Installing the xEditLib ESP backbone...")
    run_npm_install(game_root)
    os.makedirs(os.path.join(game_root, ".claude", "backups"), exist_ok=True)


def configure_mo2_paths(game_root, userhome, mo2_instance, mo2_profile):
    if not mo2_instance:
        log("MO2 instance not resolved -- leaving {{MO2_INSTANCE}}/{{MO2_PROFILE}} for later. "
            "(Pass --mo2-instance, or Claude can fill them from ModOrganizer.ini.)")
        return
    mapping = {"{{MO2_INSTANCE}}": mo2_instance}
    if mo2_profile:
        mapping["{{MO2_PROFILE}}"] = mo2_profile
    for rel in ("CLAUDE.md", ".claude/hooks/protect-bash.sh",
                ".claude/hooks/protect-files.sh", ".claude/hooks/backup-before-edit.sh"):
        if _fill_placeholders(os.path.join(game_root, rel), mapping):
            log("filled MO2 paths in %s" % rel)


# --------------------------------------------------------------------------- #
# uninstall
# --------------------------------------------------------------------------- #
def uninstall(game_root, mo2_instance, userhome):
    section("Uninstalling YesMan AI components...")
    # live-link MCP + mod (reuse its uninstaller)
    m, _ = resolve_mo2(game_root, userhome, mo2_instance)
    if os.path.isdir(LIVE_LINK_DIR):
        sys.path.insert(0, LIVE_LINK_DIR)
        try:
            import install as ll
            mods_dir = m["mods"] if m else None
            ll.uninstall(types.SimpleNamespace(mo2_mods=mods_dir), game_root)
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
    # mo2 MCP registration
    cfg = os.path.expanduser("~/.claude.json")
    if os.path.isfile(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("mcpServers", {}).pop("mo2", None) is not None:
                tmp = cfg + ".yesman-tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2); f.write("\n")
                os.replace(tmp, cfg)
                log("removed 'mo2' MCP registration")
        except (ValueError, OSError) as e:
            log("could not edit ~/.claude.json: %s" % e)
    log("core toolbox files left in the game folder (uninstall via the .exe / delete manually).")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None):
    p = argparse.ArgumentParser(description="YesMan AI unified configurator")
    p.add_argument("--game-root", help="FNV install dir (auto-detected if omitted)")
    p.add_argument("--mo2-instance", help="MO2 instance/base folder (auto-detected if omitted)")
    p.add_argument("--mo2-mods", help="MO2 mods dir (auto-detected from the instance if omitted)")
    p.add_argument("--python", help="real python.exe for the live-link MCP server (auto-detected)")
    p.add_argument("--skip-mo2", action="store_true", help="do not deploy the MO2 MCP plugin")
    p.add_argument("--no-mo2", action="store_true",
                   help="user has no MO2: skip the MO2 plugin and deploy the live link into Data")
    p.add_argument("--skip-live-link", action="store_true", help="do not deploy the YesMan AI Live Link")
    p.add_argument("--no-mcp", action="store_true", help="do not touch ~/.claude.json")
    p.add_argument("--uninstall", action="store_true")
    args = p.parse_args(argv)

    userhome = (os.environ.get("USERPROFILE") or os.path.expanduser("~")).replace("\\", "/")
    username = os.environ.get("USERNAME") or os.path.basename(userhome)

    game_root = find_game_root(args.game_root)
    if not game_root:
        sys.exit("ERROR: Fallout New Vegas (FalloutNV.exe) not found. Pass --game-root.")

    print("=" * 60)
    print(" YesMan AI - A FNV Modding Toolbox for Claude -- %s"
          % ("uninstall" if args.uninstall else "setup"))
    print("=" * 60)
    log("game root: %s" % game_root)

    if args.uninstall:
        uninstall(game_root, args.mo2_instance, userhome)
        print("\nDone.")
        return

    if not os.path.isfile(os.path.join(game_root, "CLAUDE.md")):
        sys.exit("ERROR: toolbox files not found in the game folder. Did the installer copy them?")

    # 1. core
    configure_core(game_root, userhome, username)

    # 2. MO2 detection + paths
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
    configure_mo2_paths(game_root, userhome, mo2_instance, mo2_profile)

    # 3. MO2 MCP plugin
    section("Deploying the MO2 MCP plugin...")
    if args.skip_mo2:
        log("skipped (--skip-mo2).")
    elif not mo2_instance:
        log("no chosen MO2 instance -- skipping MO2 MCP deploy.")
    else:
        plugins_dir = find_mo2_plugins_dir(mo2_ini_dir, userhome)
        deploy_mo2_plugin(plugins_dir)

    # 4. Live Link
    section("Deploying the YesMan AI Live Link...")
    if args.skip_live_link:
        log("skipped (--skip-live-link).")
    else:
        python_exe = detect_real_python(args.python)
        log("python for relay: %s" % python_exe)
        deploy_live_link(game_root, mo2_mods, python_exe, args.no_mcp)

    # summary
    print("\n" + "=" * 60)
    print(" Setup complete.")
    print("=" * 60)
    print("Next steps:")
    print("  1. Restart Claude Code so it picks up the MCP servers.")
    print("  2. If you use MO2: enable 'FNV MO2 MCP Server' and the 'YesMan AI Live Link'")
    print("     mod, then restart MO2.")
    print("  3. Live Link needs the NVSE stack incl. JIP PP LN -- see live-link/README.md.")
    print("  4. Open Claude Code in the game folder and start modding.")


if __name__ == "__main__":
    main()

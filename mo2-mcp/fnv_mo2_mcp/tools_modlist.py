"""MCP tools for querying MO2 mod and plugin lists.

Pure mobase — game-agnostic, ported verbatim from upstream apart from FNV example
names. (FNV has no light/ESL plugins; isLightFlagged() simply reports False.)
"""

import json
import os

import mobase

from .config import PLUGIN_NAME


def scan_missing_masters(plugin_list) -> dict:
    """Return {plugin_name: [missing_master, ...]} for every enabled plugin
    that has at least one missing master. Matches MO2's PluginList::testMasters()
    exactly — a declared master is "missing" when it is not ACTIVE (i.e. either
    absent from the list entirely, or present but disabled). Both cases break
    the game at load time.

    Fresh every call: no caching. Cost is a single pluginNames() walk plus one
    state() + masters() lookup per enabled plugin — cheap, runs in MO2 memory.
    """
    problems = {}
    for name in plugin_list.pluginNames():
        if plugin_list.state(name) != mobase.PluginState.ACTIVE:
            continue
        missing = [
            m for m in plugin_list.masters(name)
            if plugin_list.state(m) != mobase.PluginState.ACTIVE
        ]
        if missing:
            problems[name] = missing
    return problems


def register_modlist_tools(registry, organizer: mobase.IOrganizer):
    """Register all mod/plugin query tools with the MCP tool registry."""

    mod_list = organizer.modList()
    plugin_list = organizer.pluginList()

    # ── mo2_list_mods ────────────────────────────────────────────────

    registry.register(
        name="mo2_list_mods",
        description=(
            "List all mods with their state and priority. "
            "Supports filtering by name substring. "
            "Returns name, priority, enabled state, version, and category."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Name substring filter (case-insensitive)",
                },
                "enabled_only": {
                    "type": "boolean",
                    "description": "Only show enabled mods (default true)",
                    "default": True,
                },
                "offset": {
                    "type": "integer",
                    "description": "Skip this many results (for pagination)",
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 100)",
                    "default": 100,
                },
            },
        },
        handler=lambda args: _list_mods(mod_list, args),
    )

    # ── mo2_mod_info ─────────────────────────────────────────────────

    registry.register(
        name="mo2_mod_info",
        description=(
            "Get detailed information about a specific mod including "
            "version, Nexus ID, categories, notes, and file count."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Mod name as shown in MO2",
                },
            },
            "required": ["name"],
        },
        handler=lambda args: _mod_info(mod_list, args),
    )

    # ── mo2_list_plugins ─────────────────────────────────────────────

    registry.register(
        name="mo2_list_plugins",
        description=(
            "List all plugins in load order. "
            "Supports filtering by name substring. "
            "Returns name, load order, enabled state, master flag, and providing mod."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "description": "Name substring filter (case-insensitive)",
                },
                "enabled_only": {
                    "type": "boolean",
                    "description": "Only show enabled plugins (default true)",
                    "default": True,
                },
                "offset": {
                    "type": "integer",
                    "description": "Skip this many results (for pagination)",
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 100)",
                    "default": 100,
                },
            },
        },
        handler=lambda args: _list_plugins(plugin_list, args),
    )

    # ── mo2_plugin_info ──────────────────────────────────────────────

    registry.register(
        name="mo2_plugin_info",
        description=(
            "Get detailed info about a specific plugin including its "
            "master chain (with any missing masters flagged), load "
            "order, flags, author, and description."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Plugin filename (e.g. 'DeadMoney.esm')",
                },
            },
            "required": ["name"],
        },
        handler=lambda args: _plugin_info(plugin_list, args),
    )

    # ── mo2_find_conflicts ───────────────────────────────────────────

    registry.register(
        name="mo2_find_conflicts",
        description=(
            "Find all file-level conflicts for a mod (overwrites and overwritten-by). "
            "Takes a mod folder name from MO2's left pane, not a plugin filename. "
            "Limited to first 200 conflicts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "mod_name": {
                    "type": "string",
                    "description": (
                        "Mod folder name as shown in MO2's left pane "
                        "(e.g. 'YUP - Base Game and All DLC'), NOT a plugin filename. "
                        "Use mo2_list_mods to find the correct name."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max conflicts to return (default 200)",
                    "default": 200,
                },
            },
            "required": ["mod_name"],
        },
        handler=lambda args: _find_conflicts(organizer, mod_list, args),
    )


# ── Tool implementations ─────────────────────────────────────────────


def _is_active_mod(mod_list, name: str) -> bool:
    state = mod_list.state(name)
    return bool(state & mobase.ModState.ACTIVE)


def _list_mods(mod_list, args: dict) -> str:
    name_filter = args.get("filter", "").lower()
    enabled_only = args.get("enabled_only", True)
    offset = int(args.get("offset", 0))
    limit = int(args.get("limit", 100))

    all_mods = mod_list.allMods()
    results = []

    for mod_name in all_mods:
        active = _is_active_mod(mod_list, mod_name)
        if enabled_only and not active:
            continue
        if name_filter and name_filter not in mod_name.lower():
            continue

        mod = mod_list.getMod(mod_name)
        entry = {
            "name": mod_name,
            "priority": mod_list.priority(mod_name),
            "enabled": active,
        }
        if mod:
            ver = mod.version()
            if ver and ver.isValid():
                entry["version"] = str(ver)
            cats = mod.categories()
            if cats:
                entry["categories"] = list(cats)
        results.append(entry)

    # Sort by priority
    results.sort(key=lambda m: m.get("priority", -1))

    total = len(results)
    page = results[offset : offset + limit]

    output = {
        "total": total,
        "offset": offset,
        "limit": limit,
        "mods": page,
    }
    return json.dumps(output, indent=2)


def _mod_info(mod_list, args: dict) -> str:
    name = args.get("name", "")
    mod = mod_list.getMod(name)
    if not mod:
        return json.dumps({"error": f"Mod not found: {name}"})

    state = mod_list.state(name)
    info = {
        "name": name,
        "priority": mod_list.priority(name),
        "enabled": bool(state & mobase.ModState.ACTIVE),
        "version": str(mod.version()) if mod.version() and mod.version().isValid() else None,
        "nexus_id": mod.nexusId() if mod.nexusId() > 0 else None,
        "categories": list(mod.categories()) if mod.categories() else [],
        "path": mod.absolutePath(),
        "is_separator": mod.isSeparator(),
    }
    # These attributes may not exist in all MO2 versions
    for attr in ("author", "notes", "url"):
        if hasattr(mod, attr):
            val = getattr(mod, attr)()
            if val:
                info[attr] = val
    # Count files in the mod directory
    try:
        file_count = sum(
            len(files) for _, _, files in os.walk(mod.absolutePath())
        )
        info["file_count"] = file_count
    except OSError:
        pass

    return json.dumps(info, indent=2)


def _list_plugins(plugin_list, args: dict) -> str:
    name_filter = args.get("filter", "").lower()
    enabled_only = args.get("enabled_only", True)
    offset = int(args.get("offset", 0))
    limit = int(args.get("limit", 100))

    all_plugins = plugin_list.pluginNames()
    results = []

    for plugin_name in all_plugins:
        state = plugin_list.state(plugin_name)
        active = (state == mobase.PluginState.ACTIVE)
        if enabled_only and not active:
            continue
        if name_filter and name_filter not in plugin_name.lower():
            continue

        entry = {
            "name": plugin_name,
            "load_order": plugin_list.loadOrder(plugin_name),
            "priority": plugin_list.priority(plugin_name),
            "enabled": active,
            "is_master": plugin_list.isMasterFlagged(plugin_name),
            "is_light": plugin_list.isLightFlagged(plugin_name),  # always False on FNV (no ESL)
            "providing_mod": plugin_list.origin(plugin_name),
        }
        results.append(entry)

    # Sort by load order
    results.sort(key=lambda p: p.get("load_order", -1))

    total = len(results)
    page = results[offset : offset + limit]

    output = {
        "total": total,
        "offset": offset,
        "limit": limit,
        "plugins": page,
    }
    return json.dumps(output, indent=2)


def _plugin_info(plugin_list, args: dict) -> str:
    name = args.get("name", "")
    state = plugin_list.state(name)

    if state == mobase.PluginState.MISSING:
        return json.dumps({"error": f"Plugin not found: {name}"})

    masters = list(plugin_list.masters(name))
    is_active = (state == mobase.PluginState.ACTIVE)

    # Matches MO2's PluginList::testMasters() exactly: for enabled plugins, a
    # declared master is "missing" if it's not also enabled. Covers both
    # absent-from-list and present-but-disabled cases.
    missing_masters = [
        m for m in masters
        if plugin_list.state(m) != mobase.PluginState.ACTIVE
    ] if is_active else []

    # Find plugins that depend on this one
    dependents = []
    for p in plugin_list.pluginNames():
        if plugin_list.state(p) == mobase.PluginState.MISSING:
            continue
        if name in plugin_list.masters(p):
            dependents.append(p)

    info = {
        "name": name,
        "load_order": plugin_list.loadOrder(name),
        "priority": plugin_list.priority(name),
        "enabled": is_active,
        "is_master": plugin_list.isMasterFlagged(name),
        "is_light": plugin_list.isLightFlagged(name),  # always False on FNV (no ESL)
        "masters": masters,
        "missing_masters": missing_masters,
        "dependent_plugins": dependents,
        "providing_mod": plugin_list.origin(name),
    }
    # author/description may not be available in all MO2 versions
    for attr in ("author", "description"):
        if hasattr(plugin_list, attr):
            val = getattr(plugin_list, attr)(name)
            if val:
                info[attr] = val
    return json.dumps(info, indent=2)


def _find_conflicts(organizer, mod_list, args: dict) -> str:
    mod_name = args.get("mod_name", "")
    limit = int(args.get("limit", 200))

    mod = mod_list.getMod(mod_name)
    if not mod:
        if any(mod_name.lower().endswith(ext) for ext in ('.esp', '.esm')):
            return json.dumps({
                "error": f"'{mod_name}' looks like a plugin filename. "
                         f"This tool takes mod folder names from MO2's left pane. "
                         f"Use mo2_list_mods or mo2_plugin_info to find the mod that provides this plugin."
            })
        return json.dumps({"error": f"Mod not found: {mod_name}"})

    mod_path = mod.absolutePath()
    mod_priority = mod_list.priority(mod_name)

    overwrites = []  # files this mod wins
    overwritten_by = []  # files this mod loses
    total_conflicts = 0

    # Walk the mod's directory and check each file's origins
    for dirpath, _, filenames in os.walk(mod_path):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            # Build game-relative path
            rel_path = os.path.relpath(full_path, mod_path).replace("\\", "/")

            # Get all mods that provide this file
            origins = organizer.getFileOrigins(rel_path)
            if not origins or len(origins) <= 1:
                continue  # no conflict

            total_conflicts += 1
            if total_conflicts > limit:
                continue  # count but don't collect

            # Origins are sorted by priority (highest first = winner)
            # Check if our mod is the winner
            if origins[0] == mod_name:
                losers = [o for o in origins[1:] if o != mod_name]
                if losers:
                    overwrites.append({"file": rel_path, "losers": losers})
            else:
                overwritten_by.append({
                    "file": rel_path,
                    "winner": origins[0],
                })

    output = {
        "mod": mod_name,
        "priority": mod_priority,
        "total_conflicts": total_conflicts,
        "truncated": total_conflicts > limit,
        "overwrites": overwrites,
        "overwritten_by": overwritten_by,
    }
    return json.dumps(output, indent=2)

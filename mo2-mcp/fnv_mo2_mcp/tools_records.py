"""MCP record-reading tools (Phase 2a), backed by the toolbox's AutoMod `esp`
module (xEditLib, GM_FNV=0) via the AutoMod bridge — NOT Mutagen (no FNV support).

Phase 2a = read-only record inspection of a single plugin:
- `mo2_query_records` — enumerate the records a plugin defines/overrides.
- `mo2_record_detail` — the full field tree of one record.

VFS problem & fix: the bridge's Node subprocess does NOT inherit MO2's usvfs, so
xEditLib only sees the real Data folder. Mod-folder plugins would be invisible. So we
**stage**: resolve the target plugin + its masters to real disk paths via the MO2 API
(thread-safe), hardlink them into a temp synthetic game dir's Data/ folder, and point xEditLib
there with `esp --game-dir`. Plain subprocess — no startApplication / main-thread needs.
"""

import json
import os
import shutil
import struct
import tempfile

import mobase
from PyQt6.QtCore import qWarning

from .config import PLUGIN_NAME
from .automod_bridge import run_automod

# Record reads load the plugin's full master chain — allow generous time.
_RECORD_TIMEOUT = 180


def register_record_tools(registry, organizer: mobase.IOrganizer) -> None:

    registry.register(
        name="mo2_query_records",
        description=(
            "List the records a plugin defines or overrides (FormID, signature, "
            "EditorID, name). Filter by record signature (e.g. WEAP, ARMO, NPC_) "
            "and/or a name/EditorID substring. Read-only. Backed by xEditLib."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "plugin_name": {"type": "string", "description": "Plugin filename, e.g. 'MyMod.esp' or 'FalloutNV.esm'."},
                "signature": {"type": "string", "description": "Record type to filter to, e.g. 'WEAP', 'ARMO', 'NPC_'. Omit for all types."},
                "match": {"type": "string", "description": "Case-insensitive substring matched against EditorID or name."},
                "limit": {"type": "integer", "description": "Max records to return (default 200).", "default": 200},
            },
            "required": ["plugin_name"],
        },
        handler=lambda args: _handle_query(organizer, args),
    )

    registry.register(
        name="mo2_record_detail",
        description=(
            "Return the full field tree of one record (all subrecords, resolved "
            "FormID references, names). Identify the record by its EditorID or its "
            "plugin-relative FormID hex. Read-only. Backed by xEditLib."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "plugin_name": {"type": "string", "description": "Plugin filename that defines/overrides the record."},
                "record_id": {"type": "string", "description": "EditorID (e.g. 'Weap10mmPistol') or plugin-relative FormID hex (e.g. '00434F')."},
            },
            "required": ["plugin_name", "record_id"],
        },
        handler=lambda args: _handle_detail(organizer, args),
    )

    registry.register(
        name="mo2_conflict_chain",
        description=(
            "Show the override/conflict chain for ONE record across the whole active "
            "load order: every plugin that defines or overrides it, in order, with the "
            "winner flagged. Read-only. Backed by xEditLib (loads the full load order)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "plugin_name": {"type": "string", "description": "A plugin that defines/overrides the record (often where you spotted it)."},
                "record_id": {"type": "string", "description": "EditorID or plugin-relative FormID hex."},
            },
            "required": ["plugin_name", "record_id"],
        },
        handler=lambda args: _handle_conflict_chain(organizer, args),
    )

    registry.register(
        name="mo2_plugin_conflicts",
        description=(
            "For a plugin, list the records it overrides and whether each WINS or is overridden "
            "by a later plugin (lost). Shows what the plugin actually changes vs what gets "
            "superseded. Read-only. Backed by xEditLib (loads the full active order)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "plugin_name": {"type": "string", "description": "Plugin filename to analyze."},
                "limit": {"type": "integer", "description": "Max 'lost' records to list (default 500).", "default": 500},
            },
            "required": ["plugin_name"],
        },
        handler=lambda args: _handle_plugin_conflicts(organizer, args),
    )

    registry.register(
        name="mo2_conflict_summary",
        description=(
            "Order-wide overview: every active plugin with its record count, how many records it "
            "overrides, and how many new records it adds — sorted by override count (conflict "
            "hotspots first). Read-only. Backed by xEditLib (loads the full active order)."
        ),
        input_schema={"type": "object", "properties": {}},
        handler=lambda args: _handle_conflict_summary(organizer, args),
    )

    registry.register(
        name="mo2_create_patch",
        description=(
            "Create a compatibility patch plugin that overrides ONE record (copy-as-override) "
            "and optionally edits its fields. DRY-RUN by default — pass write=true to actually "
            "create the .esp in the configured output mod (then enable it in MO2 and place it "
            "appropriately in load order). Backed by xEditLib. v1: one record per call, new patch "
            "plugins only (no appending yet)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "patch_name": {"type": "string", "description": "Output plugin filename, e.g. 'MyCompatPatch.esp'."},
                "source_plugin": {"type": "string", "description": "Plugin containing the record to override (e.g. 'FalloutNV.esm' or a mod plugin)."},
                "record_id": {"type": "string", "description": "EditorID or plugin-relative FormID hex of the record."},
                "edits": {"type": "object", "description": "Field edits as {xEdit-path: value}, e.g. {'ACBS - Configuration\\\\Level': '30'}. Optional.", "additionalProperties": {"type": "string"}},
                "write": {"type": "boolean", "description": "false (default) = preview only; true = create the .esp in the output mod.", "default": False},
            },
            "required": ["patch_name", "source_plugin", "record_id"],
        },
        handler=lambda args: _handle_create_patch(organizer, args),
    )


# ── Staging: build a synthetic game dir xEditLib can load the modded plugin from ──

def _data_dir_real(organizer):
    try:
        return organizer.managedGame().dataDirectory().absolutePath()
    except Exception:
        return None


def _real_path(organizer, name: str, data_dir_real=None):
    try:
        p = organizer.resolvePath(name)
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    # Fallback: a master that lives in the real game Data folder (base game / DLC).
    if data_dir_real:
        cand = os.path.join(data_dir_real, name)
        if os.path.isfile(cand):
            return cand
    return None


def _read_masters_from_header(path):
    """Read the MAST master list straight from the plugin's TES4 header — reliable and
    independent of the MO2 plugin-list API (which returned nothing here)."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
            if head[:4] != b"TES4":
                return []
            data_size = struct.unpack_from("<I", head, 4)[0]
            body = f.read(data_size)
        masters, i = [], 0
        while i + 6 <= len(body):
            typ = body[i:i + 4]
            size = struct.unpack_from("<H", body, i + 4)[0]
            if typ == b"MAST":
                masters.append(body[i + 6:i + 6 + size].split(b"\x00", 1)[0].decode("latin1"))
            i += 6 + size
        return masters
    except Exception:
        return []


def _stage_closure(organizer, plugin, data_dir, data_dir_real):
    """Hardlink a plugin + its transitive master closure into data_dir. Returns (staged, missing)."""
    target = _real_path(organizer, plugin, data_dir_real)
    if not target:
        return [], [plugin]
    resolved = {plugin.lower(): (plugin, target)}
    seen = {plugin.lower()}
    queue = [target]
    missing = []
    while queue:
        for m in _read_masters_from_header(queue.pop(0)):
            k = m.lower()
            if k in seen:
                continue
            seen.add(k)
            mp = _real_path(organizer, m, data_dir_real)
            if mp:
                resolved[k] = (m, mp)
                queue.append(mp)
            else:
                missing.append(m)
    staged = []
    for name, src in resolved.values():
        dst = os.path.join(data_dir, os.path.basename(name))
        if os.path.exists(dst):
            staged.append(os.path.basename(name))
            continue
        try:
            os.link(src, dst)
            staged.append(os.path.basename(name))
        except OSError:
            try:
                shutil.copy2(src, dst)
                staged.append(os.path.basename(name))
            except OSError:
                missing.append(name)
    return staged, missing


def _run_create_patch(organizer, patch_name, source_plugin, record_id, edits, write, timeout):
    """Stage source + masters, run `esp patch`, and (on write) copy the result into the output mod."""
    output_mod = organizer.pluginSetting(PLUGIN_NAME, "output-mod")
    if not output_mod:
        return {"ok": False, "error": "No output mod configured in plugin settings."}
    if not patch_name.lower().endswith((".esp", ".esm")):
        return {"ok": False, "error": "patch_name must end in .esp (or .esm)."}
    if "/" in patch_name or "\\" in patch_name or ".." in patch_name:
        return {"ok": False, "error": "patch_name must be a bare filename (no path)."}

    output_mod_dir = os.path.join(organizer.modsPath(), output_mod)
    final_path = os.path.join(output_mod_dir, patch_name)
    if write and os.path.exists(final_path):
        return {"ok": False, "error": f"Patch '{patch_name}' already exists in '{output_mod}'. Appending isn't supported yet — pick a new name or remove it first."}

    data_dir_real = _data_dir_real(organizer)
    target = _real_path(organizer, source_plugin, data_dir_real)
    if not target:
        return {"ok": False, "error": f"source plugin not found in the load order: {source_plugin}"}
    drive = os.path.splitdrive(os.path.abspath(target))[0]
    base = (drive + os.sep) if drive else None
    try:
        tmp_game = tempfile.mkdtemp(prefix="_fnvmcp_", dir=base) if base else tempfile.mkdtemp(prefix="_fnvmcp_")
    except Exception:
        tmp_game = tempfile.mkdtemp(prefix="_fnvmcp_")
    data_dir = os.path.join(tmp_game, "Data")
    try:
        os.makedirs(data_dir, exist_ok=True)
        staged, missing = _stage_closure(organizer, source_plugin, data_dir, data_dir_real)
        cli_args = [patch_name, source_plugin, str(record_id)]
        for p, v in (edits or {}).items():
            cli_args += ["--set", f"{p}={v}"]
        cli_args += ["--game-dir", tmp_game]
        if write:
            cli_args.append("--write")
        res = run_automod(organizer, "esp", "patch", cli_args, timeout=timeout)
        if isinstance(res, dict):
            res.setdefault("_staging", {"staged": staged, "missing": missing})
        if write and res.get("ok"):
            produced = os.path.join(data_dir, patch_name)
            if os.path.isfile(produced):
                os.makedirs(output_mod_dir, exist_ok=True)
                shutil.copy2(produced, final_path)
                res["written_to"] = final_path
                try:
                    organizer.refresh(save_changes=True)
                except Exception:
                    pass
            else:
                res["ok"] = False
                res["error"] = "esp reported success but no patch file was produced."
        return res
    finally:
        shutil.rmtree(tmp_game, ignore_errors=True)


def _active_load_order(organizer):
    """Active plugins, sorted by load order (the complete, correctly-ordered set —
    MO2 won't activate a plugin with an inactive master)."""
    pl = organizer.pluginList()
    active = [n for n in pl.pluginNames() if pl.state(n) == mobase.PluginState.ACTIVE]
    active.sort(key=lambda n: pl.loadOrder(n))
    return active


def _run_with_full_order_staging(organizer, command: str, target: str, extra_args, timeout: int) -> dict:
    """Conflict tools need the WHOLE load order visible. Stage every active plugin into a
    temp synthetic game dir's Data\\ and pass the explicit order via --load-order."""
    order = _active_load_order(organizer)
    if target.lower() not in {n.lower() for n in order}:
        return {"ok": False, "error": f"plugin not active in the load order: {target}"}

    data_dir_real = _data_dir_real(organizer)
    sample = _real_path(organizer, target, data_dir_real) or os.path.join(data_dir_real or "", target)
    drive = os.path.splitdrive(os.path.abspath(sample))[0]
    base = (drive + os.sep) if drive else None
    try:
        tmp_game = tempfile.mkdtemp(prefix="_fnvmcp_", dir=base) if base else tempfile.mkdtemp(prefix="_fnvmcp_")
    except Exception:
        tmp_game = tempfile.mkdtemp(prefix="_fnvmcp_")

    data_dir = os.path.join(tmp_game, "Data")
    staged, missing = [], []
    try:
        os.makedirs(data_dir, exist_ok=True)
        for name in order:
            src = _real_path(organizer, name, data_dir_real)
            if not src:
                missing.append(name)
                continue
            dst = os.path.join(data_dir, os.path.basename(name))
            if os.path.exists(dst):
                staged.append(name)
                continue
            try:
                os.link(src, dst)
                staged.append(name)
            except OSError:
                try:
                    shutil.copy2(src, dst)
                    staged.append(name)
                except OSError:
                    missing.append(name)

        lo_file = os.path.join(tmp_game, "loadorder.txt")
        with open(lo_file, "w", encoding="utf-8") as f:
            f.write("\n".join(order))

        diag = {"order_count": len(order), "staged_count": len(staged), "missing": missing}
        res = run_automod(organizer, "esp", command, [target] + list(extra_args) + ["--game-dir", tmp_game, "--load-order", lo_file], timeout=timeout)
        if isinstance(res, dict):
            res.setdefault("_staging", diag)
        return res
    finally:
        shutil.rmtree(tmp_game, ignore_errors=True)


def _run_with_staging(organizer, command: str, plugin: str, extra_args, timeout: int) -> dict:
    """Resolve plugin + masters to real paths, hardlink into a temp game dir's Data\\,
    run `esp <command> <plugin> <extra...> --game-dir <tmp>`, then clean up."""
    target = _real_path(organizer, plugin)
    if not target:
        return {"ok": False, "error": f"plugin not found in the load order: {plugin}"}

    data_dir_real = _data_dir_real(organizer)

    # Transitive master closure: read MAST entries from the target AND from every master
    # (an "All DLC" merge master, say, pulls in DLCs the target's own header never lists).
    resolved = {plugin.lower(): (plugin, target)}   # lname -> (name, real path)
    missing, masters_order = [], []
    seen = {plugin.lower()}
    queue = [target]
    while queue:
        for m in _read_masters_from_header(queue.pop(0)):
            k = m.lower()
            if k in seen:
                continue
            seen.add(k)
            masters_order.append(m)
            mp = _real_path(organizer, m, data_dir_real)
            if mp:
                resolved[k] = (m, mp)
                queue.append(mp)            # recurse into this master's own masters
            else:
                missing.append(m)
    needed = [(plugin, target)] + [resolved[m.lower()] for m in masters_order if m.lower() in resolved]
    staged = []

    # Temp game dir on the same volume as the target (so hardlinks succeed).
    drive = os.path.splitdrive(os.path.abspath(target))[0]
    base = (drive + os.sep) if drive else None
    try:
        tmp_game = tempfile.mkdtemp(prefix="_fnvmcp_", dir=base) if base else tempfile.mkdtemp(prefix="_fnvmcp_")
    except Exception:
        tmp_game = tempfile.mkdtemp(prefix="_fnvmcp_")

    data_dir = os.path.join(tmp_game, "Data")
    try:
        os.makedirs(data_dir, exist_ok=True)
        for name, src in needed:
            dst = os.path.join(data_dir, os.path.basename(name))
            if os.path.exists(dst):
                staged.append(os.path.basename(name))
                continue
            try:
                os.link(src, dst)             # instant, same-volume
                staged.append(os.path.basename(name))
            except OSError:
                try:
                    shutil.copy2(src, dst)    # cross-volume fallback
                    staged.append(os.path.basename(name))
                except OSError:
                    missing.append(name)

        diag = {
            "target_resolved": target,
            "masters": masters_order,
            "masters_count": len(masters_order),
            "staged": staged,
            "missing": missing,
        }
        res = run_automod(organizer, "esp", command, [plugin] + list(extra_args) + ["--game-dir", tmp_game], timeout=timeout)
        if isinstance(res, dict):
            res.setdefault("_staging", diag)
        return res
    finally:
        shutil.rmtree(tmp_game, ignore_errors=True)


# ── Tool handlers ──

def _handle_query(organizer, args: dict) -> str:
    plugin = args.get("plugin_name", "")
    if not plugin:
        return json.dumps({"error": "plugin_name is required."})
    extra = []
    if args.get("signature"):
        extra += ["--sig", str(args["signature"])]
    if args.get("match"):
        extra += ["--match", str(args["match"])]
    extra += ["--limit", str(int(args.get("limit", 200)))]

    res = _run_with_staging(organizer, "query", plugin, extra, _RECORD_TIMEOUT)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "esp query failed"), "detail": res.get("stderr"), "staging": res.get("_staging")}, indent=2)
    return json.dumps({
        "success": True,
        "plugin": res.get("plugin"),
        "signature": res.get("signature"),
        "match": res.get("match"),
        "scanned": res.get("scanned"),
        "matched": res.get("matched"),
        "returned": res.get("returned"),
        "truncated": res.get("truncated"),
        "records": res.get("records", []),
    }, indent=2)


def _handle_detail(organizer, args: dict) -> str:
    plugin = args.get("plugin_name", "")
    record_id = args.get("record_id", "")
    if not plugin or not record_id:
        return json.dumps({"error": "plugin_name and record_id are required."})

    res = _run_with_staging(organizer, "record", plugin, [str(record_id)], _RECORD_TIMEOUT)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "esp record failed"), "detail": res.get("stderr"), "staging": res.get("_staging")}, indent=2)
    return json.dumps({
        "success": True,
        "plugin": res.get("plugin"),
        "formID": res.get("formID"),
        "signature": res.get("signature"),
        "editorID": res.get("editorID"),
        "name": res.get("name"),
        "longName": res.get("longName"),
        "record": res.get("record"),
    }, indent=2)


def _handle_conflict_chain(organizer, args: dict) -> str:
    plugin = args.get("plugin_name", "")
    record_id = args.get("record_id", "")
    if not plugin or not record_id:
        return json.dumps({"error": "plugin_name and record_id are required."})

    res = _run_with_full_order_staging(organizer, "overrides", plugin, [str(record_id)], _RECORD_TIMEOUT)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "conflict chain failed"), "detail": res.get("stderr"), "staging": res.get("_staging")}, indent=2)
    return json.dumps({
        "success": True,
        "plugin": res.get("plugin"),
        "record": res.get("record"),
        "winner": res.get("winner"),
        "override_count": res.get("overrideCount"),
        "conflicted": res.get("conflicted"),
        "chain": res.get("chain", []),
    }, indent=2)


def _handle_plugin_conflicts(organizer, args: dict) -> str:
    plugin = args.get("plugin_name", "")
    if not plugin:
        return json.dumps({"error": "plugin_name is required."})
    limit = int(args.get("limit", 500))
    res = _run_with_full_order_staging(organizer, "plugin-conflicts", plugin, ["--limit", str(limit)], _RECORD_TIMEOUT)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "plugin-conflicts failed"), "detail": res.get("stderr"), "staging": res.get("_staging")}, indent=2)
    return json.dumps({
        "success": True,
        "plugin": res.get("plugin"),
        "total_overrides": res.get("totalOverrides"),
        "won": res.get("won"),
        "lost": res.get("lost"),
        "lost_truncated": res.get("lostTruncated"),
        "lost_to": res.get("lostTo", []),
    }, indent=2)


def _handle_conflict_summary(organizer, args: dict) -> str:
    res = _run_with_full_order_staging(organizer, "conflict-summary", "FalloutNV.esm", [], _RECORD_TIMEOUT)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "conflict-summary failed"), "detail": res.get("stderr"), "staging": res.get("_staging")}, indent=2)
    return json.dumps({
        "success": True,
        "plugin_count": res.get("pluginCount"),
        "plugins": res.get("plugins", []),
    }, indent=2)


def _handle_create_patch(organizer, args: dict) -> str:
    patch = args.get("patch_name", "")
    source = args.get("source_plugin", "")
    rid = args.get("record_id", "")
    if not patch or not source or not rid:
        return json.dumps({"error": "patch_name, source_plugin, and record_id are required."})
    edits = args.get("edits") or {}
    write = bool(args.get("write", False))

    res = _run_create_patch(organizer, patch, source, str(rid), edits, write, _RECORD_TIMEOUT)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "create_patch failed"), "detail": res.get("stderr"), "staging": res.get("_staging")}, indent=2)
    out = {
        "success": True,
        "dry_run": not write,
        "patch": res.get("outPlugin"),
        "source": res.get("source"),
        "record": res.get("record"),
        "masters": res.get("masters"),
        "applied": res.get("applied"),
        "failed": res.get("failed"),
    }
    if write:
        out["written_to"] = res.get("written_to")
        out["next_step"] = "Enable the patch in MO2's plugin list and position it after the plugins it should win over."
    else:
        out["note"] = "Preview only — call again with write=true to create the patch in the output mod."
    return json.dumps(out, indent=2)

"""MCP tools for NIF (mesh) inspection, backed by the toolbox's AutoMod `nif`
module via the AutoMod bridge.

AutoMod's NIF reader is self-built and native for `info` + `list-textures` (no extra
binary needed, unlike the upstream Rust nif-tool). `shader-info` maps to AutoMod's
`inspect` (a full block dump via the optional fo76utils nif_info — includes shader
properties). FNV meshes are Gamebryo NIF 20.2.0.7.
"""

import json
import os

import mobase

from .automod_bridge import run_automod


def register_nif_tools(registry, organizer: mobase.IOrganizer) -> None:

    registry.register(
        name="mo2_nif_info",
        description=(
            "Return NIF metadata: header string, version (FNV is 20.2.0.7), block "
            "count, block types, and texture count. Takes a VFS or absolute path to "
            "a .nif. Native — no extra tool required."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nif_path": {"type": "string", "description": "VFS or absolute path to the .nif file."},
            },
            "required": ["nif_path"],
        },
        handler=lambda args: _handle_nif_info(organizer, args),
    )

    registry.register(
        name="mo2_nif_list_textures",
        description=(
            "List every texture path (.dds/.tga) referenced by a NIF. Useful for "
            "spotting missing-texture references or auditing texture-path prefixes. "
            "Native — no extra tool required."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nif_path": {"type": "string", "description": "VFS or absolute path to a .nif file."},
            },
            "required": ["nif_path"],
        },
        handler=lambda args: _handle_nif_list_textures(organizer, args),
    )

    registry.register(
        name="mo2_nif_shader_info",
        description=(
            "Full NIF block dump (includes shader/material properties), via the "
            "optional fo76utils nif_info tool. Use for debugging material/lighting. "
            "Requires nif_info.exe on PATH or in the game folder; returns a clear "
            "error if it isn't installed (use mo2_nif_info / NifSkope otherwise)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nif_path": {"type": "string", "description": "VFS or absolute path to a .nif file."},
            },
            "required": ["nif_path"],
        },
        handler=lambda args: _handle_nif_shader_info(organizer, args),
    )


def _resolve_nif(organizer, nif_path: str):
    if not nif_path:
        return None, "nif_path is required."
    if os.path.isabs(nif_path) and os.path.exists(nif_path):
        return nif_path, None
    disk = organizer.resolvePath(nif_path.replace("/", "\\"))
    if not disk or not os.path.exists(disk):
        return None, f"NIF not found in VFS: {nif_path}"
    return disk, None


def _strip(res: dict) -> dict:
    return {k: v for k, v in res.items() if k not in ("ok", "action", "file")}


def _handle_nif_info(organizer, args: dict) -> str:
    disk, err = _resolve_nif(organizer, args.get("nif_path", ""))
    if err:
        return json.dumps({"error": err})
    res = run_automod(organizer, "nif", "info", [disk], timeout=60)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "nif info failed"), "detail": res.get("stderr")})
    return json.dumps({"success": True, "nif": disk.replace("\\", "/"), "result": _strip(res)}, indent=2)


def _handle_nif_list_textures(organizer, args: dict) -> str:
    disk, err = _resolve_nif(organizer, args.get("nif_path", ""))
    if err:
        return json.dumps({"error": err})
    res = run_automod(organizer, "nif", "list-textures", [disk], timeout=60)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "nif list-textures failed"), "detail": res.get("stderr")})
    return json.dumps({
        "success": True,
        "nif": disk.replace("\\", "/"),
        "count": res.get("count", 0),
        "textures": res.get("textures", []),
    }, indent=2)


def _handle_nif_shader_info(organizer, args: dict) -> str:
    disk, err = _resolve_nif(organizer, args.get("nif_path", ""))
    if err:
        return json.dumps({"error": err})
    res = run_automod(organizer, "nif", "inspect", [disk], timeout=60)
    if not res.get("ok"):
        return json.dumps({
            "error": res.get("error", "nif inspect failed (fo76utils nif_info may be missing)"),
            "detail": res.get("stderr"),
        })
    return json.dumps({
        "success": True,
        "nif": disk.replace("\\", "/"),
        "tool": res.get("tool", "nif_info"),
        "dump": res.get("output"),
    }, indent=2)

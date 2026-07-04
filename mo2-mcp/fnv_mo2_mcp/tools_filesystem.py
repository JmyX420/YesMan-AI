"""MCP tools for resolving and reading files through MO2's virtual file system.

Pure mobase — game-agnostic, ported from upstream with FNV example paths and an
FNV-appropriate binary-extension set (no .ba2/.esl/.xwm/.fuz/.pex; adds .ogg/.kf).
"""

import json
import os
import fnmatch

import mobase


def register_filesystem_tools(registry, organizer: mobase.IOrganizer):
    """Register all filesystem tools with the MCP tool registry."""

    # ── mo2_resolve_path ─────────────────────────────────────────────

    registry.register(
        name="mo2_resolve_path",
        description=(
            "Resolve a game-relative path through MO2's virtual file system "
            "to its real location on disk. Shows which mod provides the file "
            "and which other mods also contain it (conflict losers)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Game-relative path, e.g. "
                        "'meshes/weapons/9mmpistol/9mmpistol.nif' or 'FalloutNV.esm'"
                    ),
                },
            },
            "required": ["path"],
        },
        handler=lambda args: _resolve_path(organizer, args),
    )

    # ── mo2_list_files ───────────────────────────────────────────────

    registry.register(
        name="mo2_list_files",
        description=(
            "List files in a virtual directory path within MO2's VFS. "
            "Optionally filter by glob pattern. Shows which mod provides each file."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": (
                        "Game-relative directory path, e.g. "
                        "'meshes/weapons' or 'sound/voice'"
                    ),
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob filter, e.g. '*.esp' or '*.nif'",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Search subdirectories (default false)",
                    "default": False,
                },
                "mod_name": {
                    "type": "string",
                    "description": "Filter to files provided by this mod (mod folder name, not plugin filename)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 200)",
                    "default": 200,
                },
            },
            "required": ["directory"],
        },
        handler=lambda args: _list_files(organizer, args),
    )

    # ── mo2_read_file ────────────────────────────────────────────────

    registry.register(
        name="mo2_read_file",
        description=(
            "Read a text file's contents through MO2's VFS resolution. "
            "Returns the file content and which mod provides it. "
            "Supports optional line-range reads via offset/limit. "
            "Only works with text files; binary files return an error."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Game-relative path to a text file, e.g. "
                        "'NVSE/Plugins/scripts/gr_MyMod.txt' or 'Config/MyMod/settings.ini'"
                    ),
                },
                "encoding": {
                    "type": "string",
                    "description": "Text encoding (default 'utf-8')",
                    "default": "utf-8",
                },
                "max_size_kb": {
                    "type": "integer",
                    "description": "Max file size in KB to read (default 512)",
                    "default": 512,
                },
                "offset": {
                    "type": "integer",
                    "description": (
                        "Start line (0-based). When provided, returns lines "
                        "starting from this position. Omit for full file."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": (
                        "Max lines to return. Use with offset for partial "
                        "reads of large files. Omit for full file."
                    ),
                },
            },
            "required": ["path"],
        },
        handler=lambda args: _read_file(organizer, args),
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _vfs_relative_path(real_path, mods_path, overwrite_path, game_data_path):
    """Extract the game-relative VFS path from an absolute disk path.

    Handles files from mod directories (modsPath/ModName/...),
    the overwrite directory, and the game's base Data directory.
    Returns None if the path can't be resolved to a VFS path.
    """
    norm = os.path.normpath(real_path)
    norm_lower = norm.lower()

    # Mod directory: modsPath\ModName\relative\path
    prefix = mods_path.lower() + os.sep
    if norm_lower.startswith(prefix):
        after_mods = norm[len(mods_path) + 1:]
        sep_idx = after_mods.find(os.sep)
        if sep_idx >= 0:
            return after_mods[sep_idx + 1:].replace(os.sep, "/")
        return None  # At mod root level, not in VFS data tree

    # Overwrite directory: overwritePath\relative\path
    prefix = overwrite_path.lower() + os.sep
    if norm_lower.startswith(prefix):
        return norm[len(overwrite_path) + 1:].replace(os.sep, "/")

    # Game data directory: dataDir\relative\path
    if game_data_path:
        prefix = game_data_path.lower() + os.sep
        if norm_lower.startswith(prefix):
            return norm[len(game_data_path) + 1:].replace(os.sep, "/")

    # Unknown source: return basename as last resort
    return os.path.basename(real_path)


# ── Tool implementations ─────────────────────────────────────────────


def _resolve_path(organizer, args: dict) -> str:
    path = args.get("path", "")
    real_path = organizer.resolvePath(path)

    if not real_path:
        return json.dumps({"error": f"File not found in VFS: {path}"})

    origins = organizer.getFileOrigins(path)
    result = {
        "path": path,
        "real_path": real_path,
        "providing_mod": origins[0] if origins else None,
        "conflicts": origins[1:] if len(origins) > 1 else [],
    }
    return json.dumps(result, indent=2)


def _list_files(organizer, args: dict) -> str:
    directory = args.get("directory", "")
    pattern = args.get("pattern", "")
    recursive = args.get("recursive", False)
    limit = int(args.get("limit", 200))
    mod_filter = args.get("mod_name", "")

    # Normalize root path: "." means VFS root, which MO2 expects as ""
    if directory in (".", "./", ".\\"):
        directory = ""
    directory = directory.strip("/\\")

    # findFiles is inherently recursive; we filter for non-recursive after
    search_pattern = pattern if pattern else "*"
    matches = organizer.findFiles(directory, search_pattern)

    # Precompute base paths for VFS-relative path reconstruction
    mods_path = os.path.normpath(organizer.modsPath())
    overwrite_path = os.path.normpath(organizer.overwritePath())
    try:
        game_data_path = os.path.normpath(
            organizer.managedGame().dataDirectory().absolutePath()
        )
    except Exception:
        game_data_path = None

    results = []
    for real_path in matches:
        # Reconstruct the correct VFS-relative path from the disk path
        rel_path = _vfs_relative_path(
            real_path, mods_path, overwrite_path, game_data_path
        )
        if not rel_path:
            continue

        # Non-recursive: skip files in subdirectories of the target
        if not recursive:
            if directory:
                expected = directory.lower() + "/"
                if not rel_path.lower().startswith(expected):
                    continue
                remainder = rel_path[len(directory) + 1:]
            else:
                remainder = rel_path
            if "/" in remainder:
                continue

        # Get origin info using the correct VFS path
        origins = organizer.getFileOrigins(rel_path)
        if mod_filter and (not origins or origins[0] != mod_filter):
            continue

        entry = {
            "path": rel_path,
            "providing_mod": origins[0] if origins else None,
        }
        try:
            entry["size"] = os.path.getsize(real_path)
        except OSError:
            pass

        results.append(entry)
        if len(results) >= limit:
            break

    output = {
        "directory": directory if directory else "(root)",
        "total": len(results),
        "truncated": len(results) >= limit,
        "files": results,
    }
    return json.dumps(output, indent=2)


def _read_file(organizer, args: dict) -> str:
    path = args.get("path", "")
    encoding = args.get("encoding", "utf-8")
    max_size_kb = int(args.get("max_size_kb", 512))
    offset = args.get("offset")   # None if not provided
    limit = args.get("limit")     # None if not provided

    real_path = organizer.resolvePath(path)
    if not real_path:
        return json.dumps({"error": f"File not found in VFS: {path}"})

    # Check file size
    try:
        size = os.path.getsize(real_path)
    except OSError as e:
        return json.dumps({"error": f"Cannot access file: {e}"})

    max_bytes = max_size_kb * 1024
    if size > max_bytes:
        return json.dumps({
            "error": f"File too large: {size} bytes (max {max_bytes} bytes). "
                     f"Increase max_size_kb parameter if needed.",
            "size": size,
        })

    # Detect binary files by extension (FNV-relevant set)
    binary_exts = {
        ".esp", ".esm", ".bsa",
        ".nif", ".dds", ".png", ".jpg", ".bmp", ".tga",
        ".wav", ".ogg", ".mp3", ".lip",
        ".kf", ".egm", ".tri",
        ".dll", ".exe",
        ".bik", ".btr", ".bto",
    }
    ext = os.path.splitext(real_path)[1].lower()
    if ext in binary_exts:
        return json.dumps({
            "error": f"Binary file format ({ext}), cannot read as text.",
            "real_path": real_path,
            "size": size,
        })

    # Read text content
    try:
        with open(real_path, "r", encoding=encoding, errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {e}"})

    total_lines = len(lines)

    # Apply line range if offset or limit provided
    if offset is not None or limit is not None:
        start = max(0, int(offset)) if offset is not None else 0
        start = min(start, total_lines)
        end = (start + int(limit)) if limit is not None else total_lines
        selected = lines[start:end]
        content = "".join(selected)
    else:
        content = "".join(lines)
        selected = None

    origins = organizer.getFileOrigins(path)
    result = {
        "path": path,
        "real_path": real_path,
        "providing_mod": origins[0] if origins else None,
        "size": size,
        "total_lines": total_lines,
        "content": content,
    }

    if selected is not None:
        result["offset"] = start
        result["lines_returned"] = len(selected)

    return json.dumps(result, indent=2)

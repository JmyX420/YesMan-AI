"""MCP tools for BSA archive operations, backed by the toolbox's AutoMod `bsa`
module (BSArch.exe `-fnv`) via the AutoMod bridge.

FNV uses BSA only (no BA2). VFS path resolution + the output-mod sandbox stay in
Python; the archive work itself routes to `node tools/automod/cli.js bsa ...`.
"""

import fnmatch
import json
import os
import shutil
import tempfile

from PyQt6.QtCore import qInfo, qWarning

import mobase

from .config import PLUGIN_NAME
from .automod_bridge import run_automod, automod_available


def register_archive_tools(registry, organizer: mobase.IOrganizer) -> None:

    registry.register(
        name="mo2_list_bsa",
        description=(
            "List files inside a BSA archive. Pass a VFS path (e.g. "
            "'Fallout - Meshes.bsa') or an absolute path. Optional filter is a "
            "case-insensitive SUBSTRING match (e.g. '.nif', 'textures/'). Default "
            "limit is 500 entries; set limit=0 for all. Returns the file list plus count."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "archive_path": {"type": "string", "description": "VFS or absolute path to the .bsa archive."},
                "filter": {"type": "string", "description": "Case-insensitive substring filter (e.g. '.nif', 'textures/')."},
                "limit": {"type": "integer", "description": "Max files to return (default 500, 0 = all).", "default": 500},
            },
            "required": ["archive_path"],
        },
        handler=lambda args: _handle_list_bsa(organizer, args),
    )

    registry.register(
        name="mo2_extract_bsa_file",
        description=(
            "Extract a single file from a BSA to disk. Preferred over mo2_extract_bsa "
            "when you only need one asset. Written into the configured output mod, "
            "preserving the archive's internal folder structure."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "archive_path": {"type": "string", "description": "VFS or absolute path to the .bsa."},
                "file_in_archive": {"type": "string", "description": "Path inside the archive (e.g. 'meshes/weapons/9mm.nif')."},
                "output_name": {"type": "string", "description": "Optional relative path inside the output mod. Default: preserves the archive's internal path."},
            },
            "required": ["archive_path", "file_in_archive"],
        },
        handler=lambda args: _handle_extract_file(organizer, args),
    )

    registry.register(
        name="mo2_extract_bsa",
        description=(
            "Extract files matching a glob from a BSA into the output mod. The filter "
            "is required to avoid unpacking a multi-GB archive when you only want a subset. "
            "For a single file, prefer mo2_extract_bsa_file."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "archive_path": {"type": "string", "description": "VFS or absolute path to the .bsa."},
                "filter": {"type": "string", "description": "Glob filter (e.g. '*.nif', 'textures/weapons/*'). Required."},
                "output_subdir": {"type": "string", "description": "Optional subdirectory inside the output mod (default: archive's basename)."},
            },
            "required": ["archive_path", "filter"],
        },
        handler=lambda args: _handle_extract(organizer, args),
    )

    registry.register(
        name="mo2_validate_bsa",
        description=(
            "Basic integrity check: confirm BSArch can open the archive and read its "
            "file table, and report the entry count. (Readability/header check, not a "
            "deep per-file corruption scan.)"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "archive_path": {"type": "string", "description": "VFS or absolute path to the .bsa."},
            },
            "required": ["archive_path"],
        },
        handler=lambda args: _handle_validate(organizer, args),
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _resolve_archive(organizer, archive_path: str):
    """Return (disk_path, error). Absolute+existing wins; else VFS-resolve."""
    if not archive_path:
        return None, "archive_path is required."
    if os.path.isabs(archive_path) and os.path.isfile(archive_path):
        return archive_path, None
    disk = organizer.resolvePath(archive_path.replace("/", "\\"))
    if not disk or not os.path.isfile(disk):
        return None, f"Archive not found in VFS: {archive_path}"
    return disk, None


def _output_mod_dir(organizer):
    output_mod = organizer.pluginSetting(PLUGIN_NAME, "output-mod")
    if not output_mod:
        return None, None, "No output mod configured in plugin settings."
    return output_mod, os.path.join(organizer.modsPath(), output_mod), None


# ── Tool implementations ─────────────────────────────────────────────


def _handle_list_bsa(organizer, args: dict) -> str:
    disk, err = _resolve_archive(organizer, args.get("archive_path", ""))
    if err:
        return json.dumps({"error": err})

    limit = args.get("limit", 500)
    cli_args = [disk]
    if args.get("filter"):
        cli_args += ["--filter", str(args["filter"])]
    # AutoMod has no "all" sentinel; limit=0 -> a very large cap.
    eff_limit = 1000000 if int(limit) == 0 else int(limit)
    cli_args += ["--limit", str(eff_limit)]

    res = run_automod(organizer, "bsa", "list", cli_args, timeout=120)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "bsa list failed"), "detail": res.get("stderr")})

    files = res.get("files", [])
    total = res.get("total", len(files))
    return json.dumps({
        "success": True,
        "archive": disk.replace("\\", "/"),
        "file_count": total,
        "showing": len(files),
        "truncated": len(files) < total,
        "files": files,
    }, indent=2)


def _handle_extract_file(organizer, args: dict) -> str:
    disk, err = _resolve_archive(organizer, args.get("archive_path", ""))
    if err:
        return json.dumps({"error": err})

    file_in_archive = args.get("file_in_archive", "")
    if not file_in_archive:
        return json.dumps({"error": "file_in_archive is required."})
    if ".." in file_in_archive:
        return json.dumps({"error": "file_in_archive must not contain '..'."})

    output_mod, output_mod_dir, err = _output_mod_dir(organizer)
    if err:
        return json.dumps({"error": err})

    rel_out = (args.get("output_name") or file_in_archive).replace("/", os.sep).lstrip("/\\")
    if ".." in rel_out:
        return json.dumps({"error": "output_name must not contain '..'."})
    final_path = os.path.join(output_mod_dir, rel_out)
    if not os.path.normpath(final_path).startswith(os.path.normpath(output_mod_dir)):
        return json.dumps({"error": "Output path escapes the output mod directory."})
    if os.path.exists(final_path):
        return json.dumps({"error": f"Output file already exists: {rel_out}. Delete first.", "existing_path": final_path})

    out_dir = os.path.dirname(final_path)
    res = run_automod(organizer, "bsa", "extract-file", [disk, file_in_archive, out_dir], timeout=180)
    if not res.get("ok"):
        return json.dumps({"error": res.get("error", "bsa extract-file failed"), "detail": res.get("stderr")})

    produced = res.get("out")
    if not produced or not os.path.isfile(produced):
        return json.dumps({"error": "AutoMod reported success but no file was produced.", "automod_result": res})

    # AutoMod names the output <out_dir>/<basename(inner)>. Honor a renaming output_name.
    if os.path.normpath(produced) != os.path.normpath(final_path):
        try:
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            os.replace(produced, final_path)
        except OSError as e:
            return json.dumps({"error": f"Failed to place extracted file: {e}", "produced": produced})
        produced = final_path

    size = os.path.getsize(produced)
    qInfo(f"{PLUGIN_NAME}: extracted '{file_in_archive}' ({size} bytes) from {os.path.basename(disk)}")
    try:
        organizer.refresh(save_changes=True)
    except Exception as exc:
        qWarning(f"{PLUGIN_NAME}: organizer.refresh() failed after BSA extract: {exc}")

    return json.dumps({
        "success": True,
        "archive": disk.replace("\\", "/"),
        "file_in_archive": file_in_archive,
        "output_path": produced.replace("\\", "/"),
        "size_bytes": size,
        "next_step": (
            f"Extracted file is visible to mo2_list_files / mo2_read_file via MO2's VFS "
            f"(as long as '{output_mod}' is enabled in MO2's left pane)."
        ),
    }, indent=2)


def _handle_extract(organizer, args: dict) -> str:
    disk, err = _resolve_archive(organizer, args.get("archive_path", ""))
    if err:
        return json.dumps({"error": err})

    glob_filter = args.get("filter")
    if not glob_filter:
        return json.dumps({"error": (
            "filter is required to prevent accidental full-archive extraction. Use a glob "
            "like 'textures/*' or '*.nif'. For a single file prefer mo2_extract_bsa_file."
        )})

    output_mod, output_mod_dir, err = _output_mod_dir(organizer)
    if err:
        return json.dumps({"error": err})

    subdir = args.get("output_subdir")
    if subdir:
        if ".." in subdir or os.path.isabs(subdir):
            return json.dumps({"error": "output_subdir must be a simple relative path."})
        out_dir = os.path.join(output_mod_dir, subdir)
    else:
        out_dir = os.path.join(output_mod_dir, os.path.splitext(os.path.basename(disk))[0])
    if not os.path.normpath(out_dir).startswith(os.path.normpath(output_mod_dir)):
        return json.dumps({"error": "Output subdir escapes the output mod directory."})
    os.makedirs(out_dir, exist_ok=True)

    # AutoMod's bsa has no filtered extract. Unpack fully to a temp dir (BSArch is fast),
    # then move only the glob matches into the output mod.
    pattern_fwd = glob_filter.replace("\\", "/")
    with tempfile.TemporaryDirectory(prefix="mo2_bsa_extract_") as tmp_extract:
        res = run_automod(organizer, "bsa", "unpack", [disk, tmp_extract], timeout=900)
        if not res.get("ok"):
            return json.dumps({"error": res.get("error", "bsa unpack failed"), "detail": res.get("stderr")})

        extracted = 0
        errors = []
        out_base = os.path.normpath(out_dir)
        tmp_base = os.path.normpath(tmp_extract)
        for root, _dirs, files in os.walk(tmp_extract):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, tmp_base).replace("\\", "/")
                if not fnmatch.fnmatch(rel, pattern_fwd):
                    continue
                dest = os.path.normpath(os.path.join(out_base, rel))
                if not dest.startswith(out_base):
                    errors.append({"file": rel, "error": "path escapes output dir"})
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                try:
                    shutil.move(full, dest)
                    extracted += 1
                except Exception as move_err:
                    errors.append({"file": rel, "error": f"move failed: {move_err}"})

    qInfo(f"{PLUGIN_NAME}: extracted {extracted} files from {os.path.basename(disk)} matching '{glob_filter}'")
    try:
        organizer.refresh(save_changes=True)
    except Exception as exc:
        qWarning(f"{PLUGIN_NAME}: organizer.refresh() failed after BSA bulk extract: {exc}")

    return json.dumps({
        "success": True,
        "archive": disk.replace("\\", "/"),
        "filter": glob_filter,
        "output_dir": out_dir.replace("\\", "/"),
        "extracted_count": extracted,
        "errors": errors,
        "next_step": (
            f"Extracted files are visible to mo2_list_files / mo2_read_file via MO2's VFS "
            f"(as long as '{output_mod}' is enabled in MO2's left pane)."
        ),
    }, indent=2)


def _handle_validate(organizer, args: dict) -> str:
    disk, err = _resolve_archive(organizer, args.get("archive_path", ""))
    if err:
        return json.dumps({"error": err})

    res = run_automod(organizer, "bsa", "list", [disk, "--limit", "1"], timeout=120)
    if not res.get("ok"):
        return json.dumps({
            "success": False,
            "archive": disk.replace("\\", "/"),
            "readable": False,
            "error": res.get("error", "BSArch could not read the archive"),
        })
    return json.dumps({
        "success": True,
        "archive": disk.replace("\\", "/"),
        "readable": True,
        "entry_count": res.get("total", 0),
        "note": "BSArch opened the archive and read its file table. This is a readability/header check, not a deep per-file corruption scan.",
    }, indent=2)

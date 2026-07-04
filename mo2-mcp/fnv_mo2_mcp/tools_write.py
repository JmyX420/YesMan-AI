"""MCP tool for writing new files to a designated output mod in MO2.

Pure mobase — game-agnostic. Sandboxed: creates NEW files only, inside the
configured output mod, never executables or plugin files.
"""

import json
import os

import mobase
from PyQt6.QtCore import qWarning

from .config import PLUGIN_NAME

# Disallowed extensions — never write executable or plugin files
BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh",
    ".esp", ".esm",
}


def register_write_tools(registry, organizer: mobase.IOrganizer):
    """Register write tools with the MCP tool registry."""

    registry.register(
        name="mo2_write_file",
        description=(
            "Write a new file to the designated output mod folder. "
            "Safety: can only create NEW files (no overwrites, no deletes), "
            "only in the configured output mod directory. "
            "Cannot write executables or plugin files."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Relative path within the output mod, e.g. "
                        "'NVSE/Plugins/scripts/gr_MyMod.txt' or 'test.txt'"
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "File contents to write",
                },
                "encoding": {
                    "type": "string",
                    "description": "Text encoding (default 'utf-8')",
                    "default": "utf-8",
                },
            },
            "required": ["path", "content"],
        },
        handler=lambda args: _write_file(organizer, args),
    )


def _write_file(organizer, args: dict) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    encoding = args.get("encoding", "utf-8")

    # Get output mod name from settings
    output_mod = organizer.pluginSetting(PLUGIN_NAME, "output-mod")
    if not output_mod:
        return json.dumps({"error": "No output mod configured in plugin settings."})

    # Validate path — no parent traversal
    normalized = os.path.normpath(path)
    if normalized.startswith("..") or os.path.isabs(path):
        return json.dumps({"error": "Path must be relative and cannot use '..' traversal."})

    # Check blocked extensions
    ext = os.path.splitext(path)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        return json.dumps({"error": f"Cannot write files with extension '{ext}'."})

    # Build the full output path
    mods_path = organizer.modsPath()
    output_dir = os.path.join(mods_path, output_mod)
    full_path = os.path.join(output_dir, normalized)

    # Ensure we're still inside the output mod (belt + suspenders)
    if not os.path.normpath(full_path).startswith(os.path.normpath(output_dir)):
        return json.dumps({"error": "Path escapes the output mod directory."})

    # Create output mod directory if it doesn't exist
    if not os.path.isdir(output_dir):
        try:
            os.makedirs(output_dir)
        except OSError as e:
            return json.dumps({"error": f"Cannot create output mod directory: {e}"})

    # Refuse to overwrite existing files
    if os.path.exists(full_path):
        return json.dumps({
            "error": f"File already exists: {path}. Overwrites are not allowed.",
            "existing_path": full_path,
        })

    # Create subdirectories if needed
    parent = os.path.dirname(full_path)
    if not os.path.isdir(parent):
        try:
            os.makedirs(parent)
        except OSError as e:
            return json.dumps({"error": f"Cannot create directory: {e}"})

    # Write the file
    try:
        with open(full_path, "w", encoding=encoding) as f:
            f.write(content)
    except Exception as e:
        return json.dumps({"error": f"Failed to write file: {e}"})

    size = os.path.getsize(full_path)

    # Fire a single MO2 refresh so the new file lands in the VFS; fire-and-forget.
    try:
        organizer.refresh(save_changes=True)
    except Exception as exc:
        qWarning(f"{PLUGIN_NAME}: organizer.refresh() failed after file write: {exc}")

    result = {
        "written_to": full_path,
        "output_mod": output_mod,
        "path": path,
        "size": size,
        "next_step": (
            f"File written and visible to mo2_list_files / mo2_read_file "
            f"via MO2's VFS (as long as '{output_mod}' is enabled in "
            f"MO2's left pane). No further action needed."
        ),
    }
    return json.dumps(result, indent=2)

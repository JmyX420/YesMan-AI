"""MCP tool for analyzing NVSE plugin DLLs through MO2's virtual file system.

PE parsing is via the bundled pure-Python `pefile`. The only FNV-specific logic is
NVSE entry-point detection (NVSEPlugin_Query/Load/Version) and a 32-bit (x86) check —
FNV is 32-bit, so a valid NVSE plugin DLL must be x86.
"""

import json
import os
import re
import time
from datetime import datetime, timezone

import mobase

from . import pefile as pefile_mod


def register_dll_tools(registry, organizer: mobase.IOrganizer):
    """Register DLL analysis tools with the MCP tool registry."""

    registry.register(
        name="mo2_analyze_dll",
        description=(
            "Analyze an NVSE plugin DLL through MO2's VFS. Returns PE metadata, "
            "imports, exports, version info, NVSE entry-point detection "
            "(Query/Load/Version), a 32-bit (x86) check, and filtered strings. "
            "Use for understanding what an NVSE plugin does."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Game-relative path to a DLL, e.g. "
                        "'NVSE/Plugins/SomeMod.dll'"
                    ),
                },
                "include_import_details": {
                    "type": "boolean",
                    "description": (
                        "Include function names in imports "
                        "(default false, returns counts only)"
                    ),
                    "default": False,
                },
                "include_strings": {
                    "type": "boolean",
                    "description": (
                        "Extract and filter strings from the DLL (default true)"
                    ),
                    "default": True,
                },
            },
            "required": ["path"],
        },
        handler=lambda args: _analyze_dll(organizer, args),
    )


# ── Tool implementation ─────────────────────────────────────────────────


MAX_SIZE_MB = 50


def _analyze_dll(organizer, args: dict) -> str:
    path = args.get("path", "")
    include_import_details = args.get("include_import_details", False)
    include_strings = args.get("include_strings", True)

    # Resolve through VFS
    real_path = organizer.resolvePath(path)
    if not real_path:
        return json.dumps({"error": f"File not found in VFS: {path}"})

    # Validate extension
    if not real_path.lower().endswith(".dll"):
        return json.dumps({"error": f"Not a DLL file: {path}"})

    # Check size
    try:
        size = os.path.getsize(real_path)
    except OSError as e:
        return json.dumps({"error": f"Cannot access file: {e}"})

    if size > MAX_SIZE_MB * 1024 * 1024:
        return json.dumps({
            "error": f"File too large: {size} bytes (max {MAX_SIZE_MB} MB)",
            "size": size,
        })

    # Read and parse
    t0 = time.perf_counter()
    try:
        with open(real_path, "rb") as f:
            data = f.read()
        pe = pefile_mod.PE(data=data)
    except Exception as e:
        return json.dumps({"error": f"Failed to parse PE: {e}"})

    # Get VFS origin info
    origins = organizer.getFileOrigins(path)

    result = {
        "path": path,
        "real_path": real_path,
        "providing_mod": origins[0] if origins else None,
        "conflicts": origins[1:] if len(origins) > 1 else [],
    }

    # File info
    result["file"] = {
        "name": os.path.basename(real_path),
        "size": size,
        "size_human": _human_size(size),
    }

    # Compile info
    result["compile"] = _get_compile_info(pe)

    # Version info from PE resources
    result["version_info"] = _get_version_info(pe)

    # Imports
    result["imports"] = _get_imports(pe, include_import_details)

    # Exports
    result["exports"] = _get_exports(pe)

    # NVSE-specific analysis
    result["nvse"] = _get_nvse_info(pe, result["exports"])

    # Companion PDB check
    pdb_path = os.path.splitext(real_path)[0] + ".pdb"
    result["has_pdb"] = os.path.isfile(pdb_path)

    # Strings (optional, on by default)
    if include_strings:
        result["strings"] = _get_filtered_strings(data)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    result["analysis_time_ms"] = round(elapsed_ms, 1)

    pe.close()
    return json.dumps(result, indent=2)


# ── Helpers ──────────────────────────────────────────────────────────────


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} B"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def _get_compile_info(pe) -> dict:
    machine = pe.FILE_HEADER.Machine
    arch_map = {0x8664: "x64", 0x14C: "x86"}
    timestamp = pe.FILE_HEADER.TimeDateStamp

    info = {
        "architecture": arch_map.get(machine, f"unknown ({hex(machine)})"),
        "timestamp": timestamp,
    }
    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        info["timestamp_human"] = dt.strftime("%Y-%m-%d %H:%M UTC")
    except (OSError, ValueError, OverflowError):
        info["timestamp_human"] = "invalid"
    return info


def _get_version_info(pe) -> dict:
    info = {}
    if not hasattr(pe, "VS_VERSIONINFO") or not hasattr(pe, "FileInfo"):
        return info

    try:
        for file_info in pe.FileInfo:
            for entry in file_info:
                if hasattr(entry, "StringTable"):
                    for st in entry.StringTable:
                        for key, val in st.entries.items():
                            k = key.decode("utf-8", errors="replace")
                            v = val.decode("utf-8", errors="replace")
                            if v:
                                info[k] = v
    except Exception:
        pass
    return info


def _get_imports(pe, include_details: bool) -> dict:
    imports = {}
    if not hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        return imports

    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        dll_name = entry.dll.decode("utf-8", errors="replace")
        if include_details:
            funcs = []
            for imp in entry.imports:
                if imp.name:
                    funcs.append(imp.name.decode("utf-8", errors="replace"))
                else:
                    funcs.append(f"ordinal_{imp.ordinal}")
            imports[dll_name] = {"count": len(entry.imports), "functions": funcs}
        else:
            imports[dll_name] = {"count": len(entry.imports)}
    return imports


def _get_exports(pe) -> list:
    exports = []
    if not hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        return exports

    for exp in pe.DIRECTORY_ENTRY_EXPORT.symbols:
        if exp.name:
            exports.append(exp.name.decode("utf-8", errors="replace"))
        else:
            exports.append(f"ordinal_{exp.ordinal}")
    return exports


def _get_nvse_info(pe, exports: list) -> dict:
    """Analyze NVSE-specific characteristics from exports + architecture."""
    info = {}

    # NVSE plugin entry points. Classic plugins export Query + Load; xNVSE added
    # NVSEPlugin_Version as a modern versioned alternative (mirrors SKSE).
    has_version = "NVSEPlugin_Version" in exports
    has_query = "NVSEPlugin_Query" in exports
    has_load = "NVSEPlugin_Load" in exports

    info["has_NVSEPlugin_Version"] = has_version
    info["has_NVSEPlugin_Query"] = has_query
    info["has_NVSEPlugin_Load"] = has_load

    if has_version:
        info["api_style"] = "modern (NVSEPlugin_Version)"
    elif has_query and has_load:
        info["api_style"] = "classic (Query/Load)"
    else:
        info["api_style"] = "unknown (no standard NVSE exports — may not be an NVSE plugin)"

    # FNV is 32-bit: an NVSE plugin MUST be x86 to load.
    machine = pe.FILE_HEADER.Machine
    info["is_x86"] = (machine == 0x14C)
    if machine != 0x14C:
        info["warning"] = (
            "Not x86 (32-bit). Fallout: New Vegas is 32-bit; a non-x86 DLL "
            "cannot load as an NVSE plugin."
        )

    return info


# ── String extraction ────────────────────────────────────────────────────

# Minimum length for extracted strings
_MIN_STR_LEN = 8

# Category keyword patterns
_ERROR_KEYWORDS = re.compile(
    r"fail|error|warn|invalid|missing|cannot|couldn\'t|unable|exception|crash|assert",
    re.IGNORECASE,
)
_FILE_REF_PATTERN = re.compile(
    r"\.(esp|esm|ini|json|toml|yaml|yml|dll|nif|dds|bsa|txt|cfg|xml|log|ogg|kf|lip)\b",
    re.IGNORECASE,
)
# FNV/NVSE engine + extender vocabulary (replaces Skyrim's SKSE/CommonLib/Papyrus set).
_ENGINE_KEYWORDS = re.compile(
    r"NVSE|xNVSE|JIP|JohnnyGuitar|ShowOff|kNVSE|lStewieAl|SUP\s*NVSE|"
    r"FalloutNV|Fallout3|TESForm|TESObjectREFR|Actor|GameSetting|Console|BGS|TES[A-Z]",
    re.IGNORECASE,
)
_VERSION_PATTERN = re.compile(
    r"v?\d+\.\d+\.\d+(?:\.\d+)?",
)

# Cap per category
_CAT_LIMIT = 25
_TOTAL_LIMIT = 100


def _get_filtered_strings(data: bytes) -> dict:
    """Extract printable ASCII strings and categorize them."""
    raw_strings = _extract_ascii_strings(data, _MIN_STR_LEN)

    errors = []
    file_refs = []
    engine = []
    versions = []
    seen = set()

    for s in raw_strings:
        if s in seen:
            continue
        seen.add(s)

        if len(errors) < _CAT_LIMIT and _ERROR_KEYWORDS.search(s):
            errors.append(s)

        if len(file_refs) < _CAT_LIMIT and _FILE_REF_PATTERN.search(s):
            file_refs.append(s)

        if len(engine) < _CAT_LIMIT and _ENGINE_KEYWORDS.search(s):
            engine.append(s)

        if len(versions) < _CAT_LIMIT and _VERSION_PATTERN.search(s):
            versions.append(s)

    total = len(errors) + len(file_refs) + len(engine) + len(versions)

    return {
        "total_raw": len(raw_strings),
        "filtered_count": total,
        "truncated": total >= _TOTAL_LIMIT,
        "errors": errors,
        "file_refs": file_refs,
        "engine": engine,
        "versions": versions,
    }


def _extract_ascii_strings(data: bytes, min_len: int) -> list:
    """Extract printable ASCII strings of at least min_len characters."""
    strings = []
    current = []
    for byte in data:
        if 32 <= byte < 127:
            current.append(chr(byte))
        else:
            if len(current) >= min_len:
                strings.append("".join(current))
            current = []
    if len(current) >= min_len:
        strings.append("".join(current))
    return strings

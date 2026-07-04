#!/bin/bash
# Protect ALL files from unnoticed edits. Every edit in the game/config directories
# requires explicit confirmation; binary plugin/archive files are hard-blocked.
#
# SETUP: the YesMan AI installer (installer/configure.py) fills in {{JQ_PATH}} below.

JQ="{{JQ_PATH}}"

INPUT=$(cat /dev/stdin)
FILE_PATH=$(echo "$INPUT" | "$JQ" -r '.tool_input.file_path // empty')

[ -z "$FILE_PATH" ] && exit 0

deny() { "$JQ" -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'; exit 0; }
ask()  { "$JQ" -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'; exit 0; }

# === HARD BLOCK -- binary plugin/archive files (FNV: esm/esp/bsa only) ===
echo "$FILE_PATH" | grep -qiE '\.(esp|esm|bsa)$' && deny "BLOCKED: Cannot directly write to plugin/archive files. Use xEditLib, an xEdit Apply Script, or the GECK."

# === WHITELIST -- our own workspace (no confirmation needed) ===
echo "$FILE_PATH" | grep -qiE '\.claude/(hooks|plans|backups|memory|skills)/' && exit 0
echo "$FILE_PATH" | grep -qiE '\.claude/projects/' && exit 0

# === HIGH-PRIORITY CONFIRM (specific message) ===
echo "$FILE_PATH" | grep -qiE '(Fallout\.ini|FalloutPrefs\.ini|FalloutCustom\.ini)$' && ask "EDITING FNV CONFIG: $FILE_PATH"
echo "$FILE_PATH" | grep -qiE 'Data/NVSE/Plugins/.*\.ini$' && ask "EDITING NVSE PLUGIN CONFIG: $FILE_PATH"
echo "$FILE_PATH" | grep -qiE '(loadorder\.txt|plugins\.txt|NVDLCList\.txt)$' && ask "EDITING LOAD ORDER FILE: $FILE_PATH"
# GECK scripts live INSIDE plugins (SCPT records), but loose .gek/.txt fragment exports may exist:
echo "$FILE_PATH" | grep -qiE 'Data/NVSE/' && ask "EDITING NVSE FILE: $FILE_PATH"

# === MO2 INSTANCE -- mods/profiles/overwrite live here, not in Data/ ===
# the YesMan AI installer replaces {{MO2_INSTANCE}} with the instance path; the generic "Mod Organizer"
# fallback catches typical portable-instance folder names even before substitution.
echo "$FILE_PATH" | grep -qiE '({{MO2_INSTANCE}}|Mod ?Organizer)' && ask "Editing file in MO2 instance (mods/profiles/overwrite): $FILE_PATH"

# === CATCH-ALL -- any file in game directory or config directory ===
echo "$FILE_PATH" | grep -qiE '(Fallout New Vegas|My Games/FalloutNV|AppData/Local/FalloutNV)' && ask "Editing file in game/config directory: $FILE_PATH"

exit 0

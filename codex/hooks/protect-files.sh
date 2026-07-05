#!/bin/bash
# Codex PreToolUse hook (matcher: apply_patch) — protect game/config files from
# unnoticed edits. Binary plugin/archive files are hard-blocked; edits in the game,
# config, or MO2 directories require confirmation.
#
# KEY DIFFERENCE from the Claude variant: Claude gave a clean `.tool_input.file_path`.
# Codex routes file edits through `apply_patch`, where `.tool_input.command` holds the
# PATCH TEXT and the affected paths live in `*** Add/Update/Delete/Move to File:` headers.
# One apply_patch may touch several files, so we extract ALL of them and evaluate each.
# (We still read `.tool_input.file_path` first, in case a Codex build supplies a clean path.)
#
# SETUP: the YesMan AI installer (installer/configure.py) fills in {{JQ_PATH}} below.

JQ="{{JQ_PATH}}"

INPUT=$(cat /dev/stdin)

# Clean path if provided; otherwise parse the apply_patch headers.
FILES=$(echo "$INPUT" | "$JQ" -r '.tool_input.file_path // empty')
if [ -z "$FILES" ]; then
    CMD=$(echo "$INPUT" | "$JQ" -r '.tool_input.command // empty')
    FILES=$(printf '%s\n' "$CMD" | grep -oiE '\*\*\* (Add|Update|Delete|Move to) File: .+' \
                                 | sed -E 's/^\*\*\* (Add|Update|Delete|Move to) File: //')
fi
[ -z "$FILES" ] && exit 0

deny() { "$JQ" -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'; exit 0; }
ask()  { "$JQ" -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'; exit 0; }

# === HARD BLOCK -- binary plugin/archive files (FNV: esm/esp/bsa only), any file in the patch ===
printf '%s\n' "$FILES" | grep -qiE '\.(esp|esm|bsa)$' && deny "BLOCKED: Cannot directly write to plugin/archive files. Use xEditLib, an xEdit Apply Script, or the GECK."

# === Per-file confirmation rules (first match asks) ===
while IFS= read -r FILE_PATH; do
    [ -z "$FILE_PATH" ] && continue

    # WHITELIST -- our own workspace (no confirmation needed)
    echo "$FILE_PATH" | grep -qiE '\.(codex|claude)/(hooks|plans|backups|memory|skills)/' && continue
    echo "$FILE_PATH" | grep -qiE '\.(codex|claude)/projects/' && continue
    echo "$FILE_PATH" | grep -qiE '\.agents/skills/' && continue

    # HIGH-PRIORITY CONFIRM (specific message)
    echo "$FILE_PATH" | grep -qiE '(Fallout\.ini|FalloutPrefs\.ini|FalloutCustom\.ini)$' && ask "EDITING FNV CONFIG: $FILE_PATH"
    echo "$FILE_PATH" | grep -qiE 'Data/NVSE/Plugins/.*\.ini$' && ask "EDITING NVSE PLUGIN CONFIG: $FILE_PATH"
    echo "$FILE_PATH" | grep -qiE '(loadorder\.txt|plugins\.txt|NVDLCList\.txt)$' && ask "EDITING LOAD ORDER FILE: $FILE_PATH"
    echo "$FILE_PATH" | grep -qiE 'Data/NVSE/' && ask "EDITING NVSE FILE: $FILE_PATH"

    # MO2 INSTANCE -- mods/profiles/overwrite live here, not in Data/
    echo "$FILE_PATH" | grep -qiE '({{MO2_INSTANCE}}|Mod ?Organizer)' && ask "Editing file in MO2 instance (mods/profiles/overwrite): $FILE_PATH"

    # CATCH-ALL -- any file in game directory or config directory
    echo "$FILE_PATH" | grep -qiE '(Fallout New Vegas|My Games/FalloutNV|AppData/Local/FalloutNV)' && ask "Editing file in game/config directory: $FILE_PATH"
done <<EOF
$FILES
EOF

exit 0

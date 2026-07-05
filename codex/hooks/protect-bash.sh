#!/bin/bash
# Codex PreToolUse hook (matcher: Bash) — protect against destructive or file-modifying
# shell commands in a Fallout: New Vegas modding environment.
#
# Codex delivers the same shape Claude Code did: the shell command is at
# `.tool_input.command`, and a hook denies/asks by printing a hookSpecificOutput JSON.
# So this script is unchanged from the Claude variant except for these comments.
#
# NOTE: "deny" is honored by Codex PreToolUse. "ask" (confirm) is best-effort — if a Codex
# build doesn't honor an "ask" decision, its own approval policy still gates the command;
# the hard "deny" blocks below always apply.
#
# SETUP: the YesMan AI installer (installer/configure.py) fills in {{JQ_PATH}} below.

JQ="{{JQ_PATH}}"

INPUT=$(cat /dev/stdin)
COMMAND=$(echo "$INPUT" | "$JQ" -r '.tool_input.command // empty')

deny() { "$JQ" -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'; exit 0; }
ask()  { "$JQ" -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'; exit 0; }

# === HARD BLOCK ===
# Prevent deleting the game installation directory (matches "Fallout New Vegas" or "FalloutNV")
echo "$COMMAND" | grep -qiE 'rm\s+(-[a-z]*f[a-z]*\s+)?["'"'"']?(C:/|/c/|D:/|/d/).*(Fallout New Vegas|FalloutNV)' && deny "BLOCKED: Cannot delete the game installation directory."
# Prevent deleting the FNV config directory
echo "$COMMAND" | grep -qiE 'rm\s+(-[a-z]*f[a-z]*\s+)?["'"'"']?(C:/|/c/).*(My Games/FalloutNV|AppData/Local/FalloutNV)' && deny "BLOCKED: Cannot delete the Fallout New Vegas config/appdata directory."
# Prevent deleting Bethesda registry keys
echo "$COMMAND" | grep -qiE '(reg\s+delete|Remove-ItemProperty.*Bethesda)' && deny "BLOCKED: Cannot delete Bethesda registry keys."

# === CONFIRM -- destructive commands ===
echo "$COMMAND" | grep -qiE 'rm\s.*(Fallout New Vegas|FalloutNV|/Data/)' && ask "Deleting files in game directory -- confirm: $COMMAND"

# === CONFIRM -- any command that modifies files in game/config directories ===
echo "$COMMAND" | grep -qiE '(mv|cp|move|copy)\s.*(Fallout New Vegas|FalloutNV|/Data/|/My Games/FalloutNV)' && ask "Moving/copying files in game directory -- confirm: $COMMAND"
echo "$COMMAND" | grep -qiE '>\s*["'"'"']?(C:/|/c/|D:/|/d/).*(Fallout New Vegas|FalloutNV)' && ask "Redirecting output to game/config directory -- confirm: $COMMAND"
echo "$COMMAND" | grep -qiE 'sed\s+-i.*(Fallout New Vegas|FalloutNV|/Data/|/My Games/FalloutNV)' && ask "In-place edit in game directory -- confirm: $COMMAND"

# === CONFIRM -- operations inside the MO2 instance (mods/profiles/overwrite) ===
echo "$COMMAND" | grep -qiE '(rm|mv|cp|move|copy|sed\s+-i)\s.*({{MO2_INSTANCE}}|Mod ?Organizer)' && ask "Modifying files in the MO2 instance -- confirm: $COMMAND"

# === CONFIRM -- plugin/archive/load order references ===
# Note: FNV has no .esl or .ba2 -- only .esm/.esp/.bsa
echo "$COMMAND" | grep -qiE '\.(esp|esm|bsa)\b' && ask "Command references plugin/archive files -- confirm: $COMMAND"
echo "$COMMAND" | grep -qiE '(loadorder\.txt|plugins\.txt|NVDLCList\.txt)' && ask "Command references load order -- confirm: $COMMAND"

exit 0

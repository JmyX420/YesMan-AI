#!/bin/bash
# Codex PreToolUse hook (matcher: apply_patch) — auto-backup any file before Codex edits
# it. Saves to .codex/backups/ with a timestamp and logs to an audit trail.
#
# Like protect-files.sh, the affected paths come from the apply_patch header text (or a
# clean `.tool_input.file_path` if a build supplies one). We back up files that ALREADY
# EXIST, i.e. Update/Delete targets — an "Add File" has nothing to back up yet. Paths in a
# patch are relative to the session cwd, so we resolve them against `.cwd` from the input.
#
# SETUP: the YesMan AI installer (installer/configure.py) fills in {{JQ_PATH}} below.

JQ="{{JQ_PATH}}"

INPUT=$(cat /dev/stdin)
TOOL_NAME=$(echo "$INPUT" | "$JQ" -r '.tool_name // "unknown"')
CWD=$(echo "$INPUT" | "$JQ" -r '.cwd // empty')

# Clean path if provided; otherwise parse Update/Delete headers (existing files only).
FILES=$(echo "$INPUT" | "$JQ" -r '.tool_input.file_path // empty')
if [ -z "$FILES" ]; then
    CMD=$(echo "$INPUT" | "$JQ" -r '.tool_input.command // empty')
    FILES=$(printf '%s\n' "$CMD" | grep -oiE '\*\*\* (Update|Delete) File: .+' \
                                 | sed -E 's/^\*\*\* (Update|Delete) File: //')
fi
[ -z "$FILES" ] && exit 0

BACKUP_DIR="${CWD:-.}/.codex/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
AUDIT_LOG="$BACKUP_DIR/AUDIT_LOG.txt"

while IFS= read -r FILE_PATH; do
    [ -z "$FILE_PATH" ] && continue
    # Resolve relative paths against cwd (absolute = leading / or a drive letter like C:).
    case "$FILE_PATH" in
        /*|?:*|?:\\*) ABS="$FILE_PATH" ;;
        *)            ABS="${CWD%/}/$FILE_PATH" ;;
    esac
    [ ! -f "$ABS" ] && continue
    # Skip our own transient workspace files.
    echo "$ABS" | grep -qiE '(\.codex/backups/|\.codex/hooks/|\.claude/backups/|\.claude/hooks/|node_modules/)' && continue

    SAFE_NAME=$(echo "$ABS" | sed 's|[/\\:]|_|g' | sed 's|^_*||')
    cp "$ABS" "$BACKUP_DIR/${TIMESTAMP}__${SAFE_NAME}" 2>/dev/null
    echo "[$TIMESTAMP] $TOOL_NAME -> $ABS (backup: ${TIMESTAMP}__${SAFE_NAME})" >> "$AUDIT_LOG"
done <<EOF
$FILES
EOF

exit 0

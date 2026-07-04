#!/bin/bash
# AutoMod CLI wrapper — Fallout: New Vegas.
# Usage: bash tools/automod-cli.sh <module> <command> [args] --json [--dry-run]
#   modules: esp · mcm · bsa · audio · nif
# Always pass --json for parseable output; always --dry-run first for writes.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec node "$DIR/automod/cli.js" "$@"

---
name: inspect-esp
description: Inspect a Fallout New Vegas ESP/ESM plugin and summarize its records, masters, and potential issues.
argument-hint: <PluginName.esp>
---

# Inspect FNV Plugin

Inspect the plugin specified by `$ARGUMENTS` and give a structured summary. Uses **xEditLib in FNV mode (`GM_FNV=0`)** — there is no Spriggit/YAML path for FNV.

**Detect-and-prefer the MO2 MCP.** If `mcp__mo2__*` tools are available (the bundled MO2 plugin is running — see CLAUDE.md), **prefer them** — they read the plugin on your **live modded load order** with no VFS hassle (they stage the plugin + its masters automatically):
- `mo2_query_records "$ARGUMENTS" [--sig WEAP] [--match …]` → records the plugin defines/overrides.
- `mo2_record_detail "$ARGUMENTS" <EditorID|FormID>` → full field tree of one record (resolved references).
- `mo2_plugin_info "$ARGUMENTS"` → masters, load order, flags, missing-master check.
- For conflicts/who-wins, see the `patch-compat` skill (`mo2_conflict_chain`/`plugin_conflicts`).

Otherwise use the CLI/xEditLib workflow below (works without the MCP).

## Workflow

1. Run the validated inspector (reads the FNV game path from the registry automatically):
   ```bash
   node examples/inspect-esp.js "$ARGUMENTS"
   ```
   It prints: file name, masters, a record-type breakdown (by signature), and a sample of records.

2. For deeper/targeted analysis, write a small xEditLib script (see `docs/xeditlib-guide.md`) — e.g. to find all `SPEL` with a given effect, or to diff against another plugin (`examples/diff-esp.js`).

3. **Read scripts directly:** FNV stores GECK script source in the `SCTX` subrecord of `SCPT` records — no decompiler needed. Pull it via `getValue(rec, 'SCTX')`.

## MO2 caveat (important — only when NOT using the MCP)
The MO2 MCP tools above sidestep this entirely (they stage the plugin + masters for you). It only matters for the raw CLI/`examples/` path: xEditLib loads from the game `Data/` folder, and under **Mod Organizer 2** an installed mod's plugin is **not** in `Data/` unless this runs **through MO2's VFS**. To inspect a mod that way:
- run the command through MO2 (add `node` as an MO2 executable), **or**
- read the plugin directly from `mods/<ModName>/<Plugin>` and load it explicitly, **or**
- pass a game path whose `Data/` actually contains it.

## Output format
- **File info**: name, masters, ESM/ESP flag, record count
- **Record breakdown**: count per signature (`WEAP`, `NPC_`, `SCPT`, `DIAL`/`INFO`, `NAVM`, …)
- **Notable records**: editor IDs + brief descriptions
- **Scripts**: any `SCPT`/embedded result scripts (show `SCTX` source)
- **Potential issues**: navmesh present (→ should be ESM), deleted refs (UDR), missing masters, FormID/load-order concerns

## Safety
Read-only. Never call `SaveFile`. The file/bash hooks block direct `.esp/.esm` writes regardless.

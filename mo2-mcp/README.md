# FNV MO2 MCP Server

A bundled **Mod Organizer 2 plugin** that gives Claude Code **live** awareness of your
modded Fallout: New Vegas setup — the virtual file system, the active load order, and
cross-plugin conflicts — while MO2 is open. A component of YesMan AI, installed with the
toolbox. A Fallout: New Vegas port of **Aaronavich's MO2 MCP Server** (MIT). See
[`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md).

The skills **use it automatically** when it's running, and fall back to the AutoMod CLI /
through-MO2 workflows when MO2 is closed — so the toolbox keeps working either way.

## Why it exists

Standalone xEdit/xEditLib only sees vanilla `Data/`. Your real mods live in the MO2
instance and load through MO2's USVFS overlay, so the *merged, modded* load order — the
one that actually matters for conflicts — isn't visible to plain tooling. This plugin runs
**inside MO2**, so it can answer questions about the live VFS and modded order directly.

## What Claude can do with it (`mcp__mo2__*` tools, ~26)

- **Modlist & load order** — `mo2_list_mods`, `mo2_list_plugins`, `mo2_plugin_info`,
  `mo2_mod_info`: enabled mods in priority order, the active plugin list, per-mod/per-plugin detail.
- **VFS file access** — `mo2_resolve_path`, `mo2_read_file`, `mo2_list_files`: resolve a
  game-relative path through the overlay to the winning mod, read it, list a virtual dir.
- **Records on the modded order** — `mo2_query_records`, `mo2_record_detail`: read records
  as the *modded* load order sees them (not just vanilla `Data/`).
- **Conflicts & patches** — `mo2_find_conflicts`, `mo2_conflict_chain`, `mo2_plugin_conflicts`,
  `mo2_conflict_summary`, `mo2_create_patch`: who-wins analysis across the load order and
  one-command compatibility patch creation (dry-run first).
- **Assets** — BSA (`mo2_list_bsa`, `mo2_extract_bsa`, `mo2_extract_bsa_file`,
  `mo2_validate_bsa`), audio (`mo2_audio_info`, `mo2_convert_audio`), NIF (`mo2_nif_info`,
  `mo2_nif_list_textures`, `mo2_nif_shader_info`), NVSE DLLs (`mo2_analyze_dll`) — all with
  VFS path resolution done for you.
- **Write** — `mo2_write_file` (creates new files only, in the configured output mod).
- **Status** — `mo2_ping`, `mo2_version`.

Record/conflict/patch and the asset tools are backed by the **same** AutoMod CLI engine
(xEditLib `GM_FNV=0`, BSArch `-fnv`, oggenc2, the toolbox's NIF reader) used everywhere
else, so results are consistent whether you use the MCP or the CLI — the MCP just adds the
live VFS + load-order context.

## Requirements

- **Mod Organizer 2** (this plugin lives in MO2's `plugins/` and runs in MO2's Python).
- YesMan AI (for the AutoMod CLI backend).
- Claude Code (the server registers itself in `~/.claude.json` as the `mo2` MCP server).

## Install

**The YesMan AI installer deploys this for you** — it copies the plugin into the MO2
instance you pick during setup. You just enable it: in MO2 open **Settings → Plugins →
FNV MO2 MCP Server**, then restart MO2 + Claude Code. `automod-path` defaults to
auto-detect (the toolbox in your game folder), so there's nothing to set. The server
auto-starts when MO2 opens (default port **49200**), so the `mcp__mo2__*` tools are
available whenever MO2 is running.

*Manual/standalone deploy* (if you're not using the installer): `bash
mo2-mcp/install-to-mo2.sh "<your MO2 folder>"`.

## Notes

- **Detect-and-prefer, never require.** If `mcp__mo2__*` tools aren't in the session (not
  installed, or MO2 closed), every workflow still works via the AutoMod CLI or by running
  xEdit/FNVEdit through MO2. Nothing depends on the MCP.
- It only adds awareness it can't get otherwise; it does not replace the GECK or FNVEdit's
  GUI conflict view for the deep, manual work.

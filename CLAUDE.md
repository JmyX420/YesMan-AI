# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in a Fallout: New Vegas modding environment.

## What This Is

A modded Fallout: New Vegas installation. (Adapt paths to your setup. Works for vanilla FNV, heavily-modded FNV, and Tale of Two Wastelands / TTW installs.)

## Key Paths

> **This install is managed by Mod Organizer 2 (MO2).** Open Claude Code in the **game root** (project dir), but understand that **your mods do NOT live in `Data/`** — they live in the MO2 instance. Read "Mod Organizer 2 Layout" below before touching anything mod-related.

- **Game root (project dir)**: `{{GAME_ROOT}}/` — mostly vanilla + DLC; `Data/` does **not** contain your installed mods under MO2.
- **MO2 instance**: `{{MO2_INSTANCE}}/`
- **Active MO2 profile**: `{{MO2_PROFILE}}` → `{{MO2_INSTANCE}}/profiles/{{MO2_PROFILE}}/`
- **Real mods**: `{{MO2_INSTANCE}}/mods/<ModName>/` — each mod is a folder mirroring `Data/` layout (meshes/, textures/, NVSE/Plugins/, *.esp, …)
- **Load order**: `{{MO2_INSTANCE}}/profiles/{{MO2_PROFILE}}/plugins.txt` (active + order), `loadorder.txt`, `modlist.txt` (MO2 install priority, `+`=enabled), `archives.txt`
- **Loose/generated output**: `{{MO2_INSTANCE}}/overwrite/`
- **User INI configs**: `{{DOCUMENTS_DIR}}/My Games/FalloutNV/` (`Fallout.ini`, `FalloutPrefs.ini`, `FalloutCustom.ini`) — MO2 may use **profile-specific INIs** under the active profile instead.
- **Script extender**: NVSE — `nvse_1_4.dll` at game root; NVSE plugin DLLs live in each mod's `NVSE/Plugins/` and merge into `Data/NVSE/Plugins/` only at runtime via the VFS.

## Mod Organizer 2 Layout (How Mods Actually Load)

MO2 uses a **virtual file system (VFS, USVFS)**. When you launch the game/tools *through MO2*, it overlays every enabled mod folder (in `modlist.txt` priority order) plus `overwrite/` on top of the real `Data/`. **On disk, those files stay in the MO2 instance — they are never copied into `Data/`** (unlike Vortex, which hardlinks into `Data/`).

**Consequences for Claude — internalize these:**
- **`Data/` looks almost empty of mods.** To read/edit an installed mod, work in `{{MO2_INSTANCE}}/mods/<ModName>/` (real files on disk, directly readable).
- **The "true" load order is the MO2 profile**, not `AppData/.../plugins.txt`. Parse `profiles/{{MO2_PROFILE}}/plugins.txt` + `loadorder.txt` + `modlist.txt`.
- **Standalone xEdit/xEditLib only sees vanilla `Data/`.** To inspect the *merged, modded* load order, **run xEdit/FNVEdit through MO2** (add it as an MO2 executable so the VFS is active), or feed xEditLib the explicit per-mod data paths.
- **New files Claude generates that the game must load** (via MO2) belong in `overwrite/` or a dedicated mod folder under `mods/`, then enabled in MO2 — not dropped into `Data/`.
- **Conflict resolution is two-layered**: MO2 *asset* conflicts (later mod in `modlist.txt` wins for loose files) and *plugin* conflicts (later in `plugins.txt`/load order wins for records). Loose files still override BSAs.

## Engine at a Glance (and how FNV differs from Skyrim)

FNV runs on **Gamebryo / "Gamebryo NetImmerse"** (the same engine family as Fallout 3 and Oblivion), **not** Creation Engine. If you know Skyrim modding, internalize these differences first:

| Topic | Skyrim | Fallout: New Vegas |
|------|--------|--------------------|
| Script extender | SKSE | **NVSE** (xNVSE is the maintained build) |
| Scripting language | Papyrus (`.psc` source, `.pex` compiled, external files) | **GECK script / "GECKScript"** (compiled into the plugin as `SCPT` records; **source text preserved in the `SCTX` subrecord**) |
| Plugin types | ESM / ESP / ESL | **ESM / ESP only** — no ESL, no light plugins, hard **254-plugin** ceiling |
| Editor | Creation Kit | **GECK** (Garden of Eden Creation Kit) + GECK Extender / NVSE GECK |
| xEdit | SSEEdit (`gmSSE=4`) | **FNVEdit (`gmFNV=0`)** |
| Archives | BSA + BA2 | **BSA only** (older archive version) |
| Voice/audio | FUZ (XWM + LIP) | **`.ogg` + `.lip`** (no FUZ, no XWM; MP3 not valid inside BSAs) |
| Config menus | SkyUI MCM | **The Mod Configuration Menu** (Pelinor's MCM) — different format |
| Save files | `.ess` (LZ4) | **`.fos`** (Gamebryo save format) |
| Mesh format | NIF (file 20.2.0.7, User 12 / BS 83) | **NIF (file 20.2.0.7, User 11 / BS 34 — same as FO3)** — same version number as Skyrim LE but different User/BS version, not cross-compatible |

> **Do not assume Skyrim behavior carries over.** The engine, scripting model, and tooling are materially different. Verify against FNV/GECK sources, not Skyrim knowledge.

## Installed / Expected Modding Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **xNVSE** | Runtime script extender | Required by most script mods. `nvse_loader.exe` / Steam loader |
| **FNVEdit (xEdit)** | Conflict detection, record viewing/editing, **Apply Scripts** (Pascal) | The workhorse for plugin work |
| **XEditLib.dll** | Programmatic ESP/ESM read/write via FFI (Node.js) | Use game mode `gmFNV=0`. See ESP backbone below |
| **BSArch** | BSA read / extract / create | FNV BSA archive version |
| **GECK + GECK Extender** | Official editor (GUI, manual) | For navmesh, complex scripts, dialogue, cells |
| **NifSkope / nifly** | NIF mesh inspection/editing | FNV NIF version |
| **AutoMod CLI** | One JSON interface over 11 modules (esp/mcm/bsa/audio/nif/lod/fomod/crashlog/funcs/ini/build) | `bash tools/automod-cli.sh <module> <command> --json` — see below |

## AutoMod CLI (preferred for routine tasks)

A single JSON-emitting CLI wrapping the toolbox's operations — use it instead of hand-writing a script for common jobs. **Always `--json`; always `--dry-run` first for writes.** Full reference: `docs/automod-cli.md`.

```bash
bash tools/automod-cli.sh <module> <command> [args] --json [--dry-run]
```
| Module | Backend | Does |
|--------|---------|------|
| `esp` | xEditLib (`gmFNV=0`) | `info`, `query <plugin> [--sig][--match]`, `record <plugin> <id>` (read-only), `create`, `add-misc/note/global/weapon/armor`, `add-record --set PATH=VAL` |
| `mcm` | JSON generation | `create`, `add-toggle/slider/dropdown`, `validate` (verified Tweaks/MenuConfig schema) |
| `bsa` | BSArch `-fnv` | `list`, `unpack`, `pack`, `extract-file` |
| `audio` | oggenc2 | `wav-to-ogg` (24kHz mono), `info` (`.lip` is GECK-only) |
| `nif` | self-built (+ optional `nif_info`) | `info`, `list-textures`, `replace-textures` (same-length, auto-`.bak`), `inspect` |
| `lod` | FNVLODGen/xLODGen orchestration | `tools`, `check-assets`, `verify-output`, `generate` (launch-helper) — toolbox drives the tool + does pre/post; see `fnv-lod` skill |
| `fomod` | FOMOD installer XML | `init`, `validate`, `types` — only for mods with install-time choices; see `fnv-fomod` skill |
| `crashlog` | Crash-log parsing | `analyze` (NVAC + modern loggers → exception, suspect modules, plugins), `find`; see `fnv-crashlog` skill |
| `funcs` | NVSE function index | `list <dll> [--grep]`, `scan <dir>` — heuristic extraction from installed extender DLLs; geckwiki is authoritative. See KB → NVSE Function Reference |
| `ini` | INI audit (read-only) | `audit [<ini>]` — flags known-harmful/placebo/dangerous game-INI tweaks. See KB → INI Tuning |
| `build` | MSVC wrapper (native NVSE plugin) | `detect` (vswhere/toolset/x86), `scaffold`, `compile` (`Enter-VsDevShell -arch=x86` + MSBuild Win32/Release/MT), `verify` (dumpbin exports + x86). Drives **your** MSVC; bundles no compiler. See `nvse-plugin` skill |

Tools (BSArch/oggenc2/nif_info) are auto-detected in the game folder/PATH; missing ones return a clear error. `nif` different-length edits / geometry → NifSkope.

## MO2 MCP server (detect-and-prefer at runtime)

YesMan AI includes a Mod Organizer 2 plugin (`mo2-mcp/`), installed with the toolbox by the YesMan AI installer. When MO2 is open with it enabled, the session has **`mcp__mo2__*` tools** that give live MO2 awareness the CLI can't: the virtual file system, the active load order, cross-plugin conflict/override analysis, and record reading on the **modded** order.

**Detect-and-prefer rule.** The plugin ships with the toolbox, but it only *runs* while MO2 is open. If `mcp__mo2__*` tools are present in the session → **prefer them** for the tasks below. If they're absent (MO2 closed, or a non-MO2 / Vortex / manual setup), **fall back to the AutoMod CLI / through-MO2** — every workflow still works without the MCP. **Never assume it's running; never require it at runtime.**

| Task | Prefer (MCP, if running) | Fallback (always works) |
|------|--------------------------|-------------------------|
| Mods / plugins / load order | `mo2_list_mods` · `mo2_list_plugins` · `mo2_plugin_info` | read the MO2 profile files directly |
| Resolve / read a VFS file | `mo2_resolve_path` · `mo2_read_file` · `mo2_list_files` | resolve the mod-folder path by hand |
| Read records (modded order) | `mo2_query_records` · `mo2_record_detail` | `automod esp query`/`record` (plugin must be in `Data`) |
| **Conflicts / who-wins** | `mo2_conflict_chain` · `mo2_plugin_conflicts` · `mo2_conflict_summary` | FNVEdit conflict view (GUI, manual) |
| **Compatibility patch** | `mo2_create_patch` (dry-run first) | `automod esp` override + FNVEdit |
| BSA / NIF / audio / NVSE-DLL | `mo2_list_bsa` · `mo2_nif_info` · `mo2_audio_info` · `mo2_analyze_dll` (resolve VFS paths for you) | the matching AutoMod module with a resolved absolute path |

The MCP's record/conflict/patch tools are backed by this **same** AutoMod `esp`/xEditLib engine, so results are consistent either way — the MCP just adds the live VFS + load-order context.

## YesMan AI Live Link (running-game control)

YesMan AI includes a real-time link to a *running* game (`live-link/`), installed with the toolbox. When FNV is running with a save loaded, the session has **`fnv_*` tools** (`fnv_link_status`, `fnv_get_player_state`, `fnv_poll_events`, `fnv_console`, `fnv_run_script`, `fnv_message`, and typed command wrappers) to observe, react to events in, and command the live game. Driven by the **`fnv-live-link`** skill — call `fnv_link_status` first; commands queue when the game is paused/unfocused. It only *works* while the game is live and is unrelated to the offline modding workflows; **never assume it's active** (the game may be closed). Full details: `live-link/README.md`.

## ESP Editing Backbone (READ THIS)

**Spriggit/Mutagen does NOT support Fallout: New Vegas** (FNV is absent from Mutagen's supported game list — [Mutagen #22](https://github.com/Mutagen-Modding/Mutagen/issues/22)). The Skyrim toolkit's "serialize to YAML, edit, deserialize" workflow is **not available here.** Use these instead:

1. **XEditLib.dll via the `xeditlib` Node wrapper** — programmatic read/edit/diff/bulk-query. Load with game mode `gmFNV=0`. Best for inspection, traversal, diffing, and scripted edits.
2. **xEdit / FNVEdit Apply Scripts (Pascal)** — load plugins in FNVEdit, right-click → *Apply Script*. Best for batch/repetitive record operations. See [matortheeternal's scripts](https://github.com/matortheeternal/TES5EditScripts) and the [FNVEdit User Scripts](https://www.nexusmods.com/newvegas/mods/52467).
3. **GECK** — for anything xEdit can't safely do: navmesh creation, complex dialogue/quest wiring, and compiling new scripts.

**Reading scripts is easy in FNV:** unlike Skyrim's compiled-only Papyrus, FNV keeps the **script source text in the `SCTX` subrecord** of each `SCPT` record. You can read it directly in xEdit/xEditLib — no decompiler needed.

### XEditLib.dll API (Critical Notes — inherited from the Skyrim toolkit, valid for FNV)
The DLL is Delphi-compiled. These quirks cause hours of debugging:
1. **All strings are UCS-2/UTF-16LE** (Delphi `PWideChar`), never UTF-8.
2. **`InitXEdit()` / `CloseXEdit()` are VOID**, not bool — declaring as bool corrupts the call stack.
3. **`WordBool` = `uint16`** (2 bytes), not bool/uint8.
4. **String return pattern**: functions write a length to a `PInteger` param, then you call `GetResultString(buffer, len)`.
5. **Game mode enum**: **`gmFNV=0`**, gmFO3=1, gmTES4=2, gmTES5=3, gmSSE=4, gmFO4=5. **Use `0` for Fallout: New Vegas.**
6. **Registry requirement**: XEditLib reads the game path from the FNV registry key (`HKLM\SOFTWARE\WOW6432Node\Bethesda Softworks\FalloutNV`, `Installed Path`). Ensure it points at your FNV install.

## INI Config Hierarchy

Settings load in this order (later overrides earlier):
1. `Fallout_default.ini` (game root) — engine defaults
2. `Fallout.ini` — base user settings
3. `FalloutPrefs.ini` — user preferences
4. `FalloutCustom.ini` — **preferred place for manual overrides** (won't be clobbered by the launcher)

## Nexus / Wiki Research (Standing Rule)

**Always research before investigating a mod or engine behavior.** Check, in order: the mod's Nexus page (description, articles, comments, bugs), the [GECK Wiki](https://geckwiki.com), the [Fallout Wiki](https://fallout.wiki), and the xNVSE/NVSE command docs. Most FNV issues are well-documented — this saves enormous time.

## Knowledgebase

`KNOWLEDGEBASE.md` (project root) is the master reference for discovered quirks, gotchas, and FNV/TTW-specific behavior. **Always consult it before making changes.**

**Standing instruction**: After every debugging session, mod investigation, or web research, extract new facts (engine quirks, GECK/NVSE gotchas, tool limitations, TTW differences) and add them to `KNOWLEDGEBASE.md`, with a source. We learn from everything we touch. Prefer **verified facts over speculation** — mark anything unverified.

## Top Gotchas (Always In Context)

These are FNV's most common footguns. See `KNOWLEDGEBASE.md` for detail and sources.

0. **MO2 VFS: mods are NOT in `Data/`** — they live in `{{MO2_INSTANCE}}/mods/`, and the real load order is the MO2 profile. Never assume `Data/` reflects the modded game. (See "Mod Organizer 2 Layout".)
1. **FNV needs the 4GB patch / xNVSE to be stable** — a clean unpatched FNV is crash-prone by design.
2. **GECK scripts are stored inside the plugin (`SCPT`/`SCTX`)** — there are no external `.psc`/`.pex` files to edit.
3. **No ESL / no light plugins** — hard 254-plugin limit (`FormID` load-order byte). Merge plugins to stay under it.
4. **`SCOF`/result scripts and dialogue scripts are embedded** — editing them safely usually means the GECK, not raw record edits.
5. **NVSE must be running** for any NVSE-extended command — vanilla GECK won't compile NVSE commands without an NVSE-aware GECK.
6. **Voice files are `.ogg` + `.lip`** (24kHz mono); `.lip` must match a valid dialogue line or it won't generate.
7. **Loose files always override BSAs** — check `Data/` for loose conflicts before assuming BSA content loads.
8. **`Archive Invalidation`** must be active for loose texture/mesh replacers to take effect.
9. **TTW is a total conversion** — unconverted FO3 mods break it; many plain-FNV mods are TTW-incompatible. Patch deliberately.
10. **Navmesh creation is GECK-only** — xEdit can delete/finalize but not author navmesh.
11. **Saves bloat and corrupt easily** — removing script-heavy mods mid-save leaves orphaned scripts; advise clean saves.
12. **Form version / master order matters** — a plugin's masters must load before it; reordering can break `FormID` references.

> Items 1, 6, 9 are verified this session (see KNOWLEDGEBASE.md sources). Others are well-established FNV community knowledge being confirmed as the knowledgebase is built out — treat any unsourced claim as ~80% until verified.

## Safety Rules

Hooks in `.claude/settings.json` enforce these automatically.

### Hard blocked (cannot proceed)
- Deleting the game installation directory or config/appdata directory
- Deleting Bethesda registry keys
- Directly writing to `.esp` / `.esm` / `.bsa` files (use xEditLib, an xEdit Apply Script, or the GECK)

### Requires user confirmation
- **Any edit to ANY file** in the game directory or config directory (catch-all)
- FNV INI files (`Fallout.ini`, `FalloutPrefs.ini`, `FalloutCustom.ini`)
- NVSE plugin configs (`Data/NVSE/Plugins/*.ini`) and other `Data/NVSE/` files
- Load order files (`plugins.txt`, `loadorder.txt`, `NVDLCList.txt`)
- Any `rm`, `mv`, `cp`, redirect, or `sed -i` touching game/config directories
- Any bash command referencing plugin/archive files

### General rules
- **Always review changes before applying** — FNV installs are fragile.
- Never modify `.esp`/`.esm` directly — use xEditLib programmatically, an xEdit Apply Script, or the GECK.
- **MO2 owns load order and mod files** — edit mods in `{{MO2_INSTANCE}}/mods/<ModName>/`, not `Data/`. Direct edits to `profiles/{{MO2_PROFILE}}/plugins.txt`/`loadorder.txt`/`modlist.txt` are confirmation-gated and may be re-sorted by MO2/LOOT; prefer changing order in MO2 itself.
- Assume the user is knowledgeable about FNV modding and INI settings.

### Audit trail
- Every file edit is auto-backed up to `.claude/backups/` with a timestamp.
- An audit log at `.claude/backups/AUDIT_LOG.txt` records every file touched, when, and by which tool.

## Confidence Levels (Mandatory)

**Before proposing ANY change** to game files, configs, scripts, or plugin records, you MUST:

1. **State a confidence level** (0–100%) for each proposed change.
2. **List assumptions** the confidence depends on.
3. **Investigate before acting**: check `KNOWLEDGEBASE.md`, read the actual records/source, and web-search FNV/GECK/NVSE/TTW specifics. FNV has many engine quirks and built-in bugs — things frequently do NOT work as expected.
4. **Target ≥ 90% confidence** before touching anything. If below, document what's uncertain and what research would raise it.
5. **Never assume Skyrim behavior = FNV behavior.** Different engine, different scripting model.

### Confidence scale
| Range | Meaning | Action |
|-------|---------|--------|
| 95–100% | Verified via testing, docs, or authoritative source | Proceed with user confirmation |
| 80–94% | Strong evidence but not fully verified | Proceed with caveats noted |
| 60–79% | Reasonable assumption, some unknowns | Research more before proceeding |
| < 60% | Speculative | Do NOT proceed — investigate first |

### Investigation checklist (before any change)
- [ ] Consulted `KNOWLEDGEBASE.md` for known quirks
- [ ] Read the actual records / script source involved
- [ ] Checked GECK Wiki / xNVSE docs for FNV-specific behavior
- [ ] Web-searched for known issues with this approach
- [ ] Considered TTW implications (if a TTW install)
- [ ] Considered the rollback path if the change breaks something

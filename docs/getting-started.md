# Getting Started

A first-session walkthrough for YesMan AI.

## Before you start
- **Claude Code** installed and signed in.
- **Node.js** (for the ESP/save tools). `node --version` should work.
- **Python 3** on PATH (for the Live Link relay + the installer's configuration step).
- A **Fallout: New Vegas** install, ideally managed by **Mod Organizer 2**.
- You ran **`YesManAI-Setup-1.0.0.exe`** — it detected your FNV folder, let you pick your MO2 instance, and installed everything (the toolbox, the xEditLib backbone, the MO2 MCP plugin, and the YesMan AI Live Link).

## First session
1. If you use MO2, (re)start it and enable **FNV MO2 MCP Server** (Settings → Plugins) and the **YesMan AI Live Link** mod in the left pane.
2. Open a terminal in your FNV folder and run `claude` (or open the Claude Code app there). The installer already filled `CLAUDE.md`, installed the hooks, and registered the MCP servers — nothing to paste.
3. Sanity-check the ESP backbone: *"read FalloutNV.esm and tell me how many records it has."* Claude runs `node examples/inspect-esp.js` under the hood.
4. Ask Claude which external modding tools you have vs. need (FNVEdit, BSArch, oggenc2, NifSkope, the GECK) for full AutoMod CLI coverage.

## What loads automatically every session
- `CLAUDE.md` — project rules, paths, the confidence system, safety rules.
- `KNOWLEDGEBASE.md` — the FNV reference (consulted before changes).
- The `fnv-context` skill — injects the top gotchas when you touch FNV files.
- The safety hooks — backups + edit confirmation + ESP/ESM/BSA write blocking.

## Try these
- **Inspect a plugin:** `/inspect-esp MyMod.esp` — or just *"what does MyMod.esp change?"*
- **Read a save:** `/fnv-save` then *"list the plugins in my latest save."*
- **Build something:** *"Create a plugin that adds a stimpak that also cures addiction."*
- **Script:** `/geck-scripting` *"write a quest script that..."*
- **Convert an FO3 mod:** `/port-ttw <mod>`
- **Fix a conflict:** `/patch-compat <plugin A> <plugin B>`

## MO2 notes
- Your installed mods are in the **MO2 instance** (`mods/<ModName>/`), not the game `Data/` folder. Claude knows this.
- To work on the **merged, modded load order** with xEdit/xEditLib, run them **through MO2** (add `node`/FNVEdit as an MO2 executable) so the virtual file system is active. For a single plugin, Claude can read it directly from its mod folder.
- New files Claude generates for the game go into a **mod folder** or `overwrite/` and get enabled in MO2 — never dumped into the real `Data/`.

## Included components (installed with the toolbox)
Two components ship and install as part of YesMan AI — no extra steps. They light up when their host is available:
- **MO2 MCP server** (`mo2-mcp/`) — live MO2 awareness *while MO2 is open*: the VFS, the modded load order, cross-plugin conflict/override analysis, and one-command compatibility patches. The skills use it automatically when it's running and fall back to the AutoMod CLI when MO2 is closed. See `mo2-mcp/README.md`.
- **YesMan AI Live Link** (`live-link/`) — a real-time link to your *running* game: a live player/world/quest snapshot, pushed in-game events, and any console command, plus on-screen messages back to you. Active whenever FNV is running with a save loaded (needs the NVSE stack incl. JIP PP LN). See `live-link/README.md`.

## When something breaks
- Claude states a **confidence level** and lists assumptions before changing anything — push back if it's low.
- Every edited file is backed up to `.claude/backups/` with an audit log. To restore, ask Claude or copy the backup back.
- Keep your own saves/backups too. This is a delicate, crash-prone engine.

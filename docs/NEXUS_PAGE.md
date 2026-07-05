# Nexus Mod Page — draft

> Draft copy for the NexusMods description. Nexus uses BBCode; this is written in plain
> markdown for easy editing — convert headings/links to BBCode on upload.

---

## YesMan AI - A FNV Modding Toolbox for Claude and Codex

<!-- MEDIA — Hero banner (~1000px wide). Suggested: New Vegas + Claude Code branding with the tagline below. Replace the placeholder path on upload. -->
![YesMan AI banner — TODO](media/banner.png)

**Turn your Fallout: New Vegas install into an AI-assisted modding workshop.**

This isn't a guide — it's a complete, ready-to-run environment. [Claude Code](https://claude.com/claude-code) or [OpenAI Codex](https://developers.openai.com/codex) becomes a New Vegas modding expert that can write ESP plugins, GECK & NVSE scripts, build entire mods, debug crashes, convert Fallout 3 mods to TTW and much more — all on your own machine, with safety guardrails so it doesn't break your game.

Built from the ground up for Fallout: New Vegas' engine.

### What it does

- **Reads & edits your plugins** programmatically — read, diff, and edit `.esp`/`.esm` records directly, validated against real game files.
- **Writes GECK scripts** — (`SCPT`/`SCTX`, NVSE).
- **Writes _and compiles_ native plugins** — with Visual Studio installed, it can author *and* build a complete xNVSE script-extender plugin (`.dll`), not just GECK scripts.
- **Builds mods from a text description** — records, scripts, MCM menus, assets, etc.
- **Converts FO3 mods to Tale of Two Wastelands** — master-swap + FormID remap, scripted.
- **Makes compatibility patches** and resolves load-order conflicts.
- **Analyzes your saves** (`.fos`) — plugin lists, mod footprint, leftover references.
- **Debugs crashes** using a built-in knowledge of the xNVSE stability stack.
- **Plays alongside you** *(YesMan AI Live Link)* — reads your *running* game's live state, reacts to in-game events, and runs any console command, in real time.

<!-- MEDIA — short GIF (~15s) of Claude building or editing a plugin from a chat prompt: the ask, the dry-run diff, the written .esp. This is the money shot. -->
![Claude building a mod from a prompt — TODO](media/demo-build.gif)

### What's inside

**One integrated toolbox** — a single installer sets up everything below; there are no separate downloads or add-ons to bolt on. The modding core works on any Fallout: New Vegas + MO2 install:

- A **650+ line FNV knowledgebase**, auto-loaded every session and confidence-tagged/sourced.
- An **AutoMod CLI** — one JSON-emitting command over **11 modules** (esp/mcm/bsa/audio/nif/lod/fomod/crashlog/funcs/ini/build) so routine tasks are one line, with `--dry-run` on every write.
- **18 skills** — 16 slash commands (inspect/create/GECK-script/esp-less-mod/NVSE-plugin/nif/bsa/audio/mcm/save/LOD/FOMOD/anim/crashlog/TTW/patching), an always-on context loader, and the Live Link skill.
- **Safety hooks** — asks before editing game files, hard-blocks direct ESP/ESM/BSA writes, auto-backs-up everything with an audit log.
- **MO2-aware** — knows your mods live in the MO2 instance, not `Data/`.

The two components below are **installed with the toolbox** (both MIT-licensed). Each simply lights up when its host is available — the MO2 plugin while MO2 is open, the Live Link while the game is running — and the rest of the toolbox works regardless.

#### Included — MO2 MCP plugin

A Mod Organizer 2 plugin that gives Claude live awareness of your *real modded load order* (otherwise it sees only vanilla `Data/`). **~26 tools**, including:

- **Conflict & override analysis** across your whole load order — who wins each record, and why.
- **One-command compatibility patches** built on the winners.
- **Record reading on the modded order**, plus VFS file access and BSA/NIF/audio/NVSE-DLL inspection.

The skills detect it and prefer it automatically when it's running.

<!-- MEDIA — screenshot of a conflict/override summary or a generated compatibility patch (e.g. mo2_conflict_summary output). -->
![Load-order conflict analysis — TODO](media/mo2-conflicts.png)

#### Included — YesMan AI Live Link

A real-time channel to your *running* game — **18 MCP tools**, eight esp-less GECK scripts + a small Python relay, no plugin DLL. Claude can:

- **Observe** — read a live **23-field** player/world/quest snapshot (position, health, survival needs, gear, caps, active quest…).
- **React** — receive **38 pushed event types**: kills & combat, item pickups/sells/equips, aid use, location discovery, fast-travel, perks, quest/objective progress, VATS/killcam, what NPCs say to you, save/load, and more.
- **Converse** — two-way in-game **text chat** with a persistent, scrollable log (press `\` to talk), plus on-screen messages back to you.
- **Act** — run **any command you could type in the console** (`tgm`, `player.additem`, anything), or any GECK script snippet.

Needs the NVSE stack (incl. JIP PP LN) — see **Install** below.

<!-- MEDIA — screenshot of the in-game chat window (the scrollable You:/Claude: log + input field + Clear/Close buttons) over live gameplay. -->
![In-game two-way chat with Claude — TODO](media/chat-window.png)

**Public tools throughout** — YesMan AI orchestrates xEditLib, FNVEdit, BSArch, NifSkope, oggenc2, the GECK, LOOT, and NVSE. Nothing is locked behind a private service; every part — including the MO2 plugin and the Live Link — is MIT-licensed and installed together by the one installer.

### Requirements

Most FNV-specific tools are only needed for the tasks that use them, and the installer sets up the core backend for you. The full picture:

**You provide (core):**
- An **AI coding agent** — [**Claude Code**](https://claude.com/claude-code) (a Claude Pro/Max subscription) and/or [**OpenAI Codex**](https://developers.openai.com/codex). The installer sets up whichever you choose.
- [**Node.js**](https://nodejs.org/) — powers the ESP/save tooling and the AutoMod CLI.
- [**Python 3**](https://www.python.org/downloads/) — for the Live Link relay and the installer's configuration step.
- **Fallout: New Vegas**, ideally with **Mod Organizer 2** + **xNVSE**.

**The installer sets up for you** (no manual steps):
- **jq** — used by the safety hooks.
- **xEditLib** (the `xeditlib` npm package — bundles `XEditLib.dll` + `FalloutNV.Hardcoded.dat`) — the plugin read/edit engine.
- **The MO2 MCP plugin and the YesMan AI Live Link** — deployed into your chosen MO2 instance and registered with your chosen agent(s) (`~/.claude.json` and/or `~/.codex/config.toml`).

**Optional external tools** — the AutoMod CLI auto-detects these and warns if one's missing; nothing breaks without them, you only need the ones for features you use:
- **FNVEdit / xEdit** — advanced record work + Apply Scripts.
- **BSArch** — BSA archive packing/unpacking (`bsa` module).
- **oggenc2** — audio conversion to FNV's format (`audio` module).
- **NifSkope** or a NIF tool — mesh inspection (`nif` module).
- **the GECK** — the official editor, for tasks that need it.
- **LOOT** — load-order sanity checks.
- **Visual Studio** (with the C++ desktop workload) — required *only* to **compile native xNVSE plugins** (`build` module / `/nvse-plugin`); GECK scripting works without it.

**MO2 MCP plugin** (installed with the toolbox — you only provide the host):
- **Mod Organizer 2** — the installer deploys the plugin into the MO2 instance you pick; it runs in MO2's own Python (no separate Python needed) and reuses the Node/AutoMod backend and Claude Code above. Enable **FNV MO2 MCP Server** in MO2's plugin settings after install.

**YesMan AI Live Link** (scripts + relay installed with the toolbox — you provide the in-game NVSE plugins):
- *In-game, required:* **xNVSE 6.21+** and **JIP PP LN**.
- *In-game, recommended* — each unlocks more of the 38 event types, and the link degrades gracefully without them: **JohnnyGuitar NVSE** (set bJIPFixes = 0 for JIP-PP-LN compatibility — HARD REQUIREMENT), **ShowOff NVSE**, **ITR NVSE**.
- *Optional:* **OneTweak But Really Updated** (set `Active in background` active = true so the game keeps running — and the link stays live — while you tab out to chat with Claude).
- The eight esp-less scripts and the Python relay are installed automatically; enable the **YesMan AI Live Link** mod in MO2 to activate it.

### Install

1. Install **Claude Code** and/or **Codex**, plus **Node.js** and **Python 3** (tick *Add to PATH*).
2. Run **`YesManAI-Setup.exe`**. The wizard auto-detects your Fallout: New Vegas folder, **asks which agent to set up** (Claude Code / Codex / both), lets you pick the **Mod Organizer 2 instance** that manages it (or choose *I don't use MO2*), then installs the whole toolbox — the xEditLib backbone, the MO2 MCP plugin, and the YesMan AI Live Link — and registers the MCP servers with your chosen agent(s).
3. **Restart your agent** (Claude Code / Codex). If you use MO2, restart it and enable **FNV MO2 MCP Server** (Settings → Plugins) and the **YesMan AI Live Link** mod in the left pane.
4. Open your agent in your FNV folder. (Paste `SETUP_PROMPT.txt` for a guided first-session check.) Done.

*The Live Link is only active while FNV is running with a save loaded, and needs the NVSE stack incl. JIP PP LN — see `live-link/README.md`. Advanced users can run the configurator directly instead of the `.exe`: `python installer/configure.py --game-root "<FNV folder>" --agent both`.*

### Notes

- This runs Claude Code locally with your permission for every change; you review before anything is written.
- Always keep your own save/mod backups too — FNV is a fragile engine.

**By JmyX.** MIT licensed. Issues/contributions welcome. Adapted from the **Skyrim Claude Code Toolkit by WingedGuardian** ([skyrimvr-claude-toolkit](https://github.com/WingedGuardian/skyrimvr-claude-toolkit), MIT) — reworked from the ground up for Fallout: New Vegas. The bundled MO2 MCP server is an FNV port of **Aaronavich's MO2 MCP Server** ([Claude_MO2](https://github.com/Avick3110/Claude_MO2), MIT); the Live Link is a re-architecture of the **SkyLink AI** concept by **Jarvann** ([SkyrimMCP](https://github.com/jarvann/SkryimMCM), MIT) onto FNV's NVSE stack. FNV knowledge from the GECK Wiki, xNVSE, Viva New Vegas, Tale of Two Wastelands, and the FNV modding community.

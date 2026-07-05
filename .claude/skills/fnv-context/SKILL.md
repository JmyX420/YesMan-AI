---
name: fnv-context
description: Fallout New Vegas modding context and GECK/NVSE gotchas. Auto-loads when working with FNV plugins, scripts, INIs, NIFs, or Data/ contents.
user-invocable: false
paths: "Data/**,**/*.esp,**/*.esm,**/*.nif,**/*.ini,**/*.fos,**/*.json"
---

# Fallout: New Vegas Modding Context

You are working in a Fallout: New Vegas modding environment (Gamebryo engine, **not** Skyrim's Creation Engine). Consult `KNOWLEDGEBASE.md` in the project root for the full reference. Below are the gotchas that most often cause silent failures, crashes, or wasted time.

## Engine reality check (don't carry Skyrim habits over)
- Script extender is **NVSE/xNVSE**, scripting is **GECK script** stored *inside* plugins (`SCPT`/`SCTX`) — **no `.psc`/`.pex`**, no Papyrus.
- **ESM/ESP only — no ESL/light plugins.** Practical limit **~130–140 plugins** without Mod Limit Fix (254 theoretical).
- **No Spriggit** (Mutagen doesn't support FNV). Edit plugins via **xEditLib** (`GM_FNV=0`), **xEdit Apply Scripts**, or the **GECK**.

## MO2 first (this is usually an MO2 install)
- **Mods are NOT in `Data/`.** They live in the MO2 instance (`mods/<ModName>/`); the real load order is the MO2 **profile**, not `AppData`. Standalone xEdit/xEditLib only sees vanilla `Data/` unless run **through MO2**. (See the MO2 section in `KNOWLEDGEBASE.md`.)
- **Detect-and-prefer the MO2 MCP.** If the mo2 MCP tools are present, the bundled MO2 plugin is running → prefer them for anything MO2-aware (load order, VFS file reads, **records/conflicts on the modded order**, compatibility patches) — they sidestep the "not in `Data/`" problem. If absent (MO2 closed, or a non-MO2 setup), fall back to the CLI/through-MO2 paths; nothing requires the MCP at runtime. See **CLAUDE.md / AGENTS.md → MO2 MCP server**.

## Top gotchas
1. **One script per form** — unlike Papyrus; use a quest script, scripted token, or NVSE `SetEventHandler` for multiple behaviors.
2. **Object scripts only run when the object's cell is loaded** — put always-on logic in a **quest script** (`fQuestDelayTime` ~5 s; `SetQuestDelay`).
3. **GECK script source lives in `SCTX`** — readable directly in xEdit, no decompiler.
4. **NVSE commands need an NVSE-aware GECK** to compile; vanilla GECK rejects them. No native string/array without NVSE.
5. **Navmesh authoring is GECK-only**; **deleted navmeshes CTD**; a mod with navmesh **must be ESM-flagged** (ESP navmesh bug).
6. **Don't clean vanilla** — never undelete navmesh UDRs in official ESMs (startup crash). Clean mods (ITM/UDR) with care.
7. **Voice = `.ogg` (24 kHz mono) + `.lip`**; music = `.mp3`. The `.wav` must be named after the dialogue line for the GECK to make the `.lip`.
8. **NIF = file version 20.2.0.7 (User 11/BS 34)**; FNV uses `BSShaderPPLightingProperty`, **not** Skyrim's `BSLightingShaderProperty`. Same NIF *number* as Skyrim LE but **not interchangeable**.
9. **Loose files override BSAs**; Archive Invalidation must be on for loose texture/mesh replacers.
10. **`.fos` saves are uncompressed** (no LZ4) — byte-scan directly (`scripts/read-fos.js`).
11. **TTW**: FO3 content loads after the NV masters — convert an FO3 mod with the **official zilav FNVEdit script + `TTWConversion.csv`** (handles master-swap + FormID remap), *not* a manual head-byte remap. See `KNOWLEDGEBASE.md → TTW` and the `port-ttw` skill.

## Stability stack to expect
xNVSE · 4GB Patcher · JIP LN + JohnnyGuitar + ShowOff · NVTF · Mod Limit Fix · a crash logger (or NVAC on NVMP). When diagnosing CTDs, check these exist and read `nvse.log` / crash-logger output.

## Before any change
Check `KNOWLEDGEBASE.md`, state a confidence level, and prefer the dry-run path. Never assume Skyrim behavior = FNV behavior.

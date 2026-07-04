---
name: create-mod
description: Guided workflow for creating a new Fallout New Vegas mod (plugin, records, scripts, assets) from scratch.
argument-hint: "[mod description]"
---

# Create a New FNV Mod

Build the mod described by `$ARGUMENTS` step by step. **No Spriggit for FNV** — use xEditLib (`GM_FNV=0`), xEdit Apply Scripts, or the GECK. Always **dry-run first** for any write.

## 1. Scope
Restate the goal, list the records/scripts/assets needed, state a confidence level, and note any KNOWLEDGEBASE gotchas that apply (e.g. one-script-per-form, navmesh→ESM, casting types).

> **Tip:** the **AutoMod CLI** gives one-liner record creation — `bash tools/automod-cli.sh esp create|add-misc|add-weapon|add-armor|add-note|add-global|add-record ... --json [--write]`. See `docs/automod-cli.md`. The xEditLib examples below are the lower-level path.

## 2. Create the plugin
```bash
# dry-run preview first (writes nothing):
node examples/create-esp.js "<ModName>.esp"
# after review, actually write it:
node examples/create-esp.js "<ModName>.esp" --write
```
Adapt `create-esp.js` (or write an xEditLib script — see `docs/xeditlib-guide.md`) to add the records you need: `WEAP`, `ARMO`, `NPC_`, `SPEL`/`MGEF`, `MISC`, `BOOK`, `LVLI`, `FLST`, `QUST`, etc.

## 3. Records — key reminders
- **Weapons/armor need a model** (`MODL`) or they're invisible; **spells need an effect** (`MGEF`) or do nothing.
- Set masters correctly (a mod referencing base content needs `FalloutNV.esm` as a master).
- **No ESL** — keep the active-plugin count down (merge later if needed).

## 4. Scripts (GECK script, not Papyrus)
- Scripts are `SCPT` records *inside* the plugin (source in `SCTX`). Author/edit source, then **compile in an NVSE-aware GECK** (vanilla GECK rejects NVSE commands).
- Choose the right script type: **object** (runs only when loaded), **quest** (always-on, `fQuestDelayTime`), **effect** (`ScriptEffectStart/Update/Finish`). Remember **one script per form**.

## 5. Navmesh (if adding to cells)
- **GECK only.** If the plugin contains navmesh, **flag it ESM** (ESP navmesh bug) and **finalize** in the GECK.

## 6. Assets
- Meshes (NIF 20.2.0.7), textures, audio (`.ogg` 24 kHz + `.lip`), MCM (`fnv-mcm` skill).
- **Under MO2:** write the plugin + assets into a **mod folder** (`mods/<YourMod>/…`) or `overwrite/`, then enable in MO2 — not loose into the real `Data/`.

## 7. Verify
Run `node examples/inspect-esp.js "<ModName>.esp"` to confirm records, masters, and flags. Test in-game.

## Safety
Dry-run every write; review before `--write`/`SaveFile`. Hooks block direct `.esp/.esm/.bsa` edits.

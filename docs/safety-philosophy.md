# Safety Philosophy

Fallout: New Vegas installs are fragile and crash-prone, and modded setups represent hours of careful work. This toolbox assumes **the cost of a silent mistake is high**, so it's built to be cautious by default.

## The layers

1. **Investigate first.** Claude is instructed to consult `KNOWLEDGEBASE.md`, read the actual records/scripts, and research FNV/GECK/NVSE/TTW specifics before acting — because FNV frequently does *not* behave as expected.

2. **Confidence + assumptions, every time.** Before any change to game files, configs, scripts, or records, Claude states a **confidence level (0–100%)** and lists the assumptions it depends on. Target is ≥90%; below that it researches more. No "this should work."

3. **Dry-run before write.** ESP/asset changes go through a preview pass first (e.g. `create-esp.js` previews records and writes nothing until `--write`). You see exactly what will change before it happens.

4. **Hooks enforce it (not just good intentions).** `.claude/settings.json` wires three hooks:
   - **Command guard** (`protect-bash.sh`): hard-blocks deleting the game/config dirs and Bethesda registry keys; asks before any `rm`/`mv`/`cp`/redirect/`sed -i` in game, config, or MO2-instance directories, and before commands referencing plugin/archive/load-order files.
   - **File guard** (`protect-files.sh`): **hard-blocks direct writes to `.esp`/`.esm`/`.bsa`** (those go through xEditLib/xEdit/GECK), and asks before editing anything in the game folder, the FNV INIs, NVSE plugin configs, load-order files, or the MO2 instance.
   - **Auto-backup** (`backup-before-edit.sh`): copies every file to `.claude/backups/` before modifying it, with a timestamped entry in `.claude/backups/AUDIT_LOG.txt`.

5. **Never edit binary plugins blindly.** Direct `.esp/.esm` writes are blocked; edits go through xEditLib (`GM_FNV=0`), an xEdit Apply Script, or the GECK — tools that understand the format.

## What this does NOT replace
- **Your own backups.** Hooks reduce risk; they don't eliminate it. Keep separate copies of saves and important mods.
- **In-game testing.** Claude can build and verify structure, but FNV has engine quirks that only show up in play.
- **Your judgment.** When Claude reports low confidence or lists shaky assumptions, take it seriously.

## MO2 and load order
A mod manager owns your load order and mod files. The hooks gate edits to `plugins.txt`/`loadorder.txt`/`modlist.txt` and the MO2 instance, but prefer making load-order changes **in MO2 itself** — direct edits can be overwritten or re-sorted.

## Improving the guardrails
After a near-miss or surprise, Claude is asked to consider whether a new hook or knowledgebase entry would have caught it, and to note candidates in `KNOWLEDGEBASE.md → Hook Candidates`. The environment is meant to get safer the more you use it.

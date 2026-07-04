---
name: geck-scripting
description: Read, write, and understand Fallout New Vegas GECK scripts (SCPT/SCTX, NVSE). Use for any FNV scripting task — this replaces Papyrus workflows.
argument-hint: "[what the script should do]"
---

# GECK Scripting (FNV)

FNV scripting is **GECK script** ("GECKScript"), **not Papyrus**. See `KNOWLEDGEBASE.md → GECK Scripting` for the full reference.

## Where scripts live
- Scripts are **`SCPT` records inside the plugin**: source text in **`SCTX`**, compiled bytecode in `SCDA`, locals in `SLSD`/`SCVR`. **No external `.psc`/`.pex`.**
- **Read source directly** with xEditLib: `getValue(rec, 'SCTX')` — no decompiler needed.
- Result scripts (dialogue `INFO`, packages, quest stages) are **embedded** in their parent records — edit via the GECK.

## Structure
```
scn MyScriptName
short myVar            ; only declarations go outside a Begin/End block
Begin GameMode
    ; runs every frame while active (object loaded / quest running)
End
```
- Block types: **`GameMode`** (per-frame), **`MenuMode`** (in menus), reference events (`OnActivate`, `OnAdd`, `OnEquip`, `OnHit`, `OnDeath`, `OnLoad`, …).
- Var types: `short`/`long`/`int` (all 32-bit int), `float`, `ref`. `string_var`/`array_var` require **NVSE**.

## Critical rules
- **One script per form** — for multiple behaviors use a **quest script**, a **scripted token**, or NVSE **`SetEventHandler`**.
- **Object scripts only run when the object's cell is loaded** — put always-on logic in a **quest script** (`fQuestDelayTime` ~5 s default; `SetQuestDelay`).
- **Quests**: auto-start on `SetStage`/`SetObjectiveDisplayed`; **`StopQuest`** when done; make stage result scripts idempotent; prefer `GetStage >= N`.
- **`ref` vars go stale** in unloaded cells / for temp objects — null-check (`IsFormValid`).

## NVSE
- xNVSE + JIP LN / JohnnyGuitar / ShowOff add thousands of commands/events.
- NVSE has its own compiler engaged via `Let`/`Eval`/`TestExpr` (`:=` assignment) and inline expressions.
- **Compile only in an NVSE-aware GECK** (GECK through NVSE / GECK Extender) — vanilla GECK rejects unknown NVSE commands.
- **Find functions:** `bash tools/automod-cli.sh funcs list <plugin.dll> --grep <substr>` indexes the installed extenders' functions; confirm signatures on geckwiki "Functions" categories (see `KNOWLEDGEBASE.md → NVSE Function Reference`).

## Workflow
1. Read existing source via `SCTX` (xEditLib) to understand current behavior.
2. Write/modify the source; pick the correct script type.
3. **Compile in an NVSE-aware GECK** (there is no standalone CLI compiler) and save.
4. Verify behavior; log with `PrintC`/`debugprint` (NVSE) — note there's no Papyrus log.

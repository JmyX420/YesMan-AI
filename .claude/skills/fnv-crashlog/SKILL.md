---
name: fnv-crashlog
description: Read and interpret a Fallout New Vegas crash log (modern crash logger or NVAC) to narrow down a CTD. Use when the game crashes and there's a log to analyze.
paths: "**/*crash*.log,**/nvac.log,**/CobbCrashLogger.log"
---

# Crash Log Analysis (FNV)

Help find the cause of a CTD from a crash log. See `KNOWLEDGEBASE.md → Stability / Crash Debugging`.

## First: which log, and where?
- **Modern crash logger (preferred):** **Yvile's Crash Logger** (or Cobb) → readable log with exception + call stack + registers + modules + plugins. If the user doesn't have one, recommend installing it — NVAC alone is poor for diagnosis.
- **NVAC (`nvac.log`):** a terse address trace; it *suppresses* crashes. Useful only to spot an involved module.
- **MO2 gotcha:** logs are usually in the **instance's `overwrite\`** (`overwrite\Root\` or `overwrite\NVSE\`), **not** the game root. `bash tools/automod-cli.sh crashlog find --json` locates them (and flags the overwrite location).

## Analyze
```bash
bash tools/automod-cli.sh crashlog analyze "<path to log>" --json
```
Returns: detected format, the **exception**, **suspect modules** (ranked by appearance, with game/OS/GPU/CRT noise filtered), and **plugin count**. Then read the raw log yourself for context.

## Interpret carefully
- **The top module is NOT automatically the cause** — it's often just where execution was. Don't over-speculate from one frame.
- **Favour frames that resolve to a form/EditorID** (modern loggers print RTTI'd game objects) — those point at actual content (a specific NIF, NPC, cell).
- **Cross-reference each `.dll`** in the call stack to the mod that ships it (search the mod folders / `NVSE/plugins/`), and each plugin to its mod.
- **Patterns:** access violation at a mesh load → a bad/corrupt NIF; crash on cell transition/load door → navmesh or a cell-edit conflict; crash referencing a specific plugin's form → that mod (or a missing master).
- **Reproduce + bisect:** if the log is ambiguous, narrow by disabling mod groups in MO2 until the CTD stops.

## Output
Report: the exception, the most likely suspect(s) (with the caveat), which mod each implicated `.dll`/form maps to, and concrete next steps (verify a NIF, check a plugin/master, disable-to-bisect). Be explicit about confidence — crash logs are suggestive, not conclusive.

## Honesty
- The `crashlog analyze` parser surfaces signals (exception, module frequency, plugin count); **it does not "solve" the crash** — interpretation + the full log are essential.
- NVAC logs rarely pinpoint a cause; treat a frequently-appearing module as a *lead*, not a verdict.

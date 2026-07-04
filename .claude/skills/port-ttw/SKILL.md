---
name: port-ttw
description: Convert a Fallout 3 mod to Tale of Two Wastelands (TTW), or patch a Fallout New Vegas mod for a TTW setup.
argument-hint: "[mod name or path]"
---

# Port to TTW (Tale of Two Wastelands)

Convert the mod in `$ARGUMENTS` for TTW. TTW merges FO3+DLC into FNV on the **FNV engine**. See `KNOWLEDGEBASE.md → Tale of Two Wastelands`. Use **FNVEdit / xEditLib** (`GM_FNV=0`; `GM_FO3=1` to read FO3 sources) — public tools only.

## Decide what's needed
- **Pure-asset mod** (textures/meshes/sound, no plugin) → usually works as-is.
- **Plugin mod** → convert (below).
- **A FNV mod for TTW** → first look for an existing **TTW patch**; otherwise treat conflicts via the `patch-compat` skill against `TaleOfTwoWastelands.esm`.

## FO3 → TTW conversion checklist (official method)
> **Get the original author's permission before converting/redistributing.** Use the official [TTW Mod Conversion Package & Guidelines](https://geckwiki.com/index.php?title=TTW_Mod_Conversion_Package_and_Guidelines) — the FormID remap is **automated by a script + CSV**, not hand-edited.

1. **Add the TTW masters (FNVEdit).** Load `FalloutNV.esm` + 5 NV DLC + `Fallout3.esm` + 5 FO3 DLC + `TaleOfTwoWastelands.esm` and your plugin. Right-click plugin → **Add Masters** (all TTW masters) → **Sort Masters** → **Save and Exit** (do not skip).
2. **Run the official conversion script.** Reload, then right-click → **Run Script** → **TTW Conversion Script** (zilav's) → pick **`TTWConversion.csv`** (matching your TTW version) → let it run. It **remaps every FO3 FormID to its TTW equivalent automatically** — no manual head-byte editing. Save & Exit; reload and re-run if forms straggle.
3. **Recompile scripts one by one in the GECK** — **never "Recompile All."** FOSE scripts need FOSE→NVSE rework.
4. **Engine differences** (check each): navmesh → **must be ESM** + re-finalize + no deleted navmesh; Actor Values (Small Guns→Guns, Throwing→Survival, Detect Life→Turbo, +DT); form types that gained fields (FACT/WEAP/ARMO/PROJ/PERK/…, open in GECK); convert scripted workbenches to the **recipe system**; companion-wheel topics + follower variables; DR/DT, economy, hardcore, leveled lists. (See KNOWLEDGEBASE for the full list.)
5. **Clean** in FNVEdit and **test on a real TTW install.**

## Output
Report: masters added, conversion script + CSV run, scripts recompiled, ESM flag set (if navmesh), engine-difference items addressed, residual conflicts, and recommended in-game tests.

## Verify
`node examples/inspect-esp.js "<Plugin>.esp"` to confirm masters and flags after conversion (run through MO2 if the masters live in the MO2 instance).

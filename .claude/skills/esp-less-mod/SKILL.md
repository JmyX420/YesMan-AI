---
name: esp-less-mod
description: Author an "esp-less" Fallout New Vegas mod — logic as a loose NVSE runtime script (JIP LN Script Runner) plus INI/JSON config, no plugin and no compiled DLL. Use for systems built on JIP LN / JohnnyGuitar / ShowOff like the B42 series.
argument-hint: "[what the mod should do]"
---

# Esp-less Mod (NVSE config-script)

Build a mod whose **logic lives in loose NVSE script + config files**, run at game load by **JIP LN NVSE's Script Runner** — **no `.esp`, no compiled DLL.** This is how systems like the **B42 series** (B42 Optics, FireMode, Melee Bash…) work. See `KNOWLEDGEBASE.md → Mods Without a Plugin §2`. It's all text — the toolbox authors it directly (no `xeditlib`, no compiler).

## When this is the right approach
- The mod is **global logic / a system** (HUD widget, weapon behavior, event reactions), not new records.
- It depends on the script-extender stack (**JIP LN required** — it's the Script Runner — plus often JohnnyGuitar, ShowOff, UIO, lStewieAl's Tweaks).
- Prefer this over a plugin when there are no new GECK records to add. If you need new items/NPCs/quests, use an esp (`create-mod`/`esp`). If you need engine hooks, use `nvse-plugin`.

## The Script Runner (the mechanism)
JIP LN scans `Data\NVSE\plugins\scripts\` and runs `.txt` scripts by **filename prefix on an event**:

| Prefix | Runs on | | Prefix | Runs on |
|--------|---------|-|--------|---------|
| `gr_` | game start | | `gx_` | game exit |
| `gl_` | game load | | `xm_` | exit to main menu |
| `gs_` | game save | | `gn_` | new game |
| **`ln_`** | **new game + every load** (most common) | | | |

Constraints: **≤ 16 KB per file**; near-full NVSE expressions (loops/lambdas) since xNVSE 6.21; **compile errors go to `jip_ln_nvse.log`** (check it when testing). Ref: [JIP LN Script Runner](https://geckwiki.com/index.php?title=JIP_LN_NVSE_Script_Runner_Introduction).

## Workflow
1. **Confirm scope & dependencies.** Restate the goal; list which extenders the logic needs (JIP LN always; + JohnnyGuitar / ShowOff / UIO / lStewieAl / kNVSE as used). State a confidence level.
2. **Pick the event prefix** (usually `ln_`). Filename: `Data\NVSE\plugins\scripts\ln_<ModName>.txt`.
3. **Write the runtime script** — start with a **dependency gate**, then the logic:
   ```
   int bDepMissing
   if GetNVSEVersionFull < 6.21
       printc "<Mod>: update xNVSE (need 6.21+)" | set bDepMissing to 1
   endif
   if GetPluginVersion "JIP LN NVSE" < 5634
       printc "<Mod>: update JIP LN NVSE" | set bDepMissing to 1
   endif
   ; ...repeat for "JohnnyGuitarNVSE", "ShowOffNVSE Plugin", "UI Organizer Plugin" as used...
   if bDepMissing
       return
   endif
   ; --- logic below: register events / build the system ---
   ; e.g.  SetEventHandler "OnFireWeapon" MyHandlerLambda
   ```
   Keep it **under 16 KB** — push bulk data into config files (below) and split into multiple prefixed scripts if needed.
4. **Config / data files** (what the script reads at runtime):
   - **Your data:** `Config\<ModName>\…\*.ini` — section-keyed, often pipe-delimited (e.g. `0=0.804|-3.428|…|path.nif`). Parse with JIP/JG INI/file functions.
   - **lStewieAl Tweaks settings (optional):** `NVSE\plugins\Tweaks\INIs\<ModName>.ini`.
   - **MCM menu (optional):** use the `fnv-mcm` skill → `NVSE\plugins\Tweaks\MenuConfig\<ModName>.json`.
5. **UI (optional):** `menus\prefabs\<ModName>\*.xml`, registered via **UIO** (`fnv-nif`/text editing for the XML).
6. **Assets (optional):** meshes/textures/sounds via the asset skills.
7. **Test:** launch through xNVSE; **check `jip_ln_nvse.log` for compile errors**; verify behavior in-game.
8. **MO2:** put everything in a **mod folder** (`mods/<ModName>/NVSE/plugins/scripts/…`, `…/Config/…`) and enable in MO2 — never loose into the real `Data\`.

## Frameworks to build on (often better than rolling your own)
- **KEYWORDS** — tag categories of forms via `Data\KEYWORDS\<name>.ini` (`KeywordName=EditorID1, EditorID2, …`), then react by tag. Use instead of hardcoding form lists.
- **Base Object Swapper** — swap/transform base objects via `Data\BaseObjectSwapper\*.ini` (or `*_SWAP.ini`), no esp/record edits. `[Forms]` rows: `origBaseID|swapBaseID|transformOverrides|chance` (comma-list the swap field for a random pick; `transformOverrides`=`NONE` or pos/scale; chance = `chanceS/L/R(n)`). E.g. `0x23D63|0x1BBC5|NONE|chanceS(50)`. Ideal for "replace all X with Y" / move/scale.
- **Function libraries** the logic draws on: JIP LN (required + Script Runner), JohnnyGuitar (events/INI/arrays), ShowOff, **SUP** (UI/HUD/menus), **Anh**. Find what's available with `bash tools/automod-cli.sh funcs list <plugin.dll> --grep <substr>`, and **confirm the exact signature on geckwiki** ("Functions (JIP)/(JG)/(ShowOff)") before relying on it.

## Reference example
Reference (a public esp-less mod): **B42 Optics** — `NVSE/plugins/scripts/ln_B42Optics.txt` + `Config/B42Optics/**.ini` + `NVSE/plugins/Tweaks/INIs/B42Optics.ini` + `menus/prefabs/` + assets, **no esp**. Read a mod like it for a real, complex implementation.

## Safety & honesty
- This runs as a script via JIP LN — a logic bug won't crash like a DLL, but can misbehave; **test on a throwaway save** and watch `jip_ln_nvse.log`.
- Declare your **minimum extender versions** in the dependency gate (use the real version ints, e.g. JIP LN `5634` = 56.34).
- State confidence; the NVSE command vocabulary is large — verify functions exist (geckwiki "Functions (JIP)/(JG)/(ShowOff)") before relying on them.

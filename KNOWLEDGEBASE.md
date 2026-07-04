# Fallout: New Vegas Modding Knowledgebase

A living document of quirks, gotchas, and hard-won lessons about Fallout: New Vegas modding (Gamebryo engine, GECK, NVSE, and TTW). Everything here is either verified through debugging, confirmed via authoritative docs/web research, or flagged as **[UNVERIFIED]** pending confirmation. **Always consult this before making changes**, and **prefer verified facts over speculation**.

> Status: **v0.11 — comprehensive** (2026-06-13). Sections, all researched/sourced and mostly verified against a real install: GECK/NVSE scripting · NVSE function reference · MO2 VFS · Foundation/Stability stack · INI tuning · Load-order management · Common CTD signatures · xEdit cleaning/merging/navmesh · BSA archives · Audio (ogg/lip) · NIF meshes · FOMOD installers · MCM · Animations (kNVSE) · Esp-less & frameworks (JIP Script Runner, KEYWORDS, Base Object Swapper) · LOD generation · TTW porting + compatibility patching · `.fos` saves · native NVSE plugins. Living doc. Confidence tags: ✅ verified · 🟡 strong consensus, verification pending · ❓ needs research — only the `.fos` ChangeForm tail (out of scope) and this legend now carry ❓.

---

## Engine Foundation

- FNV runs on **Gamebryo / NetImmerse** — the same engine family as Fallout 3 and Oblivion, **not** Skyrim's Creation Engine. 🟡
- It is a **separate build from Fallout 3**, but very close. This is what makes Tale of Two Wastelands (TTW) possible. 🟡
- XEditLib / xEdit game mode for FNV is **`gmFNV = 0`**. ✅ (game-mode enum inherited from the xEdit/zEdit source; FO3=1, TES4=2, TES5=3, SSE=4, FO4=5)
- **Mutagen does not support FNV** — FNV is not in Mutagen's supported `GameRelease` list, so **Spriggit (ESP↔YAML) cannot be used for FNV.** ✅ ([Mutagen #22](https://github.com/Mutagen-Modding/Mutagen/issues/22))
- Registry: the game path lives under `HKLM\SOFTWARE\WOW6432Node\Bethesda Softworks\FalloutNV` (`Installed Path`). 🟡

---

## Mod Managers & the MO2 Virtual File System ✅

**This toolbox targets Mod Organizer 2 (MO2) first.** MO2 is the most common FNV manager and behaves very differently from Vortex — getting this wrong makes Claude look at the wrong files.

- **MO2 uses a USVFS virtual file system.** Enabled mods are overlaid on `Data/` **only at runtime**, when the game/tools are launched *through MO2*. On disk, mod files **never enter `Data/`**. ✅ (observed directly on a real install: the `Data/` folder stays vanilla + DLC; the installed mods live in the MO2 instance)
- **Vortex, by contrast, hardlinks/deploys files into `Data/`** — so for Vortex the Skyrim-toolkit assumption ("mods are in Data/") holds. MO2 breaks it. 🟡
- **MO2 instance layout** (portable instance observed here):
  - `mods/<ModName>/` — one folder per mod, each mirroring the `Data/` structure (`*.esp`, `meshes/`, `textures/`, `NVSE/Plugins/*.dll`, `sound/voice/…`).
  - `profiles/<Profile>/` — `plugins.txt` (active plugins + order), `loadorder.txt`, `modlist.txt` (MO2 install priority; `+`=enabled, `-`=disabled, lines ending `_separator` are UI separators), `archives.txt`, optional profile-specific INIs.
  - `overwrite/` — catch-all for files generated at runtime (e.g. xEdit output, LOD, cell offsets) that weren't assigned to a mod. **Game-written logs land here too:** `nvse.log` / crash-logger output appear under `overwrite\Root\` (or `overwrite\`), **not** the game root — important when debugging via logs. ✅ (verified)
  - `ModOrganizer.ini` — instance config: `gameName`, `gamePath`, `selected_profile`.
- **`modlist.txt` order:** the **top of the file = HIGHEST priority** (overlaid last → wins loose-file conflicts); the bottom = lowest. ✅ (verified: the priority-1 mod sits at the file's bottom). `+`=enabled, `-`=disabled, lines ending `_separator` are UI separators.
- **Tools must run through MO2 to see the merged view.** Standalone FNVEdit/xEditLib/NifSkope launched outside MO2 see only vanilla `Data/`. Add them as MO2 executables, or point them at explicit per-mod paths. 🟡
- **Reading individual mod files is fine without the VFS** — they're real files at `mods/<ModName>/...`; Claude can read/edit them directly. Only the *merged/load-order-aware* view needs MO2.
- **Two conflict layers:** (1) MO2 loose-asset conflicts resolved by mod priority in `modlist.txt`; (2) plugin record conflicts resolved by load order in `plugins.txt`. Loose files still beat BSAs.

_[expand: profile-specific INI detection; how to register tools/Claude output as an MO2 mod; Vortex deployment specifics when that support is added]_

---

## The Foundation / Stability Stack

FNV is a 32-bit Gamebryo game and is **crash-prone by design** without a foundation of fixes. A modding-ready FNV is built **bottom-up**: script extender → memory/loader → engine bugfix & performance plugins → UI → content. Claude should expect this stack and **check which pieces are present when diagnosing crashes**. The canonical reference is the [Viva New Vegas](https://vivanewvegas.moddinglinked.com/utilities.html) guide. ✅

### The baseline (install in this order)

**1. Script extender — install first.**
- **xNVSE** (the maintained fork; **not** the old Bethesda-era NVSE). DLLs + loader at the **game root**. Everything below depends on it. ✅ ([xNVSE](https://www.nexusmods.com/newvegas/mods/67883))

**2. Memory / loader.**
- **4GB Patcher** — patches `FalloutNV.exe` to be **Large Address Aware** (use up to ~4 GB instead of 2 GB) **and auto-loads xNVSE** (so you can launch the base exe and still get NVSE). Essential before any texture mods. ✅ ([4GB Patcher](https://www.nexusmods.com/newvegas/mods/62552)) — GOG/Epic builds use their own patcher variant.

**3. Engine bugfix / function NVSE plugins** (DLLs in `Data/NVSE/Plugins/`; under MO2 they live in each mod's `NVSE/Plugins/`):
- **JIP LN NVSE** — hundreds of new functions + **many engine bug fixes**. ✅
- **JohnnyGuitar NVSE** — more functions/events + fixes (complements JIP). ✅
- **ShowOff xNVSE** — more functions + engine tweaks. 🟡
- **lStewieAl's Tweaks** — large configurable bug-fix/QoL/INI-tweak library (`nvse_stewie_tweaks.ini`). 🟡
- **FNV Mod Limit Fix** — fixes the **"plugin limit bug"**: the engine opens file handles per plugin × per form-processing thread (3–4), and stdio caps at **512 handles**, so you crash **well before 254 plugins**. MLF swaps stdio for direct Win32 calls, raising the ceiling and improving load times. ✅ ([Mod Limit Fix](https://www.nexusmods.com/newvegas/mods/68714))

**4. Performance / stutter.**
- **NVTF – New Vegas Tick Fix** — fixes micro-stutter, threading/tick issues, enables higher framerates. **NVTF fully supersedes the old New Vegas Stutter Remover (NVSR)** — do not run both; NVSR is deprecated. ✅
- **New Vegas Heap Replacer** — replaces the engine allocator (faster, less stutter, lower load times). **Conflicts with any other heap replacer** (NVSR's heap, NVTF's heap option) — enable exactly one heap. ✅ ([Heap Replacer](https://www.nexusmods.com/newvegas/mods/69779))

**5. Crash diagnostics** (pick the modern path):
- **Yvile's / csimonca's Crash Logger** — writes a detailed crash log (call stack, offending form) on CTD. The modern diagnostic of choice. ✅
- **NVAC – New Vegas Anti Crash** — older NVSE plugin using structured exception handling to *suppress* some access-violation crashes at known offsets. **Not a cure-all.** **Modern builds essentially never use NVAC** — a crash logger plus the bugfix plugins (JIP LN, JohnnyGuitar, NVTF) replace it. ✅
  - **Exception — NVMP (New Vegas Multiplayer):** NVAC is considered **essential on NVMP's main public server**, because the server **blocks other stability mods**, leaving NVAC as the fallback crash mitigation. So an NVMP setup may legitimately ship NVAC where a modern single-player build would not. 🟡
  - ([NVAC](https://www.nexusmods.com/newvegas/mods/53635))

**6. UI / framework.**
- **UIO – User Interface Organizer** (coordinates HUD/xml extensions), **The Mod Configuration Menu (MCM)**, **yUI/ySI**. See the MCM section below. 🟡

**7. Vanilla bug-fix plugins** (ESM/ESP, not DLLs):
- **YUP – Yukichigai Unofficial Patch** and/or **Unofficial Patch NVSE Plus** — fix hundreds of vanilla quest/record bugs. Load **high**, with the NVSE Plus patch after YUP. 🟡

### NVSE plugin load mechanics
- NVSE DLLs load from `Data/NVSE/Plugins/` at launch (no plugin entry in `plugins.txt`; they're not ESPs). 🟡
- Most are **load-order-independent**; a few document ordering — read each mod page. 🟡
- Under MO2 these merge into `Data/NVSE/Plugins/` via the VFS only at runtime (see MO2 section). Each `*.pdb` next to a DLL is debug symbols for crash loggers — harmless. ✅

### INI threading/stability tweaks — don't
- The old `bUseThreadedAI`/`iNumHWThreads`/cell-buffer/`iPreloadSizeLimit` tweaks are **placebo or harmful**; rely on **NVTF** for threading, not manual INI edits. Full myth list + the `ini audit` tool are in **INI Tuning** below. 🟡

### Diagnosing "won't launch / CTD"
1. Confirm the foundation exists & is current: xNVSE (`nvse.log` written at launch), 4GB patch, JIP LN / JohnnyGuitar, NVTF, Mod Limit Fix.
2. Read logs: `nvse.log`, `nvac.log` (if NVAC), the crash logger output, `falloutnv_error.log`.
3. Check for **double heaps** (NVHR + NVSR/NVTF heap) and **duplicate/missing NVSE plugin** versions.
4. Under MO2: verify tools are launched **through MO2** and the right **profile** is active.

_[expand: per-tool current version numbers; lStewieAl tweak specifics; exact NVTF heap settings; FNV BSA Decompressor; Ultimate Edition ESM Fixes]_

---

## GECK Scripting (replaces Skyrim's Papyrus section)

FNV scripting is **fundamentally different from Papyrus.** Do not carry Papyrus assumptions over.

### Where scripts live
- Scripts are **`SCPT` records stored inside the plugin** (`.esp`/`.esm`) — there are **no external `.psc`/`.pex` files.** 🟡
- Each `SCPT` record contains:
  - **`SCTX`** — the **human-readable source text** (preserved in the plugin!) ✅ structurally
  - **`SCDA`** — the compiled bytecode
  - **`SCHR`/`SLSD`/`SCVR`** — script header + local variable definitions/names
- Because `SCTX` exists, **you can read script source directly in xEdit / XEditLib — no decompiler needed.** This is a major ergonomic win over Skyrim. ✅ structurally
- Quest result scripts and dialogue/package result scripts are stored **embedded** in their parent records (e.g. dialogue `INFO`), not as standalone `SCPT`. Editing these safely usually means the GECK. 🟡

### Script structure
- A script is `scn <Name>` (a.k.a. `ScriptName`), variable declarations, then one or more `Begin <BlockType> … End` blocks. ✅
- **Only variable declarations may sit outside a Begin/End block — every other statement must be inside one.** ✅ ([Scripting for Beginners](https://geckwiki.com/index.php/Scripting_for_Beginners))
- Each frame/tick the engine evaluates a script's blocks and runs whichever are valid for the current context. ✅

### Script types
- **Object (reference) scripts** — attached to a base form (or placed reference). Run **only while the object's 3D is loaded** (its cell is active). `GameMode` ticks here every frame the object is loaded. 🟡
- **Quest scripts** — attached to a Quest form; run on the **quest processing delay** regardless of cells (see timing below). The backbone of most mods — run global logic here, not on a world object that may be unloaded. ✅
- **Effect scripts** — attached to a Base Effect (magic/actor effect / "Script Effect"). Use `Begin ScriptEffectStart` / `ScriptEffectUpdate` / `ScriptEffectFinish`. ✅ ([ScriptEffectStart](https://geckwiki.com/index.php/ScriptEffectStart))
- **Result scripts** — short fragments embedded in dialogue `INFO`, packages, or **quest stages** (run when the stage is set). Edited via the GECK, not as standalone `SCPT`. ✅

> **One script per form.** Each base object/reference can have **exactly one** script attached — unlike Papyrus, you cannot stack multiple scripts on one object. 🟡 Workarounds: put logic in a **quest script**, a **scripted token** (an object added to inventory whose script runs), or **NVSE event handlers** (`SetEventHandler`, which *does* support multiple prioritized handlers globally). ✅ ([SetEventHandler](https://geckwiki.com/index.php/SetEventHandler))

### Block types (common) and when they run
- **`GameMode`** — runs every frame while the script is active (object loaded / quest running) and the game is in gameplay (not in a menu). ✅ ([GameMode](https://geckwiki.com/index.php/GameMode))
- **`MenuMode [n]`** — the companion to GameMode; runs whenever **any** menu is displayed (optionally a specific menu type `n`). ✅ ([MenuMode](https://geck.bethsoft.com/index.php?title=MenuMode))
- **Reference events** — `OnActivate`, `OnAdd`, `OnEquip`/`OnUnequip`, `OnActorEquip`/`OnActorUnequip`, `OnDrop`, `OnHit`, `OnHitWith`, `OnDeath`, `OnMurder`, `OnLoad`, `OnReset`, `OnStartCombat`/`OnCombatEnd`, `OnTrigger`/`OnTriggerEnter`/`OnTriggerLeave`, `OnSell`, `OnPackageStart`/`OnPackageDone`/`OnPackageChange`, `SayToDone`. ✅ (list per geckwiki block-type category)
- `OnActivate` **suppresses default activation** — if you handle it, call `Activate` yourself or the object won't do its normal thing. 🟡

### Variables & persistence
- Types: **`short` / `long` / `int` are all the same 32-bit integer** in the engine; **`float`**; **`ref`** (stores a FormID/RefID). ✅ ([Declaring Variables](https://geck.bethsoft.com/index.php?title=Declaring_Variables))
- **Local script variables persist in the save** once the script has run. Reading a quest's variables externally uses `QuestEditorID.VariableName`. ✅
- **Globals** persist in the save; a global flagged **Constant** resets to its default on load (do not use Constant for state you change at runtime). ✅
- **`ref` variables can go stale** — a reference in an unloaded cell, or to a temporary object that gets cleaned up, may become invalid; guard with `IsFormValid` / `GetIsReference` / null checks. 🟡
- **No native string or array type** — `string_var` and `array_var` require **NVSE** (see below). ✅

### Quest script timing
- Quest scripts run on a **Script Processing Delay** (`fQuestDelayTime`), default **~5 seconds**. ✅
- Change it with **`SetQuestDelay`**; a very small value (e.g. `0.01`) effectively runs **every frame**; setting `0` reverts to the **default 5s**. ✅ ([Quest scripts](https://geckwiki.com/index.php/Quest_scripts))
- **Quests auto-start** when a stage is set (`SetStage`) or an objective is displayed (`SetObjectiveDisplayed`). **Stop completed quests** (`StopQuest`) so their script stops processing — leaving them running wastes script time and can bloat saves. ✅
- Quest variables remain readable/writable even when the quest isn't running. ✅
- **`SetStage` runs that stage's result script**; make stage results **idempotent** and prefer `GetStage >= N` comparisons over `== N` to survive out-of-order stage setting. 🟡

### NVSE / xNVSE
- **xNVSE** (the maintained fork) massively extends the command set. The **function-library extenders** that mods build on:
  - **JIP LN NVSE** — 1000+ functions + the **Script Runner** (the esp-less engine, below). · **JohnnyGuitar NVSE** — 500+ functions, event system, INI/file/array functions. · **ShowOff NVSE** — more functions + engine tweaks. · **SUP NVSE** — large function library, strong **UI/menu/HUD** functions (HUD flags, menu/tile manipulation). · **Anh NVSE** — additional function-library/modder's-resource. · **kNVSE** — animation system. · **UIO** — UI extension loader.
  - 🟡 ([xNVSE](https://github.com/xNVSE/NVSE)); SUP/Anh characterized from their installed DLLs.
- NVSE ships its **own compiler**, separate from and more flexible than the GECK's — it supports richer operators, and **native `string_var` / `array_var`**. It is only engaged for NVSE-aware functions. ✅ ([NVSE Expressions](https://geckwiki.com/index.php/NVSE_Expressions))
- **Inline expressions** via `Let`, `Eval`, `TestExpr`; `:=` is assignment. `Let` can declare on the fly: `let float fX := 1.0`. ✅
- **Compiling NVSE commands requires an NVSE-aware GECK** (launch the GECK through NVSE, or use **GECK Extender** / the NVSE GECK loader). The vanilla GECK rejects unknown NVSE commands. 🟡
- The GECK compiler can silently miscompile; modders **verify with a decompiler** (xEdit shows `SCTX`). ✅

### Known gotchas
- **Object scripts don't run when the object is unloaded** — for always-on logic use a quest script. 🟡
- **`OnAdd`/`OnEquip` fire on the item's own script**, on the actor doing the action — verify which reference `GetContainer`/`GetActionRef` returns before assuming. 🟡 _[verify per-block ref semantics]_
- **`string_var`/`array_var` (NVSE-only):** modern xNVSE **auto-destroys local** ones when the script finishes; only those stored in **quest/persistent** vars need managing (overwrite/clear) or they persist in the save. 🟡
- **Loops:** iterate arrays with **`ForEach`** (don't add/remove elements mid-iteration); prefer `ForEach`/`While` over `Label`/`Goto` (the latter work but invite spaghetti). 🟡

---

## NVSE Function Reference

The extender stack adds **thousands** of script functions over vanilla GECK script. Don't memorize them — know the landscape, look specifics up on geckwiki, and use the `funcs` tool to index what's actually installed.

### Landscape (≈ counts from a real installed stack, via `funcs` — heuristic)
| Source | ≈Fns | Domain |
|--------|------|--------|
| base **xNVSE** | ~680 | core: refs, inventory, arrays, strings, events, UI, math |
| **JIP LN NVSE** | ~1040 | the biggest — refs/actors/weapons, UI/tiles, file/INI, arrays (`ar_`), strings (`sv_`), containers, world |
| **JohnnyGuitar NVSE** | ~310 | events, navmesh, region/weather, forms, arrays |
| **ShowOff NVSE** | ~240 | engine queries/tweaks, UI/HUD |
| **SUP NVSE** | ~145 | UI/menu/HUD, tiles |
| **kNVSE** | ~60 | animation control (`kPlay*`) |
| **lStewieAl's Tweaks** | ~50 | tweak/console helpers |

### Naming
Mostly `Get*`/`Set*`/`Is*`/`Has*`/`Add*`…; JIP arrays `ar_*`, strings `sv_*`, config `con_*`; kNVSE `kPlay*`.

### Look up / index
- **Authoritative (full signatures, params, examples):** geckwiki **"Functions"** categories — [Functions (JIP)](https://geckwiki.com/index.php/Category:Functions_(JIP)), [Functions (JG)](https://geckwiki.com/index.php/Category:Functions_(JohnnyGuitar)), [Functions (ShowOff)](https://geckwiki.com/index.php/Category:Functions_(ShowOff)), and the [NVSE function list](https://geckwiki.com/index.php/New_Vegas_Script_Extender).
- **What's in THIS install:** `bash tools/automod-cli.sh funcs list <plugin.dll> [--grep <substr>]` (e.g. `funcs list jip_nvse.dll --grep weapon`) or `funcs scan <dir>`. **Heuristic** index (string scan + prefix/denylist) — high precision, **not exhaustive** (oddly-named functions may be missed). **Always confirm exact signature/params on geckwiki before relying on a function.** ✅ (JIP extracted 1041 ✓)

## Mods Without a Plugin

Not every FNV mod needs an `.esp`/`.esm`. Three **distinct** cases — keep them straight, especially the precise meaning of "esp-less":

### 1. Pure asset / replacer / UI mods (no logic)
Loose files overriding vanilla — no plugin, no script: texture/mesh replacers (`nif` + loose; `bsa` to pack), sound/voice replacers (`audio` + GECK `.lip`), UI/HUD XML (`menus\…\*.xml`, UIO-coordinated), animation packs (kNVSE JSON + `.hkx`). Handled by the toolbox's asset modules. *(These are "no-plugin" but are **not** what "esp-less" means below.)*

### 2. "Esp-less" mods — NVSE config-scripts (the specific term) ✅ verified
**"Esp-less" specifically means a mod whose *logic* is NVSE script + data carried in loose `.txt`/`.ini`/`.json` files, compiled and run at game load by the script-extender stack — no plugin record and no compiled DLL.** They almost always require **JIP LN NVSE, JohnnyGuitar NVSE, ShowOff NVSE, SUP NVSE, Anh NVSE**, **lStewieAl's Tweaks**, **UIO**, etc. Examples: the **B42 series** (B42 Optics, B42 FireMode, B42 Melee Bash…), ISControl, many total-conversion systems.

**Architecture (verified against B42 Optics):**
- **Runtime NVSE script** — `Data\NVSE\plugins\scripts\<prefix>_<Name>.txt`: a plain **GECK/NVSE script** compiled and run by **JIP LN NVSE's Script Runner** — no esp needed. ✅ The **filename prefix selects the event**: `gr_`=game start · `gl_`=game load · `gs_`=game save · `gx_`=game exit · `xm_`=exit-to-main-menu · `gn_`=new game · **`ln_`=new game + every game load** (most common for mod systems). Limits: **16 KB max** per file; near-full NVSE expressions (loops, lambdas) since xNVSE 6.21; compile errors → `jip_ln_nvse.log`. ✅ ([JIP LN Script Runner](https://geckwiki.com/index.php?title=JIP_LN_NVSE_Script_Runner_Introduction)) Typical shape:
  - **Dependency gate** at the top — bail if extenders are too old:
    `if GetNVSEVersionFull < 6.3 … MessageBoxEx … return`; `if GetPluginVersion "JIP LN NVSE" < 57.15 …`; same for `"JohnnyGuitarNVSE"`, `"ShowOffNVSE Plugin"`, `"UI Organizer Plugin"`; `if FileExists "nvse\plugins\scripts\ln_ISControl.txt" == 0 …`. Set a flag and `return` if unmet.
  - The **logic**, built almost entirely from **NVSE-extended commands** (events via `SetEventHandler`, UI via UIO, math/array/string/file IO from JIP/JG/ShowOff).
- **Data/config `.ini`** — the mod's own `Config\<Name>\…\*.ini`: section-keyed, often **pipe-delimited** records the script parses (e.g. per-weapon `0=0.804|-3.428|…|B42\Optics\LensN.nif`), read at runtime via NVSE file/INI functions.
- **lStewieAl Tweaks config** — `NVSE\plugins\Tweaks\INIs\<Name>.ini`: settings consumed by **lStewieAl's Tweaks** (distinct from the mod's own `Config\`).
- **Assets + UI** — `menus\prefabs\<Name>\*.xml`, meshes/textures/sounds.
- **Zero `.esp`.** *(Some B42 mods do ship an esp — older/simpler implementations, e.g. B42 Inertia/Inspect; the esp-less ones like B42 Optics don't.)*

**Toolbox fit:** fully in scope — it's **all text** (NVSE script + INI/JSON + XML); no compiler, no esp, no `xeditlib`. Authoring needs the **NVSE command vocabulary** (JIP LN / JohnnyGuitar / ShowOff function libraries), each system's config conventions, and the dependency-gate idiom above. The **`esp-less-mod` skill** scaffolds the `<prefix>_<Name>.txt` runtime script + config files. _[expand: catalog the most-used JIP/JohnnyGuitar/ShowOff commands; UIO & kNVSE config schemas]_

### Config-driven frameworks (the esp-less toolbox)
Two frameworks let mods change the game **from config files, no esp** — core to esp-less modding. Both verified against a real modded install.

**KEYWORDS** — a Skyrim-style **keyword/tagging system** for FNV (which has no native keywords). ✅
- Itself esp-less: a `gr_0KEYWORDS.txt` runtime script (game-start; the `0` sorts it early) + INI configs in a **`Data\KEYWORDS\`** folder. Requires xNVSE 6.33+, JIP LN 57.21+, JohnnyGuitar 493+.
- The script does `GetFilesInFolder "KEYWORDS" "*.ini"` — **any mod can drop a `KEYWORDS\<name>.ini`** to register tags (extensible, conflict-free).
- INI format: a `[1]` section, then `KeywordName=EditorID1, EditorID2, …` (comma-separated EditorIDs). The framework resolves `EditorIDToFormID` and tags those forms.
- Use: tag categories of vanilla forms (`Harvestable=BananaYuccaPickable, …`, lootable activators, mod buttons, invisible doors) so other mods apply behavior by tag — **without editing the records**.

**Base Object Swapper (BOS)** — config-driven **base-object swapping / transforms** (FNV port of powerofthree's Skyrim BOS). ✅ (config format read from `BaseObjectSwapper.dll`)
- A framework DLL that reads `.ini` swap rules from **`Data\BaseObjectSwapper\`** at load ("No .ini files were found … aborting"). Errors → `BaseObjectSwapper.log`.
- File discovery: the FNV **Community Master Plugin** build reads `Data\BaseObjectSwapper\*.ini`; the broader po3 convention also reads **`*_SWAP.ini`** anywhere in `Data\`. Errors → `BaseObjectSwapper.log`.
- **`[Forms]` row syntax (confirmed ✅):** `origBaseID|swapBaseID|transformOverrides|chance` (pipe-delimited).
  - Random pick from several targets = comma-separated swaps: `orig|swapA,swapB,swapC|…|…`.
  - `transformOverrides` = `NONE`, or position/rotation/scale/property overrides.
  - **Chance:** `chanceS(n)` = fixed, **persists across sessions** · `chanceL(n)` = fixed per **location/base** · `chanceR(n)` = **rerolled each new game**.
  - Example: `0x23D63|0x1BBC5|NONE|chanceS(50)` → 50% chance to swap Quill01 → PaintBrush01.
  - `[Transforms]` applies position/rotation/scale changes to refs (same filter/chance machinery). ([BOS format](https://www.nexusmods.com/fallout4/mods/67528))
- Use: replace/retexture/move/scale base objects across the game **without editing the original plugin** — conflict-free, esp-less patching.

### 3. Native NVSE plugins (compiled C++ DLL) — a different thing
Engine-level hooks / new functions, compiled to a `.dll` in `Data\NVSE\Plugins\` (like JIP LN, JohnnyGuitar themselves). **Not** text, not esp-less in sense #2. See the **`nvse-plugin` skill** (drives your MSVC; the toolbox bundles no compiler).

---

## Plugin Format / xEdit / FNVEdit

### Plugin types (ESM vs ESP)
| Type | Load position | Limit | Notes |
|------|--------------|-------|-------|
| **ESM** | Top of load order | 254 total ESM+ESP | Master files; supports persistent/temporary refs |
| **ESP** | After ESMs | 254 total ESM+ESP | **No ESL / no light plugins in FNV** |

- **Ceiling: 254 active plugins** in theory (load-order byte `00`–`FE`; `FF` reserved) — but the **practical limit is only ~130–140 without [Mod Limit Fix](https://www.nexusmods.com/newvegas/mods/68714)** (stdio file-handle bug; see *Foundation/Stability Stack* and *Merging plugins*). There is **no ESL escape hatch** like Skyrim SE — merging is the only way down. 🟡
- A plugin's **masters must load before it**; reordering can break `FormID` references. 🟡

### xEdit / FNVEdit
- **FNVEdit** is xEdit in FNV mode — conflict detection, record editing, and **Apply Scripts** (Pascal). ✅ ([FNVEdit](https://www.nexusmods.com/newvegas/mods/34703))
- Apply a script: load plugin(s) → right-click the plugin → **Apply Script** → pick script → OK. ✅
- Pascal scripting API: [Tome of xEdit – Scripting Functions](https://tes5edit.github.io/docs/13-Scripting-Functions.html); curated FNV scripts: [matortheeternal/TES5EditScripts](https://github.com/matortheeternal/TES5EditScripts), [FNVEdit User Scripts](https://www.nexusmods.com/newvegas/mods/52467). ✅

### Cleaning dirty edits (ITM / UDR)
Two kinds of "dirty edit":
- **ITM — Identical To Master**: an override record that changes **nothing** vs its master. Harmful because it can **cancel out an intentional change** from a higher-priority plugin. Remove via xEdit right-click → **"Remove 'Identical to Master' records."** ✅ ([EssArrBee FNVEdit Mod Cleaning](https://stepmodifications.org/wiki/User:EssArrBee/FNVEdit_Mod_Cleaning), [LOOT: Dirty Edits](https://loot.github.io/docs/help/dirty-edits-mod-cleaning--crcs/))
- **UDR — Undeleted and Disabled Reference**: a **deleted reference** is a major CTD/bug cause. The fix is **not** to leave it deleted but to **undelete it and set its Initially-Disabled flag** (same in-game effect, no crash). xEdit right-click → **"Undelete and Disable References."** The "UDR count" = deleted refs already fixed this way. ✅

**Caveats (FNV-specific, important):**
- **Not all ITMs are errors** — intentional identical overrides exist (keyword/compat injections). Review before saving. ✅
- **Do NOT undelete navmesh UDRs in the official master/DLC ESMs** — that can cause **crash on startup**. More broadly, the conservative stance is **don't clean vanilla `FalloutNV.esm` at all**; mods are built against it. 🟡
- **Modern alternative to manual DLC cleaning:** many guides now ship a pre-made fix (e.g. **Ultimate Edition ESM Fixes Remastered**) instead of hand-cleaning the DLC. 🟡 ([Viva New Vegas](https://vivanewvegas.moddinglinked.com/utilities.html))
- **Quick Auto Clean (QAC):** clean one plugin at a time by launching xEdit through MO2 with args `-iknowwhatimdoing -quickautoclean`. ✅
- **Conflict detection (shipped toolbox — public tools only):** use **xEdit/FNVEdit**'s conflict view (or xEditLib programmatically) plus **LOOT** for dirty-edit flags. Under MO2, launch them **through MO2** so the VFS reflects the real load order. The toolbox **does not depend on any private/custom MCP.** ✅
  - *(The toolbox never depends on a private/custom MCP for conflicts — use xEdit/FNVEdit + LOOT, which everyone has.)*

### Merging plugins (the real plugin limit)
- The FormID byte gives a **theoretical 254** ESM+ESP ceiling, but the **practical limit without [Mod Limit Fix](https://www.nexusmods.com/newvegas/mods/68714) is only ~130–140** active plugins (the stdio file-handle bug — see *Foundation/Stability Stack*). Mod Limit Fix raises it toward the real cap. 🟡
- **FNV has no ESL/light plugins**, so **merging is the only way to reduce active-plugin count.** 🟡
- **Tools:** xEdit's **Merge** (the *Merge Plugins* script / `mteFunctions`), the standalone **Merge Plugins** (Mator) — supports FO3/FNV and copies/renames associated assets — and **zEdit's Merge module**. ✅ ([matortheeternal/merge-plugins](https://github.com/matortheeternal/merge-plugins), [STEP: Merging Plugins](https://stepmodifications.org/wiki/Guide:Merging_Plugins))
- **Do NOT merge:** ❌ **MCM mods** or **mods that ship an `.ini`** (config is bound to the plugin *filename* — merging breaks it); ❌ mods the author says not to merge; ⚠️ mods with **embedded scripts** or **BSAs** need careful asset/script handling. ✅
- **Merging renumbers FormIDs** → external plugins that point at the merged plugin break unless patched. **Merge related mods together** and rebuild dependent patches. 🟡

### Navmesh (GECK-only, CTD-prone)
- **Navmesh authoring is GECK-only** — xEdit can **delete or finalize** navmesh but **cannot create/recreate** it. 🟡
- **Deleted navmeshes cause instant CTD** when the player reaches the area — especially if **another mod added a door link to a triangle in the deleted navmesh.** ✅ ([Causes of CTDs (GECK)](https://geckwiki.com/index.php/Causes_of_CTDs))
- **Fixing a deleted navmesh in xEdit:** remove the deleted-navmesh override from the offending plugin and **renumber the replacement navmesh's FormID to the deleted one's**; or use **GECK Extender**'s "undelete navmesh + set Initially Disabled." The **[FNVToolkit](https://www.nexusmods.com/newvegas/mods/95058)** xEdit script automates much of this. 🟡
- **Always re-finalize navmesh in the GECK after editing** — door links span the **exterior cell *and* connected interiors**; an unfinalized or mis-edited navmesh re-introduces the crash. During big navmesh work, finalize/save every 20–30 min. 🟡
- **Never naively undelete navmeshes from official ESMs** (see cleaning caveat). ✅

---

## BSA Archives

- FNV uses **BSA only** (older archive version than Skyrim; **no BA2**). 🟡
- **Loose files in `Data/` always override BSA contents.** Check for loose conflicts before assuming BSA content loads. 🟡
- **Archive Invalidation** must be active for loose mesh/texture replacers to take effect (mod managers usually handle this; otherwise `bInvalidateOlderFiles=1` + an invalidation BSA). 🟡
- Tooling: **BSArch** (read/create/extract). _[expand: exact archive version/header, FOMM archive tools]_

---

## FOMOD Installers (packaging with choices)

A **FOMOD** is the interactive installer read by MO2/Vortex/FOMM — use one **only when the player must make an install-time choice** (variants, optional files, mutually-exclusive compatibility patches). **Most mods need none** — if there's one version and no choices, just ship the files. ✅ (verified: 0 of ~179 mods in a real modded install ship a FOMOD)

- **Layout:** a `fomod/` folder at the mod root with `info.xml` (metadata) + `ModuleConfig.xml` (logic), plus option source folders (e.g. `options/bright`). `source=` paths are **relative to the mod root**.
- **`ModuleConfig.xml`** (`ModConfig5.0.xsd`): `<config>` → `<moduleName>` → optional `<requiredInstallFiles>` (always installed) → `<installSteps>` → `<installStep>` → `<optionalFileGroups>` → `<group type=…>` → `<plugins>` → `<plugin>` (`<description>`, `<image>`, `<files>` `<folder/file source= destination= priority=>`, `<conditionFlags>`, `<typeDescriptor>`).
- **Group `type`** (selection rule): `SelectExactlyOne` · `SelectAtMostOne` · `SelectAtLeastOne` · `SelectAll` · `SelectAny`. ✅
- **Plugin `<type name=>`** (default state): `Required` · `Optional` · `Recommended` · `NotUsable` · `CouldBeUsable`. ✅ Conditional defaults via `<dependencyType><patterns>`; flag-driven installs via `conditionFlags` + `conditionalFileInstalls` (`flagDependency`, `fileDependency state="Active|Inactive|Missing"`, `dependencies operator="And|Or"`).
- **Toolbox:** `fomod` AutoMod module (`init` skeleton, `validate` enums + source paths, `types`) + the `fnv-fomod` skill. Validator = structural sanity, not full XSD. ([STEP FOMOD guide](https://stepmodifications.org/wiki/Guide:FOMOD/ModuleConfigXML))

## Audio / Voice Files

FNV uses **no FUZ and no XWM** (unlike Skyrim). Three different formats by purpose:

| Purpose | Format | Notes |
|--------|--------|-------|
| **Voice / dialogue** | **`.ogg` (Ogg Vorbis) + `.lip`** | OGG = **24 kHz, mono, VBR ~64 kbps**. `.lip` drives facial lip-sync. ✅ |
| **Sound effects** | **`.wav` or `.ogg`** | 16-bit PCM WAV is the safe choice; bad OGG encodes cause crackling. 🟡 |
| **Music / radio** | **`.mp3`** | True-stereo MP3 (~160 kbit/s per channel). Radio also needs a **mono OGG** copy named `<name>_mono.ogg`. 🟡 |

- **MP3 does not work inside BSAs / for voice** — only music uses MP3, and even then loose. Voice must be OGG. ✅

### Folder structure & filename convention (verified against vanilla)
```
Data\Sound\Voice\<PluginName.esm/.esp>\<VoiceType>\<filename>.ogg   (+ matching .lip)
```
- Real vanilla example (from `Fallout - Voices1.bsa`, 105,517 files): ✅
  `sound\voice\falloutnv.esm\maleuniquemrnewvegas\radionewvegas_rnvnewsstory_0014e7cd_1.ogg` (+ `.lip`)
- Filename pattern: **`<questEDID>_<topicEDID>_<INFO-FormID 8-hex>_<take#>.ogg`**. The 8-hex chunk is the dialogue **response (`INFO`) FormID** — this is how the engine maps an audio file to a line. ✅
- The folder is named after the **plugin's full filename including extension** (`mymod.esp`), and the subfolder is the actor's **Voice Type**. ✅

### Generating `.lip` (GECK, public tool)
- The `.lip` is generated **by the GECK** from a correctly-named **`.wav`**. ✅ ([GECK: Facial Animation](https://geckwiki.com/index.php/Facial_Animation))
- **Setup once:** copy the lip-processing files into `Data\sound\voice\processing\` — installing **[FonixData.cdf](https://www.nexusmods.com/newvegas/mods/61248)** enables one-click `.lip` generation (vanilla GECK lip-sync is frequently broken without this fix). 🟡
- **The WAV must be named after a valid dialogue line** and sit in the correct voice-type folder, because the GECK compares the audio to the response text to derive phonemes. If misnamed/misplaced, **no `.lip` is produced.** ✅
- **In the GECK:** open the Response in the dialogue's bottom panel → select the audio file → click the **`FromWav`** radio → the **`GenerateLipFile`** button unlocks → click it. No success sound plays; the `.lip` appears next to the `.wav`. ✅

### Replace/add a voice line — end-to-end (public tools)
1. Record/obtain the line as **WAV**; name it to match the target `INFO` (the GECK fills the name when you assign audio to a response).
2. Place it under `Data\Sound\Voice\<yourplugin>\<voicetype>\`.
3. **GECK → GenerateLipFile** to produce the `.lip`.
4. **Encode the WAV to OGG**: **24 kHz, mono, VBR ~64 kbps** — **oggenc2** (what the AutoMod CLI `audio` module uses); alternatives: Audacity, ffmpeg (`-ar 24000 -ac 1`), **[GECK Sound Converter](https://www.nexusmods.com/newvegas/mods/73649)**. Keep the `.wav` out of the shipped mod; ship **`.ogg` + `.lip`**.
5. If crackling occurs, re-encode to **16-bit PCM WAV** or clean OGG (see **[fnv-audio-fix](https://github.com/michalrewak/fnv-audio-fix)**). 🟡

### Packing / extracting
- Vanilla voice/sound live in **`Fallout - Voices1.bsa`** and **`Fallout - Sound.bsa`**. ✅
- Extract/repack with **BSArch** (public). **Loose files override BSA audio** — a loose `.ogg`/`.lip` in `Data\Sound\Voice\...` wins.
- **Under MO2:** put new audio in a mod folder (`mods/<YourMod>/Sound/Voice/...`) or `overwrite/`, enabled in MO2 — never loose into the real `Data\`.

### TTW / FO3 portability note
- **FO3 voice OGG is 44.1 kHz**, FNV is **24 kHz** (both mono, ~64 kbps). When porting FO3 voice to FNV/TTW, the sample-rate difference matters — re-encode to 24 kHz for consistency. ✅ ([FonixData notes](https://www.nexusmods.com/newvegas/mods/61248))

---

## Save Files (.fos)

Verified by parsing a real FNV/TTW save (~6.6 MB). ✅

- **Signature: `FO3SAVEGAME`** (ASCII, first 11 bytes) — FO3 and FNV share it. ✅
- **Uncompressed.** Unlike Skyrim SE's `.ess` (LZ4), FNV `.fos` is **plain/uncompressed** — so **byte-scanning for strings, FormIDs, plugin names, and EditorIDs works directly, with no decompression step.** This makes FNV save analysis *easier* than Skyrim's. ✅
- **String fields use a `|`-delimited, length-prefixed encoding:**
  ```
  0x7C  <uint16 LE length>  0x7C  <ASCII bytes × length>
  ```
  The `|` (0x7C) byte is the field delimiter throughout the header. ✅ (verified across every plugin name in the list)
- **Plugin list:** a run of those string fields. Extracting it from a real TTW save yielded the **full plugin list (200+)** in load order. Because this is a **TTW** save, the list shows the merged structure: `FalloutNV.esm`(0) + NV DLC(1–5), then **`Fallout3.esm`(6)** + FO3 DLC(7–11), then `TaleOfTwoWastelands.esm`(16) and TTW mods. ✅
  - **Cross-validates the TTW section:** `Fallout3.esm` at load index **6** is exactly the `06` head-byte case in *TTW → FormID remap*.
- **Header layout** (documented FO3 order + verified against the real FNV save):
  | Field | Type | Notes |
  |------|------|-------|
  | `fileId` | char[11] | `"FO3SAVEGAME"` ✅ |
  | `saveHeaderSize` | uint32 | size of the header block |
  | `unknown1` | uint32 | **always `0x30`** ✅ (matches dump) |
  | *(FNV only)* `language` | `\|`-delim string | **`ENGLISH`** — FNV inserts this; **not in the FO3 spec.** ✅ (FNV≠FO3 here) |
  | `screenshotWidth` / `screenshotHeight` | uint32 each | verified **512 × 288** in a real save |
  | `saveIndex` | uint32 | save number |
  | `pcName` | size(uint16)+string | player name |
  | `pcKarma` | size+string | karma rank (e.g. "Vault Martyr") |
  | `pcLevel` | uint32 | |
  | `pcLocation` | size+string | current location |
  | `playtime` | size+string | `HHH.MM.SS` |
  - **Preview:** `screenshotData` = `W*H*3` interlaced RGB ubytes, then `0x15` marker, `pluginStructSize`, `pluginCount` (ubyte), divider. **Cross-checked:** 512×288×3 = 442,368 → plugin list begins at `0x6C088` in the verified save. ✅
  - **Stats** block: `unknown3[114]`, then a count + **26 DWORD stats** (quests completed, locations discovered, …), divider-separated. ✅
  - String fields throughout use `size + 0x7C + bytes` with `0x7C` (`|`) dividers. ✅
- The **tail beyond Stats** (global data tables / form-change records) is **largely undocumented publicly** — out of scope for the reader. ❓
  - *Source: [FOS file format (Fallout Wiki)](https://fallout.wiki/wiki/FOS_file_format), derived from the UESP Oblivion save format; FNV deltas verified against the real save.*
- **No Papyrus.** FNV has no Papyrus VM, so saves store **form-change records**, not Papyrus script instances — Skyrim save concepts (orphaned Papyrus scripts, ReSaver) **do not map directly.** "Orphaned script" analysis in FNV means scanning for a removed mod's EditorID/script-name strings. ✅

### What the toolbox can do now (verified, public, no decompression)
- **Extract the plugin list** (string-field walk). ✅ — see `scripts/read-fos.js`
- **Search** for any string (script/EditorID/mod prefix) or **FormID** (as LE uint32) by raw byte scan; **count occurrences** to detect accumulation/bloat. ✅
- **Mod footprint / orphan check**: search a removed mod's EditorID prefix or master name. 🟡
- **Bloat tracking**: compare file sizes across saves (uncompressed → size ≈ content). 🟡

### Tooling note
- There is **no strong public GUI save editor for FNV** (ReSaver targets Skyrim/FO4) — the toolbox's own `scripts/read-fos.js` (Node, no deps) fills the read/scan gap. A full structured *editor* would require reverse-engineering the ChangeForms tail (out of scope for now). 🟡
- _[expand: header field offsets (player name/level/location/playtime/screenshot); FOSE/NVSE co-save `.fos`-adjacent files; ChangeForm structure if ever needed]_

---

## NIF Meshes

### Format / version
- FNV meshes are **Gamebryo NIF, file version `20.2.0.7`** — **the same NIF version Fallout 3 uses** (this is part of why FO3↔FNV mesh sharing largely works). ✅ ([fallout.wiki: NifSkope](https://fallout.wiki/wiki/Resource:NifSkope))
- The distinguishing fields are the **User Version (11)** and **BS Version (34)** for FO3/FNV. **Skyrim LE is also file version `20.2.0.7` but User Version 12 / BS Version 83** — so the version *number* matches yet the meshes are **NOT interchangeable** with Skyrim. 🟡 (header numbers commonly cited; not re-verified live this session)
- Vanilla meshes live in **`Fallout - Meshes.bsa`** (19,587 files, **internally zlib-compressed** NIFs — verified). Loose `.nif` files override BSA meshes. ✅

### Shaders (FNV ≠ Skyrim)
- FNV/FO3 use **`BSShaderPPLightingProperty`** (+ `BSShaderTextureSet`; older assets use `NiTexturingProperty`). It controls things like environment-map cubemap brightness. ✅ ([GECK: NIF Shader Properties](https://geckwiki.com/index.php?title=NIF_Shader_Properties))
- **Skyrim's `BSLightingShaderProperty` does NOT exist in FNV.** Any tool that only reads `BSLightingShaderProperty` (e.g. some Skyrim-oriented shader inspectors) will report nothing useful on FNV meshes. ✅
- Texture paths inside the NIF must be **relative to `Data\`** and start with `textures\…`. Wrong/absolute paths or case issues → missing textures (purple/invisible). **Archive Invalidation** must be on for loose texture replacers. 🟡

### Geometry & collision (Havok / bhk)
- Geometry blocks: **`NiTriShape`** / **`NiTriStrips`** (with `NiTriShapeData` / `NiTriStripsData`). ✅
- Collision is **Havok `bhk*`**: `bhkCollisionObject` → `bhkRigidBody` → a shape (`bhkMoppBvTreeShape`/`bhkPackedNiTriStripsShape` for static, `bhkConvexVerticesShape` for convex). ✅ ([GECK: NIF Block Types](https://geckwiki.com/index.php?title=NIF_Block_Types))
- **`bhkConvexListShape` was deprecated in New Vegas** — usable only in Oblivion/FO3. A FO3 mesh using it must be reworked for FNV. ✅
- Collision authoring gotchas (Blender NifTools): collision export only works with the **"Fallout 3"** game setting (not "Fallout NV"); `bhkPackedNiTriStripsShape` **Scale exports as 0 and must be fixed to 1 in NifSkope**; bullet-hole decals require the affected `NiTriShape(s)` to be **in the same branch as the `bhkCollisionObject`**. 🟡 ([How To Make Collision For FNV](https://www.nexusmods.com/newvegas/mods/76324))

### FO3 ↔ FNV / Oblivion porting
- **FO3 → FNV meshes:** usually drop-in (same NIF version), *except* deprecated collision shapes (`bhkConvexListShape`) and a few block differences — see [MAC-TEN](https://www.nexusmods.com/newvegas/mods/83815). ✅
- **Oblivion → FNV:** needs conversion (`NiTexturingProperty` → `BSShaderPPLightingProperty`); tools like **[NIFConverter](https://www.nexusmods.com/newvegas/mods/86271)** automate it. 🟡

### Tools (public)
- **NifSkope** — the standard GUI viewer/editor; the **[fo76utils fork](https://github.com/fo76utils/nifskope)** is the actively-maintained build. ✅
- **Blender + NifTools addon** (import/export), **[Sniff](https://www.nexusmods.com/newvegas/mods/67829)** (batch NIF inspection/editing), **NIFConverter**.
- **Skyrim toolkit's `fix-eyes` does NOT port** — FNV FaceGen is a different system. The FNV analog is the **"dark face" / grey-face bug**: editing an NPC (`NPC_`) without regenerating its **FaceGenData** leaves the head tint/geometry mismatched (a dark or mismatched face). Fix by regenerating FaceGen in the **GECK** (select the NPC → **Ctrl+F4**), which rebuilds the `.egm`/`.tri` + face-tint `.dds` to match the plugin — not an eye-mesh edit. ✅
- **Under MO2:** edit meshes in `mods/<YourMod>/meshes/…` (loose), enabled in MO2 — not into the real `Data\`.

---

## Animations (kNVSE)

Animation replacement/addition in FNV uses **kNVSE** (the kNVSE Animation Plugin) — **esp-less, config-driven**. A mod ships `.kf` animations + a JSON config mapping anims to conditions; kNVSE swaps the vanilla animation group at runtime. ✅ (schema verified against real kNVSE animation mods)

### Layout
- **Config JSON:** `Data\meshes\AnimGroupOverride\<Name>.json`.
- **Anim files:** `.kf` in `Data\meshes\AnimGroupOverride\<folder>\…` (mirroring the vanilla `_male\` anim-path structure), named by **animation group** (vanilla group names, e.g. `2hrattackleft`, locomotion anims). Multiple `.kf` for one group → kNVSE picks **randomly** (variants).

### Config schema (verified)
A JSON **array** of override entries; each has a `folder` plus a target:
```json
[
  { "folder": "Hit_9mmPistol", "mod": "MyWeapons.esp", "form": "04751B" },
  { "folder": "Female", "condition": "GetIsSex Female == 1 && GetEquipped AllPowerArmor == 0" },
  { "folder": "ECR_Legate", "condition": "... && GetCombatStyle == CSNVLegateLanius", "priority": 60 }
]
```
| Key | Meaning |
|-----|---------|
| **`folder`** (req) | anim folder under `AnimGroupOverride\` holding the `.kf` files |
| **`condition`** | NVSE/GECK **condition expression** on the actor (`&&`/`\|\|`/parens; `this.`/`<ref>.`; functions like `GetIsSex`, `GetEquipped <FormList>`, `GetWeaponAnimType`, `GetCombatStyle`, `GetVariable f <Quest>`, `AuxVarGetFlt`, `GetRandomPercent`, `GetDistance3D`) |
| **`mod`** + **`form`** | target a specific base form (e.g. a weapon): plugin filename + hex FormID |
| **`priority`** | int; **higher wins** when multiple entries match |

- `condition` **and** `mod`/`form` can be **combined** (form-specific override gated by a condition). Real-install key frequency: `folder` 111 · `condition` 102 · `mod`/`form` 35 · `priority` 3. ✅
- **Requires kNVSE** (+ JIP LN). Config + `.kf` are loose files → **esp-less** (a targeted weapon may come from an esp, but the anim override itself is config). Conditions re-evaluate when an anim group is about to play, so anims switch dynamically (combat state, equipped weapon, random).

## LOD (Level of Detail) Generation

Distant low-detail objects/trees/terrain. Generated by **Sheson's xEdit-based tools** — the toolbox **orchestrates** them (detect/launch/verify), it does not reimplement generation. See the `fnv-lod` skill / `lod` AutoMod module.

- **Tools:** **FNVLODGen** = FNVEdit in LODGen mode + the worker **`Edit Scripts\LODGenx64.exe`** (both ship with FNVEdit — present on this install). **Terrain LOD** uses **xLODGen** (Sheson's terrain beta, separate download; `-fnv`, `-o:"out"`). ✅ It's xEdit-based, so **run it through MO2** (VFS) to see the modded order. ([Viva New Vegas LOD guide](https://vivanewvegas.moddinglinked.com/lod.html))
- **Output paths:** Object LOD → `Data\Meshes\Landscape\LOD\<Worldspace>\Blocks\*.nif` + `Data\Textures\Landscape\LOD\<Worldspace>\Blocks\*.dds` (built from each static's `_lod.nif`). Tree LOD → `…\<Worldspace>\Trees\*.DTL` (binary placement) + `TreeTypes.LST`. Terrain LOD → distant land/water meshes + textures. ✅
- **Prereqs:** LOD is **asset-dependent** — needs object `_lod.nif`, tree billboards, terrain meshes (LOD resource mods like Much Needed LOD / TCM's LOD). Missing assets → holes/pop-in. Generation is **interactive (GUI settings) and slow** — not unattended.
- **Esp-less:** LOD output is loose assets (no plugin). Generate to a dedicated folder → enable as an MO2 mod; package with `bsa pack`.

## The Mod Configuration Menu (MCM)

FNV's de-facto config-menu standard is **[The Mod Configuration Menu](https://www.nexusmods.com/newvegas/mods/42507)** (by Pelinor) — a community framework, **not** Skyrim's SkyUI MCM. **None of the Skyrim MCM tooling ports** (SkyUI MCM is Papyrus + a scripted MCM quest with SkyUI's API; FNV MCM is XML menus + NVSE/JSON). 🟡

### What it is
- MCM adds a **"Mod Configuration" button to the pause menu**; every mod that registers appears in one shared list and is configured there. ✅
- It is fundamentally a **UI mod** (the game's `menus\` XML/HUD system) **plus NVSE**. It therefore participates in **UI-mod compatibility**: it must be wired into the start menu, and it coexists with other UI mods via **UIO (User Interface Organizer)** + a compatible UI base (VUI+ / yUI). ✅
- **Classic "MCM button missing" fix:** there must be **exactly one** `<include src="MCM\MCM.xml"/>` line in `Data\menus\options\start_menu.xml` (or `Data\menus\prefabs\includes_StartMenu.xml`) — duplicates from multiple UI mods break it. ✅

### Two ways a mod registers a menu
- **Script-based (Pelinor's original):** a **quest + quest script** registers the menu and drives each option via `GetUIFloat`/`SetUIFloat`/`SetUIStringEx` on `StartMenu/MCM/...` paths — **fully documented in *Script-based MCM* below**. The MCM core ships UI prefabs at `menus\prefabs\MCM\*.xml` (`MCM.xml`, `Options.xml`, …) — the **framework's** UI, not per-mod files. ✅ The canonical reference is the **separate "MCM Guide" download** (Nexus mod 42507, *miscellaneous files* — `MCM Guide.doc` + `MCM Example Menu.esp` templates; **not bundled** with the MCM framework), or the **[Unlocked MCM templates](https://www.nexusmods.com/newvegas/mods/62777)**. **For new mods, prefer the verified JSON path above** (simpler); use script-based for dynamic menus or porting.
- **JSON-based (no script) — VERIFIED:** mods ship a JSON file read by **lStewieAl's Tweaks** (and **[MCM Extender](https://www.nexusmods.com/newvegas/mods/93642)**) at:
  `Data\NVSE\Plugins\Tweaks\MenuConfig\<ModName>.json` ✅ (verified against installed mods: `SmoothTrueIronsights.json`, lStewieAl's `AllTweaks.json`)

### Verified JSON schema (the path the `mcm` skill should emit)
A top-level **array of setting groups**; each group has a header toggle + `subsettings[]`:
```json
[
  {
    "name": "Smooth True Ironsights Camera",       // display label
    "internalName": "bSmoothIronsightsCameraTransition", // INI key; Hungarian prefix sets type
    "description": "…",
    "category": "Quality-of-life",                  // MCM category/page
    "subsettings": [
      { "type": "slider", "name": "Aim transition time",
        "internalName": "iAimTransitionTimeMS", "internalCategory": "Smooth Iron Sights Camera",
        "description": "…", "minValue": 0, "maxValue": 500 },
      { "name": "Easing function", "internalName": "iEasingFunction",
        "internalCategory": "Smooth Iron Sights Camera", "description": "…",
        "options": [ { "name": "None", "value": 0 }, { "name": "OutSine", "value": 1 } ] }
    ]
  }
]
```
- **Control types** (`type` field): omit `type` → **toggle/checkbox**; `"slider"` (+ `minValue`/`maxValue`); `"input"` (text); **dropdown** when an `options[]` array of `{name,value}` is present. ✅
- **Hungarian prefix on `internalName` sets the value type:** `b`=bool, `i`=int, `f`=float, `s`=string. ✅
- **Storage → INI:** `internalCategory` is the INI **`[section]`**, `internalName` is the **key** (e.g. `[Smooth Iron Sights Camera] iAimTransitionTimeMS=…`). The MCM core's own settings live in `Config\MCM.ini` (`[List]`, `[Messages]`). ✅

### Script-based MCM (advanced — Pelinor's API, VERIFIED)
For dynamic menus (values computed at runtime, types the JSON path can't express, or porting an old mod), build the menu in GECK script. **The real API is UI-path driven** — you read/write the MCM menu's XML elements with `GetUIFloat`/`SetUIFloat`/`SetUIString`/`SetUIStringEx` on `StartMenu/MCM/...` paths. ✅ (verified against the official **MCM Guide v6** + the three `MCM Example Menu*.esp` scripts — Nexus mod 42507 *misc files*). **No `GetMCMFloat`/`SetMCMFloat` functions exist** — that was a misnomer; the only MCM-specific funcs are the INI ones below.

**Setup (GECK):** ① a **Start-Game-Enabled quest** with a low Script Processing Delay (0.01–0.1) and a **Quest-type script**; ② a **Misc Item** whose *Name* is how your mod appears in the MCM list (the "mod-name token").

**Path syntax:** `StartMenu/MCM/*:N` = the Nth child (NVSE 1.0b9+ shorthand). Key elements: `*:1`=`MCM_Options`, `*:2`=`MCM_Scale`, `*:3`=`MCM_List`, `*:5`=`MCM_ModList` (sub-menus), `*:8`=`MCM_Title`, `*:9`=`MCM_Info` (mouse-over text). Paths are case-insensitive but `_`-prefixed param names are literal. `SetUIStringEx` takes printf-style format specifiers (same as `PrintToConsole`); the compiler will **not** catch path typos, so they fail silently.

**1. Register the menu** (once, in `GameMode`):
```
begin GameMode
    if GetGameRestarted
        if IsModLoaded "The Mod Configuration Menu.esp"
            set iMaster to GetModIndex "The Mod Configuration Menu.esp"
            set rList to BuildRef iMaster 2790          ; 2790 = MCM's mod-list FormList
            ListAddForm rList MyModNameToken            ; the Misc Item from setup
        endif
    endif
end
```

**2. Drive the menu** — all UI work happens in **`begin MenuMode 1013`** (the MCM menu's mode), gated on your mod being active. MCM raises one of several **event flags**; you handle the relevant block and **clear the flag** (never delete a flag-clear line — an unhandled flag freezes the menu):
```
begin MenuMode 1013
    if IsModLoaded "The Mod Configuration Menu.esp" else Return endif
    if GetUIFloat "StartMenu/MCM/_ActiveMod" == GetModIndex "MyMod.esp"
        set iOption to GetUIFloat "StartMenu/MCM/_ActiveOption"
        set fValue  to GetUIFloat "StartMenu/MCM/_Value"
        if GetUIFloat "StartMenu/MCM/_Reset"            ; 1 — REDRAW: (re)build every row here
            SetUIFloat "StartMenu/MCM/_Reset" 0
            SetUIFloat "StartMenu/MCM/*:1/_columns" 1
            ; ... define each option row (see params below) ...
        elseif GetUIFloat "StartMenu/MCM/_Default"      ; 2 — DEFAULTS button
            SetUIFloat "StartMenu/MCM/_Default" 0
            SetUIFloat "StartMenu/MCM/_Reset" 1         ; set your vars to defaults, then force a redraw
        elseif GetUIFloat "StartMenu/MCM/_NewValue"     ; 3 — user committed a value
            SetUIFloat "StartMenu/MCM/_NewValue" 0
            SetUIFloat "StartMenu/MCM/_Reset" 1
            if iOption == 1 set MyVar1 to fValue
            ; type 8/9 read _Value1/_Value2/_Value3 instead of fValue
            endif
        elseif GetUIFloat "StartMenu/MCM/_ShowList" == 1  ; 4 — populate a type-1 list (set _ShowList 2)
        elseif GetUIFloat "StartMenu/MCM/_ShowScale" == 1 ; 5 — populate a type-2/2.5/8/9 scale (set _ShowScale 2)
        elseif GetUIFloat "StartMenu/MCM/_DefaultScale"   ; 6 — scale's own Default button (set _DefaultScale 0, _ShowScale 2)
        endif
        if iMouseover != GetUIFloat "StartMenu/MCM/*:1/_optionID"   ; 7 — MOUSE-OVER help text → *:9/string
            set iMouseover to GetUIFloat "StartMenu/MCM/*:1/_optionID"
        endif
    endif
end
```

**Per-row params** (under `*:1/*:N/`, in the `_Reset` block): `_enable` (0 hidden / 1 active / 2 visible-inactive), `_title`, `_type` (below), `_value`, `_prefix`, `_suffix`(0/1)+`_suffixText`, `_textOn`/`_textOff` (type 6), `_indent`, `_highlight`, `_altFont`, `_brightness`, `_RGB`/`_RGBAlt` (9-digit RRRGGGBBB). String displays (types 1/2.5/3/8) are set via `value/*:1/string` with `SetUIStringEx`.

**Option types (`_type`):** `0` title only · `1` pick-from-list (values 1–10; populate `MCM_List` in the ShowList block) · `2` integer scale · `2.5` float scale · `3` keybind (DirectX scan code, `%k` format) · `4` ON/OFF toggle · `5` checkbox toggle (visually different from 4) · `6` custom-text toggle (`_textOn`/`_textOff`) · `7` static string · `8` 2–3 value scale (`_scales`, `_setting1..3`) · `9` RGB scale (3×0–255). Scales use `_Value`, `_ValueMin/Max/Increment/Decimal` (or `_Value1..3` + `_Value1Min` etc. for 8/9).

**Persist across saves (MCM 1.4+ INI funcs):** `SetModINI "iniName/appName/keyName" <float>` and `GetModINI "iniName/appName/keyName"` (aliases `SetModINISetting`/`GetModINISetting`; separators `:` `/` `\`). INIs live in `Data\Config\<name>.ini` (no `.ini` in the path arg); activity logs to `…\Fallout New Vegas\mcm.log`. Read them in `GameMode`/`GetGameLoaded`, write them in the `_Default` and `_NewValue` blocks.

**Other facts:** **No master dependency** — a mod with an MCM menu does *not* need MCM as a master; the menu just won't appear if MCM is absent. **Sub-menus** (up to 10): `MCM_ModList` SubMenu#/`_enable`+`text/string`, `MCM_Title` SubTitle#/`string`, switch with `_ActiveSubMenu`. **Multiple mod-list entries:** add several name tokens and branch on `_ActiveMenu`. **Big scripts:** offload `_Reset` chunks into **Quest Stage result scripts** (`SetStage`) to dodge `MAX_SCRIPT_SIZE`. **Integration:** exactly one `<include src="MCM\MCM.xml"/>` in `start_menu.xml` (or let UIO handle it). NVSE-only — no FO3/FOSE version.

### Implications for the toolbox
- The FNV **`mcm` skill must NOT reuse** the Skyrim toolkit's SkyUI-JSON generator — it should emit **this `Tweaks/MenuConfig/<Mod>.json`** schema (lowest-effort, script-free, verified), or a Pelinor script-template (using the API above) for advanced/dynamic cases. ✅
- **Do not merge MCM mods** (config is bound to the plugin filename — see *Merging plugins*). ✅
- Requires **lStewieAl's Tweaks** (or MCM Extender) for the JSON path, plus the **MCM** core mod + **UIO** for the menu itself. 🟡

---

## Tale of Two Wastelands (TTW)

- TTW is a **total conversion** that merges Fallout 3 + DLC into FNV for a single playthrough on the **FNV engine** (upgrades FO3 to FNV mechanics). ✅ ([TTW FAQ](https://taleoftwowastelands.com/faq))
- Requires **clean, unmodded FO3 and FNV installs** to build. ✅
- **Compatibility reality:** unconverted FO3 mods do nothing or **break TTW**; **many plain-FNV mods are also TTW-incompatible.** Prefer mods explicitly labeled **TTW-compatible (3.3+)**. ✅

### Converting a Fallout 3 mod to TTW (the official method)
**Authoritative process** — RoyBatty/zilav's [TTW Mod Conversion Package & Guidelines](https://geckwiki.com/index.php?title=TTW_Mod_Conversion_Package_and_Guidelines). The remap is **automated by a script + CSV database**, *not* hand-edited head-bytes. ✅

> ⚠️ **Get the original author's permission first** — converting/redistributing their work without it is not allowed; keep documentation of permission.

1. **Decide if it needs converting** — pure-asset mods (textures/meshes/sounds, no plugin) usually work as-is; plugin mods need conversion. 🟡
2. **Add the TTW masters (FNVEdit).** Load the full TTW master set + your plugin: `FalloutNV.esm`, the 5 NV DLC, `Fallout3.esm`, the 5 FO3 DLC (`Anchorage`/`ThePitt`/`BrokenSteel`/`PointLookout`/`Zeta`), `TaleOfTwoWastelands.esm`. Right-click the plugin → **Add Masters** (select all TTW masters) → **Sort Masters** → **Save and Exit** (do **not** skip this). ✅
3. **Run the official conversion script.** Reload (it now auto-loads the TTW masters). Right-click → **Run Script** → the **TTW Conversion Script** (zilav's) → choose the **`TTWConversion.csv`** database → let it run. This **remaps every FO3 FormID to its TTW equivalent automatically** from the CSV — you do **not** hand-edit head-bytes. Save & Exit; reload, check for errors, re-run if forms straggle. ✅
   - *(This CSV-driven remap is why manual `06`/`0A` head-byte editing is unnecessary — the script knows every mapping. Use the CSV matching your TTW version, 3.3/3.4.)*
4. **Recompile scripts one by one in the GECK.** FO3 `SCPT` records must be **manually recompiled** in a TTW/NVSE GECK — **never use "Recompile All."** FOSE scripts need FOSE→NVSE rework; FO3's compiler had no error-checking, so expect to fix broken/old code. ✅
5. **Address engine differences** (the long tail — check each that applies):
   - **Navmesh:** any plugin with navmesh **must be an ESM** (ESP-navmesh bug), navmesh must be **re-finalized** in the GECK, and **deleted/merged navmesh causes crashes** (undelete in xEdit). ✅
   - **Actor Values changed:** Small Guns→**Guns**, Throwing→**Survival**, Big Guns disabled (still usable via JIP LN), Detect Life Range→**Turbo**; new **DT**/Dehydration/Hunger/Sleep. ✅
   - **Form types gained fields** (open in GECK to update): `FACT` (Reputation), `WEAP`/`AMMO`/`ARMO`/`ARMA`/`PROJ`/`PERK`/`MISC`/`CONT`/`STAT`/`WTHR`/`ALCH`/`SOUN`/`DIAL`/`LSCR`/`TACT`/`ASPC`. ✅
   - **Crafting:** convert FO3 scripted workbenches to the FNV **recipe system** — never leave scripts on benches (breaks the game). ✅
   - **Companions:** add the **companion-wheel** dialogue topics + the exact follower script variables (`HasBeenHired`, `WeaponOut`, `CombatStyleRanged/Melee`, `IsFollowing*`, `Waiting`, …); **don't edit the vanilla Followers quest**. ✅
   - Also: FO3 model variants are path-prefixed **`dc`**; music uses an **Audio Marker + media set** (cell/worldspace music field no longer works); loading screens are **location-specific** in TTW; rebalance **DR vs DT**, **economy**, and **hardcore** food/healing; care with **leveled lists**. ✅
   - **Never touch** TTW's Startup/Generic-Handler quests or `TTWFunctions` (deprecated). ✅
   - **Collision note:** lStewieAl's Tweaks **restores `bhkConvexListShape`** (and stair materials) to FNV, so FO3 meshes using it may not need reworking on a Stewie's-equipped setup. 🟡
6. **Clean** the plugin in FNVEdit (especially after GECK work) and **test on a real TTW install.** ✅

### Porting a *FNV* mod onto TTW
- First check for an existing **TTW patch** (most popular mods have one). If not, conflicts are resolved like any compatibility patch (below) against `TaleOfTwoWastelands.esm`. 🟡

### General compatibility patching (the second workflow)
1. **Detect conflicts** — load the order in FNVEdit (or xEditLib) and inspect overrides; the **last-loaded plugin wins** per record. (Public tools only — no private MCP.)
2. **Author an override patch** — a small ESP that masters the conflicting plugins and carries the desired winning values ("forwarded" records).
3. **Leveled lists / large merges** — use a **Bashed Patch (Wrye Flash)** or **Merged Patch (xEdit)** to combine leveled lists, factions, etc. that single override patches can't.
4. **Clean masters** — remove stray master references; ensure masters load before dependents.
5. Sort with **LOOT** (FNV) as a starting point, then hand-tune.

### Toolbox angle
- The **`port-ttw`** and **`patch-compat`** skills (Phase 3) build on the xEditLib backbone (`GM_FNV=0`; `GM_FO3=1` to read FO3 sources) + xEdit Apply Scripts for the master-swap/FormID-offset pass. All public tooling.

### Reference guides
- [The Best of Times (ModdingLinked)](https://thebestoftimes.moddinglinked.com) · [TTW Mod Conversion Package & Guidelines (GECK)](https://geckwiki.com/index.php?title=TTW_Mod_Conversion_Package_and_Guidelines) · [Adonis VII TTW 3.X (STEP)](https://stepmodifications.org/wiki/User:Adonis_VII/TTW_3.X) · [Load Order Library: TTW](https://loadorderlibrary.com/lists/ttw)

---

## Stability / Crash Debugging

### Crash logs — get a *modern* logger
- **NVAC (`nvac.log`)** *suppresses* access-violation crashes; its log is a **terse address trace** — lines `<ts> ^ <addr> <addr> <module>` (game executing) and `<ts> h <addr> <addr> <module>` (intercepted hook), with `TRUNCATE` markers. Good for spotting an *involved* module, poor for diagnosis. ✅ (verified from a real `nvac.log`)
- **Modern crash loggers** give real diagnostics: **Cobb Crash Logger** → `CobbCrashLogger.log` (exception, instruction pointer, registers, stack, source DLL); **Yvile's Crash Logger** (the recommended fork) adds RTTI-resolved game classes, readable formatting, and an alphabetized module list with plugin versions. A modern log has: the **exception** (`EXCEPTION_ACCESS_VIOLATION at module+offset`), a **call stack** (addr → module+offset, sometimes resolved form/EditorID), **registers**, **loaded modules**, and the **plugin list**. 🟡
- **Interpretation caveats:** the **topmost stack module is NOT always the culprit** — it may just be where the game was executing. Read the whole log, favour frames that resolve to a **form/EditorID**, and **cross-reference each `.dll` to its mod**. Share the full log when asking for help.
- **Where to find it — MO2 gotcha:** the game runs in the VFS, so crash logs (and `nvse.log`) are usually captured into the **instance's `overwrite\`** (e.g. `overwrite\Root\` / `overwrite\NVSE\`), **not** the game root.
- **Toolbox:** `crashlog` AutoMod module — `analyze <log>` (detects NVAC vs modern; extracts exception, noise-filtered suspect modules ranked by frequency, plugin count) and `find` (locate logs incl. the overwrite note). See the `fnv-crashlog` skill.

### INI Tuning — don't (mostly)

**The single most useful guidance: do not manually tweak the game INIs.** ✅ The educated consensus is that nearly all "performance" INI edits are **placebo or harmful** — Nobody at Bethesda ever documented what these settings do. Modern guides (Viva New Vegas) say to **avoid INI tweaks not in the guide and avoid BethINI**; the real, *tested* knobs live in **`nvse_stewie_tweaks.ini`** (lStewieAl's Tweaks) and **NVTF's INI**, not the game INIs.

**Myth / harmful settings (the ones people still paste around):**
| Setting | Verdict |
|---------|---------|
| `bUseThreadedAI=1` | **Placebo** — no proven effect on FNV. |
| `bUseMultiThreadedFaceGen` | **Harmful vanilla default** — recommended value **0** (at 1 → NPC face discoloration). |
| `bMultiThreadAudio=1` | **Harmful** — freeze on exit to Windows. |
| `bUseMultiThreadedTrees=1` | **Caution** — tree-render glitches/crashes on some setups. |
| `iNumHWThreads=2` | **Disputed** — sometimes cited for FO3/TTW freezing; on FNV considered placebo and superseded by NVTF. |

**`uGridsToLoad` — the dangerous one.** Default **5**. Raising it strains the engine even on strong hardware, and — critically — **saving with `uGrids > 5` then reverting permanently corrupts that save** (a one-way door). Keep it at 5; only ever 7 with **uGridsToLoad SaveGuard**, never higher.

**INI hierarchy** (later overrides earlier): `Fallout_default.ini` → `Fallout.ini` → `FalloutPrefs.ini` → **`FalloutCustom.ini`** (the right place for any *deliberate* manual override). Under MO2, the active profile may use **profile-specific INIs**.

**Toolbox:** `ini audit` (read-only) flags these known-bad settings in your INIs — `bash tools/automod-cli.sh ini audit --json`. *Sources: community INI analysis, Viva New Vegas.*

### Common CTD signatures
*When* a crash happens points at the cause (always confirm with a crash logger — the top stack frame isn't always the culprit):
- **Before/at main menu (launch):** missing/mis-ordered **master**, an NVSE-plugin version mismatch, **double heap** (two heap replacers), or no 4GB patch. Read `nvse.log` + crash log.
- **Entering a cell / through a load door:** a **bad or missing mesh** (NIF) in that cell, **deleted/corrupt navmesh**, or a missing referenced master. Usually a specific mod's asset.
- **On save / autosave:** **script or array bloat** (a mod spamming `RegisterForUpdate`/leaking arrays), ActorCause bloat (→ *ActorCause Save Bloat Fix*), or a broken result script.
- **Infinite load screen:** missing master, a corrupt save, or heavy on-load scripting.
- **Equipping a specific weapon/armor:** bad mesh, missing animation, or a **kNVSE config** referencing a missing `.kf`.
- **Purple/invisible assets (not a crash):** **Archive Invalidation** off, or a wrong/loose texture path.
- **Random, no pattern:** memory (4GB/heap) or a mod conflict — get a modern crash logger and read the offending module/form.
### Load Order Management

**Curate load order manually in MO2 — don't rely on LOOT for FNV.** Load order is fundamentally a *conflict-resolution* problem, and that takes human judgment. ✅

**Manual curation (the primary method):**
- **Order:** ESMs before ESPs (FNV has **no ESL**); a plugin's **masters must load before it**; group by category in MO2 (separators) for sanity.
- **"Later plugin wins" per record** — so the thing you want to win goes **later**: bugfixes → overhauls → patches/compatibility plugins last. This is the core lever.
- **Choose winners deliberately:** inspect overrides in **FNVEdit's conflict view** (or xEditLib) and forward the desired values into a **compatibility/override patch**; use a **Bashed/Merged patch** (Wrye Flash / xEdit) for leveled lists & co. (see *Merging plugins* and the `patch-compat` skill).
- **MO2 owns it:** the order lives in the active profile's `plugins.txt`/`loadorder.txt`; change it in the MO2 UI, not by hand-editing.

**LOOT — a limited aid, not the authority.** It applies a community **masterlist** (load-after/requirement rules, group memberships, dirty-edit flags, incompatibility messages) over a master-based sort — but for FNV the **masterlist is thin/under-maintained**, so unlisted mods fall back to a generic sort, and **LOOT cannot decide conflict winners** (the part that actually matters). 🟡 Reasonable uses: flagging **dirty edits**, surfacing **requirement/incompatibility messages**, and a rough first pass on a big unsorted list — then **hand-tune in MO2**. Modern FNV guidance (Viva New Vegas) likewise ships a hand-curated order rather than leaning on LOOT.

---

## Hook Candidates

A living list of potential safety hooks identified during work. Evaluated but not necessarily implemented.

| Candidate | Trigger | What it would do | Priority | Status |
|-----------|---------|------------------|----------|--------|
| *None yet* | — | — | — | — |

**When to add entries:** after any near-miss, unexpected outcome, or pattern of risk current hooks don't cover.

---

## Sources (this session)

- [Mutagen #22 — Parse Fallout NV](https://github.com/Mutagen-Modding/Mutagen/issues/22)
- [Spriggit docs](https://mutagen-modding.github.io/Spriggit/) / [Spriggit CLI](https://mutagen-modding.github.io/Spriggit/cli/)
- [FNVEdit on Nexus](https://www.nexusmods.com/newvegas/mods/34703) · [FNVEdit User Scripts](https://www.nexusmods.com/newvegas/mods/52467) · [matortheeternal/TES5EditScripts](https://github.com/matortheeternal/TES5EditScripts)
- [Tome of xEdit — Scripting Functions](https://tes5edit.github.io/docs/13-Scripting-Functions.html)
- [GECK Wiki: Facial Animation](https://geckwiki.com/index.php/Facial_Animation) · [GECK Wiki: BSA Files](https://geckwiki.com/index.php/BSA_Files)
- [TTW FAQ](https://taleoftwowastelands.com/faq) · [The Best of Times guide](https://thebestoftimes.moddinglinked.com/intro.html)
- GECK scripting: [Scripting for Beginners](https://geckwiki.com/index.php/Scripting_for_Beginners) · [Quest scripts](https://geckwiki.com/index.php/Quest_scripts) · [GameMode](https://geckwiki.com/index.php/GameMode) · [MenuMode](https://geck.bethsoft.com/index.php?title=MenuMode) · [ScriptEffectStart](https://geckwiki.com/index.php/ScriptEffectStart) · [Declaring Variables](https://geck.bethsoft.com/index.php?title=Declaring_Variables) · [SetEventHandler](https://geckwiki.com/index.php/SetEventHandler)
- NVSE: [xNVSE (GitHub)](https://github.com/xNVSE/NVSE) · [NVSE Expressions](https://geckwiki.com/index.php/NVSE_Expressions) · [xNVSE on Nexus](https://www.nexusmods.com/newvegas/mods/67883)
- Esp-less / Script Runner: [JIP LN NVSE Script Runner](https://geckwiki.com/index.php?title=JIP_LN_NVSE_Script_Runner_Introduction) (prefix→event table, 16 KB limit) · [JIP LN NVSE](https://www.nexusmods.com/newvegas/mods/58277) · [JohnnyGuitar NVSE](https://www.nexusmods.com/newvegas/mods/66927) · architecture verified against B42 Optics (a real install)
- Frameworks & extenders: **KEYWORDS** (verified from a real install: `gr_0KEYWORDS.txt` + `KEYWORDS\*.ini`) · **Base Object Swapper** ([FNV Nexus](https://www.nexusmods.com/newvegas/mods/95581); folder/`[Forms]`/`[Transforms]` verified from `BaseObjectSwapper.dll`; **row syntax confirmed** `origBaseID|swapBaseID|transformOverrides|chance` + `chanceS/L/R(n)` via [BOS docs](https://www.nexusmods.com/fallout4/mods/67528)) · **SUP NVSE** / **Anh NVSE** (characterized from installed DLLs)
- Stability stack: [Viva New Vegas — Utilities](https://vivanewvegas.moddinglinked.com/utilities.html) · [4GB Patcher](https://www.nexusmods.com/newvegas/mods/62552) · [FNV Mod Limit Fix](https://www.nexusmods.com/newvegas/mods/68714) · [New Vegas Heap Replacer](https://www.nexusmods.com/newvegas/mods/69779) · [NVAC](https://www.nexusmods.com/newvegas/mods/53635)
- Cleaning/merging/navmesh: [EssArrBee FNVEdit Mod Cleaning](https://stepmodifications.org/wiki/User:EssArrBee/FNVEdit_Mod_Cleaning) · [LOOT: Dirty Edits](https://loot.github.io/docs/help/dirty-edits-mod-cleaning--crcs/) · [STEP: Merging Plugins](https://stepmodifications.org/wiki/Guide:Merging_Plugins) · [Merge Plugins (Mator)](https://github.com/matortheeternal/merge-plugins) · [Causes of CTDs (GECK)](https://geckwiki.com/index.php/Causes_of_CTDs) · [FNVToolkit xEdit script](https://www.nexusmods.com/newvegas/mods/95058)
- Audio: [GECK: Facial Animation](https://geckwiki.com/index.php/Facial_Animation) · [FonixData.cdf](https://www.nexusmods.com/newvegas/mods/61248) · [GECK Sound Converter](https://www.nexusmods.com/newvegas/mods/73649) · [fnv-audio-fix](https://github.com/michalrewak/fnv-audio-fix) · folder/filename convention verified against `Fallout - Voices1.bsa`
- NIF: [fallout.wiki: NifSkope](https://fallout.wiki/wiki/Resource:NifSkope) · [GECK: NIF Shader Properties](https://geckwiki.com/index.php?title=NIF_Shader_Properties) · [GECK: NIF Block Types](https://geckwiki.com/index.php?title=NIF_Block_Types) · [NifSkope (fo76utils)](https://github.com/fo76utils/nifskope) · [NIFConverter](https://www.nexusmods.com/newvegas/mods/86271) · [How To Make Collision For FNV](https://www.nexusmods.com/newvegas/mods/76324) · version verified vanilla via `Fallout - Meshes.bsa`
- MCM: [The Mod Configuration Menu (Pelinor)](https://www.nexusmods.com/newvegas/mods/42507) · [MCM Extender (JSON)](https://www.nexusmods.com/newvegas/mods/93642) · [Unlocked MCM templates](https://www.nexusmods.com/newvegas/mods/62777) · JSON schema verified against real installed mods (`Tweaks/MenuConfig/*.json`)
- TTW: [TTW FAQ](https://taleoftwowastelands.com/faq) · [TTW Mod Conversion Package & Guidelines (GECK)](https://geckwiki.com/index.php?title=TTW_Mod_Conversion_Package_and_Guidelines) (read in full — official zilav script + `TTWConversion.csv` method, engine-diff notes) · [base id / FormID thread](https://taleoftwowastelands.com/viewtopic.php@t=3314) · [The Best of Times](https://thebestoftimes.moddinglinked.com) · [Adonis VII TTW 3.X (STEP)](https://stepmodifications.org/wiki/User:Adonis_VII/TTW_3.X)
- MCM script API: verified from the official **MCM Guide v6** (Pelinor) + the three `MCM Example Menu*.esp` scripts (Nexus mod 42507, *misc files*, separate download) — UI-path model (`GetUIFloat`/`SetUIFloat`/`SetUIString`/`SetUIStringEx` on `StartMenu/MCM/...`), `MenuMode 1013` event loop (`_Reset`/`_Default`/`_NewValue`/`_ShowList`/`_ShowScale`/`_DefaultScale`/`_optionID`), register via `ListAddForm` on `BuildRef GetModIndex 2790`, option types 0–9, persist via `GetModINI`/`SetModINI`. **No `GetMCMFloat`-style functions exist** (earlier note corrected)
- .fos saves: format verified by parsing a real FNV/TTW save — signature `FO3SAVEGAME`, uncompressed, `0x7C|uint16|0x7C|name` string fields, full plugin-list extraction; tool: `scripts/read-fos.js` · ref [FOS file (Fallout Wiki)](https://fallout.wiki/wiki/FOS_file) (spec pages block automated fetch)

---

*Last updated: 2026-06-13. Add new entries as discovered. Prefer verified facts over speculation; tag confidence (✅/🟡/❓).*

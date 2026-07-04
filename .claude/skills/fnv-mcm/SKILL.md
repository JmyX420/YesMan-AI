---
name: fnv-mcm
description: Generate a Fallout New Vegas Mod Configuration Menu (MCM) using the verified JSON schema. Do NOT use SkyUI/Skyrim MCM formats.
argument-hint: "[mod name and options]"
---

# MCM Menu Generation (FNV)

> **Preferred:** `bash tools/automod-cli.sh mcm <create|add-toggle|add-slider|add-dropdown|validate> ... --json` emits the verified schema below — see `docs/automod-cli.md`.

FNV's config-menu standard is **The Mod Configuration Menu** (Pelinor) — **not** SkyUI. The lowest-effort, script-free path is a **JSON menu** read by **lStewieAl's Tweaks** (or **MCM Extender**). See `KNOWLEDGEBASE.md → MCM`.

## Emit this JSON (verified schema)
File location: `Data\NVSE\Plugins\Tweaks\MenuConfig\<ModName>.json` (under MO2: in the mod's folder).

```json
[
  {
    "name": "Display label",
    "internalName": "bEnableFeature",          // INI key; Hungarian prefix sets type (b/i/f/s)
    "description": "What this does.",
    "category": "Quality-of-life",              // MCM page/category
    "subsettings": [
      { "type": "slider", "name": "Amount", "internalName": "iAmount",
        "internalCategory": "My Mod", "description": "...", "minValue": 0, "maxValue": 100 },
      { "type": "input", "name": "Some text", "internalName": "sLabel",
        "internalCategory": "My Mod", "description": "..." },
      { "name": "Mode", "internalName": "iMode", "internalCategory": "My Mod", "description": "...",
        "options": [ { "name": "Off", "value": 0 }, { "name": "On", "value": 1 } ] }
    ]
  }
]
```

## Rules (verified from real mods)
- **Control type** = the `type` field: **omit `type` → toggle/checkbox**; `"slider"` (+`minValue`/`maxValue`); `"input"` (text); **dropdown** when `options[]` of `{name,value}` is present.
- **`internalName` Hungarian prefix sets value type:** `b`=bool, `i`=int, `f`=float, `s`=string.
- **Storage → INI:** `internalCategory` is the INI **`[section]`**, `internalName` is the **key**.
- **Requires** lStewieAl's Tweaks (or MCM Extender) for the JSON path, plus the **MCM** core mod + **UIO**.

## Advanced (script-based)
For dynamic menus (runtime-computed values, types JSON can't express, porting old mods), use Pelinor's **script-based** MCM: a **quest + quest script** that reads/writes the menu's XML via `GetUIFloat`/`SetUIFloat`/`SetUIString`/`SetUIStringEx` on `StartMenu/MCM/...` paths. **There is no `GetMCMFloat`/`SetMCMFloat`** — that was a misnomer. The full, verified API (registration via `ListAddForm` on `BuildRef GetModIndex "The Mod Configuration Menu.esp" 2790`; the `MenuMode 1013` event loop with `_Reset`/`_Default`/`_NewValue`/`_ShowList`/`_ShowScale`/`_DefaultScale`/`_optionID`; option types 0–9; row params; persist via `SetModINI`/`GetModINI` → `Data\Config\<name>.ini`) is documented in **KB → *Script-based MCM (advanced — Pelinor's API, VERIFIED)***, sourced from the official **MCM Guide v6** (Nexus 42507 misc files) + its `MCM Example Menu*.esp` scripts.
- **No master dependency** — a mod using MCM doesn't need it as a master (menu just won't show if MCM is absent). Integration: one `<include src="MCM\MCM.xml"/>` in `menus\options\start_menu.xml` (or via **UIO**). NVSE-based; no FO3 version.
- **Never delete a flag-clear line** (e.g. `SetUIFloat "StartMenu/MCM/_Reset" 0`) — an unhandled event flag freezes the menu.

## Don't
- Don't emit SkyUI/Skyrim MCM JSON. Don't **merge** MCM mods (config is bound to the plugin filename).

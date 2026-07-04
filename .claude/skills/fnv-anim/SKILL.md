---
name: fnv-anim
description: Create or replace Fallout New Vegas animations with kNVSE — .kf animation files plus a JSON condition config (esp-less). Use for weapon/movement/creature animation mods.
paths: "**/AnimGroupOverride/**,**/*.kf"
---

# Animations (kNVSE)

FNV animation mods use **kNVSE** — ship `.kf` animations + a JSON config that maps them to **conditions**, and kNVSE swaps the vanilla animation group at runtime. It's **esp-less and config-driven**. See `KNOWLEDGEBASE.md → Animations (kNVSE)`. Requires **kNVSE** (+ JIP LN); animating the `.kf` itself is Blender/3ds Max + the NifTools/Kf tools (GUI — out of scope here).

## Layout
```
Data\meshes\AnimGroupOverride\
  <Name>.json                     # the condition config
  <folder>\_male\ … <group>.kf    # the .kf anims (mirror vanilla _male\ paths; name by anim group)
```
`<folder>` is referenced by the JSON; `.kf` files are named after the **vanilla animation group** they replace (e.g. `2hrattackleft`, locomotion anims). Put multiple `.kf` in one group folder for **random variants**.

## Config schema
A JSON array; each entry = a `folder` + a target (`condition` and/or `mod`+`form`), optional `priority`:
```json
[
  { "folder": "MyPistolAnims", "mod": "MyMod.esp", "form": "001234" },
  { "folder": "FemaleMove", "condition": "GetIsSex Female == 1 && GetEquipped AllPowerArmor == 0" },
  { "folder": "SpecialAttack", "condition": "GetWeaponAnimType == 9 && GetRandomPercent < 30", "priority": 60 }
]
```
- **`folder`** (required) — anim folder under `AnimGroupOverride\`.
- **`condition`** — NVSE/GECK condition expression on the actor (`&&`/`||`/parens; `this.`/`<ref>.`; `GetEquipped <FormList>`, `GetWeaponAnimType`, `GetCombatStyle`, `GetVariable f <Quest>`, `AuxVarGetFlt`, `GetRandomPercent`, …). Verify each function exists (geckwiki).
- **`mod`** + **`form`** — target a specific base form (weapon FormID + its plugin).
- **`priority`** — int, higher wins when multiple entries match.

## Workflow
1. **Decide targeting.** A specific weapon → `mod`+`form`. A state (sex, equipped category, combat) → `condition`. Both → combine.
2. **Place the `.kf`** in `AnimGroupOverride\<folder>\…`, named by the anim group(s) you're replacing. Drop several per group for random variation.
3. **Write the JSON** config in `AnimGroupOverride\<Name>.json` (array of entries above).
4. **Test in-game** — equip the weapon / meet the condition; kNVSE supports **hot-reload** (debug) so you can iterate without a full restart. Watch for the wrong anim group / T-pose (missing/misnamed `.kf`).
5. **MO2:** ship everything under a mod folder (`mods/<Mod>/meshes/AnimGroupOverride/…`) and enable — no esp needed.

## Notes
- Conditions re-evaluate each time an anim group is about to play, so anims can switch dynamically.
- This skill handles the **config + wiring**; producing the `.kf` (rigging/animating) is external GUI work.

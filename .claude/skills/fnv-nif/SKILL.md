---
name: fnv-nif
description: Inspect and edit Fallout New Vegas NIF meshes — version, shaders, textures, collision, FO3 porting.
paths: "**/*.nif,Data/meshes/**"
---

# NIF Mesh Operations (FNV)

> **Preferred for inspect / same-length retexture:** `bash tools/automod-cli.sh nif <info|list-textures|replace-textures> ... --json` (self-built, auto-`.bak`) — see `docs/automod-cli.md`. Different-length edits, node renames, and geometry/collision → NifSkope (below).
> **With the MO2 MCP running** (`mcp__mo2__*` present): prefer `mo2_nif_info` / `mo2_nif_list_textures` / `mo2_nif_shader_info` for inspection — they take a **VFS path** and resolve the mod-provided mesh for you.

FNV meshes are **Gamebryo NIF, file version `20.2.0.7` (User 11 / BS 34)** — the same version FO3 uses; **same number as Skyrim LE but NOT interchangeable**. See `KNOWLEDGEBASE.md → NIF Meshes`.

## Tools (public)
- **NifSkope** (GUI viewer/editor) — the standard; the **fo76utils fork** is the maintained build. There is **no bundled NIF CLI** in this toolbox, so NIF editing is a guided NifSkope workflow (open the file, inspect the block tree, edit, save).
- **Blender + NifTools addon** for geometry; **Sniff** for batch inspection; **NIFConverter** for Oblivion→FNV.

## What to check / do
- **Shaders:** FNV uses **`BSShaderPPLightingProperty`** (+ `BSShaderTextureSet`), **not** Skyrim's `BSLightingShaderProperty`. Tools that only read `BSLightingShaderProperty` show nothing useful here.
- **Texture paths:** must be relative to `Data\`, starting `textures\…`. Wrong/absolute/case-mismatched paths → purple/invisible. Ensure **Archive Invalidation** for loose textures.
- **Geometry:** `NiTriShape` / `NiTriStrips` (`…Data`).
- **Collision (Havok `bhk*`):** `bhkCollisionObject → bhkRigidBody → bhkMoppBvTreeShape`/`bhkPackedNiTriStripsShape`/`bhkConvexVerticesShape`. **`bhkConvexListShape` is deprecated in FNV** (FO3/Oblivion only).

## Porting meshes
- **FO3 → FNV:** usually drop-in (same NIF version); rework deprecated collision shapes.
- **Oblivion → FNV:** convert `NiTexturingProperty` → `BSShaderPPLightingProperty` (NIFConverter).
- **Blender collision export gotchas:** use the **"Fallout 3"** game setting; fix `bhkPackedNiTriStripsShape` **Scale 0 → 1** in NifSkope; bullet-hole decals need the `NiTriShape` in the **same branch** as the `bhkCollisionObject`.

## Not portable from Skyrim
The Skyrim toolkit's **`fix-eyes`** (FaceGen eye-ghosting) does **not** apply — FNV FaceGen is a different system.

## MO2
Edit meshes in `mods/<YourMod>/meshes/…` (loose), enabled in MO2 — not the real `Data/`.

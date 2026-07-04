---
name: fnv-lod
description: Generate and verify Fallout New Vegas LOD (object/tree/terrain) by orchestrating FNVLODGen/xLODGen. The toolbox drives the tool + does the automatable pre/post; it does not reimplement LOD generation.
argument-hint: "[worldspace or goal]"
---

# FNV LOD Generation

Generate distant LOD (the low-detail far objects/trees/terrain) using **Sheson's xEdit-based tools** — the toolbox **orchestrates** them and handles the automatable checks; it does **not** generate LOD itself (that's specialized 3D processing only the Sheson tools do). See `KNOWLEDGEBASE.md` and `docs/automod-cli.md → lod`.

## The tools (you already have most of this)
- **Object + tree LOD:** **FNVLODGen** — i.e. **FNVEdit** run in LODGen mode + the worker `Edit Scripts\LODGenx64.exe` (both ship with FNVEdit).
- **Terrain LOD:** **xLODGen** (Sheson's terrain beta — a separate download; rename to `FNVLODGenx64.exe` or pass `-fnv`).
- Detect what's present: `bash tools/automod-cli.sh lod tools --json`.

## What gets generated (and where)
- **Object LOD** → `Data\Meshes\Landscape\LOD\<Worldspace>\Blocks\*.nif` + `Data\Textures\Landscape\LOD\<Worldspace>\Blocks\*.dds` (built from each static's `_lod.nif`).
- **Tree LOD** → `…\LOD\<Worldspace>\Trees\*.DTL` (binary placement data) + `TreeTypes.LST`.
- **Terrain LOD** → distant land/water meshes + LOD textures.

## Workflow
1. **Prereqs / asset check.** LOD needs source assets — object `_lod.nif` meshes, tree LOD billboards, terrain meshes. Missing assets = holes in the distance. Run `lod check-assets --json`; on a modded setup, expect LOD-resource mods (Much Needed LOD, TCM's LOD, FNV LOD textures). State confidence about coverage.
2. **Launch the tool — THROUGH MO2.** Like FNVEdit, it must run via MO2's VFS to see the modded load order. `lod generate --output "<path>" --json` reports the front-end/worker paths + recommended args (`-fnv -o:"<path>"`). Add the front-end as an MO2 executable and run it; in the LODGen window **pick the worldspace(s) + settings**, then Generate. (Generation is interactive and can take minutes–hours; the toolbox can't run it unattended.)
3. **Verify output.** `lod verify-output [--worldspace X] --json` reports per-worldspace counts (object-LOD `Blocks\*.nif`, tree `*.dtl`, `TreeTypes.lst`, LOD textures). Flag worldspaces that produced nothing.
4. **Package (optional).** Pack the LOD output into a BSA for distribution: `bash tools/automod-cli.sh bsa pack "<LOD output dir>" "<MyMod - LOD.bsa>" --compress --json`.
5. **MO2:** generate **to a dedicated output folder**, then add it as a new MO2 mod (or `overwrite/`) and enable — don't write LOD loose into the real `Data\`.

## Settings notes (consult the LOD guide)
- Follow the **[Viva New Vegas LOD guide](https://vivanewvegas.moddinglinked.com/lod.html)** for recommended xLODGen/FNVLODGen settings (atlas size, terrain LOD options, protect/ignore lists). Settings are install-specific — don't blindly copy.
- Object LOD uses terrain LOD to cull triangles below terrain/water — generate **terrain LOD first** if doing both.

## Honesty
- The toolbox **wraps, not replaces** LODGen: detect, launch-assist, check assets, verify output, package. The generation pass is Sheson's GUI tool.
- Asset-dependent and slow; always verify output and test in-game (distant pop-in, missing LOD, texture seams).

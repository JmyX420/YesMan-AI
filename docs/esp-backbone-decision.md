# Decision Record: ESP Editing Backbone for FNV

**Date:** 2026-06-11 · **Status:** Decided (pending live validation)

## Context

The Skyrim Claude Code Toolkit's preferred ESP-editing workflow is **Spriggit** (Mutagen):
serialize an ESP to human-readable YAML, edit the YAML with Claude's native Edit tool,
deserialize back. This is the cornerstone of "Claude edits mods directly." We needed to
determine whether the same approach is available for Fallout: New Vegas.

## Investigation

- **Mutagen / Spriggit:** FNV is **not** in Mutagen's supported `GameRelease` list
  (Oblivion, SkyrimLE/SE/VR, Fallout4/VR, Starfield). There is an open issue
  ([Mutagen #22](https://github.com/Mutagen-Modding/Mutagen/issues/22)) expressing intent
  to add FO3/NV, but **no implementation exists.** → Spriggit YAML workflow is **unavailable.**
- **xEdit / FNVEdit Pascal "Apply Script":** Mature, proven, widely used for FNV record
  editing and batch operations. Curated script libraries exist.
- **XEditLib.dll:** Same engine the Skyrim toolkit already wraps via the `xeditlib` npm
  package; supports FNV via game mode `gmFNV = 0`. Gives programmatic read/edit/diff/bulk-query
  from Node.js.
- **FNV advantage:** Script source text is stored in-plugin (`SCTX` subrecord), so script
  reading needs no decompiler — unlike Skyrim's compiled-only Papyrus.

## Decision

Use a **two-track backbone**, no Spriggit:

1. **XEditLib.dll via the `xeditlib` Node wrapper (`gmFNV=0`)** — primary path for
   programmatic inspection, traversal, diffing, and scripted record edits.
2. **xEdit / FNVEdit Apply Scripts (Pascal)** — for batch/repetitive operations and tasks
   better expressed as an xEdit script.
3. **GECK** — escape hatch for navmesh, complex dialogue/quest wiring, and compiling scripts.

## Consequences

- The Skyrim toolkit's "edit YAML directly" ergonomics are lost; editing is mediated through
  XEditLib calls or xEdit scripts. We may later build a thin **FNV ESP CLI** (à la AutoMod CLI)
  to restore one-liner record creation ergonomics — tracked as a future option.
- Dry-run discipline still applies: read-only pass → user review → write pass.
- Need to validate XEditLib FNV mode against this live install (registry path, load order)
  before relying on it.

## Open items

- [x] Confirm `xeditlib` wrapper loads FNV masters correctly with `gmFNV=0` on a real install.
      **Validated 2026-06-11** — `examples/inspect-esp.js` loaded `FalloutNV.esm` (465,016 records,
      correct signature breakdown); `examples/create-esp.js` built a NOTE record in memory
      (dry-run, no file written). The package bundles `XEditLib.dll` + `FalloutNV.Hardcoded.dat`.
- [x] Confirm the FNV registry key / `Installed Path` resolves to this Steam install.
      **Confirmed** — the FNV `Installed Path` resolves via
      `HKLM\SOFTWARE\WOW6432Node\Bethesda Softworks\FalloutNV` (read automatically by the examples).
- [ ] Evaluate whether a custom FNV ESP CLI is worth building for end-user ergonomics. *(deferred — stretch)*
- [ ] Seed reusable xEdit Apply Scripts (Pascal) for common batch edits. *(Phase 3)*
- [ ] Resolve the MO2 VFS data-path story for loading the *modded* order programmatically (run-through-MO2 vs explicit paths). *(Phase 3)*

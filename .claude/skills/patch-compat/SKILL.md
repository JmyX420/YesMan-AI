---
name: patch-compat
description: Detect mod conflicts and create a Fallout New Vegas compatibility / override patch.
argument-hint: "[plugins or load order to reconcile]"
---

# Compatibility Patching (FNV)

Find and resolve record conflicts for `$ARGUMENTS`, then produce a patch.

**Detect-and-prefer the MO2 MCP.** If the mo2 MCP tools are available (the bundled MO2 plugin is running — see CLAUDE.md / AGENTS.md), use them — they read your **live modded load order** directly. Otherwise fall back to FNVEdit / xEditLib (`GM_FNV=0`), Wrye Flash, LOOT — everything below works either way.

## 1. Detect conflicts
**Preferred (MCP running):**
- `mo2_conflict_summary` → order-wide overview (which plugins override the most → conflict hotspots).
- `mo2_plugin_conflicts <plugin>` → for a suspect plugin, which of its overrides **win vs lose** (and to whom).
- `mo2_conflict_chain <plugin> <record>` → the full who-overrides-whom chain for one record, winner flagged.
- `mo2_record_detail` → inspect the actual field values in each version before deciding the winner.

**Fallback (no MCP):**
- Load the plugins in **FNVEdit**; use its conflict view (colored cells = overrides). **Last-loaded plugin wins** per record.
- Or xEditLib: load the order, walk records, compare overrides (`getOverrides`, `getPreviousOverride`) — `docs/xeditlib-guide.md`, `examples/diff-esp.js`. Run **through MO2** so the merged order is visible (standalone sees only vanilla `Data/`).

## 2. Author an override patch
**Preferred (MCP running):** `mo2_create_patch <patch.esp> <source_plugin> <record> --edits {…}` — copy-as-override into a new patch plugin with the winning field values. **Dry-run first** (`write=false`) to preview, then `write=true`. It lands in your output mod; enable it and load it last. (v1: one record per call — repeat for each.)

**Fallback (no MCP):** create a small ESP in FNVEdit/xEditLib that **masters the conflicting plugins** and carries the **desired winning values** (forward the records you want to win, merging fields from each source). Or `automod esp` override commands.
- Load the patch **last** (after the plugins it patches). Keep it focused — one patch per conflict cluster.

## 3. Bulk record types
- **Leveled lists, factions, form lists** that single overrides can't reconcile → build a **Bashed Patch (Wrye Flash)** or **Merged Patch (xEdit)** to combine them.

## 4. Clean up
- **Clean Masters** (remove stray master refs); ensure masters load before dependents.
- Run **LOOT (FNV)** as a starting sort, then hand-tune order.
- If the active-plugin count is high (~130–140 ceiling without Mod Limit Fix), consider **merging** related plugins (see `KNOWLEDGEBASE.md → Merging plugins`; don't merge MCM/INI-bound mods).

## Output
Report: the conflicts found (record, plugins, current winner), the patch created (records forwarded), and any load-order/merge recommendations.

## Safety
Dry-run discipline for any xEditLib write; review the patch before `SaveFile`. Hooks block direct `.esp/.esm` edits.

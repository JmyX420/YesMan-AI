---
name: fnv-save
description: Read and scan Fallout New Vegas save files (.fos). Use to extract the plugin list, search for orphaned scripts / mod footprint, or investigate save bloat.
paths: "**/*.fos"
---

# FNV Save File Analysis (.fos)

Use `scripts/read-fos.js` (Node, no dependencies) to read/scan `.fos` saves. **FNV saves are uncompressed** (unlike Skyrim's LZ4 `.ess`), so byte-scanning works directly — no decompression step.

Saves live in `Documents/My Games/FalloutNV/Saves/` (or a profile-specific Saves folder under MO2).

## Commands

**Save info (signature, size, plugin count):**
```bash
node scripts/read-fos.js info "<path-to-save.fos>"
```

**List all plugins in the save (in load order):**
```bash
node scripts/read-fos.js plugins "<path-to-save.fos>"
```

**Search for a string (script name, EditorID, mod prefix, master name):**
```bash
node scripts/read-fos.js search "<save.fos>" --string "SomeEditorID"
```

**Search for a FormID (matched as little-endian uint32):**
```bash
node scripts/read-fos.js search "<save.fos>" --formid 0x0006B531
```

**Search for a raw hex byte pattern:**
```bash
node scripts/read-fos.js search "<save.fos>" --hex DEADBEEF
```

## What this is good for
- **Plugin footprint / load order** captured in the save (verified: 203 plugins from a real TTW save).
- **Orphaned content** from a removed mod: search its master name or EditorID prefix; nonzero hits mean the save still references it. (FNV has **no Papyrus**, so this is form/string scanning, not Papyrus-instance analysis — ReSaver does not apply.)
- **Accumulation/bloat**: `search ... --formid` and read the occurrence count; compare `.fos` file sizes across saves (uncompressed → size ≈ content).

## Format notes (see KNOWLEDGEBASE.md → Save Files)
- Signature `FO3SAVEGAME`; string fields encoded `0x7C <uint16 LE length> 0x7C <bytes>`.
- FNV inserts a `language` field ("ENGLISH") the FO3 spec lacks.
- The structured tail (form-change records) is undocumented — this tool reads/scans, it does not edit saves.

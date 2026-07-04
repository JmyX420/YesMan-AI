# xEditLib Guide (Fallout: New Vegas)

How the toolbox reads and writes FNV plugins programmatically from Node.js, via the
`xeditlib` wrapper around **XEditLib.dll** (the engine inside xEdit/zEdit).

**Status: validated** against a real FNV install — `xeditlib` loads `FalloutNV.esm` (465,016
records) in FNV mode and creates records in memory. See `examples/`.

## Install

`xeditlib` is **not on the public npm registry** — install from GitHub. The package
**bundles `XEditLib.dll` and `FalloutNV.Hardcoded.dat`** (FNV record definitions), so no
separate zEdit/xEdit download is needed.

```bash
npm install            # uses package.json: "xeditlib": "github:WingedGuardian/xeditlib"
# or directly:
npm install github:WingedGuardian/xeditlib
```

Requires Node.js (tested on v24) and `koffi` (pulled in automatically for the FFI layer).

## Initialize for FNV

```js
const xelib = require('xeditlib');
xelib.init();
xelib.setLanguage('English');
xelib.setGamePath('C:\\Program Files (x86)\\Steam\\steamapps\\common\\Fallout New Vegas\\'); // your FNV path
xelib.setGameMode(xelib.GM_FNV);   // 0 = Fallout: New Vegas  (FO3=1, TES4=2, TES5=3, SSE=4, FO4=5)
```

- **Game path**: the examples auto-detect it from the registry key
  `HKLM\SOFTWARE\WOW6432Node\Bethesda Softworks\FalloutNV` → `Installed Path`
  (read from the FNV registry key).
- XEditLib also reads that same registry key internally for game-mode 0.

## Load plugins

```js
xelib.loadPlugins('FalloutNV.esm', true, false); // list (\n-separated), smartLoad, buildRefs
await xelib.waitForLoader();                       // resolves when getLoaderStatus()===2
const file = xelib.fileByName('FalloutNV.esm');
```

- `smartLoad=true` auto-loads required masters.
- `buildRefs=false` is faster and fine for read-only inspection; pass `true` (or call
  `buildReferences`) when you need "referenced by" data.

## Read records & elements

```js
const records = xelib.getRecords(file, '', false);   // '' = all sigs; false = exclude overrides
for (const r of records) {
    xelib.signature(r);                 // 'WEAP', 'NPC_', 'SCPT', …
    xelib.getFormID(r).toString(16);    // numeric FormID
    xelib.getValue(r, 'EDID');          // editor ID (no dedicated editorID() helper)
    xelib.displayName(r);
    xelib.getValue(r, 'DATA\\Damage');  // nested element path (note: escaped backslash)
    xelib.release(r);                   // ALWAYS release handles
}
```

Key functions: `getElement`, `getElements`, `elementCount`, `hasElement`, `getValue` /
`getIntValue` / `getFloatValue`, `signature`, `name` / `longName` / `displayName`,
`getFormID`, `getRecord`, `getRecords`, `getOverrides`, `getReferencedBy`.

## Write records (with the mandatory dry-run convention)

Write functions: `addFile`, `addElement`, `addElementValue`, `setValue` / `setIntValue` /
`setFloatValue`, `removeElement`, `saveFile`.

**Two-pass rule (enforced toolbox convention):**
1. **Pass 1 — dry run:** build everything in memory and print what *would* change. **Do NOT
   call `saveFile()`.**
2. **User reviews** the preview.
3. **Pass 2 — write:** only after approval, call `saveFile(file)`.

See `examples/create-esp.js` (`--write` flag gates the actual `saveFile`).

> The Edit/Write hooks block direct writes to `.esp/.esm/.bsa`, but xEditLib writes through
> Node's `saveFile()` — so the dry-run discipline is what protects you here. Always preview first.

## Handle hygiene

Every handle from `getElement(s)`, `getRecords`, `fileByName`, etc. must be `release()`d.
Call `xelib.close()` at the end. Leaking handles bloats memory across long runs.

## MO2 caveat (important)

XEditLib loads plugins from the game's `Data/` folder. **Under Mod Organizer 2, your
installed mods are NOT in `Data/`** — they live in the MO2 instance and only overlay `Data/`
at runtime via the VFS. To work on a modded load order:
- **Run the Node script through MO2** (add `node`/a `.bat` as an MO2 executable) so the VFS is active, **or**
- point the script at a data path that actually contains the target plugin, **or**
- for single-plugin inspection, copy the plugin to a readable path and load it explicitly.

(See the "Mod Organizer 2" sections in `CLAUDE.md` and `KNOWLEDGEBASE.md`.)

## Alternative: xEdit Apply Scripts (Pascal)

For batch/repetitive record work, xEdit's **Apply Script** (Pascal) is often faster to
express than Node. Load plugins in **FNVEdit**, right-click → *Apply Script* → choose a
script. API: [Tome of xEdit — Scripting Functions](https://tes5edit.github.io/docs/13-Scripting-Functions.html).
Use xEditLib (this guide) for programmatic/analysis work; use Apply Scripts for in-tool batch edits.

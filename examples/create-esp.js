// create-esp.js — Create a new Fallout: New Vegas plugin and add a simple record.
//
// Usage (DRY-RUN by default — previews, does NOT write):
//   node examples/create-esp.js MyMod.esp
// To actually write the file (after you've reviewed the dry-run):
//   node examples/create-esp.js MyMod.esp --write
//
// Demonstrates the toolbox's mandatory two-pass dry-run convention:
//   pass 1 = build in memory + print what WOULD be written (no SaveFile)
//   pass 2 = same, but call saveFile() only when --write is given and the user approved.
//
// Uses xEditLib in FNV mode (GM_FNV = 0). The new plugin is written into the game's
// Data/ folder by default. Under MO2, write to a mod folder / overwrite instead and
// enable it in MO2 (do NOT drop files directly into Data/).

const xelib = require('xeditlib');
const { execSync } = require('child_process');

function fnvGamePathFromRegistry() {
    try {
        const out = execSync(
            'reg query "HKLM\\SOFTWARE\\WOW6432Node\\Bethesda Softworks\\FalloutNV" /v "Installed Path"',
            { encoding: 'utf8' });
        const m = out.match(/Installed Path\s+REG_SZ\s+(.+)/i);
        if (m) return m[1].trim().replace(/\\?$/, '\\');
    } catch (_) {}
    return null;
}

const name = process.argv[2];
const WRITE = process.argv.includes('--write');
if (!name) { console.error('Usage: node examples/create-esp.js <NewMod.esp> [--write]'); process.exit(1); }
const gamePath = fnvGamePathFromRegistry();
if (!gamePath) { console.error('Could not determine FNV game path.'); process.exit(1); }

xelib.init();
xelib.setLanguage('English');
xelib.setGamePath(gamePath);
xelib.setGameMode(xelib.GM_FNV);
xelib.clearMessages();

// A new plugin needs FalloutNV.esm as a master to reference base records.
xelib.loadPlugins('FalloutNV.esm', true, false);

xelib.waitForLoader().then(() => {
    xelib.clearMessages();

    // --- Build in memory ---
    const file = xelib.addFile(name);
    // Example: add a NOTE record (simple, self-contained) as a demonstration.
    const noteGroup = xelib.addElement(file, 'NOTE');
    const note = xelib.addElement(noteGroup, '.');           // new record in the group
    xelib.addElementValue(note, 'EDID', 'FNVTK_HelloNote');
    xelib.addElementValue(note, 'FULL', 'Hello from YesMan AI');

    // --- Dry-run report ---
    console.log('=== DRY-RUN PREVIEW ===');
    console.log(`Would create plugin: ${name}`);
    console.log('Records that would be authored:');
    for (const r of xelib.getRecords(file, '', false)) {
        const fid = xelib.getFormID(r).toString(16).padStart(8, '0');
        let edid = ''; try { edid = xelib.getValue(r, 'EDID'); } catch (_) {}
        console.log(`  [${fid}] ${xelib.signature(r)} ${edid} — ${xelib.displayName(r)}`);
        xelib.release(r);
    }

    if (WRITE) {
        xelib.saveFile(file);   // writes <gamePath>\Data\<name>
        console.log(`\nWROTE: ${gamePath}Data\\${name}`);
    } else {
        console.log('\n(no file written — re-run with --write after review)');
    }

    xelib.release(noteGroup);
    xelib.release(file);
    xelib.close();
    console.log('Done.');
}).catch(err => { console.error('Error:', err.message); try { xelib.close(); } catch (_) {} process.exit(1); });

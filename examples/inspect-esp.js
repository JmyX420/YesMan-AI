// inspect-esp.js — Inspect a Fallout: New Vegas plugin and summarize its records.
//
// Usage:  node examples/inspect-esp.js <PluginName.esp> [GamePath]
//   e.g.  node examples/inspect-esp.js FalloutNV.esm
//         node examples/inspect-esp.js MyMod.esp "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Fallout New Vegas\\"
//
// Reads the game path from the FNV registry install if not supplied. Uses xEditLib
// in Fallout: New Vegas mode (GM_FNV = 0). READ-ONLY — never calls SaveFile.
//
// MO2 NOTE: xEditLib loads from the game Data/ folder. Under Mod Organizer 2, mods
// installed in the MO2 instance are NOT in Data/ unless this script is launched
// through MO2's VFS. To inspect a mod's plugin directly, either run via MO2 or pass
// a game path whose Data/ actually contains the plugin.

const xelib = require('xeditlib');
const { execSync } = require('child_process');

function fnvGamePathFromRegistry() {
    try {
        const out = execSync(
            'reg query "HKLM\\SOFTWARE\\WOW6432Node\\Bethesda Softworks\\FalloutNV" /v "Installed Path"',
            { encoding: 'utf8' }
        );
        const m = out.match(/Installed Path\s+REG_SZ\s+(.+)/i);
        if (m) return m[1].trim().replace(/\\?$/, '\\');
    } catch (_) { /* fall through */ }
    return null;
}

const plugin = process.argv[2];
if (!plugin) {
    console.error('Usage: node examples/inspect-esp.js <PluginName.esp> [GamePath]');
    process.exit(1);
}
const gamePath = process.argv[3] || fnvGamePathFromRegistry();
if (!gamePath) {
    console.error('Could not determine FNV game path. Pass it as the 2nd argument.');
    process.exit(1);
}

xelib.init();
xelib.setLanguage('English');
xelib.setGamePath(gamePath);
xelib.setGameMode(xelib.GM_FNV); // 0 = Fallout: New Vegas
xelib.clearMessages();

console.log(`Game:   ${gamePath}`);
console.log(`Plugin: ${plugin}\n`);

// smartLoad=true pulls in required masters automatically; buildRefs=false (faster, read-only)
xelib.loadPlugins(plugin, true, false);

xelib.waitForLoader().then(() => {
    xelib.clearMessages();

    const file = xelib.fileByName(plugin);
    if (!file) throw new Error(`Plugin not found after load: ${plugin} (is it in Data/?)`);

    console.log('=== File ===');
    console.log('  Name:        ', xelib.name(file));
    let masters = [];
    try { masters = xelib.getElements(xelib.getElement(file, 'File Header\\Master Files')); } catch (_) {}
    console.log('  Masters:     ', masters.length ? masters.map(m => xelib.getValue(m, 'MAST')).join(', ') : '(none)');
    masters.forEach(m => xelib.release(m));

    // Record-type breakdown (records authored by THIS plugin, excluding overrides)
    const records = xelib.getRecords(file, '', false);
    const bySig = {};
    for (const r of records) {
        const sig = xelib.signature(r);
        bySig[sig] = (bySig[sig] || 0) + 1;
    }
    console.log(`\n=== Records authored by this plugin: ${records.length} ===`);
    Object.entries(bySig).sort((a, b) => b[1] - a[1]).forEach(([sig, n]) => {
        console.log(`  ${sig.padEnd(6)} ${n}`);
    });

    // Sample a few notable records
    console.log('\n=== Sample (first 10) ===');
    for (const r of records.slice(0, 10)) {
        const fid = xelib.getFormID(r).toString(16).padStart(8, '0');
        let edid = '';
        try { edid = xelib.getValue(r, 'EDID'); } catch (_) {}
        console.log(`  [${fid}] ${xelib.signature(r).padEnd(6)} ${edid.padEnd(28)} — ${xelib.displayName(r)}`);
    }

    records.forEach(r => xelib.release(r));
    xelib.release(file);
    xelib.close();
    console.log('\nDone (read-only).');
}).catch(err => {
    console.error('Error:', err.message);
    try { xelib.close(); } catch (_) {}
    process.exit(1);
});

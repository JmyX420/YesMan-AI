// diff-esp.js — Compare two Fallout: New Vegas plugins and report what differs.
//
// Usage:  node examples/diff-esp.js <Original.esp> <Modified.esp> [GamePath]
//
// Reports records added, removed, and changed between the two plugins (by FormID).
// READ-ONLY — never calls SaveFile. Uses xEditLib in FNV mode (GM_FNV = 0).
//
// MO2 NOTE: both plugins must be visible in the Data/ folder xEditLib loads from
// (run through MO2's VFS, or copy the plugins somewhere on the active data path).

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

const [a, b] = [process.argv[2], process.argv[3]];
if (!a || !b) {
    console.error('Usage: node examples/diff-esp.js <Original.esp> <Modified.esp> [GamePath]');
    process.exit(1);
}
const gamePath = process.argv[4] || fnvGamePathFromRegistry();
if (!gamePath) { console.error('Could not determine FNV game path.'); process.exit(1); }

xelib.init();
xelib.setLanguage('English');
xelib.setGamePath(gamePath);
xelib.setGameMode(xelib.GM_FNV);
xelib.clearMessages();

// Load both (newline-separated list). smartLoad pulls masters; buildRefs off.
xelib.loadPlugins(`${a}\n${b}`, true, false);

function indexRecords(file) {
    const map = new Map(); // formID(hex) -> { sig, edid }
    for (const r of xelib.getRecords(file, '', false)) {
        const fid = xelib.getFormID(r).toString(16).padStart(8, '0');
        let edid = ''; try { edid = xelib.getValue(r, 'EDID'); } catch (_) {}
        map.set(fid, { sig: xelib.signature(r), edid });
        xelib.release(r);
    }
    return map;
}

xelib.waitForLoader().then(() => {
    xelib.clearMessages();
    const fa = xelib.fileByName(a), fb = xelib.fileByName(b);
    if (!fa || !fb) throw new Error('One or both plugins not found in the data path.');

    const ma = indexRecords(fa), mb = indexRecords(fb);
    const added = [], removed = [];
    for (const k of mb.keys()) if (!ma.has(k)) added.push(k);
    for (const k of ma.keys()) if (!mb.has(k)) removed.push(k);

    console.log(`Comparing:\n  A: ${a} (${ma.size} records)\n  B: ${b} (${mb.size} records)\n`);
    console.log(`=== Added in B (${added.length}) ===`);
    added.slice(0, 50).forEach(k => console.log(`  + [${k}] ${mb.get(k).sig} ${mb.get(k).edid}`));
    if (added.length > 50) console.log(`  … and ${added.length - 50} more`);
    console.log(`\n=== Removed from A (${removed.length}) ===`);
    removed.slice(0, 50).forEach(k => console.log(`  - [${k}] ${ma.get(k).sig} ${ma.get(k).edid}`));
    if (removed.length > 50) console.log(`  … and ${removed.length - 50} more`);

    // Note: deep field-level "changed" detection requires per-record element walking;
    // this script reports presence/absence. Extend with elementEquals() for field diffs.
    console.log('\nNote: shared FormIDs are not deep-compared here — extend with elementEquals() for field-level diffs.');

    xelib.release(fa); xelib.release(fb); xelib.close();
    console.log('\nDone (read-only).');
}).catch(err => { console.error('Error:', err.message); try { xelib.close(); } catch (_) {} process.exit(1); });

#!/usr/bin/env node
// read-fos.js — Read/scan a Fallout: New Vegas (or FO3/TTW) .fos save file.
//
// FNV saves are UNCOMPRESSED (unlike Skyrim SE's LZ4 .ess), so we scan bytes directly —
// no decompression needed. Node-only, no dependencies.
//
// Usage:
//   node scripts/read-fos.js info    "<save.fos>"
//   node scripts/read-fos.js plugins "<save.fos>"
//   node scripts/read-fos.js search  "<save.fos>" --string "SomeEditorID"
//   node scripts/read-fos.js search  "<save.fos>" --formid 0x0006B531
//   node scripts/read-fos.js search  "<save.fos>" --hex DEADBEEF
//
// Verified against a real FNV/TTW save: signature "FO3SAVEGAME", string fields encoded as
//   0x7C <uint16 LE length> 0x7C <ASCII bytes>.

const fs = require('fs');

const SIG = 'FO3SAVEGAME';

function load(p) {
    const buf = fs.readFileSync(p);
    if (buf.toString('latin1', 0, SIG.length) !== SIG) {
        throw new Error(`Not a .fos save (missing "${SIG}" signature): ${p}`);
    }
    return buf;
}

// Read a "| len | string" field at offset; returns {value, next} or null.
function readStrField(buf, off) {
    if (buf[off] !== 0x7c) return null;
    const len = buf.readUInt16LE(off + 1);
    if (buf[off + 3] !== 0x7c) return null;
    if (len === 0 || len > 255) return null;
    const s = buf.toString('latin1', off + 4, off + 4 + len);
    if (!/^[ -~]+$/.test(s)) return null;
    return { value: s, next: off + 4 + len };
}

// Find and walk the plugin list (anchored on the first vanilla master present).
function extractPlugins(buf) {
    const anchors = ['FalloutNV.esm', 'Fallout3.esm'];
    let start = -1;
    for (const a of anchors) {
        const i = buf.indexOf(Buffer.from(a, 'latin1'));
        if (i >= 0) { start = i - 4; break; }
    }
    if (start < 0) return [];
    const plugins = [];
    let off = start;
    while (true) {
        const r = readStrField(buf, off);
        if (!r) break;
        plugins.push(r.value);
        off = r.next;
    }
    return plugins;
}

function countOccurrences(buf, needle) {
    let c = 0, i = -1;
    while ((i = buf.indexOf(needle, i + 1)) >= 0) c++;
    return c;
}

const [cmd, file] = [process.argv[2], process.argv[3]];
if (!cmd || !file) {
    console.error('Usage: node scripts/read-fos.js <info|plugins|search> "<save.fos>" [--string S | --formid 0xID | --hex BYTES]');
    process.exit(1);
}

try {
    const buf = load(file);
    if (cmd === 'info') {
        const plugins = extractPlugins(buf);
        console.log(JSON.stringify({
            file, signature: SIG, sizeBytes: buf.length, compressed: false, pluginCount: plugins.length
        }, null, 2));
    } else if (cmd === 'plugins') {
        const plugins = extractPlugins(buf);
        console.log(JSON.stringify({ count: plugins.length, plugins }, null, 2));
    } else if (cmd === 'search') {
        const flag = process.argv[4], val = process.argv[5];
        let needle, label;
        if (flag === '--string') { needle = Buffer.from(val, 'latin1'); label = `string "${val}"`; }
        else if (flag === '--formid') {
            const id = parseInt(val, 16) >>> 0;
            needle = Buffer.alloc(4); needle.writeUInt32LE(id); label = `FormID ${val} (LE)`;
        } else if (flag === '--hex') { needle = Buffer.from(val.replace(/\s/g, ''), 'hex'); label = `hex ${val}`; }
        else { console.error('search needs --string / --formid / --hex'); process.exit(1); }
        const count = countOccurrences(buf, needle);
        const offsets = [];
        let i = -1; while ((i = buf.indexOf(needle, i + 1)) >= 0 && offsets.length < 20) offsets.push('0x' + i.toString(16));
        console.log(JSON.stringify({ search: label, occurrences: count, firstOffsets: offsets }, null, 2));
    } else {
        console.error(`Unknown command: ${cmd}`);
        process.exit(1);
    }
} catch (e) {
    console.error('Error:', e.message);
    process.exit(1);
}

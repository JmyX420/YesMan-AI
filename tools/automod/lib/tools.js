// Locate an external tool (BSArch, oggenc2, nif_info) by searching:
//   1. the FNV game folder (and its Optional\ subfolder)
//   2. the system PATH (via `where`)
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { fnvGamePath } = require('./registry');

function findTool(exeNames) {
    const names = Array.isArray(exeNames) ? exeNames : [exeNames];
    const game = fnvGamePath();
    const dirs = [];
    if (game) {
        const root = game.replace(/\\$/, '');
        dirs.push(root, path.join(root, 'Optional'), path.join(root, 'tools'));
    }
    for (const d of dirs) {
        for (const n of names) {
            const p = path.join(d, n);
            if (fs.existsSync(p)) return p;
        }
    }
    for (const n of names) {
        try {
            // stdio: ignore stderr so `where`'s "Could not find files" doesn't leak to the console
            const hit = execSync(`where ${n}`, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).split(/\r?\n/)[0].trim();
            if (hit && fs.existsSync(hit)) return hit;
        } catch (_) { /* not on PATH */ }
    }
    return null;
}

module.exports = { findTool };

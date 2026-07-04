// Resolve the Fallout: New Vegas game path from the registry.
const { execSync } = require('child_process');

function fnvGamePath() {
    try {
        const out = execSync(
            'reg query "HKLM\\SOFTWARE\\WOW6432Node\\Bethesda Softworks\\FalloutNV" /v "Installed Path"',
            { encoding: 'utf8' }
        );
        const m = out.match(/Installed Path\s+REG_SZ\s+(.+)/i);
        if (m) return m[1].trim().replace(/\\?$/, '\\'); // ensure trailing backslash
    } catch (_) { /* not found */ }
    return null;
}

module.exports = { fnvGamePath };

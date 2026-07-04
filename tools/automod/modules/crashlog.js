// crashlog module — parse FNV crash logs and surface the useful bits.
// Handles modern crash loggers (Cobb/Yvile/csimonca: CobbCrashLogger.log / *.log) AND NVAC's nvac.log.
// Commands: analyze, find
const fs = require('fs');
const path = require('path');

// Modules that are almost never the actual culprit (game exe + OS/GPU/CRT runtime).
const NOISE = /^(FalloutNV\.exe|ntdll|kernel(base|32)|user32|gdi(32|full)|win32u|d3d9|d3d11|dxgi|nvwgf|nvldumd|nvspcap|ig\w*|atig|aticfx|msvcr|msvcp|ucrtbase|vcruntime|combase|rpcrt4|sechost|advapi32|ole32|shcore|shell32|dbghelp|wow64|apphelp)/i;

function analyze(text) {
    const isNvac = /^\d{8}\s+[\^h_~]\s/m.test(text) || /\bTRUNCATE\b/.test(text);
    const isModern = /Unhandled exception|EXCEPTION_[A-Z_]+|Call Stack|GAME CRASHED|Sic transit/i.test(text);

    const exception = (text.match(/((?:Unhandled exception|EXCEPTION_[A-Z_]+)[^\r\n]*)/i) || [])[1] || null;

    // Module frequency across the whole log (call-stack frames, NVAC hook lines, etc.).
    const counts = {};
    for (const m of text.matchAll(/([A-Za-z0-9_][\w.\-]*\.(?:dll|exe))/g)) {  // module token (no spaces → avoids grabbing the address/timestamp prefix)
        const n = m[1].trim();
        counts[n] = (counts[n] || 0) + 1;
    }
    const suspectModules = Object.entries(counts)
        .filter(([n]) => !NOISE.test(n))
        .sort((a, b) => b[1] - a[1]).slice(0, 12)
        .map(([module, hits]) => ({ module, hits }));

    // Loaded plugins (modern logs list them; one per line ending .esp/.esm).
    const plugins = [...new Set(
        [...text.matchAll(/^[\s>*\-]*([\w '().+\-]+\.es[mp])\s*$/gim)].map(m => m[1].trim())
    )];

    return {
        format: isModern ? 'modern crash logger' : (isNvac ? 'NVAC (nvac.log)' : 'unknown'),
        exception,
        suspectModules,
        pluginCount: plugins.length,
        note: 'Suspect modules are ranked by appearance with game/OS/GPU/CRT noise filtered out — but the TOP module is NOT necessarily the cause (it may just be where the game was executing). Read the full log; favour frames with resolved forms/EditorIDs; cross-reference each .dll to its mod. NVAC logs are terse address traces (it suppresses crashes rather than diagnosing); prefer a modern crash logger (Yvile\'s) for real debugging.',
    };
}

exports.run = async (command, ctx) => {
    const { positionals, emit, fail, gamePath } = ctx;

    switch (command) {
        case 'analyze': {
            const file = positionals[0];
            if (!file) return fail('usage: crashlog analyze <logfile> [--json]');
            if (!fs.existsSync(file)) return fail(`log not found: ${file}`);
            return emit({ action: 'analyze', file, ...analyze(fs.readFileSync(file, 'utf8')) });
        }

        case 'find': {
            const root = gamePath ? gamePath.replace(/\\$/, '') : null;
            const docs = process.env.USERPROFILE ? path.join(process.env.USERPROFILE, 'Documents', 'My Games', 'FalloutNV') : null;
            const candidates = [];
            const add = (p) => { if (p && fs.existsSync(p)) { try { candidates.push({ path: p, mtime: fs.statSync(p).mtime, bytes: fs.statSync(p).size }); } catch (_) {} } };
            if (root) { add(path.join(root, 'nvac.log')); add(path.join(root, 'CobbCrashLogger.log')); add(path.join(root, 'crashlogger.log')); }
            if (docs) { for (const d of ['NVSE', 'Crash Logs', '.']) { const dir = path.join(docs, d); try { for (const f of fs.readdirSync(dir)) if (/crash|nvac/i.test(f) && /\.(log|txt)$/i.test(f)) add(path.join(dir, f)); } catch (_) {} } }
            candidates.sort((a, b) => b.mtime - a.mtime);
            return emit({ action: 'find', found: candidates.map(c => ({ ...c, mtime: c.mtime.toISOString() })),
                note: 'Under MO2, the game runs in the VFS — crash logs are usually captured into the MO2 instance\'s overwrite\\ (e.g. overwrite\\Root\\ or overwrite\\NVSE\\), NOT the game root. Check there too.' });
        }

        default:
            return fail(`crashlog: unknown command '${command}'. Commands: analyze, find`);
    }
};

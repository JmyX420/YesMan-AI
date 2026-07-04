// funcs module — extract a best-effort function-name index from an NVSE extender DLL.
// HEURISTIC: scans the DLL for command-style identifiers (verb-prefixed + ar_/sv_/con_ etc.),
// filters obvious WinAPI/CRT import noise. NOT a perfect command-table parse and NOT exhaustive —
// geckwiki "Functions" categories are the authoritative complete reference. Commands: list, scan
const fs = require('fs');
const path = require('path');

const VERB = /^(Get|Set|Is|Has|Add|Remove|Force|Toggle|Create|Destroy|Play|Stop|Call|Run|Sort|Insert|Append|Clear|Copy|Move|Equip|Unequip|Cast|Dispel|Apply|Reset|Enable|Disable|Show|Hide|Update|Print|Format|Load|Save|Open|Close|Read|Write|Send|Queue|Register|Unregister|Mod|Damage|Restore|Push|Pop|Find|Count|List|Make|Build|Spawn|Place|Attach|Detach|Link|Unlink|Refresh|Rebuild|Recalculate|Reload|Compile|Eval|Test|Try)[A-Z][A-Za-z0-9_]{2,}$/;
const PREFIX = /^(ar_|sv_|con_|kPlay|tile_|ui_|le_|fn_|jip_)[A-Za-z0-9_]{2,}$/;
const API_NOISE = /(CommandLine|Console(Mode|OutputCP|CP|CtrlHandler|Screen)|Current(Process|Thread|Directory)|ProcAddress|ModuleHandle|ModuleFileName|LastError|TickCount|StdHandle|SystemTime|SystemInfo|StartupInfo|EnvironmentStrings?|EnvironmentVariable|StringType|ProcessHeap|ProcessTimes|ExitCode|ThreadLocale|TimeZone|DateFormat|TimeFormat|LocaleInfo|UserDefault|UserGeo|FileType|FileAttributes|FileSize|FullPathName|TempPath|WindowsDirectory|VersionEx|NumberOf|CPInfo|^GetACP$|^GetOEMCP$|UnhandledExceptionFilter|VectoredException|ProcessorFeature|DebuggerPresent|ValidLocale|ValidCodePage|WriteConsole|ReadConsole|WriteFile|ReadFile|CloseHandle|CreateFile|CreateThread|CreateMutex)/;

function extract(dll) {
    const s = fs.readFileSync(dll).toString('latin1');
    const set = new Set();
    for (const m of s.matchAll(/[A-Za-z_][A-Za-z0-9_]{2,48}/g)) {
        const n = m[0];
        if (API_NOISE.test(n)) continue;
        if (VERB.test(n) || PREFIX.test(n)) set.add(n);
    }
    return [...set].sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
}

const HEUR = 'Heuristic extraction (string scan + prefix/denylist filters) — high precision but NOT exhaustive; oddly-named functions may be missed and some noise may remain. geckwiki "Functions" categories are the authoritative complete reference.';

exports.run = async (command, ctx) => {
    const { positionals, flags, emit, fail } = ctx;

    switch (command) {
        case 'list': {
            const dll = positionals[0];
            if (!dll) return fail('usage: funcs list <plugin.dll> [--grep <substr>] [--limit N]');
            if (!fs.existsSync(dll)) return fail(`not found: ${dll}`);
            let fns = extract(dll);
            if (flags.grep) fns = fns.filter(f => f.toLowerCase().includes(String(flags.grep).toLowerCase()));
            const limit = flags.limit !== undefined ? Number(flags.limit) : fns.length;
            return emit({ action: 'list', dll: path.basename(dll), count: fns.length, functions: fns.slice(0, limit), note: HEUR });
        }

        case 'scan': {
            const dir = positionals[0];
            if (!dir) return fail('usage: funcs scan <dir> [--grep <substr>]');
            const dlls = [];
            (function walk(d) { let e; try { e = fs.readdirSync(d, { withFileTypes: true }); } catch (_) { return; } for (const x of e) { const p = path.join(d, x.name); if (x.isDirectory()) walk(p); else if (/\.dll$/i.test(x.name)) dlls.push(p); } })(dir);
            const per = dlls.map(d => {
                let fns = extract(d);
                if (flags.grep) fns = fns.filter(f => f.toLowerCase().includes(String(flags.grep).toLowerCase()));
                return { dll: path.basename(d), count: fns.length, ...(flags.grep ? { matches: fns } : {}) };
            }).filter(x => x.count > 0).sort((a, b) => b.count - a.count);
            return emit({ action: 'scan', dir, plugins: per, totalApprox: per.reduce((s, x) => s + x.count, 0), note: HEUR });
        }

        default:
            return fail(`funcs: unknown command '${command}'. Commands: list, scan`);
    }
};

// bsa module — wrap BSArch.exe for FNV archives. Commands: list, unpack, pack, extract-file
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

function bsarch(ctx) {
    const exe = ctx.findTool(['BSArch.exe', 'BSArch64.exe']);
    if (!exe) ctx.fail('BSArch.exe not found (searched the FNV game folder and PATH). Install BSArch (ships with xEdit).');
    return exe;
}
function run(exe, args) { return execFileSync(exe, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }); }

// Parse `BSArch.exe <archive> -list` output into archive-relative file paths.
function parseList(out) {
    return out.split(/\r?\n/)
        .map(l => l.trim())
        .filter(l => l && /[\\/].+\.\w+$|\.\w+$/.test(l) && !/^BSArch|^Packer|^The Source|^https?:|files?:/i.test(l));
}

exports.run = async (command, ctx) => {
    const { positionals, flags, emit, fail, dryRun } = ctx;
    const exe = bsarch(ctx);

    switch (command) {
        case 'list': {
            const archive = positionals[0];
            if (!archive) return fail('usage: bsa list <archive.bsa> [--filter <substr>] [--limit N]');
            let files = parseList(run(exe, [archive, '-list']));
            if (flags.filter) files = files.filter(f => f.toLowerCase().includes(String(flags.filter).toLowerCase()));
            const limit = Number(flags.limit ?? 100);
            return emit({ action: 'list', archive, total: files.length, showing: Math.min(limit, files.length), files: files.slice(0, limit) });
        }

        case 'unpack': {
            const [archive, folder] = positionals;
            if (!archive) return fail('usage: bsa unpack <archive.bsa> <folder> [--dry-run]');
            if (dryRun) return emit({ action: 'unpack', archive, folder, dryRun: true, wouldRun: `BSArch unpack "${archive}" "${folder || '(archive folder)'}"` });
            run(exe, folder ? ['unpack', archive, folder] : ['unpack', archive]);
            return emit({ action: 'unpack', archive, folder: folder || '(archive folder)' });
        }

        case 'pack': {
            const [src, archive] = positionals;
            if (!src || !archive) return fail('usage: bsa pack <source_dir> <archive.bsa> [--compress] [--dry-run]');
            const args = ['pack', src, archive, '-fnv'];
            if (flags.compress) args.push('-z');
            if (dryRun) return emit({ action: 'pack', src, archive, fnv: true, compress: !!flags.compress, dryRun: true, wouldRun: 'BSArch ' + args.join(' ') });
            run(exe, args);
            return emit({ action: 'pack', src, archive, fnv: true, compress: !!flags.compress });
        }

        case 'extract-file': {
            // BSArch has no single-file extract; unpack to a temp dir and copy the target out.
            const [archive, inner, outDir] = positionals;
            if (!archive || !inner || !outDir) return fail('usage: bsa extract-file <archive.bsa> <internal/path.ext> <out_dir> [--dry-run]');
            if (dryRun) return emit({ action: 'extract-file', archive, inner, outDir, dryRun: true });
            const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'bsa-'));
            try {
                run(exe, ['unpack', archive, tmp]);
                const srcPath = path.join(tmp, inner.replace(/\//g, '\\'));
                if (!fs.existsSync(srcPath)) return fail(`file not found in archive: ${inner}`);
                fs.mkdirSync(outDir, { recursive: true });
                const dest = path.join(outDir, path.basename(inner));
                fs.copyFileSync(srcPath, dest);
                return emit({ action: 'extract-file', archive, inner, out: dest, bytes: fs.statSync(dest).size });
            } finally {
                try { fs.rmSync(tmp, { recursive: true, force: true }); } catch (_) {}
            }
        }

        default:
            return fail(`bsa: unknown command '${command}'. Commands: list, unpack, pack, extract-file`);
    }
};

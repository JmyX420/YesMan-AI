// esp module — create/inspect FNV plugins via xeditlib (GM_FNV=0). No Spriggit for FNV.
// Commands: info, query, record, create, add-record, add-misc, add-note, add-global, add-weapon, add-armor
// query/record are READ-ONLY (records a plugin defines/overrides + full field detail) — back the
// MO2 MCP's record tools. Writes follow the two-pass dry-run convention (--write to save).
const fs = require('fs');
const xelib = require('xeditlib');

function setup(gamePath) {
    xelib.init();
    xelib.setLanguage('English');
    xelib.setGamePath(gamePath);
    xelib.setGameMode(xelib.GM_FNV);
    xelib.clearMessages();
}

function asArray(v) { return v === undefined ? [] : (Array.isArray(v) ? v : [v]); }

// Read a sub-element value without throwing when the path is absent.
function safeVal(rec, path) {
    try { return xelib.hasElement(rec, path) ? xelib.getValue(rec, path) : ''; }
    catch (_) { return ''; }
}
function tryLongName(rec) { try { return xelib.longName(rec); } catch (_) { return undefined; } }
const hex8 = (n) => n.toString(16).padStart(8, '0');

// Set an element value, creating the element/path if needed.
function setField(rec, path, value) {
    if (!xelib.hasElement(rec, path)) xelib.addElement(rec, path);
    xelib.setValue(rec, path, String(value));
}

async function addRecord(ctx, sig, opts) {
    const { gamePath, dryRun, flags, emit, fail } = ctx;
    const plugin = opts.plugin;
    const edid = opts.edid;
    if (!plugin || !edid) return fail(`usage: esp ${opts.usage}`);
    const write = !!flags.write;

    setup(gamePath);
    const dataPath = gamePath + 'Data\\' + plugin;
    const exists = fs.existsSync(dataPath);
    // Load the existing plugin (pulls its masters) or FalloutNV.esm for a new one.
    xelib.loadPlugins(exists ? plugin : 'FalloutNV.esm', true, false);
    await xelib.waitForLoader();

    let file = exists ? xelib.fileByName(plugin) : xelib.addFile(plugin);
    const grp = xelib.addElement(file, sig);
    const rec = xelib.addElement(grp, '.');

    const applied = [], failed = [];
    const trySet = (path, value) => {
        if (value === undefined || value === '') return;
        try { setField(rec, path, value); applied.push(`${path}=${value}`); }
        catch (e) { failed.push(`${path} (${e.message})`); }
    };

    trySet('EDID', edid);
    if (opts.full) trySet('FULL', opts.full);
    for (const [path, val] of opts.fields || []) trySet(path, val);
    // generic --set "PATH=VALUE" (repeatable)
    for (const s of asArray(flags.set)) {
        const eq = String(s).indexOf('=');
        if (eq < 0) { failed.push(`${s} (use PATH=VALUE)`); continue; }
        trySet(String(s).slice(0, eq), String(s).slice(eq + 1));
    }

    const formID = xelib.getFormID(rec).toString(16).padStart(8, '0');
    const preview = { plugin, signature: sig, formID, editorID: edid, full: opts.full, applied, failed };

    if (!write || dryRun) {
        xelib.close();
        return emit({ action: 'add', dryRun: true, note: 'no file written — re-run with --write after review', ...preview });
    }
    xelib.saveFile(file);
    xelib.close();
    return emit({ action: 'add', written: true, ...preview });
}

exports.run = async (command, ctx) => {
    const { positionals, flags, emit, fail, dryRun, gamePath } = ctx;
    if (!gamePath) return fail('FNV game path not found in registry.');

    switch (command) {
        case 'info': {
            const plugin = positionals[0];
            if (!plugin) return fail('usage: esp info <plugin.esp>');
            // --game-dir lets a caller point xEditLib at a synthetic game dir (a temp dir whose
            // Data\ holds the plugin + its masters) so MO2 mod-folder plugins can be read. The
            // MO2 MCP stages those hardlinks; standalone callers use the real game dir.
            const effGame = flags['game-dir'] ? String(flags['game-dir']).replace(/[\\/]+$/, '') + '\\' : gamePath;
            setup(effGame);
            try { xelib.loadPlugins(plugin, true, false); await xelib.waitForLoader(); }
            catch (e) { xelib.close(); return fail(`could not load '${plugin}': ${e.message}. NOTE: xEditLib runs outside MO2's VFS — a plugin that lives only in an MO2 mod folder must be staged into the data path (the MO2 MCP does this automatically; standalone, the plugin must be in the game's Data folder).`); }
            const file = xelib.fileByName(plugin);
            if (!file) { xelib.close(); return fail(`plugin not found in data path: ${plugin} (if it's an MO2 mod-folder plugin, run this through the MO2 MCP which stages it).`); }
            const recs = xelib.getRecords(file, '', false);
            const byType = {};
            for (const r of recs) { const s = xelib.signature(r); byType[s] = (byType[s] || 0) + 1; xelib.release(r); }
            let masters = [];
            try { masters = xelib.getElements(xelib.getElement(file, 'File Header\\Master Files')).map(m => xelib.getValue(m, 'MAST')); } catch (_) {}
            const out = { action: 'info', plugin, masters, recordCount: recs.length, byType };
            xelib.release(file); xelib.close();
            return emit(out);
        }

        case 'create': {
            const plugin = positionals[0];
            if (!plugin) return fail('usage: esp create <NewMod.esp> [--master FalloutNV.esm] [--write]');
            setup(gamePath);
            xelib.loadPlugins((flags.master || 'FalloutNV.esm'), true, false);
            await xelib.waitForLoader();
            const file = xelib.addFile(plugin);
            if (!flags.write || dryRun) { xelib.close(); return emit({ action: 'create', plugin, dryRun: true, note: 'no file written — re-run with --write' }); }
            xelib.saveFile(file); xelib.close();
            return emit({ action: 'create', plugin, written: true });
        }

        case 'add-record':
            return addRecord(ctx, positionals[1] || flags.sig, {
                plugin: positionals[0], edid: positionals[2], full: flags.full,
                usage: 'add-record <plugin> <SIG> <editorId> [--full "Name"] [--set PATH=VALUE ...] [--write]',
            });

        case 'add-misc':
            return addRecord(ctx, 'MISC', {
                plugin: positionals[0], edid: positionals[1], full: flags.name,
                fields: [['DATA\\Value', flags.value], ['DATA\\Weight', flags.weight]],
                usage: 'add-misc <plugin> <editorId> --name "Name" [--value N] [--weight N] [--write]',
            });

        case 'add-note':
            return addRecord(ctx, 'NOTE', {
                plugin: positionals[0], edid: positionals[1], full: flags.name,
                usage: 'add-note <plugin> <editorId> --name "Name" [--write]',
            });

        case 'add-global':
            return addRecord(ctx, 'GLOB', {
                plugin: positionals[0], edid: positionals[1],
                fields: [['FNAM', flags.type || 'f'], ['FLTV', flags.value ?? 0]],
                usage: 'add-global <plugin> <editorId> [--type s|l|f] [--value N] [--write]',
            });

        case 'add-weapon':
            return addRecord(ctx, 'WEAP', {
                plugin: positionals[0], edid: positionals[1], full: flags.name,
                fields: [['DATA\\Value', flags.value], ['DATA\\Health', flags.health], ['DATA\\Weight', flags.weight]],
                usage: 'add-weapon <plugin> <editorId> --name "Name" [--value N] [--health N] [--weight N] [--set DNAM\\...=N] [--write]',
            });

        case 'add-armor':
            return addRecord(ctx, 'ARMO', {
                plugin: positionals[0], edid: positionals[1], full: flags.name,
                fields: [['DATA\\Value', flags.value], ['DATA\\Health', flags.health], ['DATA\\Weight', flags.weight]],
                usage: 'add-armor <plugin> <editorId> --name "Name" [--value N] [--health N] [--weight N] [--set DNAM\\DT=N] [--write]',
            });

        case 'query': {
            // Enumerate records the plugin defines/overrides. READ-ONLY.
            const plugin = positionals[0];
            if (!plugin) return fail('usage: esp query <plugin> [--sig WEAP] [--match <substr>] [--limit N]');
            const sig = flags.sig ? String(flags.sig) : '';
            const match = flags.match ? String(flags.match).toLowerCase() : '';
            const limit = flags.limit ? Math.max(1, parseInt(flags.limit, 10)) : 200;
            // --game-dir lets a caller point xEditLib at a synthetic game dir (a temp dir whose
            // Data\ holds the plugin + its masters) so MO2 mod-folder plugins can be read. The
            // MO2 MCP stages those hardlinks; standalone callers use the real game dir.
            const effGame = flags['game-dir'] ? String(flags['game-dir']).replace(/[\\/]+$/, '') + '\\' : gamePath;
            setup(effGame);
            try { xelib.loadPlugins(plugin, true, false); await xelib.waitForLoader(); }
            catch (e) { xelib.close(); return fail(`could not load '${plugin}': ${e.message}. NOTE: xEditLib runs outside MO2's VFS — a plugin that lives only in an MO2 mod folder must be staged into the data path (the MO2 MCP does this automatically; standalone, the plugin must be in the game's Data folder).`); }
            const file = xelib.fileByName(plugin);
            if (!file) { xelib.close(); return fail(`plugin not found in data path: ${plugin} (if it's an MO2 mod-folder plugin, run this through the MO2 MCP which stages it).`); }
            // includeOverrides=true: a patch/fix plugin's changes are mostly OVERRIDES of
            // master records, not new records — we want those in "what does this plugin change".
            const recs = xelib.getRecords(file, sig, true);
            const records = [];
            let matched = 0;
            for (const r of recs) {
                const edid = safeVal(r, 'EDID');
                const full = safeVal(r, 'FULL');
                const ok = !match || (edid && edid.toLowerCase().includes(match)) || (full && full.toLowerCase().includes(match));
                if (ok) {
                    matched++;
                    if (records.length < limit) {
                        records.push({ formID: hex8(xelib.getFormID(r)), signature: xelib.signature(r), editorID: edid || undefined, name: full || undefined });
                    }
                }
                xelib.release(r);
            }
            xelib.release(file); xelib.close();
            return emit({ action: 'query', plugin, signature: sig || undefined, match: flags.match || undefined,
                scanned: recs.length, matched, returned: records.length, truncated: matched > records.length, records });
        }

        case 'record': {
            // Full field detail of one record (by FormID hex or EditorID). READ-ONLY.
            const plugin = positionals[0];
            const idArg = positionals[1];
            if (!plugin || !idArg) return fail('usage: esp record <plugin> <FormID(hex)|EditorID>');
            const wantHex = idArg.toLowerCase().replace(/^0x/, '');
            const isHex = /^[0-9a-f]{1,8}$/.test(wantHex);
            const wantFid = isHex ? wantHex.padStart(8, '0') : null;
            const wantEdid = idArg.toLowerCase();
            // --game-dir lets a caller point xEditLib at a synthetic game dir (a temp dir whose
            // Data\ holds the plugin + its masters) so MO2 mod-folder plugins can be read. The
            // MO2 MCP stages those hardlinks; standalone callers use the real game dir.
            const effGame = flags['game-dir'] ? String(flags['game-dir']).replace(/[\\/]+$/, '') + '\\' : gamePath;
            setup(effGame);
            try { xelib.loadPlugins(plugin, true, false); await xelib.waitForLoader(); }
            catch (e) { xelib.close(); return fail(`could not load '${plugin}': ${e.message}. NOTE: xEditLib runs outside MO2's VFS — a plugin that lives only in an MO2 mod folder must be staged into the data path (the MO2 MCP does this automatically; standalone, the plugin must be in the game's Data folder).`); }
            const file = xelib.fileByName(plugin);
            if (!file) { xelib.close(); return fail(`plugin not found in data path: ${plugin} (if it's an MO2 mod-folder plugin, run this through the MO2 MCP which stages it).`); }
            const recs = xelib.getRecords(file, '', true);
            let rec = null;
            for (const r of recs) {
                if (rec) { xelib.release(r); continue; }
                const fid = hex8(xelib.getFormID(r));
                const edid = safeVal(r, 'EDID');
                if ((wantFid && fid === wantFid) || (edid && edid.toLowerCase() === wantEdid)) rec = r;
                else xelib.release(r);
            }
            if (!rec) { xelib.release(file); xelib.close(); return fail(`record not found in ${plugin}: ${idArg} (try the EditorID, or the plugin-relative FormID hex)`); }
            let record;
            try { record = JSON.parse(xelib.elementToJson(rec)); }
            catch (e) { record = { error: 'elementToJson failed: ' + e.message }; }
            const out = {
                action: 'record', plugin,
                formID: hex8(xelib.getFormID(rec)), signature: xelib.signature(rec),
                editorID: safeVal(rec, 'EDID') || undefined, name: safeVal(rec, 'FULL') || undefined,
                longName: tryLongName(rec), record,
            };
            xelib.release(rec); xelib.release(file); xelib.close();
            return emit(out);
        }

        case 'overrides': {
            // Override/conflict chain for ONE record across the loaded order. READ-ONLY.
            // Needs the full load order (--load-order <file>, newline-separated, in order) so
            // every overriding plugin is visible.
            const plugin = positionals[0];
            const idArg = positionals[1];
            if (!plugin || !idArg) return fail('usage: esp overrides <plugin> <FormID(hex)|EditorID> [--game-dir <dir>] [--load-order <file>]');
            const effGame = flags['game-dir'] ? String(flags['game-dir']).replace(/[\\/]+$/, '') + '\\' : gamePath;
            setup(effGame);
            try {
                if (flags['load-order']) {
                    const order = fs.readFileSync(String(flags['load-order']), 'utf8').replace(/\r/g, '').trim();
                    xelib.loadPlugins(order, false, false);   // explicit full order
                } else {
                    xelib.loadPlugins(plugin, true, false);
                }
                await xelib.waitForLoader();
            } catch (e) { xelib.close(); return fail(`could not load order: ${e.message}`); }
            const file = xelib.fileByName(plugin);
            if (!file) { xelib.close(); return fail(`plugin not found in load order: ${plugin}`); }

            // locate the record in the target plugin
            const wantHex = idArg.toLowerCase().replace(/^0x/, '');
            const wantFid = /^[0-9a-f]{1,8}$/.test(wantHex) ? wantHex.padStart(8, '0') : null;
            const wantEdid = idArg.toLowerCase();
            const recs = xelib.getRecords(file, '', true);
            let rec = null;
            for (const r of recs) {
                if (rec) { xelib.release(r); continue; }
                const fid = hex8(xelib.getFormID(r));
                const edid = safeVal(r, 'EDID');
                if ((wantFid && fid === wantFid) || (edid && edid.toLowerCase() === wantEdid)) rec = r;
                else xelib.release(r);
            }
            if (!rec) { xelib.release(file); xelib.close(); return fail(`record not found in ${plugin}: ${idArg}`); }

            const fileNameOf = (r) => { try { return xelib.name(xelib.getElementFile(r)); } catch (_) { return undefined; } };
            const winFlag = (r) => { try { return xelib.isWinningOverride(r); } catch (_) { return undefined; } };
            let master = rec;
            try { if (xelib.isOverride(rec)) master = xelib.getMasterRecord(rec); } catch (_) {}
            const chain = [{ plugin: fileNameOf(master), formID: hex8(xelib.getFormID(master)), role: 'master', winning: winFlag(master) }];
            let overrides = [];
            try { overrides = xelib.getOverrides(master); } catch (_) {}
            for (const o of overrides) chain.push({ plugin: fileNameOf(o), formID: hex8(xelib.getFormID(o)), role: 'override', winning: winFlag(o) });
            let winner;
            try { winner = fileNameOf(xelib.getWinningOverride(master)); } catch (_) {}

            const out = {
                action: 'overrides', plugin,
                record: { formID: hex8(xelib.getFormID(rec)), signature: xelib.signature(rec), editorID: safeVal(rec, 'EDID') || undefined, name: safeVal(rec, 'FULL') || undefined },
                winner, overrideCount: overrides.length, conflicted: overrides.length > 1, chain,
            };
            xelib.release(file); xelib.close();
            return emit(out);
        }

        case 'plugin-conflicts': {
            // For each record THIS plugin overrides, does it win or lose (overridden by a
            // later plugin)? READ-ONLY. Needs the full load order.
            const plugin = positionals[0];
            if (!plugin) return fail('usage: esp plugin-conflicts <plugin> [--game-dir <dir>] [--load-order <file>] [--limit N]');
            const limit = flags.limit ? Math.max(1, parseInt(flags.limit, 10)) : 500;
            const effGame = flags['game-dir'] ? String(flags['game-dir']).replace(/[\\/]+$/, '') + '\\' : gamePath;
            setup(effGame);
            try {
                if (flags['load-order']) xelib.loadPlugins(fs.readFileSync(String(flags['load-order']), 'utf8').replace(/\r/g, '').trim(), false, false);
                else xelib.loadPlugins(plugin, true, false);
                await xelib.waitForLoader();
            } catch (e) { xelib.close(); return fail(`could not load order: ${e.message}`); }
            const file = xelib.fileByName(plugin);
            if (!file) { xelib.close(); return fail(`plugin not found in load order: ${plugin}`); }

            const fileNameOf = (r) => { try { return xelib.name(xelib.getElementFile(r)); } catch (_) { return undefined; } };
            const recs = xelib.getRecords(file, '', true);
            let total = 0, won = 0;
            const lostTo = [];
            for (const r of recs) {
                let isOv = false;
                try { isOv = xelib.isOverride(r); } catch (_) {}
                if (isOv) {
                    total++;
                    let win = true;
                    try { win = xelib.isWinningOverride(r); } catch (_) {}
                    if (win) won++;
                    else if (lostTo.length < limit) {
                        let winner; try { winner = fileNameOf(xelib.getWinningOverride(r)); } catch (_) {}
                        lostTo.push({ formID: hex8(xelib.getFormID(r)), signature: xelib.signature(r), editorID: safeVal(r, 'EDID') || undefined, winner });
                    }
                }
                xelib.release(r);
            }
            xelib.release(file); xelib.close();
            const lost = total - won;
            return emit({ action: 'plugin-conflicts', plugin, totalOverrides: total, won, lost, lostReturned: lostTo.length, lostTruncated: lost > lostTo.length, lostTo });
        }

        case 'conflict-summary': {
            // Order-wide overview: per-plugin record / override / new counts (cheap — uses counts,
            // not a full record scan). READ-ONLY. positionals[0] is a staging anchor only.
            const effGame = flags['game-dir'] ? String(flags['game-dir']).replace(/[\\/]+$/, '') + '\\' : gamePath;
            if (!flags['load-order']) return fail('conflict-summary requires --load-order (the full active order).');
            setup(effGame);
            try {
                xelib.loadPlugins(fs.readFileSync(String(flags['load-order']), 'utf8').replace(/\r/g, '').trim(), false, false);
                await xelib.waitForLoader();
            } catch (e) { xelib.close(); return fail(`could not load order: ${e.message}`); }
            const files = xelib.getElements(0);
            const plugins = [];
            for (const f of files) {
                let name, records = 0, overrides = 0;
                try { name = xelib.name(f); } catch (_) { name = undefined; }
                try { records = xelib.getRecordCount(f); } catch (_) {}
                try { overrides = xelib.getOverrideRecordCount(f); } catch (_) {}
                plugins.push({ plugin: name, records, overrides, newRecords: Math.max(0, records - overrides) });
                xelib.release(f);
            }
            xelib.close();
            plugins.sort((a, b) => b.overrides - a.overrides);
            return emit({ action: 'conflict-summary', pluginCount: plugins.length, plugins });
        }

        case 'patch': {
            // Compatibility patch: copy a record as an OVERRIDE into a new output plugin and
            // optionally edit fields. Two-pass: dry-run preview by default; --write to save.
            const outPlugin = positionals[0];
            const sourcePlugin = positionals[1];
            const idArg = positionals[2];
            if (!outPlugin || !sourcePlugin || !idArg) return fail('usage: esp patch <outPlugin.esp> <sourcePlugin> <FormID(hex)|EditorID> [--set PATH=VALUE ...] [--game-dir <dir>] [--write]');
            const write = !!flags.write;
            const effGame = flags['game-dir'] ? String(flags['game-dir']).replace(/[\\/]+$/, '') + '\\' : gamePath;
            setup(effGame);
            try { xelib.loadPlugins(sourcePlugin, true, false); await xelib.waitForLoader(); }
            catch (e) { xelib.close(); return fail(`could not load '${sourcePlugin}': ${e.message}`); }
            const srcFile = xelib.fileByName(sourcePlugin);
            if (!srcFile) { xelib.close(); return fail(`source plugin not found in data path: ${sourcePlugin}`); }

            const wantHex = idArg.toLowerCase().replace(/^0x/, '');
            const wantFid = /^[0-9a-f]{1,8}$/.test(wantHex) ? wantHex.padStart(8, '0') : null;
            const wantEdid = idArg.toLowerCase();
            const recs = xelib.getRecords(srcFile, '', true);
            let src = null;
            for (const r of recs) {
                if (src) { xelib.release(r); continue; }
                const fid = hex8(xelib.getFormID(r));
                const edid = safeVal(r, 'EDID');
                if ((wantFid && fid === wantFid) || (edid && edid.toLowerCase() === wantEdid)) src = r;
                else xelib.release(r);
            }
            if (!src) { xelib.release(srcFile); xelib.close(); return fail(`record not found in ${sourcePlugin}: ${idArg}`); }

            let out;
            try { out = xelib.addFile(outPlugin); }
            catch (e) { xelib.close(); return fail(`could not create output plugin '${outPlugin}': ${e.message}`); }
            xelib.addRequiredMasters(src, out);                 // ensure the override's masters are present
            const ov = xelib.copyElement(src, out, false);      // copy as OVERRIDE (keep FormID)

            const applied = [], failed = [];
            for (const s of asArray(flags.set)) {
                const eq = String(s).indexOf('=');
                if (eq < 0) { failed.push(`${s} (use PATH=VALUE)`); continue; }
                const p = String(s).slice(0, eq), v = String(s).slice(eq + 1);
                try { setField(ov, p, v); applied.push(`${p}=${v}`); }
                catch (e) { failed.push(`${p} (${e.message})`); }
            }

            const info = {
                action: 'patch', outPlugin, source: sourcePlugin,
                record: { formID: hex8(xelib.getFormID(ov)), signature: xelib.signature(ov), editorID: safeVal(ov, 'EDID') || undefined, name: safeVal(ov, 'FULL') || undefined },
                masters: xelib.getMasterNames(out), applied, failed,
            };
            if (!write) { xelib.close(); return emit({ ...info, dryRun: true, note: 'no file written — re-run with --write to create the patch' }); }
            xelib.saveFile(out);
            xelib.close();
            return emit({ ...info, written: true });
        }

        default:
            return fail(`esp: unknown command '${command}'. Commands: info, query, record, overrides, plugin-conflicts, conflict-summary, patch, create, add-record, add-misc, add-note, add-global, add-weapon, add-armor`);
    }
};

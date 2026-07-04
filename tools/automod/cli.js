#!/usr/bin/env node
// AutoMod CLI for Fallout: New Vegas — a single JSON-emitting interface over the
// toolbox's modding operations. Public tools only.
//
//   node tools/automod/cli.js <module> <command> [positionals...] [--key value | --flag] [--json] [--dry-run]
//
// Modules: esp (xeditlib) · mcm (JSON menus) · bsa (BSArch) · audio (oggenc2) · nif (self-built + nif_info) · lod (FNVLODGen/xLODGen orchestration) · fomod (installer XML) · crashlog (crash-log parsing) · funcs (NVSE function index) · ini (INI audit) · build (MSVC NVSE-plugin wrapper)
// Conventions: ALWAYS pass --json for parseable output; ALWAYS --dry-run first for writes.

const fs = require('fs');
const { fnvGamePath } = require('./lib/registry');
const { findTool } = require('./lib/tools');

const MODULES = ['esp', 'mcm', 'bsa', 'audio', 'nif', 'lod', 'fomod', 'crashlog', 'funcs', 'ini', 'build'];

function parse(argv) {
    const [module, command, ...rest] = argv;
    const positionals = [];
    const flags = {};
    for (let i = 0; i < rest.length; i++) {
        const t = rest[i];
        if (t.startsWith('--')) {
            const key = t.slice(2);
            const next = rest[i + 1];
            const val = (next === undefined || next.startsWith('--')) ? true : (i++, next);
            if (key in flags) { // repeated flag → collect into array (e.g. multiple --set)
                if (!Array.isArray(flags[key])) flags[key] = [flags[key]];
                flags[key].push(val);
            } else { flags[key] = val; }
        } else { positionals.push(t); }
    }
    return { module, command, positionals, flags };
}

function printHuman(o) {
    if (o.ok === false) { console.error('ERROR:', o.error); return; }
    for (const [k, v] of Object.entries(o)) {
        if (k === 'ok') continue;
        const val = (v && typeof v === 'object') ? JSON.stringify(v) : v;
        console.log(`${k}: ${val}`);
    }
}

(async () => {
    const { module, command, positionals, flags } = parse(process.argv.slice(2));
    const json = !!flags.json;
    const dryRun = !!flags['dry-run'];

    // --out <file>: also write the JSON result to a file. Lets callers that launch us
    // THROUGH MO2 (IOrganizer.startApplication, which doesn't expose stdout) capture output.
    const writeOut = (obj) => {
        if (flags.out) { try { fs.writeFileSync(String(flags.out), JSON.stringify(obj, null, 2)); } catch (_) { /* best effort */ } }
    };
    const emit = (r) => {
        const out = { ok: true, ...r };
        writeOut(out);
        if (json) process.stdout.write(JSON.stringify(out, null, 2) + '\n');
        else printHuman(out);
    };
    const fail = (msg, extra = {}) => {
        const out = { ok: false, error: msg, ...extra };
        writeOut(out);
        if (json) process.stdout.write(JSON.stringify(out, null, 2) + '\n');
        else console.error('ERROR:', msg);
        process.exit(1);
    };

    if (!module || module === 'help' || flags.help) {
        return emit({ usage: 'automod <module> <command> [...] --json [--dry-run]', modules: MODULES });
    }
    if (!MODULES.includes(module)) return fail(`Unknown module '${module}'. Modules: ${MODULES.join(', ')}`);

    let mod;
    try { mod = require('./modules/' + module); }
    catch (e) { return fail(`Module '${module}' failed to load: ${e.message}`); }

    const ctx = { command, positionals, flags, json, dryRun, gamePath: fnvGamePath(), findTool, emit, fail };
    try { await mod.run(command, ctx); }
    catch (e) { fail(e.message); }
})();

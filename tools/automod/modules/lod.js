// lod module — orchestrate FNV LOD generation (Sheson FNVLODGen/xLODGen + the LODGen worker).
// Generation itself is the external GUI tool; this module does the automatable parts:
//   tools (detect), check-assets (prereqs), verify-output (what was produced), generate (launch-helper).
const fs = require('fs');
const path = require('path');

function dataDir(ctx) {
    if (ctx.flags.data) return String(ctx.flags.data).replace(/[\\/]?$/, '\\');
    if (!ctx.gamePath) ctx.fail('FNV game path not found in registry; pass --data "<Data folder>".');
    return ctx.gamePath + 'Data\\';
}
const exists = (p) => { try { return fs.existsSync(p); } catch (_) { return false; } };
const listDirs = (p) => { try { return fs.readdirSync(p, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name); } catch (_) { return []; } };
function countFiles(dir, re) {
    let n = 0; const stack = [dir];
    while (stack.length) {
        const d = stack.pop(); let ents;
        try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch (_) { continue; }
        for (const e of ents) { const fp = path.join(d, e.name); if (e.isDirectory()) stack.push(fp); else if (re.test(e.name)) n++; }
    }
    return n;
}

exports.run = async (command, ctx) => {
    const { flags, emit, fail, gamePath } = ctx;
    const root = gamePath ? gamePath.replace(/\\$/, '') : null;
    const atRoot = (rel) => (root && exists(path.join(root, rel))) ? path.join(root, rel) : null;

    switch (command) {
        case 'tools': {
            const worker = atRoot('Edit Scripts\\LODGenx64.exe') || atRoot('Edit Scripts\\LODGen.exe') || ctx.findTool(['LODGenx64.exe', 'LODGen.exe']);
            const fnvedit = atRoot('FNVEdit.exe') || atRoot('FNVEdit64.exe') || atRoot('Optional\\FNVEdit64.exe');
            const xlodgen = ctx.findTool(['xLODGenx64.exe', 'xLODGen.exe', 'FNVLODGenx64.exe', 'FNVLODGen.exe']);
            return emit({ action: 'tools', worker, fnvedit, xlodgen, ready: !!(worker && (fnvedit || xlodgen)) });
        }

        case 'check-assets': {
            const dd = dataDir(ctx);
            const meshes = dd + 'Meshes';
            return emit({
                action: 'check-assets', dataDir: dd,
                looseObjectLodMeshes: exists(meshes) ? countFiles(meshes, /_lod\.nif$/i) : 0,
                treeBillboardTextures: exists(dd + 'Textures\\Landscape\\Trees') ? countFiles(dd + 'Textures\\Landscape\\Trees', /\.dds$/i) : 0,
                note: 'Counts LOOSE LOD source assets only (vanilla LOD lives in BSAs). On a heavily-modded setup, low object-LOD counts can mean missing LOD resource mods (e.g. Much Needed LOD / TCM\'s LOD). The definitive prerequisite check is the LODGen tool\'s own log.',
            });
        }

        case 'verify-output': {
            const dd = dataDir(ctx);
            const lodMesh = dd + 'Meshes\\Landscape\\LOD';
            const lodTex = dd + 'Textures\\Landscape\\LOD';
            if (!exists(lodMesh)) {
                return emit({ action: 'verify-output', dataDir: dd, worldspaces: [], note: 'No loose LOD output at Meshes\\Landscape\\LOD — not generated yet, or packed into a BSA.' });
            }
            let wss = listDirs(lodMesh);
            if (flags.worldspace) wss = wss.filter(w => w.toLowerCase() === String(flags.worldspace).toLowerCase());
            const worldspaces = wss.map(w => {
                const wdir = path.join(lodMesh, w);
                return {
                    worldspace: w,
                    objectLodBlocks: exists(path.join(wdir, 'Blocks')) ? countFiles(path.join(wdir, 'Blocks'), /\.nif$/i) : 0,
                    treeLodDtl: exists(path.join(wdir, 'Trees')) ? countFiles(path.join(wdir, 'Trees'), /\.dtl$/i) : 0,
                    hasTreeTypes: exists(path.join(wdir, 'Trees', 'TreeTypes.lst')),
                    lodTextures: exists(path.join(lodTex, w)) ? countFiles(path.join(lodTex, w), /\.dds$/i) : 0,
                };
            });
            return emit({ action: 'verify-output', dataDir: dd, count: worldspaces.length, worldspaces });
        }

        case 'generate': {
            // Launch-helper only — generation is interactive (worldspace/settings GUI) and must run
            // THROUGH MO2 to see the modded order. We detect tools and emit the command; we do not spawn it.
            const fnvedit = atRoot('FNVEdit.exe') || atRoot('FNVEdit64.exe');
            const worker = atRoot('Edit Scripts\\LODGenx64.exe') || atRoot('Edit Scripts\\LODGen.exe');
            const xlodgen = ctx.findTool(['xLODGenx64.exe', 'xLODGen.exe']);
            const frontend = xlodgen || fnvedit;
            if (!frontend) return fail('No LOD front-end found (xLODGen or FNVEdit). Install xLODGen, or ensure FNVEdit.exe is in the game folder.');
            if (!worker && !xlodgen) return fail('LODGen worker (Edit Scripts\\LODGenx64.exe) not found — it ships with FNVEdit/xEdit.');
            const out = flags.output ? String(flags.output) : '<output_folder>';
            return emit({
                action: 'generate', launchHelper: true, frontend, worker,
                recommendedArgs: `-fnv -o:"${out}"`,
                howToRun: 'Run the front-end THROUGH Mod Organizer 2 (add it as an MO2 executable) so the modded load order/VFS is active. In the LODGen window pick worldspace(s) + settings, then Generate. See the fnv-lod skill.',
                note: 'Generation is interactive (GUI settings) and asset-dependent; this command does not auto-run it. After generating, use "lod verify-output".',
            });
        }

        default:
            return fail(`lod: unknown command '${command}'. Commands: tools, check-assets, verify-output, generate`);
    }
};

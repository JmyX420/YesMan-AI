// ini module — audit FNV game INIs for known-harmful / placebo / dangerous tweaks.
// READ-ONLY: it never edits an INI. The real, tested knobs live in nvse_stewie_tweaks.ini / NVTF,
// NOT the game INIs. Commands: audit
const fs = require('fs');
const path = require('path');

const RULES = [
    { key: 'bUseMultiThreadedFaceGen', test: v => v === '1', severity: 'HARMFUL (vanilla default)', advice: 'Recommended value 0 — at 1 it causes NPC face discoloration.' },
    { key: 'bMultiThreadAudio', test: v => v === '1', severity: 'HARMFUL', advice: 'Causes a freeze on exit to Windows. Set to 0 / remove.' },
    { key: 'bUseThreadedAI', test: v => v === '1', severity: 'PLACEBO', advice: 'No proven effect (myth). Harmless but pointless — rely on NVTF for threading.' },
    { key: 'iNumHWThreads', test: () => true, severity: 'DISPUTED', advice: 'Disputed; sometimes cited for FO3/TTW freezing but considered placebo on FNV (NVTF supersedes). Remove unless you have a specific tested reason.' },
    { key: 'uGridsToLoad', test: v => Number(v) > 5, severity: 'DANGEROUS', advice: '>5 strains the engine AND saving then reverting permanently corrupts the save. Keep at 5 (7 max only with uGridsToLoad SaveGuard).' },
    { key: 'bUseMultiThreadedTrees', test: v => v === '1', severity: 'CAUTION', advice: 'Can cause tree-rendering glitches/crashes on some setups; default 0 is safest.' },
];

function parseIni(text) {
    const out = {};
    for (const raw of text.split(/\r?\n/)) {
        const line = raw.replace(/;.*$/, '').trim();
        const m = line.match(/^([A-Za-z0-9_ ]+?)\s*=\s*(.+?)\s*$/);
        if (m) out[m[1].toLowerCase()] = m[2];
    }
    return out;
}

function audit(file) {
    const kv = parseIni(fs.readFileSync(file, 'utf8'));
    const findings = [];
    for (const r of RULES) {
        const v = kv[r.key.toLowerCase()];
        if (v !== undefined && r.test(v)) findings.push({ setting: `${r.key}=${v}`, severity: r.severity, advice: r.advice });
    }
    return findings;
}

exports.run = async (command, ctx) => {
    const { positionals, flags, emit, fail } = ctx;

    switch (command) {
        case 'audit': {
            let files = [];
            if (positionals[0]) {
                files = [positionals[0]];
            } else {
                const docs = flags.docs ? String(flags.docs) : (process.env.USERPROFILE && path.join(process.env.USERPROFILE, 'Documents', 'My Games', 'FalloutNV'));
                if (!docs) return fail('usage: ini audit <Fallout.ini>  (or run where Documents\\My Games\\FalloutNV exists)');
                for (const f of ['Fallout.ini', 'FalloutPrefs.ini', 'FalloutCustom.ini']) {
                    const p = path.join(docs, f);
                    if (fs.existsSync(p)) files.push(p);
                }
                if (!files.length) return fail(`no FNV INIs found in ${docs}; pass a path: ini audit <file>`);
            }
            const results = files.map(f => fs.existsSync(f) ? { file: f, findings: audit(f) } : { file: f, error: 'not found' });
            const totalFindings = results.reduce((s, r) => s + ((r.findings || []).length), 0);
            return emit({
                action: 'audit', filesScanned: results.length, totalFindings, results,
                note: 'READ-ONLY. Flags known-harmful/placebo/dangerous game-INI tweaks. The real, tested knobs live in nvse_stewie_tweaks.ini / NVTF, not the game INIs. No findings ≠ "optimal" — just no known-bad tweak detected. Under MO2, INIs may be profile-specific (in the active profile folder).',
            });
        }

        default:
            return fail(`ini: unknown command '${command}'. Commands: audit`);
    }
};

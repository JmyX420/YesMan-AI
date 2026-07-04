// mcm module — generate the verified FNV MCM JSON (Tweaks/MenuConfig schema).
// Commands: create, add-toggle, add-slider, add-dropdown, validate
const fs = require('fs');

function load(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function save(file, data) { fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n'); }

exports.run = async (command, ctx) => {
    const { positionals, flags, emit, fail, dryRun } = ctx;
    const file = positionals[0];

    switch (command) {
        case 'create': {
            if (!file) return fail('usage: mcm create <file.json> --name <label> --internal <bName> [--category C] [--desc D]');
            const group = {
                name: flags.name || 'New Setting',
                internalName: flags.internal || 'bNewSetting',
                description: flags.desc || '',
                category: flags.category || 'General',
                subsettings: [],
            };
            const data = [group];
            if (dryRun) return emit({ action: 'create', file, dryRun: true, wouldWrite: data });
            save(file, data);
            return emit({ action: 'create', file, groups: 1, group });
        }

        case 'add-toggle':
        case 'add-slider':
        case 'add-dropdown': {
            if (!file) return fail(`usage: mcm ${command} <file.json> --name <label> --internal <name> [--category C] [--desc D] ...`);
            if (!flags.internal || !flags.name) return fail('--name and --internal are required');
            const data = load(file);
            if (!data.length) return fail('no setting group in file — run "mcm create" first');
            const group = data[data.length - 1]; // append to the last group
            const sub = {
                name: flags.name,
                internalName: flags.internal,
                internalCategory: flags.category || group.name,
                description: flags.desc || '',
            };
            if (command === 'add-slider') {
                sub.type = 'slider';
                sub.minValue = Number(flags.min ?? 0);
                sub.maxValue = Number(flags.max ?? 100);
            } else if (command === 'add-dropdown') {
                try { sub.options = JSON.parse(flags.options || '[]'); }
                catch (e) { return fail('--options must be JSON like \'[{"name":"Off","value":0}]\''); }
            } // toggle: no type field
            group.subsettings.push(sub);
            if (dryRun) return emit({ action: command, file, dryRun: true, wouldAdd: sub });
            save(file, data);
            return emit({ action: command, file, added: sub });
        }

        case 'validate': {
            if (!file) return fail('usage: mcm validate <file.json>');
            const data = load(file);
            const errors = [];
            if (!Array.isArray(data)) errors.push('root must be a JSON array of setting groups');
            else data.forEach((g, i) => {
                if (!g.internalName) errors.push(`group[${i}] missing internalName`);
                if (g.internalName && !/^[bifs]/.test(g.internalName)) errors.push(`group[${i}].internalName "${g.internalName}" should start with a Hungarian prefix b/i/f/s`);
                (g.subsettings || []).forEach((s, j) => {
                    if (!s.internalName) errors.push(`group[${i}].subsettings[${j}] missing internalName`);
                    if (s.type && !['slider', 'input'].includes(s.type) && !s.options) errors.push(`group[${i}].subsettings[${j}] unknown type "${s.type}"`);
                });
            });
            return emit({ action: 'validate', file, valid: errors.length === 0, errors });
        }

        default:
            return fail(`mcm: unknown command '${command}'. Commands: create, add-toggle, add-slider, add-dropdown, validate`);
    }
};

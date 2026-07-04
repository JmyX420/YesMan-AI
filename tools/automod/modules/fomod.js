// fomod module — generate & validate FOMOD installers (the XML "Configured Installer").
// Only needed when a mod has INSTALL-TIME CHOICES (variants/optional files); most mods need none.
// Commands: init, validate, types
const fs = require('fs');
const path = require('path');

const GROUP_TYPES = ['SelectExactlyOne', 'SelectAtMostOne', 'SelectAtLeastOne', 'SelectAll', 'SelectAny'];
const PLUGIN_TYPES = ['Required', 'Optional', 'Recommended', 'NotUsable', 'CouldBeUsable'];

const esc = (s) => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function infoXml(f) {
    return `<?xml version="1.0" encoding="utf-8"?>
<fomod>
  <Name>${esc(f.name)}</Name>
  <Author>${esc(f.author)}</Author>
  <Version>${esc(f.version || '1.0')}</Version>
  <Description>${esc(f.desc)}</Description>
</fomod>
`;
}

function skeletonXml(name) {
    return `<?xml version="1.0" encoding="utf-8"?>
<config xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://qconsulting.ca/fo3/ModConfig5.0.xsd">
  <moduleName>${esc(name)}</moduleName>

  <!-- Files installed for EVERYONE regardless of choices (optional):
  <requiredInstallFiles>
    <folder source="core" destination="" priority="0"/>
  </requiredInstallFiles>
  -->

  <installSteps order="Explicit">
    <installStep name="Options">
      <optionalFileGroups order="Explicit">
        <group name="Choose a variant" type="SelectExactlyOne">
          <plugins order="Explicit">
            <plugin name="Default">
              <description>The default version.</description>
              <files>
                <folder source="options/default" destination="" priority="0"/>
              </files>
              <typeDescriptor><type name="Recommended"/></typeDescriptor>
            </plugin>
            <plugin name="Variant B">
              <description>An alternative version.</description>
              <files>
                <folder source="options/variantB" destination="" priority="0"/>
              </files>
              <typeDescriptor><type name="Optional"/></typeDescriptor>
            </plugin>
          </plugins>
        </group>
      </optionalFileGroups>
    </installStep>
  </installSteps>
</config>
`;
}

// Lightweight tag-balance check (not a full XSD validation).
function checkBalance(x) {
    const stack = []; const re = /<(\/?)([A-Za-z_][\w.-]*)\b[^>]*?(\/?)>/g; let m;
    while ((m = re.exec(x))) {
        const closing = m[1] === '/', name = m[2], self = m[3] === '/';
        if (self) continue;
        if (closing) { if (!stack.length || stack[stack.length - 1] !== name) return `tag balance error near </${name}>`; stack.pop(); }
        else stack.push(name);
    }
    return stack.length ? `unclosed tag(s): ${stack.join(', ')}` : null;
}

exports.run = async (command, ctx) => {
    const { positionals, flags, emit, fail, dryRun } = ctx;

    switch (command) {
        case 'init': {
            const dir = positionals[0];
            if (!dir || !flags.name) return fail('usage: fomod init <fomodDir> --name "Mod Name" [--author X] [--version 1.0] [--desc "..."] [--dry-run]');
            const info = path.join(dir, 'info.xml');
            const cfg = path.join(dir, 'ModuleConfig.xml');
            if (dryRun) return emit({ action: 'init', dir, dryRun: true, wouldWrite: ['fomod/info.xml', 'fomod/ModuleConfig.xml'] });
            fs.mkdirSync(dir, { recursive: true });
            fs.writeFileSync(info, infoXml({ name: flags.name, author: flags.author, version: flags.version, desc: flags.desc }));
            fs.writeFileSync(cfg, skeletonXml(flags.name));
            return emit({ action: 'init', wrote: [info, cfg], note: 'Skeleton has a SelectExactlyOne group with two options — edit groups/plugins and lay out the source folders (e.g. options/default).' });
        }

        case 'validate': {
            const file = positionals[0];
            if (!file) return fail('usage: fomod validate <ModuleConfig.xml> [--mod-root <dir>]');
            const xml = fs.readFileSync(file, 'utf8');
            const x = xml.replace(/<!--[\s\S]*?-->/g, '');
            const errors = [], warnings = [];
            if (!/<config[\s>]/.test(x)) errors.push('missing <config> root');
            if (!/<moduleName>/.test(x)) errors.push('missing <moduleName>');
            if (!/<installSteps[\s>]/.test(x) && !/<requiredInstallFiles[\s>]/.test(x)) warnings.push('no <installSteps> or <requiredInstallFiles> — the installer would do nothing');
            for (const m of x.matchAll(/<group\b([^>]*)>/g)) {
                const t = (m[1].match(/\btype="([^"]+)"/) || [])[1];
                if (!t) errors.push('a <group> is missing its type attribute');
                else if (!GROUP_TYPES.includes(t)) errors.push(`invalid group type "${t}" (valid: ${GROUP_TYPES.join(', ')})`);
            }
            for (const m of x.matchAll(/<type\b[^>]*\bname="([^"]+)"/g)) {
                if (!PLUGIN_TYPES.includes(m[1])) errors.push(`invalid plugin type "${m[1]}" (valid: ${PLUGIN_TYPES.join(', ')})`);
            }
            const bal = checkBalance(x); if (bal) errors.push(bal);
            // source paths exist (relative to mod root = parent of the fomod/ folder)
            const root = flags['mod-root'] ? path.resolve(String(flags['mod-root'])) : path.dirname(path.dirname(path.resolve(file)));
            const missing = new Set();
            for (const m of x.matchAll(/\bsource="([^"]+)"/g)) {
                if (!m[1]) continue;
                if (!fs.existsSync(path.join(root, m[1].replace(/\//g, path.sep)))) missing.add(m[1]);
            }
            if (missing.size) warnings.push(`source path(s) not found under mod root (${root}): ${[...missing].slice(0, 10).join(', ')}`);
            return emit({ action: 'validate', file, valid: errors.length === 0, errors, warnings });
        }

        case 'types':
            return emit({ action: 'types', groupTypes: GROUP_TYPES, pluginTypes: PLUGIN_TYPES, note: 'Group type controls selection; plugin type controls default state. Use dependencyType/patterns for conditional defaults, conditionFlags + conditionalFileInstalls for flag-driven installs.' });

        default:
            return fail(`fomod: unknown command '${command}'. Commands: init, validate, types`);
    }
};

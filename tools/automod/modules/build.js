// build module — wrap the user's installed MSVC to compile a native NVSE plugin (32-bit DLL).
// The toolbox does NOT bundle a compiler; this drives Visual Studio / Build Tools via the
// VALIDATED recipe (vswhere -> Enter-VsDevShell -arch=x86 -> MSBuild Win32/Release/MT -> dumpbin).
// Commands: detect (toolchain) · scaffold (starter project) · compile (build a .vcxproj) · verify (dumpbin).
// See the `nvse-plugin` skill for the judgement parts (SDK layout, hooks, opcode base) this can't automate.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const onWindows = process.platform === 'win32';
const exists = (p) => { try { return fs.existsSync(p); } catch (_) { return false; } };

// MSVC toolset version dir (e.g. "14.50.35717") -> PlatformToolset tag ("v145").
function toolsetTag(ver) {
    const m = /^(\d+)\.(\d)/.exec(ver || '');
    return m ? `v${m[1]}${m[2]}` : null;
}

function findVswhere() {
    const pf86 = process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)';
    const p = path.join(pf86, 'Microsoft Visual Studio', 'Installer', 'vswhere.exe');
    return exists(p) ? p : null;
}

// Resolve VS install path + the latest installed MSVC toolset that has the x86 compiler.
function detectToolchain(vsOverride) {
    const out = { vsPath: null, vswhere: findVswhere(), msvcVersion: null, toolset: null, clx86: null, dumpbin: null, devShellModule: null, x86: false, ready: false };

    let vsPath = vsOverride || null;
    if (!vsPath && out.vswhere) {
        const r = spawnSync(out.vswhere, ['-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], { encoding: 'utf8' });
        vsPath = (r.stdout || '').split(/\r?\n/)[0].trim() || null;
    }
    if (!vsPath || !exists(vsPath)) return out;
    out.vsPath = vsPath;

    const dsm = path.join(vsPath, 'Common7', 'Tools', 'Microsoft.VisualStudio.DevShell.dll');
    out.devShellModule = exists(dsm) ? dsm : null;

    const msvcRoot = path.join(vsPath, 'VC', 'Tools', 'MSVC');
    let versions = [];
    try { versions = fs.readdirSync(msvcRoot).filter(v => /^\d+\.\d+\.\d+/.test(v)).sort(); } catch (_) { /* none */ }
    const ver = versions[versions.length - 1];
    if (ver) {
        out.msvcVersion = ver;
        out.toolset = toolsetTag(ver);
        for (const host of ['Hostx64', 'Hostx86']) {
            const cl = path.join(msvcRoot, ver, 'bin', host, 'x86', 'cl.exe');
            if (exists(cl)) { out.clx86 = cl; out.dumpbin = path.join(msvcRoot, ver, 'bin', host, 'x86', 'dumpbin.exe'); break; }
        }
    }
    out.x86 = !!out.clx86;
    out.ready = !!(out.vsPath && out.devShellModule && out.toolset && out.x86);
    return out;
}

// PowerShell preamble that enters an x86 VS dev environment (the reliable path; cmd /c quoting is fragile).
function devShellPreamble(vsPath) {
    return `Import-Module "${vsPath}\\Common7\\Tools\\Microsoft.VisualStudio.DevShell.dll";`
        + ` Enter-VsDevShell -VsInstallPath "${vsPath}" -DevCmdArguments '-arch=x86' -SkipAutomaticLocation | Out-Null;`;
}

function runPwsh(script) {
    const r = spawnSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
        { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
    return { code: r.status, stdout: r.stdout || '', stderr: r.stderr || '', err: r.error ? r.error.message : null };
}

function tail(s, n = 40) { const L = s.split(/\r?\n/).filter(Boolean); return L.slice(-n).join('\n'); }

// Stable pseudo-GUID from a string (so re-scaffolding is deterministic; MSBuild only needs *a* GUID).
function guidFrom(name) {
    let h = 0x811c9dc5; const bytes = [];
    const s = 'nvse-plugin:' + name;
    for (let i = 0; i < 32; i++) { h ^= (s.charCodeAt(i % s.length) + i * 131); h = (h * 0x01000193) >>> 0; bytes.push((h >>> (i % 4 * 8)) & 0xff); }
    const hx = bytes.map(b => b.toString(16).padStart(2, '0'));
    return `${hx.slice(0, 4).join('')}-${hx.slice(4, 6).join('')}-${hx.slice(6, 8).join('')}-${hx.slice(8, 10).join('')}-${hx.slice(10, 16).join('')}`.toUpperCase();
}

function scaffoldFiles(name, sdk, toolset) {
    const main = `#include "nvse/PluginAPI.h"
#include "nvse/CommandTable.h"
#include "nvse/GameAPI.h"

IDebugLog gLog("${name}.log");
NVSEInterface* g_nvse = nullptr;

extern "C" {

__declspec(dllexport) bool NVSEPlugin_Query(const NVSEInterface* nvse, PluginInfo* info)
{
    info->infoVersion = PluginInfo::kInfoVersion;
    info->name = "${name}";
    info->version = 1;
    if (nvse->isEditor) return true;                       // load in GECK for command registration
    if (nvse->runtimeVersion < RUNTIME_VERSION_1_4_0_525)  // FNV 1.4.0.525
        return false;
    return true;
}

__declspec(dllexport) bool NVSEPlugin_Load(NVSEInterface* nvse)
{
    g_nvse = nvse;
    if (!nvse->isEditor) {
        // Request an assigned opcode base from the NVSE team for a real plugin:
        //   nvse->SetOpcodeBase(0x????);
        //   nvse->RegisterCommand(&kCommandInfo_YourCommand);
    }
    return true;
}

}; // extern "C"
`;
    const def = `LIBRARY "${name}"\nEXPORTS\n  NVSEPlugin_Query\n  NVSEPlugin_Load\n`;
    const sdkInc = (sdk || '<path-to-nvse-sdk>').replace(/[\\/]+$/, '');
    const vcxproj = `<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup Label="ProjectConfigurations">
    <ProjectConfiguration Include="Release|Win32">
      <Configuration>Release</Configuration>
      <Platform>Win32</Platform>
    </ProjectConfiguration>
  </ItemGroup>
  <PropertyGroup Label="Globals">
    <ProjectGuid>{${guidFrom(name)}}</ProjectGuid>
    <RootNamespace>${name}</RootNamespace>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'" Label="Configuration">
    <ConfigurationType>DynamicLibrary</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>${toolset || 'v143'}</PlatformToolset>
    <CharacterSet>MultiByte</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props" />
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">
    <ClCompile>
      <WarningLevel>Level3</WarningLevel>
      <Optimization>MaxSpeed</Optimization>
      <RuntimeLibrary>MultiThreaded</RuntimeLibrary>
      <ExceptionHandling>Sync</ExceptionHandling>
      <LanguageStandard>stdcpp17</LanguageStandard>
      <AdditionalIncludeDirectories>${sdkInc};%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
    </ClCompile>
    <Link>
      <ModuleDefinitionFile>exports.def</ModuleDefinitionFile>
      <SubSystem>Windows</SubSystem>
    </Link>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClCompile Include="main.cpp" />
    <None Include="exports.def" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets" />
</Project>
`;
    return { [`main.cpp`]: main, [`exports.def`]: def, [`${name}.vcxproj`]: vcxproj };
}

exports.run = async (command, ctx) => {
    const { flags, emit, fail, dryRun } = ctx;

    if (!onWindows && command !== 'scaffold') {
        return fail('build: native NVSE-plugin compilation requires Windows + MSVC. (scaffold works anywhere.)');
    }

    switch (command) {
        case 'detect': {
            const tc = detectToolchain(flags.vs ? String(flags.vs) : null);
            return emit({
                action: 'detect', ...tc,
                advice: tc.ready
                    ? `Ready. Use: automod build compile <project.vcxproj> --json   (auto: PlatformToolset=${tc.toolset}, x86/Release/MT)`
                    : (!tc.vswhere ? 'vswhere.exe not found — install Visual Studio or Build Tools.'
                        : !tc.vsPath ? 'No VS install with the C++ x86 toolset. Install "Desktop development with C++" (incl. the x86 toolset + a Windows SDK).'
                            : !tc.x86 ? 'VS found but the x86 (32-bit) compiler is missing — add the C++ x86/x64 build tools component. FNV is 32-bit; the plugin MUST be Win32.'
                                : 'VS dev-shell module missing; cannot enter the build environment.'),
            });
        }

        case 'scaffold': {
            const name = flags.name ? String(flags.name) : null;
            if (!name) return fail('usage: build scaffold <outDir> --name <PluginName> [--sdk <nvse-sdk-dir>] [--dry-run]');
            const outDir = ctx.positionals[0] ? String(ctx.positionals[0]) : `./${name}`;
            const tc = onWindows ? detectToolchain(flags.vs ? String(flags.vs) : null) : { toolset: null };
            const files = scaffoldFiles(name, flags.sdk ? String(flags.sdk) : null, tc.toolset);
            const planned = Object.keys(files).map(f => path.join(outDir, f));
            if (dryRun || !onWindows && flags['dry-run'] === undefined && false) { /* fallthrough */ }
            if (dryRun) {
                return emit({ action: 'scaffold', dryRun: true, outDir, files: planned, toolset: tc.toolset || 'v143 (default — run detect on Windows)', note: 'Dry run — nothing written. Re-run without --dry-run to create these. main.cpp/exports.def/.vcxproj target Win32/Release/MT. Open in VS or build with `build compile`.', sdkNote: flags.sdk ? undefined : 'No --sdk given: AdditionalIncludeDirectories left as <path-to-nvse-sdk> — set it to the dir CONTAINING nvse/ (from the xNVSE source).' });
            }
            try {
                fs.mkdirSync(outDir, { recursive: true });
                for (const [fn, content] of Object.entries(files)) fs.writeFileSync(path.join(outDir, fn), content);
            } catch (e) { return fail(`scaffold: write failed: ${e.message}`); }
            return emit({ action: 'scaffold', outDir, files: planned, toolset: tc.toolset || 'v143', next: `automod build compile "${path.join(outDir, name + '.vcxproj')}" --json`, warning: 'Starter only — a real plugin needs the NVSE SDK include path (--sdk), command registration, and an assigned opcode base. See the nvse-plugin skill.' });
        }

        case 'compile': {
            const proj = ctx.positionals[0] ? String(ctx.positionals[0]) : null;
            if (!proj) return fail('usage: build compile <project.vcxproj> [--vs <VS path>] [--toolset vXXX] [--dry-run]');
            if (!exists(proj)) return fail(`compile: project not found: ${proj}`);
            const tc = detectToolchain(flags.vs ? String(flags.vs) : null);
            if (!tc.ready && !flags.vs) return fail('compile: no usable MSVC x86 toolchain. Run `build detect` for details.', { detect: tc });
            const toolset = flags.toolset ? String(flags.toolset) : tc.toolset;
            const projAbs = path.resolve(proj);
            const projDir = path.dirname(projAbs);
            const msbuild = `msbuild "${projAbs}" /t:Rebuild /p:Configuration=Release /p:Platform=Win32 /p:PlatformToolset=${toolset} /m`;
            const script = `${devShellPreamble(tc.vsPath)} Set-Location "${projDir}"; ${msbuild}`;
            if (dryRun) {
                return emit({ action: 'compile', dryRun: true, project: projAbs, toolset, vsPath: tc.vsPath, command: script, note: 'Dry run — not executed. This is the exact PowerShell pipeline (x86 dev shell + MSBuild Win32/Release). Re-run without --dry-run to build.' });
            }
            const res = runPwsh(script);
            // locate the produced DLL
            const candidates = ['Release', path.join('bin', 'Win32', 'Release'), path.join('Win32', 'Release'), '.'];
            let dll = null;
            for (const c of candidates) {
                const d = path.join(projDir, c);
                if (!exists(d)) continue;
                const hit = fs.readdirSync(d).filter(f => /\.dll$/i.test(f));
                if (hit.length) { dll = path.join(d, hit[0]); break; }
            }
            const ok = res.code === 0 && !!dll;
            return emit({
                action: 'compile', success: ok, project: projAbs, toolset, dll,
                exitCode: res.code, outputTail: tail(res.stdout + '\n' + res.stderr),
                hint: ok ? `Verify it: automod build verify "${dll}" --json` :
                    'Build failed. Common fixes (see nvse-plugin skill): retarget PlatformToolset (--toolset), align CRT (/MT vs /MD across projects), set the NVSE SDK include path. A post-build copy error (MSB3073) is harmless if the DLL exists in Release\\.',
            });
        }

        case 'verify': {
            const dll = ctx.positionals[0] ? String(ctx.positionals[0]) : null;
            if (!dll) return fail('usage: build verify <plugin.dll> [--vs <VS path>]');
            if (!exists(dll)) return fail(`verify: file not found: ${dll}`);
            const tc = detectToolchain(flags.vs ? String(flags.vs) : null);
            if (!tc.vsPath) return fail('verify: need VS for dumpbin. Run `build detect` or pass --vs <path>.');
            const dllAbs = path.resolve(dll);
            const script = `${devShellPreamble(tc.vsPath)} dumpbin /exports "${dllAbs}"; Write-Output '----HEADERS----'; dumpbin /headers "${dllAbs}"`;
            if (dryRun) return emit({ action: 'verify', dryRun: true, dll: dllAbs, command: script });
            const res = runPwsh(script);
            const o = res.stdout || '';
            const hasQuery = /NVSEPlugin_Query/.test(o);
            const hasLoad = /NVSEPlugin_Load/.test(o);
            const isX86 = /14C\s+machine\s+\(x86\)/i.test(o);
            const valid = hasQuery && hasLoad && isX86;
            return emit({
                action: 'verify', dll: dllAbs, valid,
                exportsNVSEPluginQuery: hasQuery, exportsNVSEPluginLoad: hasLoad, machineX86: isX86,
                verdict: valid ? 'Valid NVSE plugin: exports both entry points and is 32-bit (x86).'
                    : `NOT a valid FNV NVSE plugin — ${[!hasQuery && 'missing NVSEPlugin_Query', !hasLoad && 'missing NVSEPlugin_Load', !isX86 && 'not x86 (FNV is 32-bit)'].filter(Boolean).join('; ')}.`,
            });
        }

        default:
            return fail(`build: unknown command '${command}'. Commands: detect, scaffold, compile, verify`);
    }
};

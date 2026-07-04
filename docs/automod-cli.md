# AutoMod CLI (Fallout: New Vegas)

A single JSON-emitting command-line interface over the toolbox's modding operations, so Claude (and you) can do common tasks with one command instead of a custom script each time. **Public tools only** — no private/custom dependencies.

```bash
bash tools/automod-cli.sh <module> <command> [args] --json [--dry-run]
#   or: node tools/automod/cli.js <module> <command> ...
```

**Conventions**
- **Always pass `--json`** for parseable output.
- **Always `--dry-run` first** for any write (esp/mcm writes, nif edits). Review, then re-run to commit (`esp`/`mcm` use `--write`; `nif`/`bsa`/`audio` commit when `--dry-run` is omitted).

**Tool auto-detection.** External tools are located automatically in: the FNV game folder (and `Optional\`/`tools\`), then the system PATH. If a tool is missing, the command returns a clear `error` telling you what to install.

| Tool | Used by | Where it's expected |
|------|---------|---------------------|
| `xeditlib` (npm, bundled DLL) | `esp` | `node_modules/` (run `npm install`) |
| `BSArch.exe` | `bsa` | game folder / xEdit install / PATH |
| `oggenc2.exe` | `audio` | game folder / PATH |
| `nif_info.exe` (optional, fo76utils) | `nif inspect` | game folder / PATH |
| GECK | `audio` `.lip` (manual) | — |
| MSVC (VS / Build Tools) + `vswhere` | `build` | auto-detected via `vswhere`; **not bundled** — you install it |

---

## `esp` — plugins & records (via xEditLib, `GM_FNV=0`)
```bash
automod-cli.sh esp info <plugin.esp> --json
automod-cli.sh esp create <NewMod.esp> [--master FalloutNV.esm] --write --json
automod-cli.sh esp add-misc <plugin> <EditorID> --name "Name" [--value N] [--weight N] [--write] --json
automod-cli.sh esp add-note <plugin> <EditorID> --name "Name" [--write] --json
automod-cli.sh esp add-global <plugin> <EditorID> [--type s|l|f] [--value N] [--write] --json
automod-cli.sh esp add-weapon <plugin> <EditorID> --name "Name" [--value N] [--health N] [--weight N] [--write] --json
automod-cli.sh esp add-armor  <plugin> <EditorID> --name "Name" [--value N] [--health N] [--weight N] [--write] --json
# generic — set any xEdit field path(s):
automod-cli.sh esp add-record <plugin> WEAP <EditorID> --full "Name" --set "DATA\Value=100" --set "DATA\Weight=2" [--write] --json
```
Without `--write` it previews (dry-run) and writes nothing. Records are created with the fields you specify; refine detailed combat stats with `--set` or in the GECK.

**Read-only record inspection** (also powers the MO2 MCP's record tools):
```bash
automod-cli.sh esp query <plugin> [--sig WEAP] [--match <substr>] [--limit N] --json   # list records a plugin defines/overrides
automod-cli.sh esp record <plugin> <FormID-hex | EditorID> --json                       # full field tree of one record
```
`query` returns FormID/signature/EditorID/name per record; `record` returns the resolved xEdit element tree (named subrecords + resolved FormID references). Both load the plugin + its masters from the (virtual) Data dir.

## `mcm` — Mod Configuration Menu JSON (verified Tweaks/MenuConfig schema)
```bash
automod-cli.sh mcm create <file.json> --name "Enable Mod" --internal bEnableMod --category "My Mod" --desc "..." --json
automod-cli.sh mcm add-toggle  <file.json> --name "Verbose" --internal bVerbose --json
automod-cli.sh mcm add-slider  <file.json> --name "Volume" --internal iVolume --min 0 --max 100 --json
automod-cli.sh mcm add-dropdown <file.json> --name "Mode" --internal iMode --options '[{"name":"Off","value":0},{"name":"On","value":1}]' --json
automod-cli.sh mcm validate <file.json> --json
```
Output goes to `Data\NVSE\Plugins\Tweaks\MenuConfig\<Mod>.json` (read by lStewieAl's Tweaks / MCM Extender). Hungarian prefix on `internalName` sets the type (`b`/`i`/`f`/`s`).

## `bsa` — archives (via BSArch `-fnv`)
```bash
automod-cli.sh bsa list <archive.bsa> [--filter <substr>] [--limit N] --json
automod-cli.sh bsa unpack <archive.bsa> <folder> [--dry-run] --json
automod-cli.sh bsa pack <source_dir> <archive.bsa> [--compress] [--dry-run] --json
automod-cli.sh bsa extract-file <archive.bsa> <internal/path.ext> <out_dir> [--dry-run] --json
```

## `audio` — voice/sound (via oggenc2)
```bash
automod-cli.sh audio wav-to-ogg <in.wav> <out.ogg> [--quality N] [--rate 24000] [--stereo] [--dry-run] --json
automod-cli.sh audio info <file.ogg|.wav> --json
```
Defaults to FNV voice spec: **24 kHz, mono, ~64 kbps VBR**. `.lip` files are **GECK-only** (FonixData) — `audio lip` explains the GECK steps.

## `nif` — meshes (self-built reader + safe edits; NifSkope for the rest)
```bash
automod-cli.sh nif info <file.nif> --json            # version (20.2.0.7), block types, texture count
automod-cli.sh nif list-textures <file.nif> --json
automod-cli.sh nif replace-textures <file.nif> --old <path> --new <path> [--dry-run] --json   # SAME-LENGTH only (byte-safe; auto .bak)
automod-cli.sh nif inspect <file.nif> --json         # optional fo76utils nif_info (OBJ/render/full dump)
```
**Different-length texture edits, node renames, geometry/collision → NifSkope** (changing string lengths would desync NIF block sizes). `replace-textures` makes a `.bak` before writing.

---

## `lod` — LOD generation (orchestrates FNVLODGen/xLODGen)
```bash
automod-cli.sh lod tools --json                          # detect LODGen worker / FNVEdit / xLODGen
automod-cli.sh lod check-assets [--data <Data>] --json   # loose LOD source-asset presence (prereq sanity)
automod-cli.sh lod verify-output [--worldspace W] --json # per-worldspace generated-LOD counts (Blocks/Trees/textures)
automod-cli.sh lod generate [--output <dir>] --json      # launch-helper: detects tools, emits the -fnv -o: command (run via MO2)
```
Generation itself is the external (mostly GUI) Sheson tool — this module detects it, helps launch it, checks prerequisites, and verifies output. See the `fnv-lod` skill. Package results with `bsa pack`.

## `fomod` — FOMOD installer XML (only for mods with install choices)
```bash
automod-cli.sh fomod init <fomodDir> --name "Mod" --author X --version 1.0 [--desc "…"] --json   # info.xml + ModuleConfig.xml skeleton
automod-cli.sh fomod validate <ModuleConfig.xml> [--mod-root <dir>] --json   # well-formedness + group/plugin type enums + source-path existence
automod-cli.sh fomod types --json                                            # valid group/plugin type enums
```
Most mods need **no** FOMOD — only those offering install-time choices (variants/optional files). See the `fnv-fomod` skill.

## `crashlog` — crash-log parsing
```bash
automod-cli.sh crashlog analyze <logfile> --json   # detect NVAC vs modern; exception, suspect modules (noise-filtered), plugin count
automod-cli.sh crashlog find --json                # locate crash logs (notes the MO2 overwrite\ location)
```
Surfaces signals — it does not "solve" the crash; the top module is not automatically the cause. See the `fnv-crashlog` skill.

## `funcs` — NVSE function index (from installed extender DLLs)
```bash
automod-cli.sh funcs list <plugin.dll> [--grep <substr>] [--limit N] --json   # e.g. funcs list jip_nvse.dll --grep weapon
automod-cli.sh funcs scan <dir> [--grep <substr>] --json                       # per-DLL counts under a folder
```
Heuristic extraction (string scan + prefix/denylist) — high precision, **not exhaustive**. geckwiki "Functions" categories are the authoritative complete reference. See KB → NVSE Function Reference.

## `ini` — game-INI audit (read-only)
```bash
automod-cli.sh ini audit [<Fallout.ini>] --json   # no path = auto-detect the FNV INIs in Documents\My Games\FalloutNV
```
Flags known **harmful/placebo/dangerous** tweaks (`bUseMultiThreadedFaceGen`, `bMultiThreadAudio`, `uGridsToLoad>5`, …). **Never edits** an INI. The real tested knobs live in `nvse_stewie_tweaks.ini`/NVTF — see KB → INI Tuning.

## `build` — native NVSE plugin via your MSVC (no compiler bundled)
```bash
automod-cli.sh build detect --json                                    # vswhere → VS path, MSVC toolset (→vXXX), x86 cl.exe, dumpbin; ready?
automod-cli.sh build scaffold <outDir> --name MyPlugin --sdk <nvse-sdk-dir> [--dry-run] --json   # main.cpp + exports.def + .vcxproj (Win32/Release/MT)
automod-cli.sh build compile <project.vcxproj> [--toolset vXXX] [--vs <path>] [--dry-run] --json # Enter-VsDevShell -arch=x86 + MSBuild; finds the DLL
automod-cli.sh build verify <plugin.dll> [--vs <path>] --json         # dumpbin: exports NVSEPlugin_Query/Load + 14C machine (x86)
```
Wraps the **validated** recipe (auto-fills PlatformToolset, forces **Win32/Release/`/MT`**). FNV is 32-bit → the DLL **must** be x86. The toolbox ships **no compiler** — install **Visual Studio Build Tools** ("Desktop development with C++", incl. x86 toolset + a Windows SDK) and the **xNVSE SDK** (`--sdk` = the dir containing `nvse/`). `--dry-run` on `compile` prints the exact PowerShell pipeline without building. This is the last-resort, engine-level path — prefer GECK script / existing plugins first. See the `nvse-plugin` skill.

## Notes
- Each invocation is a fresh process; `esp` commands reload the plugin's masters each time (so they can be slower).
- **MO2:** write outputs into a mod folder / `overwrite/` and enable in MO2 — not the real `Data\`. xEditLib `esp` commands only see the modded order when run **through MO2**.
- Modules were validated against a real FNV install / toolchain: esp round-trip, bsa listing 783 meshes, audio 44.1k→24k mono, nif on a real mesh, mcm schema, and `build` end-to-end (scaffold → MSBuild x86 DLL → dumpbin verify).

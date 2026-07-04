---
name: nvse-plugin
description: Scaffold and build a native NVSE plugin (C++ DLL) for Fallout New Vegas using the user's installed MSVC. Use only when engine-level functionality is needed that GECK script / existing plugins can't provide.
argument-hint: "[what the plugin should do]"
---

# Build an NVSE Plugin (native C++)

An NVSE plugin is a compiled **C++ DLL** that hooks the FNV engine — for new script functions, engine patches, or event hooks beyond GECK script. This is **systems programming**, not GECK modding. The toolbox does **not bundle a compiler**; it drives your installed **MSVC** (Visual Studio / Build Tools — free). See `docs/nvse-plugin-skill-design.md` for the design rationale.

## Before anything: prefer a lighter path
A custom DLL is the **last resort**. First check whether the goal is achievable via:
- **GECK script** (a one-quest-script esp — use `create-mod`/`esp`),
- an **existing NVSE plugin's config** (lStewieAl's Tweaks, JIP LN, JohnnyGuitar — many "engine tweaks" already exist),
- or **kNVSE / config-driven** approaches.
If yes, do that instead. Native plugins run as engine code — **a bug crashes the game or corrupts saves.**

## Prerequisites (verify first — stop if missing)
1. **MSVC with the C++ x86 toolset.** FNV is 32-bit → the plugin **must** be a **Win32/x86** DLL.
   - Locate VS: `"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -property installationPath`
   - The compiler (`cl.exe`) only exists inside a VS dev environment — activate with **`vcvars32.bat`** (or `vcvarsall.bat x86`), found under `<VS>\VC\Auxiliary\Build\`.
   - If MSVC/the C++ workload is absent → tell the user to install **Visual Studio Build Tools** (free) with **"Desktop development with C++"** (incl. the x86 toolset + a Windows SDK). Do not proceed without it.
2. **xNVSE plugin SDK** — headers + the `nvse_plugin_example` from the [xNVSE source](https://github.com/xNVSE/NVSE). Obtain/point to these (the user provides or clones the repo); the scaffold compiles against them.

## Fast path: the `build` AutoMod module
The deterministic steps below are wrapped by `automod build` (drives **your** MSVC; bundles no compiler):
```bash
bash tools/automod-cli.sh build detect --json                                  # VS path, toolset (→vXXX), x86 cl.exe, dumpbin — ready?
bash tools/automod-cli.sh build scaffold ./MyPlugin --name MyPlugin --sdk <nvse-sdk-dir> --json
bash tools/automod-cli.sh build compile ./MyPlugin/MyPlugin.vcxproj --json      # x86 dev shell + MSBuild Win32/Release/MT
bash tools/automod-cli.sh build verify ./MyPlugin/Release/MyPlugin.dll --json   # dumpbin: exports + 14C machine (x86)
```
Use it for detection/compile/verify; use the **judgement** steps below for the SDK layout, what to hook, command registration, and the opcode base — the module can't decide those. `compile --dry-run` prints the exact pipeline first.

## Workflow
1. **Confirm goal & prereqs.** Restate what the plugin must do. Run `build detect` (or vswhere); confirm the x86 toolset + Windows SDK + the NVSE SDK. State a confidence level.
2. **Scaffold the project** in a working dir (NOT the live game `Data/`):
   - `main.cpp` — `NVSEPlugin_Query` + `NVSEPlugin_Load`, a `PluginInfo` (name/version), NVSE/runtime version checks, and command/function registration.
   - `exports.def` — export `NVSEPlugin_Query` and `NVSEPlugin_Load`.
   - Build file — a `.vcxproj` (MSBuild) **or** a direct `cl` command. Target **Platform=Win32, Configuration=Release, `/MT`** (static CRT → no VC++ redist needed), **`/EHsc`**, include the NVSE SDK headers.
3. **Write the source** against the NVSE plugin API: register functions (`nvse->RegisterTypedCommand`), use the script-extender services, and hook conservatively (address-library/known offsets). Keep it minimal and well-understood.
4. **Build** — enter an **x86** VS dev environment, then MSBuild. The **reliable** way (PowerShell; `cmd /c "... && ..."` quoting is fragile and may swallow output):
   ```powershell
   Import-Module "<VS>\Common7\Tools\Microsoft.VisualStudio.DevShell.dll"
   Enter-VsDevShell -VsInstallPath "<VS>" -DevCmdArguments '-arch=x86' -SkipAutomaticLocation
   msbuild MyPlugin.vcxproj /t:Rebuild /p:Configuration=Release /p:Platform=Win32 /p:PlatformToolset=<installed> /m
   ```
   (Find `<VS>` with `vswhere -latest -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`; find `<installed>` toolset under `<VS>\VC\Tools\MSVC\`.)
5. **Verify the build**: `dumpbin /exports MyPlugin.dll` shows **`NVSEPlugin_Query` + `NVSEPlugin_Load`**, and `dumpbin /headers` shows **`14C machine (x86)`**.
6. **Install**: place `MyPlugin.dll` in `Data/NVSE/Plugins/`. **Under MO2:** put it in a mod folder's `NVSE/Plugins/` and enable in MO2 — not the real `Data/`. Launch via **xNVSE**; check `nvse.log` for the plugin loading.

## Safety & honesty
- Native plugins are not sandboxed by the toolbox's hooks (they're compiled, not edited game files). **Test on a throwaway save.**
- This is the most error-prone skill (x86 correctness, ABI, SDK version, hook addresses). Target ≥90% confidence; when unsure, stop and explain.
- **Status: VALIDATED ✅ (incl. in-game)** — the xNVSE `nvse_plugin_example` was built into a 32-bit DLL exporting `NVSEPlugin_Query`/`NVSEPlugin_Load` on VS Community 2026, deployed as an MO2 mod, and **confirmed loading in-game** — `nvse.log`: `plugin …nvse_plugin_example.dll (MyFirstPlugin; version 2) loaded correctly`.
- **Opcode base:** if `nvse.log` says *"using the default opcode base"*, that's the example's placeholder — for a real plugin, request an **assigned opcode base** from the NVSE team and set it in your first `SetOpcodeBase` call (avoids command-ID clashes with other plugins).

## Gotchas (hit while validating the example build)
- **Toolset retarget:** the example targets `PlatformToolset v143` (VS2022); on a newer VS pass `/p:PlatformToolset=<installed>` (e.g. `v145` for VS2026 / MSVC 14.5x).
- **CRT must match across projects:** the SDK's `common` project (`common_vc9.vcxproj`) shipped `/MD` (MultiThreadedDLL) while the example used `/MT` → `LNK2038 RuntimeLibrary mismatch` + unresolved CRT imports (`__imp___fsopen`, …). Fix: make them consistent — set `common`'s Release `RuntimeLibrary` to `MultiThreaded` (`/MT`) to match (self-contained DLL), or switch both to `/MD`.
- **Post-build copy can fail harmlessly:** the example's post-build step does `copy … "\Data\NVSE\Plugins\…"` (hardcoded path); it errors `MSB3073` if that path is invalid, but **the DLL is already produced in `Release\`** — ignore it (or fix the path).
- The `vswhere.exe is not recognized` line from `Enter-VsDevShell` is a benign warning.

## Output
Report: prereq check (VS path, x86 toolset, SDK), what was scaffolded, the source's behavior, the exact build command + result (DLL path, `dumpbin` exports, machine type), install location, and in-game verification steps (`nvse.log`).

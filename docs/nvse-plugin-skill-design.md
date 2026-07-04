# Design Spec: `nvse-plugin` skill (native NVSE plugin builder)

**Status:** ✅ **VALIDATED end-to-end** — built the xNVSE `nvse_plugin_example` into a 32-bit DLL (`14C machine (x86)`, exports `NVSEPlugin_Query`/`NVSEPlugin_Load`) on VS Community 2026. Skill: `.claude/skills/nvse-plugin/SKILL.md`.

## Goal
Let the toolbox help author **native NVSE plugins** (C++ DLLs in `Data/NVSE/Plugins/`) for capabilities GECK script can't provide — new script functions, engine hooks, event handlers. Claude writes the C++ source + build files; the user's compiler produces the DLL.

## Core decision: wrap MSVC, do NOT bundle a compiler
Considered and rejected:
- **Write our own compiler** — absurd scope (a real C++ compiler is decades of work; tiny compilers like TinyCC are C-only).
- **Bundle MinGW/Clang** — possible but a bad fit: the FNV/NVSE ecosystem is **MSVC-built**, so non-MSVC output risks ABI/vtable/struct-layout breakage; the NVSE SDK is MSVC-oriented (`__declspec`, `__thiscall`/`__fastcall` hooks, pragmas); bundle size is 100 MB–2 GB vs an 82 KB toolbox; and we'd own a compiler distribution.

**Chosen:** detect-and-invoke the user's **MSVC** (Visual Studio / free Build Tools), exactly like the toolbox already wraps BSArch/oggenc2/xEditLib. The user installs the free C++ workload once; the skill drives it.

## Feasibility on this machine
`vswhere` reports **Visual Studio Community 2026** with the **VC C++ x86/x64 toolset** installed — so the wrap approach works here without anything new. (`cl.exe` is not on PATH by default; it's activated per-shell via `vcvars32.bat`.)

## Technical constraints (the things that must be right)
1. **32-bit / x86.** FNV is a 32-bit process — the DLL must be **Win32/x86**. Build with `vcvars32.bat` (or `vcvarsall.bat x86`) and `Platform=Win32`. An x64 DLL will not load.
2. **Entry points.** Export `NVSEPlugin_Query` and `NVSEPlugin_Load` (via `exports.def`); implement `PluginInfo` + NVSE/runtime version checks.
3. **CRT linkage.** Prefer `/MT` (static CRT) so end users don't need a specific VC++ redist.
4. **SDK.** Compile against the **xNVSE plugin SDK** headers + the sources you use (from the xNVSE repo / `nvse_plugin_example`). The SDK isn't bundled — the user provides it (clone xNVSE).
5. **Hooks.** Engine hooking uses known addresses; be conservative. Wrong addresses = crashes.

## Build approaches (pick per situation)
- **MSBuild + `.vcxproj`** — closest to the canonical `nvse_plugin_example`; `msbuild /p:Configuration=Release /p:Platform=Win32`.
- **Direct `cl`** — simplest for a tiny plugin; `cl /LD /MT /EHsc /I<sdk> main.cpp <srcs> /link /DEF:exports.def`.
- (CMake is possible but the SDK isn't CMake-native; not the default.)
All run inside a `cmd /c "<vcvars32.bat> && <build>"` so the x86 toolset is active.

## Validation gaps / open questions
- [x] **End-to-end compile — DONE.** Cloned xNVSE, built `nvse_plugin_example` Release/Win32 via `Enter-VsDevShell -arch=x86` + MSBuild (toolset `v145`). Output: a 32-bit DLL exporting `NVSEPlugin_Query`/`NVSEPlugin_Load` (verified `dumpbin`). Fixes needed: retarget v143→v145; align CRT (`common_vc9` `/MD`→`/MT`). **In-game load test PASSED** — deployed the DLL as an MO2 mod in a real MO2 instance; xNVSE loaded it (`nvse.log`: `MyFirstPlugin; version 2 … loaded correctly`). Recipe + gotchas captured in the skill.
- [ ] Decide whether the skill should **auto-clone the xNVSE SDK** or require the user to point at it.
- [x] **`automod` `build` module — DONE.** Wraps vswhere-detect + `Enter-VsDevShell -arch=x86` + MSBuild + dumpbin as `automod build detect|scaffold|compile|verify --json`. Validated end-to-end: `detect` auto-found VS + MSVC 14.51 (→`v145`) + x86 `cl.exe`; `scaffold` emitted a Win32/Release/`/MT` project; `compile` produced a 32-bit DLL via MSBuild; `verify` confirmed `NVSEPlugin_Query`/`NVSEPlugin_Load` exports + `14C machine (x86)` via dumpbin.
- [ ] Address-library/version-independence story for hooks (out of scope for v1; document "compile for your runtime").

## Guardrails (baked into the skill)
- **Last resort:** prefer GECK script / existing plugin configs / kNVSE first.
- **Not sandboxed:** compiled code isn't gated by the file hooks; test on throwaway saves.
- **Honesty:** the skill states the build path is unvalidated end-to-end until the first real compile.

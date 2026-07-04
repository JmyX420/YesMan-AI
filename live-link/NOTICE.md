# Attribution & Derivation

**YesMan AI Live Link** is a Fallout: New Vegas re-architecture of the concept behind
**SkyLink AI** (a.k.a. SkyrimMCP) by **Jarvann**, used under the MIT License.

- Upstream project: "SkyLink AI" / SkyrimMCP by Jarvann
  (<https://github.com/jarvann/SkryimMCM>).
- Upstream license: **MIT** (verified on the upstream repository).

## What this port is — and is NOT

This is a **clean re-architecture of the idea**, not a code port. **No upstream
source code is copied.** The two projects target fundamentally different engines
and script-extender ecosystems, so nothing transfers verbatim:

| | SkyLink AI (upstream) | YesMan AI Live Link (this) |
|---|---|---|
| Game / engine | Skyrim SE/AE — Creation Engine | Fallout: New Vegas — Gamebryo |
| Script extender | SKSE64 + CommonLibSSE-NG + Address Library | NVSE/xNVSE + JIP LN / JohnnyGuitar / ShowOff |
| In-game executor | C++ SKSE plugin (typed engine access) | loose NVSE script via JIP LN **Script Runner** (no plugin, no DLL) |
| Transport | C# (.NET) MCP server ⇄ named pipe | Python MCP server ⇄ **file bridge** (atomic JSON) |
| Engine bridge | Papyrus VM → ~3,389 funcs | NVSE function libraries (JIP/JG/ShowOff/…) |

## What this shares with the rest of the toolbox

The MCP transport layer is adapted from YesMan AI's own
**MO2 MCP Server** (`mo2-mcp/`, itself MIT) — the `ToolRegistry` and JSON-RPC
dispatch pattern — re-cast here as a **standalone stdio server** so Claude Code
spawns it directly (no Mod Organizer 2 process required).

## Runtime-conditional, self-contained

YesMan AI Live Link is **installed with YesMan AI** as one of its components. It is a
real-time channel to a *running* game, so it is only active while FNV is running
with a save loaded; when the game is closed, its `fnv_*` tools are simply idle and
nothing else in the toolbox depends on them. Unlike the MO2 MCP it has no offline
fallback — talking to a live game inherently requires the game to be live.

## Third-party tools

The in-game side depends on the user's installed NVSE extender stack
(xNVSE, JIP LN NVSE, JohnnyGuitar NVSE, ShowOff NVSE), each under its own
license and not bundled here.

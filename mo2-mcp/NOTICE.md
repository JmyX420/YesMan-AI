# Attribution & Derivation

**FNV MO2 MCP Server** is a Fallout: New Vegas port of the **MO2 MCP Server**
by **Aaronavich** (a.k.a. Avick3110), used under the MIT License.

- Upstream project: "MO2 MCP Server" / Claude_MO2 by Aaronavich
  (<https://github.com/Avick3110/Claude_MO2>).
- Upstream version this port derives from: **v2.9.5**.
- Upstream license: **MIT** (see `LICENSE`; the original copyright notice is retained there).

## What this port changes
The upstream server targets **Skyrim Special Edition** and reads/patches plugin
records through **Mutagen** (a C# library) and a bundled ".NET Spooky CLI."
Mutagen does not support Fallout: New Vegas, so this port:

- **Keeps, ported verbatim or lightly adapted:** the MO2-plugin shell and the
  stdlib HTTP/MCP transport (`mcp_server.py`), and the game-agnostic tool groups
  that read Mod Organizer 2's virtual file system and load order via `mobase`
  (modlist, filesystem, write).
- **Re-backs on a different engine:** record reading/patching and the asset tools
  (BSA/NIF/audio) are routed to **YesMan AI's AutoMod CLI**
  (xEditLib `GM_FNV=0` for records; BSArch `-fnv`, self-built NIF reader, oggenc2),
  which are validated against real FNV plugins/assets — instead of Mutagen/Spooky.
- **Drops:** Papyrus compilation (Fallout: New Vegas has no Papyrus — GECK script
  is stored inside plugins).
- **Bakes in** the operational fixes needed to run under MO2 on New Vegas + NVMP
  (game requirement, working auto-start, default port 49200, launcher-restart latch).

## Third-party tools
External tools the server may invoke (BSArch, xEdit/xEditLib, oggenc2, NIF tools,
`pefile`) retain their own licenses; see the upstream `THIRD_PARTY_NOTICES.md` and
each tool's distribution. None are bundled by this repository unless noted.

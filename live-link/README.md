# YesMan AI Live Link

A live game link for **Fallout: New Vegas** — lets Claude (via Claude Code) read state
from, react to events in, **chat with the player in**, and issue commands to the **running**
game. A component of YesMan AI, installed with the toolbox. Re-architecture of the
**SkyLink AI** concept by Jarvann (MIT). See [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md).

The link is **active whenever FNV is running** with a save loaded (and the NVSE stack incl.
JIP PP LN is installed); the rest of the toolbox works normally when the game is closed. This
is a real-time channel to a live game session — there is no offline equivalent to fall back to.

## What Claude can do with it

- **Observe** — `fnv_get_player_state` returns a 23-field live snapshot: position, health
  (cur/max), survival stats (food/water/sleep/rads), karma, level, caps, cell, equipped
  weapon (name+FormID), in-game time, and the active quest (name/stage/current objective).
- **React** — `fnv_poll_events` drains a queue of **38 pushed event types** (each with a name +
  FormID where applicable), including: `death`, `murder`, `combat`, `combat_end` (kills + fight
  start/end); `pickup`, `sell`, `equip`, `unequip`, `aid_use`, `read_book`, `steal`, `reload`
  (item/inventory events — `aid_use` covers all vanilla ingestibles); `cell_enter`, `discover`,
  `fast_travel`, `sleep_wait` (movement/time); `perk`, `challenge_complete`, `quest_complete`,
  `quest_fail`, `objective_shown`, `objective_complete`, `misc_stat` (progression — the
  JohnnyGuitar/ShowOff ones need those plugins); `holster`, `unholster`, `vats_enter`,
  `vats_leave`, `killcam_start`, `killcam_end`, `weapon_jam`, `casino_ban`, `crippled_limb`
  (combat/weapon/VATS — `holster`/`unholster` via ShowOff; VATS/killcam/jam/casino-ban via
  ITR NVSE; `crippled_limb` via JIP); `note_added`; `dialogue` (what NPCs say to you in a conversation — the
  speaker + the spoken line, captured from the on-screen subtitle, so dialogue subtitles must be
  enabled); and `save` / `load` / `exit_to_main_menu` / `exit_game`
  (session boundaries). See the `fnv_poll_events` tool description for the full, current list.
- **Converse** — a two-way in-game **text chat** with a persistent, scrollable conversation log.
  The player presses **`\`** (Backslash) to open a chat window and type a message — Claude reads it
  via `fnv_poll_chat`; Claude replies with `fnv_chat_reply`. Both sides' lines accumulate in a
  read-only **scrollable log** at the top of the window (`You:` / `Claude:` prefixed) that survives
  box-close **and** save reloads — scroll the mouse wheel or the arrows to read back through the
  whole history. The window **stays open after each send** (the input field clears, ready for the
  next line) and has **Clear** (wipe the input field), **Clear Log** (erase the conversation
  history), and **Close** buttons beside the native OK. No console parser is
  involved, so free-form prose survives intact. Built on JIP's `ShowTextInputMenu` + a custom
  injected UI (`InjectUIXML`); needs only the JIP requirement below.
- **Act** — command tools (18 tools total, including the two chat tools above), notably:
  - `fnv_console` — the catch-all: **any** console command the player could type
    (`tgm`, `tcl`, `player.additem ...`, `coc ...`), short aliases auto-translated.
  - `fnv_run_script` — any GECK script snippet.
  - Typed shortcuts: `fnv_message` (corner-notification text to the player), `fnv_set_time`,
    `fnv_set_weather`, `fnv_additem`/`fnv_removeitem`/`fnv_equipitem`, `fnv_moveto`,
    `fnv_placeatme`, `fnv_setav`/`fnv_modav`, `fnv_setstage`, plus `fnv_link_status`.

## How it works

```
Claude Code ⇄ stdio/MCP ⇄ Python relay ⇄ JSON files in <game-root>\FNVLink\ ⇄ in-game scripts
```

The relay is a stdio MCP server (`fnv_link_server`). The in-game side is eight esp-less
GECK scripts run by JIP LN's Script Runner — no plugin DLL, no esp (heartbeat/state, command
dispatch, world events, JohnnyGuitar events, lifecycle events, aid events, NPC dialogue capture,
and the chat box).
State, commands, events, and chat are exchanged as JSON files in a bridge folder under the game
root; the chat window's scrollable log, custom buttons, and layout are injected at runtime from a
relay-seeded XML fragment, and its log is rendered from a persistent `chatlog.json`.

## Requirements

**In-game — required** (the scripts abort on load without these):
- **xNVSE** 6.21+
- **JIP PP LN** (the maintained JIP LN fork) — **not** plain JIP LN 57.30. Required for the
  `fnv_console` catch-all (JIP LN 57.30's `Console` function can't run console-only toggles).

These two alone give you most events plus the full player/world snapshot, all command tools,
and the in-game chat.

**In-game — recommended** (each unlocks more of the 38 event types; the link degrades
gracefully without them — those `SetEventHandler` registrations simply no-op):
- **JohnnyGuitar NVSE** — perks, quest complete/fail, challenge complete, sleep/wait.
  **Mandatory if installed: set `bJIPFixes = 0` in JohnnyGuitar's INI** — JohnnyGuitar will
  not function alongside JIP PP LN otherwise.
- **ShowOff NVSE** — books read, weapon holster/unholster, quest objectives, misc PC stats.
- **ITR NVSE** — steal, VATS enter/leave, killcam, weapon jams, casino bans.

(NPC-`dialogue` capture needs no plugin — it reads on-screen subtitles, so just enable
in-game dialogue subtitles.)

**This package:**
- Python 3.x (a real install — not the Windows Store stub) for the relay.
- Claude Code (registers the MCP server in `~/.claude.json`).

**Optional but recommended for hands-free use:**
- **OneTweak BRU** with `[Active in background] Active = true` in its INI. FNV pauses its
  main loop when the window loses focus; this setting keeps the simulation running (and
  the link live) while you read/type to Claude in another window — without leaking your
  keystrokes into the game. (Note: lStewieAl's "No Alt-TAB Pause" only stops the pause
  *menu*; it does **not** keep the sim running. Don't rely on it for this.)

## Install

**The YesMan AI installer sets this up for you** — it seeds the bridge dir, deploys the
mod into the MO2 instance you pick (or into `Data\` for a non-MO2 setup), and registers the
`fnv-link` MCP server. You just enable the **YesMan AI Live Link** mod in MO2, restart
Claude Code, launch FNV via xNVSE, and load a save.

*Manual/standalone deploy* (if you're not using the installer) — this `install.py` is what
the installer calls under the hood, and can be run directly:
```
python install.py --game-root "C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas" \
                  --deploy mo2 --mo2-mods "<your MO2 instance>\mods"
```
(`--game-root` is auto-detected from common Steam paths if omitted. Use `--deploy data` to
install straight into `Data\` for a non-MO2 setup, or `--deploy none` to place the scripts
yourself. Re-runnable; `--uninstall` reverses it.)

For real-time reactions, also ask Claude to **arm the live feed** (see *Real-time feedback* below).

## Real-time feedback (live monitor)

By default Claude only learns about new events and chat when it **polls** (`fnv_poll_events` /
`fnv_poll_chat`) — i.e. when you prompt it to. For a hands-free, **truly live** experience —
Claude reacting as things happen and answering your in-game chat on its own — ask Claude to
**"arm the live feed"**. It sets up a lightweight background watch loop that drains the event +
chat queues every ~15s and surfaces each new item automatically; idle play stays silent. Notes:

- It's **session-scoped** — it does **not** survive a Claude Code restart and isn't auto-restored,
  so re-arm it each session (just say "arm the live feed" again).
- It can also stop silently if it crashes or is culled. If the feed goes quiet unexpectedly, ask
  Claude to confirm it's still running and re-arm if needed.
- While it's armed, Claude relies on it instead of manual polling — so it's the one draining the
  queues.

## Focused vs. background mode

- **Focused** (no extra setup): the link is fully functional while FNV is the active window.
  If you tab away, the game pauses; a command issued then is **queued** and runs when you tab
  back in (the tools tell you so rather than failing).
- **Background** (OneTweak `Active=true`): the game keeps simulating while unfocused, so
  Claude can observe and act live while you watch/chat from another window.

## Troubleshooting

- **`fnv_link_status` says not connected / commands say "game not running":** FNV isn't
  running, no save is loaded, or (without background-running) the window is unfocused/paused.
- **`fnv_console` toggles (tgm/tcl) do nothing:** you're on plain JIP LN 57.30 — switch to
  **JIP PP LN**. (Other console commands still work.)
- **In-game compile errors:** check `<MO2 instance>\overwrite\Root\jip_ln_nvse.log` and the
  in-game console (`~`).
- The relay's bridge files live in `<game-root>\FNVLink\`; the relay re-seeds them on start.

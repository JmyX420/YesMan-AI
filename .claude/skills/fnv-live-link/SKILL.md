---
name: fnv-live-link
description: Read state from, react to events in, two-way text-chat with the player in, and command a RUNNING Fallout New Vegas game in real time via the YesMan AI Live Link MCP server (mcp__fnv-link__* tools). Use when the user wants Claude to observe, control, chat inside, or play alongside their live FNV session.
---

# YesMan AI Live Link — operating a running game

The live link exposes the running game through the **`fnv-link` MCP server** (tools named
`fnv_*`). If those tools aren't present, the game isn't running / the mod isn't enabled — point
the user to `live-link/README.md` (enable the **YesMan AI Live Link** mod in MO2, launch FNV
with a save loaded, restart Claude Code). The link is a toolbox component that's only active
while the game is live; nothing else in the toolbox depends on it.

## Always start with status
Call **`fnv_link_status`** first. It reports `game_connected` and a freshness detail:
- **connected** → act freely.
- **stale/paused** → the game is open but unfocused/paused (no background-running). Commands
  are **queued** and run when the user tabs back into FNV — tell the user that, don't treat it
  as an error.
- **not running** → ask the user to launch FNV (xNVSE) and load a save.

## Observe — `fnv_get_player_state`
Returns a live snapshot (~23 fields): `px/py/pz`, `health`/`health_max`, `food`/`h2o`/`sleep`
(Hardcore survival), `rads`, `karma`, `level`, `caps`, `cell`, `weapon`/`weapon_form`,
`gamehour`, `quest`/`quest_stage`/`quest_objective`, and `tick` (liveness). Use it to ground
decisions and to **verify** that a command took effect (commands don't return console text).

## React — `fnv_poll_events`
A **consume-once** queue: each call returns events pushed since the last call, then clears
them. **38 types** spanning combat (`death`, `murder`, `combat`, `combat_end`, `vats_enter`,
`vats_leave`, `killcam_start`, `killcam_end`, `weapon_jam`, `crippled_limb`), items/inventory
(`pickup`, `sell`, `equip`, `unequip`, `aid_use`, `read_book`, `steal`, `reload`, `note_added`,
`holster`, `unholster`), movement/world (`cell_enter`, `discover`, `fast_travel`, `sleep_wait`,
`casino_ban`), progression (`perk`, `challenge_complete`, `quest_complete`, `quest_fail`,
`objective_shown`, `objective_complete`, `misc_stat`), `dialogue` (what an NPC says to the player
in conversation — `name` = speaker, `text` = the line; read from the on-screen subtitle, so
dialogue subtitles must be enabled), and session (`save`, `load`,
`exit_to_main_menu`, `exit_game`). Each is `{seq, type, name, form, gamehour}` (+ extra fields
on some, e.g. `misc_stat`/`crippled_limb`/`vats_leave`); the tool's own description has the
authoritative list. Poll when you want to react to what's happening.

## Converse — two-way in-game text chat (`fnv_poll_chat` / `fnv_chat_reply`)
The player presses **`\`** (Backslash) in-game to open a text box and type a message to you.
- **`fnv_poll_chat`** — consume-once queue of the player's messages (`{seq, text, gamehour}`),
  drained on read. Poll it to see what they said.
- **`fnv_chat_reply "text"`** — reply IN the chat box: your line is appended to a persistent,
  **scrollable conversation log** at the top of the window (the whole back-and-forth, `You:`/
  `Claude:` prefixed; survives box-close and save reloads — the player scrolls the wheel/arrows to
  read history). It opens scrolled to your newest line; the input field stays empty so the player
  reads and types the next line in the same window, which **stays open after each send**. The box
  also has **Clear** (wipe the field), **Clear Log** (erase the conversation history), and
  **Close** (dismiss without sending) buttons. Keep replies
  ≲400 chars (split longer ones). **No semicolons** in the text (the GECK Script Runner treats `;`
  as a comment — the relay strips them, but keep replies clean). For a brief corner notification
  instead, use `fnv_message`.

A typical loop: `fnv_poll_chat` → read the player's message → `fnv_chat_reply` (or act on a
request with the command tools, then confirm via `fnv_chat_reply`/`fnv_message`).

## Real-time feedback — arm a live-feed monitor (for a true hands-free experience)
`fnv_poll_events` / `fnv_poll_chat` are **on-demand** — you only see what happened when you
*choose* to call them. For a genuinely live experience (you react as events fire and answer the
player's chat without them prompting you to poll), arm a **persistent background watch loop** that
drains the feed for you. In Claude Code that's a background monitor running a long-lived process
which, every ~15s, calls the relay's `Bridge(<bridge-dir>).drain_events()` + `.drain_chat()`
(reuse `fnv_link_server.bridge` — you inherit its partial-read tolerance + `misc_stat` name
enrichment) and prints one line per new event/message. Idle play is silent (no token cost); it
only emits on activity, ≤15s latency. **Cap the output** (e.g. ≤12 event lines/tick + an
`(+N more)` summary) so a firefight can't trip the harness's too-many-events auto-stop.

This is what makes the link feel alive rather than poll-on-request — offer it whenever the user
wants to *play alongside* you. Rules that matter:
- **While the monitor runs, IT is the consumer** — it drains both queues, so do NOT also call
  `fnv_poll_events`/`fnv_poll_chat` yourself, or you'll double-drain and the monitor will miss
  items.
- **Session-scoped, no persistence.** It dies on a Claude restart and can crash or be culled
  **silently, with no notification**. Re-arm it each session (the user says "arm the live feed").
- **Verify before you claim it's running.** Never assume — check the background task's status
  first (a silent death looks identical to a quiet game). If you can't confirm it's alive, say so
  and offer to re-arm rather than asserting it's up.
- Most event handlers are **player-filtered**, so NPC-vs-NPC chaos (player isn't the killer) fires
  few events — a quiet feed during a brawl can be normal, not a dead monitor.

## Act — command tools
- **`fnv_console`** — the catch-all. Runs ANY console command the player could type, including
  console-only toggles (`tgm`, `tcl`, `tfc`, `tmm`). Short aliases are auto-translated to full
  names. Use real **FormIDs** (e.g. `player.additem 0000000f 1000`), not editor IDs.
- **`fnv_run_script`** — any GECK *result-script* snippet (e.g. `set GameHour to 8`). This is
  GECK script, not console syntax.
- **`fnv_message "text"`** — put text on the player's screen. This is your channel to talk to
  the player *inside the game*.
- Typed shortcuts: `fnv_set_time`, `fnv_set_weather`, `fnv_additem`/`fnv_removeitem`/
  `fnv_equipitem`, `fnv_moveto`, `fnv_placeatme`, `fnv_setav`/`fnv_modav`, `fnv_setstage`.

### Command notes
- `ok:true` means the in-game batch ran; it does **not** confirm the command's own effect —
  verify via `fnv_get_player_state` where it matters.
- `queued:true` → the game was paused; the command will run when the user returns to FNV.
- `down:true` → the game isn't running.
- Caps are an item (`fnv_additem 0000000f`), not an actor value.

## Working style
- These commands change the user's live game. For anything destructive, irreversible, or
  surprising (spawning enemies, killing NPCs, teleporting, wiping items), **confirm with the
  user first** unless they've clearly asked for it.
- Prefer the typed tool when one fits; reach for `fnv_console`/`fnv_run_script` for anything
  without a wrapper.
- To play "alongside" the user hands-free (acting while they're in another window), they need
  OneTweak BRU with `[Active in background] Active = true` (see README). Without it, you work
  in focused mode: they ask, you queue/act, they tab into the game.

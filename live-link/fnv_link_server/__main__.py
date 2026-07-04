# fnv_link_server — entrypoint
#
# YesMan AI Live Link (c) 2026 JmyX. MIT. See LICENSE and NOTICE.md.
#
# Run:  python -m fnv_link_server --bridge <shared-dir>
# Claude Code spawns this and speaks MCP over stdio. Logs go to stderr so stdout
# stays a clean JSON-RPC channel.

import argparse
import logging
import os
import sys

from .config import (
    SERVER_NAME,
    SERVER_VERSION,
    BRIDGE_ENV_VAR,
)
from .bridge import Bridge
from .registry import ToolRegistry
from .transport import StdioServer

log = logging.getLogger("fnv_link")


def _make_status_handler(bridge: Bridge | None):
    def handler(_args):
        if bridge is None:
            return {
                "server": SERVER_NAME,
                "version": SERVER_VERSION,
                "bridge_dir": None,
                "game_connected": False,
                "detail": "no bridge directory configured (pass --bridge or set "
                          f"{BRIDGE_ENV_VAR})",
            }
        state = bridge.read_state()
        if state is None:
            detail = "no state.json yet — in-game script has not written"
        elif state.get("_fresh"):
            detail = f"heartbeat fresh (age {state.get('_age_seconds')}s)"
        else:
            detail = (f"heartbeat STALE (age {state.get('_age_seconds')}s) — "
                      "game paused or not running")
        return {
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "bridge_dir": bridge.dir,
            "game_connected": bool(state and state.get("_fresh")),
            "detail": detail,
        }
    return handler


def _make_player_state_handler(bridge: Bridge | None):
    def handler(_args):
        if bridge is None:
            return {"connected": False,
                    "error": f"no bridge configured (pass --bridge or set {BRIDGE_ENV_VAR})"}
        state = bridge.read_state()
        if state is None:
            return {"connected": False,
                    "error": "no state.json — in-game script not loaded / never ran"}
        if not state.get("_fresh"):
            return {"connected": False,
                    "stale_snapshot": state,
                    "error": f"heartbeat STALE (age {state.get('_age_seconds')}s) — "
                             "game paused or not running; snapshot may be old"}
        return {"connected": True, "state": state}
    return handler


def _is_hex(s):
    """Validate a FormID-ish hex string (defensive: it's interpolated into a script)."""
    return bool(s) and len(s) <= 8 and all(c in "0123456789abcdefABCDEF" for c in s)


def _run_script(bridge, script_text, label):
    """Shared path for every command tool. execute_script handles game status:
    runs live, QUEUES when the game is paused/unfocused, refuses when it's down."""
    if bridge is None:
        return {"ok": False, "error": f"no bridge configured (pass --bridge or set "
                                      f"{BRIDGE_ENV_VAR})"}
    return bridge.execute_script(script_text, label=label)


def _make_run_script_handler(bridge):
    def handler(args):
        script = (args or {}).get("script", "")
        if not script.strip():
            return {"ok": False, "error": "empty script"}
        return _run_script(bridge, script, label=script.strip()[:48])
    return handler


def _make_additem_handler(bridge):
    def handler(args):
        form = str((args or {}).get("form", "")).strip()
        count = int((args or {}).get("count", 1))
        if not form:
            return {"ok": False, "error": "form (hex FormID, e.g. 0000000F) required"}
        return _run_script(bridge, f'player.AddItem "{form}" {count}',
                           label=f"additem {form} x{count}")
    return handler


def _make_setstage_handler(bridge):
    def handler(args):
        quest = str((args or {}).get("quest", "")).strip()
        stage = int((args or {}).get("stage", 0))
        if not quest:
            return {"ok": False, "error": "quest (hex FormID) required"}
        return _run_script(bridge, f'SetStage "{quest}" {stage}',
                           label=f"setstage {quest} {stage}")
    return handler


def _make_set_time_handler(bridge):
    def handler(args):
        hour = float((args or {}).get("hour", 12))
        return _run_script(bridge, f"set GameHour to {hour}", label=f"set time {hour}")
    return handler


def _make_set_weather_handler(bridge):
    def handler(args):
        weather = str((args or {}).get("weather", "")).strip()
        if not weather:
            return {"ok": False, "error": "weather (hex FormID) required"}
        return _run_script(bridge, f'ForceWeather "{weather}"',
                           label=f"weather {weather}")
    return handler


# Map common non-ASCII typography to ASCII before building a GECK string literal. The in-game
# string display is ASCII-oriented, so a raw em-dash/smart-quote/ellipsis renders as mojibake
# (e.g. "—" showed up in-game as "â€""). We map the usual offenders, then drop anything else
# non-ASCII so nothing garbled ever reaches the engine. Applied by the message/chat/console tools.
_NONASCII_MAP = {
    "—": "-", "–": "-",            # em / en dash
    "‘": "'", "’": "'",            # left / right single quote
    "“": "'", "”": "'",            # left / right double quote -> apostrophe
    "…": "...",                          # horizontal ellipsis
    " ": " ",                            # non-breaking space
    "•": "-", "·": "-",            # bullet / middle dot
    "™": "(TM)", "®": "(R)", "©": "(C)",
}


def _ascii_safe(s: str) -> str:
    for k, v in _NONASCII_MAP.items():
        s = s.replace(k, v)
    return s.encode("ascii", "ignore").decode("ascii")


def _make_message_handler(bridge):
    def handler(args):
        text = str((args or {}).get("text", "")).strip()
        if not text:
            return {"ok": False, "error": "text required"}
        # Single GECK string literal: no embedded double-quotes, newlines, or semicolons
        # (the Script Runner treats ';' as a comment start even inside a string — gotcha 19).
        safe = (_ascii_safe(text).replace('"', "'").replace(";", ",")
                .replace("\r", " ").replace("\n", " ")[:200])
        return _run_script(bridge, f'MessageEx "{safe}"', label=f"message: {safe[:32]}")
    return handler


def _make_moveto_handler(bridge):
    def handler(args):
        ref = str((args or {}).get("ref", "")).strip()
        if not _is_hex(ref):
            return {"ok": False, "error": "ref (hex FormID of a placed reference) required"}
        return _run_script(bridge, f'Player.MoveTo "{ref}"', label=f"moveto {ref}")
    return handler


def _make_placeatme_handler(bridge):
    def handler(args):
        form = str((args or {}).get("form", "")).strip()
        count = int((args or {}).get("count", 1))
        if not _is_hex(form):
            return {"ok": False, "error": "form (hex FormID) required"}
        return _run_script(bridge, f'Player.PlaceAtMe "{form}" {count}',
                           label=f"placeatme {form} x{count}")
    return handler


def _make_removeitem_handler(bridge):
    def handler(args):
        form = str((args or {}).get("form", "")).strip()
        count = int((args or {}).get("count", 1))
        if not _is_hex(form):
            return {"ok": False, "error": "form (hex FormID) required"}
        return _run_script(bridge, f'player.RemoveItem "{form}" {count}',
                           label=f"removeitem {form} x{count}")
    return handler


def _make_equipitem_handler(bridge):
    def handler(args):
        form = str((args or {}).get("form", "")).strip()
        if not _is_hex(form):
            return {"ok": False, "error": "form (hex FormID) required"}
        return _run_script(bridge, f'player.EquipItem "{form}"', label=f"equipitem {form}")
    return handler


def _av_num(value):
    """Format an AV value: int when whole (RunBatchScript dislikes '0.0'), else float."""
    v = float(value)
    return int(v) if v == int(v) else v


# JIP's Console fn resolves real command names, not the interactive short aliases — verified:
# Console "tgm" does nothing, Console "ToggleGodMode" toggles god mode. Map the common
# shortcuts to their full names (only the leading token; any args are preserved).
_CONSOLE_ALIASES = {
    "tgm": "ToggleGodMode", "tcl": "ToggleCollision", "tdetect": "ToggleDetection",
    "tai": "ToggleAI", "tcai": "ToggleCombatAI", "tmm": "ToggleMapMarkers",
    "tm": "ToggleMenus", "tfc": "ToggleFreeCamera", "tfow": "ToggleFogOfWar",
    "tgp": "TogglePrimitives", "coc": "CenterOnCell", "cow": "CenterOnWorld",
}


def _make_console_handler(bridge):
    def handler(args):
        cmd = str((args or {}).get("command", "")).strip()
        if not cmd:
            return {"ok": False, "error": "command required"}
        # Translate a leading console short-alias to its full command name.
        parts = cmd.split(None, 1)
        full = _CONSOLE_ALIASES.get(parts[0].lower())
        if full:
            cmd = full + ((" " + parts[1]) if len(parts) > 1 else "")
        # One GECK string literal: collapse inner quotes/newlines.
        safe = _ascii_safe(cmd).replace('"', "'").replace("\r", " ").replace("\n", " ")
        return _run_script(bridge, f'Console "{safe}"', label=f"console: {safe[:40]}")
    return handler


def _make_setav_handler(bridge):
    def handler(args):
        av = str((args or {}).get("av", "")).strip()
        if not av.isalnum():
            return {"ok": False, "error": "av (Actor Value name, letters/digits only) required"}
        v = _av_num((args or {}).get("value", 0))
        # ForceAV (short NVSE form) works in RunBatchScript; ForceActorValue (long) does not.
        return _run_script(bridge, f"Player.ForceAV {av} {v}", label=f"setav {av} {v}")
    return handler


def _make_modav_handler(bridge):
    def handler(args):
        av = str((args or {}).get("av", "")).strip()
        if not av.isalnum():
            return {"ok": False, "error": "av (Actor Value name, letters/digits only) required"}
        v = _av_num((args or {}).get("value", 0))
        return _run_script(bridge, f"Player.ModAV {av} {v}", label=f"modav {av} {v}")
    return handler


def _make_poll_events_handler(bridge):
    def handler(_args):
        if bridge is None:
            return {"connected": False, "error": "no bridge configured"}
        events = bridge.drain_events()
        return {"events": events, "count": len(events)}
    return handler


def _make_poll_chat_handler(bridge):
    def handler(_args):
        if bridge is None:
            return {"connected": False, "error": "no bridge configured"}
        messages = bridge.drain_chat()
        return {"messages": messages, "count": len(messages)}
    return handler


def _make_chat_reply_handler(bridge):
    def handler(args):
        text = str((args or {}).get("text", "")).strip()
        if not text:
            return {"ok": False, "error": "text required"}
        # Sanitize for a single GECK string literal baked into the append below: no embedded
        # double-quotes (-> apostrophes) or newlines (collapsed to spaces; the log wraps on its
        # own), and NO semicolons — the Script Runner strips ';'-to-EOL as a comment even inside a
        # quoted string (gotcha 19), which would drop the closing quote and fail compilation. Cap
        # ~400 chars/call (the log wraps + scrolls, so length is fine; split longer replies).
        body = (_ascii_safe(text).replace('"', "'").replace(";", ",")
                .replace("\r", " ").replace("\n", " ")[:400])
        # v2: (re)open the SAME box, inject the scrollable-log UI + Clear/Close buttons (InjectUIXML
        # reads the relay-seeded fragment), move the native input box DOWN below the log, APPEND
        # Claude's line to the persistent display log chatlog.json as a {role:"claude"} entry, then
        # RunBatchScript the renderer to paint the whole conversation into the read-only log tile.
        # The input field stays EMPTY so the player just types the next line and presses OK/Enter.
        # The box is bottom-anchored, so it opens scrolled to this newest line. AuxVarGetRef in a
        # batch is proven; the callback UDF ref was stashed at startup by ln_FNVLinkChat.txt.
        script = "\r\n".join([
            'ref rFnvCB = (Player.AuxVarGetRef "FNVLink_chatcb")',
            'ShowTextInputMenu rFnvCB 1000 420 "Chat with Claude - type your reply, Enter to send:"',
            'InjectUIXML "TextEditMenu/NOGLOW_BRANCH" "FNVLink\\chat_inject.xml"',
            'SetUIFloatAlt "TextEditMenu/NOGLOW_BRANCH/TEM_TextInputBox/y" 235',
            'SetUIFloatAlt "TextEditMenu/NOGLOW_BRANCH/TEM_TextInputBox/height" 130',
            'array_var aFnvLg = (ReadFromJSON "FNVLink/chatlog.json" "" 0)',
            'array_var aFnvL = Ar_Construct "stringmap"',
            'aFnvL["role"] = "claude"',
            'aFnvL["text"] = "%s"' % body,
            'Ar_Append aFnvLg, aFnvL',
            'WriteToJSON aFnvLg ("FNVLink/chatlog.json") "" 0 0 1',
            'RunBatchScript "FNVLink/chatlog_render.txt"',
            'SetTextInputExtendedProps 0 0 1 0 2',
        ])
        return _run_script(bridge, script, label="chat reply: %s" % body[:32])
    return handler


_HEX_FORM = {"type": "string",
             "description": "Hex FormID as it appears in the console (e.g. 0000000F "
                            "for caps, or modindex-prefixed like 1A0034C2). Editor IDs "
                            "are NOT accepted — RunBatchScript needs FormIDs."}

_AV_NAME = {"type": "string",
            "description": "Actor Value name (letters/digits), e.g. Health, Hunger, "
                           "Dehydration, SleepDeprevation (note the engine misspelling), "
                           "RadiationRads, Strength, Luck, Guns, Sneak."}


def build_registry(bridge: Bridge | None) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "fnv_link_status",
        "Report whether the YesMan AI Live Link is up and whether a running game is "
        "currently connected (based on the freshness of the in-game heartbeat). "
        "Use this first to confirm the link before issuing commands.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _make_status_handler(bridge),
    )
    registry.register(
        "fnv_get_player_state",
        "Return the latest snapshot the running game wrote: player position, "
        "health, and world state. Reports connected=false with details if the "
        "game isn't running or the heartbeat is stale.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _make_player_state_handler(bridge),
    )
    registry.register(
        "fnv_poll_events",
        "Return and CONSUME in-game events the game has pushed since the last poll: a "
        "list of {seq, type, name, form, gamehour}. Each event is delivered exactly once "
        "(the queue is drained on read), with a monotonic relay-assigned seq. Types: "
        "'death' (an actor the player killed), 'murder' (an unprovoked kill — also emits a "
        "'death'); 'combat' / 'combat_end' (a fight started/ended; name = the enemy); "
        "'pickup' / 'sell' / 'equip' / 'unequip' (item events; name = the item); 'read_book' "
        "(the player read a book/note; name = the book; ShowOff); 'steal' (the player stole an "
        "item; name = the "
        "item; ITR); 'reload' (the player reloaded a weapon; name = the weapon; JIP); "
        "'cell_enter' "
        "(player entered a new, differently-named cell; name = the cell — exterior 'Mojave "
        "Wasteland' grid spam is deduped out); 'discover' (a location "
        "found; name = the place); 'fast_travel' (name = destination); 'quest_complete' / "
        "'quest_fail' (a quest finished/failed; name = the quest; needs JohnnyGuitar NVSE); "
        "'perk' (perk gained; name = the perk; JohnnyGuitar); 'challenge_complete' (a Challenge "
        "was completed; name = the challenge; JohnnyGuitar); 'objective_shown' / "
        "'objective_complete' (a quest "
        "objective was displayed / completed; name = the quest, 'objective' = the objective text; "
        "ShowOff); 'note_added' (a note/holotape was added to the player; name = the note; JIP); "
        "'crippled_limb' (the player's limb was crippled; 'limb' = 0 Head/1 Torso/2 LHand/3 RHand/"
        "4 LLeg/5 RLeg/6 Brain; JIP); 'misc_stat' (a tracked PC stat changed; 'stat' = the name "
        "e.g. 'Speech Successes'/'Speech Failures'/'Computers Hacked'/'Locks Picked'/'Pockets "
        "Picked'/'Items Crafted'/'Weapon Modifications'/'Times Addicted'/gambling/etc., 'delta' = "
        "the change, 'value' = the new total; ShowOff; per-kill counters are excluded); 'aid_use' "
        "(any ingestible/ALCH "
        "was used — meds, chems, food, drink, poisons, magazines; JIP); 'sleep_wait' (the "
        "player slept or waited; no name/form; JohnnyGuitar); 'holster' / 'unholster' (player "
        "sheathed/drew a weapon; name = the weapon; ShowOff); 'vats_enter' (VATS playback began; "
        "name = the target, may be empty) / 'vats_leave' (VATS ended; has a 'kills' count, no "
        "name) (ITR); 'killcam_start' / 'killcam_end' (a killcam ran; name = the target; ITR); "
        "'weapon_jam' (the player's weapon jammed; name = the weapon; ITR); 'casino_ban' (the "
        "player was banned from a casino; name = the casino; ITR); 'save' / 'load' "
        "(session boundaries; no name/form); 'exit_to_main_menu' / 'exit_game' (the player left "
        "the loaded game to the title screen / to desktop; no name/form — lets you notice "
        "the session ended); 'dialogue' (an NPC said a line TO the player in a conversation; "
        "name = the speaking NPC, 'text' = what they said - captured from the on-screen subtitle, "
        "so the player must have dialogue subtitles enabled; lets you follow what NPCs tell the "
        "player). Use to react to world events without polling state.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _make_poll_events_handler(bridge),
    )
    registry.register(
        "fnv_poll_chat",
        "Return and CONSUME chat messages the PLAYER typed to you in-game since the last poll: "
        "a list of {seq, text, gamehour}. The player opens an in-game text box with the chat "
        "hotkey (default '\\' Backslash), types free-form prose, and presses Enter; that message "
        "lands here. Each message is delivered exactly once (the queue is drained on read), with "
        "a monotonic relay-assigned seq. Poll this to see what the player is saying, then reply "
        "with fnv_chat_reply (shows your reply in the same in-game box) or act on their request "
        "with the command tools. This is the player->Claude half of the two-way chat; "
        "fnv_chat_reply / fnv_message are the Claude->player half.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _make_poll_chat_handler(bridge),
    )
    registry.register(
        "fnv_chat_reply",
        "Reply to the player IN-GAME by (re)opening the chat box. Your line is appended to a "
        "persistent, SCROLLABLE conversation log shown at the top of the box (the whole "
        "back-and-forth, 'You:'/'Claude:' prefixed, survives reloads; the player can mouse-wheel "
        "or use the arrows to scroll back through history). It opens scrolled to your newest line. "
        "The input field below stays EMPTY, so the player just types their reply and presses "
        "OK/Enter — a true back-and-forth in one window. The box also has Clear (wipe the field), "
        "Clear Log (erase the whole conversation history), and Close (dismiss without sending) "
        "buttons. Use this to answer a message from "
        "fnv_poll_chat, or to start a conversation unprompted. Requires the chat script "
        "(ln_FNVLinkChat.txt) loaded in the running game. Plain text, ~400 chars per call (it "
        "wraps + scrolls; split longer replies across calls; double-quotes become apostrophes, "
        "newlines collapse to spaces). For a brief corner notification instead, use fnv_message.",
        {"type": "object",
         "properties": {"text": {"type": "string",
                                 "description": "Your reply to the player (appended to the "
                                                "in-game scrollable conversation log)."}},
         "required": ["text"], "additionalProperties": False},
        _make_chat_reply_handler(bridge),
    )
    registry.register(
        "fnv_run_script",
        "Run a GECK script snippet in the RUNNING game (via JIP RunBatchScript). "
        "This is GECK script, NOT console syntax: use script functions and quote "
        "FormIDs, e.g. 'player.AddItem \"0000000F\" 100' or 'set GameHour to 3'. "
        "Console-only toggles (tgm, tcl) are not script functions and won't work. "
        "Returns ok=true only if the snippet compiled and ran cleanly in-game.",
        {"type": "object",
         "properties": {"script": {"type": "string",
                                   "description": "GECK script source (result-script "
                                                  "syntax; multiple lines allowed)."}},
         "required": ["script"], "additionalProperties": False},
        _make_run_script_handler(bridge),
    )
    registry.register(
        "fnv_additem",
        "Give the player an item by FormID. Wraps RunBatchScript with "
        "'player.AddItem \"<form>\" <count>'.",
        {"type": "object",
         "properties": {"form": _HEX_FORM,
                        "count": {"type": "integer", "minimum": 1, "default": 1}},
         "required": ["form"], "additionalProperties": False},
        _make_additem_handler(bridge),
    )
    registry.register(
        "fnv_setstage",
        "Set a quest's stage. Wraps 'SetStage \"<quest>\" <stage>'.",
        {"type": "object",
         "properties": {"quest": _HEX_FORM,
                        "stage": {"type": "integer", "minimum": 0}},
         "required": ["quest", "stage"], "additionalProperties": False},
        _make_setstage_handler(bridge),
    )
    registry.register(
        "fnv_set_time",
        "Set the in-game time of day (0–24 hour). Wraps 'set GameHour to <hour>'. "
        "Effect is observable in the next fnv_get_player_state (gamehour field).",
        {"type": "object",
         "properties": {"hour": {"type": "number", "minimum": 0, "maximum": 24}},
         "required": ["hour"], "additionalProperties": False},
        _make_set_time_handler(bridge),
    )
    registry.register(
        "fnv_set_weather",
        "Force a weather by FormID. Wraps 'ForceWeather \"<weather>\"'.",
        {"type": "object",
         "properties": {"weather": _HEX_FORM},
         "required": ["weather"], "additionalProperties": False},
        _make_set_weather_handler(bridge),
    )
    registry.register(
        "fnv_console",
        "Run ANY in-game console command (the holy-grail catch-all): exactly what the player "
        "would type in the ~ console, including console-only toggles like tgm/tcl/tfc/tmm that "
        "aren't script functions. Wraps JIP 'Console \"<command>\"'. Examples: 'tgm' (god mode), "
        "'tcl' (no-clip), 'player.additem 0000000f 1000', 'coc GoodspringsCell'. Common short "
        "aliases (tgm/tcl/tdetect/tai/tcai/tmm/tm/tfc/tfow/coc/cow…) are auto-translated to their "
        "full command names, which is what Console actually needs. Toggles require JIP PP LN "
        "57.54+ (the maintained JIP fork that fixes Console); plain JIP LN 57.30 runs command-"
        "style calls but not toggles. Single line; inner double-quotes become apostrophes. NOTE: "
        "the command executes but its console TEXT output is NOT captured — read results via "
        "fnv_get_player_state, not here. 'ok' only means the batch ran, not the command's own "
        "success.",
        {"type": "object",
         "properties": {"command": {"type": "string",
                                    "description": "Console command line, e.g. 'tgm' or "
                                                   "'player.additem 0000000f 100'."}},
         "required": ["command"], "additionalProperties": False},
        _make_console_handler(bridge),
    )
    registry.register(
        "fnv_message",
        "Show an on-screen message to the player (corner notification). Use to "
        "communicate with the player inside the game. Wraps 'MessageEx \"<text>\"'. "
        "Plain text only (quotes become apostrophes; single line; ~200 chars).",
        {"type": "object",
         "properties": {"text": {"type": "string", "description": "Message to display."}},
         "required": ["text"], "additionalProperties": False},
        _make_message_handler(bridge),
    )
    registry.register(
        "fnv_moveto",
        "Teleport the player to a placed reference by FormID (e.g. an NPC or marker). "
        "Wraps 'Player.MoveTo \"<ref>\"'. The FormID must be a reference, not a base form.",
        {"type": "object",
         "properties": {"ref": _HEX_FORM},
         "required": ["ref"], "additionalProperties": False},
        _make_moveto_handler(bridge),
    )
    registry.register(
        "fnv_placeatme",
        "Spawn a copy of a base form (item, creature, NPC) next to the player. "
        "Wraps 'Player.PlaceAtMe \"<form>\" <count>'. Powerful — spawns into the world.",
        {"type": "object",
         "properties": {"form": _HEX_FORM,
                        "count": {"type": "integer", "minimum": 1, "default": 1}},
         "required": ["form"], "additionalProperties": False},
        _make_placeatme_handler(bridge),
    )
    registry.register(
        "fnv_removeitem",
        "Remove items from the player's inventory by FormID. "
        "Wraps 'player.RemoveItem \"<form>\" <count>'.",
        {"type": "object",
         "properties": {"form": _HEX_FORM,
                        "count": {"type": "integer", "minimum": 1, "default": 1}},
         "required": ["form"], "additionalProperties": False},
        _make_removeitem_handler(bridge),
    )
    registry.register(
        "fnv_equipitem",
        "Equip an item the player owns by FormID. Wraps 'player.EquipItem \"<form>\"'.",
        {"type": "object",
         "properties": {"form": _HEX_FORM},
         "required": ["form"], "additionalProperties": False},
        _make_equipitem_handler(bridge),
    )
    registry.register(
        "fnv_setav",
        "Set an Actor Value to a value (permanent). Wraps 'Player.ForceActorValue <av> "
        "<value>'. Good for skills/SPECIAL/survival (e.g. av=Hunger value=0) and rads "
        "(av=RadiationRads value=0). Note: Caps is an item, not an AV (use fnv_additem "
        "0000000F). For restoring current Health damage, ModActorValue may behave better.",
        {"type": "object",
         "properties": {"av": _AV_NAME, "value": {"type": "number"}},
         "required": ["av", "value"], "additionalProperties": False},
        _make_setav_handler(bridge),
    )
    registry.register(
        "fnv_modav",
        "Add a delta to an Actor Value. Wraps 'Player.ModActorValue <av> <value>' "
        "(value may be negative). E.g. av=RadiationRads value=-500 to cure rads.",
        {"type": "object",
         "properties": {"av": _AV_NAME, "value": {"type": "number"}},
         "required": ["av", "value"], "additionalProperties": False},
        _make_modav_handler(bridge),
    )
    return registry


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fnv_link_server", description=SERVER_NAME)
    parser.add_argument(
        "--bridge",
        default=os.environ.get(BRIDGE_ENV_VAR),
        help="Shared bridge directory the in-game script polls "
             f"(or set {BRIDGE_ENV_VAR}).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s fnv-link %(levelname)s: %(message)s",
    )

    bridge = Bridge(os.path.abspath(args.bridge)) if args.bridge else None
    if bridge is not None:
        try:
            bridge.seed()
        except OSError as e:
            log.warning("could not seed bridge dir %s: %s", bridge.dir, e)
    registry = build_registry(bridge)
    server = StdioServer(registry, SERVER_NAME, SERVER_VERSION)
    server.serve_forever()


if __name__ == "__main__":
    main()

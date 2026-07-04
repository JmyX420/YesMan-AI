# fnv_link_server — file bridge
#
# YesMan AI Live Link (c) 2026 JmyX. MIT. See LICENSE and NOTICE.md.
#
# The transport between the Python relay and the running game is a set of JSON
# files in a shared directory. The relay operates on the REAL filesystem path it
# is handed (--bridge); the in-game JIP LN Script Runner script reads/writes the
# same files relative to the game root (usvfs may redirect those — see PORT_PLAN).
#
# Robustness requirements this layer must satisfy, because the two writers do not
# share a lock:
#   * The relay writes cmd.json ATOMICALLY (temp file + os.replace) so the game
#     never reads a half-written command.
#   * The game's WriteToJSON truncates-in-place (not atomic from our side), so the
#     relay's reads are PARTIAL-TOLERANT: a JSON decode error is retried briefly,
#     then treated as "not ready" rather than crashing.
#   * Commands are id-matched: every cmd.json carries a strictly increasing id and
#     the game echoes it in reply.json, so a stale reply is never mistaken for ours.

import glob
import json
import os
import time

from .config import (
    CMD_FILE,
    REPLY_FILE,
    STATE_FILE,
    EVENTS_FILE,
    CHAT_FILE,
    CHAT_INJECT_FILE,
    CHATLOG_FILE,
    CHAT_RECV_FILE,
    CHATLOG_RENDER_FILE,
    CHAT_REOPEN_FILE,
    DISPATCH_FILE,
    EVT_DEATH_FILE,
    EVT_MURDER_FILE,
    EVT_COMBAT_FILE,
    EVT_PICKUP_FILE,
    EVT_SELL_FILE,
    EVT_EQUIP_FILE,
    EVT_UNEQUIP_FILE,
    EVT_CELLENTER_FILE,
    EVT_READBOOK_FILE,
    EVT_STEAL_FILE,
    EVT_RELOAD_FILE,
    EVT_SLEEPWAIT_FILE,
    EVT_HOLSTER_FILE,
    EVT_UNHOLSTER_FILE,
    EVT_VATSENTER_FILE,
    EVT_VATSLEAVE_FILE,
    EVT_KILLCAMSTART_FILE,
    EVT_KILLCAMEND_FILE,
    EVT_WEAPONJAM_FILE,
    EVT_CASINOBAN_FILE,
    EVT_COMBATEND_FILE,
    EVT_DISCOVER_FILE,
    EVT_SAVE_FILE,
    EVT_LOAD_FILE,
    EVT_EXITMENU_FILE,
    EVT_EXITGAME_FILE,
    EVT_CHALLENGE_FILE,
    EVT_OBJSHOWN_FILE,
    EVT_OBJDONE_FILE,
    EVT_NOTEADDED_FILE,
    EVT_CRIPPLED_FILE,
    EVT_MISCSTAT_FILE,
    EVT_QUESTDONE_FILE,
    EVT_QUESTFAIL_FILE,
    EVT_FASTTRAVEL_FILE,
    EVT_PERK_FILE,
    EVT_AIDUSE_FILE,
    STATE_WRITE_FILE,
    DIALOGUE_POLL_FILE,
    DIALOGUE_LAST_FILE,
    BRIDGE_SUBFOLDER,
    COMMAND_TIMEOUT_SECONDS,
    HEARTBEAT_STALE_SECONDS,
    PAUSED_GRACE_SECONDS,
)

# Enriched heartbeat snapshot (GECK source), materialised into the bridge dir and run every
# tick by the heartbeat callback (ln_FNVLink). Kept in a batch, not inline in the callback's
# lambda, because the full field set exceeds GECK's 512-char parenthesis limit. All fields
# verified in-game (Phase 5 enrichment). Reads live player/world state each call.
STATE_SCRIPT = "\r\n".join([
    'int iTick = (Player.AuxVarGetFlt "FNVLink_tick") + 1',
    'Player.AuxVarSetFlt "FNVLink_tick" iTick',
    'ref rFnvCell = (Player.GetParentCell)',
    'ref rFnvWeap = (Player.GetEquippedObject 5)',
    'ref rFnvQuest = (GetActiveQuest)',  # player's tracked quest (0 if none); JIP, FNV-only
    'array_var aFnvObj = (GetActiveObjectives)',  # array of active objective INDICES (e.g. [10])
    'array_var aS = Ar_Construct "stringmap"',
    'aS["alive"] = 1',
    'aS["tick"] = (iTick)',
    'aS["px"] = (Player.GetPos X)',
    'aS["py"] = (Player.GetPos Y)',
    'aS["pz"] = (Player.GetPos Z)',
    'aS["health"] = (Player.GetAV Health)',
    'aS["health_max"] = (Player.GetBaseAV Health)',  # GetBaseAV is expr-aware; GetBaseActorValue is NOT
    'aS["gamehour"] = (GameHour)',
    'aS["cell"] = (LNGetName rFnvCell)',
    'aS["caps"] = (Player.GetItemCount "0000000F")',
    'aS["level"] = (Player.GetLevel)',
    'aS["weapon"] = (LNGetName rFnvWeap)',
    'aS["weapon_form"] = (GetFormIDString rFnvWeap)',
    'aS["ammo"] = (Player.GetCurrentAmmoRounds)',
    'aS["rads"] = (Player.GetAV RadiationRads)',
    'aS["karma"] = (Player.GetAV Karma)',
    'aS["food"] = (Player.GetAV Hunger)',          # FNV Hardcore: food need
    'aS["h2o"] = (Player.GetAV Dehydration)',       # FNV Hardcore: water need
    'aS["sleep"] = (Player.GetAV SleepDeprevation)',  # NOTE engine typo: SleepDeprevation
    # Active quest: name + FormID + current stage (arg-form funcs accept the quest ref var).
    # Objective TEXT is omitted: GetCurrentObjective is a dot-call requiring a reference, and
    # a quest is a base form — it errors on a ref var. (Future: arg-form objective lookup.)
    'aS["quest"] = (LNGetName rFnvQuest)',
    'aS["quest_form"] = (GetFormIDString rFnvQuest)',
    'aS["quest_stage"] = (GetStage rFnvQuest)',
    # Current objective TEXT: GetObjectiveText wants the objective INDEX (from
    # GetActiveObjectives[0]), NOT the objectiveID from GetCurrentObjective (95 vs 10 — passing
    # the ID returns ""). Default empty, fill only when an active objective exists.
    'aS["quest_objective"] = ""',
    'if eval ((Ar_Size aFnvObj) > 0)',
    '    aS["quest_objective"] = (GetObjectiveText rFnvQuest (aFnvObj[0]))',
    'endif',
    'WriteToJSON aS ("FNVLink/state.json") "" 0 0 1',
    'aS = Ar_Null',
    '',
])

# NPC-dialogue capture batch (GECK source), materialised into the bridge dir and run every tick by a
# main-loop callback (ln_FNVLinkEvtDialog). POLLING approach — NOT the JG dialogue EVENT hooks
# (SetOnNPCResponseEventHandler / SetOnGeneralSubtitleEventHandler), which compile + register but
# never fire in MTUI / heavily-modded-UI load orders: the vanilla dialogue/subtitle functions JG
# detours are bypassed by the UI overhaul's own subtitle rendering (verified live — subtitles show on
# screen, perk events fire, yet neither JG dialogue hook dispatches; not a togglable conflict).
# Instead we read the on-screen subtitle directly from the DialogMenu UI tiles (the VANILLA tiles
# DM_SpeakerText = the spoken line, DM_SpeakerNameLabel = the speaker — these are base-game tile
# names, NOT MTUI-specific; confirmed by extracting the vanilla menu from Fallout - Misc.bsa, and
# MTUI/VUI+/most overhauls keep them), via a candidate-path chain (below) so it spans UIs. Immune
# to the hook bypass. Logic: only in the DialogMenu (GetActiveMenuMode 1009); read the line via the
# first candidate path that has text; if non-empty AND
# different from the last captured line (dedupe via dlg_last.json — the subtitle persists in the tile
# for several ticks while shown, so without this it would re-emit every tick); record the new line +
# speaker as a {type:"dialogue"} event. ALL VERIFIED LIVE before deploy (captured Easy Pete's line,
# second identical tick correctly emitted nothing). GECK notes: a string-returning func (GetUIString)
# must go through `let sv := (...)` into a string_var, NOT a direct map assign (a direct assign stores
# the function NAME — gotcha); string compares need `if eval (sA != sB)`; map value -> string_var via
# `let s := map["k"]`; nested ifs (not &&) for compile safety. GetUIString (NOT GetUIStringAlt, which
# returns its own name here) reads a tile's string trait.
DIALOGUE_POLL_SCRIPT = "\r\n".join([
    'if eval ((GetActiveMenuMode) == 1009)',
    # UI-agnostic capture: try a list of candidate (speaker-name-path, response-text-path) pairs in
    # order; the first pair whose response tile has non-empty text wins. Pair 0 is the VANILLA
    # DialogMenu structure (verified by extracting menus/dialog/dialog_menu.xml from the base game's
    # Fallout - Misc.bsa: NOGLOW_BRANCH > DM_SpeakerText id 2 = the line, DM_SpeakerNameLabel id 1 =
    # the speaker). MTUI, VUI+ and the great majority of UI overhauls are edits of the vanilla menu
    # that KEEP these tile names, so this one pair covers vanilla + the common UIs. To support a UI
    # that RENAMES the dialogue subtitle tiles, add another Ar_Append pair below (name path, then
    # text path) — no other change needed. On an unknown UI the loop simply finds nothing and emits
    # no event (harmless no-op).
    'array_var aNPaths = Ar_Construct "array"',
    'array_var aTPaths = Ar_Construct "array"',
    'Ar_Append aNPaths, "DialogMenu/NOGLOW_BRANCH/DM_SpeakerNameLabel/string"',
    'Ar_Append aTPaths, "DialogMenu/NOGLOW_BRANCH/DM_SpeakerText/string"',
    # --- add more UI candidates here, e.g.:
    # 'Ar_Append aNPaths, "DialogMenu/.../<speaker tile>/string"',
    # 'Ar_Append aTPaths, "DialogMenu/.../<response tile>/string"',
    'string_var sCur',
    'string_var sName',
    'int iFnvI',
    'let iFnvI := 0',
    'while (iFnvI < (Ar_Size aTPaths))',
    '    let sCur := (GetUIString (aTPaths[iFnvI]))',
    '    if eval (sCur != "")',
    '        let sName := (GetUIString (aNPaths[iFnvI]))',
    '        let iFnvI := (Ar_Size aTPaths)',
    '    else',
    '        let iFnvI := iFnvI + 1',
    '    endif',
    'loop',
    'if eval (sCur != "")',
    '    array_var aL = (ReadFromJSON "FNVLink/dlg_last.json" "" 0)',
    '    string_var sLast',
    '    let sLast := aL["t"]',
    '    if eval (sCur != sLast)',
    '        array_var aNew = Ar_Construct "stringmap"',
    '        aNew["t"] = sCur',
    '        WriteToJSON aNew ("FNVLink/dlg_last.json") "" 0 0 1',
    '        array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
    '        array_var aE = Ar_Construct "stringmap"',
    '        aE["seq"] = ((Ar_Size aEv) + 1)',
    '        aE["type"] = "dialogue"',
    '        aE["gamehour"] = (GameHour)',
    '        aE["name"] = sName',
    '        aE["text"] = sCur',
    '        Ar_Append aEv, aE',
    '        WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
    '    endif',
    'endif',
    'endif',
    '',
])

# OnDeath event-append batch (GECK source), materialised into the bridge dir by the relay
# and run by the in-game OnDeath handler. Append-only: read events.json (a JSON array →
# NVSE Array), bump a session seq counter, append {seq,type,gamehour}, write back. Verified
# in-game (Phase 5). Kept in a batch (not the handler lambda) for the 512-char reason.
EVENT_DEATH_SCRIPT = "\r\n".join([
    # The OnDeath handler stashes the killed actor in the FNVLink_evactor aux ref before
    # running this. We read it back and enrich the event with the actor's full name and
    # FormID. NOTE: 'rK' is a reserved command name and will not compile as a var — use a
    # distinctive name like rKilledRef. GetFormIDString requires a ref VARIABLE (not a
    # literal), which rKilledRef satisfies. Verified in-game (Phase 5 enrichment).
    'ref rKilledRef = (Player.AuxVarGetRef "FNVLink_evactor")',
    'array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
    # seq is derived from the events array length, NOT a saved AuxVar counter: AuxVars revert
    # on save-reload while events.json (on disk) keeps growing, which caused seq collisions
    # (two seq:1 entries) and broke the relay's cursor. Array length is monotonic with the file.
    'array_var aE = Ar_Construct "stringmap"',
    'aE["seq"] = ((Ar_Size aEv) + 1)',
    'aE["type"] = "death"',
    'aE["gamehour"] = (GameHour)',
    'aE["name"] = (LNGetName rKilledRef)',
    'aE["form"] = (GetFormIDString rKilledRef)',
    'Ar_Append aEv, aE',
    'WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
    '',
])

# OnMurder reuses the exact death-append logic with a different event type label. (A murder
# also fires OnDeath, so a murdered actor yields two events — type "death" and type "murder";
# the latter flags it as a karma/reputation-relevant kill.)
EVENT_MURDER_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"murder"')
# OnStartCombat: the handler stashes the OTHER combatant (the enemy) in FNVLink_evactor, so the
# same name+FormID enrichment applies — just a different type label.
EVENT_COMBAT_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"combat"')

# Item events (OnAdd/OnSell/OnActorEquip): the handler stashes the ITEM (a form) in
# FNVLink_evactor; the same name+FormID read applies, so the event's name/form describe the
# item. Same enrichment script, different type label.
EVENT_PICKUP_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"pickup"')
EVENT_SELL_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"sell"')
EVENT_EQUIP_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"equip"')
# OnActorUnequip mirrors OnActorEquip exactly — the handler stashes the unequipped item in
# FNVLink_evactor, so the same name+FormID enrichment applies, just a different type label.
EVENT_UNEQUIP_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"unequip"')
# ShowOff:OnReadBook — calling ref is always the player; the handler stashes the book BaseForm.
# Same enrichment (name = book, form = book FormID). Catches BOOK-type items (skill books,
# notes) that aid_use/ALCH can't.
EVENT_READBOOK_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"read_book"')
# ITR:OnSteal (filtered first::playerref = player is the thief) — the handler stashes the stolen
# item BaseForm (arg3). Name = the item taken.
EVENT_STEAL_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"steal"')
# OnReloadWeapon (JIP, guarded GetSelf==Player) — the handler stashes the reloaded weapon
# BaseForm. Name = the weapon.
EVENT_RELOAD_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"reload"')
# Weapon holster/unholster (ShowOff, guarded GetSelf==Player) — handler stashes the weapon.
EVENT_HOLSTER_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"holster"')
EVENT_UNHOLSTER_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"unholster"')
# VATS / killcam / weapon-jam / casino-ban (ITR). Subject-ref events stash a ref in FNVLink_evactor
# (vats_enter = the VATS target; killcam_start/end = the killcam target; weapon_jam = the jammed
# weapon (arg2, filtered to the player's actor); casino_ban = the TESCasino). 0-refs come through
# with empty name/form, which is fine. vats_leave is the odd one (an int kill-count, no ref) and
# gets a custom batch below.
EVENT_VATSENTER_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"vats_enter"')
EVENT_KILLCAMSTART_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"killcam_start"')
EVENT_KILLCAMEND_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"killcam_end"')
EVENT_WEAPONJAM_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"weapon_jam"')
EVENT_CASINOBAN_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"casino_ban"')
# vats_leave: ITR:OnVATSLeave passes an INT (kills recorded in VATS), not a ref. The handler
# stashes it via AuxVarSetFlt "FNVLink_evnum"; this batch reads it back and records a 'kills' field
# (no name/form). AuxVarGetFlt is proven (heartbeat tick).
EVENT_VATSLEAVE_SCRIPT = "\r\n".join([
    'array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
    'array_var aE = Ar_Construct "stringmap"',
    'aE["seq"] = ((Ar_Size aEv) + 1)',
    'aE["type"] = "vats_leave"',
    'aE["gamehour"] = (GameHour)',
    'aE["kills"] = (Player.AuxVarGetFlt "FNVLink_evnum")',
    'Ar_Append aEv, aE',
    'WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
    '',
])

# OnCombatEnd: the handler stashes the OTHER combatant in FNVLink_evactor (same as combat
# start), so the name+FormID enrichment applies — a "combat_end" closes the arc a "combat"
# opened, letting Claude track when a fight is over.
EVENT_COMBATEND_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"combat_end"')

# Place events (discover / fast_travel): the handler stashes a MAP MARKER ref. A map marker's
# display name ("Goodsprings") lives on the REFERENCE's extra data, NOT the base form, so
# LNGetName returns "" for it (confirmed live — discover came through with an empty name).
# GetMapMarkerName (JIP, orig. Lutana) reads the reference's marker name. We try it first and
# fall back to LNGetName for the rare ref that isn't a named marker. Dot-call is valid here:
# the stashed value is a placed reference, not a base form (cf. the quest base-form gotcha).
def _place_event_script(type_label: str) -> str:
    return "\r\n".join([
        'ref rFnvMk = (Player.AuxVarGetRef "FNVLink_evactor")',
        'string_var sFnvPlace = (rFnvMk.GetMapMarkerName)',
        'if eval (sFnvPlace == "")',
        '    let sFnvPlace := (LNGetName rFnvMk)',
        'endif',
        'array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
        'array_var aE = Ar_Construct "stringmap"',
        'aE["seq"] = ((Ar_Size aEv) + 1)',
        'aE["type"] = "%s"' % type_label,
        'aE["gamehour"] = (GameHour)',
        'aE["name"] = (sFnvPlace)',
        'aE["form"] = (GetFormIDString rFnvMk)',
        'Ar_Append aEv, aE',
        'WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
        '',
    ])


EVENT_DISCOVER_SCRIPT = _place_event_script("discover")

# JohnnyGuitar quest events: the handler stashes the QUEST form (passed as the single handler
# arg) in FNVLink_evactor; LNGetName/GetFormIDString then name the quest. (quest_start was
# dropped — unfiltered "any quest started" floods on framework quests like MCM; complete/fail
# are deliberate, rare milestones.)
EVENT_QUESTDONE_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"quest_complete"')
EVENT_QUESTFAIL_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"quest_fail"')
# JohnnyGuitar OnChallengeComplete: handler stashes the completed Challenge (CHAL form); same
# name+FormID enrichment names the challenge. Filter omitted at registration = any challenge.
EVENT_CHALLENGE_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"challenge_complete"')

# OnNoteAdded (JIP, player-inherent): handler stashes the Note form; name/form = the note.
EVENT_NOTEADDED_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"note_added"')

# Objective events (ShowOff): handler stashes the QUEST (ref) in FNVLink_evactor and the
# objective NUMBER (int) in FNVLink_evnum. We record the quest name/form AND resolve the
# objective TEXT via GetObjectiveText(quest, number) — that's the useful "what's the goal" bit.
# If the number isn't the index GetObjectiveText wants, the text is "" and the raw number remains.
def _objective_event_script(type_label):
    return "\r\n".join([
        'ref rFnvObjQ = (Player.AuxVarGetRef "FNVLink_evactor")',
        'int iFnvObjN',
        'set iFnvObjN to (Player.AuxVarGetFlt "FNVLink_evnum")',
        'string_var sFnvObjT',
        'let sFnvObjT := (GetObjectiveText rFnvObjQ iFnvObjN)',
        'array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
        'array_var aE = Ar_Construct "stringmap"',
        'aE["seq"] = ((Ar_Size aEv) + 1)',
        'aE["type"] = "%s"' % type_label,
        'aE["gamehour"] = (GameHour)',
        'aE["name"] = (LNGetName rFnvObjQ)',
        'aE["form"] = (GetFormIDString rFnvObjQ)',
        'aE["objective"] = (sFnvObjT)',
        'aE["obj_num"] = iFnvObjN',
        'Ar_Append aEv, aE',
        'WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
        '',
    ])


EVENT_OBJSHOWN_SCRIPT = _objective_event_script("objective_shown")
EVENT_OBJDONE_SCRIPT = _objective_event_script("objective_complete")

# OnCrippledLimb (JIP, filtered to PlayerRef): handler stashes the limb index (int) in
# FNVLink_evnum. limb: 0 Head, 1 Torso, 2 LeftHand, 3 RightHand, 4 LeftLeg, 5 RightLeg, 6 Brain.
EVENT_CRIPPLED_SCRIPT = "\r\n".join([
    'array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
    'array_var aE = Ar_Construct "stringmap"',
    'aE["seq"] = ((Ar_Size aEv) + 1)',
    'aE["type"] = "crippled_limb"',
    'aE["gamehour"] = (GameHour)',
    'aE["limb"] = (Player.AuxVarGetFlt "FNVLink_evnum")',
    'Ar_Append aEv, aE',
    'WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
    '',
])

# misc_stat (ShowOff:OnPCMiscStatChange): the handler (after dropping the per-kill flood codes
# 2/3/35) stashes the stat code / delta / new value into aux vars; this batch records them raw.
# The relay maps stat_code -> a readable name (MISC_STAT_NAMES) when the event is drained, so the
# GECK side stays a trivial recorder (no 43-way if-chain in-game).
EVENT_MISCSTAT_SCRIPT = "\r\n".join([
    'int iFnvStatCode',
    'set iFnvStatCode to (Player.AuxVarGetFlt "FNVLink_evstat")',
    'int iFnvStatDelta',
    'set iFnvStatDelta to (Player.AuxVarGetFlt "FNVLink_evdelta")',
    'int iFnvStatVal',
    'set iFnvStatVal to (Player.AuxVarGetFlt "FNVLink_evnum")',
    'array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
    'array_var aE = Ar_Construct "stringmap"',
    'aE["seq"] = ((Ar_Size aEv) + 1)',
    'aE["type"] = "misc_stat"',
    'aE["gamehour"] = (GameHour)',
    'aE["stat_code"] = iFnvStatCode',
    'aE["delta"] = iFnvStatDelta',
    'aE["value"] = iFnvStatVal',
    'Ar_Append aEv, aE',
    'WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
    '',
])

# Vanilla FNV PC-misc-stat code -> name (geckwiki "Misc Stat Codes"). The relay adds a "stat"
# field to each misc_stat event from this map. (Codes 2/3/35 — People/Creatures/Total Killed —
# are filtered out in-game and won't appear.)
MISC_STAT_NAMES = {
    0: "Quests Completed", 1: "Locations Discovered", 2: "People Killed",
    3: "Creatures Killed", 4: "Locks Picked", 5: "Computers Hacked", 6: "Stimpaks Taken",
    7: "Rad-X Taken", 8: "RadAway Taken", 9: "Chems Taken", 10: "Times Addicted",
    11: "Mines Disarmed", 12: "Speech Successes", 13: "Pockets Picked", 14: "Pants Exploded",
    15: "Books Read", 16: "Health From Stimpaks", 17: "Weapons Created", 18: "Health From Food",
    19: "Water Consumed", 20: "Sandman Kills", 21: "Paralyzing Punches", 22: "Robots Disabled",
    23: "Times Slept", 24: "Corpses Eaten", 25: "Mysterious Stranger Visits",
    26: "Doctor Bags Used", 27: "Challenges Completed", 28: "Miss Fortunate Occurrences",
    29: "Disintegrations", 30: "Have Limbs Crippled", 31: "Speech Failures", 32: "Items Crafted",
    33: "Weapon Modifications", 34: "Items Repaired", 35: "Total Things Killed",
    36: "Dismembered Limbs", 37: "Caravan Games Won", 38: "Caravan Games Lost",
    39: "Barter Amount Traded", 40: "Roulette Games Played", 41: "Blackjack Games Played",
    42: "Slots Games Played",
}

# (level_up was DROPPED — JohnnyGuitar OnProcessLevelChange registered cleanly but never
# dispatched on a real level-up, and there's no other clean level-up hook (character level is not
# a vanilla misc stat, so ShowOff:OnPCMiscStatChange can't catch it either). Level awareness is
# already covered by the `level` field in the state snapshot.)

# fast_travel needs one MORE step than discover: the ref the handler is given is often the
# linked teleport/appear marker (where the player materialises), NOT the named map marker —
# so GetMapMarkerName on it returns "" (confirmed live: fast_travel name was empty while
# discover names resolved). Per the SetOnFastTravel wiki, the real marker is the first
# GetLinkedChildren of that ref. So: try the ref directly, else its first linked child, else
# LNGetName. Kept SEPARATE from _place_event_script (discover's working batch) so this richer
# logic — and its GetLinkedChildren / array-element-to-ref step — can't regress discover.
EVENT_FASTTRAVEL_SCRIPT = "\r\n".join([
    'ref rFnvMk = (Player.AuxVarGetRef "FNVLink_evactor")',
    'string_var sFnvPlace = (rFnvMk.GetMapMarkerName)',
    'if eval (sFnvPlace == "")',
    '    array_var aFnvLk = (rFnvMk.GetLinkedChildren)',
    '    if eval ((Ar_Size aFnvLk) > 0)',
    '        ref rFnvReal = (aFnvLk[0])',
    '        let sFnvPlace := (rFnvReal.GetMapMarkerName)',
    '    endif',
    'endif',
    'if eval (sFnvPlace == "")',
    '    let sFnvPlace := (LNGetName rFnvMk)',
    'endif',
    'array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
    'array_var aE = Ar_Construct "stringmap"',
    'aE["seq"] = ((Ar_Size aEv) + 1)',
    'aE["type"] = "fast_travel"',
    'aE["gamehour"] = (GameHour)',
    'aE["name"] = (sFnvPlace)',
    'aE["form"] = (GetFormIDString rFnvMk)',
    'Ar_Append aEv, aE',
    'WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
    '',
])

# aid_use: the consumed ingestible (JIP; no in-game filter = any ALCH/ingestible).
EVENT_AIDUSE_SCRIPT = EVENT_DEATH_SCRIPT.replace('"death"', '"aid_use"')

# cell_enter: the player entered a new cell (JIP OnCellEnter — player-scoped; arg = the cell).
# NAME-DEDUPED: OnCellEnter also fires on every exterior grid-cell crossing, where nearly all
# cells share the name "Mojave Wasteland" — so we only append when the entered cell's NAME
# differs from the last cell's name. We persist the LAST CELL AS A REF (AuxVarSetRef) and compare
# LNGetName(new) vs LNGetName(lastRef). NOTE: do NOT use AuxVarSetStr here — its string value
# needs a `$`-dereference to store a string_var's CONTENT, and `$` does not compile inside
# RunBatchScript (it silently stored the literal var-NAME, making every crossing look "new" and
# leaking the exterior spam — fixed 2026-06-20). AuxVarSetRef needs no `$` and works in a batch.
# Cheap compare first; the O(n) events.json read-modify-write happens ONLY on a new name.
EVENT_CELLENTER_SCRIPT = "\r\n".join([
    'ref rFnvCellArg = (Player.AuxVarGetRef "FNVLink_evactor")',
    'string_var sFnvCellName = (LNGetName rFnvCellArg)',
    'ref rFnvLastCell = (Player.AuxVarGetRef "FNVLink_lastcellref")',
    'string_var sFnvLastName = (LNGetName rFnvLastCell)',
    'if eval (sFnvCellName != sFnvLastName)',
    '    Player.AuxVarSetRef "FNVLink_lastcellref" rFnvCellArg',
    '    array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
    '    array_var aE = Ar_Construct "stringmap"',
    '    aE["seq"] = ((Ar_Size aEv) + 1)',
    '    aE["type"] = "cell_enter"',
    '    aE["gamehour"] = (GameHour)',
    '    aE["name"] = (sFnvCellName)',
    '    aE["form"] = (GetFormIDString rFnvCellArg)',
    '    Ar_Append aEv, aE',
    '    WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
    'endif',
    '',
])

# perk (JohnnyGuitar OnAddPerk) gets a NAME GUARD, not the plain death-pattern: DUST (and
# other mods) re-apply hidden, UNNAMED perks on a timer, which floods an unfiltered handler —
# form 270DDF6E fired ~30x in a minute of testing, all with empty names. Real, player-facing
# perks always have a name, so we only append when LNGetName is non-empty. This kills the
# framework churn while keeping genuine perk gains (Sprint Perk, Holding Breath, level-ups).
EVENT_PERK_SCRIPT = "\r\n".join([
    'ref rFnvPerkRef = (Player.AuxVarGetRef "FNVLink_evactor")',
    'if eval ((LNGetName rFnvPerkRef) != "")',
    '    array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
    '    array_var aE = Ar_Construct "stringmap"',
    '    aE["seq"] = ((Ar_Size aEv) + 1)',
    '    aE["type"] = "perk"',
    '    aE["gamehour"] = (GameHour)',
    '    aE["name"] = (LNGetName rFnvPerkRef)',
    '    aE["form"] = (GetFormIDString rFnvPerkRef)',
    '    Ar_Append aEv, aE',
    '    WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
    'endif',
    '',
])

# Subject-less events (SaveGame/LoadGame): no actor/item/quest to enrich — just record the
# event type, the relay-derived seq, and the in-game hour. Same append-to-events.json logic
# as the subject batches, minus the FNLink_evactor read and the name/form fields. Kept tiny
# and run from the SaveGame/LoadGame handlers via RunBatchScript (512-char reason as usual).
def _bare_event_script(type_label: str) -> str:
    return "\r\n".join([
        'array_var aEv = (ReadFromJSON "FNVLink/events.json" "" 0)',
        'array_var aE = Ar_Construct "stringmap"',
        'aE["seq"] = ((Ar_Size aEv) + 1)',
        'aE["type"] = "%s"' % type_label,
        'aE["gamehour"] = (GameHour)',
        'Ar_Append aEv, aE',
        'WriteToJSON aEv ("FNVLink/events.json") "" 0 0 1',
        '',
    ])


EVENT_SAVE_SCRIPT = _bare_event_script("save")
EVENT_LOAD_SCRIPT = _bare_event_script("load")
# OnSleepWait (JohnnyGuitar): fires when the player sleeps or waits; subject-less (no actor/item)
# — records just the type + gamehour, like save/load.
EVENT_SLEEPWAIT_SCRIPT = _bare_event_script("sleep_wait")
# Session-boundary lifecycle events (xNVSE ExitToMainMenu / ExitGame): also subject-less. They
# fire as the player leaves the loaded game — letting Claude notice the session ended without
# being told. ExitToMainMenu is reliable (the process keeps running at the title screen);
# ExitGame's append may not flush before the process dies on a hard quit (best-effort).
EVENT_EXITMENU_SCRIPT = _bare_event_script("exit_to_main_menu")
EVENT_EXITGAME_SCRIPT = _bare_event_script("exit_game")
# (MainMenu / PostLoadGame were tried and DROPPED — they don't dispatch via SetEventHandler in
# this xNVSE build, and are redundant with exit_to_main_menu + the heartbeat / with `load`.)

# The in-game command dispatcher (GECK script source). The ln_FNVLinkCmd callback runs
# this every tick via RunBatchScript. It MUST live in a batch file, not inline in the
# callback's parens, because GECK caps a parenthesised expression at 512 chars and the
# full handler exceeds that (a longer inline lambda silently fails to compile). Every line
# uses only syntax verified in-game (Phase 4): map value read once as a function arg into
# an AuxVar; the id-guard makes each command run exactly once. Kept here so the relay
# materialises it into the bridge dir — the user installs no extra file.
#
# Each command runs a UNIQUE per-id exec file (cmd.json carries its relative path in "exec").
# This is REQUIRED: RunBatchScript caches its compile by filename, so reusing one exec.txt
# would re-run the first command's cached script forever (confirmed in-game). A fresh
# filename per command forces a fresh compile. RunBatchScript accepts the variable path.
DISPATCH_SCRIPT = "\r\n".join([
    'array_var aCmd = (ReadFromJSON "FNVLink/cmd.json" "" 0)',
    'if eval (Ar_HasKey aCmd, "id")',
    # Guard re-runs on the ON-DISK reply.json id, NOT an AuxVar: AuxVars REVERT on save-load
    # (gotcha 13) while cmd.json persists, so the old AuxVar guard let the last command re-run
    # every load (e.g. a fnv_chat_reply box would re-pop). reply.json is a real file, so its id
    # survives reloads — run only if cmd.id > the last replied id. Read both map ids as function
    # ARGS (reading a map value into a scalar throws SYNTAX — gotcha 2).
    '    array_var aRep = (ReadFromJSON "FNVLink/reply.json" "" 0)',
    '    Player.AuxVarSetFlt "FNVLink_incid" (aCmd["id"])',
    '    Player.AuxVarSetFlt "FNVLink_repid" 0',
    '    if eval (Ar_HasKey aRep, "id")',
    '        Player.AuxVarSetFlt "FNVLink_repid" (aRep["id"])',
    '    endif',
    '    if eval ((Player.AuxVarGetFlt "FNVLink_incid") > (Player.AuxVarGetFlt "FNVLink_repid"))',
    '        int iOk = (RunBatchScript (aCmd["exec"]))',
    '        array_var aReply = Ar_Construct "stringmap"',
    '        aReply["id"] = (Player.AuxVarGetFlt "FNVLink_incid")',
    '        aReply["ok"] = (iOk)',
    '        WriteToJSON aReply ("FNVLink/reply.json") "" 0 0 1',
    '    endif',
    'endif',
    '',
])


# Custom UI fragment injected into the TextEditMenu (the box ShowTextInputMenu opens) via JIP
# InjectUIXML on each chat-box open. v2 adds a SCROLLABLE read-only conversation log
# (FNVLink_LogBox: a clipwindow hotrect cloning the menu's own scroll machinery) plus the
# "Clear" (wipe the input field) and "Close" (dismiss without sending) buttons. The in-game side
# registers the button click handlers by tile path (SetOnMenuClickEventHandler) at startup; the
# log is filled each open by chatlog_render.txt (SetUIStringAlt into FNVLink_LogText). See the
# inline comments for the hard-won scroll details (line-height hardcode, bottom-anchoring,
# grandparent-space coords, the input-field wheel bridge). Tile tree from JIP's texteditmenu.xml.
#
# WHITESPACE NOTE: the in-game JIP XML parser is ASCII-only-safe, so keep this fragment ASCII.
CHAT_INJECT_XML = """<rect name="FNVLink_ChatExtra">
	<width> <copy src="parent()" trait="width"/> </width>
	<height> <copy src="parent()" trait="height"/> </height>
	<locus> 1 </locus>
	<!-- WHEEL BRIDGE: the native input field (TEM_TextInputBox, our sibling under -->
	<!-- NOGLOW_BRANCH) is the engine's focused text-edit control, so its wheelmoved -->
	<!-- updates smoothly even with a still cursor (a read-only tile's only refreshes -->
	<!-- on mouse-move). Mirror it here so the log scrollbar (two levels down) can     -->
	<!-- read it via grandparent() and scroll smoothly regardless of cursor motion.    -->
	<!-- TRADEOFF (accepted): because the input is the focused control, wheeling over  -->
	<!-- a long typed message scrolls both it and the log. Smooth scroll is worth it.  -->
	<user0> <copy src="sibling(TEM_TextInputBox)" trait="wheelmoved"/> </user0>

	<!-- ============================================================= -->
	<!-- Scrollable read-only conversation log. Cloned from JIP's       -->
	<!-- TEM_TextInputBox scroll machinery (clipwindow + wheelable +    -->
	<!-- TEM_Scrollbar + a text child whose y is driven by the          -->
	<!-- scrollbar accumulator user0). Differences from the original:   -->
	<!--   * sub-region (explicit x/y/w/h) instead of full menu         -->
	<!--   * read-only text (id 104, NOT 0) - no engine input routing   -->
	<!--   * line height HARDCODED in user3 (the engine only fills the   -->
	<!--     id=0 input tile's user1, so a clone must supply it itself)  -->
	<!--   * scrollbar height is PARENT-relative (the log box), not the  -->
	<!--     full-menu grandparent the original uses.                    -->
	<!-- ============================================================= -->
	<hotrect name="FNVLink_LogBox">
		<id> 103 </id>
		<!-- FULL WIDTH to line up with the native input field below (which spans -->
		<!-- the whole menu width); inset is done via the text x + scrollbar gap.  -->
		<x> 0 </x>
		<y> 46 </y>
		<width> <copy src="parent()" trait="width"/> </width>
		<height> 178 </height>
		<clipwindow> 1 </clipwindow>
		<wheelable> <copy src="me()" trait="user1"/> <gt> 0 </gt> </wheelable>
		<!-- user3 = hardcoded line height for the log font (font 3) -->
		<user3> 18 </user3>
		<!-- user0 = number of fully visible lines = floor(height / lineHeight) -->
		<user0>
			<copy src="me()" trait="height"/>
			<div src="me()" trait="user3"/>
			<floor> 0 </floor>
		</user0>
		<!-- user1 = overflow lines = max(totalLines - visibleLines, 0) -->
		<user1>
			<copy src="child(FNVLink_LogText)" trait="user2"/>
			<sub src="me()" trait="user0"/>
			<max> 0 </max>
		</user1>
		<user2> 0 </user2>

		<image name="FNVLink_LogBg">
			<filename> Interface\\Shared\\solid.dds </filename>
			<!-- Like the text, a clipwindow child renders in GRANDPARENT space, so -->
			<!-- the bg must add +parent.x/+parent.y to fill the actual clip region  -->
			<!-- (without the y it sat at the clip origin and the dark only covered  -->
			<!-- the TOP ~7 lines, leaving the last line rendering past the dark).   -->
			<x> <copy src="parent()" trait="x"/> </x>
			<y> <copy src="parent()" trait="y"/> </y>
			<width> <copy src="parent()" trait="width"/> </width>
			<height> <copy src="parent()" trait="height"/> </height>
			<red> 0 </red>
			<green> 0 </green>
			<blue> 0 </blue>
			<alpha> 160 </alpha>
			<depth> 1 </depth>
		</image>

		<rect name="FNVLink_LogScroll">
			<!-- READ-ONLY LOG scroll accumulator. UNLIKE the native input-box     -->
			<!-- scrollbar this OMITS the `+parent.user1` auto-follow-bottom term:  -->
			<!-- that term re-pins the view to the bottom every frame (right for a  -->
			<!-- live input cursor, wrong for a log you want to scroll up and READ).-->
			<!-- Without it the position HOLDS where the wheel/arrows put it; the    -->
			<!-- text is BOTTOM-ANCHORED (see FNVLink_LogText/y) so the resting      -->
			<!-- state (scroll 0) already shows the newest line - no script pin.     -->
			<user0>
				<add>
					<!-- Down arrow -> NEWER (scroll decreases), Up -> OLDER (scroll    -->
					<!-- increases): matches the bottom-anchored log + the wheel.        -->
					<copy src="child(FNVLink_SbUp)" trait="clicked"/>
					<sub src="child(FNVLink_SbDown)" trait="clicked"/>
					<!-- The log's own wheel (cursor over the log + moving) PLUS the     -->
					<!-- native input field's wheel bridged via ChatExtra.user0 (smooth  -->
					<!-- even with a still cursor). Both terms negated together so the    -->
					<!-- net wheel direction is wheel-down -> newer, matching the arrows; -->
					<!-- negating the WHOLE contribution flips direction yet stays smooth.-->
					<sub src="parent()" trait="wheelmoved"/>
					<add src="grandparent()" trait="user0"/>
				</add>
				<onlyif src="child(FNVLink_SbMarker)" trait="user0"/>
				<add src="child(FNVLink_SbMarker)" trait="user2"/>
				<min src="parent()" trait="user1"/>
				<max> 0 </max>
			</user0>
			<height> <copy src="parent()" trait="height"/> <sub> 32 </sub> </height>
			<x> <copy src="parent()" trait="width"/> <sub> 17 </sub> </x>
			<y> 16 </y>
			<locus> 1 </locus>
			<alpha> 223 </alpha>
			<visible>
				<copy src="parent()" trait="user1"/>
				<gt> 0 </gt>
			</visible>

			<image name="FNVLink_SbMarker">
				<id> -1 </id>
				<target> <copy src="parent()" trait="visible"/> </target>
				<!-- INDICATOR ONLY: draggable removed. The native drag math was both -->
				<!-- the source of the release-jitter AND visually inverse; wheel +    -->
				<!-- arrow buttons cover scrolling cleanly. dragstarty stays -1 so the  -->
				<!-- scroll formula's marker.user0/user2 references stay valid (user2   -->
				<!-- evaluates to 0 with no drag, so the marker no longer feeds scroll).-->
				<dragstarty> -1 </dragstarty>
				<filename> Interface\\Shared\\scrollbar\\vert_marker.dds </filename>
				<texatlas> Interface\\InterfaceShared.tai </texatlas>
				<depth> 3 </depth>
				<width> 5 </width>
				<height>
					<copy src="parent()" trait="height"/>
					<div> <copy> 1 </copy> <add src="grandparent()" trait="user1"/> </div>
					<max> 24 </max>
				</height>
				<user0> <copy src="me()" trait="dragstarty"/> <lt> 0 </lt> </user0>
				<user1>
					<copy src="parent()" trait="height"/>
					<sub src="me()" trait="height"/>
					<div> <copy src="grandparent()" trait="user1"/> <max> 1 </max> </div>
				</user1>
				<user2>
					<copy src="me()" trait="dragy"/>
					<div src="me()" trait="user1"/>
					<floor> 0 </floor>
					<mul> <not src="me()" trait="user0"/> </mul>
				</user2>
				<x> 13 </x>
				<!-- INVERTED to match the bottom-anchored log: scroll 0 (newest) puts -->
				<!-- the marker at the BOTTOM of the track; scrolling into older history -->
				<!-- (scroll -> overflow) moves it UP. y = (track - markerH) - scroll*px. -->
				<y>
					<copy src="parent()" trait="height"/>
					<sub src="me()" trait="height"/>
					<sub> <copy src="parent()" trait="user0"/> <mul src="me()" trait="user1"/> </sub>
					<max> 0 </max>
					<min> <copy src="parent()" trait="height"/> <sub src="me()" trait="height"/> </min>
				</y>
			</image>

			<image name="FNVLink_SbUp">
				<id> -1 </id>
				<target> <copy src="parent()" trait="visible"/> </target>
				<filename> Interface\\Shared\\scrollbar\\arrow_up.dds </filename>
				<width> 32 </width>
				<height> 16 </height>
				<y> -16 </y>
				<alpha> <copy src="parent()" trait="alpha"/> </alpha>
				<depth> 3 </depth>
			</image>

			<image name="FNVLink_SbDown">
				<id> -1 </id>
				<target> <copy src="parent()" trait="visible"/> </target>
				<filename> Interface\\Shared\\scrollbar\\arrow_down.dds </filename>
				<width> 32 </width>
				<height> 16 </height>
				<y> <copy src="parent()" trait="height"/> </y>
				<alpha> <copy src="parent()" trait="alpha"/> </alpha>
				<depth> 3 </depth>
			</image>
		</rect>

		<text name="FNVLink_LogText">
			<id> 104 </id>
			<string></string>
			<clips> 1 </clips>
			<user0> 0 </user0>
			<user1> <copy src="parent()" trait="user3"/> </user1>
			<user2>
				<copy src="me()" trait="height"/>
				<sub src="me()" trait="user0"/>
				<div src="me()" trait="user1"/>
			</user2>
			<!-- x and y are both in the GRANDPARENT (clipwindow) coordinate space -->
			<!-- so BOTH add the parent's offset (confirmed live: y needed +parent.y -->
			<!-- to sit in the box; without +parent.x the text clipped off the left). -->
			<!-- 30px left padding inside the box.                                    -->
			<x> <copy> 30 </copy> <add src="parent()" trait="x"/> </x>
			<!-- BOTTOM-ANCHORED so the resting state (scroll user0 = 0) shows the   -->
			<!-- NEWEST line flush with the box bottom WITHOUT any script pin (a      -->
			<!-- SetUIFloatAlt pin permanently OVERRIDES the scroll formula - learned -->
			<!-- the hard way). y = boxTop + boxHeight - textHeight - 8px + scroll*lh:-->
			<!-- at scroll 0 the text's bottom ~= box bottom (latest visible); as     -->
			<!-- scroll grows the block slides DOWN, bringing older lines in from the -->
			<!-- top, and the self-holding accumulator keeps it where you leave it.   -->
			<y>
				<copy src="parent()" trait="y"/>
				<add src="parent()" trait="height"/>
				<sub src="me()" trait="height"/>
				<sub> 8 </sub>
				<add> <copy src="sibling(FNVLink_LogScroll)" trait="user0"/> <mul src="me()" trait="user1"/> </add>
			</y>
			<wrapwidth> <copy src="parent()" trait="width"/> <sub> 76 </sub> </wrapwidth>
			<font> 3 </font>
			<justify> 1 </justify>
			<systemcolor> 0 </systemcolor>
			<red> 200 </red>
			<green> 220 </green>
			<blue> 255 </blue>
			<depth> 2 </depth>
		</text>
	</hotrect>

	<!-- ============================================================= -->
	<!-- Clear (wipe input field) + Close (dismiss without sending)     -->
	<!-- buttons. Bottom row, left of native OK.                        -->
	<!-- ============================================================= -->
	<hotrect name="FNVLink_CloseBtn">
		<id> 100 </id>
		<width> 90 </width>
		<height> 40 </height>
		<x> 60 </x>
		<y> <copy src="parent()" trait="height"/> <sub src="me()" trait="height"/> <add> 3 </add> </y>
		<target> 1 </target>
		<locus> 1 </locus>
		<mouseoversound> UIMenuFocus </mouseoversound>
		<text name="Button_Text">
			<string> Close </string>
			<font> 2 </font>
			<justify> 2 </justify>
			<x> <copy src="parent()" trait="width"/> <div> 2 </div> </x>
			<y> 8 </y>
			<depth> 4 </depth>
			<alpha> <copy> 140 </copy> <add> <copy> 115 </copy> <onlyif src="parent()" trait="mouseover"/> </add> </alpha>
		</text>
	</hotrect>

	<hotrect name="FNVLink_ClearBtn">
		<id> 101 </id>
		<width> 90 </width>
		<height> 40 </height>
		<x> 170 </x>
		<y> <copy src="sibling(FNVLink_CloseBtn)" trait="y"/> </y>
		<target> 1 </target>
		<locus> 1 </locus>
		<mouseoversound> UIMenuFocus </mouseoversound>
		<text name="Button_Text">
			<string> Clear </string>
			<font> 2 </font>
			<justify> 2 </justify>
			<x> <copy src="parent()" trait="width"/> <div> 2 </div> </x>
			<y> 8 </y>
			<depth> 4 </depth>
			<alpha> <copy> 140 </copy> <add> <copy> 115 </copy> <onlyif src="parent()" trait="mouseover"/> </add> </alpha>
		</text>
	</hotrect>

	<!-- Clear Log: wipe the persistent conversation log (chatlog.json) + re-render it empty.
	     Distinct from Clear (which only wipes the input field). Slightly wider for the label. -->
	<hotrect name="FNVLink_ClearLogBtn">
		<id> 102 </id>
		<width> 110 </width>
		<height> 40 </height>
		<x> 280 </x>
		<y> <copy src="sibling(FNVLink_CloseBtn)" trait="y"/> </y>
		<target> 1 </target>
		<locus> 1 </locus>
		<mouseoversound> UIMenuFocus </mouseoversound>
		<text name="Button_Text">
			<string> Clear Log </string>
			<font> 2 </font>
			<justify> 2 </justify>
			<x> <copy src="parent()" trait="width"/> <div> 2 </div> </x>
			<y> 8 </y>
			<depth> 4 </depth>
			<alpha> <copy> 140 </copy> <add> <copy> 115 </copy> <onlyif src="parent()" trait="mouseover"/> </add> </alpha>
		</text>
	</hotrect>
</rect>
"""


# Render the persistent display log (chatlog.json) into the injected read-only log tile.
# Run via RunBatchScript by BOTH the '\' hotkey handler and the fnv_chat_reply exec batch right
# after the box is opened + chat_inject.xml injected. Reads chatlog.json (array of {role,text}),
# builds one %r-joined role-prefixed string via sv_Construct "%z%r%z" (the %r in the FORMAT string
# bakes a real newline, the %z splice accumulator+line), then SetUIStringAlt "%z" into the tile —
# both validated live (no literal %r). The box is bottom-anchored, so a fresh open rests at scroll
# 0 = newest flush to the box bottom (no pin). GECK gotchas baked in: string/number comparisons in
# a batch need `if eval (...)`; increment is `let i := i + 1` (not +=); `let s := map["k"]` is fine.
CHATLOG_RENDER_SCRIPT = "\r\n".join([
    'array_var aFnvLog = (ReadFromJSON "FNVLink/chatlog.json" "" 0)',
    'int iFnvN',
    'let iFnvN := (Ar_Size aFnvLog)',
    'string_var sFnvOut',
    'int iFnvI',
    'let iFnvI := 0',
    'array_var aFnvE',
    'string_var sFnvRole',
    'string_var sFnvTxt',
    'string_var sFnvLine',
    'while (iFnvI < iFnvN)',
    '    let aFnvE := aFnvLog[iFnvI]',
    '    let sFnvRole := aFnvE["role"]',
    '    let sFnvTxt := aFnvE["text"]',
    '    if eval (sFnvRole == "you")',
    '        let sFnvLine := (sv_Construct "You:  %z" sFnvTxt)',
    '    else',
    '        let sFnvLine := (sv_Construct "Claude:  %z" sFnvTxt)',
    '    endif',
    '    if eval (iFnvI == 0)',
    '        let sFnvOut := sFnvLine',
    '    else',
    '        let sFnvOut := (sv_Construct "%z%r%z" sFnvOut sFnvLine)',
    '    endif',
    '    let iFnvI := iFnvI + 1',
    'loop',
    'if eval (iFnvN == 0)',
    '    let sFnvOut := "(No messages yet. Type below and press Enter to talk to Claude.)"',
    'endif',
    'SetUIStringAlt "TextEditMenu/NOGLOW_BRANCH/FNVLink_ChatExtra/FNVLink_LogBox/FNVLink_LogText/string" "%z" sFnvOut',
    '',
])


# Mirror the player's just-typed line into the persistent display log. The '\' callback appends the
# typed line to chat.json (the fnv_poll_chat feed) and THEN RunBatchScripts this; we read the LAST
# chat.json entry and append it to chatlog.json as a {role:"you"} entry. In a batch (not the
# callback lambda) because the lambda's parenthesised body can't fit BOTH appends under GECK's
# 512-char limit. No aux-var hand-off (AuxVarSetStr/GetString don't compile cleanly in a batch):
# chat.json already carries the text and, same frame, reflects the callback's just-written append.
CHAT_RECV_SCRIPT = "\r\n".join([
    'array_var aFnvCh = (ReadFromJSON "FNVLink/chat.json" "" 0)',
    'int iFnvLast',
    'let iFnvLast := (Ar_Size aFnvCh) - 1',
    'if eval (iFnvLast >= 0)',
    '    array_var aFnvLastE',
    '    let aFnvLastE := aFnvCh[iFnvLast]',
    '    string_var sFnvT',
    '    let sFnvT := aFnvLastE["text"]',
    # Skip blank/whitespace lines: the Close + Clear buttons submit a single space (the relay's
    # drain_chat drops it from the FEED, but this display-log mirror needs its own guard or
    # closing the box would add an empty "You:" line). Nested ifs (not &&) for compile safety.
    '    if eval (sFnvT != "")',
    '        if eval (sFnvT != " ")',
    '            array_var aFnvLg = (ReadFromJSON "FNVLink/chatlog.json" "" 0)',
    '            array_var aFnvL = Ar_Construct "stringmap"',
    '            aFnvL["role"] = "you"',
    '            aFnvL["text"] = sFnvT',
    '            Ar_Append aFnvLg, aFnvL',
    '            WriteToJSON aFnvLg ("FNVLink/chatlog.json") "" 0 0 1',
    # Request a reopen so the chat box stays open after a REAL send (the native OK/Enter always
    # closes the menu; a GameMode-only checker in ln_FNVLinkChat.txt counts this down and reopens
    # the box with this new line in the log). A COUNTDOWN (not a boolean) gives the menu-close a
    # few GameMode frames to fully settle before reopening — reopening mid-Accept produced a ghost,
    # unpaused, non-interactive box. Set here, inside the non-blank guard, so the Close button's
    # blank submit does NOT reopen (Close still closes).
    '            Player.AuxVarSetFlt "FNVLink_reopen" 3',
    '        endif',
    '    endif',
    'endif',
    '',
])


# The shared "open the chat box" batch: (re)open the TextEditMenu, inject the scrollable-log UI,
# move the native input below the log, render the current chatlog.json, and set Enter=submit. Run
# by the '\' hotkey handler AND by the post-send reopen checker (ln_FNVLinkChat.txt), so a real
# send re-opens the box with the just-sent line now in the log (the native OK/Enter always closes
# the menu, so "stays open" = reopen one tick later). ShowTextInputMenu from a batch is proven (it
# is how fnv_chat_reply opens the box). Same title/layout as the hotkey open for a seamless feel.
CHAT_REOPEN_SCRIPT = "\r\n".join([
    'ref rFnvCB = (Player.AuxVarGetRef "FNVLink_chatcb")',
    'ShowTextInputMenu rFnvCB 1000 420 "Chat with Claude (Enter to send, or use the buttons):"',
    'InjectUIXML "TextEditMenu/NOGLOW_BRANCH" "FNVLink\\chat_inject.xml"',
    'SetUIFloatAlt "TextEditMenu/NOGLOW_BRANCH/TEM_TextInputBox/y" 235',
    'SetUIFloatAlt "TextEditMenu/NOGLOW_BRANCH/TEM_TextInputBox/height" 130',
    'RunBatchScript "FNVLink/chatlog_render.txt"',
    'SetTextInputExtendedProps 0 0 1 0 2',
    '',
])


class Bridge:
    """Read/write side of the live-link file bridge (relay process)."""

    def __init__(self, bridge_dir: str):
        self.dir = bridge_dir
        self._next_id = None  # lazily seeded from any existing files
        self.event_seq = 0  # monotonic counter the relay assigns to drained events
        self.chat_seq = 0  # monotonic counter the relay assigns to drained chat messages

    # ── paths / io primitives ────────────────────────────────────────

    def _path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def ensure_dir(self):
        if self.dir:
            os.makedirs(self.dir, exist_ok=True)

    def _read_json(self, name, retries: int = 5, delay: float = 0.02):
        """Read+parse a bridge file, tolerating a concurrent in-place write.

        Returns the parsed object, or None if the file is missing or never
        parses cleanly within the retry budget (treated as "not ready yet").
        """
        path = self._path(name)
        for attempt in range(retries):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except FileNotFoundError:
                return None
            except OSError:
                # transient sharing violation while the game writes — retry
                text = ""
            if text.strip():
                try:
                    return json.loads(text)
                except (ValueError, json.JSONDecodeError):
                    pass  # caught mid-write; retry
            if attempt < retries - 1:
                time.sleep(delay)
        return None

    def _write_json_atomic(self, name, obj):
        """Write a bridge file the game will read — atomically.

        Write to a sibling .tmp then os.replace, which is atomic on the same
        volume, so the game's reader sees either the old file or the whole new
        one, never a truncated cmd.json.
        """
        self.ensure_dir()
        path = self._path(name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _write_text_atomic(self, name, text):
        """Write a plain-text bridge file atomically (e.g. the exec.txt script)."""
        self.ensure_dir()
        path = self._path(name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _prune_exec(self, keep_id: int, keep_recent: int = 8):
        """Delete stale per-command exec files, keeping the last few.

        Each command writes exec_<id>.txt; once its reply is back the file is dead
        weight. Keep a small recent window (cheap insurance against a reload re-running
        a just-issued command) and remove the rest so the bridge dir doesn't grow.
        """
        for p in glob.glob(self._path("exec_*.txt")):
            base = os.path.basename(p)
            try:
                n = int(base[len("exec_"):-len(".txt")])
            except ValueError:
                continue
            if n <= keep_id - keep_recent:
                try:
                    os.remove(p)
                except OSError:
                    pass

    def seed(self):
        """Ensure the files the in-game script reads every tick exist.

        The in-game callback calls ReadFromJSON on cmd.json each tick; seeding an
        id-0 no-op command means it never reads a missing file and never executes
        anything until a real command arrives (id 0 is never greater than the game's
        reset 'last seen' id, and a noop carries no "exec" path to run).
        """
        self.ensure_dir()
        if not os.path.isfile(self._path(CMD_FILE)):
            self._write_json_atomic(CMD_FILE, {"id": 0, "type": "noop", "label": ""})
        # Seed reply.json too: the dispatcher now guards re-runs on reply.json's id (durable
        # across reloads, unlike the reverting AuxVar), so it must always be a valid {id} map.
        if not os.path.isfile(self._path(REPLY_FILE)):
            self._write_json_atomic(REPLY_FILE, {"id": 0, "ok": True})
        if not os.path.isfile(self._path(EVENTS_FILE)):
            self._write_text_atomic(EVENTS_FILE, "[]")
        if not os.path.isfile(self._path(CHAT_FILE)):
            self._write_text_atomic(CHAT_FILE, "[]")
        # The persistent display log: seed once, never auto-clear (it survives reloads and
        # accumulates the whole conversation; both sides append to it in-game).
        if not os.path.isfile(self._path(CHATLOG_FILE)):
            self._write_text_atomic(CHATLOG_FILE, "[]")
        # Always (re)write the injectable chat UI fragment + the chat batches so they track
        # the relay version.
        self._write_text_atomic(CHAT_INJECT_FILE, CHAT_INJECT_XML)
        self._write_text_atomic(CHAT_RECV_FILE, CHAT_RECV_SCRIPT)
        self._write_text_atomic(CHATLOG_RENDER_FILE, CHATLOG_RENDER_SCRIPT)
        self._write_text_atomic(CHAT_REOPEN_FILE, CHAT_REOPEN_SCRIPT)
        # Always (re)write the relay-owned batches so they track this relay version.
        self._write_text_atomic(DISPATCH_FILE, DISPATCH_SCRIPT)
        self._write_text_atomic(EVT_DEATH_FILE, EVENT_DEATH_SCRIPT)
        self._write_text_atomic(EVT_MURDER_FILE, EVENT_MURDER_SCRIPT)
        self._write_text_atomic(EVT_COMBAT_FILE, EVENT_COMBAT_SCRIPT)
        self._write_text_atomic(EVT_PICKUP_FILE, EVENT_PICKUP_SCRIPT)
        self._write_text_atomic(EVT_SELL_FILE, EVENT_SELL_SCRIPT)
        self._write_text_atomic(EVT_EQUIP_FILE, EVENT_EQUIP_SCRIPT)
        self._write_text_atomic(EVT_UNEQUIP_FILE, EVENT_UNEQUIP_SCRIPT)
        self._write_text_atomic(EVT_CELLENTER_FILE, EVENT_CELLENTER_SCRIPT)
        self._write_text_atomic(EVT_READBOOK_FILE, EVENT_READBOOK_SCRIPT)
        self._write_text_atomic(EVT_STEAL_FILE, EVENT_STEAL_SCRIPT)
        self._write_text_atomic(EVT_RELOAD_FILE, EVENT_RELOAD_SCRIPT)
        self._write_text_atomic(EVT_HOLSTER_FILE, EVENT_HOLSTER_SCRIPT)
        self._write_text_atomic(EVT_UNHOLSTER_FILE, EVENT_UNHOLSTER_SCRIPT)
        self._write_text_atomic(EVT_VATSENTER_FILE, EVENT_VATSENTER_SCRIPT)
        self._write_text_atomic(EVT_VATSLEAVE_FILE, EVENT_VATSLEAVE_SCRIPT)
        self._write_text_atomic(EVT_KILLCAMSTART_FILE, EVENT_KILLCAMSTART_SCRIPT)
        self._write_text_atomic(EVT_KILLCAMEND_FILE, EVENT_KILLCAMEND_SCRIPT)
        self._write_text_atomic(EVT_WEAPONJAM_FILE, EVENT_WEAPONJAM_SCRIPT)
        self._write_text_atomic(EVT_CASINOBAN_FILE, EVENT_CASINOBAN_SCRIPT)
        self._write_text_atomic(EVT_COMBATEND_FILE, EVENT_COMBATEND_SCRIPT)
        self._write_text_atomic(EVT_DISCOVER_FILE, EVENT_DISCOVER_SCRIPT)
        self._write_text_atomic(EVT_SAVE_FILE, EVENT_SAVE_SCRIPT)
        self._write_text_atomic(EVT_LOAD_FILE, EVENT_LOAD_SCRIPT)
        self._write_text_atomic(EVT_SLEEPWAIT_FILE, EVENT_SLEEPWAIT_SCRIPT)
        self._write_text_atomic(EVT_EXITMENU_FILE, EVENT_EXITMENU_SCRIPT)
        self._write_text_atomic(EVT_EXITGAME_FILE, EVENT_EXITGAME_SCRIPT)
        self._write_text_atomic(EVT_QUESTDONE_FILE, EVENT_QUESTDONE_SCRIPT)
        self._write_text_atomic(EVT_QUESTFAIL_FILE, EVENT_QUESTFAIL_SCRIPT)
        self._write_text_atomic(EVT_FASTTRAVEL_FILE, EVENT_FASTTRAVEL_SCRIPT)
        self._write_text_atomic(EVT_PERK_FILE, EVENT_PERK_SCRIPT)
        self._write_text_atomic(EVT_CHALLENGE_FILE, EVENT_CHALLENGE_SCRIPT)
        self._write_text_atomic(EVT_OBJSHOWN_FILE, EVENT_OBJSHOWN_SCRIPT)
        self._write_text_atomic(EVT_OBJDONE_FILE, EVENT_OBJDONE_SCRIPT)
        self._write_text_atomic(EVT_NOTEADDED_FILE, EVENT_NOTEADDED_SCRIPT)
        self._write_text_atomic(EVT_CRIPPLED_FILE, EVENT_CRIPPLED_SCRIPT)
        self._write_text_atomic(EVT_MISCSTAT_FILE, EVENT_MISCSTAT_SCRIPT)
        self._write_text_atomic(EVT_AIDUSE_FILE, EVENT_AIDUSE_SCRIPT)
        self._write_text_atomic(STATE_WRITE_FILE, STATE_SCRIPT)
        self._write_text_atomic(DIALOGUE_POLL_FILE, DIALOGUE_POLL_SCRIPT)
        # Seed the dialogue dedupe state once (never clobber a live one mid-session).
        if not os.path.isfile(self._path(DIALOGUE_LAST_FILE)):
            self._write_text_atomic(DIALOGUE_LAST_FILE, '{"t":""}')

    # ── id allocation ────────────────────────────────────────────────

    def _seed_id(self):
        """Seed the command counter above any id already on disk.

        Survives a relay restart: if a cmd/reply from a previous run is still
        present, continue past its id so the game never sees a "new" command
        whose id it already processed.
        """
        highest = 0
        for name in (CMD_FILE, REPLY_FILE):
            d = self._read_json(name)
            if isinstance(d, dict) and isinstance(d.get("id"), int):
                highest = max(highest, d["id"])
        self._next_id = highest + 1

    def _alloc_id(self) -> int:
        if self._next_id is None:
            self._seed_id()
        cid = self._next_id
        self._next_id += 1
        return cid

    # ── command round-trip ───────────────────────────────────────────

    def send_command(self, ctype: str, args: dict | None = None) -> int:
        cid = self._alloc_id()
        self._write_json_atomic(CMD_FILE, {"id": cid, "type": ctype, "args": args or {}})
        return cid

    def wait_reply(self, cid: int, timeout: float, poll: float = 0.1) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            r = self._read_json(REPLY_FILE)
            if isinstance(r, dict) and r.get("id") == cid:
                return r
            time.sleep(poll)
        return None

    def game_status(self) -> str:
        """'live' (fresh heartbeat), 'paused' (open but main loop stalled), or 'down'.

        'paused' is the alt-tabbed-without-background-running case: the game is up but
        its loop is frozen, so a command can be queued to run on resume.
        """
        s = self.read_state()
        age = s.get("_age_seconds") if s else None
        if age is None:
            return "down"
        if age <= HEARTBEAT_STALE_SECONDS:
            return "live"
        if age <= PAUSED_GRACE_SECONDS:
            return "paused"
        return "down"

    def execute_script(self, script_text: str, label: str = "",
                       timeout: float = COMMAND_TIMEOUT_SECONDS) -> dict:
        """Run a GECK script snippet in the game and block on its reply.

        Writes a UNIQUE per-id exec file (the plain script source) FIRST, then the
        id-stamped cmd.json carrying that file's game-relative path in "exec" — so by
        the time the game sees a new id, the script it must run is already fully on
        disk. A unique filename per command is required to defeat RunBatchScript's
        per-filename compile cache. The reply's 'ok' is the RunBatchScript return
        value (1 = compiled+ran cleanly, 0 = failed).

        Status-aware: if the game is down, refuse without writing. If it's paused
        (alt-tabbed, no background-running), QUEUE the command — the in-game dispatch
        runs it when the game resumes — and report queued rather than a hard timeout.
        """
        status = self.game_status()
        if status == "down":
            return {"ok": False, "down": True, "script": script_text,
                    "error": "game not running — launch FNV (xNVSE) and load a save"}

        cid = self._alloc_id()
        exec_name = "exec_%d.txt" % cid
        self._write_text_atomic(exec_name, script_text)
        self._prune_exec(keep_id=cid)
        # "exec" is the path as the GAME sees it (relative to the game root).
        self._write_json_atomic(CMD_FILE, {
            "id": cid,
            "exec": "%s/%s" % (BRIDGE_SUBFOLDER, exec_name),
            "label": label,
        })

        if status == "paused":
            return {
                "id": cid, "ok": False, "queued": True, "script": script_text,
                "error": ("game is paused/unfocused — command QUEUED; tab into FNV and it "
                          "will run on resume. (Enable OneTweak background-running to act "
                          "while tabbed out.) Note: only the most recent queued command "
                          "survives until resume."),
            }

        reply = self.wait_reply(cid, timeout=timeout)
        if reply is None:
            return {
                "id": cid, "ok": False, "timed_out": True, "script": script_text,
                "error": ("no reply from game within %.1fs — the link may have just "
                          "paused; tab into FNV and retry, or check fnv_link_status"
                          % timeout),
            }
        ok = bool(reply.get("ok"))
        return {
            "id": cid, "ok": ok, "timed_out": False,
            "script": script_text,
            "error": "" if ok else "RunBatchScript reported failure (script did not "
                                   "compile/run cleanly in-game)",
        }

    def execute(self, ctype: str, args: dict | None = None,
                timeout: float = COMMAND_TIMEOUT_SECONDS) -> dict:
        """Send a command and block on its id-matched reply.

        On timeout, returns a synthetic failure rather than raising — a missing
        reply means the game isn't running, is paused, or the link is down, which
        is information the caller wants, not an exception.
        """
        cid = self.send_command(ctype, args)
        reply = self.wait_reply(cid, timeout=timeout)
        if reply is None:
            return {
                "id": cid, "ok": False, "timed_out": True,
                "error": ("no reply from game within %.1fs — game not running, "
                          "paused, or live link not loaded" % timeout),
            }
        return reply

    # ── state / events (read side) ───────────────────────────────────

    def read_state(self, stale_seconds: float = HEARTBEAT_STALE_SECONDS) -> dict | None:
        """Latest player/world snapshot, annotated with heartbeat freshness."""
        d = self._read_json(STATE_FILE)
        if d is None:
            return None
        try:
            age = time.time() - os.path.getmtime(self._path(STATE_FILE))
        except OSError:
            age = None
        d["_age_seconds"] = round(age, 2) if age is not None else None
        d["_fresh"] = age is not None and age <= stale_seconds
        return d

    def is_connected(self, stale_seconds: float = HEARTBEAT_STALE_SECONDS) -> bool:
        s = self.read_state(stale_seconds)
        return bool(s and s.get("_fresh"))

    def drain_events(self) -> list:
        """Return all pending events and CLEAR the file (consume-once queue).

        Draining bounds events.json (it only holds events between polls) and keeps
        the in-game append cheap — instead of the array growing unbounded. The relay
        assigns each event a monotonic `seq` from its own counter (persists for the
        relay process), so sequence is reliable regardless of the in-game seq, which
        is unusable across save-reloads.

        Best-effort: if a death is appended in the tiny window between the read and
        the clear, that one notification may be lost. Acceptable for event pings;
        deaths are infrequent and polls are occasional, so the window is negligible.
        """
        d = self._read_json(EVENTS_FILE)
        if not isinstance(d, list) or not d:
            return []
        out = []
        for e in d:
            if isinstance(e, dict):
                self.event_seq += 1
                ev = {**e, "seq": self.event_seq}
                # Enrich misc_stat events with a readable stat name from the code.
                if ev.get("type") == "misc_stat":
                    try:
                        ev["stat"] = MISC_STAT_NAMES.get(
                            int(ev.get("stat_code")), "stat_%s" % ev.get("stat_code"))
                    except (TypeError, ValueError):
                        pass
                out.append(ev)
        self._write_text_atomic(EVENTS_FILE, "[]")  # drain
        return out

    def drain_chat(self) -> list:
        """Return all pending player chat messages and CLEAR the file (consume-once).

        Mirrors drain_events: chat.json is an append-only array the in-game
        ShowTextInputMenu callback writes to (one {seq,text,gamehour} per Enter).
        Draining bounds the file and lets the relay own a reliable monotonic seq
        (the in-game seq, derived from array length, is fine within a session but
        resets across reloads — same reason as events).

        Best-effort: a message typed in the tiny window between the read and the
        clear could be lost. A human types one line at a time between polls, so the
        window is negligible.
        """
        d = self._read_json(CHAT_FILE)
        if not isinstance(d, list) or not d:
            return []
        out = []
        for m in d:
            if not isinstance(m, dict):
                continue
            text = str(m.get("text", "")).strip()
            if not text:
                continue  # drop whitespace-only sends (minLength 1 lets a lone space through)
            self.chat_seq += 1
            out.append({**m, "text": text, "seq": self.chat_seq})
        self._write_text_atomic(CHAT_FILE, "[]")  # drain
        return out

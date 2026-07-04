# fnv_link_server — configuration defaults
#
# YesMan AI Live Link (c) 2026 JmyX. MIT. See LICENSE and NOTICE.md.

SERVER_NAME = "YesMan AI Live Link"
SERVER_VERSION = "1.0.0"

# Tick the in-game Script Runner script uses; the relay treats a heartbeat older
# than HEARTBEAT_STALE_SECONDS as "game not running / paused / not connected".
# (Informational in Phase 1; enforced once the bridge lands in Phase 2-3.)
DEFAULT_TICK_SECONDS = 0.75
HEARTBEAT_STALE_SECONDS = 5.0

# Bridge directory: the shared folder where the relay and the in-game script
# exchange JSON files.  EMPIRICALLY CONFIRMED (Phase 3, 2026-06-16): JIP
# WriteToJSON writes to the REAL game install dir, even under Mod Organizer 2 —
# usvfs does NOT redirect these game-root writes into overwrite\. So the bridge
# is simply  <FalloutNV game root>\FNVLink\  for every setup (MO2, Vortex, manual),
# and the relay reads that same real folder directly (no VFS involvement).
# NOTE: WriteToJSON does NOT create the subfolder — it must exist before the game
# runs (created by the installer / setup, or pre-created for testing).
BRIDGE_ENV_VAR = "FNV_LINK_BRIDGE"
BRIDGE_SUBFOLDER = "FNVLink"  # relative to the game root, from the in-game script's view

# Bridge file names (the protocol contract — see PORT_PLAN.md).
CMD_FILE = "cmd.json"        # server -> game : {id, type, label}
EXEC_FILE = "exec.txt"       # server -> game : plain GECK script source for RunBatchScript
REPLY_FILE = "reply.json"    # game -> server : {id, ok}   (ok = RunBatchScript return 0/1)
STATE_FILE = "state.json"    # game -> server : full snapshot, every tick
EVENTS_FILE = "events.json"  # game -> server : append-only list of {seq, type, ...}
CHAT_FILE = "chat.json"      # game -> server : append-only list of {seq, text, gamehour}
                             # — the player's chat messages, typed into the in-game
                             # ShowTextInputMenu box (ln_FNVLinkChat.txt) and drained by
                             # the relay's fnv_poll_chat. Claude replies via fnv_chat_reply,
                             # which re-opens the same box with the reply in the field.
CHAT_INJECT_FILE = "chat_inject.xml"  # relay -> bridge : the custom UI fragment (scrollable
                                      # conversation log + Clear/Clear Log/Close buttons) injected into the
                                      # TextEditMenu via JIP InjectUIXML on each chat-box open.
                                      # InjectUIXML reads it relative to the game root, so it
                                      # lives in the bridge dir like the relay's batch scripts.
CHATLOG_FILE = "chatlog.json"        # game -> game : the PERSISTENT display log — a JSON array of
                                     # {role,text} ("you"/"claude"). Distinct from chat.json (the
                                     # consume-once fnv_poll_chat feed): chatlog.json is never
                                     # drained, survives box-close + reload, and both sides append
                                     # to it IN-GAME (player line via chat_recv.txt, Claude line via
                                     # the fnv_chat_reply exec batch) so the game is its sole writer
                                     # (no relay-vs-game race). Rendered into the scrollable log tile.
CHAT_RECV_FILE = "chat_recv.txt"     # relay -> bridge : batch the '\' callback runs after appending
                                     # the typed line to chat.json — reads the last chat.json entry
                                     # and mirrors it into chatlog.json as a {role:"you"} entry.
CHATLOG_RENDER_FILE = "chatlog_render.txt"  # relay -> bridge : batch that reads chatlog.json, builds
                                            # one %r-joined role-prefixed string, and writes it into
                                            # the injected FNVLink_LogText tile via SetUIStringAlt.
                                            # Run by both the '\' handler and fnv_chat_reply on open.
CHAT_REOPEN_FILE = "chat_reopen.txt"  # relay -> bridge : the shared "open the chat box" batch
                                      # (ShowTextInputMenu + inject + reposition + render). Run by
                                      # the '\' hotkey handler AND by the post-send reopen checker
                                      # (ln_FNVLinkChat.txt) so the box stays open after a real send.
DISPATCH_FILE = "dispatch.txt"  # relay -> bridge : the in-game command dispatcher batch
                                # (the ln_ callback just RunBatchScripts this; kept out of
                                # the callback's parens to dodge GECK's 512-char limit)
EVT_DEATH_FILE = "evt_death.txt"  # relay -> bridge : append-a-death-event batch, run by the
                                  # OnDeath handler (same tiny-handler + batch pattern)
EVT_MURDER_FILE = "evt_murder.txt"  # relay -> bridge : append-a-murder-event batch (OnMurder)
EVT_COMBAT_FILE = "evt_combat.txt"  # relay -> bridge : append-a-combat-event batch (OnStartCombat)
EVT_PICKUP_FILE = "evt_pickup.txt"  # relay -> bridge : append-a-pickup-event batch (OnAdd)
EVT_SELL_FILE = "evt_sell.txt"      # relay -> bridge : append-a-sell-event batch (OnSell)
EVT_EQUIP_FILE = "evt_equip.txt"    # relay -> bridge : append-an-equip-event batch (OnActorEquip)
EVT_UNEQUIP_FILE = "evt_unequip.txt"  # relay -> bridge : append-an-unequip-event batch
                                      # (OnActorUnequip; name = the item, mirrors equip)
EVT_CELLENTER_FILE = "evt_cell_enter.txt"  # relay -> bridge : player-entered-a-cell batch (JIP
                                           # OnCellEnter; name = cell, NAME-DEDUPED so the
                                           # repeated "Mojave Wasteland" exterior-grid spam is
                                           # suppressed — only new-named cells emit)
EVT_READBOOK_FILE = "evt_read_book.txt"  # relay -> bridge : book-read batch (ShowOff:OnReadBook;
                                         # calling ref always player; name = the book)
EVT_STEAL_FILE = "evt_steal.txt"    # relay -> bridge : player-stole-an-item batch (ITR:OnSteal,
                                    # filtered first::playerref; name = the stolen item)
EVT_RELOAD_FILE = "evt_reload.txt"  # relay -> bridge : player-reloaded-weapon batch (JIP
                                    # SetOnReloadWeaponEventHandler + GetSelf==Player guard;
                                    # name = the weapon)
EVT_SLEEPWAIT_FILE = "evt_sleep_wait.txt"  # relay -> bridge : player-slept/waited batch
                                           # (JohnnyGuitar SetJohnnyOnSleepWaitEventHandler;
                                           # subject-less)
EVT_HOLSTER_FILE = "evt_holster.txt"    # relay -> bridge : weapon-holstered batch
                                        # (ShowOff:OnWeaponHolster + GetSelf==Player; name = weapon)
EVT_UNHOLSTER_FILE = "evt_unholster.txt"  # relay -> bridge : weapon-unholstered batch
                                          # (ShowOff:OnWeaponUnholster + GetSelf==Player; name = weapon)
EVT_VATSENTER_FILE = "evt_vats_enter.txt"  # relay -> bridge : VATS-playback-started batch
                                           # (ITR:OnVATSEnter; name = the VATS target, may be empty)
EVT_VATSLEAVE_FILE = "evt_vats_leave.txt"  # relay -> bridge : VATS-ended batch (ITR:OnVATSLeave;
                                           # subject-less + a 'kills' count field)
EVT_KILLCAMSTART_FILE = "evt_killcam_start.txt"  # relay -> bridge : killcam-started batch
                                                 # (ITR:OnKillCamStart; name = the killcam target)
EVT_KILLCAMEND_FILE = "evt_killcam_end.txt"  # relay -> bridge : killcam-ended batch
                                             # (ITR:OnKillCamEnd; name = the target, may be empty)
EVT_WEAPONJAM_FILE = "evt_weapon_jam.txt"  # relay -> bridge : weapon-jammed batch (ITR:OnWeaponJam,
                                           # filtered first::playerref; name = the jammed weapon)
EVT_CASINOBAN_FILE = "evt_casino_ban.txt"  # relay -> bridge : casino-ban batch (ITR:OnCasinoBan;
                                           # name = the casino)
EVT_COMBATEND_FILE = "evt_combat_end.txt"  # relay -> bridge : combat-ended batch (OnCombatEnd)
EVT_DISCOVER_FILE = "evt_discover.txt"     # relay -> bridge : location-discovered batch
                                           # (JIP SetOnLocationDiscoverEventHandler)
EVT_SAVE_FILE = "evt_save.txt"      # relay -> bridge : game-saved batch (SaveGame, subject-less)
EVT_LOAD_FILE = "evt_load.txt"      # relay -> bridge : game-loaded batch (LoadGame, subject-less)
EVT_EXITMENU_FILE = "evt_exit_to_main_menu.txt"  # relay -> bridge : exited-to-main-menu batch
                                                 # (xNVSE ExitToMainMenu event, subject-less)
EVT_EXITGAME_FILE = "evt_exit_game.txt"  # relay -> bridge : quit-to-desktop batch (xNVSE
                                         # ExitGame event, subject-less; write may not flush
                                         # on a hard process exit)
EVT_QUESTDONE_FILE = "evt_quest_complete.txt"  # relay -> bridge : quest-completed batch
EVT_QUESTFAIL_FILE = "evt_quest_fail.txt"      # relay -> bridge : quest-failed batch
                                               # (quest complete/fail = JohnnyGuitar SetJohnnyOn*QuestEventHandler;
                                               # quest_start removed — unfiltered "any start" floods on MCM)
EVT_FASTTRAVEL_FILE = "evt_fast_travel.txt"  # relay -> bridge : fast-travelled batch
                                             # (JIP SetOnFastTravelEventHandler; name = destination)
EVT_PERK_FILE = "evt_perk.txt"      # relay -> bridge : perk-gained batch
                                    # (JohnnyGuitar SetJohnnyOnAddPerkEventHandler; name = perk)
EVT_CHALLENGE_FILE = "evt_challenge_complete.txt"  # relay -> bridge : challenge-completed batch
                                                   # (JohnnyGuitar SetJohnnyOnChallengeComplete...;
                                                   # filter omitted = any challenge; name = the challenge)
EVT_OBJSHOWN_FILE = "evt_objective_shown.txt"  # relay -> bridge : objective-displayed batch
                                               # (ShowOff:OnDisplayObjective; name = quest, objective = text)
EVT_OBJDONE_FILE = "evt_objective_complete.txt"  # relay -> bridge : objective-completed batch
                                                 # (ShowOff:OnCompleteObjective; name = quest, objective = text)
EVT_NOTEADDED_FILE = "evt_note_added.txt"  # relay -> bridge : note-added batch (JIP OnNoteAdded;
                                           # player-inherent; name = the note)
EVT_CRIPPLED_FILE = "evt_crippled_limb.txt"  # relay -> bridge : limb-crippled batch (JIP
                                             # OnCrippledLimb, filtered to PlayerRef; limb = 0..6)
EVT_MISCSTAT_FILE = "evt_misc_stat.txt"  # relay -> bridge : misc-stat-changed batch (ShowOff:
                                         # OnPCMiscStatChange; records stat_code/delta/value, the
                                         # relay maps stat_code -> stat name. Per-kill codes
                                         # (2/3/35) are filtered out in the handler to avoid a
                                         # combat flood.)
EVT_AIDUSE_FILE = "evt_aid_use.txt"  # relay -> bridge : aid-item-used batch (JIP
                                     # SetOnUseAidItemEventHandler; no filter = any ingestible)
STATE_WRITE_FILE = "state_write.txt"  # relay -> bridge : the enriched heartbeat snapshot
                                      # batch (the heartbeat callback just RunBatchScripts
                                      # it — keeps the rich state out of the 512-char lambda)
DIALOGUE_POLL_FILE = "dialogue_poll.txt"  # relay -> bridge : NPC-dialogue capture batch, run by a
                                          # main-loop callback (ln_FNVLinkEvtDialog) every tick. The
                                          # JG dialogue EVENT hooks (SetOnNPCResponse/GeneralSubtitle)
                                          # don't fire in MTUI/heavily-modded UIs (the vanilla funcs
                                          # they hook are bypassed), so instead we POLL the on-screen
                                          # subtitle: when in the DialogMenu (menumode 1009) read the
                                          # DM_SpeakerText / DM_SpeakerNameLabel tiles via GetUIString,
                                          # dedupe against the last line, and append a {type:"dialogue",
                                          # name:speaker, text} event. Hook-free => UI-overhaul-proof.
DIALOGUE_LAST_FILE = "dlg_last.json"  # game<->game : {"t": <last captured line>} — the dedupe state
                                      # for dialogue_poll (so the same subtitle, which persists in the
                                      # tile for several ticks while shown, only emits ONE event).
                                      # A string can't be stashed via AuxVarSetStr in a batch
                                      # (gotcha 134), so the last line is persisted as JSON instead.

# How long a command tool waits for the id-matched reply before reporting the
# link as down. Must comfortably exceed two in-game ticks plus VFS latency.
COMMAND_TIMEOUT_SECONDS = 4.0

# A heartbeat between HEARTBEAT_STALE_SECONDS and PAUSED_GRACE_SECONDS old means the
# game is open but its main loop is stalled — almost always alt-tabbed/unfocused with
# NO background-running (OneTweak Active=true keeps it fresh). In that window the relay
# QUEUES a command (the in-game dispatch runs it on resume) instead of hard-failing.
# Older than this → treat the game as not running.
PAUSED_GRACE_SECONDS = 600.0

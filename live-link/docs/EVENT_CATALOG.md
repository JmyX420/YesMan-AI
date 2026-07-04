# YesMan AI Live Link — NVSE Event Catalog

A living reference of the script events exposed by the NVSE-stack plugins on this install,
and which ones the Live Link currently emits. **✅ = the Live Link already emits it.**

Machinery is excluded: `SetEventHandler` / `RemoveEventHandler` / `DispatchEvent`, render/
settings-update internals, UI-tile events, and binary string fragments. Names are extracted
heuristically from the plugin DLLs (string scan) — geckwiki's "Functions/Event Handlers"
categories are the authoritative reference.

Plugins surveyed (as installed in the DUST MO2 instance):
xNVSE 6.48 · JIP LN (PP) 57.54 · JohnnyGuitar 5.16 · ShowOff 1.80 · ITR 1.1.0 · Postal 0.0002.
**AnhNVSE 1.3.1 was surveyed and exposes NO events** (it's a 44-*function* utility plugin).

The Live Link emits **38** event types (one source event each):
`death`(OnDeath) `murder`(OnMurder) `combat`(OnStartCombat) `combat_end`(OnCombatEnd)
`pickup`(OnAdd) `sell`(OnSell) `equip`(OnActorEquip) `unequip`(OnActorUnequip)
`read_book`(ShowOff:OnReadBook) `steal`(ITR:OnSteal) `reload`(OnReloadWeapon)
`cell_enter`(OnCellEnter) `discover`(OnLocationDiscover) `fast_travel`(OnFastTravel)
`aid_use`(OnUseAidItem) `perk`(OnAddPerk) `challenge_complete`(SetJohnnyOnChallengeComplete)
`sleep_wait`(SetJohnnyOnSleepWait)
`objective_shown`(ShowOff:OnDisplayObjective) `objective_complete`(ShowOff:OnCompleteObjective)
`note_added`(OnNoteAdded) `crippled_limb`(OnCrippledLimb)
`misc_stat`(ShowOff:OnPCMiscStatChange — one event covering ~40 tracked stats, relay-named)
`holster`(ShowOff:OnWeaponHolster) `unholster`(ShowOff:OnWeaponUnholster)
`vats_enter`(ITR:OnVATSEnter) `vats_leave`(ITR:OnVATSLeave) `killcam_start`(ITR:OnKillCamStart)
`killcam_end`(ITR:OnKillCamEnd) `weapon_jam`(ITR:OnWeaponJam) `casino_ban`(ITR:OnCasinoBan)
`quest_complete`(OnCompleteQuest)
`quest_fail`(OnFailQuest) `save`(SaveGame) `load`(LoadGame) `exit_to_main_menu`(ExitToMainMenu)
`exit_game`(ExitGame)
`dialogue`(subtitle poll — NPC speech to the player; see note below, NOT an event hook).

---

## Base xNVSE — generic `SetEventHandler "OnX"`
**World / actor:** OnActivate · OnAdd ✅(pickup) · OnActorEquip ✅ · OnActorUnequip ✅ · OnDrop ·
OnEquip · OnUnequip · OnDeath ✅ · OnMurder ✅ · OnHit · OnHitWith · OnMagicEffectHit ·
OnStartCombat ✅ · OnCombatEnd ✅ · OnSell ✅ · OnGrab · OnRelease ·
OnOpen *(tried & DROPPED — unfiltered OnOpen doesn't dispatch; OnOpen/OnClose are object-scoped
and need a "first"::ref/formlist filter naming which objects to watch, so no generic version;
confirmed live with Just Loot Menu ON and OFF)* · OnClose · OnFire ·
OnReset · OnLoad · OnUnload · OnPackageChange · OnPackageStart · OnPackageDone · OnTrigger ·
OnTriggerEnter · OnTriggerLeave · OnDestructionStageChange
**Lifecycle:** SaveGame ✅ · LoadGame ✅ · ExitGame ✅ · ExitToMainMenu ✅ · QuitGame ·
MainMenu *(tried — does not dispatch via SetEventHandler in this build)* ·
PostLoadGame *(tried — does not dispatch)*

## JIP LN — dedicated `SetOnXEventHandler`
OnAnimAction · OnControlDown · OnControlUp · OnCrafting · OnCrippledLimb ✅ · OnCriticalHit ·
OnFastTravel ✅ · OnFireWeapon · OnHealthDamage · OnHit · OnKeyDown · OnKeyUp ·
OnLocationDiscover ✅ · OnMenuClick · OnMenuOpen · OnMenuClose · OnMouseoverChange · OnNoteAdded ✅ ·
OnPCTargetChange · OnPlayGroup · OnProjectileImpact · OnQuestStage · OnRagdoll · OnReloadWeapon ✅ ·
OnTriggerDown · OnTriggerUp · OnUseAidItem ✅
**JIP generic extras (`SetEventHandler`):** OnCellEnter ✅ · OnCellExit · OnButtonDown ·
OnButtonUp · OnCrosshairOn · OnCrosshairOff · OnPlayerGrab · OnPlayerRelease

## JohnnyGuitar NVSE — `SetJohnnyOnX` / `SetOnX`
OnAddPerk ✅ · OnRemovePerk · OnCompleteQuest ✅ · OnFailQuest ✅ ·
OnStartQuest *(FLOODS — fires per-frame on framework quests like MCM; do not use unfiltered)* ·
OnStopQuest · OnActorValueChange · OnChallengeComplete ✅ · OnDying · OnLimbGone ·
OnProcessLevelChange *(tried as `level_up` — registers clean but NEVER dispatches; DROPPED. No
clean level-up hook exists; character level isn't a misc stat so OnPCMiscStatChange can't help.
Level awareness is in the state snapshot's `level` field.)* · OnSleepWait ✅ · OnCrosshair ·
OnKeyboardControllerSelectionChange ·
OnRadioPostSoundAttach · OnSeenData ·
~~OnReputationChange~~ *(SCRAPPED — never dispatches in this JG build, verified exhaustively)*

## ShowOff NVSE
OnReadBook ✅ · OnWeaponHolster ✅ · OnWeaponUnholster ✅ · OnPlayerJump · OnPOVChange ·
OnDispositionChange · OnPCMiscStatChange ✅ *(emitted as the single `misc_stat` event — covers
~40 vanilla misc stats {statCode, delta, newVal}, relay maps code→name; per-kill codes 2/3/35
filtered out. NOT character level — that's not a misc stat.)* · OnChallengeProgress ·
OnQuestAdded ·
OnCompleteObjective ✅ · OnDisplayObjective ✅ · OnExplosionHit · OnExplosionHitAnyRef · OnFireWeapon ·
OnHit · OnLockpickMenuClose · OnProjectileCreate · OnProjectileDestroy · OnProjectileImpact ·
OnCalculateEffectMagnitude · OnCalculateSellPrice · OnTimerStart · OnTimerStop · OnTimerUpdate ·
OnCornerMessage
**Pre-hooks (intercept / block):** OnPreActivate · OnPreActivateInventoryItem(+Alt) ·
OnPreDropInventoryItem · OnPreLoadGame · OnPreProjectileCreate · OnPreProjectileExplode ·
OnPreRemoveItemFromMenu · OnPreScriptedActivate

## ITR NVSE
OnSteal ✅ · OnWitnessed *(undocumented on geckwiki; deferred)* · OnConsoleOpen · OnConsoleClose ·
OnConsoleCommand *(undocumented; deferred — ties into the 2-way-comms idea)* · OnVATSEnter ✅ ·
OnVATSLeave ✅ · OnKillCamStart ✅ · OnKillCamEnd ✅ · OnEffectApplied · OnEffectRemoved · OnFrenzy ·
OnActorLanded · OnJumpStart · OnDoubleTap · OnKeyEnabled · OnKeyDisabled · OnKeyHeld ·
OnContactBegin · OnContactEnd · OnContactWatch · OnDialogueText · OnEntryPoint ·
OnImpactDataSpawn · OnPrePickUp · OnSoundPlayed · OnSoundCompleted · OnSprayDecal · OnWeaponDrop ·
OnWeaponJam ✅*(by analogy — jamming is disabled in this load order, so it can't fire live here;
correct handler, fires where a mod enables jamming)* · OnWoundSpray ·
OnCasinoBan ✅ · OnCombatProcedure · OnMenuFilterChange ·
OnMenuListRefresh · OnMenuSideChange

## Postal NVSE
OnSteal *(only event cleanly extractable; v0.0002, very small/new)*

## AnhNVSE
*(no events — 44 utility functions only)*

---

## Notes / guidance
- **Flood risks (frame- or input-paced) — avoid or debounce:** OnHit, OnHitWith, OnFireWeapon,
  OnProjectile*, OnControlDown/Up, OnKeyDown/Up/Held, OnTriggerDown/Up, OnMouseoverChange,
  OnContactWatch, OnRenderUpdate, OnActorValueChange, OnHealthDamage, OnStartQuest (framework).
- **Player-scoping:** generic `SetEventHandler` events take up to two filter pairs
  (`"first"::<what>` / `"second"::<causer>`). Filter `"second"::playerref` to limit to the
  player where the event passes a causer (e.g. OnActorEquip, OnAdd, OnSell, ITR:OnSteal). Events
  with no causer arg can't be filtered this way — guard with `if eval (GetSelf == Player)` instead
  (e.g. reload, holster, OnWeaponJam), or they may be inherently player-only (VATS, killcam).
- **`OnQuestStage` (JIP)** watches a SPECIFIC quest+stage named at registration — it cannot be a
  generic "any quest progressed" event. State already exposes `quest_stage`; milestones are
  covered by `quest_complete` / `quest_fail`.
- Lifecycle events register on game LOAD (ln_ scripts run on load), so events that fire only at
  the title screen (MainMenu) can't be caught by a session-registered handler.
- **`dialogue` is captured by POLLING, not an event hook.** JohnnyGuitar's dialogue events
  (`SetOnNPCResponseEventHandler`, `SetOnGeneralSubtitleEventHandler`) compile and register but
  **never fire under a UI overhaul like MTUI** — the vanilla dialogue/subtitle engine functions
  they detour are bypassed by the overhaul's own subtitle rendering (verified live: subtitles draw
  on screen and other JG events fire, yet neither dialogue hook dispatches; it is NOT a togglable
  plugin conflict). So `ln_FNVLinkEvtDialog` instead runs a main-loop callback that reads the
  on-screen subtitle from the DialogMenu UI tiles (`DM_SpeakerText` / `DM_SpeakerNameLabel`) via
  `GetUIString` while `GetActiveMenuMode == 1009`, dedupes against the last line, and emits the
  `dialogue` event. Hook-free, so it's immune to the bypass — it requires dialogue subtitles to be
  enabled (it reads what the engine draws). **These are the VANILLA DialogMenu tile names** (verified
  by extracting `menus/dialog/dialog_menu.xml` from `Fallout - Misc.bsa`), so it works on vanilla and
  on overhauls that keep them (MTUI, VUI+, etc. — they're edits of the vanilla menu). The read uses a
  **candidate-path chain** (`DIALOGUE_POLL_SCRIPT`), so a UI that *renames* the subtitle tiles is
  supported by appending its path — and it harmlessly no-ops on an unknown UI. `GetUIString` reads a
  tile's string trait (`GetUIStringAlt` does not).

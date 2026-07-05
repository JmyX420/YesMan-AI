# YesMan AI — Codex integration layer

This folder holds the **Codex-specific** integration for YesMan AI. The Claude Code
integration lives at the repo root (`CLAUDE.md`, `.claude/`) and is untouched; the
**engine is shared** and lives once, at the repo root:

- `tools/` (AutoMod CLI), `KNOWLEDGEBASE.md`, `examples/`, `scripts/`, `docs/`
- `mo2-mcp/` (MO2 MCP server) and `live-link/` (YesMan AI Live Link)

Only the thin per-agent adapter differs. This folder is that adapter for Codex.

## Layout

| Source (here) | Installs to (game folder) | Purpose |
|---|---|---|
| `codex/AGENTS.md` | `<game>/AGENTS.md` | Codex instructions (twin of `CLAUDE.md`) |
| `codex/skills/` | `<game>/.agents/skills/` | Codex skills (ported from `.claude/skills/`) |
| `codex/hooks/` | hook scripts + `.codex/config.toml` `[hooks]` / `hooks.json` | safety guardrails |

The installer (`installer/configure.py --agent codex`) fills the same `{{GAME_ROOT}}` /
`{{MO2_INSTANCE}}` / `{{MO2_PROFILE}}` / `{{DOCUMENTS_DIR}}` / `{{JQ_PATH}}` placeholders in
`AGENTS.md` and the hooks that it already fills for the Claude variant.

## Claude → Codex mapping (verified against Codex docs, 2026-07)

| Concern | Claude Code | Codex |
|---|---|---|
| Instructions file | `CLAUDE.md` (root) | `AGENTS.md` (root; walked down-tree, concatenated) |
| Skills | `.claude/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md` — **same format** (YAML `name`/`description`), auto-discovered, implicit invocation. Optional `agents/openai.yaml` for UI metadata |
| Safety hooks | `.claude/settings.json` `PreToolUse` (matcher `Bash` / `Edit\|Write`) | `.codex/config.toml` `[hooks]` or `hooks.json`, event `PreToolUse` (matcher `Bash` / `apply_patch`); deny via `hookSpecificOutput.permissionDecision:"deny"` or exit 2 |
| MCP registration | `~/.claude.json` `mcpServers` (JSON) | `~/.codex/config.toml` `[mcp_servers.NAME]` (TOML) — stdio (`command`/`args`/`env`/`cwd`) or HTTP (`url`) |
| MCP tool names | `mcp__mo2__*`, `mcp__fnv-link__*` | server tool names as-is (`mo2_*`, `fnv_*`) |
| Trust | (implicit) | project-scoped `.codex/` loads only for **trusted** projects — installer sets `[projects."<game>"] trust_level = "trusted"` |

## Status

- [x] `AGENTS.md` — adapted from `CLAUDE.md` (header, MCP-tool naming, `PreToolUse`
      safety section, `.codex/backups/` audit trail, Claude→Codex wording).
- [x] **Skills** — DONE. Decision: **no duplication** — the 18 `.claude/skills/*/SKILL.md`
      were made **agent-neutral** (14 edits across 7 skills: `mcp__*` naming → "the mo2/fnv-link
      MCP tools"; "see CLAUDE.md" → "CLAUDE.md / AGENTS.md"; `fnv-live-link` agent-runtime
      wording genericized). The installer will copy this single set to `<game>/.agents/skills/`
      for Codex (auto-discovered). `fnv-context` (Claude `paths:` always-load) is covered for
      Codex by AGENTS.md's Top-Gotchas/MO2 sections. See `codex/skills/README.md`. Deferred:
      per-skill `agents/openai.yaml` UI metadata. Follow-up (live-link, not skills): in-game
      chat label renders `Claude:` — make agent-aware in a live-link render tweak.
- [x] **Hooks** — DONE + tested (`codex/hooks/`). `protect-bash.sh` (near-direct copy),
      `protect-files.sh` + `backup-before-edit.sh` (extract target path(s) from the
      `apply_patch` **patch text** — `*** Add/Update/Delete/Move to File:` headers — with a
      `.tool_input.file_path` fallback; multi-file patches evaluated per file, hard-block
      wins), and `hooks.json` wiring (`Bash` + `apply_patch` matchers, `{{GAME_ROOT}}`).
      Verified with mock Codex inputs: deny (.esp/.bsa, incl. multi-file), ask (FNV ini),
      whitelist (`.agents/skills`), and a real backup→`.codex/backups/` + audit log.
      Backups use the input's `.cwd` to resolve relative patch paths. STILL TODO in a later
      phase: configure.py deploys these to `<game>/.codex/hooks/` + writes `.codex/hooks.json`
      + sets project trust (`[projects."<game>"] trust_level="trusted"`). Note: `jq` is a
      real dependency (installed on the dev box during testing — winget `jqlang.jq`).
- [x] **MCP registration for Codex** — DONE + tested. `configure.py` writes
      `~/.codex/config.toml` `[mcp_servers.fnv-link]` (stdio) + `[mcp_servers.mo2]` (http :49200)
      via a text-based upsert helper (idempotent, preserves existing config + comments, valid
      TOML verified with tomllib), and sets `[projects."<game>"] trust_level="trusted"`.
      **MO2 plugin dual-write (DONE):** the plugin's `_ensure_mcp_config(port)` self-registers
      `mo2` into BOTH `~/.claude.json` (JSON) AND `~/.codex/config.toml` (TOML) on each MO2 start,
      keyed off the **live port** — so a port change propagates to whichever agent(s) are installed
      (self-contained text-based TOML upsert in the plugin, best-effort, never raises; tested for
      insert / idempotency / port-change / preserve). configure.py still writes the `mo2` entry
      (default port) at install as a bootstrap for the window before MO2 first launches; the plugin
      then keeps it in sync. `live-link/install.py::register_mcp` (JSON) still handles Claude fnv-link.
- [x] **Installer** — DONE. `configure.py --agent claude|codex|both` (refactored: shared
      detect/npm/MO2/plugin/bridge steps done once, per-agent files + MCP registration branched);
      `deploy_codex_files` deploys AGENTS.md→root, hooks→`.codex/hooks`+`hooks.json`, skills→
      `.agents/skills`, fills all placeholders, makes `.codex/backups`. Inno wizard gains an
      **AI Coding Agent** page (Claude / Codex / Both) before the MO2 page; `--agent` passed to
      configure.py (defaults to claude in silent mode). Recompiles clean. **Tested end-to-end**
      via `--agent both` against a sandbox (fake MO2, redirected HOME): all Codex artifacts
      deployed + filled, config.toml valid, `~/.claude.json` preserved+updated, both MCPs registered.
- [x] **Docs + naming** — DONE. Product name is now "YesMan AI - A FNV Modding Toolbox for
      Claude and Codex" (README H1, NEXUS title, SETUP_PROMPT, `.iss` AppNameLong, configure.py).
      README / NEXUS / getting-started updated: prerequisites list Claude and/or Codex, the
      installer's **agent-picker page** is described, restart/first-run steps are agent-neutral
      ("restart your agent", `CLAUDE.md`/`AGENTS.md`, `~/.claude.json` and/or `~/.codex/config.toml`),
      and `SETUP_PROMPT.txt` was neutralized to work for both agents. README Docs list points to
      `codex/`. Installer recompiles clean.
- [x] **Dogfood** on a real Codex install — DONE (2026-07-05, Codex desktop app 26.x /
      `codex-cli 0.142.5`). Guarded (isolated `CODEX_HOME`, real config untouched, verified).
      Confirmed on the ACTUAL current Codex:
      - **AGENTS.md project load** ✓ — `codex exec` returned a unique marker planted in a test
        project's AGENTS.md.
      - **`.agents/skills` discovery** ✓ — Codex reported the planted skill was "present in the
        declared skill list" and invoked it by name/description. **Path confirmed** (`.agents/skills`,
        not `.codex/skills`); skills use frontmatter-for-discovery + on-demand body read (same
        progressive-disclosure model as Claude → our SKILL.md format is correct).
      - **config.toml MCP** ✓ — `codex mcp add fnv-link/mo2` produced config matching ours and
        `codex mcp list` parsed it; MCP servers load in a live `exec` session (`node_repl` etc.).
      - **Hooks** exist with a **trust model** (`--dangerously-bypass-hook-trust`) as designed.
      - Caveat (env, not a defect): `codex exec --sandbox read-only` headless from a shell hit
        `CreateProcessAsUserW failed: 5` when spawning a process to read the skill body; the
        desktop app runs skills normally. Hook *firing* (blocking a real edit) wasn't exercised
        live — deferred to interactive verification; the mechanism + format are validated.

## Resolved empirical unknowns (dogfood, 2026-07-05)

1. `PreToolUse` input schema — `tool_name` + `tool_input.command` (per docs; hooks built to it).
2. **Skills discovery path — CONFIRMED `.agents/skills/`** (the installer deploy target is correct).
3. `permissionDecision:"ask"` support not exercised live; hard `deny` blocks are the critical
   guarantee and Codex's native approval policy backstops the confirms regardless.

## Recommended refinement (optional)

`codex mcp add <name> --url ...` / `... --env K=V -- <cmd> args` is the **canonical** registration
path (Codex writes/owns the TOML, incl. an `[mcp_servers.NAME.env]` sub-table vs. our valid inline
`env = {…}`). configure.py could **prefer `codex mcp add`** (locate codex via PATH / `CODEX_CLI_PATH`
/ the `AppData\Local\OpenAI\Codex\bin\*\codex.exe` glob) and fall back to the hand-written TOML upsert.
Not required — the hand-written TOML is validated to parse and match Codex's format — but more robust.

Reference: developers.openai.com/codex/{config-reference, mcp, hooks, skills}; verified against codex-cli 0.142.5.

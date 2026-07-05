# Codex skills — deploy model

**There are no duplicated skill files here, by design.** The 18 skills live once, at the
repo root in `.claude/skills/<name>/SKILL.md`, authored **agent-neutrally** so a single set
serves both agents. Duplicating them into `codex/` would recreate the exact divergence we
avoided by choosing one repo over two — so instead the installer routes the same source to
each agent's discovery path.

## Format compatibility

Codex skills and Claude skills share the format: a `<name>/SKILL.md` directory with YAML
frontmatter (`name` + `description`, optional `argument-hint`), auto-discovered. Our skills
are already in this shape, so they need no structural change — only the wording neutralization
below.

## Discovery paths

| Agent | Reads skills from |
|---|---|
| Claude Code | `<game>/.claude/skills/` |
| Codex | `<game>/.agents/skills/` (repo-scoped; also `$HOME/.agents/skills`), **auto-discovered** |

`installer/configure.py --agent codex` copies `.claude/skills/*` → `<game>/.agents/skills/`
(a later installer-phase task). Codex detects them automatically; no config entry needed.

## Neutralization applied (2026-07)

The shared skills were made agent-agnostic so both deploys read correctly:
- `` `mcp__mo2__*` `` presence checks → "the mo2 MCP tools" (`mcp__fnv-link__*` → "the fnv-link MCP tools").
  The specific server tool names (`mo2_audio_info`, `mo2_create_patch`, …) are kept — they're
  identical across agents.
- "see CLAUDE.md" pointers → "CLAUDE.md / AGENTS.md".
- Agent-runtime wording in `fnv-live-link` ("restart Claude Code", "In Claude Code that's a
  background monitor", "dies on a Claude restart") → agent-neutral ("your agent", …).

## `fnv-context` (the always-on skill)

`fnv-context` uses Claude-specific frontmatter (`user-invocable: false` + `paths:` globs) to
**auto-inject** when FNV files are touched. Codex has no path-based always-inject. Its content
(the **Top Gotchas** + **MO2 first** sections) already lives in `AGENTS.md`, which Codex loads
every session — so Codex is covered without it. The installer therefore does **not** need to
deploy `fnv-context` to `.agents/skills/` (harmless if it does; the extra frontmatter is ignored).

## Known follow-up (live-link, not skills)

The in-game chat log renders the assistant's lines as **`Claude:`** (from the live-link render
scripts / `chatlog.json` role mapping). For a Codex user this ideally reads `Codex:` or a neutral
label. That's a live-link enhancement (make the render label agent-aware), tracked separately —
the skill text still describes the current `You:` / `Claude:` behavior accurately.

## Optional, deferred

Per-skill `agents/openai.yaml` (Codex app UI metadata: `display_name`, `short_description`,
icons, `default_prompt`) can be added later for polish. Not required for function.

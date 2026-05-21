# mnemo Agent Instructions

mnemo is a dual-runtime Agent Skills plugin for Codex and Claude Code. Keep Claude Code compatibility intact while adding Codex support.

## Compatibility Rules

- Do not remove `plugins/mnemo/.claude-plugin/plugin.json` or `plugins/mnemo/commands/mn/*`; Claude users rely on `/mn:*`.
- Codex support is additive: keep `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` beside the Claude manifest.
- Shared skills live in `plugins/mnemo/skills/*/SKILL.md`; avoid forked copies unless behavior must diverge by runtime.
- Runtime-specific behavior belongs in scripts or `references/`, not duplicated skill bodies.

## Memory Backends

- Obsidian is the primary user-visible memory store.
- claude-mem is optional and may be intentionally disabled for CPU/RAM reasons. Do not auto-start ChromaDB, the claude-mem worker, or repair claude-mem unless the user explicitly asks.
- In Codex, fallback local memory goes under `~/.codex/memories/`.
- In Claude Code, fallback local memory goes under `~/.claude/projects/<slug>/memory/`.

## Verification

- Run `python3 scripts/lint-skills.py` after editing any skill, manifest, script reference, or plugin metadata.
- Run `python3 plugins/mnemo/scripts/session-scan.py` once without runtime env vars to verify graceful fallback.
- Preserve shell-safety: never pass arbitrary markdown through `obsidian create content="..."` or `obsidian append content="..."`.

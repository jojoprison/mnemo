# mnemo on Codex

mnemo ships as native Agent Skills for Codex while preserving the Claude Code `/mn:*` command wrappers.

## Install

```bash
codex plugin marketplace add jojoprison/mnemo
codex plugin add mnemo@mnemo
```

For local development from this repository, Codex reads `.agents/plugins/marketplace.json` and `plugins/mnemo/.codex-plugin/plugin.json`.

## Invocation

Codex exposes Claude-compatible mnemo aliases:

```text
/mn:ask what did we decide about Obsidian MCP?
/mn:save remember this deployment gotcha
/mn:session
/mn:review
```

Use `/mn:review` to close a session: it runs the end-of-session review and then routes into save + session notes. The longer skill names (`mnemo:vault-search`, `mnemo:memory-routing`, `mnemo:session-notes`, `mnemo:session-review`) remain available for compatibility. Accidental `/mnemo:mn:*` invocations are also routed, but `/mn:*` is the canonical Codex/Claude-compatible form. The same `plugins/mnemo/skills/*/SKILL.md` files are used by Claude Code. Avoid creating Codex-only copies unless the workflow genuinely diverges.

## Runtime Differences

| Area | Claude Code | Codex |
|------|-------------|-------|
| User rules | `CLAUDE.md` | `AGENTS.md` |
| Commands | `/mn:*` wrappers | `/mn:*` alias skills + `mnemo:*` and `/mnemo:mn:*` compatibility aliases |
| Plugin manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| Marketplace | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json` |
| Session log | `~/.claude/projects/*/*.jsonl` | `~/.codex/sessions/**/*.jsonl` |
| Local memory fallback | `~/.claude/projects/<slug>/memory/` | `~/.codex/memories/` |

## Obsidian and claude-mem

Obsidian remains the primary memory store. Search and graph operations use the `obsidian` CLI because it is indexed and exposes operations MCP does not.

claude-mem is optional. New configs default to:

```json
"claude_mem": { "enabled": false, "url": "http://127.0.0.1:37777" }
```

Do not start ChromaDB or the claude-mem worker from mnemo. Users who intentionally disable claude-mem should see a silent skip, not a warning.

## Verification

```bash
python3 scripts/lint-skills.py
python3 plugins/mnemo/scripts/session-scan.py
python3 plugins/mnemo/scripts/skills-discover.py | tail -5
```

All commands should exit 0. `session-scan.py` should parse the current Codex rollout JSONL when run inside Codex, or return a graceful fallback outside Codex.

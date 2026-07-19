# mnemo on Codex

mnemo ships seven native Agent Skills from the same source used by Claude Code. The workflows are shared; only identity and presentation differ by runtime.

## Install

```bash
codex plugin marketplace add jojoprison/mnemo
codex plugin add mnemo@mnemo
```

For local development, Codex reads `.agents/plugins/marketplace.json` and `plugins/mnemo/.codex-plugin/plugin.json`.

## Invocation

Codex explicitly invokes skills with `$` (or through `/skills`), not with Claude's slash-command syntax:

| UI label | Deterministic Codex invocation |
|----------|--------------------------------|
| `mn:ask` | `$mnemo:ask` |
| `mn:save` | `$mnemo:save` |
| `mn:session` | `$mnemo:session` |
| `mn:review` | `$mnemo:review` |
| `mn:connect` | `$mnemo:connect` |
| `mn:setup` | `$mnemo:setup` |
| `mn:health` | `$mnemo:health` |

For example:

```text
$mnemo:ask what did we decide about Obsidian MCP?
$mnemo:save remember this deployment gotcha
$mnemo:review
```

Typing `$` or opening `/skills` shows the short `mn:*` labels configured in each skill's `agents/openai.yaml`. A literal `/mn:save` is a Claude Code command, not a guaranteed Codex invocation. Codex may also invoke a skill implicitly when its description matches the task.

## Identity Contract

| Area | Claude Code | Codex |
|------|-------------|-------|
| Install ID | `mnemo@mnemo` | `mnemo@mnemo` |
| Runtime namespace | `mn` | `mnemo` |
| Explicit invocation | `/mn:save` | `$mnemo:save` |
| User-facing label | `mn:save` | `mn:save` |
| Plugin manifest | `.claude-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| Marketplace | `.claude-plugin/marketplace.json` | `.agents/plugins/marketplace.json` |
| Session log | `~/.claude/projects/*/*.jsonl` | `~/.codex/sessions/**/*.jsonl` |
| Local memory fallback | `~/.claude/projects/<slug>/memory/` | `~/.codex/memories/` |

There are no alias skills and no command wrappers. All seven workflows live once under `plugins/mnemo/skills/`; Codex-only presentation stays in `agents/openai.yaml`.

Claude's optional `model` and `context` frontmatter fields remain in the shared files to preserve its fork/model routing. Codex's plugin validator accepts these extensions; the standalone strict Agent Skills validator does not. This is an intentional compatibility trade-off, not duplicated behavior.

## Obsidian and claude-mem

Obsidian remains the primary memory store. Search and graph operations use the indexed `obsidian` CLI through `safe-read.py` (`shell=False` for dynamic names/queries); markdown writes use MCP to avoid shell expansion.

claude-mem is optional and disabled by default. mnemo never starts ChromaDB or the claude-mem worker automatically.

## Verification

```bash
python3 scripts/lint-skills.py
python3 scripts/test-runtime-compat.py
python3 scripts/test-handoff-archive.py
python3 plugins/mnemo/scripts/session-scan.py
python3 /path/to/plugin-creator/scripts/validate_plugin.py plugins/mnemo
```

All commands should exit 0. `session-scan.py` must return a graceful fallback when no supported runtime session is discoverable. A fresh `skills-discover.py` run in Codex must expose exactly the seven `mnemo:*` IDs; `scripts/test-runtime-compat.py` guards the runtime-isolation rules without depending on the user's installed skill inventory.

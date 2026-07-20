# mn:save — Memory Routing Cascade

## Overview

The brain of mnemo. When you say "remember this" or "save to memory", this skill routes the information to the right storage backends — Obsidian, optional claude-mem, Claude auto-memory when applicable, and the existing project-instruction path for actionable rules — with explicit graceful degradation. Codex generated memories are a read-only recall source, not a manual write target.

## Usage

```
/mn:save "we decided to use SCOPE over TextGrad for self-correction"
/mn:save "gotcha: execSync with shell=true is banned in antomate"
/mn:save "HisPO algorithm stabilizes RL training for MoE models"
/mn:save "принцип: сначала ambitious-вариант с честными trade-offs"
/mn:save "это моя боль: вставляю стену промпта каждую сессию"
```

Or just say naturally:
```
запомни: Obsidian CLI встроен в Obsidian 1.12+, не отдельный npm пакет
remember: gws gmail command is +triage not list
```

## How It Works

```
Your input
  ↓ classify — recall item, or an actionable rule?
  ↓
  recall item ─┬─→ 1. Obsidian (type mapped by semantic role) → if down, skip
               ├─→ 2. claude-mem (semantic search)    → if down, skip
               └─→ 3. Claude auto memory (error prevention) → Codex: generated state stays read-only
  ↓
  actionable rule ─→ 3.5 .claude/rules/<domain>.md (auto-inject, path-scoped)
                          → create file/dir if none matches; CLAUDE.md only as fallback
  ↓
  Report: what saved where, what skipped
```

## Example Output

```
💾 Memory saved:

Content: "SCOPE chosen over TextGrad for agent self-correction"
Type: decision

Backends:
  1. Obsidian  ✅ → "Atom — SCOPE chosen over TextGrad" in MOC — Agent Self-Correction
  2. claude-mem ✅ → semantic search indexed
  3. Claude auto memory ✅ → verified topic/index updated (Codex would report generated-state skip)
  3.5 .claude/rules ⏭  skipped (recall item, not an actionable rule)
  4. CLAUDE.md ⏭  skipped (not critical rule)
```

## Configuration

In `~/.mnemo/config.json`:

```json
{
  "cascade": {
    "obsidian": { "enabled": true },
    "claude_mem": { "enabled": false, "url": "http://127.0.0.1:37777" },
    "memory_dir": { "enabled": true },
    "project_rules": { "enabled": true },
    "claude_md": { "enabled": false }
  }
}
```

Don't have claude-mem? Set `"enabled": false` — everything else works.

## Depth via structure, not volume

`save` never writes one exhaustive blob — depth is distributed across many atomic, claim-titled notes so a future agent can grab the exact slice. Each note's body follows a **typed slot** for its semantic type (Step 0b):

- **decision** → a single Y-statement (context / choice / rejected / goal / trade-off / because)
- **gotcha / business rule** → GIVEN / WHEN / THEN + Because + Fails-when
- **principle / pain / stance** → JTBD (Job / Pain / Done-well / Anti-goal) — captures your business logic, pains, and how you think/decide as human-authored/confirmed atoms (recorded with a searchable `kind:` field), never an agent-invented dossier
- **fact / insight** → claim-title + BLUF first line + evidence

Material with ≥2 separable claims becomes ≥2 notes (plus an optional synthesis), never a single note. Every typed note carries a claim-shaped title + a `because` rationale (hard-gated for decision / rule / pain).

## Important Notes

- **Fails visibly, never invents a shadow store** — unavailable durable backends are reported so the user can retry
- **Classifies automatically** — you don't choose a physical type; the exact five-key `taxonomy_roles` map resolves it, and a narrower `kind:` sub-type shapes the body
- **Duplicate check** — always searches Obsidian before creating
- **Bundled adapters in both runtimes** — dynamic reads go through `safe-read.py`; every vault Markdown write goes through the JSON-stdin optimistic `vault-write.py`

## Related Skills

- `/mn:session` — writes the full session narrative and handoff; complements discrete saves
- `/mn:review` — recommends running save if unsaved decisions detected
- `/mn:health` — verify saved notes aren't orphans

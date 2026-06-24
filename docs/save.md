# mnemo:save — Memory Routing Cascade

## Overview

The brain of mnemo. When you say "remember this" or "save to memory", this skill routes the information to the right storage backends — Obsidian, claude-mem, memory files, `.claude/rules/` (for actionable rules), CLAUDE.md — with graceful degradation. If one backend is down, others still work.

## Usage

```
/mn:save "we decided to use SCOPE over TextGrad for self-correction"
/mn:save "gotcha: execSync with shell=true is banned in antomate"
/mn:save "HisPO algorithm stabilizes RL training for MoE models"
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
  recall item ─┬─→ 1. Obsidian (Atom/Molecule/Source) → if down, skip
               ├─→ 2. claude-mem (semantic search)    → if down, skip
               └─→ 3. memory/ (error prevention)      → if not needed, skip
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
  3. memory/   ✅ → memory/antomate-stack.md updated
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

## Important Notes

- **Never fails completely** — at least one backend always works
- **Classifies automatically** — you don't need to specify atom vs molecule
- **Duplicate check** — always searches Obsidian before creating
- **CLI-first** — uses obsidian CLI, not MCP

## Related Skills

- `/mn:session` — saves an entire session summary (uses save internally)
- `/mn:review` — recommends running save if unsaved decisions detected
- `/mn:health` — verify saved notes aren't orphans

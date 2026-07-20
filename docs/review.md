# mn:review — End-of-Session Orchestrator

## Overview

The only command you need at session end. Analyzes everything, then presents one prioritized offer — unsaved decisions (`/mn:save`), session notes (`/mn:session`), and the remaining skills. **Nothing runs without your confirmation.** One command replaces manually running save + session + connect + health — you approve the batch once. Add `--full` and even that one approval goes away: the flag itself is consent (see [`--full` below](#--full--one-command-close-out-v128)).

## Usage

```
/mn:review
```

Codex explicit form: `$mnemo:review`. Samples below use Claude Code syntax.

Also triggers on: "что забыли?", "что осталось?", "session review", "all done?", "what did we miss?"

## How It Works

### 1. Runtime evidence collection

The skill collects fresh evidence with the current runtime's normal tools:
- **Git state** — status, branch, recent commits, uncommitted changes
- **JSONL introspection** — reads the exact active Claude session or Codex thread to extract tool calls, explicit skill invocations, modified files, commits, and error count; it never falls back to another task
- **Skill discovery** — scans active runtime locations, selects only the current plugin generation, and ignores shadowed cache copies
- **Open PRs** — checks for your open GitHub PRs

### 2. Session fingerprinting

Classifies the session based on tool usage patterns:

| Type | Key signals |
|------|-------------|
| Implementation | Write/Edit heavy, commits, "feat/add" |
| Research | Read/Grep/WebSearch heavy, few writes |
| Debugging | Error patterns, "fix" commits |
| Refactoring | Renames, large diffs |
| Documentation | .md files dominant |
| Configuration | Config/CI/deploy files |
| Planning | Plan mode, brainstorm docs |

### 3. Skill gap analysis

Cross-references session type → signals → available skills → already used skills. Only recommends skills that are **actually installed**.

Examples:
- Implementation session + no tests → recommends `/test-master`
- Research session + no notes saved → recommends `/mn:save`, `/mn:session`
- Branch diverged + no PR → recommends `/ship`

### 4. Execution chain

Offers to run missed skills in priority order:

```
3 skills recommended. Execute?

  1. [CRITICAL] /commit — uncommitted changes
  2. [HIGH] /mn:save — 3 unsaved decisions
  3. [HIGH] /mn:session — session notes

Options:
  A — Execute all in order
  1,2,3 — Execute specific ones
  N — Skip
```

## Example Output

```
## Session Review

Project: mnemo
Branch: main
Type: Implementation
Task: Plugin refactoring — naming, review rewrite

### Done (4)
| # | What | Evidence |
|---|------|----------|
| 1 | Plugin rename mn→mnemo | plugin.json |
| 2 | Review SKILL.md rewrite | 350+ lines |

### Missed (2)
| # | What | Priority | Action |
|---|------|----------|--------|
| 1 | Uncommitted changes | CRITICAL | git commit |
| 2 | Session notes | HIGH | /mn:session |

### Skill Gap
Used: mn:ask
Should use: /mn:session, /mn:save

### Score: 5/10
```

## Core-Skill Recommendations (v0.16.0 — no auto-run)

Review prepares two core candidates but **never runs them without asking** (auto-run removed in v0.16.0; it existed v0.5.9–v0.15.x):

| Skill | When offered | What happens if accepted |
|-------|-------------|--------------------------|
| `/mn:save` | Unsaved decisions/findings detected | Extracts and routes to Obsidian, optional claude-mem, and enabled Claude auto-memory; Codex generated memory remains read-only |
| `/mn:session` | Significant work done | Creates session note + handoff |

**Skips** if the skill was already invoked this session (checked via runtime JSONL evidence).

Everything lands in a single prioritized offer:
```
Recommended:
  1. [CRITICAL] /commit — 5 uncommitted files
  2. [HIGH] /mn:save — 3 unsaved decisions (X, Y, Z)
  3. [HIGH] /mn:session — significant work, no session note yet
  4. [MEDIUM] /mn:connect — 2 new notes, find links?

Run any? (1,2,3,4 / A=all / N=skip)
```

## `--full` — one-command close-out (v1.2.8)

```
/mn:review --full
```

The explicit flag **is** the consent, so the whole close-out runs with no per-skill prompt. It:

1. **Anchors on the session's origin** — reconstructs the first request and measures drift (discussed vs wanted vs did), not just an end-state inventory.
2. **Audits** the whole arc (Done / Missed / Hanging Threads / score) — this produces the recommendation list.
3. **Executes the chain** in order — `save → session → [any focus text you passed after --full] → connect` — injecting the depth-contract so business-logic / pains / how-you-think route into typed `save` atoms, not the session narrative. `health` is excluded (heavy — run it by hand).
4. **Verifies (read-only)** — checks the freshly-parked notes for typed-slot quality, atomicity, and connectedness (binary orphan check, delegated to `connect`, never self-linked); REPORTS any missing prod/e2e verification as a gap (mnemo never runs QA); and is idempotent — a second `--full` on an unchanged session prints "🏛 already in order" and stops.

Plain `/mn:review` (no flag) is unchanged: audit + one interactive offer, never auto-runs (v0.16.0). `--full` does **not** revive that killed implicit autorun — the user typed the flag.

## Important Notes

- **Always thorough** — no quick mode, full analysis every time
- **Asks before running** — save + session are top recommendations, never silent auto-runs
- **Inline execution** — runs in main conversation context, can invoke other skills
- **BLUF** — score and critical items first, details below
- **Won't nag** — skill already ran this session? Skips it
- **Only recommends installed skills** — never suggests unavailable tools

## Related Skills

- `/mn:save` — top review recommendation when unsaved decisions detected
- `/mn:session` — top review recommendation when the session is significant
- `/mn:health` — review recommends if new notes were created
- `/mn:connect` — review recommends if new notes need linking

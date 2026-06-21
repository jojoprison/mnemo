# mnemo:review — End-of-Session Orchestrator

## Overview

The only command you need at session end. Analyzes everything, **auto-saves** unsaved decisions, **auto-creates** session notes, then recommends remaining skills. One command replaces manually running save + session + connect + health.

## Usage

```
/mn:review
```

Also triggers on: "что забыли?", "что осталось?", "session review", "all done?", "what did we miss?"

## How It Works

### 1. Preprocessing (before Claude sees the prompt)

Shell scripts run automatically:
- **Git state** — status, branch, recent commits, uncommitted changes
- **JSONL introspection** — parses `${CLAUDE_SESSION_ID}.jsonl` to extract every tool call, skill invocation, modified file, error count
- **Skill discovery** — globs the install locations (personal skills, plugins, cache, marketplaces) to find all available skills
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

## Auto-Execution (v0.5.9)

Review now **auto-runs** two core skills without asking:

| Skill | When | What happens |
|-------|------|-------------|
| `/mn:save` | Unsaved decisions/findings detected | Extracts and saves to Obsidian + claude-mem + memory/ |
| `/mn:session` | Significant work done | Creates session note + handoff |

**Skips** if the skill was already invoked this session (checked via JSONL preprocessing).

After auto-run, asks about remaining skills:
```
Auto-completed:
  ✅ /mn:save — 3 decisions saved
  ✅ /mn:session — session note created

Also recommended:
  1. [CRITICAL] /commit — 5 uncommitted files
  2. [MEDIUM] /mn:connect — 2 new notes, find links?

Run any? (1,2 / A=all / N=skip)
```

## Important Notes

- **Always thorough** — no quick mode, full analysis every time
- **Auto-executes save + session** — no need to run them manually
- **Inline execution** — runs in main conversation context, can invoke other skills
- **BLUF** — score and critical items first, details below
- **Won't nag** — skill already ran this session? Skips it
- **Only recommends installed skills** — never suggests unavailable tools

## Related Skills

- `/mn:save` — auto-invoked by review when unsaved decisions detected
- `/mn:session` — auto-invoked by review when session is significant
- `/mn:health` — review recommends if new notes were created
- `/mn:connect` — review recommends if new notes need linking

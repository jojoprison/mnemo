---
name: session-review
description: "End-of-session orchestrator. Auto-saves decisions (mnemo:memory-routing) and creates session notes (mnemo:session-notes) without asking. Then recommends remaining skills. Triggers on: 'что забыли', 'session review', 'что осталось', 'all done?', 'review', end of significant work. The ONLY command users need at session end — handles everything."
user-invocable: false
model: inherit
---

# mnemo:review — Skill-Aware Session Completeness Analyzer

You are performing a thorough end-of-session review. Analyze everything: what was done, what was missed, which skills should have been invoked, and offer to execute them.

> **Tip:** For deepest analysis depth, run `/model opus[1m]` before `/mn:review` if you're not already on Opus. This skill inherits your session's model (v0.7.3+) so you control the quality/speed trade-off.

## Session Data (Preprocessed)

### Git State

!`echo "=== STATUS ===" && git status --short 2>/dev/null && echo "=== BRANCH ===" && git branch --show-current 2>/dev/null && echo "=== LOG ===" && git log --oneline -10 2>/dev/null && echo "=== UNCOMMITTED ===" && git diff --stat 2>/dev/null && echo "=== STAGED ===" && git diff --staged --stat 2>/dev/null`

### Open PRs

!`gh pr list --author @me --state open --json number,title,url 2>/dev/null || echo "gh: not available"`

### Tools & Skills Used This Session

!`CLAUDE_SESSION_ID='${CLAUDE_SESSION_ID}' CODEX_SESSION_ID='${CODEX_SESSION_ID}' bash -c 'for p in "${CLAUDE_PLUGIN_ROOT}/scripts/session-scan.py" "${CLAUDE_PLUGIN_ROOT}/plugins/mnemo/scripts/session-scan.py" "$HOME/.claude/plugins/cache/jojoprison/mnemo/"*"/plugins/mnemo/scripts/session-scan.py" "$HOME/.claude/plugins/cache/jojoprison/claude-mnemo/"*"/plugins/mnemo/scripts/session-scan.py" "$HOME/.codex/plugins/cache/mnemo/mnemo/"*"/scripts/session-scan.py" "$HOME/.codex/plugins/cache/claude-mnemo/mnemo/"*"/scripts/session-scan.py" "./plugins/mnemo/scripts/session-scan.py"; do [ -f "$p" ] && exec python3 "$p"; done; echo "SESSION_ID: script unavailable"'`

### All Available Skills (Auto-Discovered)

!`bash -c 'for p in "${CLAUDE_PLUGIN_ROOT}/scripts/skills-discover.py" "${CLAUDE_PLUGIN_ROOT}/plugins/mnemo/scripts/skills-discover.py" "$HOME/.claude/plugins/cache/jojoprison/mnemo/"*"/plugins/mnemo/scripts/skills-discover.py" "$HOME/.claude/plugins/cache/jojoprison/claude-mnemo/"*"/plugins/mnemo/scripts/skills-discover.py" "$HOME/.codex/plugins/cache/mnemo/mnemo/"*"/scripts/skills-discover.py" "$HOME/.codex/plugins/cache/claude-mnemo/mnemo/"*"/scripts/skills-discover.py" "./plugins/mnemo/scripts/skills-discover.py"; do [ -f "$p" ] && exec python3 "$p"; done; echo "TOTAL_SKILLS: discover unavailable"'`

$ARGUMENTS

## Workflow

### Step 1: Load Project Context

Read CLAUDE.md for project-specific rules:

```bash
cat CLAUDE.md 2>/dev/null | head -300
```

Check memory index:
```bash
cat .claude/projects/*/memory/MEMORY.md 2>/dev/null | head -100
```

### Step 2: Determine Session Type

Classify by primary activity using preprocessed data + conversation history:

| Type | Key signals |
|------|-------------|
| **Implementation** | Write/Edit heavy, commits, new files, "feat/add" keywords |
| **Research** | Read/Grep/WebSearch/Agent heavy, few writes |
| **Debugging** | Error patterns, "fix" commits, investigation flow |
| **Refactoring** | Renames, large diffs, net-zero line changes |
| **Documentation** | .md files dominant, few code changes |
| **Configuration** | Config/CI/deploy files changed |
| **Planning** | Plan mode, brainstorm docs, no code |

State the detected type explicitly.

### Step 3: Full Session Scan

From conversation history + preprocessed data, identify:

1. **User requests** — all explicit and implicit asks. Were they all fulfilled?
2. **Decisions made** — architecture, approach, scope choices. Were they saved?
3. **Actions completed** — commits, PRs, file changes, deployments
4. **TODOs mentioned** — "потом", "later", "TODO", "FIXME" in conversation or code
5. **Errors encountered** — all resolved? Workarounds or proper fixes?
6. **Questions asked** — by user or Claude, answered or dropped?
7. **External systems** — Linear tasks, GitHub PRs, Obsidian notes — updated?

### Step 4: Skill Gap Analysis

Cross-reference:
- **Session type** (Step 2) → expected skill categories
- **Signals detected** (Step 3) → specific skill triggers
- **Skills already invoked** (preprocessed `SKILLS_INVOKED`)
- **All available skills** (preprocessed auto-discovery)

**Only recommend skills that appear in the auto-discovered list.** Never recommend skills that aren't installed — the user can't act on them.

**Load the matching trigger matrix file explicitly.** Pick `{type}` from the session classification in Step 2 (`implementation`, `research`, `debugging`, or `universal` for refactor / documentation / configuration / planning). Always also load `triggers-universal.md`.

```bash
TYPE={implementation|research|debugging|universal}
REF_DIR="${CLAUDE_PLUGIN_ROOT}/references"
[ -d "$REF_DIR" ] || REF_DIR="$(dirname "$0")/../../references"

echo "=== type-specific triggers ==="
cat "${REF_DIR}/triggers-${TYPE}.md" 2>/dev/null || echo "(triggers file unavailable)"

echo ""
echo "=== universal triggers ==="
cat "${REF_DIR}/triggers-universal.md" 2>/dev/null || echo "(universal file unavailable)"

echo ""
echo "=== project-specific triggers (if any) ==="
cat "${CLAUDE_PLUGIN_ROOT}/skill-triggers.md" 2>/dev/null \
  || cat ".claude/skill-triggers.md" 2>/dev/null \
  || echo "(no custom triggers)"
```

Run this command **before** walking the trigger rows. Progressive disclosure — don't load the other 3 type files when only one applies.

### Step 5: Cross-Reference Project Rules

From CLAUDE.md, check mandatory steps:

| Rule category | What to check |
|---------------|--------------|
| Git flow | PR created? Correct format? Draft or ready? |
| CI checks | Tests run? Lint passing? Type-check? |
| Memory routing | All required backends updated? (Obsidian, claude-mem, memory/) |
| Session handoff | Handoff note updated in Obsidian? |
| Task tracker | Linear/GitHub issue status moved? PR linked? |
| Documentation | README/docs match code changes? |
| Stop-rules | Any project-specific rules violated? |

### Step 6: Generate Report

**Respond in the user's language** (match conversation language).

**BLUF: score first, then details.**

```markdown
## Session Review

**Project:** {name}
**Branch:** {branch}
**Type:** {session type}
**Task:** {one-line summary}

### Done ({count})

| # | What | Evidence |
|---|------|----------|
| 1 | {item} | {commit hash / PR / file path} |

### Missed ({count})

| # | What | Priority | Action |
|---|------|----------|--------|
| 1 | {item} | CRITICAL | {specific action} |

### Hanging Threads ({count})

| # | What | Where mentioned | Next step |
|---|------|----------------|-----------|
| 1 | {item} | {context} | {action} |

### Skill Gap

**Invoked this session:** {list, or "none"}

**Should have been invoked:**

| # | Skill | Why | Priority |
|---|-------|-----|----------|
| 1 | /mnemo:session | Significant work done, no session notes | HIGH |

**Correctly skipped:** {skills matching signals but rightly unused, with reason}

### Score: {X}/10

| Dimension | Status | Detail |
|-----------|--------|--------|
| Code | {status} | |
| Tests | {status} | |
| Memory | {status} | |
| Docs | {status} | |
| PR / Git | {status} | |
| Skills | {used/recommended} | |
```

### Step 7: Auto-Execute Core Skills

After the report, **automatically run** save + session without asking — these are the two skills that matter most and the user expects them to happen.

**Auto-run (no confirmation needed):**

1. **mnemo:memory-routing** (save) — if unsaved decisions/findings detected, extract them and invoke:
   ```
   Skill(skill: "mnemo:memory-routing", args: "{extracted decisions and findings}")
   ```
2. **mnemo:session-notes** (session) — if significant work was done, invoke:
   ```
   Skill(skill: "mnemo:session-notes", args: "")
   ```

**Order matters:** save before session (decisions should be persisted before session note references them).

**Skip auto-run if:** the skill was already invoked this session (per SKILLS_INVOKED preprocessing).

### Step 8: Offer Remaining Skills

For everything else, ask the user:

```
Auto-completed:
  ✅ /mn:save — 3 decisions saved
  ✅ /mn:session — session note created

Also recommended:

  1. [CRITICAL] /commit — 5 uncommitted files
  2. [MEDIUM] /mn:connect — 2 new notes, find links?
  3. [LOW] /mn:health — vault audit after mass creation?

Run any? (1,2,3 / A=all / N=skip)
```

**Execution rules:**
1. Run skills sequentially using the Skill tool
2. Brief status after each
3. Dependency order: /commit before /ship
4. After all done, output updated score

## Rules

- **Always thorough** — full analysis, no shortcuts
- **BLUF** — score and critical items first
- **Be specific** — "3 unsaved decisions: X, Y, Z" not "maybe save something"
- **Don't nag** — skill already ran per SKILLS_INVOKED? Skip it
- **Don't hallucinate skills** — only recommend from auto-discovered list
- **Project rules override** — CLAUDE.md > generic recommendations
- **Execution order** — commit → review → ship → session → save
- **User's language** — match conversation
- **Preprocessing fallback** — if JSONL/discovery failed, gather data with Bash at runtime
- **Don't over-report** — unchecked plan AC is noise if code + tests pass
- **Multiple projects** — analyze each project dir separately
- **Respect completed work** — /mnemo:save already ran? Acknowledge, don't re-recommend

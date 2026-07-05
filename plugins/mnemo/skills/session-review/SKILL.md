---
name: session-review
description: "End-of-session orchestrator. Audits the session, then recommends core skills (mnemo:memory-routing, mnemo:session-notes) and the rest — always asks before running anything, never auto-runs. Triggers on 'что забыли', 'что осталось', 'что ещё осталось', 'что ещё тут осталось', 'session review', 'ревью сессии', 'сессия ревью', 'что добить до идеала', 'all done', end of significant work, or similar. The ONLY command users need at session end — one confirmation covers everything."
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
8. **Actionable rules learned** — any "never do X / always do Y" lesson tied to specific code/paths that a *future agent* must auto-see before repeating the mistake (vs recall "what/why"). These belong in `.claude/rules/<domain>.md` (path-scoped auto-inject), not just recall memory — flag them for Step 8 routing.

### Step 4: Skill Gap Analysis

Cross-reference:
- **Session type** (Step 2) → expected skill categories
- **Signals detected** (Step 3) → specific skill triggers
- **Skills already invoked** (preprocessed `SKILLS_INVOKED`)
- **All available skills** (preprocessed auto-discovery)

**Only recommend skills that appear in the auto-discovered list.** Never recommend skills that aren't installed — the user can't act on them.

**Load the matching trigger matrix file explicitly.** Pick `{type}` from the session classification in Step 2 (`implementation`, `research`, `debugging`, or `universal` for refactor / documentation / configuration / planning). Always also load `triggers-universal.md` (the snippet below skips the second cat when `type` is already `universal`).

```bash
TYPE={implementation|research|debugging|universal}
REF_DIR="${CLAUDE_PLUGIN_ROOT}/references"
[ -d "$REF_DIR" ] || REF_DIR="$(ls -d "$HOME/.claude/plugins/cache/"*"/mnemo/"*"/plugins/mnemo/references" 2>/dev/null | head -1)"
[ -d "$REF_DIR" ] || REF_DIR="$(ls -d "$HOME/.codex/plugins/cache/"*"/mnemo/"*"/references" 2>/dev/null | head -1)"
[ -d "$REF_DIR" ] || REF_DIR="./plugins/mnemo/references"

echo "=== type-specific triggers ==="
cat "${REF_DIR}/triggers-${TYPE}.md" 2>/dev/null || echo "(triggers file unavailable)"

echo ""
# Skip if TYPE is already 'universal' (loaded above) — avoid double-cat of the same file
if [ "$TYPE" != "universal" ]; then
  echo "=== universal triggers ==="
  cat "${REF_DIR}/triggers-universal.md" 2>/dev/null || echo "(universal file unavailable)"
fi

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
| Graph integrity | `obsidian unresolved`/`orphans` — **advisory** if notes were created this session (CLI cache lags writes 1-5s & can show a note resolved+broken at once; use `metadataCache` eval for truth — see `${CLAUDE_PLUGIN_ROOT}/references/gotchas.md`). Don't raise false CRITICAL on fresh notes |
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
| 1 | /mn:session | Significant work done, no session notes | HIGH |

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

### Step 7: Prepare Core Skill Candidates (no auto-run)

**Never invoke save or session yourself without confirmation** — every skill run goes through the Step 8 offer. Here, only prepare the two core candidates with specific payloads so the offer is concrete ("3 decisions: X, Y, Z", not "maybe save something"):

1. **mnemo:memory-routing** (save) — if unsaved decisions/findings are detected, extract them now and stage the invocation for Step 8:
   ```
   Skill(skill: "mnemo:memory-routing", args: "{extracted decisions and findings}")
   ```
2. **mnemo:session-notes** (session) — if significant work was done, stage it (a research / exploration / personal-curiosity session counts as significant — never skip it for being "just curiosity" or "no code produced"):
   ```
   Skill(skill: "mnemo:session-notes", args: "")
   ```

**Order matters:** save before session (decisions should be persisted before the session note references them) — keep that order in the offer and in execution.

**Actionable rules get their own line item.** When a save would route an actionable rule into `.claude/rules/` (memory-routing Step 3.5 — it **creates/edits committed project files**, not just a recall note), surface it as a separate entry in Step 8 ("found an actionable rule → put it in `.claude/rules/<domain>` so it auto-injects? y/n") — never bundle it silently into a recall save.

**Drop a candidate if:** the skill was already invoked this session (per SKILLS_INVOKED preprocessing) — acknowledge it in the report instead of re-offering.

### Step 8: Offer Skills

Present everything — core candidates from Step 7 first among equals, sorted by priority — and ask:

```
Recommended:

  1. [CRITICAL] /commit — 5 uncommitted files
  2. [HIGH] /mn:save — 3 unsaved decisions (X, Y, Z)
  3. [HIGH] /mn:session — significant work, no session note yet
  4. [HIGH] .claude/rules — 1 actionable rule learned ("gate Kontur on the flag") → route to .claude/rules/te5-frontend.md (auto-inject)?
  5. [MEDIUM] /mn:connect — 2 new notes, find links?
  6. [LOW] /mn:health — vault audit after mass creation?

Run any? (1,2,3... / A=all / N=skip)
```

When the user accepts a `.claude/rules` routing offer, invoke memory-routing with the extracted rule so Step 3.5 handles the file create/append (don't hand-write the file from here — keep one code path):

```
Skill(skill: "mnemo:memory-routing", args: "{the actionable rule, phrased as a never-X/always-Y instruction tied to its code paths}")
```

**Execution rules:**
1. Run skills sequentially using the Skill tool
2. Brief status after each
3. Dependency order: /commit before /ship
4. After all done, output updated score

## Rules

- **Always thorough** — full analysis, no shortcuts
- **No auto-run** — never invoke another skill without the user's explicit pick in Step 8; analysis is free, execution is confirmed
- **BLUF** — score and critical items first
- **Be specific** — "3 unsaved decisions: X, Y, Z" not "maybe save something"
- **Don't nag** — skill already ran per SKILLS_INVOKED? Skip it
- **Don't hallucinate skills** — only recommend from auto-discovered list
- **Project rules override** — CLAUDE.md > generic recommendations
- **Execution order** — commit → review → ship → save → session (save before session: decisions persist before the session note references them — matches Step 7)
- **User's language** — match conversation
- **Preprocessing fallback** — if JSONL/discovery failed, gather data with Bash at runtime
- **Don't over-report** — unchecked plan AC is noise if code + tests pass
- **Multiple projects** — analyze each project dir separately
- **Respect completed work** — /mn:save already ran? Acknowledge, don't re-recommend

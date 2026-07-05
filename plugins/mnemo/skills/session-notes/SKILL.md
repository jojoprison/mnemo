---
name: session-notes
description: "Use when significant work wraps up — a feature shipped, a bug fixed, a research thread finished, before the user steps away — and also mid-task as a checkpoint before a long run risks context compaction (it updates the same session note + handoff, never spawns a duplicate). Also on 'записать сессию', 'сохрани сессию', 'отложи сессию в память', 'сессию в обсидиан', 'закругляйся с сессией', 'session note', 'handoff', or similar. Writes a human-readable summary plus a handoff so the next session picks up where you left off."
user-invocable: false
model: inherit
---

# mnemo:session — Session Notes to Obsidian

Create a human-readable session summary note in Obsidian after significant work.

## Prerequisites & config

Obsidian must be open. Config at `~/.mnemo/config.json` — reads `vault`, `taxonomy.session`, `links_section`, `handoff_note`. Schema in `${CLAUDE_PLUGIN_ROOT}/references/config-schema.md`.

Tool-routing (MCP for writes, CLI for reads/search) in `${CLAUDE_PLUGIN_ROOT}/references/tool-routing.md`. Frontmatter template in `assets/session-template.md`.

## When to Trigger

- After completing a feature / PR / fix
- After significant research session
- Manually via `/mn:session`
- Do NOT trigger for trivial tasks (typo fix, one-liner). Research / exploration / personal-curiosity sessions are **NOT** trivial — they get a note even with zero code. When unsure, create: a session note is cheap, a lost session is not.

## Workflow

### Step 1: Summarize Current Session

Analyze the conversation: what was done, key decisions, commits/PRs created, findings.

Derive a **planned filename**: `{session_prefix}{YYYY-MM-DD} {short descriptive topic}`. Topic should be specific enough to disambiguate from other sessions the same day (include PR number, Linear ticket, branch name, or primary keyword).

**Naming:** the topic must NOT contain `#`, `.`, or `/` — they break wikilinks (`#`→heading anchor) or the CLI (`.`→truncation). Write `PR 387`, not `PR #387`. See `${CLAUDE_PLUGIN_ROOT}/references/tool-routing.md` (naming rules).

### Step 2: Duplicate Check (two-level, parallel)

**Run Level 1 and Level 2 in parallel — single assistant message with two Bash tool uses.** ~185ms total instead of ~370ms sequential.

**Level 1 — exact filename:**

```bash
obsidian read file="{planned-filename}" vault="{vault}" 2>/dev/null | head -5
```

If the read returns content → a note with this EXACT filename already exists. Do NOT silently skip and do NOT auto-overwrite. Offer **append / overwrite / rename**, leading with append/continuation. To append, use `mcp__obsidian__insert` (at the file's last line) or `mcp__obsidian__str_replace` to add a `## part 2` / `## continuation` section — NOT `mcp__obsidian__create` (it only creates new files and will fail or clobber an existing one). Overwrite only if the user is clearly regenerating the same session.

**Level 2 — related same-day sessions (informational only):**

```bash
obsidian search query="{session_prefix}{YYYY-MM-DD}" vault="{vault}"
```

These are NOT duplicates — same day, different topics. **Doing many sessions in one day is normal: each distinct topic gets its OWN note. A Level-2 same-day match is context, NOT a reason to skip creation or to assume the note already exists** — that mistake silently loses sessions. Show the list to the user so they can:
- Decide if this session should be merged into an existing one
- Remember to cross-link related sessions via `## Связи` / `## Links`

Do not block creation on Level 2 matches — they're context, not conflicts.

### Step 3: Create Session Note (MCP — primary; Codex fallback below)

**In Claude, always use `mcp__obsidian__create` for creation.** Never CLI with inline `content=` (shell-injection). In Codex, where the Obsidian MCP isn't available, take the **Codex fallback** at the end of this step instead — the inline-`content=` ban still holds there.

First, read the template (provides the exact structure to follow):

```bash
cat "${CLAUDE_PLUGIN_ROOT}/assets/session-template.md" 2>/dev/null \
  || cat "$(ls -d "$HOME/.claude/plugins/cache/"*"/mnemo/"*"/plugins/mnemo/assets/session-template.md" 2>/dev/null | head -1)"
```

Then create the note, filling the template placeholders (`{Session Title}`, `{YYYY-MM-DD}`, `{project}`, etc.) with the current session's context:

```
mcp__obsidian__create(
  path: "{planned-filename}.md",
  file_text: "<template with placeholders filled in>"
)
```

Where `{session_prefix}` comes from `config.taxonomy.session.prefix`, `{links_section}` from `config.links_section`, and the session id from `{CLAUDE_SESSION_ID}` — or `{CODEX_SESSION_ID}` under Codex — in the environment (empty string if neither is available).

**Why MCP here:** frontmatter and body may contain any markdown — code blocks with backticks, `$(...)` samples, shell snippets. MCP passes `file_text` as a JSON parameter; no shell involved.

**Codex fallback (no Obsidian MCP, no safe CLI create):** the human-readable Obsidian note is a Claude-path deliverable, and there is no shell-safe way to create it with a markdown body from Codex. So instead of failing silently or running an unsafe inline `content=`, write the filled summary to the local fallback memory — `~/.codex/memories/session-{YYYY-MM-DD}-{HHMM}.md` (include the time so two sessions the same day don't overwrite each other) — and tell the user the full vault note needs a Claude/Obsidian session. This degrades gracefully and preserves the content.

### Step 4: Verify MOC Link

**Read MOC (CLI — safe, read-only):**

```bash
obsidian read file="{MOC name}" vault="{vault}"
```

Check if the new session note is listed.

**If missing — append link (MCP preferred):**

```
mcp__obsidian__str_replace(
  path: "{MOC name}.md",
  old_str: "{some stable anchor line near the session list}",
  new_str: "{same anchor}\n- [[{session note name}]]"
)
```

Alternatively, if the MOC has a predictable append point, use `mcp__obsidian__insert` with a line number.

**CLI fallback (only if link text has no backticks/`$()`):** `obsidian append file="{MOC}" content="- [[{name}]]"` — a plain wikilink is safe, but prefer MCP for consistency.

### Step 5: Update Session Handoff

**Read handoff (CLI — safe):**

```bash
obsidian read file="{handoff_note}" vault="{vault}"
```

**Update with MCP `str_replace` — targeted, not blind append:**

- Remove completed pending items from previous sessions
- Add new pending items from current session (if any)
- Update context carry-over section

```
mcp__obsidian__str_replace(
  path: "{handoff_note}.md",
  old_str: "{old section content}",
  new_str: "{updated section content}"
)
```

If handoff note doesn't exist, create it via `mcp__obsidian__create` (same structure as `initial-setup` Step 6).

### Step 6: Orphan Check

```bash
obsidian orphans vault="{vault}"
```

If the newly created note appears in orphans, it means no `## Связи` links or the MOC didn't get updated.

⚠️ **`obsidian orphans` caches & lags writes 1-5s** — a note created moments ago via MCP may show as orphan falsely. If it appears right after creation, wait 2-3s and re-run, or verify authoritatively via `obsidian eval` (`metadataCache.resolvedLinks`/`unresolvedLinks`). See `${CLAUDE_PLUGIN_ROOT}/references/gotchas.md`.

### Step 7: Confirm

Output summary:
- Note name
- MOC updated (yes/no)
- Handoff updated (yes/no)
- Orphan status (clean / flagged)

## Rules

- **MCP for any write with markdown body** — non-negotiable, shell-safety
- **CLI for read/search/index** — faster, indexed, unique functions
- **No inline `obsidian create content="..."` with markdown** — banned: zsh expands backticks / `$(...)` in the body (real incident: nearly ran `make deploy-back`)
- **Two-level duplicate check** — exact-read + same-day-search
- **Include session_id in frontmatter** — disambiguates same-day sessions
- **No session notes for trivial work** — but "trivial" = mechanical one-liners only (typo, single rename). A research / exploration / curiosity session counts as significant even with zero code; default to creating.
- **Branch field optional** — research sessions don't have branches
- **Handoff file: targeted `str_replace`, not blind append** — pending items shouldn't accumulate infinitely
- **Links section is mandatory** — at least one MOC link, else the note orphans (invisible to graph navigation)
- **Ghost notes generously** — wrap projects, technologies, people in `[[wikilinks]]`

## Gotchas

Common failures (IPC hung, shell injection) in `${CLAUDE_PLUGIN_ROOT}/references/gotchas.md`. Skill-specific rules:

- **MCP `create` signature**: `path` (not `name`), `file_text` (not `content`). Path is relative to vault root, include `.md` extension.
- **Always check duplicate before creating** — prevents clobbering same-day work. Two-level check in Step 2.
- **`str_replace` requires exact match** — copy the anchor text verbatim from read output, including whitespace.

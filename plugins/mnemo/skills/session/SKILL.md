---
name: session
description: "Use when significant work wraps up — a feature shipped, a bug fixed, a research thread finished, before the user steps away — and also mid-task as a checkpoint before a long run risks context compaction (it updates the same session note + handoff, never spawns a duplicate). Also on 'записать сессию', 'сохрани сессию', 'отложи сессию в память', 'сессию в обсидиан', 'закругляйся с сессией', 'session note', 'handoff', or similar. Writes a human-readable summary plus a handoff so the next session picks up where you left off."
model: inherit
---

# mn:session — Session Notes to Obsidian

> **Invocation marker (both runtimes):** begin your reply with the exact line `🧠 mn:session (mnemo) → running` — the user-visible confirmation that this skill actually loaded. Emit it once per invocation, before any other output.

## Portable paths

Resolve `<mnemo-root>` once to the absolute plugin root before reading bundled files or running bundled scripts. In Claude Code, use `${CLAUDE_PLUGIN_ROOT}`; in Codex, derive it from this loaded `SKILL.md` path (skill directory → `skills/` → plugin root). Replace `<mnemo-root>` with that quoted absolute path in every command — never execute the placeholder literally and never hunt versioned cache directories.

When another mnemo skill must run, use the runtime-native path: Claude Code invokes `mn:<skill>` through its Skill tool; Codex reads `<mnemo-root>/skills/<skill>/SKILL.md` completely and follows it with the prepared input. For user-facing explicit syntax, render `/mn:<skill>` in Claude Code and `$mnemo:<skill>` in Codex.

Create a human-readable session summary note in Obsidian after significant work.

## Prerequisites & config

Obsidian must be open. Config at `~/.mnemo/config.json` — reads `vault`, `taxonomy`, `taxonomy_roles`, `links_section`, and `handoff_note`. Before resolving session or hub destinations, require exactly the five role keys `fact`, `insight`, `source`, `session`, and `moc`; require every target to exist in `taxonomy`; and require `session → session` plus `moc → moc`. The deterministic legacy Zettelkasten fallback is allowed; any other missing/invalid map offers the runtime-native setup skill instead of guessing. Schema in `<mnemo-root>/references/config-schema.md`.

Tool-routing (bundled atomic writer for writes, bundled CLI adapter for reads/search) is in `<mnemo-root>/references/tool-routing.md`. Frontmatter template is in `<mnemo-root>/assets/session-template.md`.

## When to Trigger

- After completing a feature / PR / fix
- After significant research session
- Manually via the current runtime's explicit form (`/mn:session` in Claude Code, `$mnemo:session` in Codex)
- Do NOT trigger for trivial tasks (typo fix, one-liner). Research / exploration / personal-curiosity sessions are **NOT** trivial — they get a note even with zero code. When unsure, create: a session note is cheap, a lost session is not.

## Workflow

### Step 1: Summarize Current Session

**Mid-task checkpoint vs end-of-session note.** If this is a mid-task checkpoint (a long run risks compaction and you're saving progress, not wrapping up) **and** a note for *this same session* already exists — match by the `session_id` you'd write in frontmatter (or the filename derived earlier this session) — **update that note in place** through the bundled exact-replace/insert writer plus refresh the handoff (Step 5). Do **not** create a second note for the same session — that fragments the record. Only a genuinely new session or a distinct topic gets a new note.

Analyze the conversation: what was done, key decisions, commits/PRs created, findings.

**Thoroughness by routing (standing default).** A good session note is thorough by *routing* material to its right home, not by swelling this one note: the narrative + arc + decisions-in-context live here; business-logic / pains / how-the-user-thinks route to `save`'s typed `principle` / `pain` / `stance` atoms; connections go to `connect`; unfinished threads become handoff `- [ ]` items. Full contract: `<mnemo-root>/references/depth-contract.md`. Depth = structure, not volume — never fold "capture everything" into the narrative (that is the blob anti-pattern).

**Ground the summary in facts — don't rely on conversation memory alone** (a note that claims "shipped X" when git shows no such commit is worse than no note). Before writing "what was done", cross-check against reality: `git log --oneline -15` + `git status --short` for real commits/changes, and — when the script is reachable — the session's actual tool/skill activity:

```bash
python3 "<mnemo-root>/scripts/session-scan.py" 2>/dev/null | head -30
```

Reconcile claimed outcomes with these before persisting — the same grounding the canonical `review` skill performs, applied to the note this `session` skill writes directly.

Derive a **planned filename**: `{session_prefix}{YYYY-MM-DD} {short descriptive topic}`. Topic should be specific enough to disambiguate from other sessions the same day (include PR number, Linear ticket, branch name, or primary keyword).

**Naming:** the topic must NOT contain `#`, `.`, or `/` — they break wikilinks (`#`→heading anchor) or the CLI (`.`→truncation). Write `PR 387`, not `PR #387`. See `<mnemo-root>/references/tool-routing.md` (naming rules).

### Step 2: Duplicate Check (two-level, parallel)

**Run Level 1 and Level 2 in parallel — single assistant message with two shell tool uses.** Use the bundled shell-free helper with quoted JSON heredocs. ~185ms total instead of ~370ms sequential.

**Level 1 — exact filename:**

```bash
python3 "<mnemo-root>/scripts/safe-read.py" read <<'JSON'
{"file":"{planned-filename}","vault":"{vault}"}
JSON
```

If the read returns content → a note with this EXACT filename already exists. Do NOT silently skip and do NOT auto-overwrite. Offer **append / overwrite / rename**, leading with append/continuation. For continuation use `vault-write.py insert` with a unique copied anchor, or guarded `append` with the exact current tail/hash. Never call `create` for an existing note. Overwrite only if the user is clearly regenerating the same session, and implement it as an exact optimistic replacement rather than a blind file write.

**Level 2 — related same-day sessions (informational only):**

```bash
python3 "<mnemo-root>/scripts/safe-read.py" search <<'JSON'
{"query":"{session_prefix}{YYYY-MM-DD}","vault":"{vault}"}
JSON
```

These are NOT duplicates — same day, different topics. **Doing many sessions in one day is normal: each distinct topic gets its OWN note. A Level-2 same-day match is context, NOT a reason to skip creation or to assume the note already exists** — that mistake silently loses sessions. Show the list to the user so they can:
- Decide if this session should be merged into an existing one
- Remember to cross-link related sessions via `## Связи` / `## Links`

Do not block creation on Level 2 matches — they're context, not conflicts.

### Step 3: Create Session Note (same writer in both runtimes)

After the exact role-map validation in Prerequisites, resolve `taxonomy_roles.session` and `taxonomy_roles.moc` to existing `config.taxonomy` entries and use their configured prefixes/tags. Legacy Zettelkasten without a role map uses the documented deterministic fallback; any other missing/invalid map must go through `setup` rather than guessing.

First, read the template (provides the exact structure to follow):

```bash
cat "<mnemo-root>/assets/session-template.md"
```

Then create the note, filling every template placeholder with grounded current-session context. In particular, `{session_type}` and `{session_tag}` come from the taxonomy entry mapped by `taxonomy_roles.session`; `{mapped_moc_note}` uses the prefix from the entry mapped by `taxonomy_roles.moc`; `{session_id}` is runtime-neutral; and `{topic_tags}` contains only validated YAML-safe tag values:

```bash
python3 "<mnemo-root>/scripts/vault-write.py" <<'JSON'
{"action":"create","vault":"{vault}","note":"{planned filename}","content":"{one JSON-escaped Markdown string with the filled template}"}
JSON
```

Where `{session_prefix}` comes from the taxonomy entry mapped by `taxonomy_roles.session`, `{links_section}` from `config.links_section`, and the session id comes from `CLAUDE_SESSION_ID` in Claude Code or `CODEX_THREAD_ID` in Codex (`CODEX_SESSION_ID` remains a legacy fallback; use an empty string if none is available).

The helper receives Markdown through JSON stdin, never shell syntax or Obsidian CLI argv. It verifies vault containment and performs an exclusive atomic create, so backticks, `$(...)`, quotes, and code blocks remain inert. On `conflict`, re-read and use the duplicate flow; never overwrite.

**Codex memory ownership:** `${CODEX_HOME:-~/.codex}/memories/` is Codex-generated state. Never create, edit, append, or use it as a session-note fallback. If the vault is unavailable, report the failed durable write and retain the summary in the current response so the user can retry; do not create a shadow copy.

### Step 4: Verify MOC Link

**Read MOC through the shell-free CLI adapter:**

```bash
python3 "<mnemo-root>/scripts/safe-read.py" read <<'JSON'
{"file":"{MOC name}","vault":"{vault}"}
JSON
```

Check if the new session note is listed.

**If missing — insert through the same optimistic writer:**

```bash
python3 "<mnemo-root>/scripts/vault-write.py" <<'JSON'
{"action":"insert","vault":"{vault}","note":"{mapped moc note}","anchor":"{unique stable anchor copied from read}","position":"after","content":"\n- [[{session note name}]] — session context"}
JSON
```

If the anchor is missing/non-unique or the file changes during publication, re-read and retry. Never use inline CLI content.

### Step 5: Update Session Handoff

**Read handoff through the shell-free CLI adapter:**

```bash
python3 "<mnemo-root>/scripts/safe-read.py" read <<'JSON'
{"file":"{handoff_note}","vault":"{vault}"}
JSON
```

**Update with `vault-write.py replace/insert` — targeted, not blind append:**

- Remove completed pending items from previous sessions
- Add new pending items from current session (if any)
- Update context carry-over section

```bash
python3 "<mnemo-root>/scripts/vault-write.py" <<'JSON'
{"action":"replace","vault":"{vault}","note":"{handoff_note}","old_str":"{exact old section copied from read}","new_str":"{updated section as one JSON-escaped string}"}
JSON
```

If the handoff note does not exist, create it via `vault-write.py create` with the same structure as `setup` Step 6.

**Size-guard — keep the handoff thin (run every session):**

The handoff is a LIVE index, not an archive. After updating it, run the archival helper so closed history doesn't accumulate into a multi-MB token bomb (it no-ops when the note is at/under `handoff.maxKB`):

```bash
python3 "<mnemo-root>/scripts/vault-write.py" <<'JSON'
{"action":"archive-handoff","vault":"{vault}","note":"{handoff_note}","max_kb":40,"keep_days":14}
JSON
```

Replace `40` and `14` with the configured integer values when present.

Keeps HOT: entries with an open `- [ ]` + the last `keepDays`. Moves CLOSED older entries verbatim to `{handoff_note} Archive` (cold, not read at session start; a unique `.bak-<date>` is written for undo). Archive-first publication and retry deduplication prevent loss across partial failures; the handoff/archive replacements use the same optimistic atomic writer as every other vault edit. Their durable detail already lives in the linked session notes. If the vault path can't be resolved (Obsidian absent), skip and report it.

### Step 6: Orphan Check

```bash
python3 "<mnemo-root>/scripts/safe-read.py" orphans <<'JSON'
{"vault":"{vault}"}
JSON
```

If the newly created note appears in orphans, it means no `## Связи` links or the MOC didn't get updated.

⚠️ **`obsidian orphans` caches & lags writes 1-5s** — a freshly written note may show as orphan falsely. If it appears right after creation, wait 2-3s and re-run, or verify authoritatively via `obsidian eval` (`metadataCache.resolvedLinks`/`unresolvedLinks`). See `<mnemo-root>/references/gotchas.md`.

### Step 7: Confirm — with an own-note self-check

Before the summary, self-verify **this note's own artifact** (not a cross-skill audit — that is `review --full` Step 9): reusing Steps 2 / 4 / 6, reconfirm it is not a duplicate of today's session, its `## Связи` carries the mapped MOC link, it is non-orphan, and any atom-worthy material was delegated to `save` rather than folded in. Report residual own-note gaps.

Output summary:
- Note name
- MOC updated (yes/no)
- Handoff updated (yes/no)
- Orphan status (clean / flagged)
- Own-note self-check (clean / gaps: {list})

## Rules

- **`vault-write.py` for every vault write** — one shell-free, atomic path in both runtimes
- **CLI for read/search/index** — faster, indexed, unique functions
- **No inline `obsidian create content="..."` with markdown** — banned: zsh expands backticks / `$(...)` in the body (real incident: nearly ran `make deploy-back`)
- **Two-level duplicate check** — exact-read + same-day-search
- **Include session_id in frontmatter** — disambiguates same-day sessions
- **No session notes for trivial work** — but "trivial" = mechanical one-liners only (typo, single rename). A research / exploration / curiosity session counts as significant even with zero code; default to creating.
- **Branch field optional** — research sessions don't have branches
- **Handoff = thin live index, not an archive** — targeted optimistic replacement, not blind append. Named ceiling: when it exceeds `handoff.maxKB` (default 40KB), `vault-write.py archive-handoff` (Step 5) rotates CLOSED blocks older than `handoff.keepDays` into `{handoff_note} Archive` (cold); open `- [ ]` + recent stay hot. Prevents multi-MB token-bomb accumulation without a second writer.
- **Links section is mandatory** — at least one MOC link, else the note orphans (invisible to graph navigation)
- **Ghost notes generously** — wrap projects, technologies, people in `[[wikilinks]]`
- **Thorough by routing, not volume** — the note stays a narrative; atom-worthy material (decisions, business-logic, pains, how-the-user-thinks) goes to `save`, links to `connect`, unfinished work to handoff. Full contract in `<mnemo-root>/references/depth-contract.md`
- **Own-note self-check only** — Step 7 verifies this note's own artifact (dup / MOC / orphan / delegation); the cross-skill palace audit belongs to `review --full`, not here

## Gotchas

Common failures (IPC hung, shell injection) in `<mnemo-root>/references/gotchas.md`. Skill-specific rules:

- **Writer contract:** `note` is vault-relative (`.md` optional); `create` fails if the target exists; `replace` requires exactly one `old_str`; `insert` requires exactly one anchor; guarded append requires an expected tail/hash.
- **Always check duplicate before creating** — prevents clobbering same-day work. Two-level check in Step 2.
- **Exact matching means exact whitespace** — copy the anchor/old section verbatim from read output.

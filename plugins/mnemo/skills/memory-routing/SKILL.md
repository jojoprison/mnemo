---
name: memory-routing
description: "Use whenever the user says 'remember this', 'save to memory', 'save this', 'запомни', 'запоминай', 'сохрани', 'помни', 'отложи в память', 'в память', 'в памяти', 'в мнемо', solved a bug worth remembering, made a non-obvious decision, or learned a gotcha. Routes each item to Obsidian + optional claude-mem + memory/ + CLAUDE.md with graceful degradation if a backend is unavailable."
user-invocable: false
model: inherit
---

# mnemo:save — Memory Routing Cascade

Save information to multiple memory backends with graceful degradation. Each backend is tried independently — if one fails, others still work.

## Prerequisites & config

Obsidian is preferred but not required (skill degrades gracefully). Config at `~/.mnemo/config.json` — full schema including `cascade.*` toggles in `references/config-schema.md`.

## Workflow

### Step 0: Classify the Input

Determine what type of information is being saved:

| Type | Goes to | Example |
|------|---------|---------|
| **fact** | Obsidian Atom + optional claude-mem | "Heroku standard-0 has 25 auto-backups" |
| **insight** | Obsidian Molecule + optional claude-mem | "CLI-first is 70,000x cheaper because of token savings" |
| **decision** | Obsidian Atom + optional claude-mem + memory/ | "We chose SCOPE over TextGrad for self-correction" |
| **gotcha** | Obsidian Atom + memory/ + possibly CLAUDE.md | "execSync with shell=true is banned in antomate" |
| **source** | Obsidian Source + optional claude-mem | External article, tool, research finding |
| **rule** | CLAUDE.md (if error-preventing) + memory/ | "Never mark Gmail as read without explicit request" |

### Step 1: Obsidian (Primary — for the user)

**Skip if:** `cascade.obsidian.enabled` is false, or Obsidian CLI returns "Unable to connect"

```bash
obsidian search query="{key words}" vault="{vault}"
```

If duplicate found → ask: update existing or create new?

**Create note — MCP (shell-safe for markdown with code blocks):**

```
mcp__obsidian__create(
  path: "{type_prefix}{descriptive title}.md",
  file_text: """---
type: {type}
tags: [{type}, {topic_tags}]
date: {YYYY-MM-DD}
source: "{where this came from}"
---

# {type_prefix}{title}

{content}

{links_section}
- [[{relevant MOC}]]
- [[{ghost notes for entities}]]
"""
)
```

**Why MCP:** content may contain code blocks with backticks or `$(...)` — CLI `obsidian create content="..."` would trigger zsh command substitution. See `references/tool-routing.md` for the full rule.

**Note quality rules** (details + tables in `references/tool-routing.md`):
- **Naming:** never `#` / `.` / `/` / `.md` in the title — they break wikilinks (`#`→heading anchor) or the CLI (`.`→truncation). Sanitize before `create`. Use `—` or space.
- **Atom title = a statement, not a topic** (Matuschak «title as API» / Умэсао): `Atom — Redis fail-open keeps reads alive when cache is down`, NOT `Atom — Redis`.
- **Molecule = non-trivial synthesis** of ≥2 atoms (new insight not in either alone), not "linked two notes."
- **Molecule handed off with `cites:` (e.g. from `/mn:ask` compounding):** when the caller passes `type: molecule` plus a `cites:` source list and a pre-built `{links_section}`, write `cites: [{sources}]` into frontmatter (right after `date:`) and use the caller's links block verbatim instead of generating a bare MOC link.
- **Two link layers:** inline with context in the body («contradicts [[X]]», «builds on [[Y]]») + `{links_section}` for MOC/nav. A bare link without context is noise.
- **Short project names** (`[[Diadoc]]`, `[[BTS Holding]]`) need a **hub note** — Obsidian doesn't resolve bare links via alias (by design). If `[[ShortName]]` is referenced and no `ShortName.md` exists, create it: a one-liner redirecting to `[[MOC — …]]`.
- **Staleness is type-driven, not stamped here.** The `date` you write *is* the review anchor — `vault-health` derives review cadence from the note's `type` (config `review.staleDays`), so you don't add a review date. **Exception:** for a fast-rotting fact (a volatile API quirk, a "current as of" price) add an optional `ttl: <days>` to the frontmatter to age it faster than its type default. Don't add `reviewed:` — that's the snooze health/the user stamps later. See `references/config-schema.md` → "Optional per-note frontmatter".

**Add to MOC — MCP `str_replace` for targeted insert, or CLI for plain wikilinks:**

```
mcp__obsidian__str_replace(
  path: "{MOC}.md",
  old_str: "{stable anchor line near list}",
  new_str: "{same anchor}\n- [[{note name}]]"
)
```

CLI fallback for plain wikilink appends (safe — no backticks):

```bash
obsidian append file="{MOC}" vault="{vault}" content="- [[{note name}]]"
```

**On error:** Log `⚠️ Obsidian: skipped (not connected)`, continue to next backend.

### Step 2: claude-mem (Optional Semantic Search — cross-session recall)

**Skip if:** `cascade.claude_mem.enabled` is false. This is the default in new installs because many users intentionally disable claude-mem for CPU/RAM reasons.

Auto-detect the installed claude-mem version so observations carry provenance (useful when filtering pre-v12 data from post-v12 data):

```bash
CM_VERSION=$(ls -1 ~/.claude/plugins/cache/thedotmack/claude-mem/ 2>/dev/null | sort -V | tail -1)

# Build the observation text with embedded provenance (see "v12.3.9 gotcha" below).
SUMMARY="{one-line summary of what was saved}"
TEXT="${SUMMARY} [note: {note name if created} | vault: {vault} | cm: ${CM_VERSION:-unknown}]"

curl -s -X POST http://{claude_mem_url}/api/memory/save \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"${TEXT}\",
    \"metadata\": {
      \"type\": \"{type}\",
      \"project\": \"{current project or 'general'}\",
      \"obsidian_note\": \"{note name if created}\",
      \"obsidian_vault\": \"{vault}\",
      \"claude_mem_version\": \"${CM_VERSION:-unknown}\"
    }
  }"
```

**API field name (v12.3.9):** the request body key is `text`, not `content`. Earlier versions accepted `content`; as of v12.3.9 the API returns `{"error": "text is required and must be non-empty"}` if you send `content`. Confirmed during v0.7.3 smoke test — verified in claude-mem source.

**v12.3.9 metadata gotcha — custom fields are dropped silently.** POST returns `{"success": true, "id": ...}` but the stored observation only persists `text` + API-generated fields (`type`, `title`, `narrative`, `facts`, `concepts`, `content_hash`, `created_at`, ...). Custom `metadata.*` entries (including `project`, `obsidian_note`, `obsidian_vault`, `claude_mem_version`) are **not** retrievable from the observation record. The `project` field on the stored record is forced to the calling plugin's project (`claude-mem`), not `metadata.project`.

**Workaround (used above):** embed the key provenance fields (note name, vault, CM version) directly into `text` as a bracketed tail. Losing structured filtering hurts less than losing the data entirely — full-text search still finds the provenance. Keep the `metadata: {...}` block in the POST anyway so recovery is automatic once upstream fixes drop-silent behavior. Track upstream: [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem/issues) — search for `metadata` / `project override`.

**Why `obsidian_note` + `obsidian_vault`:** once upstream restores metadata persistence, `claude-mem search` results can link back to the full Obsidian note. Future `/mn:ask --deep` will show a direct wikilink alongside the observation.

**Why `claude_mem_version`:** v11.0.1 disabled semantic-inject by default, v12.0.0 introduced the file-read gate. Tagging observations by version lets retrieval logic filter legacy entries when needed.

**On error:** Log `⚠️ claude-mem: skipped (port {port} not responding)`, continue. Do not start ChromaDB or the claude-mem worker automatically.

### Step 3: memory/ (For Claude — error prevention)

**Skip if:** `cascade.memory_dir.enabled` is false

Only write here if the information **prevents the coding agent from making errors** in future sessions:
- Gotchas, commands, conventions
- NOT business context (that's Obsidian's job)

**Path resolution:**
- Claude Code: `~/.claude/projects/-{slugified-cwd}/memory/`, **not** `./memory/` in the project root.
- Codex: `~/.codex/memories/`.

Find the correct Claude path by reading the `MEMORY.md` already loaded in the conversation context when available. Use `~/.claude/memory/` only for cross-project Claude rules. See `references/gotchas.md` for why this matters.

**How to write — keep the index lean (autodream discipline):**

`memory/` is two layers: **topic files** (the detail) + **`MEMORY.md`** (a lean index — a table `| File | Read when… |`, one short "Read when…" row of recall triggers per topic, ≤~200 chars). Never dump prose into `MEMORY.md` — a bloated index gets **truncated on load** and old entries become invisible to Claude.

1. Write the detail to a **topic file** (`{topic}.md`) — create or update it.
2. Add/refresh **one thin index row** in `MEMORY.md` pointing to it (link + "Read when…" triggers: names / IDs / PR# / domain terms). Never a paragraph.
3. If `MEMORY.md` links a **`MEMORY-archive-index.md`** at the top, aged/older rows live there — add aged rows there (not the lean index) and read it when recalling old context.

The index is periodically re-slimmed by **autodream** (memory consolidation). Full 4-phase procedure + no-loss rules: `~/.claude/memory/autodream-principles.md`.

**On error:** Log `⚠️ memory/: skipped (directory not found)`, continue.

### Step 4: CLAUDE.md (Only critical error-preventing rules)

**Skip if:** `cascade.claude_md.enabled` is false (default)

Only write here if the rule is:
- 1-2 lines max
- Violation would cause a real error or bad behavior
- Not already covered by Obsidian or memory/

This is almost never needed. Most things go to Obsidian + claude-mem.

### Step 5: Report

```
💾 Memory saved:

Content: "{short summary}"
Type: {atom/molecule/source/decision/gotcha}

Backends:
  1. Obsidian  ✅ → "Atom — {title}" in MOC — {name}
  2. claude-mem ⏭  skipped (disabled)
  3. memory/   ⏭  skipped (not error-preventing)
  4. CLAUDE.md ⏭  skipped (not critical rule)
```

Or with failures:

```
💾 Memory saved (partial):

  1. Obsidian  ⚠️ skipped (not connected — restart Obsidian)
  2. claude-mem ⏭  skipped (disabled)
  3. memory/   ✅ → ~/.claude/memory/topic.md updated

⚠️ Run /mn:save again after restarting Obsidian to complete sync.
```

## Decision Matrix

| Information type | Obsidian | claude-mem | memory/ | CLAUDE.md |
|-----------------|----------|-----------|---------|-----------|
| Fact (atomic) | ✅ Atom | Optional | ❌ | ❌ |
| Insight (synthesized) | ✅ Molecule | Optional | ❌ | ❌ |
| External source | ✅ Source | Optional | ❌ | ❌ |
| Decision | ✅ Atom | Optional | ✅ if prevents errors | ❌ |
| Gotcha | ✅ Atom | ✅ | ✅ | ✅ if critical |
| Command/convention | ✅ Atom | ✅ | ✅ | ❌ |
| Error-preventing rule | ❌ | ❌ | ✅ | ✅ |

## Gotchas

Common failures in `references/gotchas.md`. Tool-routing rationale in `references/tool-routing.md`. Skill-specific rules:

- **Graceful degradation is the point** — never fail completely. If Obsidian IPC is hung, skip it and save to enabled fallback backends. The user can retry when Obsidian recovers.
- **Don't duplicate Obsidian content in memory/** — different audiences. Obsidian is for the user (cite-able, searchable in vault); memory/ is for Claude (error prevention across sessions).
- **claude-mem is optional** — many users won't have it running on :37777. Skip silently, don't warn.
- **CLAUDE.md is almost never written to** — only 1-2 line rules that prevent actual errors. Target: <120 lines total to preserve prompt budget.
- **Always check duplicates** before creating Obsidian notes — clobbering a note silently is worse than any write latency.
- **Ghost notes generously** — wrap entities in `[[wikilinks]]` even when the target doesn't exist yet. Enables future entity discovery.
- **Never `[[wikilink]]` a memory/ file — use inline code** — `memory/` files (`feedback-*.md`, `reference-*.md`, etc.) and project files (`CLAUDE.md`, `AGENTS.md`) live **outside** the Obsidian vault graph. Writing `[[memory/foo]]` or `[[foo.md]]` from a note creates a permanent unresolved link (a phantom ghost that pollutes `orphans`/`unresolved` reports forever). Reference them as `` `memory/foo.md` `` instead. If the memory file has a real vault counterpart (a MOC or Atom on the same topic), link THAT note — it strengthens the graph instead of dangling. See `references/tool-routing.md`.
- **MOC link mandatory** for typed Obsidian notes (Atom/Molecule/Source/Session).

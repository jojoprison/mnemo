---
name: save
description: "Use right after something worth keeping appears — you solved a tricky bug, made a non-obvious decision, or hit a gotcha — proactively, without being asked, so a future session doesn't relearn it. Also when the user says 'remember this', 'save this', 'запомни', 'запоминай', 'сохрани', 'сохрани в память', 'сохрани в обсидиан', 'сохрани в базу знаний', 'помни', 'отложи в память', 'в мнемо', or similar. Routes a recall item to Obsidian + optional claude-mem + the active runtime's local memory, or an actionable never-X / always-Y rule to runtime-native project instructions, with graceful degradation if a backend is down."
model: inherit
---

# mn:save — Memory Routing Cascade

> **Invocation marker (both runtimes):** begin your reply with the exact line `🧠 mn:save (mnemo) → running` — the user-visible confirmation that this skill actually loaded. Emit it once per invocation, before any other output.

## Portable paths

Resolve `<mnemo-root>` once to the absolute plugin root before reading bundled files or running bundled scripts. In Claude Code, use `${CLAUDE_PLUGIN_ROOT}`; in Codex, derive it from this loaded `SKILL.md` path (skill directory → `skills/` → plugin root). Replace `<mnemo-root>` with that quoted absolute path in every command — never execute the placeholder literally and never hunt versioned cache directories.

When another mnemo skill must run, use the runtime-native path: Claude Code invokes `mn:<skill>` through its Skill tool; Codex reads `<mnemo-root>/skills/<skill>/SKILL.md` completely and follows it with the prepared input. For user-facing explicit syntax, render `/mn:<skill>` in Claude Code and `$mnemo:<skill>` in Codex.

Save information to multiple memory backends with graceful degradation. Each backend is tried independently — if one fails, others still work.

## Prerequisites & config

Obsidian is preferred but not required (skill degrades gracefully). Config at `~/.mnemo/config.json` — full schema including `cascade.*` toggles in `<mnemo-root>/references/config-schema.md`.

## Workflow

### Step 0: Classify the Input

**First — is this worth saving at all?** (Especially when saving proactively, unprompted.) Save only if a *future session would act differently* for knowing it: a solved bug + root cause, a non-obvious decision + why, a gotcha that bit you, a durable fact, an actionable rule. **Skip as a NOOP** — say "nothing worth persisting here" and stop — for routine steps, anything the repo/git already records, one-off chatter, or what a future agent would re-derive trivially. Saving noise pollutes recall; a lean vault is the asset.

**Never persist secrets** — mask tokens / keys / passwords as `<REDACTED>` before writing (a note is durable and may sync).

Then determine what type of information is being saved:

| Type | Goes to | Example |
|------|---------|---------|
| **fact** | Obsidian Atom + optional claude-mem | "Heroku standard-0 has 25 auto-backups" |
| **insight** | Obsidian Molecule + optional claude-mem | "CLI-first is 70,000x cheaper because of token savings" |
| **decision** | Obsidian Atom + optional claude-mem + memory/ | "We chose SCOPE over TextGrad for self-correction" |
| **gotcha** | Obsidian Atom + memory/ + possibly CLAUDE.md | "execSync with shell=true is banned in antomate" |
| **source** | Obsidian Source + optional claude-mem | External article, tool, research finding |
| **actionable rule** | `.claude/rules/<domain>.md` (auto-inject, path-scoped) — Step 3.5 only | "After touching `sign_epl.py`, always gate the Kontur call on the flag" |

> **Recall vs actionable rule — the fork this cascade turns on.** A *recall* item (fact / insight / decision / source) answers "what / why" and is **fetched on demand**. An *actionable rule* — "never do X / always do Y" tied to specific code — must **auto-surface** when a future agent opens the relevant file, *before* it repeats the mistake. Its home is `.claude/rules/` (native path-scoped auto-load, Step 3.5), **not** recall memory. Most saves are recall; route to `.claude/rules/` only when the rule would have prevented an error by appearing at the right moment.
>
> **Routing consequence — apply this to every step below.** A *recall* item flows through **Steps 1-4** normally. An *actionable rule* goes to **Step 3.5 only**: skip Steps 1-3 (Obsidian / claude-mem / memory/ are superseded by the auto-injecting rule file — don't double-write), and Step 4 (CLAUDE.md) fires only as the fallback if Step 3.5 declined (e.g. `project_rules` disabled). One kind → one home.

### Step 1: Obsidian (Primary — for the user)

**Skip if:** `cascade.obsidian.enabled` is false, or Obsidian CLI returns "Unable to connect"

```bash
python3 "<mnemo-root>/scripts/safe-read.py" search <<'JSON'
{"query":"{key words}","vault":"{vault}"}
JSON
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

**Why MCP:** content may contain code blocks with backticks or `$(...)` — CLI `obsidian create content="..."` would trigger zsh command substitution. See `<mnemo-root>/references/tool-routing.md` for the full rule.

**Note quality rules** (details + tables in `<mnemo-root>/references/tool-routing.md`):
- **Naming:** never `#` / `.` / `/` / `.md` in the title — they break wikilinks (`#`→heading anchor) or the CLI (`.`→truncation). Sanitize before `create`. Use `—` or space.
- **Atom title = a statement, not a topic** (Matuschak «title as API» / Умэсао): `Atom — Redis fail-open keeps reads alive when cache is down`, NOT `Atom — Redis`.
- **Molecule = non-trivial synthesis** of ≥2 atoms (new insight not in either alone), not "linked two notes."
- **Molecule handed off with `cites:` (e.g. from `/mn:ask` compounding):** when the caller passes `type: molecule` plus a `cites:` source list and a pre-built `{links_section}`, write `cites: [{sources}]` into frontmatter (right after `date:`) and use the caller's links block verbatim instead of generating a bare MOC link.
- **Two link layers:** inline with context in the body («contradicts [[X]]», «builds on [[Y]]») + `{links_section}` for MOC/nav. A bare link without context is noise.
- **Short project names** (`[[Diadoc]]`, `[[BTS Holding]]`) need a **hub note** — Obsidian doesn't resolve bare links via alias (by design). If `[[ShortName]]` is referenced and no `ShortName.md` exists, create it: a one-liner redirecting to `[[MOC — …]]`.
- **Staleness is type-driven, not stamped here.** The `date` you write *is* the review anchor — `health` derives review cadence from the note's `type` (config `review.staleDays`), so you don't add a review date. **Exception:** for a fast-rotting fact (a volatile API quirk, a "current as of" price) add an optional `ttl: <days>` to the frontmatter to age it faster than its type default. Don't add `reviewed:` — that's the snooze health/the user stamps later. See `<mnemo-root>/references/config-schema.md` → "Optional per-note frontmatter".
- **Load-bearing `[[links]]` go OUTSIDE code fences** — a wikilink inside a ` ``` ` block is NOT parsed into the graph (by design), so it's silently lost to backlinks. Agents emit code blocks constantly — keep navigable links in prose. Full vault conventions (Bases-first computed indexes, schema self-policing, concurrent-edit safety): `<mnemo-root>/references/vault-conventions.md`.

**Add to MOC — MCP `str_replace` for a targeted insert:**

```
mcp__obsidian__str_replace(
  path: "{MOC}.md",
  old_str: "{stable anchor line near list}",
  new_str: "{same anchor}\n- [[{note name}]]"
)
```

There is no inline CLI write fallback. Even a plain-looking dynamic wikilink can contain a quote that escapes `content="..."` and turns the rest into shell syntax. If MCP is unavailable, log the skipped MOC update and continue; never interpolate a generated note name into a shell command.

**On error:** Log `⚠️ Obsidian: skipped (not connected)`, continue to next backend.

### Step 2: claude-mem (Optional Semantic Search — cross-session recall)

**Skip if:** `cascade.claude_mem.enabled` is false. This is the default in new installs because many users intentionally disable claude-mem for CPU/RAM reasons.

Use the bundled helper — it auto-detects the claude-mem version for provenance, reads dynamic values as JSON from a quoted heredoc, and sends the HTTP request without a shell. A summary containing quotes, backticks, or `$(...)` remains data. It also bakes in the v12.3.9 gotchas documented below:

```bash
python3 "<mnemo-root>/scripts/claude-mem-save.py" <<'JSON'
{"url":"{claude_mem_url}","type":"{type}","project":"{current project or general}","summary":"{one-line summary of what was saved}","note":"{note name if created}","vault":"{vault}"}
JSON
```

**API field name (v12.3.9):** the request body key is `text`, not `content`. Earlier versions accepted `content`; as of v12.3.9 the API returns `{"error": "text is required and must be non-empty"}` if you send `content`. Confirmed during v0.7.3 smoke test — verified in claude-mem source.

**v12.3.9 metadata gotcha — custom fields are dropped silently.** POST returns `{"success": true, "id": ...}` but the stored observation only persists `text` + API-generated fields (`type`, `title`, `narrative`, `facts`, `concepts`, `content_hash`, `created_at`, ...). Custom `metadata.*` entries (including `project`, `obsidian_note`, `obsidian_vault`, `claude_mem_version`) are **not** retrievable from the observation record. The `project` field on the stored record is forced to the calling plugin's project (`claude-mem`), not `metadata.project`.

**Workaround (used above):** embed the key provenance fields (note name, vault, CM version) directly into `text` as a bracketed tail. Losing structured filtering hurts less than losing the data entirely — full-text search still finds the provenance. Keep the `metadata: {...}` block in the POST anyway so recovery is automatic once upstream fixes drop-silent behavior. Track upstream: [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem/issues) — search for `metadata` / `project override`.

**Why `obsidian_note` + `obsidian_vault`:** once upstream restores metadata persistence, `claude-mem search` results can link back to the full Obsidian note. Future `/mn:ask --deep` will show a direct wikilink alongside the observation.

**Why `claude_mem_version`:** v11.0.1 disabled semantic-inject by default, v12.0.0 introduced the file-read gate. Tagging observations by version lets retrieval logic filter legacy entries when needed.

**On error:** Log `⚠️ claude-mem: skipped (port {port} not responding)`, continue. Do not start ChromaDB or the claude-mem worker automatically.

### Step 3: Runtime Memory (coding-agent error prevention)

**Skip if:** `cascade.memory_dir.enabled` is false — **or this is an actionable rule** (it goes to Step 3.5; `.claude/rules/` supersedes a memory/ copy, never write both).

Only write here if the information **prevents the coding agent from making errors** in future sessions **and is not an actionable rule**:
- Gotchas, commands, conventions
- NOT business context (that's Obsidian's job)

**Path resolution:**
- Claude Code: `~/.claude/projects/-{slugified-cwd}/memory/`, **not** `./memory/` in the project root.
- Codex: `~/.codex/memories/`.

Find the correct Claude path by reading the `MEMORY.md` already loaded in the conversation context when available. Use `~/.claude/memory/` only for cross-project Claude rules. See `<mnemo-root>/references/gotchas.md` for why this matters.

**How to write — keep the index lean (autodream discipline):**

`memory/` is two layers: **topic files** (the detail) + **`MEMORY.md`** (a lean index — a table `| File | Read when… |`, one short "Read when…" row of recall triggers per topic, ≤~200 chars). Never dump prose into `MEMORY.md` — a bloated index gets **truncated on load** and old entries become invisible to Claude.

1. Write the detail to a **topic file** (`{topic}.md`) — create or update it.
2. Add/refresh **one thin index row** in `MEMORY.md` pointing to it (link + "Read when…" triggers: names / IDs / PR# / domain terms). Never a paragraph.
3. If `MEMORY.md` links a **`MEMORY-archive-index.md`** at the top, aged/older rows live there — add aged rows there (not the lean index) and read it when recalling old context.

The index is periodically re-slimmed by **autodream** (memory consolidation). Full 4-phase procedure + no-loss rules: `~/.claude/memory/autodream-principles.md`.

**On error:** Log `⚠️ memory/: skipped (directory not found)`, continue.

### Step 3.5: `.claude/rules/` — actionable path-scoped rules (auto-inject)

**Skip if:** `cascade.project_rules.enabled` is false (default **true**).

**Fires only for an *actionable rule*** (Step 0) — never for recall items. The test: *would this rule have prevented an error if it had auto-surfaced the moment the agent opened the relevant file?* Yes → here. "What we did / why" → recall memory (Steps 1-3), not here.

**Why `.claude/rules/` and not CLAUDE.md:** Claude Code natively auto-loads `.claude/rules/*.md`. A file **with** `paths:` frontmatter loads only when the agent touches a matching file (path-scoped, zero idle-context cost); a file **without** `paths:` loads every session (always-on). It is the granular evolution of the old "dump a rule into CLAUDE.md" branch (Step 4). Docs: https://code.claude.com/docs/en/memory.md (§ "Path-specific rules", "User-level rules"). **The load trigger is `paths:` — not `description:`** (that field is for humans skimming the dir; it does not affect loading).

**1 — Pick the level:**
- Rule is **specific to this repo** (names its files, domains, deploy quirks) → **project** `.claude/rules/` (committed in the repo).
- Rule is **generic / cross-project** (a language convention, a git habit, a universal gotcha that applies in every repo) → **user-global** `~/.claude/rules/` (auto-applies on every project on this machine).

**2 — Find or create the target file** (project shown; use `~/.claude/rules/` for global):

```bash
ls .claude/rules/*.md 2>/dev/null
```

- Read each file's `paths:` / domain. **Append** the rule to the file whose scope covers the code it governs (under the matching section, surgical insert).
- **No file matches by meaning → create a new `<domain>.md`.** Don't wedge an unrelated rule into the nearest file (that's the wrong-abstraction smell at the doc level).
- **`.claude/rules/` doesn't exist → create the dir *and* the file.** A first rule bootstraps the convention; do **not** silently fall back to CLAUDE.md just because the folder is missing.

**3 — Frontmatter for a new file:**

```yaml
---
paths:
  - "src/<area>/**"          # globs for the files this rule governs → path-scoped auto-load
  - "tests/<area>/**"
description: "<one line, for humans skimming .claude/rules/ — NOT a load trigger>"
---
```

Omit `paths:` only for an always-on rule (rare in a project — it costs context every session). A generic **global** rule usually omits `paths:` (it should always apply).

**4 — Write it.** These are plain repo / dotfiles **outside** the Obsidian vault → use **Write/Edit**, never the Obsidian CLI/MCP (no vault graph to join, and `obsidian create content=` would shell-expand backticks). Match the file's existing section style; append surgically, don't reformat neighbors. **Verify the YAML** after writing — a broken-indent `paths:` entry silently drops the whole file from auto-load (real incident: a 0-indent list item under `paths:` made the rule never load).

**Codex / AGENTS.md gotcha:** Codex does **not** read `.claude/rules/` — only `AGENTS.md` (nested, **32 KiB** hard limit, silent truncate past it). If the project has an assemble-AGENTS build-step (rules → `AGENTS.md`), the rule reaches Codex on rebuild — run it and confirm `wc -c AGENTS.md` stays `< 32768`. No build-step + Codex devs on the repo → also surface the critical rule into `AGENTS.md` by hand.

**On error / not applicable:** Log `⚠️ .claude/rules: skipped (recall item / cascade.project_rules disabled)`, continue.

### Step 4: CLAUDE.md (Only critical error-preventing rules)

**Skip if:** `cascade.claude_md.enabled` is false (default) — **or the item is an actionable rule already handled by Step 3.5** (`cascade.project_rules.enabled` true). This branch is the **fallback**, reached only when Step 3.5 declined (e.g. `project_rules` disabled).

Only write here if the rule is:
- 1-2 lines max
- Violation would cause a real error or bad behavior
- Not already covered by Obsidian or memory/

This is almost never needed. Most things go to Obsidian + claude-mem. **For any rule tied to code, prefer Step 3.5 (`.claude/rules/`)** — CLAUDE.md is the fallback only when you genuinely can't use a rules file (and Step 3.5 already creates the dir/file when missing, so that's rare).

### Step 5: Report

```
💾 Memory saved:

Content: "{short summary}"
Type: {atom/molecule/source/decision/gotcha/actionable rule}

Backends:
  1. Obsidian   ✅ → "Atom — {title}" in MOC — {name}
  2. claude-mem ⏭  skipped (disabled)
  3. memory/    ⏭  skipped (not error-preventing)
  3.5 .claude/rules ⏭  skipped (recall item, not an actionable rule)
  4. CLAUDE.md  ⏭  skipped (not critical rule)
```

For an **actionable rule**, the rule branch is the only write (one kind → one home):

```
💾 Memory saved:

Content: "after touching sign_epl.py, gate the Kontur call on the flag"
Type: actionable rule

Backends:
  1. Obsidian   ⏭  skipped (rule, not recall)
  2. claude-mem ⏭  skipped (rule, not recall)
  3. memory/    ⏭  skipped (rule → .claude/rules supersedes a memory/ copy)
  3.5 .claude/rules ✅ → .claude/rules/te5-frontend.md (path-scoped) — appended
  4. CLAUDE.md  ⏭  skipped (Step 3.5 handled it)
```

Or with failures:

```
💾 Memory saved (partial):

  1. Obsidian  ⚠️ skipped (not connected — restart Obsidian)
  2. claude-mem ⏭  skipped (disabled)
  3. memory/   ✅ → ~/.claude/memory/topic.md updated

⚠️ Restart Obsidian, then run this `save` skill again (`/mn:save` in Claude Code, `$mnemo:save` in Codex) to complete sync.
```

**After a *new* note is created** (not a plain append/update, not an actionable-rule write), offer to run the canonical `connect` skill using the current runtime's explicit syntax: "New note created — run `/mn:connect` (Claude Code) or `$mnemo:connect` (Codex) to surface related notes and cross-link it?" After an explicit user save, wait for their choice. If this was a proactive save mid-task, delegate to `connect` immediately to surface suggestions; `connect` still never applies links without confirmation. A fresh note that never gets connected becomes an orphan; this closes the save→connect loop without changing the original workflow.

## Decision Matrix

| Information type | Obsidian | claude-mem | memory/ | .claude/rules/ | CLAUDE.md |
|-----------------|----------|-----------|---------|----------------|-----------|
| Fact (atomic) | ✅ Atom | Optional | ❌ | ❌ | ❌ |
| Insight (synthesized) | ✅ Molecule | Optional | ❌ | ❌ | ❌ |
| External source | ✅ Source | Optional | ❌ | ❌ | ❌ |
| Decision | ✅ Atom | Optional | ✅ if prevents errors | ❌ | ❌ |
| Gotcha | ✅ Atom | ✅ | ✅ | ❌ (path-scoped + code-tied → classify as rule, row below) | rare |
| Command/convention | ✅ Atom | ✅ | ✅ | ❌ | ❌ |
| Actionable path-scoped rule | ❌ | ❌ | ❌ | ✅ **primary** | ⚠️ fallback only |

## Gotchas

Common failures in `<mnemo-root>/references/gotchas.md`. Tool-routing rationale in `<mnemo-root>/references/tool-routing.md`. Skill-specific rules:

- **Graceful degradation is the point** — never fail completely. If Obsidian IPC is hung, skip it and save to enabled fallback backends. The user can retry when Obsidian recovers.
- **Don't duplicate Obsidian content in memory/** — different audiences. Obsidian is for the user (cite-able, searchable in vault); memory/ is for Claude (error prevention across sessions).
- **claude-mem is optional** — many users won't have it running on :37777. Skip silently, don't warn.
- **CLAUDE.md is almost never written to** — only 1-2 line rules that prevent actual errors. Target: <120 lines total to preserve prompt budget.
- **Recall vs actionable rule is the routing fork (Step 3.5)** — recall ("what / why") is fetched on demand; an actionable rule ("never X / always Y" tied to code) must auto-surface when the agent opens the file. Misrouting a rule into recall = it never fires when it matters. Misrouting recall into `.claude/rules/` = idle context bloat. When unsure, ask "would this have *prevented* an error by appearing at the right file?"
- **`.claude/rules/` ≠ CLAUDE.md** — native path-scoped auto-load. `paths:` is the load trigger (not `description:`); no `paths:` = always-on. A new rule **creates** the `<domain>.md` (and the dir) when none matches — don't wedge it into an unrelated file. Verify the YAML: a broken-indent `paths:` entry silently drops the whole file from loading.
- **`.claude/rules/` files live outside the vault** — like `memory/` files, never `[[wikilink]]` them and never write them via the Obsidian CLI/MCP. Plain `Write`/`Edit`.
- **Codex is blind to `.claude/rules/`** — it reads only `AGENTS.md` (nested, 32 KiB silent-truncate). For a repo with Codex devs, route the critical rule into the AGENTS.md build-step (or by hand) too, and keep `wc -c AGENTS.md < 32768`.
- **Always check duplicates** before creating Obsidian notes — clobbering a note silently is worse than any write latency.
- **Ghost notes generously** — wrap entities in `[[wikilinks]]` even when the target doesn't exist yet. Enables future entity discovery.
- **Never `[[wikilink]]` a memory/ file — use inline code** — `memory/` files (`feedback-*.md`, `reference-*.md`, etc.) and project files (`CLAUDE.md`, `AGENTS.md`) live **outside** the Obsidian vault graph. Writing `[[memory/foo]]` or `[[foo.md]]` from a note creates a permanent unresolved link (a phantom ghost that pollutes `orphans`/`unresolved` reports forever). Reference them as `` `memory/foo.md` `` instead. If the memory file has a real vault counterpart (a MOC or Atom on the same topic), link THAT note — it strengthens the graph instead of dangling. See `<mnemo-root>/references/tool-routing.md`.
- **MOC link mandatory** for typed Obsidian notes (Atom/Molecule/Source/Session).

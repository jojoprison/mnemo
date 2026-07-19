---
name: connect
description: "Use automatically right after a new Obsidian note is created — e.g. an mn:save or mn:session that created one (skip when mn:save only appended to an existing note) — to surface hidden connections with existing notes. Also when the user asks to 'find related notes', 'connect this to others', 'найди связи', 'сделай связи', 'свяжи заметки', 'свяжи память', 'свяжи базу знаний', 'свяжи обсидиан', 'перелинкуй', or similar. Shows ranked suggestions with 'why relevant' explanations — does NOT auto-apply."
model: sonnet
context: fork
---

# mn:connect — Discover Hidden Links

## Portable paths

Resolve `<mnemo-root>` once to the absolute plugin root before reading bundled files or running bundled scripts. In Claude Code, use `${CLAUDE_PLUGIN_ROOT}`; in Codex, derive it from this loaded `SKILL.md` path (skill directory → `skills/` → plugin root). Replace `<mnemo-root>` with that quoted absolute path in every command — never execute the placeholder literally and never hunt versioned cache directories.

When another mnemo skill must run, use the runtime-native path: Claude Code invokes `mn:<skill>` through its Skill tool; Codex reads `<mnemo-root>/skills/<skill>/SKILL.md` completely and follows it with the prepared input. For user-facing explicit syntax, render `/mn:<skill>` in Claude Code and `$mnemo:<skill>` in Codex.

Analyze a note and discover connections to other notes in the vault that aren't linked yet.

## Prerequisites & config

Obsidian must be open. Config at `~/.mnemo/config.json` — reads `vault` and `links_section`. Schema in `<mnemo-root>/references/config-schema.md`.

## Workflow

### Step 1: Identify Target Note

Accept a note name from the explicit invocation, for example `/mn:connect "Atom — LongCat-Flash-Prover"` in Claude Code or `$mnemo:connect Atom — LongCat-Flash-Prover` in Codex.

If no argument, ask: "Which note should I analyze for connections?"

### Step 2: Read the Note

```bash
python3 "<mnemo-root>/scripts/safe-read.py" read <<'JSON'
{"file":"{note_name}","vault":"{vault}"}
JSON
```

Extract:
- Key concepts, technologies, names mentioned in text
- Existing `[[wikilinks]]`
- Existing links in `{links_section}` section

### Step 3: Search for Related Notes + Backlinks (single grep + backlinks, parallel)

**Even better than parallel `obsidian search` calls: one literal filesystem scan for all concepts.** The helper treats each concept as data, not regex or shell syntax. It takes ~50ms for any number of concepts vs ~180ms per `obsidian search`.

```bash
# Run these TWO commands in parallel (single message, two Bash tool uses):
# 1. One literal scan — much faster than N separate Obsidian searches
python3 "<mnemo-root>/scripts/safe-read.py" grep-concepts <<'JSON'
{"vault":"{vault}","concepts":["{concept_1}","{concept_2}","{concept_N}"]}
JSON

# 2. Backlinks check
python3 "<mnemo-root>/scripts/safe-read.py" backlinks <<'JSON'
{"file":"{note_name}","vault":"{vault}"}
JSON
```

Collect matching note paths from the scan output. Exclude the target note itself. Backlinks output → notes already connected (exclude from suggestions).

**Why not `obsidian search` per concept:** each CLI call is ~180ms. One literal scan = ~50ms total for any N. On 7 concepts: 1.26s → 50ms (**25x faster**).

### Step 4: Generate Suggestions

Compare: notes found by search MINUS notes already linked (wikilinks + backlinks).

For each suggestion, explain WHY it's relevant (shared concept, shared tag, complementary topics).

**Tension-nodes (high value, ТРИЗ):** if a found note makes an OPPOSITE claim on the same question — that's NOT a duplicate, it's a `#contradiction` link worth surfacing. Two notes disagreeing on the same benchmark is a synthesis point, not noise.

### Step 5: Present (DO NOT auto-apply)

```
🔗 Connection suggestions for "{note_name}"

Already connected: {N} notes
New suggestions: {N}

1. [[Atom — SCOPE beats TextGrad]]
   Why: Both discuss agentic RL stability — HisPO and SCOPE solve similar problems

2. [[MOC — Agent Self-Correction]]
   Why: Note mentions trial→verify→reflect cycle, this MOC covers the same pattern
   Action: Add to MOC? (currently not listed there)

3. [[Session — ANT-14 TextGrad research]]
   Why: Both evaluate RL approaches for agent improvement

4. [[Atom — Full attention wins on this benchmark]]  ⚡ #contradiction
   Why: opposite conclusion on the same GPU-efficiency question — tension to resolve

Apply these? (y/N, or pick numbers: 1,3)
```

Links are applied **with their one-line context** (the «Why»), not as bare `[[wikilinks]]` (Luhmann: state why you linked).

### Step 6: Apply on Confirmation

If user confirms:
1. Add new links to `{links_section}` **with a one-line context** (Luhmann — state why connected): `- [[Name]] — {why, ≤10 words}`, not a bare `[[Name]]`. Tension links get the marker: `- [[Name]] #contradiction — {what disagrees}`. Use **`mcp__obsidian__str_replace`** for the targeted insert.
2. If MOC suggestion — add the note link to the MOC via `mcp__obsidian__str_replace`.
3. Verify with the helper's `backlinks` action

**No inline CLI write fallback:** a dynamic name or explanation can contain quotes as well as backticks/`$()`. Any of them can break shell quoting. MCP passes content as JSON; if MCP is unavailable, report that the confirmed links were not applied and leave the vault unchanged.

## Advanced modes (optional)

- **Radius-2 (Scrapbox/Cosense-style):** two notes sharing ≥2 of the target's links are likely related even without shared text. If text search yields <3 results or user asks `--deep`, run:

```bash
python3 "<mnemo-root>/scripts/safe-read.py" shared-targets <<'JSON'
{"note_path":"{note_path}","vault":"{vault}"}
JSON
```

- **KJ-Canvas (bottom-up MOC, 川喜田 affinity):** for `--canvas {topic}` — gather all topic Atoms, drop them onto an Obsidian Canvas without categories, let the user group spatially so structure emerges. Then name clusters → new Molecules / MOC revision. Use when a topic has many Atoms but no clear MOC yet.

## Gotchas

Common failures in `<mnemo-root>/references/gotchas.md`. Tool-routing rationale in `<mnemo-root>/references/tool-routing.md`. Skill-specific rules:

- **Max 5-7 suggestions** — don't overwhelm. If you find more, rank and present top-7.
- **Don't suggest links to orphan notes** — they need their own fixing first (run `/mn:health` if interested).
- **Ghost notes are normal** — `[[Technology]]` pointing to a non-existent note enables entity discovery. Not "unresolved" in the bad sense.
- **Avoid generic connections** — "both mention Claude" is noise. A connection is meaningful if it shares a concept, approach, or unresolved question.
- **Never auto-apply** — always ask the user before writing new wikilinks.

---
name: connect
description: "Use automatically right after a new Obsidian note is created — e.g. an mn:save or mn:session that created one (skip when mn:save only appended to an existing note) — to surface hidden connections with existing notes. Also when the user asks to 'find related notes', 'connect this to others', 'найди связи', 'сделай связи', 'свяжи заметки', 'свяжи память', 'свяжи базу знаний', 'свяжи обсидиан', 'перелинкуй', or similar. Shows ranked suggestions with 'why relevant' explanations — does NOT auto-apply."
model: sonnet
---

# mn:connect — Discover Hidden Links

> **Invocation marker (both runtimes):** begin your reply with the exact line `🧠 mn:connect (mnemo) → running` — the user-visible confirmation that this skill actually loaded. Emit it once per invocation, before any other output.

## Portable paths

Resolve `<mnemo-root>` once to the absolute plugin root before reading bundled files or running bundled scripts. In Claude Code, use `${CLAUDE_PLUGIN_ROOT}`; in Codex, derive it from this loaded `SKILL.md` path (skill directory → `skills/` → plugin root). Replace `<mnemo-root>` with that quoted absolute path in every command — never execute the placeholder literally and never hunt versioned cache directories.

When another mnemo skill must run, use the runtime-native path: Claude Code invokes `mn:<skill>` through its Skill tool; Codex reads `<mnemo-root>/skills/<skill>/SKILL.md` completely and follows it with the prepared input. For user-facing explicit syntax, render `/mn:<skill>` in Claude Code and `$mnemo:<skill>` in Codex.

Analyze a note and discover connections to other notes in the vault that aren't linked yet.

## Prerequisites & config

Obsidian must be open. Config at `~/.mnemo/config.json` — reads `vault`, `links_section`, `taxonomy`, and `taxonomy_roles`. Before any mapped-hub operation, require exactly the five semantic roles `fact`, `insight`, `source`, `session`, and `moc`; require every target to exist; and require `session → session` plus `moc → moc`. The deterministic legacy Zettelkasten fallback is allowed; any other missing/invalid map stops mapped routing and offers the runtime-native setup skill instead of guessing. Schema in `<mnemo-root>/references/config-schema.md`.

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

### Step 5.5: Auto-apply mode (the `review --full` chain only)

**Fires only when the invoking payload carries an explicit auto-apply directive** — the `review --full` chain sends one after reading `review.full.autoConnect: true` from `~/.mnemo/config.json` (see `<mnemo-root>/references/config-schema.md`). A standalone `/mn:connect` / `$mnemo:connect` — anything a user typed, or any invocation without that directive — **never** auto-applies; it renders Step 5 and waits. This is the same shape as the other `--full` writes: the user opting into `--full` *and* flipping the config flag is the consent, exactly as `review.lint.autoStampReviewed` gates the one write `health` makes.

When the directive is present, skip the Step 5 confirmation prompt and go straight to **Step 6** for the ranked, deduplicated, backlink-excluded suggestions this run produced — then report every link written (tension links included and clearly marked) so nothing is applied invisibly. The suggestions are still the same high-quality set (max 5-7, meaningful-not-generic, orphans excluded); auto-apply removes the keystroke, not the quality bar. If the config flag is off, or the directive is absent, this step does not run — fall through to Step 5.

### Step 6: Apply on Confirmation

If the user confirms (Step 5) — or auto-apply mode is active (Step 5.5):
1. Read the target again, choose one unique stable anchor in `{links_section}`, then add new links **with a one-line context** (Luhmann — state why connected): `- [[Name]] — {why, ≤10 words}`, not a bare `[[Name]]`. Tension links get the marker: `- [[Name]] #contradiction — {what disagrees}`.
2. Apply the confirmed block through the bundled writer:

```bash
python3 "<mnemo-root>/scripts/vault-write.py" <<'JSON'
{"action":"insert","vault":"{vault}","note":"{target note}","anchor":"{unique anchor copied from safe-read}","position":"after","content":"{one JSON-escaped Markdown block containing only confirmed contextual links}"}
JSON
```

3. If a mapped hub suggestion was confirmed, repeat the same exact-anchor insert for the note reached through `taxonomy_roles.moc`.
4. Verify with the helper's `backlinks` action.

If an anchor is missing/non-unique or a concurrent edit wins, re-read and retry only the confirmed changes. A dynamic name or explanation can contain quotes, backticks, or `$()`; keep it JSON data and never use inline Obsidian CLI content.

## Advanced modes (optional)

- **Radius-2 (Scrapbox/Cosense-style):** two notes sharing ≥2 of the target's links are likely related even without shared text. If text search yields <3 results or user asks `--deep`, run:

```bash
python3 "<mnemo-root>/scripts/safe-read.py" shared-targets <<'JSON'
{"note_path":"{note_path}","vault":"{vault}"}
JSON
```

- **KJ-Canvas (bottom-up hub, 川喜田 affinity):** for `--canvas {topic}` — gather notes mapped to the `fact` role, drop them onto an Obsidian Canvas without categories, and let the user group spatially so structure emerges. Then name clusters → new `insight` notes / mapped-hub revision. In the default taxonomy those are Atoms, Molecules, and a MOC.

## Gotchas

Common failures in `<mnemo-root>/references/gotchas.md`. Tool-routing rationale in `<mnemo-root>/references/tool-routing.md`. Skill-specific rules:

- **Max 5-7 suggestions** — don't overwhelm. If you find more, rank and present top-7.
- **Don't suggest links to orphan notes** — they need their own fixing first (run `/mn:health` if interested).
- **Ghost notes are normal** — `[[Technology]]` pointing to a non-existent note enables entity discovery. Not "unresolved" in the bad sense.
- **Avoid generic connections** — "both mention Claude" is noise. A connection is meaningful if it shares a concept, approach, or unresolved question.
- **Never auto-apply on the standalone path** — a user-typed `/mn:connect` / `$mnemo:connect`, or any invocation without the explicit `review --full` auto-apply directive, always asks before writing new wikilinks (Step 5). The **only** exception is Step 5.5: the `review --full` chain with `review.full.autoConnect: true` — there the user opted into `--full` and flipped the config flag, so the links apply without a per-suggestion `y` and every write is reported. Default config keeps the flag off, so the default connect behavior is unchanged.

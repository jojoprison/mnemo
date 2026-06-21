# mnemo config.json schema

Path: `~/.mnemo/config.json`. Created by `initial-setup` skill on first install. All other skills read it at runtime.

## Minimal required fields

```json
{
  "vault": "main",
  "taxonomy": {
    "atom": { "prefix": "Atom — ", "tag": "atom" },
    "molecule": { "prefix": "Molecule — ", "tag": "molecule" },
    "source": { "prefix": "Source — ", "tag": "source" },
    "session": { "prefix": "Session — ", "tag": "session" },
    "moc": { "prefix": "MOC — ", "tag": "moc" }
  },
  "links_section": "## Links",
  "handoff_note": "Meta — Session Handoff"
}
```

## Full schema with cascade settings

```json
{
  "vault": "main",

  "taxonomy": {
    "atom":     { "prefix": "Atom — ",     "tag": "atom" },
    "molecule": { "prefix": "Molecule — ", "tag": "molecule" },
    "source":   { "prefix": "Source — ",   "tag": "source" },
    "session":  { "prefix": "Session — ",  "tag": "session" },
    "moc":      { "prefix": "MOC — ",      "tag": "moc" }
  },

  "links_section": "## Links",
  "handoff_note":  "Meta — Session Handoff",

  "cascade": {
    "obsidian":   { "enabled": true },
    "claude_mem": { "enabled": false, "url": "http://127.0.0.1:37777" },
    "memory_dir": { "enabled": true },
    "claude_md":  { "enabled": false }
  },

  "memory": {
    "indexWarnKB": 22
  },

  "review": {
    "staleDays": {
      "default": 30,
      "atom": 60,
      "molecule": 120,
      "source": 180,
      "session": 90,
      "moc": 365
    },
    "lint": { "enabled": false, "maxCandidates": 15, "model": "haiku", "autoStampReviewed": true }
  },

  "recall": {
    "codeGraph": null
  }
}
```

The whole `review` section is **optional** — if absent, `vault-health` falls back to a uniform 30-day staleness threshold (the legacy behavior) and the content-lint pass stays off. Add it only when you want type-aware cadence or the LLM lint.

The `recall` section is optional and ships off. `recall.codeGraph` (default `null`) is a seam for `/mn:ask` Step 4c: set it to a code-knowledge-graph backend you have installed — `"graphify"` (reads its `graph.json` / `GRAPH_REPORT.md`) or an MCP server (`"sourcegraph"` / `"ast-grep"` / `"tree-sitter-analyzer"`) — and recall gains structural "what's where" context. With no backend it's a no-op. (The project-repo **git-log** grounding in Step 4c runs regardless whenever `/mn:ask` is invoked inside a git project — it needs no config.)

## Field reference

| Path | Purpose | Used by |
|------|---------|---------|
| `vault` | Obsidian vault name (as shown in vault switcher) | All skills |
| `taxonomy.{type}.prefix` | Filename prefix for each note type | save, session |
| `taxonomy.{type}.tag` | Frontmatter tag for each note type | save, health |
| `links_section` | Heading used for cross-references (`## Связи` / `## Links`) | All skills |
| `handoff_note` | Cross-session continuity file name | session, setup |
| `cascade.obsidian.enabled` | Skip Obsidian writes if false | memory-routing |
| `cascade.claude_mem.enabled` | Enable optional claude-mem POSTs; keep false if claude-mem is disabled for CPU/RAM reasons | memory-routing |
| `cascade.claude_mem.url` | claude-mem worker URL (default port 37777) | memory-routing |
| `cascade.memory_dir.enabled` | Skip memory/ writes if false | memory-routing |
| `cascade.claude_md.enabled` | Write error-preventing rules to CLAUDE.md (default false) | memory-routing |
| `memory.indexWarnKB` | Warn threshold (KB) for `memory/MEMORY.md` size. Claude Code auto-memory **hard-truncates the index ~24.4KB on load** → warn earlier. Default **22** | vault-health |
| `review.staleDays.default` | Days before a note becomes a review candidate when its type has no specific entry. Default **30**. (`review.staleDays` may also be a bare integer — a single uniform threshold for every type.) | vault-health |
| `review.staleDays.{type}` | Per-type staleness cadence (key = a taxonomy `type` you actually use: `atom`/`molecule`/`source`/`session`/`moc`). A fast-moving fact ages quicker than an architectural decision | vault-health |
| `review.lint.enabled` | Run the content-lint deep pass (LLM re-reads candidates, emits still-valid/update-needed/contradicts verdicts). Default **false** — it reads note bodies and costs tokens | vault-health |
| `review.lint.maxCandidates` | Cap on notes the lint pass reads per run (most-overdue first). Default **15** | vault-health |
| `review.lint.model` | Model for the lint pass, spawned as a subagent so the cheap haiku health fork stays cheap. `haiku` (default, triage-grade) / `sonnet` / `opus` (highest-quality verdicts & contradiction detection — `opus` = current Opus 4.8). Only the lint subagent uses it; Steps 1-7 always run on the health fork's own model | vault-health |
| `review.lint.autoStampReviewed` | Close the review loop automatically: the content lint stamps `reviewed: {today}` on notes it judges **still-valid** (the only frontmatter write health makes — never content, never on update-needed/contradicts). Default **true**, but only takes effect when `review.lint.enabled` is also on; with the lint off (the default) health writes nothing. Set **false** to keep the lint suggest-only | vault-health |

## Optional per-note frontmatter (review)

Two optional fields override the config cadence on a single note. Neither is written automatically — they are the user's lever:

| Field | Meaning | Example |
|-------|---------|---------|
| `ttl` | Per-note staleness budget **in days**, measured from `date`/`reviewed`. Overrides `review.staleDays`. For notes that age faster or slower than their type's default (a volatile API gotcha: `ttl: 14`) | `ttl: 14` |
| `reviewed` | Snooze stamp — date the note was last confirmed still valid. Resets the staleness clock (age is measured from `max(date, reviewed)`). Stamp this on a still-valid candidate so it stops appearing in reports | `reviewed: 2026-06-21` |

This is deliberately **not** an absolute `review-by:` date. Computed-from-type plus an optional relative `ttl` does not rot the way a hand-typed future date does, and avoids the "guilt-debt" failure mode where stale review dates pile up as unactioned nags.

## Defaults when fields are missing

If the whole `cascade` section is absent, defaults are: obsidian=true, claude_mem=false, memory_dir=true, claude_md=false.

If `vault` or `taxonomy` is missing, the skill that needs them asks the user and offers to run `/mnemo:setup`.

## Customizing taxonomy

The default is Zettelkasten-inspired (atom/molecule/source). **Naming constraint:** prefixes and note names must never contain `#`, `.` (except the auto `.md`), or `/` — these break wikilink resolution or CLI indexing (see `tool-routing.md`, "Note naming rules"). Other common setups:

**PARA** (Projects/Areas/Resources/Archive):
```json
"taxonomy": {
  "project":  { "prefix": "Project — ",  "tag": "project" },
  "area":     { "prefix": "Area — ",     "tag": "area" },
  "resource": { "prefix": "Resource — ", "tag": "resource" },
  "archive":  { "prefix": "Archive — ",  "tag": "archive" }
}
```

**Custom** — any prefix/tag scheme, as long as `prefix` ends with a separator Obsidian can recognize in filenames (` — `, `: `, `/`, etc).

## Note type semantics (Zettelkasten default)

| Type | Definition | Title form |
|------|-----------|------------|
| **Atom** | Single atomic claim, true independently | A **statement** (Matuschak «title as API» / Умэсао «bean essay»), not a topic: `Atom — Caching cuts read latency 10×`, not `Atom — Caching` |
| **Molecule** | Non-trivial synthesis of ≥2 Atoms — new insight not present in either alone | Compound statement; optional `cites:` field listing source atoms |
| **Source** | External material + your annotations | Descriptive: `Source — {author} {title} ({year})` |
| **Session** | Work log for one session | `Session — {date} {project} {topic}` |
| **MOC** | Navigation hub (create at 5+ notes OR when you lose overview — Milo «mental squeeze point») | `MOC — {domain}` |

**Atom vs Molecule:** if one source note supports the claim → Atom. If the insight only emerges by combining ≥2 → Molecule. "Linked two notes" alone is not a Molecule.

## Internationalization

`links_section` is the natural i18n point. Russian vaults use `## Связи`, English `## Links`, Chinese `## 链接`, etc. All skills honor whatever string is set.

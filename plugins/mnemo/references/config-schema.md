# mnemo config.json schema

Path: `~/.mnemo/config.json`. Created by `setup` skill on first install. All other skills read it at runtime.

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
  "taxonomy_roles": {
    "fact": "atom",
    "insight": "molecule",
    "source": "source",
    "session": "session",
    "moc": "moc"
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

  "taxonomy_roles": {
    "fact":    "atom",
    "insight": "molecule",
    "source":  "source",
    "session": "session",
    "moc":     "moc"
  },

  "links_section": "## Links",
  "handoff_note":  "Meta — Session Handoff",

  "cascade": {
    "obsidian":      { "enabled": true },
    "claude_mem":    { "enabled": false, "url": "http://127.0.0.1:37777" },
    "memory_dir":    { "enabled": true },
    "project_rules": { "enabled": true },
    "claude_md":     { "enabled": false }
  },

  "memory": {
    "indexWarnKB": 22
  },

  "handoff": {
    "maxKB": 40,
    "keepDays": 14
  },

  "review": {
    "full": { "autoConnect": false },
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
    "codeGraph": null,
    "runtimeMemory": {
      "enabled": false,
      "globalSources": "explicit",
      "maxHits": 5,
      "maxExcerptBytes": 12288
    }
  },

  "hooks": {
    "sessionStartNudge": true,
    "stopNudge": false,
    "invocationEcho": true
  }
}
```

The whole `review` section is **optional** — if absent, `health` falls back to a uniform 30-day staleness threshold (the legacy behavior), the content-lint pass stays off, and `review.full.autoConnect` defaults to **false** so `review --full`'s connect step stays suggest-only. Add it only when you want type-aware cadence, the LLM lint, or one-command auto-linking.

The `recall` section is optional and ships off. `recall.codeGraph` (default `null`) is a seam for `/mn:ask` Step 4c: set it to a code-knowledge-graph backend you have installed — `"graphify"` (reads its `graph.json` / `GRAPH_REPORT.md`) or an MCP server (`"sourcegraph"` / `"ast-grep"` / `"tree-sitter-analyzer"`) — and recall gains structural "what's where" context. With no backend it's a no-op. (The project-repo **git-log** grounding in Step 4c runs regardless whenever `/mn:ask` is invoked inside a git project — it needs no config.)

`recall.runtimeMemory` is a read-only cross-runtime overlay for `ask`: Codex may retrieve Claude Code auto-memory for the **same verified git repository**, and Claude may retrieve only Codex task groups with exactly one matching `applies_to: cwd=…`. Claude identity is proven from its exact app-state project keys plus the git common directory; the lossy on-disk slug is never sufficient, and session JSONL is never opened. Obsidian remains authoritative; nothing is copied, synchronized, indexed in the background, or written by the bridge. It is opt-in (`enabled: false`) because native runtime memory is local agent-generated data. Mapping failure degrades silently and never widens the search to other projects.

`globalSources: "explicit"` permits direct Markdown topics under `~/.claude/memory/` only when the current user query explicitly asks for global/cross-project memory. Use `"off"` to disable that path completely. The bridge never reads `~/.claude/CLAUDE.md`, transcript bodies, subdirectories, symlinks, or secret-like filenames. `maxHits` is clamped to 1-7; `maxExcerptBytes` is a total output budget clamped to 256-12288 bytes. The `ask` skill still enforces one global maximum of 7 evidence items after merging all sources.

## Field reference

| Path | Purpose | Used by |
|------|---------|---------|
| `vault` | Obsidian vault name (as shown in vault switcher) | All skills |
| `taxonomy.{type}.prefix` | Filename prefix for each note type | save, session |
| `taxonomy.{type}.tag` | Frontmatter tag for each note type | save, health |
| `taxonomy_roles.{role}` | Exactly five stable semantic roles (`fact`/`insight`/`source`/`session`/`moc`) → existing taxonomy type keys. `session` and `moc` self-map; the three content roles may coalesce | ask, save, session, connect, health, setup |
| `links_section` | Heading used for cross-references (`## Связи` / `## Links`) | All skills |
| `handoff_note` | Cross-session continuity file name | session, setup |
| `cascade.obsidian.enabled` | Skip Obsidian writes if false | save |
| `cascade.claude_mem.enabled` | Enable optional claude-mem POSTs; keep false if claude-mem is disabled for CPU/RAM reasons | save |
| `cascade.claude_mem.url` | claude-mem worker URL (default port 37777) | save |
| `cascade.memory_dir.enabled` | Skip Claude Code auto-memory writes if false. It never authorizes manual writes to Codex generated memories | save |
| `cascade.project_rules.enabled` | Route an **actionable path-scoped rule** (a "never X / always Y" lesson tied to code) into `.claude/rules/<domain>.md` (project) or `~/.claude/rules/` (cross-project) so it **auto-injects** when a future agent touches the matching files — Claude Code's native path-scoped rules. Fires only for actionable-rule saves (recall items are untouched); creates the file/dir when none matches. Default **true**. Set false to keep rules out of the cascade | save |
| `cascade.claude_md.enabled` | Write error-preventing rules to CLAUDE.md — the **fallback** for `cascade.project_rules` (prefer `.claude/rules/`). Default false | save |
| `recall.codeGraph` | Optional structural code-search backend; `null` disables it. Default **null** | ask |
| `recall.runtimeMemory.enabled` | Allow bounded read-only retrieval from the counterpart runtime for the exact same git repository. Default **false** | ask, health, setup |
| `recall.runtimeMemory.globalSources` | `"explicit"` allows Claude global topic lookup only for an explicitly global query; `"off"` disables it. Default **explicit** | ask |
| `recall.runtimeMemory.maxHits` | Helper result cap, clamped to 1-7. The final cross-source cap remains 7 total. Default **5** | ask |
| `recall.runtimeMemory.maxExcerptBytes` | Total UTF-8 excerpt budget for counterpart results, clamped to 256-12288 bytes. Default **12288** | ask |
| `hooks.sessionStartNudge` | Inject a one-line memory reminder at SessionStart, rendered as `/mn:ask` + `/mn:save` in Claude Code or `$mnemo:ask` + `$mnemo:save` in Codex. Gated on a configured `vault`. Default **true**; set false to silence | hooks/mnemo-context.sh |
| `hooks.stopNudge` | At session end, if the session looks worth-saving but the save and/or session skill never ran, block once with the current runtime's native commands. This is **opt-in, default false**; an anti-loop governor prevents repeated blocking | hooks/mnemo-stop-nudge.sh |
| `hooks.invocationEcho` | Claude Code only: on a `/mn:*` slash command, emit a `systemMessage` line (`🧠 mnemo: /mn:save → skill body loaded`) via the Claude-only `UserPromptExpansion` hook — a **deterministic** invocation confirmation that, unlike the in-body marker, does not depend on model compliance. Codex does not load this unsupported event. Default **true**; set false to silence | hooks/mnemo-skill-echo.sh |
| `memory.indexWarnKB` | Early loaded-content byte warning for Claude `MEMORY.md`. Current loader limits are 200 lines or 25,000 bytes after stripping leading YAML frontmatter and block-level HTML comments; health always reports either hard-limit breach independently of this threshold. Default **22** | health |
| `handoff.maxKB` | Size ceiling (KB) before `vault-write.py archive-handoff` rotates CLOSED old blocks into `<handoff_note> Archive` (cold). The handoff is a live index, not a store; un-rotated it becomes a token bomb read every session. Default **40** | session |
| `handoff.keepDays` | Blocks newer than this stay hot regardless of status; older **and** closed (no open `- [ ]`) move to the archive. Default **14** | session |
| `review.full.autoConnect` | In `review --full`, the internal `connect` step **applies** its link suggestions without a per-suggestion prompt instead of only showing them (connect Step 5.5, review Step 9A). The user typing `--full` **and** setting this flag is the consent — mirroring `review.lint.autoStampReviewed`, the opt-in that lets a skill write. A standalone `/mn:connect` is unaffected and never auto-applies. Default **false** (non-destructive default; connect stays suggest-only for everyone who doesn't opt in) | review, connect |
| `review.staleDays.default` | Days before a note becomes a review candidate when its type has no specific entry. Default **30**. (`review.staleDays` may also be a bare integer — a single uniform threshold for every type.) | health |
| `review.staleDays.{type}` | Per-type staleness cadence (key = a taxonomy `type` you actually use: `atom`/`molecule`/`source`/`session`/`moc`). A fast-moving fact ages quicker than an architectural decision | health |
| `review.lint.enabled` | Run the content-lint deep pass (LLM re-reads candidates, emits still-valid/update-needed/contradicts verdicts). Default **false** — it reads note bodies and costs tokens | health |
| `review.lint.maxCandidates` | Cap on notes the lint pass reads per run (most-overdue first). Default **15** | health |
| `review.lint.model` | Model for the lint pass, spawned as a subagent so the cheap haiku health fork stays cheap. `haiku` (default, triage-grade) / `sonnet` / `opus` (highest-quality verdicts & contradiction detection — `opus` = current Opus 4.8). Only the lint subagent uses it; Steps 1-7 always run on the health fork's own model | health |
| `review.lint.autoStampReviewed` | Close the review loop automatically: the content lint stamps `reviewed: {today}` on notes it judges **still-valid** (the only frontmatter write health makes — never content, never on update-needed/contradicts). Default **true**, but only takes effect when `review.lint.enabled` is also on; with the lint off (the default) health writes nothing. Set **false** to keep the lint suggest-only | health |

## Optional per-note frontmatter (review)

Two optional fields override the config cadence on a single note. Neither is written automatically — they are the user's lever:

| Field | Meaning | Example |
|-------|---------|---------|
| `ttl` | Per-note staleness budget **in days**, measured from `date`/`reviewed`. Overrides `review.staleDays`. For notes that age faster or slower than their type's default (a volatile API gotcha: `ttl: 14`) | `ttl: 14` |
| `reviewed` | Snooze stamp — date the note was last confirmed still valid. Resets the staleness clock (age is measured from `max(date, reviewed)`). Stamp this on a still-valid candidate so it stops appearing in reports | `reviewed: 2026-06-21` |

This is deliberately **not** an absolute `review-by:` date. Computed-from-type plus an optional relative `ttl` does not rot the way a hand-typed future date does, and avoids the "guilt-debt" failure mode where stale review dates pile up as unactioned nags.

## Optional per-note frontmatter (retrieval)

Two optional fields sharpen retrieval; both are written by `save` (see `Step 0b` in `../skills/save/SKILL.md`), never required:

| Field | Meaning | Example |
|-------|---------|---------|
| `kind` | Semantic sub-type when it is **narrower** than the taxonomy role: `decision`/`gotcha` (on the `fact` role), `principle`/`pain`/`stance` (on the `insight` role). Makes `[kind:pain]` property-searchable in `/mn:ask`. Omit for a plain `fact`/`insight`/`source` — there it would only echo the role | `kind: pain` |
| `aliases` | Retrieval keys — EN/RU synonyms or a short name so a cross-language or short query still finds the note. A search key, **not** authored content; add only when a future search would plausibly use a different term than the title | `aliases: [save redesign, редизайн save]` |

## Defaults when fields are missing

If the whole `cascade` section is absent, defaults are: obsidian=true, claude_mem=false, memory_dir=true, project_rules=true, claude_md=false.

If `recall.runtimeMemory` is absent, cross-runtime recall is disabled. Active-runtime memory and normal Obsidian recall keep their existing behavior.

If `taxonomy_roles` is absent, a legacy Zettelkasten config is migrated deterministically in memory as `fact → atom`, `insight → molecule`, `source → source`, `session → session`, `moc → moc`; the next `setup` run persists that map. For any other legacy/custom taxonomy, `setup` must show the existing taxonomy keys and ask once where `fact`, `insight`, and `source` belong instead of guessing from prefixes or tags. A configured map is valid only when its key set is exactly those five roles, every target names an existing `taxonomy` key, and the functional roles self-map as `session → session` and `moc → moc`. Only `fact`, `insight`, and `source` may intentionally coalesce onto one type.

The `hooks` section is optional; defaults are: sessionStartNudge=true, stopNudge=false, invocationEcho=true. If absent, the SessionStart nudge still fires (when a vault is configured), the Stop nudge stays off, and the invocation echo stays on (it does not require a vault).

If `vault` or `taxonomy` is missing, the skill that needs them asks the user and offers to run `/mn:setup` in Claude Code or `$mnemo:setup` in Codex.

## Customizing taxonomy

The default is Zettelkasten-inspired (atom/molecule/source). **Naming constraint:** prefixes and note names must never contain `#`, `.` (except the auto `.md`), or `/` — these break wikilink resolution or CLI indexing (see `tool-routing.md`, "Note naming rules"). Other common setups:

**PARA** (Projects/Areas/Resources/Archive):
```json
"taxonomy": {
  "project":  { "prefix": "Project — ",  "tag": "project" },
  "area":     { "prefix": "Area — ",     "tag": "area" },
  "resource": { "prefix": "Resource — ", "tag": "resource" },
  "archive":  { "prefix": "Archive — ",  "tag": "archive" },
  "session":  { "prefix": "Session — ",  "tag": "session" },
  "moc":      { "prefix": "MOC — ",      "tag": "moc" }
},
"taxonomy_roles": {
  "fact": "resource",
  "insight": "resource",
  "source": "resource",
  "session": "session",
  "moc": "moc"
}
```

The PARA role map above is the setup suggestion: durable knowledge defaults to `resource`, while project/area/archive notes remain organizational. Setup shows it and asks for confirmation; users may explicitly choose another existing PARA key per content role.

**Custom** — any prefix/tag scheme, as long as `prefix` ends with a filename-safe separator (` — `, `: `, ` - `, etc). Never use `/`, `#`, or `.` in a prefix. Include functional `session` and `moc` types, self-map those two roles, then provide explicit targets for `fact`, `insight`, and `source`. Those three content roles may intentionally share a type; each role still has exactly one target.

## Note type semantics (Zettelkasten default)

| Type | Definition | Title form |
|------|-----------|------------|
| **Atom** | Single atomic claim, true independently | A **statement** (Matuschak «title as API» / Умэсао «bean essay»), not a topic: `Atom — Caching cuts read latency 10×`, not `Atom — Caching` |
| **Molecule** | Non-trivial synthesis of ≥2 Atoms — new insight not present in either alone | Compound statement; optional `cites:` field listing source atoms |
| **Source** | External material + your annotations | Descriptive: `Source — {author} {title} ({year})` |
| **Session** | Work log for one session | `Session — {date} {project} {topic}` |
| **MOC** | Navigation hub (create at 5+ notes OR when you lose overview — Milo «mental squeeze point») | `MOC — {domain}` |

**Atom vs Molecule:** if one source note supports the claim → Atom. If the insight only emerges by combining ≥2 → Molecule. "Linked two notes" alone is not a Molecule.

## Semantic sub-types (the `kind` field)

The five `taxonomy_roles` are the physical routing targets; a note may also carry a narrower **semantic sub-type** in `kind:` that shapes its body (typed slots) without changing where it is stored. These piggyback on a role — no schema change, works on every vault:

| `kind` | Piggybacks on role | Body slot (see `save` Step 0b) |
|--------|--------------------|-------------------------------|
| `decision` | `fact` | Y-statement: context / choice / rejected / goal / trade-off / because |
| `gotcha` | `fact` | GIVEN / WHEN / THEN + Because + Fails-when |
| `principle` / `pain` / `stance` | `insight` | JTBD: Job / Pain (func·emo·social) / Done-well / Anti-goal |

`principle`/`pain`/`stance` capture the **user's** business logic, pains, and decision stance as human-authored/confirmed atomic claims — never an agent-generated dossier (that would be the rejected auto-ingest fork; see `../../../docs/design-decisions.md`). A plain `fact`/`insight`/`source` note omits `kind:`.

## Internationalization

`links_section` is the natural i18n point. Russian vaults use `## Связи`, English `## Links`, Chinese `## 链接`, etc. All skills honor whatever string is set.

# Changelog

All notable changes to this project will be documented in this file.

## [0.10.1] - 2026-06-07

### Changed — vault-health memory-index check: configurable threshold + accurate truncation framing

- **`vault-health` Step 10** now reads the warn threshold from `config.json` → **`memory.indexWarnKB`** (default **22**) instead of a hardcoded 60 KB. Claude Code auto-memory **hard-truncates `memory/MEMORY.md` at ~24.4 KiB on load** (25 000 bytes) — beyond that, trailing rows silently vanish from Claude's context. The check now warns *early* (before the cliff) and recommends target <20 KB, with the precise mechanism in the message + the Step 9 report line.
- **`references/config-schema.md`**: documented the new `memory.indexWarnKB` field (config block example + table row).

## [0.10.0] - 2026-06-07

### Added — autodream-aware memory skills (lean-index discipline)

- **`memory-routing` (`/mn:save`)** — Step 3 (`memory/`) now documents the lean-index discipline: write the detail to a **topic file** + **one thin index row** in `MEMORY.md` (a `| File | Read when… |` table, ≤~200-char recall triggers like names / IDs / PR# / domain terms), **never a paragraph**. A bloated index gets **truncated on load** and old entries become invisible to Claude. Knows about an optional `MEMORY-archive-index.md` for aged rows, and points to the consolidation procedure (`autodream`).
- **`vault-search` (`/mn:ask`)** — new Step 3b: recall now also scans Claude's `memory/` index (`MEMORY.md` + topic files + optional `MEMORY-archive-index.md`), not just the Obsidian vault. Obsidian = user-facing knowledge; `memory/` = Claude-facing technical context (gotchas, decisions, sessions).
- **`vault-health` (`/mn:health`)** — new Step 10: flags an oversized `memory/MEMORY.md` (>60 KB) and recommends running **autodream** (consolidate into topic files + archive index, no loss). Guards against the index silently re-bloating.

### Context

Aligns mnemo with **autodream** (background memory consolidation, akin to Anthropic's AutoDream): `MEMORY.md` is a lean retrieval index, details live in topic files, aged rows split into a linked `MEMORY-archive-index.md`. Cross-project principles: `~/.claude/memory/autodream-principles.md`. Skill count unchanged (7); `session-notes` / `link-discovery` / `session-review` / `initial-setup` untouched (Obsidian-only or already correct — they pick up the discipline via the `MEMORY.md` header they read).

## [0.9.0] - 2026-05-27

### Removed — inbox-triage skill (`/mn:sort`)

- Removed `inbox-triage` skill + `commands/mn/sort.md`. In an agent-driven memory workflow, Claude creates typed notes (Atom/Molecule/Session) directly via `memory-routing`/`session-notes` — there are no manual Inbox captures to triage (the missing piece would be *capture*, not triage). Skill count **8 → 7**. Cleaned all references: both plugin manifests, marketplace, `vault-health` Inbox-backlog step, `memory-routing` decision matrix, `config-schema` taxonomy, `initial-setup` help.

### Added — PKM-canon alignment (Zettelkasten + Obsidian-official + cross-cultural research)

- **Naming rules** (`references/tool-routing.md`, `gotchas.md`, create-skills): `#` / `.` / `/` / `.md` forbidden in note names — `#` breaks wikilinks (parsed as heading anchor), `.` truncates CLI `create`. Incident-driven (56 silent orphans found in a real vault).
- **Hub notes** (`tool-routing.md`, `initial-setup` Step 6.5, `memory-routing`, `vault-health`): bare `[[ShortName]]` does NOT resolve via frontmatter `aliases` — **by design** in Obsidian (only pipe `[[MOC|Short]]` works). Use a hub note (file named with the short name → redirects to its MOC). Documented as canon (Luhmann register / Milo home / Obsidian hub note).
- **metadataCache over CLI cache** (`gotchas.md`, `vault-health`, `session-review`, `session-notes`): `obsidian orphans/unresolved/backlinks` cache & lag writes 1-5s and can report a note resolved+broken at once. Critical resolution checks now use `obsidian eval` on `app.metadataCache`.
- **vault-health**: top unresolved targets surfaced as missing-hub candidates (actionable); `#`-in-filename detection replaces the Inbox-backlog step.
- **link-discovery**: tension-node `#contradiction` suggestions (ТРИЗ), inline link context (Luhmann «state why»), optional radius-2 (Scrapbox/Cosense) + KJ-Canvas affinity (川喜田) modes.
- **Note quality** (`config-schema` note-type semantics, `memory-routing` quality rules): Atom title = a statement not a topic (Matuschak «title as API» / Умэсао «bean essay»); Molecule = non-trivial synthesis of ≥2 atoms; two link layers (inline-with-context + `## links` for nav).

## [0.8.2] - 2026-05-23

### Added — memory-routing guard against phantom wikilinks

- `memory-routing` SKILL.md Gotchas + `references/tool-routing.md`: documented that `memory/` files (and project files like `CLAUDE.md`/`AGENTS.md`) must be referenced as inline code, never `[[wikilinks]]`. They live outside the Obsidian vault graph, so `[[memory/foo]]` / `[[foo.md]]` create permanent unresolved links (phantom ghosts). Prefer linking a real vault counterpart (MOC/Atom) when one exists.

## [0.8.1] - 2026-05-22

### Changed — Codex install hygiene

- Released `mnemo` under the new repository name with both Claude Code and Codex manifests at `0.8.1`.
- Verified the Codex marketplace snapshot resolves from `https://github.com/jojoprison/mnemo` and exposes `mnemo@mnemo` as installed/enabled.
- Documented the clean Codex setup expectation: `mnemo@mnemo` and `compound-engineering@compound-engineering-plugin` stay enabled, while Superpowers is not installed.
- Tightened `skills-discover.py` so Codex sessions do not report stale Claude plugin cache skills as active Codex capabilities.

### Removed — legacy Codex Superpowers install

- Removed the previously installed `superpowers@claude-plugins-official` Codex plugin and its cache.
- Removed the `claude-plugins-official` Codex marketplace from the user setup after uninstalling its remaining installed plugin, so the old Superpowers entry no longer appears through that marketplace.
- Cleared the stale Superpowers hook trust state from `~/.codex/config.toml`.

## [0.8.0] - 2026-05-21

### Added — Codex support without breaking Claude Code

- Added native Codex plugin metadata: `.agents/plugins/marketplace.json` and `plugins/mnemo/.codex-plugin/plugin.json`.
- Added `AGENTS.md` with Codex-facing project rules and compatibility constraints.
- Added `docs/codex.md` with install, invocation, runtime differences, and verification.
- Extended `skills-discover.py` to scan Codex skill/plugin paths alongside existing Claude Code paths.
- Extended `session-scan.py` to parse Codex rollout JSONL from `~/.codex/sessions/**/*.jsonl` while preserving Claude Code JSONL parsing.

### Changed — project renamed to `mnemo`

- Public branding, manifests, and docs now use `mnemo` and `https://github.com/jojoprison/mnemo`.
- Legacy `jojoprison/claude-mnemo` install/cache paths remain documented as compatibility fallbacks so existing Claude Code installs keep working through repository redirects.

### Changed — claude-mem is optional by default

- New config examples default `cascade.claude_mem.enabled` to `false`.
- Skills now treat disabled claude-mem as a normal state, not a repair target. mnemo will not start ChromaDB or the claude-mem worker automatically.

### Tooling

- `scripts/lint-skills.py` now validates Claude and Codex plugin manifests plus marketplace files, not only `SKILL.md`.

## [0.7.4] - 2026-04-24

### Fixed — `/mn:save` POST body matches claude-mem v12.3.9 API

**Bug caught during v0.7.3 smoke test (7/7 checks, observation #65284).** `plugins/mnemo/skills/memory-routing/SKILL.md` documented the claude-mem save payload as `{"content": "...", "metadata": {...}}`. claude-mem v12.3.9 renamed the body key to `text` and returns `{"error": "text is required and must be non-empty"}` for any POST that still sends `content`. Result: `/mn:save`'s claude-mem cascade step silently failed for every v12-era installation.

- Changed the documented payload key from `content` → `text` in `Step 2: claude-mem` of the skill body.
- Confirmed the fix end-to-end: POST with `text` returns `{"success": true, "id": 65284}` on v12.3.9 (observation #65284 is the smoke-test summary itself).

### Documented — v12.3.9 drops custom `metadata.*` fields silently

During the same smoke test we discovered that v12.3.9 accepts the `metadata: {...}` block on the save endpoint and returns `success: true`, but then **does not persist** the custom keys. Stored observation #65272 came back as `text: null, facts: [], concepts: [], project: "claude-mem"` — our `obsidian_note`, `obsidian_vault`, `claude_mem_version`, and `project: "mnemo"` were dropped without error. The `project` column is forced to the calling plugin's project (`claude-mem`) rather than `metadata.project`.

Until upstream (`thedotmack/claude-mem`) restores custom metadata persistence:

- The skill now **embeds key provenance** (note name, vault, CM version) as a bracketed tail inside `text` itself — e.g. `"... [note: Atom — X | vault: main | cm: 12.3.9]"`. Full-text search still finds it.
- The `metadata: {...}` block is kept in the POST anyway, so recovery is automatic once upstream fixes the drop-silent behavior.
- Full explanation lives inline in the skill body next to the `curl` snippet.

### Verified — v0.7.3 smoke test passed 7/7

All seven checks from `TESTING.md` ran clean in a large opus-4-7[1m] session:

| # | Skill | Result |
|---|-------|--------|
| 1 | `/mn:health` | Forked, Step 0 detected `claude-mem v12.3.9`, Step 5 instant grep |
| 2 | `/mn:ask` | Inherit (no 429), parallel search (3 terms) + parallel read (3 notes), citations present |
| 3 | `/mn:connect` | Single `grep -rlE` with OR'd concepts confirmed in SKILL.md (25x faster vs N obsidian searches) |
| 4 | `/mn:save` | Obsidian MCP create ✅, claude-mem POST succeeded → uncovered the two bugs fixed above |
| 5 | `/mn:review` | Preprocessed data + explicit `cat triggers-*.md` progressive disclosure |
| 6 | `/mn:sort` | Forked, bulk mode (0 per-note prompts), inbox → Atom + MOC |
| 7 | `/mn:setup` | `md5` of `Meta — Session Handoff.md` identical before/after — idempotent |

**Universal red flag `API Error: Extra usage is required for 1M context` never appeared** across 5 forked + 3 inherit skill invocations in a 1M-context session. The v0.7.3 hybrid routing is stable.

## [0.7.3] - 2026-04-24

### Fixed — Eliminate mid-session model switches that triggered "Extra usage required for 1M context" 429s

**Root cause (regression from v0.6.0):** every skill declared a concrete `model:` in its frontmatter (`haiku` / `sonnet` / `opus`) to route for cost. Per [Anthropic's Skills docs](https://code.claude.com/docs/en/skills), a skill's `model:` field overrides the session model **for the current turn**, which forces Claude Code to re-read the full conversation history without cached context. On Max plans where Opus auto-upgrades to a 1M context variant, a mid-session switch on a large conversation can trip the server-side 1M billing gate and return **`API Error: Extra usage is required for 1M context`** (tracked upstream in `anthropics/claude-code` issues [#40223](https://github.com/anthropics/claude-code/issues/40223), [#42616](https://github.com/anthropics/claude-code/issues/42616), [#45249](https://github.com/anthropics/claude-code/issues/45249)).

**Fix — hybrid fork/inherit routing across 8 skills:**

| Skill | v0.7.2 routing | v0.7.3 routing | Reason |
|-------|----------------|----------------|--------|
| `/mn:health` | `model: haiku` | `context: fork` + `model: haiku` | Zero-reasoning filesystem scan — isolated subagent, no main-session cache hit. |
| `/mn:connect` | `model: sonnet` | `context: fork` + `model: sonnet` | Semantic concept ranking is argument-based and safe to isolate. |
| `/mn:sort` | `model: haiku` | `context: fork` + `model: haiku` | Rule-based inbox taxonomy — doesn't need conversation history. |
| `/mn:setup` | `model: haiku` | `context: fork` + `model: haiku` | One-shot Q&A config wizard. |
| `/mn:ask` | `model: sonnet` | `model: inherit` | Recall queries may reference current conversation ("что мы обсуждали про X") — must see session. |
| `/mn:save` | `model: haiku` | `model: inherit` | "Remember THIS" requires knowing what "this" is. |
| `/mn:session` | `model: sonnet` | `model: inherit` | Summarizes the whole conversation. |
| `/mn:review` | `model: opus` | `model: inherit` | End-of-session orchestrator — must see session; users choose depth via `/model` (skill body adds a one-line nudge recommending `/model opus[1m]` before review). |

**Net effect**

- Forked skills run in isolated subagents (fresh 200K context, zero impact on main-session cache) → eliminates the switch trigger entirely.
- Inherit skills reuse the session's model — whatever the user picked via `/model` — so they never force a transition either.
- User keeps central control: `/model` governs synthesis quality + speed for the four inherit skills; the four forked skills stay fast on haiku/sonnet regardless.

### Changed — `/mn:review` gained a model-selection nudge

Inline tip in the skill body: *"For deepest analysis depth, run `/model opus[1m]` before `/mn:review` if you're not already on Opus. This skill inherits your session's model."* Keeps the cheap-by-default path without losing the previous forced-opus quality ceiling.

### Added — linter now accepts `inherit` and `context: fork`

`scripts/lint-skills.py`:

- Extends `MODEL_WHITELIST` with `inherit` (valid value per [Anthropic docs](https://code.claude.com/docs/en/skills#frontmatter-reference)).
- New `CONTEXT_WHITELIST` validates `context: fork`.
- New guard rule: `context: fork` + `model: inherit` is contradictory (fork creates an isolated subagent that can't inherit); linter flags the combination.

### Benchmarks (user on `opus-4-7[1m]`, xhigh effort — the case that triggered the regression)

| Skill | v0.7.2 (switch+cache-reload) | v0.7.3 (fork or inherit) | Change |
|-------|:---:|:---:|:---:|
| `/mn:health` | ~8s + 429 risk on large context | ~7s (fork + haiku, isolated) | stable, no 429 |
| `/mn:connect` | ~0.8s + 429 risk | ~8s (fork + sonnet) | heavier-model quality, no 429 |
| `/mn:sort` (per note) | ~3s + 429 risk | ~5s (fork + haiku) | slightly slower, no 429 |
| `/mn:setup` | ~3s + 429 risk | ~5s (fork + haiku) | slightly slower, no 429 |
| `/mn:ask` | ~2s + 429 risk | ~9s on opus / ~3s on sonnet | user-controlled, no 429 |
| `/mn:save` | ~3s + 429 risk | ~9s on opus / ~3s on sonnet | user-controlled, no 429 |
| `/mn:session` | ~5s + 429 risk | ~15s on opus / ~5s on sonnet | user-controlled, no 429 |
| `/mn:review` | ~5s + 429 risk | ~15s on opus / ~5s on sonnet | user-controlled, no 429 |

Sources: [Artificial Analysis — Haiku 4.5 (TTFT 0.67s, 95 t/s)](https://artificialanalysis.ai/models/claude-4-5-haiku), [Opus 4.7 (TTFT 3–19s, 43–50 t/s)](https://artificialanalysis.ai/models/claude-opus-4-7).

## [0.7.2] - 2026-04-24

### Added — CI lint for SKILL.md files

`scripts/lint-skills.py` validates every `SKILL.md` in `plugins/*/skills/*/`:

- Frontmatter parses and has required `name` + `description`
- `model` (if set) is in the whitelist: `haiku`, `sonnet`, `opus`
- File is under 500 lines (skill-creator recommendation)
- Any `references/*.md`, `scripts/*.{sh,py}`, or `assets/*` paths mentioned in the body actually exist

Wired into `.github/workflows/skill-lint.yml` — runs on every push/PR touching `plugins/` or the linter itself. Catches broken references after a rename, stale script pointers, accidental `model: opus-42`, and runaway SKILL.md sizes.

Locally: `python3 scripts/lint-skills.py` — same output as CI.

### Fixed — `/mn:session` Step 3 actually reads the template

`assets/session-template.md` was referenced in the skill preamble but no step actually loaded it. Step 3 now runs `cat "${CLAUDE_PLUGIN_ROOT}/assets/session-template.md"` (with source-tree fallback) before filling in placeholders. Guarantees the template shape reaches the model.

### Fixed — `/mn:review` Step 4 loads trigger files explicitly

Previously the skill said "read `triggers-{type}.md`" but left it to Claude's discretion. Now Step 4 includes an explicit bash block that `cat`s the chosen type file, the universal file, and any project-local `skill-triggers.md` — so the trigger matrix always reaches the analysis step.

### Changed — README "Project Structure" matches reality

Added `references/`, `assets/`, `hooks/`, `scripts/` and the `.github/workflows/skill-lint.yml` / root `scripts/lint-skills.py` to the structure diagram. Per-skill routing and per-reference purpose annotated inline.

### Changed — `memory/mnemo-tool-routing.md` thin-pointer

The project-memory file duplicated the plugin's `references/tool-routing.md`. Reduced to a one-line pointer at the GitHub URL — single source of truth in the plugin itself.

## [0.7.1] - 2026-04-24

### Changed — Progressive disclosure via shared `references/`

A skill-creator audit flagged ~100 lines of duplicated gotchas, config schemas, and tool-routing rationale across 7 of 8 SKILL.md files. Extracted into `plugins/mnemo/references/`:

- `gotchas.md` — IPC hung, plugin update stale cache, shell injection, `memory/` path resolution, claude-mem worker availability
- `config-schema.md` — full `~/.mnemo/config.json` field reference + PARA / custom taxonomy examples
- `tool-routing.md` — the MCP-first hybrid rule with rationale and the 2026-04-21 zsh-backticks incident
- `triggers-implementation.md` / `triggers-research.md` / `triggers-debugging.md` / `triggers-universal.md` — `/mn:review` trigger matrix split by session type (progressive disclosure — read only the matching file)

Each SKILL.md now has a one-line pointer: *"Common failures in `references/gotchas.md`"*. Claude loads the reference only when it actually needs the detail.

**Net: 1290 → 1186 lines across skills (−104 duplicated lines), `session-review` alone dropped 262 → 222.**

### Changed — Pushier descriptions to fix under-triggering

skill-creator explicitly warns that Claude under-triggers skills with passive descriptions. Rewrote 5 descriptions to include "use whenever..." language, Russian trigger phrases (`'запомни'`, `'мнемо настрой'`, `'инбокс'`), and Russian intent verbs practitioners actually type:

- `vault-search` → recall, summarize, "что мы решили"
- `vault-health` → vault maintenance, "проверь vault", proactive after 3+ notes
- `link-discovery` → automatic after any new note, "find related notes"
- `inbox-triage` → "inbox cleanup", "разгреби inbox"
- `memory-routing` → solved a bug, non-obvious decision, "в мнемо"
- `session-notes` → ship completion, "записать сессию", before stepping away
- `initial-setup` → "mnemo not configured", auto-invoked on missing config

### Changed — `/mn:review` auto-discovery uses `${CLAUDE_PLUGIN_ROOT}`

The Step 4 custom-triggers path referenced a non-existent `${CLAUDE_SKILL_DIR}` env var. Fixed to `${CLAUDE_PLUGIN_ROOT}/skill-triggers.md` with fallback to `.claude/skill-triggers.md` at project root.

### Added — Shared shell scripts for repeated logic

- `scripts/get-vault-path.sh` — returns the filesystem path of a named vault via `obsidian vault`. Used by `/mn:health` Step 5 and `/mn:connect` Step 3.
- `scripts/check-cm-version.sh` — inspects claude-mem cache, emits `version:`, `stale:`, `path:` lines. Used by `/mn:health` Step 0 and `/mn:save` Step 2.

Single source of truth for cache-path and version-detection logic.

### Added — `assets/session-template.md`

Reusable session frontmatter + structure template. `/mn:session` now references it instead of inlining the whole example.

### Changed — Incremental JSONL parsing in `session-scan.py`

`session-scan.py` now reads only bytes appended since the last scan (offset stored in `/tmp/mnemo-session-offset-{id}.json`) and merges into the cached aggregate. On a long session (5000+ lines), the first `/mn:review` after cache expiry drops from ~200ms parse to ~5-20ms because JSONL is append-only.

Safely falls back to full re-scan if the offset exceeds file size (session rotated) or if the cache JSON is corrupt.

### Added — Bulk mode in `/mn:sort`

Say "accept all" / "применить все" / "bulk" to skip per-note confirmation and apply suggested classification to every remaining inbox note. Still shows per-note progress so you can abort mid-stream if a suggestion looks wrong.

### Changed — `/mn:setup` Step 6 idempotent

Now skips handoff-note creation if it already exists. Prevents clobbering a live handoff when the user re-runs setup.

## [0.7.0] - 2026-04-24

### Added — claude-mem v12.3.9 integration

mnemo now plays nicely with the major claude-mem upgrade (10.5.2 → 12.3.9, landed on this machine 2026-04-24). Two skills became aware of the co-installed plugin:

**`/mn:health` Step 0 — claude-mem sanity check.** When the plugin is present, surface two common gotchas at the top of the health report:

- Multiple version folders in cache → "restart all Claude windows" (stale Stop hooks point to an old `CLAUDE_PLUGIN_ROOT`, a real failure mode after every major upgrade)
- Major version < 12 → "you're missing file-read gate, tier routing, and knowledge agents — run `/plugin update claude-mem`"

Skipped entirely when claude-mem isn't installed.

**`/mn:save` Step 2 — enriched observation metadata:**

- `claude_mem_version` auto-detected from `~/.claude/plugins/cache/thedotmack/claude-mem/`. Lets future retrieval filter legacy pre-v12 observations from post-file-read-gate entries.
- `obsidian_note` + `obsidian_vault` — backlinks the observation to the full note in the vault. Groundwork for `/mn:ask --deep` (a future skill upgrade) to show semantic-search results next to direct wikilinks.

### Why a minor bump

v0.6.x was pure perf. v0.7.0 adds new semantic capabilities (version detection, cross-system backlinks) that external scripts may depend on. Breaking none of v0.6.x — purely additive.

## [0.6.2] - 2026-04-24

### Changed — `/mn:connect` switches to single grep for all concepts

Step 3 used to run N parallel `obsidian search` calls, one per extracted concept — still 180ms per call minimum. Replaced with one `grep -rlE "({c1}|{c2}|...|{cN})"` against the vault's filesystem path. Single filesystem walk = ~50ms regardless of concept count.

**Measured on 7 concepts: 1.26s → 50ms (25x faster).** Backlinks check still runs in parallel with the grep.

### Changed — `/mn:health` Steps 1-4 run in parallel

Orphans, unresolved links, tags, and files count are independent CLI queries. Documented them as parallel (single assistant message, 4 Bash tool uses). 720ms → 180ms.

### Added — SessionStart prewarm hook

`plugins/mnemo/hooks/prewarm.sh` runs async on SessionStart (`startup` and `resume` matchers) and warms `/tmp` caches for `session-scan.py` + `skills-discover.py`. **First** `/mn:review` in a session is now as fast as a cached rerun — no more 10s wait on the initial invocation.

Hook is async + non-blocking + fails silently — doesn't slow down session boot even if scripts are unavailable.

### Performance (cumulative since v0.5.10)

| Command | v0.5.10 | v0.6.2 | Speedup |
|---------|---------|--------|---------|
| `/mn:health` | ~8s | ~1s | 8x |
| `/mn:ask` | ~6s | ~2s | 3x |
| `/mn:connect` | ~7s | ~0.8s | **8.7x** |
| `/mn:save` | ~5s | ~1.5s | 3.3x |
| `/mn:session` | ~5s | ~2.5s | 2x |
| `/mn:review` first run | ~10s | ~3s (prewarmed) | 3.3x |

## [0.6.1] - 2026-04-24

### Changed — Model tier correction based on public benchmarks

v0.6.0 was based on intuition. Actual research across Anthropic docs, Artificial Analysis benchmarks, Reddit practitioner reports and Sider's production retrospective revealed two miscalibrated choices:

- **`/mn:connect`**: haiku → **sonnet**. Semantic concept extraction + ranking with "why relevant" explanations is exactly where Haiku 4.5 breaks on subtle connections. Multiple practitioner reports flag this failure mode ("missed something crucial on page 87"). Sonnet 4.6's 94/100 coding-composite vs Haiku's 82 is also meaningful for this task.
- **`/mn:save`**: sonnet → **haiku**. Rule-based classification (fact/insight/decision/gotcha/rule) against a fixed taxonomy + routing cascade. Short input, clear schema — Haiku's sweet spot. Anthropic's own tiering guidance for structured output + routing supports this.

`/mn:review` stays on **opus** — kept by user preference despite research suggesting Sonnet 4.6 would suffice. The 1M context window matters for long session JSONL analysis.

Final tiering: **4× haiku** (health, sort, setup, save), **3× sonnet** (connect, ask, session), **1× opus** (review).

### Changed — `/mn:health` Step 5 is 1800x faster

Previously looped `obsidian read` per file to check for `## Связи` heading — on a 1000-note vault that's ~180 seconds. Replaced with a single recursive `grep -rL` against the vault's filesystem path (obtained via `obsidian vault vault="{name}"`).

Measured: **49ms vs ~180s on a 999-note vault** — no more "skip on large vaults" caveat. Safe to run every time.

### Model tier summary (final)

| Skill | Model | Why |
|-------|-------|-----|
| `/mn:health` | haiku | Parse CLI output, format table, no reasoning |
| `/mn:sort` | haiku | Rule-based classification, clear taxonomy |
| `/mn:setup` | haiku | Interactive Q&A, one-time |
| `/mn:save` | haiku | Classify + route to 4 backends by schema |
| `/mn:connect` | sonnet | Semantic ranking with explanations |
| `/mn:ask` | sonnet | Multi-source synthesis + citations |
| `/mn:session` | sonnet | Session summary with coherent frontmatter + wikilinks |
| `/mn:review` | opus | JSONL-wide skill-gap reasoning, kept by preference |

## [0.6.0] - 2026-04-24

### Changed — Tiered model selection (~60% latency reduction on common ops)

Every skill declared `model: opus` in v0.5.x. Opus is the slowest tier and overkill for index lookups and fixed-workflow classification. Retuned:

| Skill | Before | After | Rationale |
|-------|--------|-------|-----------|
| `/mn:health` | opus | **haiku** | Deterministic CLI outputs → formatted report, no synthesis |
| `/mn:connect` | opus | **haiku** | Mechanical search + backlinks diff, no judgment calls |
| `/mn:sort` | opus | **haiku** | Rule-based classification against a fixed taxonomy |
| `/mn:setup` | opus | **haiku** | Interactive Q&A, one-time |
| `/mn:ask` | opus | **sonnet** | Light synthesis from N notes — Sonnet 4.6 is plenty |
| `/mn:save` | opus | **sonnet** | Classify + cascade to 4 backends |
| `/mn:session` | opus | **sonnet** | Summarize + MCP write + handoff update |
| `/mn:review` | opus | **opus** (kept) | Session-completeness analysis + skill-gap reasoning genuinely needs Opus |

### Changed — No more `context: fork` on index-only skills

`context: fork` spins up a fresh Claude session with a cold cache. Kept only on skills that process large vault context (`/mn:save`, `/mn:session`, `/mn:review` stays default). Removed from `/mn:ask`, `/mn:connect`, `/mn:health`, `/mn:sort`, `/mn:setup` — they reuse the current session's warm cache.

### Changed — Parallel CLI invocations

Three skills previously made sequential `obsidian` calls. Now documented as parallel (single assistant message, multiple Bash tool uses):

- **`/mn:ask`** Step 3 — all search terms in parallel (4×180ms → 180ms)
- **`/mn:ask`** Step 4 — read top-7 notes in parallel (7×185ms → 185ms)
- **`/mn:session`** Step 2 — exact-filename read + same-day search in parallel
- **`/mn:connect`** Step 3 — all concept searches + backlinks check in parallel (8×180ms → 180ms)

### Changed — `/mn:review` inline Python extracted

`session-review/SKILL.md` dropped from 387 to ~250 lines. The two inline Python heredocs (session JSONL scan + skill auto-discovery) moved to `plugins/mnemo/scripts/session-scan.py` and `skills-discover.py`. Each script now caches results to `/tmp/` (60s for session scan, 300s for skills inventory) — `/mn:review` reruns during the same session are instant instead of re-parsing the JSONL every time.

### Performance

Combined effect on a warm Claude Code instance:

| Operation | Before | After |
|-----------|--------|-------|
| `/mn:health` (400-note vault) | ~8s | ~3s |
| `/mn:ask` broad query | ~6s | ~2s |
| `/mn:connect` | ~7s | ~2.5s |
| `/mn:session` | ~5s | ~2.5s |
| `/mn:review` (rerun) | ~10s | ~3s (cached scan) |

## [0.5.10] - 2026-04-21

### Security

- **🚨 Fixed shell injection in `/mn:session`, `/mn:save`, `/mn:sort`, `/mn:setup`** — CLI `obsidian create content="..."` passes markdown through zsh double-quoted strings, which triggers command substitution on any backticks or `$(...)` inside code blocks. A real incident on 2026-04-21 accidentally executed `make deploy-back` on production because a session note contained a bash code block. (Harmless that time — same image SHA, no migrations — but a genuine vulnerability.)

### Changed — MCP-first hybrid tool routing

All write operations with arbitrary markdown bodies are now routed through MCP (`mcp__obsidian__create`, `mcp__obsidian__str_replace`, `mcp__obsidian__insert`) instead of CLI. Read/search/orphans/backlinks stay on CLI — they're faster (indexed) and unique to CLI. Benchmark on this machine:

| Operation | CLI | MCP |
|-----------|-----|-----|
| create | ~180 ms (node cold-start) | ~30-50 ms |
| search | ~175 ms (indexed) | not available |
| read | ~185 ms | similar |
| orphans/backlinks/tags | ~180 ms | not available |

Rule of thumb: **any `content=` arg with markdown → MCP; everything else → CLI**.

### Changed — session duplicate detection

`/mn:session` Step 2 became two-level:

1. **Exact filename read** (`obsidian read file="{planned-name}"`) — if the note exists, ask append/overwrite/rename
2. **Related same-day search** (`obsidian search query="{prefix}{date}"`) — show informational list so the user can cross-link, but don't block creation

Frontmatter now includes `session_id: {CLAUDE_SESSION_ID}` — disambiguates same-day sessions when topic keywords overlap.

### Changed — handoff updates are targeted

`/mn:session` Step 5 uses `mcp__obsidian__str_replace` to update specific sections of `Meta — Session Handoff` instead of blind `obsidian append`. Handoff no longer accumulates stale pending items.

### Changed — inbox/memory/setup notes

- `/mn:save` — Atom/Molecule/Source creation via `mcp__obsidian__create`
- `/mn:sort` — reclassified notes created via MCP
- `/mn:setup` — `Meta — Session Handoff` bootstrapped via MCP
- `/mn:connect` — prefer `mcp__obsidian__str_replace` for adding `[[wikilinks]]` to the links section

### Fixed

- Removed stale "skill unsafe — don't invoke" ban from global `~/.claude/CLAUDE.md`. `/mn:session` is safe to use again as of this release.

## [0.5.9] - 2026-04-07

### Changed
- **`/mn:review` is now an end-of-session orchestrator** — auto-runs save + session without asking
  - Detects unsaved decisions → auto-invokes `mnemo:memory-routing`
  - Detects no session notes → auto-invokes `mnemo:session-notes`
  - Remaining skills (commit, connect, health, sort) → asks before running
  - Skip auto-run if skill was already invoked this session
  - Only command users need at session end
- Improved skill descriptions for better auto-triggering (pushy pattern from skill-creator)
- docs/review.md updated with orchestrator workflow

## [0.5.8] - 2026-04-07

### Breaking Changes
- **Plugin name reverted to `mnemo`** (was `mn` in 0.4.0). Autocomplete now shows `(mnemo)` label.
- **Skill directories renamed** — internal names changed (e.g. `session` → `session-notes`). User-facing commands (`/mn:session`) unchanged.

### Added
- **Skill-aware session review** (`/mn:review`) — complete rewrite:
  - JSONL session introspection via `${CLAUDE_SESSION_ID}` preprocessing
  - Auto-discovers 200+ installed skills across 6 glob paths
  - Session fingerprinting: implementation, research, debugging, refactoring, documentation, configuration, planning
  - Skill gap analysis with trigger matrix per session type
  - Execution chain — offers to run missed skills in priority order
  - Inline execution (no `context: fork`) for conversation access + skill invocation
- **SessionStart cleanup hook** — automatically removes stale plugin cache versions on every Claude Code launch. No more autocomplete ghosts from old versions.

### Changed
- **CE-pattern naming** — plugin name `mnemo` + command prefix `mn:` (same pattern as compound-engineering `ce:` prefix). Type `/mn:` to see all commands with `(mnemo)` label.
- **Skills hidden from autocomplete** — `user-invocable: false` + unique directory names prevent duplicate entries. Commands (`/mn:*`) are the sole user-facing UI.
- **Skill directories renamed** to avoid autocomplete collision with commands:
  - `session` → `session-notes`
  - `save` → `memory-routing`
  - `review` → `session-review`
  - `ask` → `vault-search`
  - `health` → `vault-health`
  - `connect` → `link-discovery`
  - `sort` → `inbox-triage`
  - `setup` → `initial-setup`
- Cross-references updated: `/mn:` → `/mnemo:` in all skill files
- Stale references removed: `dump`, `check-gmail`, `gmail_enabled` config

### Technical Notes
- Skill tool resolves by **directory name**, not frontmatter `name` field — both must match
- `disable-model-invocation: true` shows in autocomplete (counterintuitive); `user-invocable: false` hides from autocomplete
- Default (no flags) = `user-invocable: true`

## [0.4.0] - 2026-03-28

### Added
- `/mn:` command aliases for autocomplete — 8 thin command wrappers in `commands/mn/`
- `mnemo:review` skill — session completeness analyzer

### Changed
- Plugin renamed `mnemo` → `mn` for shorter invocation (reverted in 0.5.8)
- Removed `dump` and `check-gmail` skills (consolidated into `save` and external `gws`)
- Skill count: 9 → 8

## [0.3.0] - 2026-03-24

### Added
- `mnemo:save` — memory routing cascade with graceful degradation
  - Routes to: Obsidian → claude-mem → memory/ → CLAUDE.md
  - Each backend independent — if one fails, others still work
  - Auto-classifies input (fact→Atom, insight→Molecule, decision, gotcha, source)
  - Configurable via `cascade` section in config.json

### Changed
- All skills: IPC error handling (v0.2.4)
- health: tag-based counting (v0.2.4)
- Skill count: 8 → 9

## [0.2.0] - 2026-03-24

### Added
- `mnemo:ask` — vault knowledge search with citation synthesis
- `mnemo:sort` — classify inbox notes into proper typed notes
- `mnemo:setup` — interactive onboarding
- `CONTRIBUTING.md`
- Config path unified: `~/.mnemo/config.json`
- `links_section` configurable

### Changed
- All skills: English code, localized examples
- health: specific CLI commands for all 8 audit steps
- session: MOC verification, handoff update, orphan check

## [0.1.0] - 2026-03-23

### Added
- Initial release with 5 skills: health, connect, dump, session, check-gmail
- Plugin marketplace support
- `config.example.json`
- MIT License

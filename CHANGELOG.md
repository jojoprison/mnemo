# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.5] - 2026-07-20

### Added

- **Stable semantic taxonomy roles** — `taxonomy_roles` maps exactly `fact`, `insight`, `source`, `session`, and `moc` onto configured note types. Default Zettelkasten, PARA, and custom taxonomies now share one skill implementation without hard-coded Atom/Molecule routing; the two functional roles self-map and contract tests protect the schema.
- **Required dual-runtime packaging E2E** — CI pins current tested Claude Code and Codex loaders, installs mnemo into isolated `CLAUDE_CONFIG_DIR` / `CODEX_HOME` homes, and requires exactly seven skills plus all packaged references, scripts, assets, and hooks. The release workflow now rejects tags that disagree with any manifest or lack a dated changelog section.

### Changed

- **One bundled vault write boundary** — every Obsidian Markdown create/update, reviewed stamp, and handoff rotation now goes through the JSON-stdin `vault-write.py` adapter. The Obsidian CLI only resolves the vault by argv; Markdown never enters a shell or CLI argument. The old archive writer is removed, while indexed reads remain in the separate argv-safe `safe-read.py` adapter.
- **Current runtime-memory semantics** — Claude index health measures the content Claude actually loads after stripping frontmatter and block HTML comments, with the documented 200-line / 25,000-byte limits. All helpers honor custom runtime homes; ambiguous project/local `autoMemoryDirectory` precedence or workspace trust fails closed instead of guessing.
- **Runtime-owned save policy** — Claude auto-memory remains an enabled, runtime-specific error-prevention backend; Codex `${CODEX_HOME}/memories/` is treated as generated read-only state. Cross-runtime recall stays opt-in federation, never synchronization or a shared writer. Existing actionable-rule routing through `.claude/rules/` is intentionally unchanged.

### Fixed

- **Crash/race-safe handoff rotation** — archive-first updates now preserve backups, exact block multiplicity, pending/open blocks, clean prefix/newline boundaries, and idempotent partial retries. Same-inode handoff/archive aliases fail before a second lock, preventing a hardlink or case-fold deadlock.
- **Optimistic writer conflicts** — atomic exchange detects changes both before and during publication, keeps a later writer at the public path, preserves displaced content in a durable conflict file, retains note mode, and rejects symlink, traversal, foreign-owner, oversized, non-UTF-8, or ambiguous targeted edits.
- **Custom-home discovery** — `CLAUDE_CONFIG_DIR` and `CODEX_HOME` now flow through session scanning, skill discovery, claude-mem helpers, and user-skill namespace classification instead of assuming literal `~/.claude` / `~/.codex` segments.
- **Relevant-first Codex recall** — task groups are scored before exact-project Git probes, with per-search identity caching. Unrelated history no longer spawns one Git check per group or emits a false scope warning; regressions also cover publish-time create races and byte-exact handoff backups.

### Security

- **Structure-aware scope parsing** — fenced code, YAML frontmatter, block comments, and raw HTML can no longer forge Codex task-group scope or Claude index links. Every memory component is opened descriptor-relative with no-follow checks and before/after metadata validation; unobservable managed-policy or `--settings` state is reported as an honest fail-closed limitation.

## [1.2.4] - 2026-07-20

### Fixed

- **Claude hook auto-discovery** — Claude's manifest now lists only the additive `hooks/claude-hooks.json`; the standard `hooks/hooks.json` baseline is auto-loaded by Claude Code. This removes the `Duplicate hooks file detected` load failure introduced in v1.2.3 while preserving Claude's `UserPromptExpansion` echo and Codex's `SessionStart`/`Stop` baseline.
- **Required real-loader CI gate** — CI installs the tested Claude Code loader, then `test-runtime-compat.py` installs mnemo into an isolated `CLAUDE_CONFIG_DIR` and requires the plugin to report enabled. The gate catches duplicate component paths that `claude plugin validate --strict` accepts; CI also runs the full cross-runtime memory suite.

## [1.2.3] - 2026-07-20

### Added

- **Cross-runtime recall without synchronization** — opt-in `recall.runtimeMemory` lets Codex retrieve verified Claude Code project memory and Claude retrieve only Codex task groups scoped to the exact same git common directory. Obsidian stays authoritative; runtime memory is cited as untrusted secondary evidence.
- **Bounded read-only adapter** — `runtime-memory.py` returns at most seven hits, 12 KiB of excerpts, and 32 KiB of JSON. It never writes, caches, follows symlinks, reads transcript bodies, fetches embedded links, or broadens an unverified project mapping. Explicit global lookup is restricted to direct non-secret Markdown topics under `~/.claude/memory/`.
- **Setup and health integration** — setup offers the bridge as an off-by-default choice; health reports only mapping availability through a bounded metadata projection, never returns/summarizes counterpart body content, and never attempts repair.

### Changed

- **Runtime-safe hook composition** — shared `hooks/hooks.json` now contains only Codex-supported `SessionStart` and `Stop`. Claude's manifest additively loads `hooks/claude-hooks.json` for `UserPromptExpansion`, preserving the v1.2.2 invocation echo without depending on Codex silently ignoring an unsupported event. Every hook event still has exactly one definition.
- **Recall evidence budget** — `/mn:ask` merges Obsidian, active-runtime, and counterpart candidates under one seven-item cap, prefers Obsidian on ties, and treats all runtime-memory excerpts as data rather than instructions.

### Security

- **Fail-closed project isolation** — Claude's lossy project slug is accepted only when every matching exact app-state project key resolves to the same git common directory; session JSONL is never opened. Codex memory requires exactly one explicit matching `applies_to: cwd=…`. Foreign, mixed, malformed, oversized, symlinked, and unscoped candidates are rejected, with regression coverage for worktrees, slug collisions, injection-shaped content, secret-like names, metadata-only status, and real output bounds.

## [1.2.2] - 2026-07-20

### Added

- **Invocation visibility, two layers** — the v1.2.0 unify removed the command-router layer and with it the visible Skill-tool call that confirmed a `/mn:*` command loaded its skill. (1) Every canonical `SKILL.md` now opens with an **invocation marker** instruction — the reply starts with `🧠 mn:<skill> (mnemo) → running` — working in both runtimes (in Codex UI, which has no native skill-invocation indicator, this is the only visible signal). (2) A new **deterministic** Claude Code hook `hooks/mnemo-skill-echo.sh` on `UserPromptExpansion` emits a `systemMessage` confirmation (`🧠 mnemo: /mn:save → skill body loaded`) on every `/mn:*` expansion, gated by `hooks.invocationEcho` (default **true**). Live-verified on Claude Code 2.1.215: the event fires for plugin slash commands (`command_source: "plugin"`), and hook output never alters the expansion. Codex 0.140.0 silently ignores this unsupported event; v1.2.3 routes it only to Claude instead of depending on that tolerance.
- **Regression coverage** — `test_every_skill_body_carries_its_invocation_marker` (marker present exactly once, ahead of Portable paths, in all seven skills) and `test_skill_echo_hook_announces_mn_commands_only_and_respects_gate` (announce / foreign-command silence / config gate / missing-config default).

## [1.2.1] - 2026-07-19

### Fixed

- **Backward-compatible Codex hook discovery** — removed optional top-level metadata from the shared `hooks/hooks.json`, so older Codex plugin parsers that accept only the `hooks` object load mnemo's lifecycle hooks without an `unknown field` startup error. Current Codex and Claude Code use the same hook definitions and behavior as before.

## [1.2.0] - 2026-07-19

### Added

- **Native Codex skill presentation** — every canonical skill now has `agents/openai.yaml` with a short `mn:*` UI label and a deterministic `$mnemo:*` starter prompt.
- **Dual-runtime contract validation** — `scripts/lint-skills.py` now enforces the seven-skill inventory, Agent Skills naming rules, invocation metadata, manifest namespaces, and absence of duplicate routers.
- **Runtime regression harness** — `scripts/test-runtime-compat.py` covers Codex JSONL parsing, Claude direct-command envelopes, nested-cwd discovery, runtime isolation, private caches, portable hook commands, and Claude/Codex hook schemas.

### Changed

- **Seven canonical short skills** — implementation directories and frontmatter names are now exactly `ask`, `save`, `session`, `review`, `connect`, `setup`, and `health`; workflow bodies remain shared across Claude Code and Codex.
- **Claude namespace is `mn`, package identity remains `mnemo`** — marketplace installs stay `mnemo@mnemo`, while Claude Code now registers exact `/mn:*` commands directly from canonical skills. Codex keeps its stable `mnemo` component namespace and explicit `$mnemo:*` IDs.
- **Portable skill execution** — bundled scripts/references resolve from the loaded `SKILL.md` path instead of assuming `${CLAUDE_PLUGIN_ROOT}` exists in normal Codex shell calls. `review` now collects evidence through ordinary tools instead of Claude-only `!command` preprocessing, and `session-scan.py` recognizes `CODEX_THREAD_ID`.
- **Runtime-safe hooks and discovery** — one shared hook manifest emits official cross-runtime hook payloads with runtime-native invocation syntax. Codex-compatible synchronous prewarming runs against the tiny SessionStart transcript and fails open. Session scanning ignores documentation-only command mentions, and skill discovery works from nested directories while excluding the other runtime's private scopes and stale plugin generations.
- **Runtime-isolated memory checks** — `ask` uses the active runtime's local memory, while `health` only inspects Claude auto-memory and claude-mem state inside Claude Code; Codex never scans `~/.claude/` as its own state.

### Fixed

- **Hook semantics across both runtimes** — SessionStart now injects model context through `hookSpecificOutput.additionalContext`, Stop continuation uses `decision: block`, and unsupported `async` declarations no longer cause Codex to skip prewarming.
- **Shell-safe vault writes** — generated markdown is written through Obsidian MCP only; inline `obsidian create/append/prepend ... content=` fallbacks were removed and are now rejected by the linter.
- **Shell-safe indexed reads** — vault names, note names, search terms, concepts, prefixes, and metadataCache paths now flow through one allowlisted `safe-read.py` adapter using argv (`shell=False`) and JSON-encoded JavaScript literals; direct Obsidian CLI commands in skill bodies are lint failures.
- **Private helper caches** — session/discovery caches and Stop anti-loop markers now use hashed names, owner/mode checks, symlink-safe reads, and atomic `0600` replacement inside a per-user `0700` directory.
- **Vault-contained handoff rotation** — the archive helper rejects traversal, out-of-vault targets, symlinked handoff notes, and a handoff/archive collision before any write; regression coverage now includes both handoff and archive escape attempts.

### Removed

- **Legacy routing layers** — deleted seven `commands/mn/*` wrappers plus eight alias/compatibility skill directories. Old `/mnemo:*` and `/mnemo:mn:*` spellings no longer resolve; use `/mn:*` in Claude Code or `$mnemo:*` in Codex.
- **Redundant vault-path shell helper** — dynamic vault resolution now lives in the single allowlisted `safe-read.py` adapter.

## [1.1.11] - 2026-07-17

### Fixed

- **handoff-archive.py corrupted the live handoff on every `--execute` run** — production incident (16-17.07: glued `## 2026-03-25…## 2026-07-16…` headers in the hot handoff, frontmatter/guard eaten, 5+ stray duplicate headers piling up in the archive). Two root causes: (1) *loop-variable shadowing* — the per-block `header = b.split('\n', 1)[0]` overwrote the document header parsed earlier, so every rewrite began the file with the LAST block's first line (no trailing newline) glued straight onto the first hot block, while the orphaned dated header left behind was counted as a fresh block by the next run and re-archived — hence the accumulating duplicates; (2) *unnormalized join* — `''.join(blocks)` glued any block lacking its trailing `\n` (typically the file's last block) onto the next `## header`, in both the handoff and the archive. Fixed by renaming the loop variable (`first_line`) and joining through a newline-guaranteeing `joined()` helper.
- **First automated regression tests in the repo** — `scripts/test-handoff-archive.py` (stdlib-only unittest + subprocess, no framework): doc-header survival + zero glued headers, archive-append normalization with a missing trailing newline, and byte-stable idempotency of repeated runs. Run directly: `python3 scripts/test-handoff-archive.py`.
- **CHANGELOG compare-links backfilled** — versions 1.1.7–1.1.10 shipped without their compare-links (and without git tags; tags `v1.1.7`–`v1.1.10` are created retroactively with this release).

## [1.1.10] - 2026-07-06

### Fixed

- **handoff-archive.py dropped prose-live blocks into cold** — the "keep hot" test only checked for `- [ ]` checkboxes, so a block whose still-open state lived in its header prose ("— В ПРОЦЕССЕ", "— WAITING FEEDBACK", "(PENDING ответ)") could be archived while genuinely live (a real drop-off found in adversarial verification). Added a header-level pending detector (`В ПРОЦЕССЕ` / `НЕ закрыто` / `ждём` / `отложено` / `WAITING` / `PENDING` / `IN PROGRESS` / `TODO` / `BLOCKED`) to the keep-hot rule — **header-only**, since a body `Pending:` section is too noisy (most completed blocks carry one). A block now cools only when past the keep-days cutoff AND has no open checkbox AND no header pending-marker.

## [1.1.9] - 2026-07-06

### Added

- **Structured property-search recall** (`vault-search` Step 3a) — `/mn:ask` now queries the typed-Properties layer, not just fuzzy fulltext. For filterable/countable questions ("what's open", "all sessions about X", "sources I disagreed with", "notes citing Y") it runs Obsidian's property-search syntax (`[status:open]`, `[type:session]`, `[disagreements]`, `[prop:null]`) — precise enumeration that matches the vault's Bases. Also teaches recall to READ a control-panel `.base` file (plain YAML) as a canonical computed index and reproduce its filter, preferring that deterministic path over keyword guessing. Complements the Bases-first convention added in 1.1.8.

## [1.1.8] - 2026-07-06

### Added

- **Vault conventions reference** (`references/vault-conventions.md`) — verified best practices (deep-research 2026-07-06: Obsidian official Help + kepano) for an AI-agent-maintained vault, wired into `memory-routing`: (1) load-bearing `[[links]]` must stay OUTSIDE code fences (links in ` ``` ` blocks are not parsed into the graph — a real agent blind spot); (2) compute indexes with Bases over typed Properties instead of hand-maintaining index notes that drift/bloat; (3) property types are self-policed (Obsidian does not enforce them globally); (4) concurrent human+agent edits have no native merge-conflict safety — use targeted `str_replace`, never blind overwrite. Baseline (atomic notes, near-flat root, File Recovery as the only local undo) confirmed canonical.

## [1.1.7] - 2026-07-06

### Added

- **Handoff size-guard + auto-archive** (`scripts/handoff-archive.py`) — the `session-notes` handoff is a live index, not a store; left un-rotated it grows into a multi-MB log that is a token bomb read every session and buries live pending items under months of closed history. Step 5 now runs the helper each `/mn:session`: blocks with an open `- [ ]` **or** within the last `handoff.keepDays` (default 14) stay hot; CLOSED older blocks move verbatim into `<handoff_note> Archive` (cold, not read at session start; a `.bak-<date>` backup is written for undo). No-ops under `handoff.maxKB` (default 40). Never archives a block with an open checkbox. Mirrors the existing `memory.indexWarnKB` MEMORY.md discipline (thin hot index + cold archive + header pointer).
- **Config:** `handoff.maxKB` (default 40) and `handoff.keepDays` (default 14).

## [1.1.6] - 2026-07-06

### Changed

- **`/mn:review` trigger coverage** — added `'что осталось добить'`, `'что надо добить'`, `'что ещё надо добить'` to the `session-review` description (on top of `'что осталось'` / `'что ещё осталось'` / `'что добить до идеала'`), so the orchestrator fires on the "надо добить" phrasings too.

## [1.1.5] - 2026-07-05

### Fixed / Added — e2e-hardening (closes 3 gaps a live e2e pass found)

- **Last bare `references/` link** — `initial-setup` still had one `references/config-schema.md` without `${CLAUDE_PLUGIN_ROOT}/` (ironically added in 1.1.4's own hooks hint). Now qualified; a repo-wide grep confirms **zero** bare references across all skills.
- **`/mn:session` now grounds its narrative** — `session-notes` Step 1 cross-checks "what was done" against `git log` / `git status` and `session-scan.py` before persisting, so a direct `/mn:session` can't fabricate status. This is the same grounding `/mn:review` already ran; previously only `session-review` invoked the scan.
- **Committed trigger-eval** — `evals/trigger-eval.json` (6 proactive positives + 6 near-miss negatives) + `evals/README.md` make the description-trigger check reproducible, so a future `description:` edit can be regression-tested instead of trusted (baseline 12/12). Format is compatible with skill-creator's `run_loop.py`.

## [1.1.4] - 2026-07-05

### Fixed

- **Codex path-cascade in two secondary fallbacks** — `session-review` (REF_DIR) and `session-notes` (template read) now also glob `~/.codex/plugins/cache/…` before the final fallback, matching the primary cascade and `session-scan.py`. Under Codex without `CLAUDE_PLUGIN_ROOT` these had degraded to an empty ref/template (graceful, not a crash); now they resolve.
- **`initial-setup` config template** — the generated `~/.mnemo/config.json` now includes the `hooks` block (`sessionStartNudge` / `stopNudge`) and the `cascade.project_rules` key, matching the documented schema. Everything already worked on defaults; this just makes the toggles discoverable to a new user.
- Docs polish: `session-notes` bare `assets/session-template.md` pointer → `${CLAUDE_PLUGIN_ROOT}/…`; `TESTING.md` header refreshed to v1.1.3 with V13/V14 checks (Stop-nudge session scope, `/mn:review` new trigger phrasings).

## [1.1.3] - 2026-07-05

### Changed

- **`/mn:review` trigger coverage** — added `'что ещё осталось'` and `'что ещё тут осталось'` to the `session-review` description so the orchestrator fires on those phrasings too (previously only `'что осталось'`).

## [1.1.2] - 2026-07-05

### Changed

- **Stop nudge now tracks `/mn:session` too, not just `/mn:save`** (`hooks/mnemo-stop-nudge.sh`). At session end (when `hooks.stopNudge` is on), if the session looks worth-saving but either the discrete save (`/mn:save`) **or** the session note (`/mn:session`) is missing, the nudge blocks once and names whichever is still needed — `/mn:save` pins facts as they happen, `/mn:session` writes the end-of-session narrative + handoff, so a complete wrap-up wants both. Both present → silent. Anti-loop governor and opt-in default (false) unchanged.

## [1.1.1] - 2026-07-05

### Added — proactive nudges via hooks + agent-initiated skill bodies

Descriptions raise the odds an agent reaches for mnemo; hooks add a deterministic *delivery* layer (the model still decides — **deterministic delivery ≠ deterministic effect**). See [design-decisions](docs/design-decisions.md#proactive-nudges-via-hooks-v111).

- **SessionStart nudge** (`hooks/mnemo-context.sh`, `hooks.sessionStartNudge` default **true**) — a one-line "mnemo memory exists; recall with `/mn:ask` before non-trivial work, save with `/mn:save` as you go", gated on a configured vault (silent otherwise), so the agent reaches for memory on its own initiative.
- **Stop nudge** (`hooks/mnemo-stop-nudge.sh`, `hooks.stopNudge` default **false**, opt-in) — if a session looks worth-saving (fix/decision signals) but `/mn:save` never ran, it blocks the stop **once** (anti-loop governor, keyed by session_id) to prompt a save. Opt-in because a blocking Stop hook can loop for arbitrary users of a public plugin; the default install never blocks.
- **`hooks/codex-hooks.json`** — mirrors both nudges for Codex (confirmed: Codex consumes plugin hooks; degrades to a safe no-op if it ignores `additionalContext`/`decision:block`). `hooks/hooks.json` was extended, not replaced — the async `prewarm.sh` is preserved.
- **Agent-initiated skill bodies** — `/mn:ask` derives its query from the task when invoked proactively (doesn't stop to ask the user) with a once-per-topic anti-loop; `/mn:save` gained a worth-saving gate (NOOP for trivia), secret masking (`<REDACTED>`), and a save→connect offer on new notes; `/mn:session` mid-task checkpoint updates the *same* note (dedupe by `session_id`) instead of spawning a duplicate.
- **Config keys** `hooks.sessionStartNudge` / `hooks.stopNudge` documented in `config-schema.md` + `config.example.json`.

Measured: a 12-prompt trigger-eval (6 proactive positives + 6 near-miss negatives) routed **12/12** correctly at the simulated-routing level (`TESTING.md` V9–V12). Caveat: simulation of routing judgment, not a live trigger.

### Fixed

- **`claude-mem-save.sh` aborted on a missing plugin cache** — `set -euo pipefail` killed the version-detect (`ls` non-zero) before the `unknown` fallback and the POST, breaking graceful degradation. Now `set -u` + an explicit cache-dir guard (the `check-cm-version.sh` pattern).
- Code comments in `claude-mem-save.sh` and `.gitignore` translated to English (this is a public plugin).

## [1.1.0] - 2026-07-05

### Changed — proactive self-invocation + doc-blessed visibility

mnemo's skills now describe *when an agent should reach for them mid-task on its own* (not only on an explicit user command), and the `/mn:*` surface is cleaned up to the pattern the official skill docs recommend.

- **Proactive descriptions (7 canonical skills).** Each `description:` now leads with agent-situations — recall before re-fixing a recurring bug / entering an unfamiliar subsystem / a risky change (`/mn:ask`); save right after solving a bug or making a non-obvious decision (`/mn:save`) — followed by the user-phrase triggers, plus Russian keyword tails matching how the maintainer actually types.
- **Visibility (docs "Hide individual skills" + CE pattern).** The 8 alias skills (`mn-*`, `mnemo-mn-*` — the Codex slash layer) are now `user-invocable: false` + `disable-model-invocation: true`, hidden from Claude entirely (removing the duplicate `/mn:ask` in autocomplete) while the files remain for Codex and programmatic `Skill()`. The 7 `commands/mn/*` gained `disable-model-invocation: true`, so the model's auto-invocation listing shows exactly the 7 rich canonical skills, not 15 thin redirects. Users still invoke `/mn:*` via the commands; Codex (which doesn't honor these Claude-Code fields) keeps its slash layer.

### Fixed

- **`references/` paths didn't resolve** — bare `references/X.md` (read relative to cwd, not the plugin root) → `${CLAUDE_PLUGIN_ROOT}/references/` across 7 skills, matching the scripts convention.
- **`/mn:review` order contradiction** — Rules said `session → save` while Step 7 + the example said `save → session`; unified to `save → session`.
- **claude-mem save block → `scripts/claude-mem-save.sh`** — the ~20-line inline bash (carrying the v12.3.9 `text`-not-`content` / dropped-`project` gotcha) is now a script that builds the JSON via python3, so a summary containing quotes / backticks / `$(...)` can no longer break or execute the request. Guarded with `set -u` + a cache-dir check so a missing claude-mem degrades gracefully instead of aborting.
- **`/mn:session` had no Codex write path** — the vault note needs the Obsidian MCP (Claude-only) and there's no shell-safe CLI create, so the path is now Claude-primary with a graceful Codex fallback (summary to a timestamped `~/.codex/memories/` file) + `CODEX_SESSION_ID`.
- **`/mn:setup` taxonomy config** — full JSON now shown for PARA and Custom (was only Zettelkasten); `session`/`moc` documented as functional types kept in every taxonomy.
- **Overtrigger tightening** — `/mn:ask` no longer fires on every bugfix (scoped to recurring/previously-seen bugs); `/mn:connect` skips a `mn:save` that only appended to an existing note. Fragile `$0`-based path fallbacks replaced with cache-glob candidates.

## [1.0.0] - 2026-07-05

First stable release. **No skill/CLI behavior change from 0.16.0** — this milestone declares the `/mn:*` surface stable and codifies the release-governance policy below.

### Added — versioning & approval gate

`AGENTS.md ## Releasing` now codifies SemVer-from-1.0.0 with a per-digit release-autonomy rule, so version bumps stop happening unprompted:

- **patch** (`1.0.z`) — bug fixes, doc/wording tweaks, internal refactors with no user-visible behavior change → an agent **may** cut it autonomously.
- **minor** (`1.y.0`) — any new or changed user-visible behavior (new skill, flag, config key, reworked flow) → **requires the maintainer's explicit approval before the bump**; propose, don't self-approve.
- **major** (`x.0.0`) — breaking changes → maintainer approval too.
- When unsure which it is, treat it as minor and ask. The gate governs the *version bump*, not the work — implement and commit freely, stop at the manifest bump.

## [0.16.0] - 2026-07-05

### Changed — `/mn:review` no longer auto-runs save + session

Step 7 "Auto-Execute Core Skills" is gone. `/mn:review` still audits the session and extracts unsaved decisions/findings, but **nothing runs without one explicit confirmation** (Step 8): `/mn:save` and `/mn:session` now appear as top-priority line items in the single recommendation list instead of executing unattended. Rationale: the user invokes `/mn:review` deliberately — silently spawning two more skills takes the session out of their hands, and the SKILLS_INVOKED guard only sees Skill-tool invocations, so manual save/session work in flight could still be double-written.

- **`session-review` SKILL.md**: Step 7 → "Prepare Core Skill Candidates (no auto-run)" — still extracts concrete payloads so the offer reads "3 unsaved decisions (X, Y, Z)", but only stages the invocation; Step 8 → one prioritized offer covering core + remaining skills; new "No auto-run" rule ("analysis is free, execution is confirmed"); frontmatter description updated (no longer advertises "without asking").
- **Actionable-rule confirmation (v0.15.0) unchanged** — a rule still gets its own explicit y/n line item (it writes committed project files); now every other item is confirmed too, so the rule flow is no longer an "exception".
- **Docs aligned**: README (skills table, when-to-use, quick-start), `docs/review.md` (overview, "Core-Skill Recommendations" section replaces "Auto-Execution (v0.5.9)", notes, related skills), `commands/mn/review.md` description, `docs/design-decisions.md` boundary bullet.

## [0.15.0] - 2026-06-24

### Added — actionable rules route to `.claude/rules/` (recall vs auto-inject split)

mnemo now distinguishes two kinds of save and sends them to different homes. A **recall** item (fact / insight / decision / source — "what we did / why") is fetched on demand and still goes to Obsidian + claude-mem + `memory/`. An **actionable rule** ("never do X / always do Y" tied to specific code) must *auto-surface* the moment a future agent opens the relevant file — so it now routes into **`.claude/rules/<domain>.md`** (Claude Code's native path-scoped rules), the granular evolution of the old "dump it in CLAUDE.md" branch. Motivated by a real workflow gap: lessons were being hand-placed into `.claude/rules/` because `/mn:save` had no path for them.

- **`memory-routing` Step 3.5 — `.claude/rules/` routing.** On an actionable-rule save: pick the level (repo-specific → project `.claude/rules/`; cross-project generic → user-global `~/.claude/rules/`), find the file whose `paths:`/domain matches the code the rule governs and append, or **create a new `<domain>.md` (and the dir) when none matches**. Frontmatter guidance makes `paths:` the load trigger (path-scoped auto-load; `description:` is for humans, not loading) and the YAML is verified after write (a broken-indent `paths:` silently drops the file). Plain `Write`/`Edit` (these files live outside the vault — never the Obsidian CLI/MCP). Step 0 classification, the report block, the decision matrix, and the gotchas all gained the recall-vs-rule fork; Step 4 (CLAUDE.md) is now explicitly the fallback.
- **`cascade.project_rules.enabled` (default true).** New config toggle gating Step 3.5. Fires **only** for actionable-rule saves — recall items are never touched — so a default install routes a rule to `.claude/rules/` but still writes nothing extra for ordinary notes. Set false to keep rules out of the cascade. Documented in `config-schema.md` (schema block, field reference, defaults line).
- **`/mn:review` interactive rule-routing (Step 8).** The orchestrator's session scan now detects actionable rules learned in the session, and — because routing one **creates/edits committed project files** — surfaces them for a y/n in Step 8 instead of writing unattended (recall items still auto-save silently). On accept it delegates to `memory-routing` Step 3.5, keeping a single write path. A direct `/mn:save` of a rule still routes automatically.

### Changed
- **`docs/design-decisions.md`** — new "Recall memory vs auto-inject rules" section documents the split, the project-vs-global decision, and the **deliberate boundaries**: `/mn:session` stays a pure narrative channel (rule-routing there was rejected), the orchestrator confirms before writing project files, and the Codex/`AGENTS.md` 32 KiB caveat is acknowledged but not owned by mnemo.

## [0.14.1] - 2026-06-21

### Fixed — `/mn:health` content-lint report aggregation (found by live smoke-testing v0.14.0)

- **The lint report could overstate the still-valid count when the lint runs in a spawned subagent** (`review.lint.model` ≠ haiku). On a live run the fork's Step 9 summary reported "15 still-valid" while the lint subagent had actually returned **13 still-valid + 2 update-needed** — the fork defaulted the count to the candidate total instead of waiting for and aggregating the subagent's verdicts. **Writes were always correct** (only still-valid notes were stamped; the 2 update-needed were correctly left alone) — the defect was reporting-only, but it could hide notes that genuinely need updating from anyone reading just the final report. Step 7.5 now instructs the fork to report the subagent's verdicts verbatim and never assume "all still-valid"; the Step 9 `🔬 Content lint` block carries the actual `still-valid / update-needed / contradicts` breakdown.

### Added
- **`docs/design-decisions.md`** — design philosophy & non-goals: the one principle mnemo follows (human-authored vault, non-destructive, in-agent) and the Karpathy LLM-wiki features deliberately **not** shipped (auto-ingest `raw/`→`wiki/`, web-search imputation in the lint, `hot.md` cache) — each with why, and an on-philosophy "if you want it" note so a contributor can add it opt-in. Linked from `AGENTS.md` + README.

### Changed
- **`TESTING.md` refreshed** — header/status were frozen at v0.9.0/v0.7.3; updated to current and added smoke-check sections for the v0.10–v0.13 features (autodream memory index, type-aware review candidates, content lint, recency-aware recall, code-grounding) alongside the v0.14.0 checks. Corrected stale version/cache references.

## [0.14.0] - 2026-06-21

### Added — close the loop: knowledge compounds, lint self-snoozes, vault growth surfaced

Three opt-in, on-philosophy enhancements distilled from a full audit of Andrej Karpathy's "LLM Wiki" pattern against mnemo's real code (26-agent comparison, every claim adversarially verified). mnemo already matched or exceeded the pattern on maintenance, recall, recency, code-grounding, MOC/hub structure, and the non-destructive stance; these close the few genuine, philosophy-compatible gaps. All are opt-in: a default install still writes nothing (the content lint is off by default), the compounding save is always user-confirmed, and the single auto-write — the `reviewed:` stamp — happens only once you enable the lint.

- **Compounding loop in `/mn:ask`.** After synthesizing an answer across ≥2 notes, `vault-search` Step 6 now offers to **save the synthesis back as a `Molecule`** (via `/mn:save`, with `cites:` + `[[links]]` to the sources pre-attached) so an exploration accumulates instead of evaporating when the conversation ends — Karpathy's "knowledge compounds like interest". Gated on the Molecule bar (a real ≥2-note insight, not a trivial lookup) and never written without the user's go-ahead; the write is delegated to the existing memory-routing cascade (dedup + shell-safe MCP create + mandatory MOC link), not re-implemented.
- **`review.lint.autoStampReviewed` (default true) — self-snoozing lint.** The content lint (Step 7.5) stamps `reviewed: {today}` on notes it judges **still-valid**, closing the snooze loop so a confirmed note stops resurfacing without a manual edit. This is the *only* frontmatter write health can make, and only ever the `reviewed:` field on a still-valid verdict — never content, never on update-needed/contradicts. It fires only when the content lint is enabled (`review.lint.enabled`, default false), so a default install still writes nothing; set `autoStampReviewed: false` to keep the lint suggest-only.
- **Research-gap candidates in `/mn:health` (report-only).** New Step 8.5 turns signal already collected (Step 2 unresolved targets, Step 3/4 tag counts, Step 8 MOC list — no new CLI calls) into the on-philosophy half of Karpathy's "suggest new article candidates": a populous topic tag (≥5 notes) with no MOC, and a recurring external entity cited many times with no `Source —` note. Suggestions only — mnemo points at the gap and the user decides; it deliberately does **not** web-search to fill it (the auto-imputation half is out of scope for a human-authored vault).

Docs: `docs/ask.md`, `docs/health.md`, `config-schema.md`, `config.example.json`, README updated.

### Fixed — repo-wide documentation/consistency sweep

A multi-persona review of the changeset plus a full audit of every project `.md` surfaced and fixed a batch of pre-existing doc/consistency defects:

- **`## {links_section}` double-heading bug.** `links_section` already includes the `##` (e.g. `## Links`), so templates must use `{links_section}`, not `## {links_section}`. The latter produced a malformed `## ## Links` heading — including in `initial-setup`'s **hub-note create template** (every hub note got a broken heading). Fixed across `initial-setup`, `memory-routing`, `vault-search`, and `tool-routing.md`.
- **Canonical command form.** Standardized scattered `/mnemo:*` slash-command examples to the canonical `/mn:*` across all skills (the `mnemo:skill-name` invocation form is unchanged).
- **`config.example.json`** now matches `config-schema.md`: added the documented `memory.indexWarnKB`, removed undocumented/unused `gmail_*` keys.
- **CONTRIBUTING.md** "CLI-first" principle corrected to the hybrid rule (CLI for reads, MCP for markdown writes) — the old wording could lead a contributor to reintroduce the v0.5.10 shell-injection vector.
- **Coherence fixes:** CHANGELOG v0.11.0 "strictly read-only" now notes the v0.14.0 extension; `docs/health.md` example used the wrong `source` budget (30d → 180d) and a stale "never auto-applied" line; `vault-health` Step 9 example used a 14d atom budget (→ 60d); `session-notes` cross-ref pointed at the wrong setup step; README trilingual health example regained its Sessions/MOCs line and the project tree regained `.claude-plugin/marketplace.json`; `TESTING.md` version/count refs refreshed; `docs/setup.md`/`docs/review.md` stale lines corrected.

## [0.13.0] - 2026-06-21

### Added — `/mn:ask` grounds recall in the live code

- **New Step 4c in `vault-search`: code grounding.** For *current-state* questions ("is X still true / what changed") run from inside a git project, `/mn:ask` now cross-checks the **project repo's recent commits** (`git log --grep` / `-- path` in the CWD repo, distinct from the vault) and flags any cited note a newer commit may have outdated — so recall agrees with the code, not just with old notes. **Auto-gated:** fires only inside a git repo AND for current-state intent (pure decision-rationale recall skips it). Extends the existing multi-store / git-shelling pattern (Steps 3b/4b) rather than adding a separate skill.
- **`recall.codeGraph` config seam (default off).** Optional code-knowledge-graph backend for structural "what's where" context — a file-output skill (`"graphify"` → reads its `graph.json` / `GRAPH_REPORT.md`) or an MCP server (`"sourcegraph"` / `"ast-grep"` / `"tree-sitter-analyzer"`). Ships dark; a no-op unless you set it and have the backend installed. Documented in `config-schema.md` + `config.example.json`; `docs/ask.md` + README updated.

## [0.12.1] - 2026-06-21

### Fixed — `/mn:ask` recency: separate "last changed" from "stale"

- **A measurement on the real vault caught a v0.12.0 semantic flaw.** v0.12.0 collapsed recency into one "updated" date with precedence `git → reviewed → date → mtime` — so a note edited *today* displayed its **creation** date as "updated" (`date` wrongly outranked `mtime`). Step 4b now reports two distinct signals: **last-changed** = git last-commit (vault is a git repo) else file `mtime`; **stale?** = the content-freshness check delegated to `review-candidates.py` (`max(date, reviewed)` vs the type budget — the same engine `/mn:health` uses), never `mtime`. A file touched today can still be flagged stale, and `/mn:ask` and `/mn:health` now agree on "stale" by construction. `docs/ask.md` + README aligned.

## [0.12.0] - 2026-06-21

### Added — recency-aware recall in `/mn:ask`

- **`vault-search` (`/mn:ask`) now dates every source it cites.** New Step 4b resolves each cited note's last-changed signal — **git last-commit** when the vault is a git repo (e.g. the obsidian-git plugin), else **filesystem mtime** (portable, macOS + Linux) plus frontmatter `date`/`reviewed`. Freshness precedence: git → `reviewed` → `date` → mtime. The synthesis annotates each source with its date and **flags an answer resting on a note older than its type's `review.staleDays` budget**, so recall and the v0.11 staleness model reinforce each other. Reuses the shared `get-vault-path.sh`; recency is fetched only for the ≤7 cited notes, in parallel. `docs/ask.md` + README updated.

## [0.11.2] - 2026-06-21

### Fixed — code-review follow-ups (full multi-persona review of the v0.11.x changeset)

- **`link-discovery` (`/mn:connect`)** carried its own copy of the BSD/macOS-awk `\s` bug that v0.11.1 fixed elsewhere — it inlined `awk '/^path\s/'` instead of using the shared `get-vault-path.sh`, so on macOS `$VAULT_PATH` was empty and `/mn:connect` silently surfaced **zero** connections. Now uses the shared helper. (Pre-existing; the v0.11.x awk fix should have reached this sibling skill.)
- **`vault-health` Step 7.5** described the lint-subagent spawn with Claude-Code-only tool names (`Task` / `subagent_type`) inside a dual-runtime SKILL.md — misleading for Codex. Reworded by capability (Claude Code: Task tool; Codex: `spawn_agent`).
- **`review.staleDays` sample drift** — `README.md` was missing the `molecule` key that `config.example.json` and `config-schema.md` carry; all three now agree.
- **Worked-example types** — `vault-health` Step 9 and `config-schema.md` used a `decision` type that ships in no config (so its `365d` budget wasn't reproducible); switched to shipping types.
- **`scripts/review-candidates.py`** — hand-rolled arg parser → `argparse` (also fixes the `--limit`-before-path footgun); `parse_frontmatter` now caps at 100 lines so an unterminated `---` block can't stream a whole note body; bare-scalar `staleDays` now accepts a numeric string; stale tuple-shape comment corrected. The bare-integer `staleDays` form is now documented in `config-schema.md`.

## [0.11.1] - 2026-06-21

### Fixed

- **`.github/workflows/release.yml`** — the CHANGELOG section extractor now stops at the Keep-a-Changelog link-reference block (`[x.y.z]: https://…`), so releasing the file's oldest/last version no longer appends the whole compare-link list to the GitHub Release body. (Latent in v0.11.0; harmless for any version that has a newer section after it.)
- **`scripts/review-candidates.py`** now emits the resolved per-note threshold (the budget actually applied: per-note `ttl` → per-type → default) as a 6th column. `vault-health` Step 9 and `docs/health.md` report examples now show `(type, Nd budget)` instead of an invented `ttl N` the script never output — a doc/output contract mismatch.
- **`config.example.json`** — added `review.lint.model` (`"haiku"`) so the copy-paste template matches the documented configurable lint model.

## [0.11.0] - 2026-06-21

### Added — type-aware review candidates + optional content lint (Karpathy "lint your wiki")

- **`vault-health` Step 7 reworked into type-aware review candidates.** Staleness is no longer a hardcoded uniform 30 days. New `scripts/review-candidates.py` (pure filesystem, no obsidian-CLI graph dependency) flags notes past a per-**type** threshold from `config.json` → **`review.staleDays`** (e.g. a volatile `atom` ages in 60d, a `decision` in 365d). Precedence: per-note `ttl:` → `review.staleDays.<type>` → `review.staleDays.default` → 30 (legacy fallback when the `review` section is absent — fully backward compatible).
- **`reviewed:` snooze + `ttl:` override (optional per-note frontmatter).** Age is measured from `max(date, reviewed)`, so stamping `reviewed: {today}` on a still-valid note resets its clock — the fix for the "guilt-debt" failure mode of review dates. `ttl: <days>` ages a single note faster/slower than its type default. Deliberately **not** an absolute `review-by:` date (those rot). At this version health never writes either field — strictly read-only *(extended in [0.14.0]: opt-in `autoStampReviewed` lets the content lint auto-stamp `reviewed:` on still-valid notes once the lint is enabled)*.
- **`vault-health` Step 7.5: optional content lint** gated by **`review.lint.enabled`** (default false). When on, an LLM re-reads the top `review.lint.maxCandidates` (default 15) candidates and emits verdicts (still-valid / update-needed / contradicts `[[Other]]`) — Karpathy's "lint your wiki" applied to claims, not the calendar. Triage only, never auto-applied. Together with orphans (Step 1) and unresolved links (Step 2 = "concepts mentioned but missing a page"), health now covers all four of Karpathy's lint checks including **contradictions**.
- **Config + docs:** documented the `review` section and the optional `reviewed`/`ttl` frontmatter in `references/config-schema.md`, added the block to `config.example.json`, and refreshed `docs/health.md`. `memory-routing` now notes that staleness is type-driven (no review date to stamp at save time; `ttl:` only for fast-rotting facts).

### Added — configurable lint model

- **`review.lint.model`** (default `haiku`) selects the model for the Step 7.5 content lint. The lint runs as a spawned subagent, so the cheap `haiku` health fork stays cheap while verdicts can run on `sonnet`/`opus` when you want higher quality.

### Added — `/rs` research skill (standalone, global)

- New standalone personal skill `~/.claude/skills/rs/` — give it a GitHub repo or news URL and it vets hype-vs-substance: checks your vault & `memory/` **first** (Step 0), fans out across GitHub internals + Twitter/Reddit/HN/Lobsters/Bluesky, adversarially verifies claims, and returns an adopt / defer-until-pain verdict. Not part of mnemo (general research), but consults mnemo's vault-search.

### Changed — stronger skill auto-trigger descriptions

- `memory-routing` and `vault-search` descriptions gained more trigger phrases (incl. `помни`, `в памяти`, `отложи в память`, `напомни мне`, `посмотри в память`, `найди в памяти`) per Anthropic's skill-authoring best practices — addresses occasional under-triggering on paraphrased/misspelled Russian input.

### Changed — changelog is now single-source (Keep a Changelog v2 + GitHub Releases)

- `CHANGELOG.md` adopts Keep a Changelog v2 (an `[Unreleased]` section + version compare-links). A new `.github/workflows/release.yml` mirrors each tag's section into a GitHub Release on push. The trilingual README keeps only a short "What's New" summary + a link here.

### Fixed — `get-vault-path.sh` returned empty on macOS

- The helper matched `awk '/^path\s/'`, but `\s` is unsupported by macOS/BSD awk → it returned an empty path even with Obsidian running, breaking `vault-health` Steps 5/7. Now splits on tab (`awk -F'\t' '$1=="path"'`). Affected every macOS user.

### Removed — inbox taxonomy remnants

- The `inbox-triage` skill (`/mn:sort`) was removed in v0.9.0; this release cleans the leftover `inbox` type from `config.example.json`, deletes `docs/sort.md`, and drops inbox references from `docs/health.md` / `docs/setup.md`.

## [0.10.4] - 2026-06-21

### Changed — session notes never gated by "significance" + same-day dedup hardened

- **`session-notes` / `session-review`**: a research / exploration / personal-curiosity session is no longer mis-classified as "trivial" and skipped — it always gets a session note, even with zero code. Closes a loophole where a no-code research session could be silently dropped (`session-notes` When-to-Trigger + Rules, `session-review` Step 7). "Trivial" is now explicitly narrowed to mechanical one-liners (typo, single rename).
- **`session-notes` Step 2 (duplicate check)**: hardened against the many-sessions-in-one-day footgun. A same-day match is context, NOT a reason to skip creation or assume the note already exists (that silently lost sessions). On an exact-filename collision, lead with append/continuation via `mcp__obsidian__insert` / `str_replace` — never silent-skip, never auto-clobber with `create`.

### Changed — README rewrite (trilingual)

- Condensed the long per-version "What's New" wall into a short "What's New (v0.10.x)" + a link to this CHANGELOG; the full history lives here.
- Synced all three language sections (EN / RU / 中文): 7 skills (inbox-triage long removed), Codex + Claude dual-runtime everywhere, a new "When to use which" cadence chapter, accurate v0.10.x facts. Fixed the broken top-of-file language-anchor links and a duplicated section heading.

## [0.10.3] - 2026-06-13

### Added — complete Codex mn slash alias coverage

- Added the missing Codex-native **`/mn:review`** alias for `mnemo:session-review`, matching the existing Claude Code command and the documented "one command to end a session" workflow.
- Added compatibility aliases for accidental namespaced invocations: **`/mnemo:mn:ask`**, **`/mnemo:mn:save`**, **`/mnemo:mn:session`**, and **`/mnemo:mn:review`**. The canonical commands remain `/mn:*`, but old muscle memory now routes instead of failing with "Unrecognized command".
- Updated Codex docs and starter prompts to make `/mn:review` the default session-close entry point.

## [0.10.2] - 2026-06-12

### Added — Codex slash aliases for Claude-compatible mnemo commands

- Added Codex-native alias skills for **`/mn:ask`**, **`/mn:save`**, and **`/mn:session`**. They route to the existing `vault-search`, `memory-routing`, and `session-notes` skills respectively, so Codex users can keep the same muscle memory as Claude Code.
- Updated the Codex starter prompts to advertise the short `/mn:*` entry points instead of the longer `$mnemo:*` skill names.
- This is additive: existing Claude Code commands under `commands/mn/` and existing Codex skill names (`mnemo:vault-search`, `mnemo:memory-routing`, `mnemo:session-notes`) continue to work.

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

[Unreleased]: https://github.com/jojoprison/mnemo/compare/v1.2.5...HEAD
[1.2.5]: https://github.com/jojoprison/mnemo/compare/v1.2.4...v1.2.5
[1.2.4]: https://github.com/jojoprison/mnemo/compare/v1.2.3...v1.2.4
[1.2.3]: https://github.com/jojoprison/mnemo/compare/v1.2.2...v1.2.3
[1.2.2]: https://github.com/jojoprison/mnemo/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/jojoprison/mnemo/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/jojoprison/mnemo/compare/v1.1.11...v1.2.0
[1.1.11]: https://github.com/jojoprison/mnemo/compare/v1.1.10...v1.1.11
[1.1.10]: https://github.com/jojoprison/mnemo/compare/v1.1.9...v1.1.10
[1.1.9]: https://github.com/jojoprison/mnemo/compare/v1.1.8...v1.1.9
[1.1.8]: https://github.com/jojoprison/mnemo/compare/v1.1.7...v1.1.8
[1.1.7]: https://github.com/jojoprison/mnemo/compare/v1.1.6...v1.1.7
[1.1.6]: https://github.com/jojoprison/mnemo/compare/v1.1.5...v1.1.6
[1.1.5]: https://github.com/jojoprison/mnemo/compare/v1.1.4...v1.1.5
[1.1.4]: https://github.com/jojoprison/mnemo/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/jojoprison/mnemo/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/jojoprison/mnemo/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/jojoprison/mnemo/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/jojoprison/mnemo/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/jojoprison/mnemo/compare/v0.16.0...v1.0.0
[0.16.0]: https://github.com/jojoprison/mnemo/compare/v0.15.0...v0.16.0
[0.15.0]: https://github.com/jojoprison/mnemo/compare/v0.14.1...v0.15.0
[0.14.1]: https://github.com/jojoprison/mnemo/compare/v0.14.0...v0.14.1
[0.14.0]: https://github.com/jojoprison/mnemo/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/jojoprison/mnemo/compare/v0.12.1...v0.13.0
[0.12.1]: https://github.com/jojoprison/mnemo/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/jojoprison/mnemo/compare/v0.11.2...v0.12.0
[0.11.2]: https://github.com/jojoprison/mnemo/compare/v0.11.1...v0.11.2
[0.11.1]: https://github.com/jojoprison/mnemo/compare/v0.11.0...v0.11.1
[0.11.0]: https://github.com/jojoprison/mnemo/compare/v0.10.4...v0.11.0
[0.10.4]: https://github.com/jojoprison/mnemo/compare/v0.10.3...v0.10.4
[0.10.3]: https://github.com/jojoprison/mnemo/compare/v0.10.2...v0.10.3
[0.10.2]: https://github.com/jojoprison/mnemo/compare/v0.10.1...v0.10.2
[0.10.1]: https://github.com/jojoprison/mnemo/compare/v0.10.0...v0.10.1
[0.10.0]: https://github.com/jojoprison/mnemo/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/jojoprison/mnemo/compare/v0.8.2...v0.9.0
[0.8.2]: https://github.com/jojoprison/mnemo/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/jojoprison/mnemo/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/jojoprison/mnemo/compare/v0.7.4...v0.8.0
[0.7.4]: https://github.com/jojoprison/mnemo/compare/v0.7.3...v0.7.4
[0.7.3]: https://github.com/jojoprison/mnemo/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/jojoprison/mnemo/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/jojoprison/mnemo/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/jojoprison/mnemo/compare/v0.6.2...v0.7.0
[0.6.2]: https://github.com/jojoprison/mnemo/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/jojoprison/mnemo/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/jojoprison/mnemo/compare/v0.5.10...v0.6.0
[0.5.10]: https://github.com/jojoprison/mnemo/compare/v0.5.9...v0.5.10
[0.5.9]: https://github.com/jojoprison/mnemo/compare/v0.5.8...v0.5.9
[0.5.8]: https://github.com/jojoprison/mnemo/compare/v0.4.0...v0.5.8
[0.4.0]: https://github.com/jojoprison/mnemo/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jojoprison/mnemo/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jojoprison/mnemo/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jojoprison/mnemo/releases/tag/v0.1.0

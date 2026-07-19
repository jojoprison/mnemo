# Testing — mnemo smoke tests (current: v1.2.2)

mnemo has an automated structural/runtime regression gate plus manual end-to-end smoke tests. Run the automated gate after every skill, manifest, hook, or helper change; run the relevant manual checks after `/plugin update mnemo@mnemo` or `codex plugin add mnemo@mnemo`.

## Automated gate

```bash
python3 scripts/lint-skills.py
python3 scripts/test-runtime-compat.py
python3 scripts/test-handoff-archive.py
claude plugin validate plugins/mnemo --strict
python3 /path/to/plugin-creator/scripts/validate_plugin.py plugins/mnemo
```

The first three commands are repository-owned regression tests. The last two are the official Claude Code and Codex plugin validators; replace `/path/to/plugin-creator` with the installed Codex `plugin-creator` skill directory. All five must pass before release.

The manual suite below has two layers: the **6 per-skill checks** (version-agnostic — do the workflows still behave?) and the **"What changed in vX" feature checks** (run the groups relevant to your change).

## Status

- **Last full per-skill pass:** v0.7.3 — 7/7 clean on 2026-04-24 (large opus-4-7[1m] session; universal red flag never fired; two claude-mem v12.3.9 API bugs found in Check #4, patched in v0.7.4).
- **Feature checks v0.10–v0.14** added 2026-06-21 (this is the checklist; not yet run end-to-end on a fresh install). The v0.14.0 write-path check (V3) is the highest priority — it is the first frontmatter write `/mn:health` can make.

## What changed in v1.2.0 — canonical dual-runtime surface

- **R1 — exact inventory.** Claude Code discovers exactly `/mn:ask`, `/mn:save`, `/mn:session`, `/mn:review`, `/mn:connect`, `/mn:setup`, and `/mn:health`; Codex discovers exactly the corresponding `$mnemo:*` IDs with `mn:*` picker labels. No command routers or compatibility aliases appear.
- **R2 — one implementation each.** Every runtime resolves the same seven `skills/<name>/SKILL.md` bodies. Claude-only presentation comes from its `mn` manifest namespace; Codex-only presentation comes from `agents/openai.yaml`, never copied workflow text.
- **R3 — runtime hooks.** In fresh Claude and Codex sessions, SessionStart injects the runtime-native ask/save nudge, synchronous prewarm does not block startup, and the opt-in Stop nudge blocks at most once with the correct native invocation syntax.
- **R4 — safe degradation.** With claude-mem disabled or fully absent, both runtimes continue through Obsidian and their own local-memory fallback without starting or repairing claude-mem. Dynamic vault values remain JSON/argv data, and handoff/archive paths cannot escape the resolved vault.

## What changed in v1.2.1 — hook-parser compatibility

- **R5 — legacy Codex hook parser.** The shared `hooks/hooks.json` keeps `hooks` as its only top-level key. A fresh Codex process must load the plugin without an `unknown field 'description'` hook error, while Claude Code validation and the SessionStart/Stop payload tests remain green.

## What changed in v0.7.3

Model routing was rewritten to prevent mid-session model switches from triggering `API Error: Extra usage is required for 1M context` on Max plans. Three current skills run in isolated forked subagents (`context: fork` + `haiku` or `sonnet`); the remaining four inherit the session model (`model: inherit`). See [CHANGELOG](./CHANGELOG.md#073---2026-04-24).

## What changed in v0.7.4

`/mn:save`'s claude-mem POST body switched from `content` → `text` to match v12.3.9 (previously returned `{"error": "text is required"}`). Key provenance (note name, vault, CM version) is now embedded in the `text` itself because v12.3.9 silently drops custom `metadata.*` fields — full-text search keeps the link back to Obsidian until upstream restores persistence.

## What changed in v0.10–v0.13 — smoke checks

Feature checks for the releases between v0.9 and v0.14. Run after `/plugin update mnemo@mnemo`.

- **A1 — Autodream-aware memory index (v0.10).** `/mn:health` Step 10: on a project whose `memory/MEMORY.md` exceeds `memory.indexWarnKB` (default 22), the report warns to run autodream (the index hard-truncates ~24.4 KB on load). Verify the threshold is read from config — set `memory.indexWarnKB: 5` on a small index → the warning fires earlier.
- **A2 — Type-aware review candidates (v0.11).** `/mn:health` Step 7: a stale `atom` is flagged against the **atom** budget (60d), not a flat 30; a note whose `reviewed:` is newer than its `date:` is **not** flagged (snooze); a note with per-note `ttl: 14` ages on 14 days regardless of type. With no `review` config → falls back to a uniform 30 days.
- **A3 — Content lint (v0.11, opt-in).** With `review.lint.enabled: true`, `/mn:health` Step 7.5 re-reads the top candidates and emits still-valid / update-needed / contradicts verdicts on `review.lint.model`. With it `false` (default) → the step is skipped silently.
- **A4 — Recency-aware recall (v0.12).** `/mn:ask` annotates each cited source with `changed YYYY-MM-DD` (git last-commit if the vault is a repo, else file mtime) and ⚠️-flags any cited note older than its type budget. "changed today" must NOT clear a stale flag — touch ≠ fresh (staleness uses `date`/`reviewed`).
- **A5 — Code-grounding (v0.13).** Run `/mn:ask` about *current state* ("is X still true / what changed") from **inside a git project** (CWD a repo, separate from the vault): it cross-checks the project's recent commits and flags a cited note a newer commit may have outdated. A pure "why did we decide" recall must NOT trigger it. `recall.codeGraph` stays off unless a backend is configured.

## What changed in v0.14.0 — smoke checks for the new behaviors

Three opt-in features were added (see [CHANGELOG](./CHANGELOG.md#0140---2026-06-21)). Run these after `/plugin update mnemo@mnemo`. The **stamp check (V3) is the highest priority** — it is the first and only frontmatter write `/mn:health` can make, and it had no automated coverage.

- **V1 — Compounding loop (`/mn:ask`).** Ask a question whose answer synthesizes ≥2 notes. Expect Step 6 to *offer* "save this synthesis as a Molecule" (not auto-save). Accept → confirm one `Molecule — …` note is created via `/mn:save` with a `cites:` frontmatter field and the source `[[links]]` pre-populated. Ask a question with **one** hit or **no** hits → the offer must NOT appear (Molecule-bar gate).
- **V2 — Research-gap candidates (`/mn:health`).** On a vault with a tag used ≥5 times and no matching `MOC — {Topic}`, the report shows a `🌱 Research-gap candidates` block suggesting the MOC. On a vault where every populous tag already has a MOC → block is omitted (no false suggestion). Never auto-creates anything.
- **V3 — autoStampReviewed write-path (`/mn:health`, the one write).** Set `review.lint.enabled: true` in `~/.mnemo/config.json` (default leaves it off — verify that with the flag off, health writes **zero** frontmatter). With lint on and `autoStampReviewed: true` (default), run `/mn:health` on a vault holding a stale-but-still-valid note. **Read the note back** and assert: `reviewed:` was added/updated to today's date, inside the `---` frontmatter block, with the note body unchanged. Then set `autoStampReviewed: false`, re-run, and assert the report only *recommends* the stamp and the file is **not** modified. Red flag: any write to a note the lint judged `update-needed`/`contradicts`, or any body-text change — health must only ever touch the `reviewed:` field of a still-valid note.

**Universal red flag for every test below:** if you see `API Error: Extra usage is required for 1M context` during any skill invocation, the routing regressed — a skill is still forcing a model switch in the main session. File an issue with the skill name.

## What changed in v0.15.0 — smoke checks for actionable-rule routing

`/mn:save` now splits **recall** (Obsidian/claude-mem/memory) from **actionable rules** (`.claude/rules/`), see [CHANGELOG](./CHANGELOG.md#0150---2026-06-24). Run after `/plugin update mnemo@mnemo`.

- **V4 — actionable rule → `.claude/rules/` (the new write path).** In a git project that has a `.claude/rules/` dir, run `/mn:save` with a rule phrased as never-X/always-Y tied to a file (e.g. "after touching `auth.py`, always validate the token first"). Assert the rule is **appended to — or created as — a `.claude/rules/<domain>.md`** whose `paths:` covers that file, and is **NOT** written to `memory/`, Obsidian, or CLAUDE.md (one kind → one home). Read the file back: valid YAML frontmatter, `paths:` present, rule under a sensible section. In a project with **no** `.claude/rules/` dir, the same save must **create the dir + file** (create-if-absent), not silently fall back to CLAUDE.md.
- **V5 — recall item is untouched by the rule path.** Run `/mn:save "we decided X because Y"` (a recall decision). Assert the report shows `3.5 .claude/rules ⏭ skipped (recall item)` and the item lands in Obsidian/`memory/` as before — the rule branch must NOT fire for recall.
- **V6 — `cascade.project_rules` toggle + `/mn:review` confirmation.** With `cascade.project_rules.enabled: false`, a rule save falls back to CLAUDE.md/`memory/` and leaves `.claude/rules/` untouched. With it on (default), run `/mn:review` after a session that learned a rule: the orchestrator must **surface the rule for y/n in Step 8** (not write the committed project file unattended); accepting delegates the write to save Step 3.5 (single code path).

## Proactive description checks — introduced in v1.1.0, current surface in v1.2.2

- **V7 — one canonical surface.** After loading the current plugin, Claude Code lists exactly seven `/mn:*` skills and Codex lists exactly seven `mn:*` UI labels backed by `$mnemo:*` IDs. There are no `commands/`, alias skills, `/mnemo:*`, or `/mnemo:mn:*` duplicates.
- **V8 — references resolve portably.** Trigger a skill that points at a shared reference or script. `<mnemo-root>` must resolve from the loaded `SKILL.md` path in Codex and from `${CLAUDE_PLUGIN_ROOT}` in Claude Code; no versioned cache hunting and no literal `<mnemo-root>` may reach a shell.

## What changed in v1.1.1 — proactive hooks + agent-initiated bodies

- **V9 — SessionStart nudge (`hooks/mnemo-context.sh`).** With a configured vault, a new session's context includes the one-line mnemo nudge. Direct smoke: `bash hooks/mnemo-context.sh` → prints `hookSpecificOutput.additionalContext`; `HOME=/tmp/empty bash …` → `{"continue":true,"suppressOutput":true}` (silent unconfigured); `hooks.sessionStartNudge:false` → silent. **(smoke-passed 2026-07-05)**
- **V10 — Stop nudge governor (`hooks/mnemo-stop-nudge.sh`, opt-in).** Default (`hooks.stopNudge` absent/false) → always `pass`, never blocks. With `hooks.stopNudge:true` + stdin `{"session_id":"x","transcript_path":"<file>"}` and ≥3 fix/decision signals: **neither** `mn:save` nor `mn:session` in the transcript → `block` listing both ONCE; **only** `mn:save` present → `block` listing `/mn:session`; **only** `mn:session` present → `block` listing `/mn:save`; **both** present → `pass`; second call same session_id → `pass` (anti-loop); <3 signals → `pass`. **(smoke-passed 2026-07-05 — save+session tracking; earlier caught + fixed a `grep -c` double-zero bug)**
- **V11 — agent-initiated recall (`/mn:ask` body).** Invoked proactively (not by the user), Step 1 derives the query from the task and does NOT ask "what would you like to find". Nothing found → one line, back to work; a topic is recalled at most once per session.
- **V12 — worth-saving gate (`/mn:save` body).** Proactive save of trivial/routine content → NOOP ("nothing worth persisting"). Content with a secret → masked `<REDACTED>`. An explicit user save that creates a note offers `/mn:connect`; a proactive mid-task save delegates to connect immediately, but connect still never applies links without confirmation.

**Measured — trigger-eval (2026-07-05):** 12-prompt routing eval (6 proactive positives + 6 near-miss negatives) → **12/12** correct (recall 6/6, specificity 6/6) at the simulated-routing level; near-miss traps on shared words (`сохрани`/`здоровье`/`свяжись`/`поищи`) all held. Caveat: simulation of agent routing judgment, not a live CC trigger; n=1 per case. Follow-up (non-blocking): widen to ~5/skill + save↔council and ask↔health boundary cases.

## What changed in v1.1.2 / v1.1.3 — Stop-nudge scope + review triggers

- **V13 — Stop nudge tracks `/mn:session` too (v1.1.2).** Covered by V10 above: with `hooks.stopNudge:true` and worth-saving signals, the nudge now blocks on either missing `/mn:save` **or** `/mn:session` (both present → silent).
- **V14 — `/mn:review` trigger phrasings (v1.1.3).** The `review` description now fires on `'что ещё осталось'` / `'что ещё тут осталось'` in addition to `'что осталось'`. Type one mid-session → the orchestrator should engage.

## What changed in v1.2.2 — invocation visibility (marker + expansion echo)

- **V17 — in-body invocation marker.** Every `skills/*/SKILL.md` opens with an instruction to begin the reply with the exact line `🧠 mn:<skill> (mnemo) → running` (guarded by `test_every_skill_body_carries_its_invocation_marker`: present exactly once, ahead of Portable paths). Invoke any `/mn:*` command → the reply should start with the marker (probabilistic — model compliance, both runtimes).
- **V18 — expansion echo hook (`hooks/mnemo-skill-echo.sh`).** Covered by `test_skill_echo_hook_announces_mn_commands_only_and_respects_gate`: `mn:*` command → `systemMessage` announce; foreign command → silent continue; `hooks.invocationEcho:false` → silent; missing config → announce (default on). Live payload schema captured on CC 2.1.215 (`expansion_type`/`command_name`/`command_source`); three headless runs verified hook stdout never alters the skill expansion; interactive-UI rendering **confirmed live 2026-07-20**: Claude Code renders the hook line as `⌊ UserPromptExpansion says: 🧠 mnemo: /mn:ask → skill body loaded` right under the prompt (headless `-p` transcripts still do not record it — a `-p` quirk, not a hook limitation). Bonus empiric: the plugin's event hooks took effect right after `claude plugin update`, without a session restart.

## What changed in v1.1.11 — handoff-archive corruption fix + first automated tests

- **V15 — automated regression suite.** `python3 scripts/test-handoff-archive.py` → 5 tests OK. This is the fastest check for the whole class: doc-header survival, zero glued `## date## date` headers, archive-append normalization, idempotent repeated runs, and vault containment for handoff/archive paths.
- **V16 — live handoff integrity after `/mn:session` (v1.1.11).** After a session where the size-guard actually archived blocks: the handoff still starts with its original header (frontmatter/guard, exactly one `SIZE-GUARD` line), `grep -c 'research##'`-style glued headers = 0, and the archive gained each cold block exactly once (no duplicate stray headers accumulating run-over-run).

## Prerequisites

- **Obsidian running**, vault `main` (or whatever is in `~/.mnemo/config.json`)
- **Plugin updated to the current manifest version** in a fresh runtime session:
  ```
  claude plugin update mnemo@mnemo
  codex plugin add mnemo@mnemo
  ```
- **claude-mem plugin optional**. If `cascade.claude_mem.enabled=false`, `/mn:health` Step 0 and `/mn:save` claude-mem POST should skip silently.

## Test plan — 6 checks, ~10 minutes total

### 1. `/mn:health` — the biggest surface

```
/mn:health
```

**Expect:**
- **Step 0 is Claude-only and respects claude-mem config** — Codex never scans `~/.claude/`; in Claude, disabled means a silent skip and enabled surfaces version/stale-cache state.
- **Steps 1-4 execute in parallel** (you'll see 4 Bash tool calls in a single assistant message).
- **Step 5 is instant** (~50ms) — uses one `safe-read.py missing-links` filesystem pass, not per-file `obsidian read`.
- Final report shows: vault size, note counts by type, orphans, missing `## Связи`, stale notes, top hubs.

**Red flags:**
- Step 5 takes >5 seconds → vault-path resolution or the filesystem scan is slow
- "claude-mem" section missing even though the plugin is installed → `check-cm-version.sh` path resolution broken
- References to "Obsidian must be open" gotcha inline in the skill body → reference files didn't extract (shouldn't happen since linter passed, but verify)

### 2. `/mn:ask` — pushy description triggers

Try a recall-style query you know is in your vault:

```
/mn:ask "что мы решили про tiered models в mnemo"
```

**Expect:**
- Skill triggers (pushy description changes in v0.7.1 should make this reliable).
- Step 3 fires multiple `safe-read.py search` calls in parallel (indexed Obsidian CLI underneath, no dynamic shell interpolation).
- Step 4 reads up to 7 notes **in parallel**.
- Answer cites specific notes with source labels like `[Source: Session — X]`.

**Red flag:** skill runs searches sequentially (one at a time) → parallelism rule didn't land.

### 3. `/mn:connect` — single-pass performance

```
/mn:connect "Atom — mnemo ask стоит расширить knowledge-agent для глобальных вопросов"
```

**Expect:**
- Step 3 runs **one `safe-read.py grep-concepts` literal scan** — not N separate `obsidian search` calls and not a generated regex/shell command.
- Backlinks check runs through the helper in parallel with the scan (two tool calls, one message).
- Total time ~1-2 seconds for 7 concepts.
- Output: ranked list of 5-7 candidate notes with "why relevant" blurbs. Does NOT auto-apply.

**Red flag:** a vault-derived name/concept/query appears directly inside an `obsidian ...` shell command → the argv-safety contract regressed.

### 4. `/mn:save` — claude-mem metadata enrichment

```
/mn:save "Тестовая заметка: smoke test mnemo. Facade ping."
```

**Expect:**
- Skill classifies the input (fact/insight/decision/gotcha).
- Creates Obsidian note via MCP (`mcp__obsidian__create`, not CLI).
- POSTs to claude-mem at `127.0.0.1:37777` using the `text` key (NOT `content` — v12.3.9 API requirement).
- `text` has a bracketed tail like `... [note: {name} | vault: main | cm: 12.3.9]` — provenance embedded because v12.3.9 silently drops `metadata.*` custom fields.
- `metadata: {...}` block is still sent (forward-compat for when upstream fixes drop-silent).
- Final report shows `Backends: Obsidian ✅, claude-mem ✅, memory/ ⏭` (or similar).

**Verify:** POST returns `{"success": true, "id": N}` — if it returns `{"error": "text is required..."}`, the `content` → `text` rename wasn't applied.

**Red flags:**
- `text` still labeled `content` in the skill body → v0.7.4 fix didn't land, POST will 400.
- `CM_VERSION` empty/missing → version detection broken; check `ls ~/.claude/plugins/cache/thedotmack/claude-mem/`.

### 5. `/mn:review` — prewarmed caches + progressive disclosure

```
/mn:review
```

**Expect:**
- **First run of the session is near-instant** (~3s) because `plugins/mnemo/hooks/prewarm.sh` warmed `session-scan` + `skills-discover` caches on SessionStart.
- Session classified (Implementation / Research / Debugging / etc).
- Step 4 runs explicit `cat` on `triggers-{type}.md` + `triggers-universal.md` — you should see these file contents in the bash output.
- Skill gap analysis references the cat'd matrix, not an inline table in the skill body.

**Red flag:** no `cat triggers-*.md` call visible → Step 4 fix didn't land.

### 6. `/mn:setup` — idempotent handoff

```
/mn:setup
```

**Expect:** skill detects existing `~/.mnemo/config.json`, shows current values, asks whether to overwrite before rewriting. **Does NOT clobber** the existing `Meta — Session Handoff.md` — Step 6 checks and skips creation if it exists.

**Red flag:** handoff gets overwritten → idempotency fix didn't land.

## Codex smoke check

After installing through Codex:

```bash
python3 scripts/test-runtime-compat.py
python3 plugins/mnemo/scripts/session-scan.py
CODEX_CI=1 python3 plugins/mnemo/scripts/skills-discover.py
```

Expected: all commands exit 0. Discovery contains exactly seven mnemo IDs — `mnemo:ask`, `connect`, `health`, `review`, `save`, `session`, and `setup` — with no `mn:*`, `mnemo:mn:*`, or Claude-only skills. `session-scan.py` finds the current Codex rollout JSONL inside an active task, or prints a graceful fallback if none exists.

## CI verification (Optional — in browser)

Open <https://github.com/jojoprison/mnemo/actions>. Last run should show **Skill lint passed** on `plugins/**` files. No workflow should be red.

## If something breaks

1. Note **which skill** and **what output differed** from "Expect" above.
2. Check the active runtime's installed plugin version. If the update did not take effect, run `claude plugin update mnemo@mnemo` or reinstall it through Codex, then start a fresh session.
3. Check CI: if GitHub Actions is red, the linter found an issue.
4. Open a fresh session with the same failure, tag Claude: "smoke test failed on `/mn:X`, expected Y, got Z" — we'll debug from there.

## Cleanup after a clean run

- Optionally delete the "Facade ping" test atom via Obsidian
- Remove legacy cache (older version dirs), only after confirming the current version works — and **never** a dir with a live `.in_use/` lock (check `~/.claude/plugins/cache/.../<ver>/.in_use/` against running sessions first):
  ```bash
  ls ~/.claude/plugins/cache/mnemo/mnemo/   # delete only stale, unlocked version dirs
  ```

## Expected total time

~10 minutes on a warm vault. All 6 checks independent — you can skip any that aren't relevant, but `/mn:health` and `/mn:ask` are the most important (cover the most surface).

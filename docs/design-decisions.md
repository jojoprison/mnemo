# mnemo — design decisions & non-goals

Why mnemo is shaped the way it is, and which tempting features it deliberately does **not** ship. Read this before proposing a change — and if you *want* one of the rejected features, the "If you want it" notes show how to add it without breaking the core.

## The one principle everything follows

**mnemo maintains a *human-authored* knowledge vault from *inside* a coding agent, non-destructively.**

Three consequences:

- **Human-authored** — the atomic claims are written by you (or by the agent, in-conversation, on your behalf). mnemo does not generate vault content from a document corpus. The agent "was there" when the insight happened and pins the discrete claim. Contrast: an LLM that ingests a folder of PDFs and auto-explodes them into pages.
- **Non-destructive** — skills report and suggest; they never auto-delete, overwrite, or author content. There are two **opt-in, default-off** exceptions, each a config flag the user must flip: the `reviewed:` snooze stamp (`review.lint.autoStampReviewed`), written only on notes the lint judged still-valid; and `review --full` auto-linking (`review.full.autoConnect`), where the chain's `connect` step writes its suggested links without a per-suggestion prompt. Both stay suggest-only until the user opts in — a standalone `/mn:connect` never auto-applies, and the default install writes neither.
- **In-agent** — mnemo runs inside Claude Code / Codex. The harness already injects the `memory/MEMORY.md` index and the live conversation as hot context, so mnemo never has to re-create the agent's working memory.

## Cross-runtime recall is federation, not synchronization (v1.2.3)

Claude Code and Codex each own generated local-memory state with different layouts and lifecycle rules. mnemo deliberately does **not** symlink, mirror, merge, migrate, or let both runtimes write the same generated `MEMORY.md`. That would turn undocumented internal formats into a shared database and create multi-writer races, duplicate facts, scope leaks, and upgrade breakage.

Instead, `recall.runtimeMemory.enabled` adds a bounded **read-only retrieval overlay** to `ask`:

- Codex may read Claude Code's `MEMORY.md` and linked topic files only after Claude's exact app-state project keys resolve to the same git common directory. The lossy Claude slug alone is never trusted; mixed/ambiguous mappings fail closed, and session JSONL is never opened.
- Claude may read only `# Task Group:` sections in Codex `MEMORY.md` whose metadata contains a matching `applies_to: cwd=…`. Unscoped and foreign-project groups fail closed.
- Worktrees that share a git common directory intentionally share project scope; unrelated clones and non-git directories do not.
- Symlinks, path escapes, non-regular/foreign-owned files, oversized inputs, secret-like global filenames, and unknown structure are rejected. Missing proof disables only that backend; it never falls back to a home-wide scan.
- Runtime-memory excerpts are labelled `runtime-generated-untrusted`. They can support an answer but cannot issue instructions, widen scope, trigger tools, fetch embedded links, or write back to the vault.
- One global result budget applies after source merge: at most seven evidence items, with bounded excerpts. Obsidian remains the authoritative human-authored source and wins ties.

The overlay is off by default and has no daemon, mnemo-owned registry, cache, vector store, or background index. It only verifies against Claude's existing app-state registry and Codex's existing task-group metadata. Optional direct Markdown topics under `~/.claude/memory/` are searched only when both config and the individual query explicitly request global/cross-project recall; `~/.claude/CLAUDE.md` stays on the instruction plane and is never treated as remembered facts.

This gives each agent visibility into useful counterpart context without creating a third writer or pretending the runtimes expose a stable synchronization protocol. `save` continues writing through the existing canonical cascade; federation changes retrieval only.

## Recall memory vs auto-inject rules (v0.15.0)

mnemo saves two different kinds of thing, and they must land in different places:

- **Recall memory** — facts, insights, decisions, sources: "*what* we did / *why*". Fetched **on demand** (`/mn:ask`, a future agent searching the vault). Home: Obsidian + optional claude-mem + `memory/`.
- **Actionable rules** — "never do X / always do Y" tied to specific code: a lesson a future agent must see **before** it repeats the mistake. Useless if it only sits in recall — by the time someone thinks to search for it, the error is already made. Home: **`.claude/rules/<domain>.md`** — Claude Code's native path-scoped rules, which auto-load the moment the agent touches a matching file.

`save` Step 3.5 makes this split: an actionable-rule save is routed into `.claude/rules/` (project) or `~/.claude/rules/` (cross-project, applies on every repo), creating the file — and the dir — when none matches by meaning. It's the granular evolution of the old "write the rule into CLAUDE.md" branch: `.claude/rules/` is path-scoped (zero idle context cost) where CLAUDE.md is always-on and unstructured. The load trigger is the file's `paths:` frontmatter, not `description:`. Gated by `cascade.project_rules.enabled` (default true; fires only for actionable-rule saves, never for recall). On a fresh repo with no `.claude/rules/`, the first such save **creates** the dir + domain file (a rule bootstraps the convention) — intentional, but set `project_rules.enabled: false` if you'd rather rules fall back to CLAUDE.md/`memory/`. See [config-schema](../plugins/mnemo/references/config-schema.md).

**Deliberate boundaries:**

- **`/mn:session` stays pure narrative.** Session notes record "what happened" for human recall; they are *not* a rules channel. Folding rule-routing into session would blur two responsibilities and was rejected. The interactive "found an actionable rule → route it?" prompt lives in the **orchestrator** (`/mn:review`, Step 8) instead, where it can confirm before writing committed project files — and even then it delegates the write to `save` Step 3.5 rather than re-implementing it.
- **Auto-route on explicit save, confirmed in the orchestrator.** A direct `/mn:save` of a rule routes automatically (the user explicitly asked to save). `/mn:review` never writes unattended — since v0.16.0 *every* skill it wants to run goes through one Step 8 confirmation, and an actionable rule additionally gets its own explicit line item there, because routing it creates/edits committed project files.
- **Codex caveat acknowledged, not solved here.** Codex reads only `AGENTS.md` (32 KiB, silent truncate), not `.claude/rules/`. mnemo routes to `.claude/rules/` and flags the AGENTS.md build-step as the user's responsibility — it does not own that assemble step.

## One-command close-out: `review --full` (v1.2.8)

`/mn:review --full` collapses the end-of-session ritual — audit, save, session, connect, verify — into a single explicit command, so the user never pastes a "capture everything, check everything, keep it like a clean palace" wall of prompt. It is a **flag on `review`**, not an eighth skill (the 7-skill canon holds).

**Deliberate boundaries** (each is load-bearing — removing it reintroduces a rejected behavior):

- **Flag = consent, not implicit autorun.** The explicit `--full` the user typed *is* the confirmation, so the chain runs without a per-skill `y`. This does not revive the autorun removed in v0.16.0: that was *plain* `/mn:review` firing skills unasked. Default `/mn:review` still audits + offers + never auto-runs — only the typed flag chains.
- **Verify grounds externally, never self-grades.** The Step 9 verify pass anchors every check to a fact — git diff, orphans, `session-scan`, the Step-0 snapshot — never the agent's own assertion. A same-agent self-audit that trusts itself rubber-stamps (eval-integrity).
- **Verify never links; over-linking is defused.** The non-orphan check is binary (connected or not) and never rewards link *count*; an orphan is delegated to `connect`, and verify adds no link itself. So "score the palace green" cannot incentivize link-spam from a "connect everything" instruction.
- **Depth-contract is routing, not volume.** `--full` injects `references/depth-contract.md` as guidance: thorough means the right material in the right home (business-logic / pains / mental-model → `save`'s typed atoms, **not** the session narrative), never a bigger note. "Capture everything, super-detailed" is the blob anti-pattern rejected in v1.2.7; it is explicitly dropped.
- **memory-not-CI.** For "did we verify on prod / run e2e / really done?", `--full` REPORTS the absence of test/deploy evidence as an unchecked gap; it never runs tests, hits prod, or fires a trigger. That execution lives in the harness (`finish-the-work` / `loop-gate`), outside a memory plugin's mandate.
- **`health` stays manual.** Heavy; recommended in the report, never auto-chained.
- **`session` stays pure narrative.** Its own Step 7 self-check verifies only *its* note (dup / MOC / orphan / delegation); the cross-skill palace audit is `review --full`'s Step 9, not session's — the same boundary that keeps rule-routing out of session (v0.15.0).
- **Idempotent.** A second `--full` on an unchanged session prints "already in order" and stops — it never re-parks or re-links.

## Proactive nudges via hooks (v1.1.1)

Descriptions get an agent to *consider* mnemo, but Opus 4.8 / Fable 5 under-trigger skills — a good description raises the odds, it doesn't guarantee the call. v1.1.1 adds a deterministic **delivery** layer via hooks, with one honest caveat baked into the design: **deterministic delivery ≠ deterministic effect** — the hook always fires, but the model still decides whether to act. A prose nudge is exactly the "marginal rule ≈ 0" pattern, so it's kept short, factual (not an order), and gated.

- **SessionStart nudge** (`hooks/mnemo-context.sh`, `hooks.sessionStartNudge` default **true**) — one line: mnemo memory exists, recall with `/mn:ask` before non-trivial work, save with `/mn:save` as you go. Gated on a configured vault (silent otherwise). Cost: a few dozen tokens every session — an accepted always-on price for keeping memory top-of-mind. **One channel only:** the nudge lives in the hook, *not* duplicated into a committed `CLAUDE.md` line (that would be a second always-on copy and a committed→private cross-link leak).
- **Stop nudge** (`hooks/mnemo-stop-nudge.sh`, `hooks.stopNudge` default **false**) — if a session looks worth-saving (fix/decision signals) but `/mn:save` and/or `/mn:session` never ran, it blocks the stop **once** and recommends the one-command close-out `/mn:review --full` (v1.2.9 — it audits, then chains save → session → connect + verify), instead of listing save and session separately. Blocking is powerful but can loop for arbitrary users of a public plugin, so it's **opt-in**, and an anti-loop governor blocks at most once per session — keyed on `session_id`, falling back to `CODEX_THREAD_ID` when a Codex Stop payload omits it, so it dedups instead of re-nudging every Stop. The default install never blocks.
- **Autocompact nudge** (`hooks/mnemo-autocompact-nudge.sh`, `hooks.autocompactNudge` default **false**) — Claude Code's effective autocompact threshold is `min(settings.autoCompactWindow, the model's context window)` — see [[Atom — Окно автокомпакта Claude Code равно min настройки и контекста модели]] — and it ranges 200k-1M depending on the model, so mnemo ships no per-model table; a hardcoded fraction or default would be wrong for someone. Instead the window comes only from sources Claude Code itself already resolved — `CLAUDE_CODE_AUTO_COMPACT_WINDOW`, then `settings.autoCompactWindow`, then its own `~/.claude.json` cache — and if none apply, the hook stays silent rather than guess. Token usage comes from the transcript, not hook stdin, which carries no token count (a Stop hook gotcha the same as `stopNudge`'s signal scan). The threshold is a fixed margin from the window (warn ~50k / critical ~10k remaining), clamped down on a small window so the bands can't eat the whole thing, and it blocks at most once per severity level per session — same anti-loop posture as `stopNudge`, recommending the same `/mn:review --full` close-out. Claude Code only: Codex has no comparable window to protect against, so the hook no-ops there. **Opt-in, default false** — same loop-risk reasoning as `stopNudge`. **Rejected:** clamping the resolved window to the model's real context ceiling. There is no per-model table to clamp against (that's the whole reason for resolving W from Claude Code's own sources instead of guessing), so an explicit `settings.autoCompactWindow` larger than the active model's actual limit is trusted as-is — if a user sets it above what their model supports, the nudge fires later than the real autocompact and that's on their own misconfiguration, not a case mnemo defends against.
- **Invocation echo** (`hooks/mnemo-skill-echo.sh`, `hooks.invocationEcho` default **true**, v1.2.2) — unifying skills removed the command-router layer, and with it the visible Skill-tool call users relied on to *see* that a `/mn:*` command loaded its skill. Visibility comes back in two layers: an **in-body invocation marker** (each `SKILL.md` opens its reply with `🧠 mn:<skill> (mnemo) → running` — both runtimes, probabilistic like every body instruction) and this **deterministic** Claude Code hook on `UserPromptExpansion` (fires on every `/mn:*` expansion; live-verified on CC 2.1.215 that hook output never alters the expansion). The event fires only on **user-typed** `/mn:*` — a model-initiated (self-invoked) skill run never triggers it and is covered by the in-body marker alone. Codex does not support this event, and Codex UI has no native invocation indicator, which is exactly why the in-body marker exists.
- **Runtime-safe hook composition** (v1.2.3; Claude loader fix v1.2.4) — `hooks/hooks.json` is the auto-discovered Codex-safe baseline (`SessionStart` + `Stop`). Claude's manifest lists only the additive `hooks/claude-hooks.json`, which contains `UserPromptExpansion`; explicitly listing the standard file as well makes current Claude Code reject the plugin as a duplicate. Each event still has one definition: Claude keeps all three behaviors, while Codex never has to ignore an undocumented event. The Codex manifest deliberately relies on default discovery because the bundled validator rejects an explicit `hooks` field even though the current manual documents it.
- **Rejected:** `PreToolUse(Read)` auto-recall (needs an index/daemon — mnemo has neither), `UserPromptSubmit` nudges (a cost on every prompt), and a **default-on** blocking Stop (loop risk for others). The nudge measures its own worth: ship it only if a trigger-eval shows lift over the bare description — otherwise it's paying an always-on price for nothing.

## The handoff is an index of pointers, not a store (v1.2.12)

**What changed.** An unfinished thread now lives in its own session note's pending section; the handoff holds one line per session — `- 2026-07-25 · project · open 3 · [[Session — …]]`.

**Why.** The previous contract sent open threads *into* the shared handoff. Measured on a real vault: only **9%** of fresh open items also existed in their own session note (34% for older ones), so the handoff had become the sole home of forward state. It reached **805 KiB** — and at that size nothing can read it (a file read refuses past 256 KB / 25,000 tokens), so the "read the handoff at session start" instruction was unexecutable and continuity happened in **6%** of sessions. A pointer line is bounded by the *number of sessions*; a copied thread is bounded by nothing.

**What was rejected, and why it matters:**

- **Archiving harder.** The archiver may never move a block holding an open `- [ ]` — an unkept promise must not slip into cold storage silently. On the live file that invariant meant it could free **zero** bytes while the file sat 20× over its ceiling. The guard is correct and insufficient: size is decided by the *format* of what gets written, not by rotation.
- **Triage as a size strategy.** Resolving *every* open item would have freed **2.47%**. Triage buys correctness, not size — which is why `handoff-resolver.py` is permanently report-only.
- **Compressing blocks into lines.** Live state is not always a `- [ ]`: 90 flat bullets and ~200 prose lines carried it. Extraction would have dropped them, so migration moves blocks **verbatim and whole**.
- **Rewriting the user's session notes** to redistribute 863 existing threads. Those files are human-authored and the vault has no version control; the threads went to the archive with a searchable inventory instead. (v1.2.13 revisits this **narrowly**, not generally — see the rotation rule below.)

**Why migration is a separate manual step.** `migrate-handoff-to-index.py` is not run by any skill: it rewrites the vault irreversibly, so it defaults to `--dry-run`, writes `.bak` first, verifies every block is byte-present in the archive afterwards, and ships with a rehearsed `restore-handoff-from-bak.py`. A skill that silently reshapes your vault mid-session would violate the one principle above.

## The index rotates by calendar, and says so when it can't (v1.2.13)

**What changed.** The index keeps the last `handoff.keepDays` (default **31**) days of pointers. A line count (`handoff.maxLines`) no longer decides anything and the key is gone; `handoff.maxKB` (56) is a backstop underneath the window, and `handoff.maxLineBytes` (200) bounds a line. Five knobs became three.

**Why.** "The last month of sessions" is what a reader asks for; a line count answers it only by accident. At this vault's measured pace — **7.5 sessions/day, 234 in 31 days** — the old 180-line ceiling silently delivered ~24 days under a config that said `keepDays: 31`. The sizing follows from measurement rather than taste: 234 lines × ~195 B ≈ 46 KiB, so 56 KiB carries a normal month with ~20% headroom and still opens in one read.

**Evicting a pointer loses nothing — but only because two gaps were closed first.** A pointer is derived from a session note that keeps its own dated file, so dropping it drops a duplicate. That argument fails for a pointer whose target does not exist, which is why v1.2.13 ships `relink-orphan-pointers.py` (a pointer with no session note now points at the archive part holding its block — 10 such on the live vault, 170 open items) and `backfill-tails-from-archive.py` (tails that exist *only* in recently-archived blocks are appended to their own session note). The backfill is the narrow revisit of "don't rewrite the user's notes": it appends **only genuinely missing** items — measured, 105 of 136 recent tails were already in their note under different wording, so 31 were appended, each marked with the block's date — instead of redistributing 863.

**When the window doesn't fit, the file says so.** If a month is busier than `maxKB` allows, the oldest pointers give way and one `> _overflow:` line states it. A window that silently holds less than it promises is the exact failure this reform exists to remove, so it must never fail silently again.

**The remaining gap.** Tails older than the digest's `hot.windowDays` that live only in archived blocks are still outside its reach — deliberately: the digest is for current work, and teaching it to scan cold archive parts on every session start would pay a permanent cost for a legacy pile. They stay searchable, and `health` Step 7.6 triages them on demand.

## Non-goals (deliberately rejected)

The first three surfaced during the Karpathy "LLM Wiki" audit (v0.14.0 — see [CHANGELOG](../CHANGELOG.md)); the fourth came out of a later competitor audit. Each is a reasonable idea for a *different* tool; each conflicts with the principle above. None are "forgotten" — they were evaluated and declined. If you want one, the "If you want it" note shows the on-philosophy way: always opt-in, default off, never masquerading as hand-curated content.

### 1. Auto-ingest pipeline (`raw/` → `wiki/`, one source → many auto-notes)

**What it is:** drop a PDF / article / transcript into a `raw/` folder; the LLM reads it and auto-generates 5–25 interlinked wiki notes (Karpathy's core operation).

**Why not:** this is the *document-driven* model — the vault becomes LLM-authored output, not human-authored atomic claims. It is the single largest fork from mnemo's identity. mnemo's atomicity is enforced per-claim at write time by the agent who was in the conversation, not by exploding a document after the fact.

**If you want it:** add an opt-in `/mn:ingest` skill (classify → extract → create), gated behind a config flag, producing clearly machine-authored notes (e.g. a distinct `type: ingested`) so they never pass as hand-curated atoms. The classify-before-extract primitive already exists in `save` Step 0.

### 2. Web-search imputation in the lint

**What it is:** the health lint not only flags problems but goes to the web, searches, and writes the missing data back into your notes (Karpathy's lint imputes missing fields).

**Why not:** breaks non-destructive — the tool would author content into your vault. mnemo's lint reports; you decide.

**What we shipped instead:** the report-only half — **research-gap candidates** (`/mn:health` Step 8.5): it *points at* gaps ("topic X has ≥5 notes but no MOC", "external Y is cited but has no Source note") without filling them.

**If you want it:** a suggest-only variant that proposes "this field looks missing — research X?" and writes only on explicit per-note confirmation. Never a default auto-write.

### 3. `hot.md` recent-context cache

**What it is:** a tiny (~500-char) cache of the most-recent context that downstream agents read first, to avoid crawling the whole vault on every query.

**Why not (as a *file*):** a cache note in the vault is another artifact to keep true, and a stale one is worse than none.

**What shipped instead (v1.2.11):** the same need — "what was I in the middle of" — is served by an **ephemeral, computed** digest: `hot-scan.py` reads the pending sections of recent session notes at SessionStart and injects a byte-capped summary (`hot.scope` / `hot.windowDays` / `hot.maxKB`). Nothing is written to the vault, so it cannot rot; it is recomputed every session from the notes themselves. Note the naming: the `hot.*` config namespace belongs to that digest, not to a `hot.md` file.

**If you want it:** only worthwhile if you build an external service that queries the vault headlessly; then a bounded `hot.md` maintained by `/mn:save` could accelerate it.

### 4. A vendored semantic-search index over the vault (embeddings / vector store / MCP index server)

**What it is:** ship semantic recall by bundling a search engine — an embeddings + BM25 index over the vault, kept current by a background refresh worker, provisioned by a bootstrap script and exposed to the agent as an MCP server that mnemo declares and starts. This is the shape `breferrari/obsidian-mind` ships (via QMD), and it is the single most tempting thing to copy from any competitor: it is genuinely the strongest retrieval upgrade available.

**Why not:** it is the exact trio the one principle forbids — *no daemon, no mnemo-owned cache or registry, no vector store, no background index*. The distinction that matters is ownership: mnemo would **start and maintain** the index, not passively query something the user already runs. Two further disqualifiers are independent of philosophy: a Node launcher injects a runtime dependency into a pure-Python plugin, and an `.mcp.json` server declaration is Claude-only, so dual-runtime parity breaks.

**On "but it would fill the hole claude-mem left" — that reads the history backwards.** The optional claude-mem backend was not lost for want of a replacement; it was removed deliberately, together with the launch agent that revived its embeddings service on every boot. The empty slot *is* the decision. Re-vendoring an always-warm index reinstalls precisely the failure mode that emptied it.

**If you want it:** the on-philosophy seam is already shipped and is the opposite arrangement — `recall.codeGraph` (default `null`) names a semantic or graph backend **the user installs and runs**, which `ask` queries retrieval-only inside the same ≤7-item evidence budget, with Obsidian winning ties and a silent no-op when the backend is absent. Bring your own engine; mnemo never provisions, spawns, or refreshes one.

## See also

- The full audit with per-feature adopt/reject rationale lives in the maintainer's agent knowledge base (topic: what was taken from — and rejected out of — the Karpathy LLM-wiki pattern)
- [BACKLOG](BACKLOG.md) — ideas that are *wanted but not built yet*, as opposed to the non-goals above (declined on purpose)
- [CHANGELOG](../CHANGELOG.md) `[0.14.0]` — the three features we *did* adopt from the same audit (compounding loop, self-snoozing lint, research-gap candidates)
- [Andrej Karpathy's "LLM Wiki" gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — the pattern that prompted the audit

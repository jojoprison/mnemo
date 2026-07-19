# mnemo — design decisions & non-goals

Why mnemo is shaped the way it is, and which tempting features it deliberately does **not** ship. Read this before proposing a change — and if you *want* one of the rejected features, the "If you want it" notes show how to add it without breaking the core.

## The one principle everything follows

**mnemo maintains a *human-authored* knowledge vault from *inside* a coding agent, non-destructively.**

Three consequences:

- **Human-authored** — the atomic claims are written by you (or by the agent, in-conversation, on your behalf). mnemo does not generate vault content from a document corpus. The agent "was there" when the insight happened and pins the discrete claim. Contrast: an LLM that ingests a folder of PDFs and auto-explodes them into pages.
- **Non-destructive** — skills report and suggest; they never auto-delete, overwrite, or author content. The single, opt-in exception is the `reviewed:` snooze stamp (`review.lint.autoStampReviewed`), and only on notes the lint judged still-valid.
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

## Proactive nudges via hooks (v1.1.1)

Descriptions get an agent to *consider* mnemo, but Opus 4.8 / Fable 5 under-trigger skills — a good description raises the odds, it doesn't guarantee the call. v1.1.1 adds a deterministic **delivery** layer via hooks, with one honest caveat baked into the design: **deterministic delivery ≠ deterministic effect** — the hook always fires, but the model still decides whether to act. A prose nudge is exactly the "marginal rule ≈ 0" pattern, so it's kept short, factual (not an order), and gated.

- **SessionStart nudge** (`hooks/mnemo-context.sh`, `hooks.sessionStartNudge` default **true**) — one line: mnemo memory exists, recall with `/mn:ask` before non-trivial work, save with `/mn:save` as you go. Gated on a configured vault (silent otherwise). Cost: a few dozen tokens every session — an accepted always-on price for keeping memory top-of-mind. **One channel only:** the nudge lives in the hook, *not* duplicated into a committed `CLAUDE.md` line (that would be a second always-on copy and a committed→private cross-link leak).
- **Stop nudge** (`hooks/mnemo-stop-nudge.sh`, `hooks.stopNudge` default **false**) — if a session looks worth-saving (fix/decision signals) but `/mn:save` and/or `/mn:session` never ran, it blocks the stop **once**, listing whichever is missing (save pins discrete facts; session writes the narrative + handoff). Blocking is powerful but can loop for arbitrary users of a public plugin, so it's **opt-in**, and an anti-loop governor blocks at most once per session. The default install never blocks.
- **Invocation echo** (`hooks/mnemo-skill-echo.sh`, `hooks.invocationEcho` default **true**, v1.2.2) — unifying skills removed the command-router layer, and with it the visible Skill-tool call users relied on to *see* that a `/mn:*` command loaded its skill. Visibility comes back in two layers: an **in-body invocation marker** (each `SKILL.md` opens its reply with `🧠 mn:<skill> (mnemo) → running` — both runtimes, probabilistic like every body instruction) and this **deterministic** Claude Code hook on `UserPromptExpansion` (fires on every `/mn:*` expansion; live-verified on CC 2.1.215 that hook output never alters the expansion). The event fires only on **user-typed** `/mn:*` — a model-initiated (self-invoked) skill run never triggers it and is covered by the in-body marker alone. Codex does not support this event, and Codex UI has no native invocation indicator, which is exactly why the in-body marker exists.
- **Runtime-safe hook composition** (v1.2.3) — `hooks/hooks.json` is the shared Codex-safe baseline (`SessionStart` + `Stop`). Claude's manifest adds `hooks/claude-hooks.json`, which contains only `UserPromptExpansion`. Each event has one definition: Claude keeps all three behaviors, while Codex never has to ignore an undocumented event. The Codex manifest deliberately relies on default `hooks/hooks.json` discovery because the current bundled validator rejects an explicit `hooks` field even though the current manual documents it.
- **Rejected:** `PreToolUse(Read)` auto-recall (needs an index/daemon — mnemo has neither), `UserPromptSubmit` nudges (a cost on every prompt), and a **default-on** blocking Stop (loop risk for others). The nudge measures its own worth: ship it only if a trigger-eval shows lift over the bare description — otherwise it's paying an always-on price for nothing.

## Non-goals (deliberately rejected)

These surfaced during the Karpathy "LLM Wiki" audit (v0.14.0 — see [CHANGELOG](../CHANGELOG.md)). Each is a reasonable idea for a *different* tool; each conflicts with the principle above. None are "forgotten" — they were evaluated and declined. If you want one, the "If you want it" note shows the on-philosophy way: always opt-in, default off, never masquerading as hand-curated content.

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

**Why not (near-N/A):** mnemo runs in-agent; the harness already injects `memory/MEMORY.md` + the live conversation as hot context, so the cold-crawl cost `hot.md` solves doesn't exist here. It would only help a *separate, external* agent querying the vault out-of-band — not mnemo's loop.

**If you want it:** only worthwhile if you build an external service that queries the vault headlessly; then a bounded `hot.md` maintained by `/mn:save` could accelerate it.

## See also

- **Vault note** (the full audit + adopt/reject rationale, in the maintainer's Obsidian): `Molecule — что взяли и отвергли из Karpathy LLM-wiki в mnemo`
- [CHANGELOG](../CHANGELOG.md) `[0.14.0]` — the three features we *did* adopt from the same audit (compounding loop, self-snoozing lint, research-gap candidates)
- [Andrej Karpathy's "LLM Wiki" gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) — the pattern that prompted the audit

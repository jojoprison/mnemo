---
name: vault-search
description: "Use proactively mid-task, on your own initiative, whenever past work might already cover the current step — before fixing a bug (was it solved before?), touching an unfamiliar subsystem, or making a risky/hard-to-reverse change — not only when asked. Also when the user wants to recall prior context: 'what did we decide about X', 'find everything about Y', 'что мы решили про', 'что мы знаем', 'как мы делали', 'когда последний раз', 'такое уже было', 'вспомни', 'напомни', 'посмотри в памяти', 'найди в памяти', 'как решали', 'где ещё может быть', 'что было с', or similar. Synthesizes across notes with source citations; prefer over generic memory tools when an Obsidian vault is available."
user-invocable: false
model: inherit
---

# mnemo:ask — Vault Knowledge Search & Synthesis

Search across the entire vault, read relevant notes, and synthesize an answer with source citations.

## Prerequisites & config

Obsidian must be open. Config at `~/.mnemo/config.json` — reads `vault` and `links_section`. Full schema in `references/config-schema.md`. If missing, ask the user for vault name and save.

## Workflow

### Step 1: Accept Query

Input as argument: `/mn:ask "what did we decide about pricing strategy?"`

If no argument, ask: "What would you like to find in your vault?"

### Step 2: Extract Search Terms

Break query into 2-4 key search terms. Example:
- "what did we decide about pricing strategy?" → ["pricing", "strategy", "decision"]

### Step 3: Search Vault (parallel)

**Run all searches in parallel — single assistant message with multiple Bash tool uses.** For 4 terms this takes ~180ms total instead of ~720ms sequential.

```bash
obsidian search query="{term1}" vault="{vault}"
obsidian search query="{term2}" vault="{vault}"
obsidian search query="{term3}" vault="{vault}"
obsidian search query="{term4}" vault="{vault}"
```

Collect all unique matching notes. Deduplicate.

### Step 3b: Also check Claude's memory/ index (not just Obsidian)

Obsidian = user-facing knowledge; **`memory/`** (MEMORY.md + topic files) = Claude-facing technical context (gotchas, decisions, sessions) in a separate store. For recall queries ("what did we decide / how did we do X"), also scan the project's memory index — the `MEMORY.md` already loaded in context — for the search terms. If the topic looks older and the index links a **`MEMORY-archive-index.md`**, read that too. Each matching row links a topic file (`{name}.md` in the same `memory/` dir) — read it for detail and cite as `[memory/{file}]`. Why two layers + how memory is arranged: `~/.claude/memory/autodream-principles.md`.

### Step 4: Read Top Results (parallel)

Read the most relevant notes (max 7) **in parallel — single message with multiple Bash tool uses.** ~185ms vs ~1.3s sequential for 7 notes.

```bash
obsidian read file="{note_name_1}" vault="{vault}"
obsidian read file="{note_name_2}" vault="{vault}"
...
```

### Step 4b: Date each source (recency)

An answer is only as fresh as the notes behind it. Two **different** signals matter — never conflate them:

- **Last changed** = when the *file* was last touched → `git log` if the vault is a git repo (obsidian-git), else filesystem **mtime**. This is "обновлено когда".
- **Stale?** = whether the *content* is likely outdated → the same rule `/mn:health` uses: age from `max(date, reviewed)` vs `review.staleDays.<type>`. A cosmetic edit bumps mtime but does NOT make stale content fresh — that's exactly why staleness anchors on `date`/`reviewed`, not mtime (a note touched today can still be stale).

Resolve the vault path once, then for the cited notes (parallel, one batched pass):

```bash
VAULT_PATH=$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/get-vault-path.sh" "{vault}")

# "Last changed": git last-commit if the vault is a git repo, else file mtime.
if git -C "$VAULT_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$VAULT_PATH" log -1 --format='%cs' -- "{note}.md"            # last commit date
else
  python3 -c "import os,datetime,sys;print(datetime.date.fromtimestamp(os.path.getmtime(sys.argv[1])))" "$VAULT_PATH/{note}.md"
fi
```

For the **stale** flag, reuse the one staleness engine instead of re-deriving the rule — run it once and intersect with your cited notes (a cited note in the output is stale; col 5 = its type budget):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/review-candidates.py" "$VAULT_PATH" --limit 9999
```

This keeps `/mn:ask` and `/mn:health` in lock-step on what "stale" means. Read `date`/`reviewed` from frontmatter only for display context.

### Step 4c: Ground in the live code (optional — only when it earns it)

mnemo runs *inside* your coding agent, so for **current-state** questions the code is ground truth and the notes are what you distrust. **Gate this — run only when BOTH hold, else skip silently:**

1. The working dir is a git repo — a real project, separate from the vault: `git rev-parse --is-inside-work-tree`.
2. The query is about current/actual state, not past rationale. "what did we DECIDE / why did we choose" → notes suffice, skip. "is this still true / what changed / current state of X" → ground it.

Then pull the project's recent history relevant to the query (in the CWD repo, **not** the vault) and cross-check your cited notes:

```bash
git log --oneline -n 15 -i --grep="{term}" 2>/dev/null               # recent commits mentioning the topic
git log --oneline -n 10 -- "{relevant_path_or_glob}" 2>/dev/null      # …or touching the implied area
```

If a cited note predates a relevant code change, say so: "⚠️ [[note]] (2026-03-14) predates commit a1b2 (2026-06-20) touching `auth/` — verify against current code." This makes recall agree with reality, not just with old notes.

**Code-knowledge-graph (config seam, default OFF).** If `config.json` → `recall.codeGraph` names a backend you actually have, also query it for structural "what's where": a file-output skill (Graphify → read its `graph.json` / `GRAPH_REPORT.md`) or an MCP server (Sourcegraph SCIP / ast-grep / tree-sitter-analyzer). Ships off — lights up only when you set it; no-op otherwise.

### Step 5: Synthesize Answer

Compose a clear answer from the found notes. For each claim, cite the source note **with its last-changed date** (Step 4b). If a load-bearing source is in the stale set, flag it ⚠️ — note the file may have been touched recently yet its content still be stale — so the reader knows the answer may rest on outdated info (offer `/mn:health` or a re-check). If Step 4c ran, fold the live-code findings in and flag any note a recent commit contradicts:

```
Based on your vault:

The pricing strategy was decided on 2026-03-14 during the pipeline review session.
Key points:
- Freemium model with usage-based tiers [Source: Session — 2026-03-14 pipeline vision]
- Enterprise plan at $99/mo was rejected as too low [Source: Atom — pricing research]
- Final decision: $29 starter, $99 pro, custom enterprise [Source: Molecule — pricing decision]

📚 Sources (3 notes):
1. [[Session — 2026-03-14 pipeline vision]] — changed 2026-03-14
2. [[Atom — pricing research]] — changed 2026-06-20 · ⚠️ stale (created 2026-03-14, never reviewed → 99d > atom 60d budget)
3. [[Molecule — pricing decision]] — changed 2026-05-02
```
(Note source 2: the file was touched yesterday, but its *content* is stale — `changed` ≠ `fresh`.)

### Step 6: Offer Follow-up — and let the answer compound

A synthesized answer is itself knowledge. If it's a non-trivial insight drawn across **≥2** notes (not just "here are the notes I found"), offer to fold it back into the vault so future recall starts from it instead of re-deriving it every time. This is the compounding loop — explorations add up like interest instead of evaporating when the conversation ends.

Ask: "Want me to **save this synthesis** as a `Molecule` (cites the sources above, links pre-attached), search deeper, or connect any of these notes?"

If the user accepts the save, hand off to `/mn:save` (memory-routing) with the synthesis as the content, `type: molecule`, a `cites:` field listing the cited source notes, and the `{links_section}` pre-populated with `[[links]]` to those sources + the relevant MOC. **memory-routing owns the write** (duplicate check, shell-safe MCP create, mandatory MOC link) — don't create the note here; reuse the one cascade that already does it right.

**Only offer when the answer clears the Molecule bar** — a genuine synthesis (config `taxonomy.molecule` semantics). A trivial single-note lookup or a "nothing found" result doesn't compound; skip the offer. Never save without the user's go-ahead — the user authors their vault (non-destructive).

## Gotchas

Common failures (Obsidian IPC, shell injection) are documented once in `references/gotchas.md`. Skill-specific rules:

- **Max 7 notes read** — don't blow context reading the entire vault. If the query is too broad, narrow it and re-search.
- **Always cite sources** — every claim references a specific note. Hallucinated facts are worse than "not found".
- **If nothing found** — say so honestly, suggest alternative search terms instead of guessing.
- **Respect note types** — Sessions contain decisions, Atoms contain facts, Molecules contain insights. Use the right citation format for each.
- **CLI for search** — only CLI has `obsidian search` (indexed). MCP doesn't expose it.
- **Two signals, don't conflate (Step 4b)** — "last changed" (git/mtime = when the file moved) is NOT "stale" (content outdated). A note edited today can still be stale; staleness uses `date`/`reviewed` vs the type budget (same engine as `/mn:health` — `review-candidates.py`), never mtime.
- **mtime is a fallback for "last changed" only** — it resets on vault sync/copy/restore (Syncthing, iCloud, fresh clone). Most Obsidian vaults aren't git repos, so "last changed" = mtime; but "stale?" always comes from `date`/`reviewed`, so a sync that bumps every mtime can't fake freshness.
- **Only date what you cite** — "last changed" is per cited note; the stale set is one `review-candidates.py` pass intersected with your ≤7 cited notes. Never date every search hit.
- **Compounding is opt-in per answer (Step 6)** — offer to save a real synthesis as a Molecule, never auto-file it. Delegate the write to `/mn:save`; gate the offer on the Molecule bar (≥2-note insight) so trivial lookups don't spawn note-spam.

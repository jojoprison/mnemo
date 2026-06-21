---
name: vault-health
description: "Use whenever the user mentions vault maintenance, orphans, broken links, 'is my vault clean', 'проверь vault', or asks for vault statistics. Also invoke proactively after creating 3+ notes in one session, weekly, or after mass note creation — the longer between checks, the more invisible orphans accumulate."
user-invocable: false
model: haiku
context: fork
---

# mnemo:health — Vault Health Check & Analytics

Run a comprehensive health check on the Obsidian vault: orphans, broken links, missing sections, stale notes, and growth statistics.

## Prerequisites & config

Obsidian must be open; `obsidian` CLI on PATH. Config at `~/.mnemo/config.json` (required fields: `vault`, `taxonomy`, `links_section`) — schema in `references/config-schema.md`.

## Workflow

**Steps 1-4 run in parallel** — single assistant message with 4 Bash tool uses. These are independent CLI queries against the same indexed vault, ~180ms each → 180ms total vs 720ms sequential.

### Step 0: claude-mem Sanity Check (optional, ~20ms)

Surface two common gotchas if claude-mem plugin is installed and enabled. If `cascade.claude_mem.enabled` is false, skip this section silently — many users intentionally disable claude-mem for CPU/RAM reasons.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/check-cm-version.sh"
# Or from source: plugins/mnemo/scripts/check-cm-version.sh
```

Script emits three lines: `version: X`, `stale: N`, `path: ...`. Interpret:

- `stale > 0` → warn: "claude-mem has {stale} old version folder(s) cached. Restart all Claude windows — old Stop hooks point to a path that no longer exists."
- `version < 12` → warn: "claude-mem v{version} is behind v12 — you're missing file-read gate, tier routing, and knowledge agents. Run `/plugin update claude-mem`."
- Empty path → claude-mem not installed. Skip the section entirely.

### Step 1: Orphan Detection

```bash
obsidian orphans vault="{vault}"
```

List notes with zero backlinks. These are invisible in Graph View.

### Step 2: Unresolved Links (Ghost Notes)

```bash
obsidian unresolved vault="{vault}"
```

Show `[[wikilinks]]` pointing to non-existent files. Ghost notes are NORMAL (entity discovery) — don't flag on raw count alone.

**Actionable — top unresolved targets = missing hub notes** (via `obsidian eval`, authoritative; CLI `unresolved` can lag/lie — see `references/gotchas.md`):

```bash
obsidian eval code="(()=>{const u=app.metadataCache.unresolvedLinks;const f={};Object.values(u).forEach(l=>Object.keys(l).forEach(t=>f[t]=(f[t]||0)+1));return JSON.stringify(Object.entries(f).sort((a,b)=>b[1]-a[1]).slice(0,10));})()" vault="{vault}"
```

A short name with many refs (e.g. `[[Diadoc]]` ×30) = create a hub note `Diadoc.md` → `[[MOC — …]]` so all those links resolve (alias doesn't work for bare links — by design).

### Step 3: Tag Distribution

```bash
obsidian tags counts sort=count vault="{vault}"
```

Show top 15 tags. Flag tags used only once (potential typos).

### Step 4: Notes by Type

Use tags (indexed, reliable) instead of fulltext search:

```bash
obsidian tags counts sort=count vault="{vault}"
```

From the output, extract counts for taxonomy tags: `#atom`, `#molecule`, `#source`, `#session`, `#moc`. These correspond to `config.taxonomy.*.tag` values.

Total notes count:

```bash
obsidian files ext=md vault="{vault}" total
```

### Step 5: Missing Links Section (batched grep — 3600x faster)

**Do NOT loop `obsidian read` per file** — on a 1000-note vault that's ~180s. Use a single filesystem grep against the vault directory.

```bash
VAULT_PATH=$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/get-vault-path.sh" "{vault}")

# Single recursive grep -L: files NOT containing the links section heading.
# Filter to taxonomy-prefixed notes.
grep -rL --include="*.md" "{links_section}" "$VAULT_PATH" 2>/dev/null \
  | grep -E "(Atom|Molecule|Source|Session|MOC) — "
```

**Measured on 999-note vault: ~49ms vs ~180s serial** — 3600x speedup. Safe to run always.

Report notes missing the section.

### Step 6: Bad Filenames (`#` in names → permanent orphans)

```bash
VAULT_PATH=$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/get-vault-path.sh" "{vault}")
find "$VAULT_PATH" -name "*#*.md" -not -path "*/.obsidian/*" -not -path "*/.trash/*" 2>/dev/null | sed "s|$VAULT_PATH/||"
```

Files with `#` in the name are **permanent orphans** — `[[Note #1]]` parses as `[[Note]]` + heading anchor `#1`, so nothing resolves to them (even existing links). Flag for rename (`#` → `—` or drop the `#`). Same for `.` mid-name (breaks CLI create). See `references/tool-routing.md` (naming rules).

### Step 7: Review Candidates (content-staleness, type-aware)

A *temporal* signal, distinct from orphans (Step 1, which is *structural*): notes untouched longer than the threshold **for their type** are candidates for a re-read. Threshold precedence: per-note `ttl: <days>` → `review.staleDays.<type>` → `review.staleDays.default` → `30` (legacy). Age is measured from the newest of `date` or `reviewed` — so stamping `reviewed: {today}` on a still-valid note **resets its clock**. That snooze is what stops a stale list from rotting into guilt-debt (the canonical failure mode of review dates — see Gotchas).

```bash
VAULT_PATH=$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/get-vault-path.sh" "{vault}")
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/review-candidates.py" "$VAULT_PATH" --limit 30
# Or from source: plugins/mnemo/scripts/review-candidates.py
```

Output: `CANDIDATES\t{n}`, then `THRESHOLDS\t{json}`, then one tab-separated row per note (`{overdue_days}  {type}  {anchor_date}  {anchor_src}  {relpath}`), most-overdue first. Pure filesystem — independent of the obsidian CLI graph cache (no lag/lie risk). A missing `review` config section reproduces the legacy uniform 30-day behavior, so this is safe before any config migration.

Don't AND this with backlinks — a well-linked note can still hold outdated claims. Report candidates on their own; cross-reference Step 1 yourself if you specifically want "old **and** orphaned."

### Step 7.5: Content Lint (optional deep pass — gated by `review.lint.enabled`)

Steps 1-7 are cheap and structural. This is the **content** pass — Karpathy's "lint": actually re-read the notes to judge whether claims have rotted, instead of trusting the calendar. Together the checks cover his four: orphans (Step 1) + concepts-mentioned-but-no-page (Step 2 unresolved links) + stale claims (Step 7) + **contradictions** (here). Gated by `config.json` → `review.lint.enabled` (default **false**) because it reads note bodies and costs tokens — **skip this step silently when disabled**.

When enabled, take the top `review.lint.maxCandidates` (default **15**) candidates from Step 7 and have them read & judged on the model set by `config.json` → `review.lint.model` (default **`haiku`**; `sonnet`/`opus` for higher-quality verdicts). This health skill itself runs as a `haiku` fork and **cannot upgrade its own model**, so:

- If `review.lint.model` is `haiku` (or unset) → do the lint inline in this fork.
- Otherwise → **spawn one subagent** (Agent/Task tool, `model: {review.lint.model}`, `subagent_type: Explore` or general) that reads the candidate note bodies in **one batched pass** (filesystem read, not one `obsidian read` per file) and returns the verdicts. Keeping the cheap Steps 1-7 on `haiku` while the lint runs on `opus` is the whole point of the split.

Emit a verdict per candidate:

- **still-valid** → recommend the user stamp `reviewed: {today}` on it (resets the clock).
- **update-needed** → one line on what specifically looks outdated.
- **contradicts [[Other Note]]** → name the conflicting note; flag the *older* one against the newer.

Verdicts are **triage, not truth** — on `haiku` especially, expect false positives; even on `opus`, surface them as questions. Never auto-edit; only report (consistent with the rest of health). The user decides.

### Step 8: Top Hubs

For each MOC, count backlinks:

```bash
obsidian backlinks file="{moc_name}" vault="{vault}"
```

Sort by count, show top 5.

### Step 9: Output Report

```
📊 Vault Health Report ({date})

⚠️ claude-mem: {warning or "v12.3.9, clean"}

Total: {N} notes
  Atoms: {N} | Molecules: {N} | Sources: {N}
  Sessions: {N} | MOCs: {N} | Other: {N}

🔴 Orphans: {N}
  - Note Name 1
  - Note Name 2

🟡 Missing {links_section}: {N}
  - Note Name 1

🚫 Bad filenames (`#`/`.`): {N} — permanent broken links, rename
  - Atom — Foo (PR #12)  → rename to "PR 12"

🔍 Top unresolved targets (missing hub notes?):
  1. [[Diadoc]] ×34 → create hub note?
  2. [[Python]] ×28

🔗 Unresolved wikilinks: {N} total
📏 Tags: {N} total, {N} used once

🏆 Top-5 Hubs (most backlinks):
  1. MOC — Security (34)
  2. MOC — AI ML Tools (28)
  ...

💤 Review candidates (stale by type-aware age): {N}
  - Atom — API X gotcha — 45d overdue (atom, ttl 14)
  - Decision — auth model — 35d overdue (decision, 365d)
  (snooze a still-valid note: add `reviewed: {today}` to its frontmatter)

🔬 Content lint: {N judged}   ← only when review.lint.enabled
  - Atom — API X gotcha → UPDATE-NEEDED: superseded by [[Atom — API X v2]]
  - Decision — auth model → still-valid (recommend `reviewed: {today}`)

🧠 Claude memory/ index: {KB}KB / {lines} lines {✅ lean | ⚠️ bloated → autodream}
```

Omit the `🔬 Content lint` block entirely when `review.lint.enabled` is false.

Skip the `⚠️ claude-mem` line entirely if Step 0 found nothing to warn about.

### Step 10: Claude memory/ index health (autodream check)

Separate from the Obsidian vault, Claude Code keeps an **always-loaded** index at `memory/MEMORY.md`. Claude Code auto-memory **hard-truncates this index at ~24.4 KB on load** — beyond that, trailing rows silently vanish from Claude's context. So warn *early* (before the cliff), not at some lax size. Threshold is configurable via `config.json` → `memory.indexWarnKB` (default **22**):

```bash
WARN=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.mnemo/config.json'))).get('memory',{}).get('indexWarnKB',22))" 2>/dev/null || echo 22)
for f in "$HOME"/.claude/projects/-*/memory/MEMORY.md; do
  [ -f "$f" ] || continue
  kb=$(( $(wc -c < "$f") / 1024 )); ln=$(wc -l < "$f")
  [ "$kb" -gt "$WARN" ] && echo "⚠️ $(basename "$(dirname "$(dirname "$f")")"): ${kb}KB / ${ln} lines — >${WARN}KB warn (auto-memory truncates ~24.4KB) → run autodream (move sessions → MEMORY-archive-index.md, target <20KB)"
done
```

If flagged → recommend **autodream** (memory consolidation): slim the index into topic files + `MEMORY-archive-index.md`, **no loss**. Procedure: `~/.claude/memory/autodream-principles.md`. This is the only `memory/` check here — vault-health otherwise audits Obsidian, not Claude's memory/.

## Gotchas

Common failures in `references/gotchas.md`. Skill-specific rules:

- `obsidian orphans` may return empty on small vaults — this is OK, not an error.
- Reference notes (taxonomy docs, templates) aren't orphans even if few backlinks — they're meant to be lookups.
- Ghost notes (unresolved wikilinks) are a **feature**, not a bug — they enable entity discovery. Don't flag on raw count; instead surface the **top targets** (Step 2 eval) — frequent ones = missing hub notes (actionable).
- **CLI graph queries cache & can lie** — `orphans`/`unresolved`/`backlinks` lag writes and have shown a note as resolved AND broken at once. For critical checks use `obsidian eval` on `metadataCache` (see `references/gotchas.md`). Treat counts as advisory if notes were created this session.
- **Do not auto-fix anything** — only report. User decides what to clean up. This includes `reviewed:` — **health never writes frontmatter**; the snooze stamp is the user's call (keeps health strictly read-only).
- Step 5 uses filesystem grep (~3600x faster than per-file reads — 49ms vs 180s on a 999-note vault) — safe on any vault size.
- **Review candidates (Step 7) are temporal, not structural** — don't conflate with orphans. A note can be both, either, or neither. The script is age-only by design (cheap, no graph dependency).
- **Content-lint verdicts (Step 7.5) are triage-grade** — time-based staleness is a *proxy*, not the signal (a 6-month-old note may be perfectly valid; "not read ≠ not valuable"). On `haiku` especially, contradiction/update calls have false positives. Surface them as questions, never as facts, and never act on them automatically. The whole point of `reviewed:` is to let a quick human confirm and silence a false flag.

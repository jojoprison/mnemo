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

### Step 7: Stale Notes

Find notes with `date:` in frontmatter older than 30 days, then check backlinks:

```bash
obsidian backlinks file="{note_name}" vault="{vault}"
```

If zero backlinks AND date > 30 days ago → stale.

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

💤 Stale (30d+ no backlinks): {N}

🧠 Claude memory/ index: {KB}KB / {lines} lines {✅ lean | ⚠️ bloated → autodream}
```

Skip the `⚠️ claude-mem` line entirely if Step 0 found nothing to warn about.

### Step 10: Claude memory/ index health (autodream check)

Separate from the Obsidian vault, Claude Code keeps an **always-loaded** index at `memory/MEMORY.md`. It must stay lean — a bloated index gets **truncated on load**, so old entries silently vanish from Claude's context. Flag oversized indexes:

```bash
for f in "$HOME"/.claude/projects/-*/memory/MEMORY.md; do
  [ -f "$f" ] || continue
  kb=$(( $(wc -c < "$f") / 1024 )); ln=$(wc -l < "$f")
  [ "$kb" -gt 60 ] && echo "⚠️ $(basename "$(dirname "$(dirname "$f")")"): ${kb}KB / ${ln} lines — run autodream (target <40KB / <200 lines)"
done
```

If flagged → recommend **autodream** (memory consolidation): slim the index into topic files + `MEMORY-archive-index.md`, **no loss**. Procedure: `~/.claude/memory/autodream-principles.md`. This is the only `memory/` check here — vault-health otherwise audits Obsidian, not Claude's memory/.

## Gotchas

Common failures in `references/gotchas.md`. Skill-specific rules:

- `obsidian orphans` may return empty on small vaults — this is OK, not an error.
- Reference notes (taxonomy docs, templates) aren't orphans even if few backlinks — they're meant to be lookups.
- Ghost notes (unresolved wikilinks) are a **feature**, not a bug — they enable entity discovery. Don't flag on raw count; instead surface the **top targets** (Step 2 eval) — frequent ones = missing hub notes (actionable).
- **CLI graph queries cache & can lie** — `orphans`/`unresolved`/`backlinks` lag writes and have shown a note as resolved AND broken at once. For critical checks use `obsidian eval` on `metadataCache` (see `references/gotchas.md`). Treat counts as advisory if notes were created this session.
- **Do not auto-fix anything** — only report. User decides what to clean up.
- Step 5 uses filesystem grep (~3600x faster than per-file reads — 49ms vs 180s on a 999-note vault) — safe on any vault size.

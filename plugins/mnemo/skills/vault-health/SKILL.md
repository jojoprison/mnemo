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

Show `[[wikilinks]]` pointing to non-existent files. Ghost notes are NORMAL (entity discovery) — only flag if count seems excessive (>200).

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

From the output, extract counts for taxonomy tags: `#atom`, `#molecule`, `#source`, `#session`, `#moc`, `#inbox`. These correspond to `config.taxonomy.*.tag` values.

Total notes count:

```bash
obsidian files ext=md vault="{vault}" total
```

### Step 5: Missing Links Section (batched grep — 1800x faster)

**Do NOT loop `obsidian read` per file** — on a 1000-note vault that's ~180s. Use a single filesystem grep against the vault directory.

```bash
VAULT_PATH=$(bash "${CLAUDE_PLUGIN_ROOT}/scripts/get-vault-path.sh" "{vault}")

# Single recursive grep -L: files NOT containing the links section heading.
# Filter to taxonomy-prefixed notes, exclude inbox.
grep -rL --include="*.md" "{links_section}" "$VAULT_PATH" 2>/dev/null \
  | grep -E "(Atom|Molecule|Source|Session|MOC) — " \
  | grep -v "Inbox —"
```

**Measured on 999-note vault: ~49ms vs ~180s serial** — 3600x speedup. Safe to run always.

Inbox notes are **exempt** via the `grep -v "Inbox —"` filter.

Report notes missing the section.

### Step 6: Inbox Backlog

Count from Step 4's inbox search. If > 0, remind:
"N inbox notes waiting for classification. Run /mnemo:sort to classify."

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
  Sessions: {N} | MOCs: {N} | Inbox: {N} | Other: {N}

🔴 Orphans: {N}
  - Note Name 1
  - Note Name 2

🟡 Missing {links_section}: {N}
  - Note Name 1

📬 Inbox backlog: {N} notes — run /mnemo:sort to classify

🔗 Unresolved wikilinks: {N}
📏 Tags: {N} total, {N} used once

🏆 Top-5 Hubs (most backlinks):
  1. MOC — Security (34)
  2. MOC — AI ML Tools (28)
  ...

💤 Stale (30d+ no backlinks): {N}
```

Skip the `⚠️ claude-mem` line entirely if Step 0 found nothing to warn about.

## Gotchas

Common failures in `references/gotchas.md`. Skill-specific rules:

- `obsidian orphans` may return empty on small vaults — this is OK, not an error.
- Reference notes (taxonomy docs, templates) aren't orphans even if few backlinks — they're meant to be lookups.
- Ghost notes (unresolved wikilinks) are a **feature**, not a bug — they enable entity discovery. Only flag if excessive (>200).
- **Do not auto-fix anything** — only report. User decides what to clean up.
- Step 5 uses filesystem grep (1800x faster than per-file reads) — safe on any vault size.

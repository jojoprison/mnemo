# mnemo:health — Vault Health Check & Analytics

## Overview

Comprehensive audit of your Obsidian vault: orphans, broken links, missing sections, stale notes, type distribution, and hub analysis.

## Usage

```
/mn:health
```

No arguments needed. Reads vault name from `~/.mnemo/config.json`.

## What It Checks

| Check | What it finds | Severity |
|-------|--------------|----------|
| Orphans | Notes with zero backlinks (invisible in Graph View) | 🔴 High |
| Missing links section | Notes without `## Links` / `## Связи` (disconnected from graph) | 🟡 Medium |
| Unresolved wikilinks | `[[Ghost Notes]]` pointing to non-existent files | ℹ️ Normal |
| Tag typos | Tags used only once (potential misspelling) | 🟡 Medium |
| Review candidates | Notes past their **type-aware** staleness threshold — due for a re-read/refresh | 💤 Low |
| Content lint *(opt-in)* | LLM re-reads candidates → still-valid / update-needed / contradicts verdicts | 🔬 Deep |

## Example Output

```
📊 Vault Health Report (2026-03-24)

Total: 375 notes
  Atoms: 221 | Sessions: 96 | Sources: 21
  Molecules: 19 | MOCs: 17

🔴 Orphans: 14
  - Atom — old note without links
  - Session — 2026-03-14 forgotten session

🟡 Missing ## Связи: 2
  - Atom — quick note without links section

🏆 Top-5 Hubs (most backlinks):
  1. MOC — Arcadia (102)
  2. MOC — Claude Code Tools (54)
  3. MOC — Infrastructure (37)

💤 Review candidates (stale by type-aware age): 3
  - Atom — Heroku backup count — 72d overdue (atom, 60d)
  - Source — pricing page snapshot — 40d overdue (source, ttl 30)
  (snooze a still-valid note: add `reviewed: 2026-03-24` to its frontmatter)
```

## Staleness & review

Review candidates are **temporal** (age-based), separate from orphans (structural). The threshold is per **type**, configured in `~/.mnemo/config.json` → `review.staleDays` — a volatile `atom` ages faster than a `decision`. A per-note `ttl: <days>` overrides it; a `reviewed: <date>` stamp resets the clock (the snooze that keeps stale lists from becoming guilt-debt). With no `review` config, it falls back to a uniform 30 days.

Set `review.lint.enabled: true` to add the **content lint** — an LLM re-reads the top candidates and judges whether claims actually rotted (still-valid / update-needed / contradicts), Karpathy-style, instead of trusting the calendar. It's off by default because it reads note bodies; verdicts are triage, never auto-applied.

## Important Notes

- **Ghost notes are a feature** — `[[Technology]]` links to non-existent files are intentional for entity discovery in Graph View
- **Non-destructive** — only reports, never auto-fixes. You decide what to fix
- Run weekly or after creating many notes at once

## Related Skills

- `/mn:connect` — fix orphans by discovering hidden connections

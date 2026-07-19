# mn:health — Vault Health Check & Analytics

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
| Research-gap candidates | Where the vault wants to grow — populous topic with no MOC, recurring external with no Source note | 🌱 Growth |
| Cross-runtime recall status *(opt-in)* | Whether the counterpart runtime can be mapped to this exact git repository; metadata only, no memory-content audit | 🔄 Info |

## Example Output

```
📊 Vault Health Report (2026-03-24)

🔄 Cross-runtime recall: Claude memory available

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
  - Atom — Heroku backup count — 72d overdue (atom, 60d budget)
  - Source — pricing page snapshot — 40d overdue (source, 180d budget)
  (snooze a still-valid note: add `reviewed: 2026-03-24` to its frontmatter)

🌱 Research-gap candidates (where the vault wants to grow): 2
  - #auth ×12 notes, no MOC → create MOC — Auth?
  - [[LangGraph]] ×9, no Source note → capture one?
```

## Staleness & review

Review candidates are **temporal** (age-based), separate from orphans (structural). The threshold is per **type**, configured in `~/.mnemo/config.json` → `review.staleDays` — a volatile `atom` ages faster than a `decision`. A per-note `ttl: <days>` overrides it; a `reviewed: <date>` stamp resets the clock (the snooze that keeps stale lists from becoming guilt-debt). With no `review` config, it falls back to a uniform 30 days.

Set `review.lint.enabled: true` to add the **content lint** — an LLM re-reads the top candidates and judges whether claims actually rotted (still-valid / update-needed / contradicts), Karpathy-style, instead of trusting the calendar. It's off by default because it reads note bodies; verdicts are triage — the only write they can trigger is the `reviewed:` snooze stamp on still-valid notes (see next paragraph), never a content edit.

`review.lint.autoStampReviewed` (default **true**) **closes the snooze loop**: the lint stamps `reviewed: {today}` on notes it judges still-valid, so a confirmed note stops resurfacing without a manual edit. That one `reviewed:` write is the *only* frontmatter health ever touches (never content, never on update-needed/contradicts). It only fires when the content lint is enabled (`review.lint.enabled`, default off), so a default install still writes nothing; set `autoStampReviewed: false` to keep the lint suggest-only.

## Research-gap candidates

Beyond cleaning up, `/mn:health` points at where the vault wants to **grow** — Karpathy's "suggest new article candidates", the on-philosophy half. From signal it already collected (no extra cost), it flags a populous topic tag (≥5 notes) with no MOC, and a recurring external entity cited many times with no `Source —` note. These are suggestions only — mnemo never web-searches to fill them or auto-creates anything; it shows the gap and you decide.

## Important Notes

- **Ghost notes are a feature** — `[[Technology]]` links to non-existent files are intentional for entity discovery in Graph View
- **Non-destructive by default** — out of the box health only reports (the content lint is off). The one write it can make is the `reviewed:` snooze stamp on still-valid notes once you enable the lint (`review.lint.autoStampReviewed`, default on; set false to keep the lint suggest-only).
- **Runtime isolation** — Claude Code additionally checks its own auto-memory index and optional claude-mem cache. Codex skips both size/cache checks. When cross-runtime recall is enabled, either runtime may run one exact-project metadata projection: it decodes/retains only scope metadata, never returns or summarizes body content, never broad-scans another runtime, and repairs nothing. The flat Codex registry may require bounded streaming past opaque body bytes to locate later task-group headers.
- Run weekly or after creating many notes at once

## Related Skills

- `/mn:connect` — fix orphans by discovering hidden connections

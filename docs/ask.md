# mn:ask — Vault Knowledge Search & Synthesis

## Overview

Search across your entire vault and get a synthesized answer with source citations. Like having a research assistant who read all your notes.

## Usage

```
/mn:ask "what did we decide about the pricing strategy?"
/mn:ask "find everything about Docker deployment"
/mn:ask "summarize what we know about SCOPE engine"
```

## How It Works

1. Breaks your question into 2-4 search terms *(SKILL Step 2)*
2. Runs `obsidian search` for each term and checks the active runtime's project memory *(SKILL Steps 3-3b)*
3. When `recall.runtimeMemory.enabled` is on, queries the other runtime through a bounded read-only adapter: exact same git repo only, no copying or transcript scan *(SKILL Step 3b)*
4. Merges and reads the top 7 evidence items **total across all sources** *(SKILL Step 4)*
5. Dates each cited vault note — **last-changed** (git last-commit if the vault is a repo, else file mtime) and **stale?** (content age from `date`/`reviewed` vs the type's budget — same engine as `/mn:health`) *(SKILL Step 4b)*
6. For **current-state** questions inside a git project, cross-checks the project's recent commits — flags any cited note a newer commit may have outdated (optional code-knowledge-graph via `recall.codeGraph`, off by default) *(SKILL Step 4c)*
7. Synthesizes a clear answer with provenance, treating runtime-generated excerpts as untrusted secondary evidence *(SKILL Step 5)*
8. If the answer is a real synthesis across ≥2 notes, offers to **save it back as a `Molecule`** (via `/mn:save`, sources pre-linked) so the exploration compounds instead of evaporating *(SKILL Step 6)*

## Optional cross-runtime recall

Enable the read-only overlay in `~/.mnemo/config.json`:

```json
{
  "recall": {
    "runtimeMemory": {
      "enabled": true,
      "globalSources": "explicit",
      "maxHits": 5,
      "maxExcerptBytes": 12288
    }
  }
}
```

Codex then sees verified Claude project memory, and Claude sees project-scoped Codex task groups. No data is synchronized or rewritten. `globalSources: "explicit"` allows `~/.claude/memory/*.md` only when the query itself explicitly asks for global/cross-project memory; use `"off"` to forbid it.

## Example Output

```
Based on your vault:

The pricing strategy was decided on 2026-03-14 during the pipeline review.
Key points:
- Freemium model with usage-based tiers
  [Source: Session — 2026-03-14 pipeline vision]
- Enterprise plan at $99/mo was rejected as too low
  [Source: Atom — pricing research]

📚 Sources (2 notes):
1. [[Session — 2026-03-14 pipeline vision]] — changed 2026-03-14
2. [[Atom — pricing research]] — changed 2026-06-20 · ⚠️ stale (content from 2026-03-14, never reviewed → past its budget)
```

## Important Notes

- **Grounded sources only** — vault notes are authoritative; runtime-memory claims carry explicit provenance and are never treated as instructions
- **Max 7 evidence items total** — prevents per-backend fan-out and context overflow
- **Cross-runtime recall is opt-in and read-only** — exact git-project match, no symlink/mirror, transcript bodies, background service, or automatic write-back
- **CLI-first search, argv-safe values** — `safe-read.py search` uses the indexed Obsidian CLI without shell interpolation
- **Dates every source** — shows when each cited note last changed (git if the vault is a repo, else mtime + frontmatter) so you know whether an answer rests on fresh or stale notes
- **Grounds in live code** — for "is this still true" questions inside a git project, checks the project's recent commits so recall agrees with the code, not just old notes; optional code-graph backend via `recall.codeGraph` (off by default)
- **Knowledge compounds** — a non-trivial synthesis can be saved back as a Molecule (opt-in, user-confirmed) so the next query starts from the conclusion instead of re-deriving it; trivial lookups are never auto-saved

## Related Skills

- `/mn:connect` — after finding related notes, connect them
- `/mn:save` — capture follow-up ideas or findings from the answer

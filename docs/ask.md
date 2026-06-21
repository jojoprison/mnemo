# mnemo:ask — Vault Knowledge Search & Synthesis

## Overview

Search across your entire vault and get a synthesized answer with source citations. Like having a research assistant who read all your notes.

## Usage

```
/mn:ask "what did we decide about the pricing strategy?"
/mn:ask "find everything about Docker deployment"
/mn:ask "summarize what we know about SCOPE engine"
```

## How It Works

1. Breaks your question into 2-4 search terms
2. Runs `obsidian search` for each term
3. Reads the top 7 most relevant notes
4. Dates each cited note — **last-changed** (git last-commit if the vault is a repo, else file mtime) and **stale?** (content age from `date`/`reviewed` vs the type's budget — same engine as `/mn:health`)
5. For **current-state** questions inside a git project, cross-checks the project's recent commits — flags any cited note a newer commit may have outdated (optional code-knowledge-graph via `recall.codeGraph`, off by default)
6. Synthesizes a clear answer citing specific notes, ⚠️-flagging any whose content is stale or contradicted by recent code
7. Lists all source notes with `[[wikilinks]]`, their last-changed date, and a stale flag where it applies

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

- **Only answers from your vault** — never hallucinated from general knowledge
- **Max 7 notes read** — prevents context overflow
- **CLI-first search** — uses `obsidian search`, not MCP
- **Dates every source** — shows when each cited note last changed (git if the vault is a repo, else mtime + frontmatter) so you know whether an answer rests on fresh or stale notes
- **Grounds in live code** — for "is this still true" questions inside a git project, checks the project's recent commits so recall agrees with the code, not just old notes; optional code-graph backend via `recall.codeGraph` (off by default)

## Related Skills

- `/mn:connect` — after finding related notes, connect them
- `/mn:save` — capture follow-up ideas or findings from the answer

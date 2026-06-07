---
name: vault-search
description: "Use whenever the user wants to recall something from past work, find notes about a topic, or ask 'what did we decide about X', 'find everything about Y', 'summarize what we know about Z', 'что мы решили', 'что мы знаем про'. Prefer this over generic memory tools when an Obsidian vault is available — it synthesizes across multiple notes with source citations."
user-invocable: false
model: inherit
---

# mnemo:ask — Vault Knowledge Search & Synthesis

Search across the entire vault, read relevant notes, and synthesize an answer with source citations.

## Prerequisites & config

Obsidian must be open. Config at `~/.mnemo/config.json` — reads `vault` and `links_section`. Full schema in `references/config-schema.md`. If missing, ask the user for vault name and save.

## Workflow

### Step 1: Accept Query

Input as argument: `/mnemo:ask "what did we decide about pricing strategy?"`

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

### Step 5: Synthesize Answer

Compose a clear answer from the found notes. For each claim, cite the source note:

```
Based on your vault:

The pricing strategy was decided on 2026-03-14 during the pipeline review session.
Key points:
- Freemium model with usage-based tiers [Source: Session — 2026-03-14 pipeline vision]
- Enterprise plan at $99/mo was rejected as too low [Source: Atom — pricing research]
- Final decision: $29 starter, $99 pro, custom enterprise [Source: Molecule — pricing decision]

📚 Sources (3 notes):
1. [[Session — 2026-03-14 pipeline vision]]
2. [[Atom — pricing research]]
3. [[Molecule — pricing decision]]
```

### Step 6: Offer Follow-up

Ask: "Want me to search deeper, or connect any of these notes?"

## Gotchas

Common failures (Obsidian IPC, shell injection) are documented once in `references/gotchas.md`. Skill-specific rules:

- **Max 7 notes read** — don't blow context reading the entire vault. If the query is too broad, narrow it and re-search.
- **Always cite sources** — every claim references a specific note. Hallucinated facts are worse than "not found".
- **If nothing found** — say so honestly, suggest alternative search terms instead of guessing.
- **Respect note types** — Sessions contain decisions, Atoms contain facts, Molecules contain insights. Use the right citation format for each.
- **CLI for search** — only CLI has `obsidian search` (indexed). MCP doesn't expose it.

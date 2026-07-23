# mn:connect — Discover Hidden Links

## Overview

Analyzes a note and discovers connections to other notes you'd never think of. Shows suggestions with explanations — you confirm before applying. (One exception: `/mn:review --full` with `review.full.autoConnect` turned on applies them for you — the standalone command never does.)

## Usage

```
/mn:connect "Atom — LongCat-Flash-Prover"
/mn:connect "Session — 2026-03-23 Tech Research"
```

## How It Works

1. Reads the target note
2. Extracts key concepts (technologies, names, patterns)
3. Searches vault for each concept
4. Compares found notes vs already linked notes
5. Suggests new connections with reasoning
6. Applies only what you approve (the `review --full` chain can auto-apply when `review.full.autoConnect` is on)

## Example Output

```
🔗 Connection suggestions for "Atom — LongCat-Flash-Prover"

Already connected: 3 notes
New suggestions: 5

1. [[Atom — SCOPE beats TextGrad]]
   Why: Both discuss agentic RL stability

2. [[MOC — Agent Self-Correction]]
   Why: trial→verify→reflect cycle matches SCOPE pattern
   Action: Add to MOC?

Apply these? (y/N, or pick numbers: 1,2)
```

## Important Notes

- **Max 5-7 suggestions** — won't overwhelm you
- **Standalone never auto-applies** — you confirm each connection; only `review --full` with `review.full.autoConnect` (default off) applies them for you
- **Ignores generic matches** — "both mention Claude" is not a meaningful connection
- **Won't suggest orphans** — they need their own fixing first

## Related Skills

- `/mn:health` — find orphans that need connecting
- `/mn:ask` — search first, then connect what you find

# mn:session — Session Notes + Cross-Session Handoff

## Overview

Creates a session summary note in Obsidian after significant work. The killer feature: writes a handoff file so the next session knows where you left off.

## Usage

```
/mn:session
```

No arguments. Summarizes the current conversation automatically.

## How It Works

1. Analyzes current conversation (what was done, decisions, PRs)
2. Checks for duplicate session notes (same day)
3. Creates `Session — YYYY-MM-DD description` note
4. Verifies the note is linked in the relevant MOC
5. Updates `Meta — Session Handoff` with pending items
6. Checks for orphans after creation

## Example Output

```
✅ Session saved

Note: "Session — 2026-03-24 Tech Research + mnemo plugin"
MOC: [[MOC — Claude Code Tools]] — link added ✅
Handoff: Updated with 2 pending items
Orphans: 0 new

Handoff contents:
## Pending
- [ ] Test /mn:review in real session
- [ ] Update docs for new skill names

## Context
- Refactored mnemo plugin, 8 skills, CE-pattern naming
```

## Cross-Session Continuity

When the next session starts, it reads `Meta — Session Handoff`:
- Picks up pending items
- Has context about what happened
- No more "what was I doing yesterday?"

## When to Use

- ✅ After completing a feature / PR / fix
- ✅ After significant research session
- ✅ End of work day
- ❌ Don't use for trivial tasks (typo fix, one-liner)

## Important Notes

- **Handoff: append, don't overwrite** — pending items accumulate
- **MOC verification** — automatically adds to MOC if missing
- **Branch field optional** — research sessions don't have branches
- **Ghost notes generously** — wraps projects, technologies, people in `[[wikilinks]]`

## Related Skills

- `/mn:review` — recommends session when significant work lacks a note, then waits for confirmation
- `/mn:health` — verify session note isn't an orphan
- `/mn:connect` — discover connections for the new session note

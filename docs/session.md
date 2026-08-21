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
2. Checks for duplicate session notes (same day) — and if a note for *this same session* already exists (matched by the `session_id` it would write, or by the filename derived earlier this session), updates that note in place instead of creating a second one
3. Creates a note with the prefix/tag reached through `taxonomy_roles.session`
4. Verifies the note is linked in the hub reached through `taxonomy_roles.moc`
5. Writes the session's open tails into that note's own `## Next steps / pending`, and upserts **one pointer line** into `Meta — Session Handoff`
6. Checks for orphans after creation
7. Self-checks its own note (duplicate / MOC link / orphan / atom-delegation) before confirming

## Example Output

```
✅ Session saved

Note: "Session — 2026-03-24 Tech Research + mnemo plugin"
MOC: [[MOC — Claude Code Tools]] — link added ✅
Handoff: pointer line upserted (2 open tails stay in the note)
Orphans: 0 new

In the session note:
## Next steps / pending
- [ ] Test /mn:review in real session
- [ ] Update docs for new skill names

In Meta — Session Handoff (one line):
- 2026-03-24 · mnemo · open 2 · [[Session — 2026-03-24 Tech Research + mnemo plugin]]
```

**Why the tail stays in its own note.** When unfinished work was written into the shared handoff instead, only 9% of a live vault's fresh open items existed in their own session note — the handoff became the single home of forward state, reached 805 KiB, and could then be neither read nor shrunk. A pointer line is bounded by the number of sessions; a copied tail is bounded by nothing. The handoff keeps the last `handoff.keepDays` (default 31) days of pointers; older ones drop, because the note behind each pointer keeps the detail.

## Cross-Session Continuity

The next session starts with the **open-tails digest**: `hooks/mnemo-context.sh` runs `hot-scan.py` over the pending sections of recent session notes and injects a byte-capped summary (`hot.windowDays`, `hot.maxKB`) next to the memory nudge, scoped to the repo you are in (`hot.scope`).

- Picks up pending items
- Has context about what happened
- No more "what was I doing yesterday?"

**The handoff note itself is not read at startup, and never was.** That expectation was documented here for a long time, but no such path existed in any hook or skill — and a grown handoff cannot be read even on request (a file read caps at 256 KB / 25,000 tokens). Measured on a live vault in July 2026, an 805 KiB handoff was opened for continuity in 6% of sessions. The digest above is the automatic reader that claim always assumed; `Meta — Session Handoff` remains the durable index that `session` writes and `health` Step 7.6 triages.

## When to Use

- ✅ After completing a feature / PR / fix
- ✅ After significant research session
- ✅ End of work day
- ✅ Mid-task checkpoint, before a long run risks context compaction — the same session's note is updated in place, never duplicated
- ❌ Don't use for trivial tasks (typo fix, one-liner)

## Important Notes

- **Handoff: targeted optimistic update** — replace/insert exact sections after a read; guarded archive rotation keeps open/recent items hot and closed history cold without blind append
- **Semantic routing** — requires exactly `fact`/`insight`/`source`/`session`/`moc`, valid taxonomy targets, and the functional self-maps `session → session`, `moc → moc`
- **One vault writer** — note, hub, and handoff updates all use the bundled JSON-stdin `vault-write.py`
- **MOC verification** — automatically adds to MOC if missing
- **Branch field optional** — research sessions don't have branches
- **Ghost notes generously** — wraps projects, technologies, people in `[[wikilinks]]`
- **Thorough by routing, not volume** — the note stays a narrative; decisions, business-logic, pains, and how-you-think route to `save`'s typed atoms (see the depth-contract), links to `connect`, unfinished work to handoff — never a "capture everything" blob
- **Own-note self-check** — Step 7 verifies only this note's own artifact; the cross-skill palace audit is `review --full`'s job, not session's

## Related Skills

- `/mn:review` — recommends session when significant work lacks a note, then waits for confirmation
- `/mn:health` — verify session note isn't an orphan
- `/mn:connect` — discover connections for the new session note

# depth-contract — thoroughness by routing, not volume

The standing "be thorough when closing a session" contract. `review --full` injects this as the
thoroughness guidance for the `save` and `session` steps of its chain; `session` also reads it as
its default bar for a standalone run. It exists so the user never again pastes a "capture
everything, super-detailed, everything in its place" wall of prompt — that intent lives here,
natively.

## The one rule

**Thorough = the right material in the right home, richly linked — NOT more words in one note.**

Depth is a property of the *corpus* (many atoms + one narrative `session` note + `connect` links),
never of a single note. "Maximally detailed / capture everything" written into one note is a blob:
unretrievable point-precisely, and it drifts straight into the auto-ingest fork mnemo's founding
principle rejects (`docs/design-decisions.md`). This is the depth-via-structure rule from `save`
Step 0b, applied across the whole close-out.

## Routing table — material → home

| Material surfaced this session | Home | Shape |
|--------------------------------|------|-------|
| A decision + why | `save` → fact role | Y-statement (Step 0b) |
| A gotcha / business rule | `save` → fact role | GIVEN / WHEN / THEN + Because + Fails-when |
| How the user thinks / decides / what pains them / their quality bar | `save` → insight role, `kind: principle / pain / stance` | JTBD slots — user-authored/confirmed, never an agent dossier |
| A durable fact / external source | `save` → fact / source role | claim-title + BLUF + evidence |
| A cross-note synthesis (≥2 notes) | `save` → insight role | non-trivial insight, `cites:` the sources |
| An actionable never-X / always-Y rule tied to code | `save` Step 3.5 → `.claude/rules/` | path-scoped auto-inject, not recall |
| The session narrative (what happened, the arc, decisions-in-context) | `session` | one note + handoff, never a duplicate of today's |
| Connections between the new notes (incl. non-obvious) | `connect` | suggest-only links, no orphans |
| A future-useful thread not finished | `session` handoff `- [ ]` pending | thin live index |

The business-logic / pains / mental-model layer is the crown material — it routes to `save`'s typed
`principle` / `pain` / `stance` atoms, **not** the session narrative. That is how "capture the way I
think" lands as connected, retrievable atoms instead of a scroll.

## Aesthetic (the palace)

Apply the user's memory aesthetic, captured as a durable `stance` atom: a curated palace where every
atom sits in its right place and connects — not a warehouse of "everything, in full". Curated over
exhaustive; atomic over monolithic; linked over loose; structured over voluminous.

## What NOT to do

- Do **not** inflate a note to be "more detailed" — split into atoms instead.
- Do **not** triplicate one finding into every store "to be safe" — route by kind (one kind → one home).
- Do **not** invent a psychological dossier of the user — the how-they-think atoms are user-authored/confirmed only.
- Do **not** fold business-logic / mental-model into the session narrative — that is `save`'s typed-atom job.

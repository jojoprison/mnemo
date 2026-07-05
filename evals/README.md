# mnemo trigger-evals

`trigger-eval.json` is a fixed set of prompts for checking that the canonical skill **descriptions** trigger correctly: 6 proactive-positive prompts (a specific skill *should* auto-invoke) and 6 near-miss negatives (they share keywords with a skill but must *not* trigger). Re-run it after editing any `description:` to catch a trigger regression before release.

## Why this exists

A skill's `description` is the only thing the model sees when deciding whether to auto-invoke it (the body loads only after). Rewriting a description to be more "pushy" can quietly start over-triggering (fires on unrelated tasks) or under-triggering. This set pins the intended behavior — especially the hard part: **near-miss discrimination** on shared words (`сохрани` a file ≠ save to memory, `здоровье` of a service ≠ vault health, `свяжись` with a team ≠ link notes, `поищи` on the web ≠ vault recall).

## How to run

Two options, both fine:

1. **skill-creator's optimizer** (Claude Code): the JSON's `query` + `should_trigger` fields are compatible with `skill-creator`'s `run_loop.py`, which measures trigger rate per description and can propose improvements. Point it at a skill and this eval set.

2. **Direct routing check** (what produced the 2026-07-05 baseline): give a fresh agent the current listing of the 7 canonical mnemo descriptions plus one `query`, and ask which skill (if any) it would auto-invoke. Score `predicted == expect_skill` for positives, `predicted == none` for negatives. **Normalize the skill name** (strip any `mnemo:` prefix) before comparing — a strict `===` that ignores the prefix under-counts a correct route.

## Baseline

**2026-07-05 (v1.1.x): 12/12** — recall 6/6 (all positives routed to the right skill), specificity 6/6 (all near-misses returned none). Caveat: this is a *simulation of routing judgment*, not a live Claude Code trigger; treat it as a strong signal and a regression tripwire, not a physical guarantee. The live effect (does the model actually reach for the skill mid-task) is probabilistic by nature — see `docs/design-decisions.md` → "Proactive nudges via hooks" (delivery ≠ effect).

## Extending (follow-up, non-blocking)

Widen to ~5 examples per skill and add boundary cases where two mnemo skills compete: `memory-routing` ↔ `council` (deciding vs recording a decision), `vault-search` ↔ `vault-health` (recall vs maintenance).

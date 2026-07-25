# mnemo — backlog

Evaluated ideas that are **wanted but not built yet**, newest concern first. Rejected ideas do not live here — they belong in [`design-decisions.md`](design-decisions.md) § Non-goals, with their "If you want it" note.

**Card format:** `## <priority> — <title>` · **What** (the gap) · **Why now** (the pain that motivates it) · **Minimal shape** (smallest thing that earns its keep) · **On-philosophy** (why it does not break the one principle) · **Open questions** · **Origin**.

Priorities: 🔴 P1 must-do · 🟠 P2 valuable · 🟡 P3 nice · ⚪ P4 someday.

---

## 🔴 P1 — memory-freshness detector: flag notes that new commits have contradicted

**What.** Nothing in mnemo notices when a note becomes **false because the code changed**. Every freshness signal we ship looks at the *note*: `health` computes staleness from `date`/`reviewed` against a per-type budget, and `ask` Step 4c grounds a note in git only *reactively*, only for the CWD repo, and only when the user happens to ask. A commit in a file the note describes moves neither `date` nor `reviewed` — so a note can be simultaneously "fresh" by every metric and plainly wrong.

**Why now.** This is the highest-cost failure mode a memory tool has: a confidently wrong note is worse than a missing one, because agents act on it. Real precedent (a production Django project, July 2026): a note asserting "these snapshots are written **only** by the 15-minute scheduler" became false the day a PR added a second write path at document-creation time. The drift was even *spotted* by the maintainer four days later — and the note still stayed wrong for **5 days total**, because spotting is not fixing. It was finally corrected only when an unrelated branch-cleanup session happened to re-verify the subsystem against production. Everything read that note in the meantime. Frequency matters too: the same class recurred a second time within the same week on a different subsystem, which is the signal to build a detector rather than write a third note about it.

**Minimal shape (~50 lines, no agent, no token, no schedule).** A report-only check, run on demand, in the current repo:

1. `git log --name-only --since="<N> days"` (or since the last run) → the set of paths touched.
2. Grep the vault for notes mentioning those paths / their symbols.
3. Print candidates: *"`Atom — …` mentions `apps/documents/onec_snapshots.py`, touched by `abc1234` (2026-07-20) — re-verify."*

Nothing is rewritten; the output is a worklist. Natural home is **`mn:health`** as one more check (it already owns report-only detects and the research-gap candidates), which also keeps detects in one house instead of scattering them across skills.

**On-philosophy.** It is the *report-only half* — the exact pattern already shipped for web-search imputation (declined as a writer, shipped as `health` Step 8.5 research-gap candidates): point at the gap, never fill it. Non-destructive holds (no note is authored or overwritten), human-authored holds (the user judges and edits), in-agent holds (reads the repo mnemo is already running in — no external service, no crawl). Contrast with the ambitious version below, which is where the cost sits.

**Open questions.**
- **MATCH granularity:** by file path (cheap, noisy — a hub file touched every day flags everything) vs by symbol/subsystem (precise, needs parsing). Suggest starting per-path with a noise cap, and only then considering symbols.
- **Baseline of "since":** last-run marker in config vs a fixed window vs the note's own `date` (probably the note's `date` — it makes the check per-note and stateless).
- **Cross-repo / cross-org reach (the ambitious variant):** an agent with a broad read-scope GitHub token walking every repo and org, so drift caused by *another* repo's merge is caught too. This is where token perimeter, secret storage, and scheduling (nightly vs merge-webhook) become real questions — and why the minimal single-repo version should ship first and prove the signal.
- **Noise budget:** what makes this check *not* the one users disable. A hard cap on candidates per run, and ranking by "how central is this path to the note" are the obvious levers.

**Origin.** Requested by the maintainer, 2026-07-25, after the 5-day-wrong-note incident above; flagged explicitly as very important to build. The cross-repo agent framing predates it (2026-07-21) and is retained as the ambitious variant, not the first deliverable.

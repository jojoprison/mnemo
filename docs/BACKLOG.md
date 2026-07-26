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

**What already exists — do not rebuild it (added 2026-07-27).** `handoff-resolver.py` (v1.2.11) already ships the *anchor* half of this idea: it extracts Linear keys and PR numbers from open items, separates an item's **own** anchors from ones inherited from its header (inherited counting inflated resolvability 27.6% → 60.6%), and reports a worklist without ever writing. `health` Step 7.6 is its report-only host. So this card's remaining, genuinely new part is narrower than it reads: **the git side** — mapping "paths touched since the note's `date`" to the notes that mention them. Reuse the resolver's anchor parsing and its report shape; do not write a second anchor extractor, and do not widen this card back into "a general staleness detector" — type-aware staleness already ships in `health` Steps 7/7.5.

**On-philosophy.** It is the *report-only half* — the exact pattern already shipped for web-search imputation (declined as a writer, shipped as `health` Step 8.5 research-gap candidates): point at the gap, never fill it. Non-destructive holds (no note is authored or overwritten), human-authored holds (the user judges and edits), in-agent holds (reads the repo mnemo is already running in — no external service, no crawl). Contrast with the ambitious version below, which is where the cost sits.

**Open questions.**
- **MATCH granularity:** by file path (cheap, noisy — a hub file touched every day flags everything) vs by symbol/subsystem (precise, needs parsing). Suggest starting per-path with a noise cap, and only then considering symbols.
- **Baseline of "since":** last-run marker in config vs a fixed window vs the note's own `date` (probably the note's `date` — it makes the check per-note and stateless).
- **Cross-repo / cross-org reach (the ambitious variant):** an agent with a broad read-scope GitHub token walking every repo and org, so drift caused by *another* repo's merge is caught too. This is where token perimeter, secret storage, and scheduling (nightly vs merge-webhook) become real questions — and why the minimal single-repo version should ship first and prove the signal.
- **Noise budget:** what makes this check *not* the one users disable. A hard cap on candidates per run, and ranking by "how central is this path to the note" are the obvious levers.

**Origin.** Requested by the maintainer, 2026-07-25, after the 5-day-wrong-note incident above; flagged explicitly as very important to build. The cross-repo agent framing predates it (2026-07-21) and is retained as the ambitious variant, not the first deliverable.

---

## 🟠 P2 — re-verify the premise under `hooks.sessionStartNudge` (it was measured on a model that behaves differently now)

**What.** `sessionStartNudge` ships **default-on**, and `design-decisions.md` § "Proactive nudges via hooks (v1.1.1)" justifies it verbatim with: *"Descriptions get an agent to consider mnemo, but Opus 4.8 / Fable 5 under-trigger skills."* That premise was measured in July 2026 against the then-current flagship. It has not been re-measured since, and the flagship has changed — so a default-on behaviour now rests on an unverified condition.

**Why now.** The condition is **partially** inverted on the current flagship, and the inversion is narrower than it first looks — which is exactly why this needs a measurement rather than a guess:

- **Inverted, documented:** the vendor guide for the current Opus states it *"delegates to subagents more readily"* and *"verifies its own work without being told to"*. Under-triggering is not the failure mode there.
- **Unknown, NOT inverted:** the same guide is **silent about skills and file-based memory** — 0 occurrences of `skill` / file-based memory in its migration section, where the previous model's section named them explicitly. Silence is absent evidence, not evidence of the opposite.

So the honest state is: the premise is **stale for delegation** and **unmeasured for skill invocation** — and skill invocation is the only part mnemo's nudge actually addresses. Flipping the default off on the strength of the delegation finding would be reasoning past the evidence; leaving it on forever without a check is how a premise quietly rots.

**Minimal shape.** A small trigger-eval, not a redesign:

1. Fix a set of ~15-20 realistic prompts where `ask` / `save` *should* fire (mid-task recall, post-decision capture) and ~5 where they should not.
2. Run each twice on the current flagship — nudge on vs nudge off — counting invocations. No LLM judge; the invocation either happened or it did not.
3. Decide from the delta: lift → keep default-on and record the new measurement date; no lift → flip the default and keep the hook available opt-in.

**On-philosophy.** This is `harness.md`'s own rule applied to mnemo itself — *"прозаический always-on нудж = маржинальное правило ≈0 → ставить ТОЛЬКО после eval, доказавшего lift"*. The nudge was shipped on a documented model property rather than a local eval; this card is the eval that was owed. It also matches the read-side invariant this backlog's P1 card is about: a written fact is a claim with a date, and a default-on behaviour built on one deserves re-verification, not faith.

**Open questions.**
- **Cross-runtime split:** the nudge also serves Codex, and Codex's model is chosen per task — a result measured on one flagship does not transfer. Likely outcome is a per-runtime default rather than one global flag.
- **Scope of the flip, if any:** `sessionStartNudge` covers recall *and* capture. Over-triggering costs differ between them (a redundant `ask` is cheap; a redundant `save` writes a note), so the two may deserve separate verdicts.
- **Who owns the eval harness:** mnemo has no eval runner today. Smallest version is a scripted transcript-count, not new infrastructure.

**Origin.** Surfaced 2026-07-25 while auditing the maintainer's global rules against the new flagship's prompting guide: `~/.claude/rules/skill-design.md` carried the same premise and was dated in place rather than deleted, precisely because this decision stands on it. Explicitly **not** actioned in that pass — flipping a public cross-runtime default is a decision of its own, not a side effect of editing a rule file.

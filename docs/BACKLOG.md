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

## 🟠 P2 — oversize-note sensor: catch the atom that grew past atomic

**What.** mnemo enforces atomicity only at *create* time (`save` Step 0b: split, don't dump, claim-shaped title) and size-checks only one file afterwards — Claude's generated `MEMORY.md` index (`health` Step 10, `memory.indexWarnKB`). A vault note that grows past atomic *after* creation is invisible: nothing walks the vault for size. So the founding "one note = one claim" thesis is enforced at the door and never re-checked inside.

**Why now.** `save`'s append path *actively produces* this drift — every "update the existing note instead of creating a duplicate" adds bytes to a note whose title still promises one claim, and no check ever fires. The failure is silent and compounding: an oversized note is exactly the blob shape `design-decisions.md` rejects (unretrievable point-precisely — you cannot grab the right slice from it), and by the time a human notices, the split is expensive. Size here is a **structure** signal, never a brevity one: the fix is *split verbatim*, never trim — which is why this reinforces rather than contradicts `save`'s never-truncate rule.

**Minimal shape (report-only, no write, no flag).**

1. New deterministic `oversize` action in `scripts/safe-read.py`, mirroring the existing `missing-links` / `bad-filenames` passes: walk the vault's markdown files, compare `stat().st_size` against `health.oversizeKB * 1024`, return `[{path, sizeKb}]` most-oversize-first. Measure **bytes, not lines** — a single-line giant must not hide.
2. New report-only step in `health` (beside bad-filenames / review-candidates), plus one report block: `📏 Oversize (structure signal): N`, with the hint fixed to *split into domain note / event log / cluster, leave a one-line index — never trim*.
3. New `health.oversizeKB` in the config schema, default **25**, mirroring the existing `memory.indexWarnKB` (22) precedent.

**On-philosophy.** Report-only: it points at the gap and never authors, splits, moves, or trims anything — the same half-of-the-idea pattern already shipped for web-search imputation (declined as a writer, shipped as `health` research-gap candidates). No daemon, no index, no new skill, no folder semantics, so BYO-vault and the 7-skill canon both hold. It is the backstop to mnemo's own atomicity thesis rather than a new opinion about the user's vault.

**Open questions.**
- **Role-aware exemption is mandatory, or it nags.** Notes in the `session` role are governed by their own budget (`handoff.maxKB`) and `moc` hubs are legitimately large by design — both must be skipped. Route the exemption through `taxonomy_roles`, never through a title prefix or tag guess (a prefix is human-facing presentation, not routing).
- **Threshold realism:** 25 KB is inherited from a sibling constant, not measured against a mature vault. Worth sampling the size distribution of real fact-role notes before fixing the default.
- **Noise cap and ranking:** how many candidates per run before the check becomes the one users ignore.

**Origin.** Competitor audit of `breferrari/obsidian-mind`, 2026-07-24 — its `active-hygiene.ts` flags oversize at write time and `tidy-fix.ts` *acts* on it (`git mv`, split, relink). Only the scan half is vendored; the acting half is a non-goal here (it would author into the user's vault). Ranked the single highest value/effort item of that audit and confirmed twice by independent adversarial passes.

---

## 🟡 P3 — three small report-only detectors from the same audit (phantom edges, title clusters, claim grounding)

**What.** Three unrelated small gaps, grouped because each is a sub-day change in an existing skill and none justifies its own card:

1. **Ticket-ID phantom edges.** `health`'s research-gap step treats every unresolved wikilink as a missing note and can suggest *"create a hub for `[[BTS-250]]`?"* — the opposite of correct. A tracker ID is a plain-text reference, never a graph node; the right advice is *unlink*, not *create*. Fix is a classifier (`/^[A-Z]{2,10}-\d+$/`) over the already-computed top-unresolved list, filtering those targets out of the gap types and optionally reporting them as `🔗 phantom edges → unlink`. Pure prose, no new script, no flag.
2. **Title-token clusters with a document-frequency guard.** Today clustering keys on shared **tags** at a ≥5-note threshold; `connect` is semantic and heavier. Neither surfaces a *tag-free* cluster whose notes share a distinctive **title** token. The genuinely novel piece is the DF-guard — drop tokens appearing in more than half the notes — which is what keeps the suggestion from degenerating into noise. Suggest a hub note, never a folder.
3. **Claim grounding in `review`.** The verify pass grounds structural state (parked, connected, orphaned) but never the note's own *semantic* claims, so an overstating save ("tripled" when the source says doubled; "decided Monday" when it was Tuesday) passes green. Fix is a small claim taxonomy (number / timeline / attribution / comparison / characterization / day-of-week), grepping source-role notes per claim, emitting three buckets (verified / unverified-but-plausible / flagged with a suggested fix) into the existing residual-gap list. Every fix stays a suggestion — the step already contracts "report gaps, do not rewrite the user's notes".

**Why now.** Cheap, and #1 is a correctness fix rather than a feature: it removes an existing wrong suggestion instead of adding a right one. #3 protects the property the whole tool sells — recall you can trust — at the one moment the material is still verifiable.

**Minimal shape.** #1 is prose-only inside `health`. #2 is a ~40-line pure-string action (stopwords + title tokens + DF-guard + dedupe) over the note index `health` already builds. #3 is a `review` sub-check plus one bundled reference file holding the taxonomy.

**On-philosophy.** All three are report-only and additive to skills that already exist — no new skill (canon holds), no writes (non-destructive holds), no folder inference (routing stays role-based).

**Open questions.**
- **#2 scope:** a `floor(N/2)` DF-guard tuned on a tiny folder turns every two-note token into noise on a multi-thousand-note vault; scope to a recent window or to fact-role notes first.
- **#3 cost:** grounding is bounded by how much evidence lives in the vault versus the live conversation, and it adds latency to `--full`; may deserve an opt-in flag rather than always running.
- **#1 frequency:** tracker IDs appear more often as plain text than as wikilinks, so the trigger is occasional — the value is the corrected advice, not the hit rate.

**Origin.** Same competitor audit as the P2 card above (`breferrari/obsidian-mind`, 2026-07-24): #1 and #2 are the scan halves of its write-time validator and hygiene scanner, #3 is the vault-agnostic core of its review fact-checker with the career-vault folder assumptions stripped out.

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

---

## ⚪ P4 — story-first README with a demo recording (the repo half of distribution)

**What.** The README explains *what mnemo is* and lists what it does; it never *shows* the moment the tool pays for itself. There is no recording, no 30-second "this happened to me" scene, and no path for someone who does not already keep an Obsidian vault. A reader has to assemble the value proposition themselves from a feature list.

**Why now.** Measured against a competitor with the same tagline and ~3.8k stars: it wins on presentation, not on engineering — mnemo's non-destructive / BYO-vault / dual-runtime discipline is the stronger design. Its stars arrived as social-repost sustain (a large tech channel), **not** from Hacker News, which ignored it. That inverts the usual instinct: the lever is a scene a reader can retell, not another feature or a better ranking. The scene mnemo already owns is sharper than the competitor's file-tidying demo — *the agent stops you before you re-fix a bug you already fixed three sessions ago* — and today nothing anywhere demonstrates it.

**Minimal shape.**

1. One 15-30s asciinema/GIF of the recall-before-repeat moment, embedded at the top of the README.
2. A short scene above the feature list: the problem, the one command, the save that pays off next session.
3. A quickstart for the no-vault-yet reader — the current on-ramp assumes a mature vault plus a config.
4. ~~A Russian README~~ — already shipped: `README.md` carries full Russian (`## Что делает`) and Chinese (`## 功能介绍`) sections. What is still missing is the demo recording and the no-vault quickstart above.

**On-philosophy.** Presentation only — nothing here changes routing, defaults, or write behaviour. The explicit anti-goal is the tempting inverse: **do not add aggressive auto-capture to make the demo flashier.** Non-destructive is the differentiator being advertised; sacrificing it for a better GIF would sell something mnemo is not. The demo must be of the shipped default install, not of a flag nobody enables.

**Open questions.**
- **Which scene records best:** recall-before-repeat is the strongest claim but takes two sessions to stage honestly; a single-session cut risks implying an instant payoff the tool does not promise.
- **Recording format:** asciinema (small, copy-pasteable, terminal-only) vs GIF (renders on every surface, heavy). The competitor's ~4 MB GIF sits in-repo — a cost worth deciding deliberately.
- **Scope of a second language:** a translated README is easy to add and easy to let rot; a stale translation is worse than none, so it needs an owner or a generation step.

**Origin.** Competitor-distribution analysis, 2026-07-27, alongside the audit that produced the P2/P3 cards above. Filed at P4 deliberately: it is the highest-leverage *growth* work and the lowest-priority *product* work, and it should not displace correctness items. The rest of that analysis (channels, launch timing, positioning) is not repo work and lives in the maintainer's agent knowledge base.

---

## ⚪ P4 — `PreCompact` as a second leg for `autocompactNudge`

**What.** `hooks.autocompactNudge` (v1.2.14) warns *before* Claude Code compacts by predicting the moment from token usage and a resolved window. Claude Code also emits a **native `PreCompact` event** (matchers `auto` / `manual`) that fires deterministically at the actual moment, and a hook there can even block the compaction. mnemo does not use it at all — `PreCompact` appears exactly once in the repo, as a list item inside `scripts/lint-skills.py`'s set of valid event names.

**Why it was not simply used instead.** The two are not interchangeable, and the difference is the whole reason a predictor exists. At `PreCompact` time the agent is **not running**, so the hook cannot invoke `/mn:review --full` — it can only write a file or refuse the compaction. The Stop-hook predictor fires while the agent can still act, which is the entire point of the nudge: close the session out *before* the raw context is gone.

**Minimal shape, if picked up.**

1. `PreCompact` writes a small deterministic snapshot (open tails, last-turn usage, `session_id`) to the private cache.
2. `SessionStart` with the `compact` source re-injects a one-line pointer to it, so the post-compaction agent knows what it just lost and can still write the session note.
3. The existing Stop-hook nudge stays as the "warn while you can still act" leg. Two legs, different jobs — not a replacement.

**Why this is a card and not a fix.** Adding it means a new always-on write path on an event that fires for *every* user with autocompact on, including those who never enabled the nudge. That is a bigger posture change than the opt-in blocking hook, and it deserves its own decision rather than arriving as a side effect. Filed so the option is visible instead of being re-proposed as a novelty by the next session that reads `design-decisions.md`.

**Adjacent, cheap, unowned — done in v1.2.17.** This card used to note that `scripts/lint-skills.py` flagged no `[[wikilink]]` anywhere. It does now: see the private-leak guard and `scripts/test-lint-wikilinks.py`. It turned out not to be the one-line rule this card predicted — a repo *about* Obsidian is full of legitimate examples, so the guard passes shapes that cannot name a real note and keeps an explicit allowlist for the rest.

**Origin.** Adversarial review of PR #39 (autocompact nudge), 2026-08-20 — the reviewer proposed `PreCompact` as a possible replacement; it was deliberately not implemented in that pass and the reasoning above is the record of why.

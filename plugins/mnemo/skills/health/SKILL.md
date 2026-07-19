---
name: health
description: "Vault health audit — orphans, broken links, type-aware stale-review candidates, growth stats. Use whenever the user mentions vault maintenance, orphans, broken links, 'is my vault clean', 'проверь vault', 'сироты', 'битые ссылки', 'здоровье базы знаний', 'здоровье памяти', 'здоровье обсидиана', or asks for vault statistics — or proactively after creating 3+ notes in a session, after mass note creation, or when health checks haven't run in a while; the longer between checks, the more invisible orphans accumulate."
model: haiku
context: fork
---

# mn:health — Vault Health Check & Analytics

> **Invocation marker (both runtimes):** begin your reply with the exact line `🧠 mn:health (mnemo) → running` — the user-visible confirmation that this skill actually loaded. Emit it once per invocation, before any other output.

## Portable paths

Resolve `<mnemo-root>` once to the absolute plugin root before reading bundled files or running bundled scripts. In Claude Code, use `${CLAUDE_PLUGIN_ROOT}`; in Codex, derive it from this loaded `SKILL.md` path (skill directory → `skills/` → plugin root). Replace `<mnemo-root>` with that quoted absolute path in every command — never execute the placeholder literally and never hunt versioned cache directories.

When another mnemo skill must run, use the runtime-native path: Claude Code invokes `mn:<skill>` through its Skill tool; Codex reads `<mnemo-root>/skills/<skill>/SKILL.md` completely and follows it with the prepared input. For user-facing explicit syntax, render `/mn:<skill>` in Claude Code and `$mnemo:<skill>` in Codex.

Run a comprehensive health check on the Obsidian vault: orphans, broken links, missing sections, stale notes, and growth statistics.

## Prerequisites & config

Obsidian must be open; `obsidian` CLI on PATH. Config at `~/.mnemo/config.json` (required fields: `vault`, `taxonomy`, `links_section`) — schema in `<mnemo-root>/references/config-schema.md`.

## Workflow

**Steps 1-4 run in parallel** — single assistant message batching the independent indexed reads (orphans, unresolved, tag counts; Step 4 reuses Step 3's tag output, no extra call). Use the bundled shell-free helper with quoted JSON heredocs for every dynamic value. These queries take ~180ms total vs ~720ms sequential.

### Step 0: claude-mem Sanity Check (optional, ~20ms)

**Claude Code only.** In Codex, skip this step and omit the `⚠️ claude-mem` report line — do not inspect another runtime's plugin cache. In Claude Code, surface two common gotchas if claude-mem is installed and enabled. If `cascade.claude_mem.enabled` is false, skip this section silently — many users intentionally disable claude-mem for CPU/RAM reasons.

```bash
bash "<mnemo-root>/scripts/check-cm-version.sh"
# Or from source: plugins/mnemo/scripts/check-cm-version.sh
```

Script emits three lines: `version: X`, `stale: N`, `path: ...`. Interpret:

- `stale > 0` → warn: "claude-mem has {stale} old version folder(s) cached. Restart all Claude windows — old Stop hooks point to a path that no longer exists."
- `version < 12` → warn: "claude-mem v{version} is behind v12 — you're missing file-read gate, tier routing, and knowledge agents. Run `/plugin update claude-mem`."
- Empty path → claude-mem not installed. Skip the section entirely.

### Step 0.5: Cross-runtime Recall Status (conditional, read-only)

When `recall.runtimeMemory.enabled` is `true`, report whether the other runtime's project memory can be mapped safely. Run only the helper's metadata-only status probe; do not read or summarize counterpart memory content during a health audit:

```bash
python3 "<mnemo-root>/scripts/runtime-memory.py" status <<'JSON'
{"runtime":"{claude|codex}"}
JSON
```

Pass the active runtime. `available` means the helper proved an exact same-repository mapping; `unavailable` is not corruption and must not trigger repair, copying, broad scans, or claude-mem startup. Omit the report line when the feature is disabled.

### Step 1: Orphan Detection

```bash
python3 "<mnemo-root>/scripts/safe-read.py" orphans <<'JSON'
{"vault":"{vault}"}
JSON
```

List notes with zero backlinks. These are invisible in Graph View.

### Step 2: Unresolved Links (Ghost Notes)

```bash
python3 "<mnemo-root>/scripts/safe-read.py" unresolved <<'JSON'
{"vault":"{vault}"}
JSON
```

Show `[[wikilinks]]` pointing to non-existent files. Ghost notes are NORMAL (entity discovery) — don't flag on raw count alone.

**Actionable — top unresolved targets = missing hub notes** (via `obsidian eval`, authoritative; CLI `unresolved` can lag/lie — see `<mnemo-root>/references/gotchas.md`):

```bash
python3 "<mnemo-root>/scripts/safe-read.py" top-unresolved <<'JSON'
{"vault":"{vault}"}
JSON
```

A short name with many refs (e.g. `[[Diadoc]]` ×30) = create a hub note `Diadoc.md` → `[[MOC — …]]` so all those links resolve (alias doesn't work for bare links — by design).

### Step 3: Tag Distribution

```bash
python3 "<mnemo-root>/scripts/safe-read.py" tags <<'JSON'
{"vault":"{vault}"}
JSON
```

Show top 15 tags. Flag tags used only once (potential typos).

### Step 4: Notes by Type

**Reuse the `obsidian tags counts` output from Step 3 — do not call it again** (the tag index is one query; Steps 3 and 4 are two views of the same result). From it, extract counts for taxonomy tags: `#atom`, `#molecule`, `#source`, `#session`, `#moc`. These correspond to `config.taxonomy.*.tag` values.

Total notes count:

```bash
python3 "<mnemo-root>/scripts/safe-read.py" files-total <<'JSON'
{"vault":"{vault}"}
JSON
```

### Step 5: Missing Links Section (batched grep — 3600x faster)

**Do NOT loop `obsidian read` per file** — on a 1000-note vault that's ~180s. Use the helper's single filesystem pass.

```bash
python3 "<mnemo-root>/scripts/safe-read.py" missing-links <<'JSON'
{"vault":"{vault}","links_section":"{links_section}","prefixes":["Atom — ","Molecule — ","Source — ","Session — ","MOC — "]}
JSON
```

Replace the sample `prefixes` array with **every configured taxonomy prefix** from `config.taxonomy`; do not silently omit a custom note type.

**Measured on 999-note vault: ~49ms vs ~180s serial** — 3600x speedup. Safe to run always.

Report notes missing the section.

### Step 6: Bad Filenames (`#` in names → permanent orphans)

```bash
python3 "<mnemo-root>/scripts/safe-read.py" bad-filenames <<'JSON'
{"vault":"{vault}"}
JSON
```

Files with `#` in the name are **permanent orphans** — `[[Note #1]]` parses as `[[Note]]` + heading anchor `#1`, so nothing resolves to them (even existing links). Flag for rename (`#` → `—` or drop the `#`). Same for `.` mid-name (breaks CLI create). See `<mnemo-root>/references/tool-routing.md` (naming rules).

### Step 7: Review Candidates (content-staleness, type-aware)

A *temporal* signal, distinct from orphans (Step 1, which is *structural*): notes untouched longer than the threshold **for their type** are candidates for a re-read. Threshold precedence: per-note `ttl: <days>` → `review.staleDays.<type>` → `review.staleDays.default` → `30` (legacy). Age is measured from the newest of `date` or `reviewed` — so stamping `reviewed: {today}` on a still-valid note **resets its clock**. That snooze is what stops a stale list from rotting into guilt-debt (the canonical failure mode of review dates — see Gotchas).

```bash
python3 "<mnemo-root>/scripts/safe-read.py" review-candidates <<'JSON'
{"vault":"{vault}","limit":30}
JSON
```

Output: `CANDIDATES\t{n}`, then `THRESHOLDS\t{json}`, then one tab-separated row per note (`{overdue_days}  {type}  {anchor_date}  {anchor_src}  {threshold_days}  {relpath}`), most-overdue first. `{threshold_days}` is the budget actually applied to that note (per-note `ttl:` if set, else its type's `staleDays`, else default) — show it as `(type, Nd budget)`, never invent a `ttl`. Pure filesystem — independent of the obsidian CLI graph cache (no lag/lie risk). A missing `review` config section reproduces the legacy uniform 30-day behavior, so this is safe before any config migration.

Don't AND this with backlinks — a well-linked note can still hold outdated claims. Report candidates on their own; cross-reference Step 1 yourself if you specifically want "old **and** orphaned."

### Step 7.5: Content Lint (optional deep pass — gated by `review.lint.enabled`)

Steps 1-7 are cheap and structural. This is the **content** pass — Karpathy's "lint": actually re-read the notes to judge whether claims have rotted, instead of trusting the calendar. Together the checks cover his four: orphans (Step 1) + concepts-mentioned-but-no-page (Step 2 unresolved links) + stale claims (Step 7) + **contradictions** (here). Gated by `config.json` → `review.lint.enabled` (default **false**) because it reads note bodies and costs tokens — **skip this step silently when disabled**.

When enabled, take the top `review.lint.maxCandidates` (default **15**) candidates from Step 7 and have them read & judged on the model set by `config.json` → `review.lint.model` (default **`haiku`**; `sonnet`/`opus` for higher-quality verdicts). This health skill itself runs as a `haiku` fork and **cannot upgrade its own model**, so:

- If `review.lint.model` is `haiku` (or unset) → do the lint inline in this fork.
- Otherwise → **spawn one subagent** on `model: {review.lint.model}` (Claude Code: Task tool, `subagent_type: Explore` or general; Codex: `spawn_agent`) that reads the candidate note bodies in **one batched pass** (filesystem read, not one `obsidian read` per file) and returns the verdicts. Keeping the cheap Steps 1-7 on `haiku` while the lint runs on `opus` is the whole point of the split.
  - **Report the subagent's verdicts verbatim — never assume "all still-valid".** The fork only *aggregates* what the subagent returned; it does not re-judge. The Step 9 Content-lint block and its count MUST reflect the subagent's actual breakdown: if the subagent returned 13 still-valid + 2 update-needed out of 15, the report says `13 still-valid, 2 update-needed`, NOT `15 still-valid`. Defaulting the count to the candidate total (as if everything passed) is a reporting bug — wait for the subagent's verdicts before writing the report.

Emit a verdict per candidate:

- **still-valid** → close the loop: stamp `reviewed: {today}` into the note's frontmatter via `mcp__obsidian__str_replace` — anchor on the **frontmatter** line inside the leading `---` block (not a `date:`/`reviewed:` mention in the body): replace the existing `reviewed:` value, or if absent insert after `date:` (`date: {d}` → `date: {d}\nreviewed: {today}`). A confirmed-valid note then stops resurfacing without a manual edit. This auto-stamp is **on by default** (`config.json` → `review.lint.autoStampReviewed`, default **true**); **only if the user set it to `false`** do you just *recommend* the stamp and write nothing. When the lint runs in a spawned subagent (model ≠ haiku), that subagent does the stamping — it already holds the verdict and the note path. If a stamp write fails (Obsidian offline, or `mcp__obsidian__str_replace` unavailable in the subagent context), don't drop it silently — collect those note paths and surface them under the Content lint report block so the user can stamp them manually.
- **update-needed** → one line on what specifically looks outdated.
- **contradicts [[Other Note]]** → name the conflicting note; flag the *older* one against the newer.

Verdicts are **triage, not truth** — on `haiku` especially, expect false positives; even on `opus`, surface them as questions. The **only** write health ever performs is the `reviewed:` auto-stamp above, and only ever on a **still-valid** verdict — never content, never on update-needed/contradicts. It fires only inside this lint pass (which is itself off unless `review.lint.enabled` is true), and can be turned back to suggest-only with `autoStampReviewed: false`. The user stays in control.

### Step 8: Top Hubs

Enumerate the MOC notes (by the `moc` taxonomy prefix), then count backlinks for each:

```bash
python3 "<mnemo-root>/scripts/safe-read.py" moc-names <<'JSON'
{"vault":"{vault}","prefix":"{moc_prefix}"}
JSON
```

For each enumerated MOC name, count backlinks:

```bash
python3 "<mnemo-root>/scripts/safe-read.py" backlinks <<'JSON'
{"file":"{moc_name}","vault":"{vault}"}
JSON
```

Sort by count, show top 5. **Keep the enumerated MOC-name list** — Step 8.5 reuses it to find topics that have no MOC.

### Step 8.5: Research-Gap Candidates (report-only — where the vault wants to grow)

Karpathy's lint also proposes *what to research next*. Steps 1-8 already collected the raw signal — turn it into growth suggestions **without any new CLI calls** (reuse Step 2's `obsidian eval` top-10 unresolved targets, Step 3/4's tag counts, and the MOC-name list enumerated in Step 8). Two cheap, computable gap types:

- **Topic cluster with no MOC** — a non-taxonomy topic tag with **≥5 notes** (Milo's "mental squeeze point", the same trigger `config-schema.md` uses for creating a MOC) whose `{moc_prefix}{Topic}` is **absent from Step 8's enumerated MOC-name list**. Suggest: "12 notes tagged `#auth`, no MOC → create `MOC — Auth`?"
- **Recurring external with no Source note** — a top unresolved target from **Step 2's `obsidian eval` list** (the authoritative metadataCache top-10, not the CLI `unresolved` output) cited **≥5 times** that reads like an external tool/paper/vendor (not a short *project* name, which instead wants a hub note) and has no `Source — …` note. Suggest: "`[[LangGraph]]` cited ×9, no Source note → capture one?"

These are **suggestions, never auto-created** (same non-destructive stance as the rest of health). Skip a type silently when it yields nothing. Do **not** web-search to fill the gap — mnemo maintains a human-authored vault: it points at the gap, the user decides whether to fill it. (This is the on-philosophy half of Karpathy's "suggest new article candidates"; the auto-web-imputation half is deliberately omitted.)

### Step 9: Output Report

```
📊 Vault Health Report ({date})

⚠️ claude-mem: {warning or "v12.3.9, clean"}
🔄 Cross-runtime recall: {Claude memory available | Codex memory available | enabled, counterpart unavailable ({reason})}

Total: {N} notes
  Atoms: {N} | Molecules: {N} | Sources: {N}
  Sessions: {N} | MOCs: {N} | Other: {N}

🔴 Orphans: {N}
  - Note Name 1
  - Note Name 2

🟡 Missing {links_section}: {N}
  - Note Name 1

🚫 Bad filenames (`#`/`.`): {N} — permanent broken links, rename
  - Atom — Foo (PR #12)  → rename to "PR 12"

🔍 Top unresolved targets (missing hub notes?):
  1. [[Diadoc]] ×34 → create hub note?
  2. [[Python]] ×28

🔗 Unresolved wikilinks: {N} total
📏 Tags: {N} total, {N} used once

🏆 Top-5 Hubs (most backlinks):
  1. MOC — Security (34)
  2. MOC — AI ML Tools (28)
  ...

💤 Review candidates (stale by type-aware age): {N}
  - Atom — API X gotcha — 45d overdue (atom, 60d budget)
  - Source — vendor API pricing — 35d overdue (source, 180d budget)
  (snooze a still-valid note: add `reviewed: {today}` to its frontmatter)

🔬 Content lint: {N judged} — {S} still-valid, {U} update-needed, {C} contradicts   ← only when review.lint.enabled
  (counts MUST equal the lint's actual verdicts — never default to all-still-valid; see Step 7.5)
  - Atom — API X gotcha → UPDATE-NEEDED: superseded by [[Atom — API X v2]]
  - Source — vendor API pricing → still-valid (stamped reviewed: {today})

🌱 Research-gap candidates (where the vault wants to grow): {N}
  - #auth ×12 notes, no MOC → create MOC — Auth?
  - [[LangGraph]] ×9, no Source note → capture one?

🧠 Claude memory/ index: {KB}KB / {lines} lines {✅ lean | ⚠️ bloated → autodream}
```

Omit the `🔬 Content lint` block entirely when `review.lint.enabled` is false. Omit the `🌱 Research-gap candidates` block when Step 8.5 found nothing. The still-valid line above shows the default (`autoStampReviewed: true` — the note was stamped); with `autoStampReviewed: false` render it as `→ still-valid (recommend reviewed: {today})` instead, since nothing was written.

Both Claude-specific lines are conditional: skip the `⚠️ claude-mem` line if Step 0 found nothing to warn about, and omit **both** it and the `🧠 Claude memory/ index` line entirely in Codex. The `🔄 Cross-runtime recall` line is runtime-neutral and appears only when Step 0.5 says the opt-in feature is enabled.

### Step 10: Claude memory/ index health (autodream check)

**Claude Code only.** In Codex, skip this step and omit its report line; never scan `~/.claude/projects/` broadly as a proxy for Codex memory. Step 0.5 may verify one exact counterpart mapping without reading memory content, but Codex local memory lives under `~/.codex/memories/`, is not governed by Claude's auto-memory truncation behavior, and remains outside this size audit.

In Claude Code, separate from the Obsidian vault, an **always-loaded** index lives at `memory/MEMORY.md`. Claude Code auto-memory **hard-truncates this index at ~24.4 KB on load** — beyond that, trailing rows silently vanish from Claude's context. So warn *early* (before the cliff), not at some lax size. Threshold is configurable via `config.json` → `memory.indexWarnKB` (default **22**):

```bash
WARN=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.mnemo/config.json'))).get('memory',{}).get('indexWarnKB',22))" 2>/dev/null || echo 22)
for f in "$HOME"/.claude/projects/-*/memory/MEMORY.md; do
  [ -f "$f" ] || continue
  kb=$(( $(wc -c < "$f") / 1024 )); ln=$(wc -l < "$f")
  [ "$kb" -gt "$WARN" ] && echo "⚠️ $(basename "$(dirname "$(dirname "$f")")"): ${kb}KB / ${ln} lines — >${WARN}KB warn (auto-memory truncates ~24.4KB) → run autodream (move sessions → MEMORY-archive-index.md, target <20KB)"
done
```

If flagged → recommend **autodream** (memory consolidation): slim the index into topic files + `MEMORY-archive-index.md`, **no loss**. Procedure: `~/.claude/memory/autodream-principles.md`. This is the only `memory/` check here — health otherwise audits Obsidian, not Claude's memory/.

## Gotchas

Common failures in `<mnemo-root>/references/gotchas.md`. Skill-specific rules:

- `obsidian orphans` may return empty on small vaults — this is OK, not an error.
- Reference notes (taxonomy docs, templates) aren't orphans even if few backlinks — they're meant to be lookups.
- Ghost notes (unresolved wikilinks) are a **feature**, not a bug — they enable entity discovery. Don't flag on raw count; instead surface the **top targets** (Step 2 eval) — frequent ones = missing hub notes (actionable).
- **CLI graph queries cache & can lie** — `orphans`/`unresolved`/`backlinks` lag writes and have shown a note as resolved AND broken at once. For critical checks use `obsidian eval` on `metadataCache` (see `<mnemo-root>/references/gotchas.md`). Treat counts as advisory if notes were created this session.
- **Do not auto-fix anything** — only report. User decides what to clean up. The **one** exception is `review.lint.autoStampReviewed` (default **true**): it lets the content-lint stamp `reviewed: {today}` on a **still-valid** note (Step 7.5) to close the snooze loop. That is the sole frontmatter write health can make — only the `reviewed:` field of a confirmed-valid note, never content, never anything else. It fires **only when the content lint itself is enabled** (`review.lint.enabled`, default **false**), so a default install still writes nothing; set `autoStampReviewed: false` to keep the lint suggest-only.
- **Counterpart unavailable is informational** — Step 0.5 is a bounded status probe, not a repair trigger. Never infer another project, start a daemon, create a symlink, or copy runtime memory to make it pass.
- Step 5 uses filesystem grep (~3600x faster than per-file reads — 49ms vs 180s on a 999-note vault) — safe on any vault size.
- **Review candidates (Step 7) are temporal, not structural** — don't conflate with orphans. A note can be both, either, or neither. The script is age-only by design (cheap, no graph dependency).
- **Content-lint verdicts (Step 7.5) are triage-grade** — time-based staleness is a *proxy*, not the signal (a 6-month-old note may be perfectly valid; "not read ≠ not valuable"). On `haiku` especially, contradiction/update calls have false positives. Surface them as questions, never as facts, and never act on them automatically. The whole point of `reviewed:` is to let a quick human confirm and silence a false flag.

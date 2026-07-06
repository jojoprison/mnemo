# Vault conventions for an AI-agent-maintained vault

Verified best practices (Obsidian official Help + Steph Ango/kepano, the Obsidian CEO + PKM canon; deep-research 2026-07-06, 20/25 claims confirmed). Apply whenever mnemo reads or writes notes. Reuse what Obsidian ships — don't reinvent.

## 1. Load-bearing links go OUTSIDE code fences
Links inside ` ``` ` code blocks are NOT parsed into the graph (by design) — they never appear under Links/Backlinks. Agents emit fenced blocks constantly, so a `[[link]]` placed in one is silently lost to graph retrieval. Keep any link that must be navigable in prose, not in a code block. (Source: obsidian.md/help/plugins/outgoing-links — verbatim: "links don't show up under the Links section".)

## 2. Compute indexes with Bases — don't hand-maintain them
Dashboards / "what's live" / per-topic lists should be COMPUTED from typed Properties via **Bases** (core plugin since v1.9) — a `.base` file or an embedded ` ```base ` block filtering on `type` / `status` / `date` / `tags`. A hand-maintained index note drifts and bloats into a store (the handoff / fat-MOC anti-pattern). This is how the Obsidian CEO organizes his own vault (a multi-valued property surfaced via Bases, not folders). Prefer adding a Base over growing a MOC past ~a screenful. Scale gotcha: `file.backlinks` is performance-heavy and does not auto-refresh — reverse the lookup and use `file.links`. (Source: obsidian.md/help/bases, obsidian.md/help/bases/syntax, stephango.com/vault.)

## 3. Property schema is self-policed
Obsidian does NOT globally enforce property types — the same property name can carry different types across notes (the "types are globally enforced" claim was refuted 0-3). A Base is only as good as the schema beneath it, so keep `type` / `tags` / `date` / `status` / `cites` consistent yourself.

## 4. Concurrent human + agent edits have NO native safety
Obsidian file-sync does not resolve merge conflicts when a human and an agent edit the same note (the "safe without merge-conflict resolution" claim was refuted 0-3). Never blind-overwrite a note you did not just read — use a targeted `mcp__obsidian__str_replace` on a verbatim anchor (or per-note / per-section ownership), and re-read before editing a note another party may have touched.

## Already-correct baseline (keep, don't churn)
Atomic notes + `[[wikilinks]]` + a `## Links` / `## Связи` section + MOCs + near-flat root + typed Properties + **File Recovery** (the only local undo when the vault is not a git repo — keep it enabled) — all verified-canonical (kepano, Zettelkasten, LYT). Retrieve via quick switcher / backlinks / links, not folder trees. Quick switcher degrades past ~10,000 vault items; single-file editor lag starts ~0.5–1 MB — split with Note composer before then.

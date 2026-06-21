# Tool Routing — MCP-first hybrid

Rule of thumb: **any write with markdown body → MCP; everything else → CLI.**

## Routing table

| Operation | Tool | Why |
|-----------|------|-----|
| **Create note** (arbitrary markdown) | `mcp__obsidian__create` | Shell-safe — content passes as JSON parameter, no zsh expansion |
| **Edit middle of file** | `mcp__obsidian__str_replace` | Exact-match replace, shell-safe |
| **Insert at line** | `mcp__obsidian__insert` | Line-number-based, shell-safe |
| **View file** | `mcp__obsidian__view` or CLI `obsidian read` | Both work; CLI is ~180ms, MCP similar |
| **Search (fulltext)** | CLI `obsidian search` | **Only CLI has this** — indexed, ~175ms, not available in MCP |
| **Orphans / backlinks / tags / unresolved** | CLI `obsidian orphans` / `backlinks` / etc. | **Only CLI has these** — indexed graph queries. ⚠️ cache lags writes 1-5s & can give false positives — for critical checks use `obsidian eval` on `metadataCache` (see gotchas) |
| **Vault metadata** | CLI `obsidian vault` | Returns filesystem path, file count, size |
| **List files** | CLI `obsidian files` | Indexed |
| **Append plain wikilink** (no backticks) | CLI `obsidian append content="- [[Name]]"` | Safe — no backticks means no shell expansion |
| **Append with markdown body** | `mcp__obsidian__str_replace` or temp-file + CLI | CLI with inline content is unsafe |
| **Delete** | CLI `obsidian delete` | No content arg, safe |
| **Arbitrary JS** | `mcp__obsidian__obsidian_api` or CLI `obsidian eval` | Both work |

## Why CLI-first for read / search / index

| Operation | CLI (ms) | MCP (ms) | Notes |
|-----------|----------|----------|-------|
| search | ~175 | N/A | Only CLI — kepano benchmarked 70,000x cheaper than scanning |
| read | ~185 | ~150-200 | Similar; CLI avoids MCP handshake |
| orphans / backlinks | ~180 | N/A | Only CLI |
| tags / files | ~180 | N/A | Only CLI |
| create | ~180 (cold node start) | ~30-50 | MCP wins when you're creating content |

## Why MCP-first for writes with markdown

CLI `obsidian create content="..."` is executed inside a zsh double-quoted context. That means:

- **Backticks** `` `cmd` `` → shell runs `cmd`, substitutes output.
- **`$(cmd)`** → same, command substitution.
- **`$VAR`** → variable expansion.

A markdown code block inside the content is an **exploit** in disguise:

````
```bash
make deploy-back
```
````

If that string ends up in `content="..."`, zsh runs `make deploy-back`. This really happened on 2026-04-21 — session note content triggered accidental prod deploy.

**MCP has no shell.** Content flows as a JSON string to the MCP server → Obsidian's internal API → disk. Backticks and `$(...)` are preserved verbatim, treated as text.

## When CLI append is safe

Plain wikilink appends (no backticks, no `$()`):

```bash
obsidian append file="MOC — Memory Systems" vault="main" \
  content="- [[Atom — New Note]]"
```

This is how skills add MOC entries. It's fast, indexed, and bulletproof when the content is literally just `- [[Name]]`.

Anything with code blocks or shell metacharacters → switch to MCP `str_replace` or `insert`.

## Referencing memory/ files (never wikilink them)

`memory/` files (Claude's cross-session error-prevention notes) are **not** part of the Obsidian vault graph. A `[[memory/foo]]` or `[[foo.md]]` link from inside a note never resolves — it becomes a phantom ghost that pollutes `orphans`/`unresolved` reports forever.

- **Reference as inline code** — `` `memory/foo.md` `` — keeps the pointer, no broken link.
- **If a real vault note covers the same topic** (a MOC or Atom), link THAT instead — strengthens the graph rather than dangling.
- **Same for project files** (`CLAUDE.md`, `AGENTS.md`, `TECH_DEBT_AUDIT.md`): inline code, not `[[wikilink]]`.

The failure mode is silent: `obsidian create`/`str_replace` happily writes the broken link, and it only surfaces later as an orphan/unresolved entry. Get it right at write time.

## Note naming rules (enforce BEFORE create — violations create permanent orphans)

Obsidian/CLI break on certain chars in filenames. Check every note name before `create`:

| Char | Effect | Rule |
|------|--------|------|
| `#` | Breaks wikilink — `[[Note #1]]` parses as `[[Note]]` + heading anchor `#1` → note becomes an unreachable orphan, even existing links to it | **Never** in names |
| `.` (mid-name) | CLI `obsidian create` truncates the name at the dot (treats tail as extension) | **Never** except the auto `.md` |
| `/` | Path separator — creates a subfolder instead of the note | **Never** in names |
| `.md` (in name arg) | Double extension, breaks resolution | Omit — added automatically |

Use `—` (em-dash) or a space instead. Real incident 2026-05-26: 56 notes with `(PR #NNN)` / `VPS#1` were silent orphans — their `[[…#NNN]]` links never resolved; had to rename all.

## Hub notes — making short `[[Name]]` resolve

Obsidian's resolver **ignores frontmatter `aliases` for bare `[[Name]]` links — BY DESIGN** (not a bug / version / cache). `[[Diadoc]]` will NOT find `MOC — BTS Diadoc.md` via `aliases: [Diadoc]`. Only the pipe form `[[MOC — BTS Diadoc|Diadoc]]` (inserted via `[[` autocomplete) resolves through an alias.

**Pattern (canon: Luhmann *register note* / Milo *home note* / Obsidian *hub note*):** create a real file named with the short name — `Diadoc.md` — whose body redirects to the MOC:

```
# Diadoc
→ [[MOC — BTS Diadoc]]
## Связи
- [[MOC — BTS Diadoc]]
```

Now `[[Diadoc]]` resolves everywhere by filename-match (100% reliable). Optionally add `aliases: [Diadoc, Диадок]` to the hub note itself — gives `[[` autocomplete + unlinked-mentions in the backlinks panel (the link still resolves by filename). Real incident 2026-05-26: `[[BTS Holding]]` (469 refs), `[[Diadoc]]` (246), `[[1С]]` (330) were all broken until hub notes were created.

**When:** `initial-setup` offers a project hub; `memory-routing` creates one when a `[[ShortName]]` is needed and none exists. Verify resolution with `obsidian eval` (`metadataCache`), NOT CLI `unresolved` (caches — see gotchas).

## Two link layers (Luhmann / Matuschak)

1. **Inline with context** — in the body, where the connection matters: «builds on [[Atom — X]] because…», «contradicts [[Atom — Y]]». The sentence carries the *why*. A bare `[[link]]` with no context is noise (zettelkasten.de: "state explicitly why you made the link").
2. **`{links_section}`** — bottom nav block: MOC + structural links, pure wikilinks (context lives inline).

For graph/backlinks the position doesn't matter (Obsidian parses the whole file), but inline context makes the graph semantically rich. Skills creating notes: always emit `{links_section}` (≥1 MOC link); for Atoms/Molecules that reference other notes — add inline context too.

## Reading order of preference

1. **Search / index query** → CLI (only option).
2. **Write with markdown body** → MCP (safety).
3. **Plain wikilink append** → CLI (faster, indexed).
4. **Targeted edit to existing note** → MCP `str_replace`.
5. **Read (for diff / context)** → CLI (warm index).

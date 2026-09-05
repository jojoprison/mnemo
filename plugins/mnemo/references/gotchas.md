# Shared Gotchas — mnemo skills

Common failure modes and their fixes. Any mnemo skill can reference this file instead of repeating the same block.

## Obsidian IPC hung — "Unable to connect to main process"

**Symptom:** `obsidian <anything>` returns `Error: Unable to connect to main process`.

**Cause:** Obsidian's CLI IPC socket crashed. The app might still look alive in the Dock but isn't accepting connections.

**Fix:**
1. Quit Obsidian fully: Cmd+Q (not just close the window).
2. Reopen Obsidian.
3. Wait ~3 seconds for the vault to finish indexing.
4. Retry the mnemo command.

## Obsidian must be open

All indexed reads and the bundled writer's vault-root lookup require the running Obsidian app. Skills don't probe for this on every step — they fail fast on the first IPC call and report any backend they had to skip. Claude Code may still save an error-prevention item to its enabled auto-memory or optional claude-mem; Codex does not fabricate a shadow copy in generated `${CODEX_HOME:-~/.codex}/memories/` state.

If a skill is supposed to only write (not search/read), check whether it can proceed offline: `save` and `save`-flavored skills degrade gracefully, search/connect/health skills can't.

## `/plugin update` — stale Stop hooks

After upgrading any plugin (claude-mem especially), already-open Claude Code windows continue to reference the OLD cache path:

```
Plugin directory does not exist: /Users/<you>/plugins/cache/thedotmack/claude-mem/10.5.2
```

**Why:** hook paths are captured at window-start time. Newer windows pick up the fresh version; older windows keep the stale path and fail on Stop.

**Fix:** close and reopen **all** Claude Code windows after any `/plugin install` or `/plugin update`. New windows inherit the updated `CLAUDE_PLUGIN_ROOT`.

Verify clean cache:
```bash
ls ~/.claude/plugins/cache/thedotmack/claude-mem/
# Should be ONE folder = current version. Multiple folders = restart windows.
```

## Shell injection via dynamic Obsidian CLI arguments

**Don't** pass generated markdown through `obsidian create content="..."` or `obsidian append content="..."` from Bash. Also don't paste a vault-derived note name, query, concept, prefix, or path into a read/index command. zsh expands backticks, `$()`, and variables inside generated double-quoted literals; a generated `"` can close the argument and expose shell separators. A real 2026-04-21 incident accidentally ran `make deploy-back` on production because a session note contained a bash code block.

**Use instead:**
- `<mnemo-root>/scripts/vault-write.py <<< '{…}'` for create/replace/insert/guarded append — content passes as JSON stdin, shell uninvolved, writes are optimistic and atomic
- `<mnemo-root>/scripts/safe-read.py ACTION <<< '{…}'` for dynamic reads/index queries — strict action allowlist + argv (`shell=False`) + safe JS literals

**Direct CLI is safe only when the entire command is a static, human-authored literal.** Canonical skills use `safe-read.py` even for `search`, `read`, `orphans`, `backlinks`, `tags`, and `vault`, because their vault/query/note arguments are dynamic. Generated wikilink appends go through `vault-write.py insert` or its guarded append action.

## A worktree-isolated session refuses heredocs — the input form is a herestring

**Symptom:** every bundled-script call dies with `This session is isolated in the worktree …, but this command is too complex to verify that it stays inside the worktree. Refusing to run it`. Nothing in mnemo works — not `ask`, not `save`, not `session` — and the message reads like a broken tool rather than a refused input form, so the fix is easy to look for in the wrong place.

**Cause:** Claude Code's worktree guard cannot statically prove a heredoc (`<<'JSON'`) stays inside the worktree, so it rejects the whole command. Measured 2026-09-04: it is the **heredoc specifically**, not multi-line commands — two `echo` lines in one call run fine, and the same payload piped in works. The guard rejects `python3 -c "…"` with a path built from a shell variable for the same reason.

**Canonical form — a single-quoted herestring:**

```bash
python3 "<mnemo-root>/scripts/safe-read.py" ACTION <<< '{"vault":"main"}'
```

One line, so the guard accepts it. Single quotes keep the shell out of the payload exactly as the quoted heredoc did — backticks, `$()` and quotes stay inert data. Prefer it over `echo '…' | python3 …`: `echo` in some shells interprets escape sequences, and `insert` payloads legitimately start with `\n`, which `echo` would turn into a real newline and corrupt the JSON.

**One limitation, and its workaround:** a single quote inside the payload closes the shell literal. JSON does not require escaping `'`, so a note named `Kate's plan` breaks the form. When a value contains `'`, write the JSON with the Write tool (no shell involved) and redirect the file in: `python3 script.py ACTION < /path/payload.json`.

## claude-mem worker not responding on 127.0.0.1:37777

`save` pings the local claude-mem worker when saving observations. If the port doesn't respond:

- **Most common cause:** claude-mem plugin isn't installed, or worker hasn't started yet after session boot (takes 5-10s).
- **Less common:** port collision. Reserved port per global CLAUDE.md — another process shouldn't be on 37777.

**Skill behavior:** log `⚠️ claude-mem: skipped (port 37777 not responding)` and continue with the other backends. Never fail the whole save.

## Runtime memory is NOT `./memory/`

Runtime-generated memory belongs to each runtime:

- Claude Code: the effective auto-memory directory (the documented `autoMemoryDirectory` override when configured, otherwise `${CLAUDE_CONFIG_DIR:-~/.claude}/projects/<verified-project>/memory/`). `save` may update it only when auto-memory is enabled.
- Codex: `${CODEX_HOME:-~/.codex}/memories/`. This is generated state; mnemo may read verified project-scoped groups for recall but must never create or edit it manually.

**Never** write to `./memory/` in the project root — that puts agent memory files into git. Never guess a Claude slug or use Codex generated memory as a fallback save surface.

## `vault-write.py` reports `vault_unavailable`

The writer resolves the named vault through the Obsidian CLI before opening it safely. Treat this like the CLI IPC failure above: restart Obsidian and retry. Do not bypass containment by guessing the vault path.

## CLI orphans / unresolved / backlinks cache lag — `eval` for truth

`obsidian orphans` / `unresolved` / `backlinks` read Obsidian's index, which **lags writes 1-5s** (longer on big vaults). Symptom: a note shows as resolved AND unresolved at once, or a freshly created note still appears as orphan, or alias/hub changes don't surface even after edits. Real incident 2026-05-26: CLI `unresolved` kept listing hubs as broken while `metadataCache` already resolved them.

**Authoritative check — `obsidian eval` on `metadataCache`:**

```bash
# Top broken targets:
python3 "<mnemo-root>/scripts/safe-read.py" top-unresolved <<< '{"vault":"main"}'

# Real backlink count for one note:
python3 "<mnemo-root>/scripts/safe-read.py" resolved-backlink-count <<< '{"target":"TARGET.md","vault":"main"}'
```

Treat CLI graph counts as **advisory** if notes were created/edited in the same session. `health` and `review` should prefer `eval` for critical resolution checks.

## Forbidden chars in note names (`#` `.` `/`)

`#` breaks wikilinks (parsed as a heading anchor → permanent orphan, even existing links to it), `.` truncates CLI `create` at the dot, `/` makes a subfolder. Full table + the hub-note fix → `references/tool-routing.md` ("Note naming rules" + "Hub notes"). Always sanitize a name before `create`. Incident 2026-05-26: 56 `#`-named notes were silent orphans.

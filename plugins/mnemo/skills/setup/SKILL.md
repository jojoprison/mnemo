---
name: setup
description: "Use on first install, when reconfiguring mnemo, or when the user says 'setup mnemo', 'mnemo not configured', 'change vault', 'reset config', 'мнемо настрой', 'настрой мнемо', or similar — also invoked automatically when any other mnemo skill detects a missing config. Interactive onboarding that creates ~/.mnemo/config.json (vault name, taxonomy, links-section language, cascade defaults)."
model: haiku
---

# mn:setup — Interactive Onboarding

> **Invocation marker (both runtimes):** begin your reply with the exact line `🧠 mn:setup (mnemo) → running` — the user-visible confirmation that this skill actually loaded. Emit it once per invocation, before any other output.

## Portable paths

Resolve `<mnemo-root>` once to the absolute plugin root before reading bundled files or running bundled scripts. In Claude Code, use `${CLAUDE_PLUGIN_ROOT}`; in Codex, derive it from this loaded `SKILL.md` path (skill directory → `skills/` → plugin root). Replace `<mnemo-root>` with that quoted absolute path in every command — never execute the placeholder literally and never hunt versioned cache directories.

When another mnemo skill must run, use the runtime-native path: Claude Code invokes `mn:<skill>` through its Skill tool; Codex reads `<mnemo-root>/skills/<skill>/SKILL.md` completely and follows it with the prepared input. For user-facing explicit syntax, render `/mn:<skill>` in Claude Code and `$mnemo:<skill>` in Codex.

First-time setup for mnemo. Creates config.json with all settings.

## Workflow

### Step 1: Welcome

```
🧠 Welcome to mnemo — persistent memory for Codex and Claude Code.

Let's set up your configuration. This takes about 30 seconds.
```

### Step 2: Vault Name

```
What's your Obsidian vault name?
(The name shown in Obsidian's vault switcher)
> main
```

Verify vault exists:
```bash
python3 "<mnemo-root>/scripts/safe-read.py" search <<'JSON'
{"query":"test","vault":"{input}"}
JSON
```

If error → "Vault not found. Is Obsidian open? Check the vault name."

### Step 3: Note Taxonomy

```
Which note taxonomy do you use?

[1] Atom/Molecule/Source/Session/MOC (Zettelkasten-inspired)
[2] PARA (Projects/Areas/Resources/Archive)
[3] Custom (you'll define prefixes and tags)

> 1
```

Map the selection to two adjacent config objects:

- `taxonomy` defines physical note types. Each entry is `{ "prefix": "…", "tag": "…" }`, and every prefix **must end in a filename-safe separator** such as ` — `, `: `, or ` - `. Never allow `/`, `#`, or `.` in a prefix.
- `taxonomy_roles` maps the stable semantic roles `fact`, `insight`, `source`, `session`, and `moc` to keys that exist in `taxonomy`. This is the only routing layer skills consume; never infer a destination from a display prefix or tag.

Always keep `session` and `moc` in `taxonomy` and map those two roles to themselves — they are *functional* types. The canonical workflows still resolve them through `taxonomy_roles.session` and `taxonomy_roles.moc`; they never bypass the role map.

**[1] Zettelkasten** — use the full blocks shown in Step 5 below. The role map is deterministic: `fact → atom`, `insight → molecule`, `source → source`, `session → session`, `moc → moc`.

**[2] PARA:**
```json
"taxonomy": {
  "project":  { "prefix": "Project — ",  "tag": "project" },
  "area":     { "prefix": "Area — ",     "tag": "area" },
  "resource": { "prefix": "Resource — ", "tag": "resource" },
  "archive":  { "prefix": "Archive — ",  "tag": "archive" },
  "session":  { "prefix": "Session — ",  "tag": "session" },
  "moc":      { "prefix": "MOC — ",      "tag": "moc" }
},
"taxonomy_roles": {
  "fact": "resource",
  "insight": "resource",
  "source": "resource",
  "session": "session",
  "moc": "moc"
}
```

PARA organizes by actionability rather than knowledge shape, so propose `resource` for the three durable-memory roles, show the mapping, and ask the user to confirm or choose a different existing PARA key for each role. Never silently guess `project` versus `area` from content.

**[3] Custom** — ask the user for each type's key + prefix + tag; enforce the separator rule on every prefix; still include `session` and `moc` (add them yourself if the user doesn't name them). Then show the final type keys and ask once which key receives each of `fact`, `insight`, and `source`; keep `session → session` and `moc → moc`. Reject a role target that is not an exact `taxonomy` key.

**Existing config migration:** preserve a `taxonomy_roles` object only when its key set is exactly `fact`, `insight`, `source`, `session`, and `moc`, every target is an existing taxonomy key, and `session → session` plus `moc → moc`. If it is absent and `taxonomy` contains the legacy Zettelkasten keys `atom`, `molecule`, `source`, `session`, and `moc`, add the deterministic [1] map without asking. For any other missing/invalid custom map, show the existing taxonomy keys and ask once for the three content-role targets; keep the functional self-maps, do not rename types, and do not guess from prefixes/tags. Preserve all unrelated config fields.

### Step 4: Links Section Name

```
What heading do you use for note cross-references?

[1] ## Связи (Russian)
[2] ## Links
[3] ## Related
[4] ## Connections
[5] Custom

> 1
```

### Step 4.5: Cross-runtime Recall (opt-in)

```
Let Codex read this project's Claude memory, and Claude read this project's Codex memory?

[1] No (default — Obsidian + the active runtime only)
[2] Yes (read-only, exact git-project match, no copying or syncing)

> 1
```

Map the choice to `recall.runtimeMemory.enabled`. This is intentionally **off by default** because runtime memory may contain agent-generated or sensitive local context. Enabling it adds a bounded read-only overlay to `ask`; it does not create symlinks, share writers, scan transcripts, or change where either runtime stores memory. `globalSources: "explicit"` still requires the user to ask for global/cross-project memory in that specific query.

### Step 5: Save Config

Write `~/.mnemo/config.json`:

```json
{
  "vault": "main",
  "taxonomy": {
    "atom": { "prefix": "Atom — ", "tag": "atom" },
    "molecule": { "prefix": "Molecule — ", "tag": "molecule" },
    "source": { "prefix": "Source — ", "tag": "source" },
    "session": { "prefix": "Session — ", "tag": "session" },
    "moc": { "prefix": "MOC — ", "tag": "moc" }
  },
  "taxonomy_roles": {
    "fact": "atom",
    "insight": "molecule",
    "source": "source",
    "session": "session",
    "moc": "moc"
  },
  "links_section": "## Связи",
  "handoff_note": "Meta — Session Handoff",
  "cascade": {
    "obsidian": { "enabled": true },
    "claude_mem": { "enabled": false, "url": "http://127.0.0.1:37777" },
    "memory_dir": { "enabled": true },
    "project_rules": { "enabled": true },
    "claude_md": { "enabled": false }
  },
  "recall": {
    "codeGraph": null,
    "runtimeMemory": {
      "enabled": false,
      "globalSources": "explicit",
      "maxHits": 5,
      "maxExcerptBytes": 12288
    }
  },
  "hooks": {
    "sessionStartNudge": true,
    "stopNudge": false,
    "invocationEcho": true
  }
}
```

`hooks.stopNudge` ships **false** — flip it to `true` if you want the end-of-session save/session reminder (see `<mnemo-root>/references/config-schema.md`). `hooks.invocationEcho` (Claude Code only, default true) prints a `🧠 mnemo: /mn:<skill> → skill body loaded` confirmation when a `/mn:*` command expands. Everything works on these defaults even if the whole `hooks` block is omitted.

Use the Step 4.5 answer for `recall.runtimeMemory.enabled`; the JSON above shows the safe default. If an existing config is being edited, preserve every unrelated field and change only the requested setting.

### Step 6: Create Handoff Note (only if missing)

First check — skip this step entirely if the handoff note already exists:

```bash
python3 "<mnemo-root>/scripts/safe-read.py" read <<'JSON'
{"file":"{handoff_note}","vault":"{vault}"}
JSON
```

If empty output, create through the bundled shell-free writer in either runtime:

```bash
python3 "<mnemo-root>/scripts/vault-write.py" <<'JSON'
{"action":"create","vault":"{vault}","note":"Meta — Session Handoff","content":"{one JSON-escaped Markdown string containing the meta frontmatter, Pending and Context sections, and setup date}"}
JSON
```

`create` is exclusive and atomic. If it reports `conflict`, re-read the note rather than overwriting it.

### Step 6.5: Project Hub Note (optional)

Offer: "Create a hub note for short-name navigation? E.g. `[[ProjectName]]` → its MOC."

**Why:** Obsidian's resolver ignores frontmatter `aliases` for bare `[[Name]]` links (by design) — only a real file named `ProjectName.md` makes `[[ProjectName]]` resolve. See `<mnemo-root>/references/tool-routing.md` ("Hub notes"). Without it, every short `[[ProjectName]]` reference is a broken ghost.

If user confirms, resolve `taxonomy_roles.moc` to its configured prefix and create through the same writer:

```bash
python3 "<mnemo-root>/scripts/vault-write.py" <<'JSON'
{"action":"create","vault":"{vault}","note":"{short-name}","content":"{one JSON-escaped Markdown hub body linking to the mapped moc note}"}
JSON
```

Skip if a file with that name already exists (`obsidian read` returns content). Note name must not contain `#` / `.` / `/` (see `<mnemo-root>/references/tool-routing.md` naming rules).

### Step 7: Done

Render the completion message with one runtime-native `{prefix}`: `/mn:` in Claude Code or `$mnemo:` in Codex. Replace the placeholder before showing the message.

```
🧠 mnemo is ready!

Your skills:
  {prefix}ask       — search & synthesize
  {prefix}save      — memory routing cascade
  {prefix}session   — session notes + handoff
  {prefix}review    — session completeness review
  {prefix}connect   — discover hidden links
  {prefix}setup     — configure or reconfigure mnemo
  {prefix}health    — vault audit & analytics

Config saved to: ~/.mnemo/config.json
Handoff note created: Meta — Session Handoff

Try: {prefix}health
```

## Gotchas

Common failures in `<mnemo-root>/references/gotchas.md`. Full config schema in `<mnemo-root>/references/config-schema.md`. Skill-specific rules:

- **Run once** — if `~/.mnemo/config.json` exists, show current values and ask before overwriting. User may just want to change one field, not rebuild everything.
- **Verify Obsidian is open during vault name step** — run the Step 2 `safe-read.py search` probe with `{"query":"test","vault":"{input}"}`. It fails fast if the vault name is wrong or Obsidian isn't running, while keeping the user-provided name out of shell syntax.
- **Don't create vault structure** — mnemo works with existing vaults. Do not create folders, templates, or sample notes. The user's vault is theirs.
- **PARA taxonomy selection** — create `project/area/resource/archive` types plus functional `session/moc`, then confirm the explicit `taxonomy_roles` targets. Custom taxonomy accepts any prefixes as long as each ends in a filename-safe separator such as ` — `, `: `, or ` - `; never `/`, `#`, or `.`.
- **Role-map integrity** — write exactly the five stable role keys and require every value to name an existing taxonomy key. Never route by comparing human-facing prefixes or tags.
- **One write path in both runtimes** — all vault Markdown goes through `scripts/vault-write.py`; never require an external Obsidian MCP and never use inline `obsidian create/append content=`.

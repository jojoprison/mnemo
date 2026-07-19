---
name: setup
description: "Use on first install, when reconfiguring mnemo, or when the user says 'setup mnemo', 'mnemo not configured', 'change vault', 'reset config', 'мнемо настрой', 'настрой мнемо', or similar — also invoked automatically when any other mnemo skill detects a missing config. Interactive onboarding that creates ~/.mnemo/config.json (vault name, taxonomy, links-section language, cascade defaults)."
model: haiku
context: fork
---

# mn:setup — Interactive Onboarding

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

Map the selection to `config.taxonomy` — each entry is `{ "prefix": "…", "tag": "…" }`, and every prefix **must end in a filename-safe separator** such as ` — `, `: `, or ` - `. Never allow `/`, `#`, or `.` in a prefix. Always keep `session` and `moc` regardless of choice — they are *functional* types (the canonical `session` skill reads `taxonomy.session.prefix`; hub-linking uses `moc`), not just note archetypes.

**[1] Zettelkasten** — use the full block shown in Step 5 below.

**[2] PARA:**
```json
"taxonomy": {
  "project":  { "prefix": "Project — ",  "tag": "project" },
  "area":     { "prefix": "Area — ",     "tag": "area" },
  "resource": { "prefix": "Resource — ", "tag": "resource" },
  "archive":  { "prefix": "Archive — ",  "tag": "archive" },
  "session":  { "prefix": "Session — ",  "tag": "session" },
  "moc":      { "prefix": "MOC — ",      "tag": "moc" }
}
```

**[3] Custom** — ask the user for each type's prefix + tag; enforce the separator rule on every prefix; still include `session` and `moc` (add them yourself if the user doesn't name them).

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
  "links_section": "## Связи",
  "handoff_note": "Meta — Session Handoff",
  "cascade": {
    "obsidian": { "enabled": true },
    "claude_mem": { "enabled": false, "url": "http://127.0.0.1:37777" },
    "memory_dir": { "enabled": true },
    "project_rules": { "enabled": true },
    "claude_md": { "enabled": false }
  },
  "hooks": {
    "sessionStartNudge": true,
    "stopNudge": false
  }
}
```

`hooks.stopNudge` ships **false** — flip it to `true` if you want the end-of-session save/session reminder (see `<mnemo-root>/references/config-schema.md`). Everything works on these defaults even if the whole `hooks` block is omitted.

### Step 6: Create Handoff Note (only if missing)

First check — skip this step entirely if the handoff note already exists:

```bash
python3 "<mnemo-root>/scripts/safe-read.py" read <<'JSON'
{"file":"{handoff_note}","vault":"{vault}"}
JSON
```

If empty output, create via MCP (shell-safe for future edits that may contain code blocks — see `<mnemo-root>/references/tool-routing.md`):

```
mcp__obsidian__create(
  path: "Meta — Session Handoff.md",
  file_text: """---
type: meta
tags: [meta, handoff, cross-session]
---

# Meta — Session Handoff

Cross-session continuity file. Updated by the canonical session skill.

## Pending

## Context
- mnemo setup completed on {date}
"""
)
```

### Step 6.5: Project Hub Note (optional)

Offer: "Create a hub note for short-name navigation? E.g. `[[ProjectName]]` → its MOC."

**Why:** Obsidian's resolver ignores frontmatter `aliases` for bare `[[Name]]` links (by design) — only a real file named `ProjectName.md` makes `[[ProjectName]]` resolve. See `<mnemo-root>/references/tool-routing.md` ("Hub notes"). Without it, every short `[[ProjectName]]` reference is a broken ghost.

If user confirms — via MCP:

```
mcp__obsidian__create(
  path: "{short-name}.md",
  file_text: """---
type: hub
aliases: [{short-name}]
---

# {short-name}

→ [[MOC — {full project name}]]

{links_section}
- [[MOC — {full project name}]]
"""
)
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
- **PARA taxonomy selection** — map to `project/area/resource/archive` prefixes. Custom taxonomy accepts any prefixes as long as each ends in a filename-safe separator such as ` — `, `: `, or ` - `; never `/`, `#`, or `.`.

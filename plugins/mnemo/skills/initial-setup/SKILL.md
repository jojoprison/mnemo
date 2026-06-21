---
name: initial-setup
description: "Use on first install, when reconfiguring mnemo, or when the user says 'setup mnemo', 'mnemo not configured', 'change vault', 'reset config', 'мнемо настрой'. Interactive onboarding that creates ~/.mnemo/config.json with vault name, taxonomy, language preferences, and cascade integration settings. Also invoked automatically when any other mnemo skill detects a missing config."
user-invocable: false
model: haiku
context: fork
---

# mnemo:setup — Interactive Onboarding

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
obsidian search query="test" vault="{input}"
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

Map selection to taxonomy config.

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
    "claude_md": { "enabled": false }
  }
}
```

### Step 6: Create Handoff Note (only if missing)

First check — skip this step entirely if the handoff note already exists:

```bash
obsidian read file="{handoff_note}" vault="{vault}" 2>/dev/null | head -1
```

If empty output, create via MCP (shell-safe for future edits that may contain code blocks — see `references/tool-routing.md`):

```
mcp__obsidian__create(
  path: "Meta — Session Handoff.md",
  file_text: """---
type: meta
tags: [meta, handoff, cross-session]
---

# Meta — Session Handoff

Cross-session continuity file. Updated by mnemo:session.

## Pending

## Context
- mnemo setup completed on {date}
"""
)
```

### Step 6.5: Project Hub Note (optional)

Offer: "Create a hub note for short-name navigation? E.g. `[[ProjectName]]` → its MOC."

**Why:** Obsidian's resolver ignores frontmatter `aliases` for bare `[[Name]]` links (by design) — only a real file named `ProjectName.md` makes `[[ProjectName]]` resolve. See `references/tool-routing.md` ("Hub notes"). Without it, every short `[[ProjectName]]` reference is a broken ghost.

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

Skip if a file with that name already exists (`obsidian read` returns content). Note name must not contain `#` / `.` / `/` (see `references/tool-routing.md` naming rules).

### Step 7: Done

```
🧠 mnemo is ready!

Your skills:
  /mn:health    — vault audit & analytics
  /mn:connect   — discover hidden links
  /mn:session   — session notes + handoff
  /mn:ask       — search & synthesize
  /mn:save      — memory routing cascade
  /mn:review    — session completeness review

Config saved to: ~/.mnemo/config.json
Handoff note created: Meta — Session Handoff

Try: /mn:health
```

## Gotchas

Common failures in `references/gotchas.md`. Full config schema in `references/config-schema.md`. Skill-specific rules:

- **Run once** — if `~/.mnemo/config.json` exists, show current values and ask before overwriting. User may just want to change one field, not rebuild everything.
- **Verify Obsidian is open during vault name step** — the test `obsidian search query="test" vault={input}` fails-fast if the vault name is wrong or Obsidian isn't running.
- **Don't create vault structure** — mnemo works with existing vaults. Do not create folders, templates, or sample notes. The user's vault is theirs.
- **PARA taxonomy selection** — map to `project/area/resource/archive` prefixes. Custom taxonomy accepts any prefixes as long as each ends in a separator (` — `, `: `, `/`).

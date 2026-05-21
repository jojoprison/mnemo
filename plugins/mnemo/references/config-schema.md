# mnemo config.json schema

Path: `~/.mnemo/config.json`. Created by `initial-setup` skill on first install. All other skills read it at runtime.

## Minimal required fields

```json
{
  "vault": "main",
  "taxonomy": {
    "atom": { "prefix": "Atom — ", "tag": "atom" },
    "molecule": { "prefix": "Molecule — ", "tag": "molecule" },
    "source": { "prefix": "Source — ", "tag": "source" },
    "session": { "prefix": "Session — ", "tag": "session" },
    "moc": { "prefix": "MOC — ", "tag": "moc" },
    "inbox": { "prefix": "Inbox — ", "tag": "inbox" }
  },
  "links_section": "## Связи",
  "handoff_note": "Meta — Session Handoff"
}
```

## Full schema with cascade settings

```json
{
  "vault": "main",

  "taxonomy": {
    "atom":     { "prefix": "Atom — ",     "tag": "atom" },
    "molecule": { "prefix": "Molecule — ", "tag": "molecule" },
    "source":   { "prefix": "Source — ",   "tag": "source" },
    "session":  { "prefix": "Session — ",  "tag": "session" },
    "moc":      { "prefix": "MOC — ",      "tag": "moc" },
    "inbox":    { "prefix": "Inbox — ",    "tag": "inbox" }
  },

  "links_section": "## Связи",
  "handoff_note":  "Meta — Session Handoff",

  "cascade": {
    "obsidian":   { "enabled": true },
    "claude_mem": { "enabled": false, "url": "http://127.0.0.1:37777" },
    "memory_dir": { "enabled": true },
    "claude_md":  { "enabled": false }
  }
}
```

## Field reference

| Path | Purpose | Used by |
|------|---------|---------|
| `vault` | Obsidian vault name (as shown in vault switcher) | All skills |
| `taxonomy.{type}.prefix` | Filename prefix for each note type | save, sort, session |
| `taxonomy.{type}.tag` | Frontmatter tag for each note type | save, health, sort |
| `links_section` | Heading used for cross-references (`## Связи` / `## Links`) | All skills |
| `handoff_note` | Cross-session continuity file name | session, setup |
| `cascade.obsidian.enabled` | Skip Obsidian writes if false | memory-routing |
| `cascade.claude_mem.enabled` | Enable optional claude-mem POSTs; keep false if claude-mem is disabled for CPU/RAM reasons | memory-routing |
| `cascade.claude_mem.url` | claude-mem worker URL (default port 37777) | memory-routing |
| `cascade.memory_dir.enabled` | Skip memory/ writes if false | memory-routing |
| `cascade.claude_md.enabled` | Write error-preventing rules to CLAUDE.md (default false) | memory-routing |

## Defaults when fields are missing

If the whole `cascade` section is absent, defaults are: obsidian=true, claude_mem=false, memory_dir=true, claude_md=false.

If `vault` or `taxonomy` is missing, the skill that needs them asks the user and offers to run `/mnemo:setup`.

## Customizing taxonomy

The default is Zettelkasten-inspired (atom/molecule/source). Other common setups:

**PARA** (Projects/Areas/Resources/Archive):
```json
"taxonomy": {
  "project":  { "prefix": "Project — ",  "tag": "project" },
  "area":     { "prefix": "Area — ",     "tag": "area" },
  "resource": { "prefix": "Resource — ", "tag": "resource" },
  "archive":  { "prefix": "Archive — ",  "tag": "archive" },
  "inbox":    { "prefix": "Inbox — ",    "tag": "inbox" }
}
```

**Custom** — any prefix/tag scheme, as long as `prefix` ends with a separator Obsidian can recognize in filenames (` — `, `: `, `/`, etc).

## Internationalization

`links_section` is the natural i18n point. Russian vaults use `## Связи`, English `## Links`, Chinese `## 链接`, etc. All skills honor whatever string is set.

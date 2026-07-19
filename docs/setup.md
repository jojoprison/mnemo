# mn:setup — Interactive Onboarding

## Overview

First-time configuration for mnemo. Creates `~/.mnemo/config.json` through an interactive conversation.

## Usage

```
/mn:setup
```

Run once after installing the plugin.

## What It Configures

| Setting | What it does | Example |
|---------|-------------|---------|
| Vault name | Which Obsidian vault to use | `main` |
| Taxonomy | Note type prefixes and tags | Atom/Molecule/PARA/Custom |
| Links section | Heading for cross-references | `## Links`, `## Связи` |

## Onboarding Flow

```
🧠 Welcome to mnemo!

1. What's your Obsidian vault name? → main
2. Which taxonomy? → [1] Atom/Molecule (Zettelkasten)
3. Links section heading? → [1] ## Связи
4. Config saved to ~/.mnemo/config.json
5. Handoff note created in vault

Your skills:
  /mn:health    — vault audit & analytics
  /mn:connect   — discover hidden links
  /mn:session   — session notes + handoff
  /mn:ask       — search & synthesize
  /mn:save      — memory routing cascade
  /mn:review    — session completeness review

Try: /mn:health
```

## Generated Config

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
  "handoff_note": "Meta — Session Handoff"
}
```

## Optional: Memory Cascade

Add `cascade` to config for multi-backend saves via `/mn:save`:

```json
{
  "cascade": {
    "obsidian": { "enabled": true },
    "claude_mem": { "enabled": false, "url": "http://127.0.0.1:37777" },
    "memory_dir": { "enabled": true },
    "project_rules": { "enabled": true }
  }
}
```

Don't have claude-mem? Leave it out — save works with Obsidian alone.

## Important Notes

- **Run once** — if config exists, asks before overwriting
- **Obsidian must be open** — verifies vault by running a test search
- **Creates handoff note** — `Meta — Session Handoff` in your vault
- **Doesn't create vault structure** — works with your existing vault as-is

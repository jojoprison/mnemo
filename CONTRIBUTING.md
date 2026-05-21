# Contributing to mnemo

## Adding a New Skill

1. Create `plugins/mnemo/skills/{skill-name}/SKILL.md`
2. Follow the frontmatter format:

```yaml
---
name: skill-name
description: "Use when [trigger situation]. Invoke for [action]."
user-invocable: true
context: fork    # if skill writes to vault
model: opus      # or omit for default
---
```

3. Include these sections:
   - **Prerequisites** — what must be installed/running
   - **Config** — what config fields are needed (read from `~/.mnemo/config.json`)
   - **Workflow** — step-by-step with exact CLI commands
   - **Gotchas** — real failure points, edge cases

4. Config fields: use `{vault}`, `{links_section}`, `{taxonomy.*}` placeholders — never hardcode values.

5. Update README.md with the new skill in English, Russian, and Codex installation sections.

6. Open a PR.

## Skill Design Principles

- **CLI-first** — use `obsidian` CLI, not MCP (70,000x cheaper)
- **Non-destructive** — report and suggest, never auto-delete
- **Config-driven** — all user-specific values in `~/.mnemo/config.json`
- **Description = trigger** — write as "Use when [situation]", not "This skill does [function]"
- **Gotchas = highest signal** — every real failure → add to Gotchas

## Adding Taxonomy Support

To support a new note taxonomy (beyond Zettelkasten/PARA):

1. Define type names, prefixes, and tags in `config.example.json`
2. Ensure all skills read from `config.taxonomy` instead of hardcoding
3. Add the taxonomy option to `mnemo:setup` Step 3
4. Document in README under "Custom Taxonomy"

## Reporting Issues

Include:
- Which skill failed
- Your `config.json` (remove vault name if private)
- Obsidian version and CLI version
- Error output

# Contributing to mnemo

## Adding a New Skill

1. Create `plugins/mnemo/skills/{skill-name}/SKILL.md`
2. Follow the frontmatter format:

```yaml
---
name: skill-name
description: "Use when [trigger situation]. Invoke for [action]."
---
```

The directory and `name` must match and use lowercase letters, digits, and single hyphens only. Canonical skills are user-invocable by default, so omit `user-invocable` unless there is a concrete reason to hide one. Claude-only `model` / `context` extensions are allowed when routing genuinely needs them; Codex UI metadata belongs in `agents/openai.yaml` and its `default_prompt` must explicitly mention `$mnemo:{skill-name}`.

3. Include these sections:
   - **Prerequisites** — what must be installed/running
   - **Config** — what config fields are needed (read from `~/.mnemo/config.json`)
   - **Workflow** — step-by-step with exact CLI commands
   - **Gotchas** — real failure points, edge cases

4. Config fields: use `{vault}`, `{links_section}`, `{taxonomy.*}` placeholders — never hardcode values.

5. Add `agents/openai.yaml`, update README.md in English, Russian, and Chinese, and extend the structural checks in `scripts/lint-skills.py`.

6. Run the complete gate before opening a PR:

   ```bash
   python3 scripts/lint-skills.py
   python3 scripts/test-runtime-compat.py
   python3 scripts/test-handoff-archive.py
   claude plugin validate plugins/mnemo --strict
   python3 /path/to/plugin-creator/scripts/validate_plugin.py plugins/mnemo
   ```

## Skill Design Principles

- **CLI-first for reads, shell-free for values** — indexed reads/search/orphans/backlinks run through `scripts/safe-read.py`, which invokes the CLI with argv (`shell=False`); use MCP (`mcp__obsidian__create` / `str_replace`) for markdown writes
- **Non-destructive** — report and suggest, never auto-delete
- **Config-driven** — all user-specific values in `~/.mnemo/config.json`
- **Description = trigger** — write as "Use when [situation]", not "This skill does [function]"
- **Gotchas = highest signal** — every real failure → add to Gotchas

## Adding Taxonomy Support

To support a new note taxonomy (beyond Zettelkasten/PARA):

1. Define type names, prefixes, and tags in `config.example.json`
2. Ensure all skills read from `config.taxonomy` instead of hardcoding
3. Add the taxonomy option to `setup` Step 3
4. Document in README under "Custom Taxonomy"

## Reporting Issues

Include:
- Which skill failed
- Your `config.json` (remove vault name if private)
- Obsidian version and CLI version
- Error output

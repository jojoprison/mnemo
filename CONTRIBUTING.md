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

4. Config fields: use `{vault}`, `{links_section}`, and semantic `taxonomy_roles` lookups — never hardcode built-in type keys. Resolve a role to a `taxonomy` entry, then use that entry's prefix/tag.

5. Add `agents/openai.yaml`, update README.md in English, Russian, and Chinese, and extend the structural checks in `scripts/lint-skills.py`.

6. Run the complete gate before opening a PR:

   ```bash
   python3 scripts/lint-skills.py
   python3 scripts/test-runtime-compat.py
   python3 scripts/test-runtime-memory.py
   python3 scripts/test-runtime-homes.py
   python3 scripts/test-vault-write.py
   python3 scripts/test-skill-write-contracts.py
   python3 scripts/test-handoff-archive.py
   MNEMO_REQUIRE_RUNTIME_LOADERS=1 python3 scripts/test-fresh-install.py
   claude plugin validate plugins/mnemo --strict
   python3 /path/to/plugin-creator/scripts/validate_plugin.py plugins/mnemo
   ```

   CI pins and installs both tested runtime loaders, makes the isolated compatibility/fresh-install checks mandatory, and runs the writer/security suites. Release workstations must use the same strict gate; schema validation alone does not detect loader composition or packaging failures.

## Skill Design Principles

- **Bundled adapters for every vault operation** — indexed reads/search/orphans/backlinks run through `scripts/safe-read.py`, which invokes the CLI with argv (`shell=False`); all Markdown writes use `scripts/vault-write.py` with JSON stdin and optimistic atomic guards
- **Non-destructive** — report and suggest, never auto-delete
- **Config-driven** — all user-specific values in `~/.mnemo/config.json`
- **Description = trigger** — write as "Use when [situation]", not "This skill does [function]"
- **Gotchas = highest signal** — every real failure → add to Gotchas

## Adding Taxonomy Support

To support a new note taxonomy (beyond Zettelkasten/PARA):

1. Define type names, prefixes, and tags in `config.example.json`; retain functional `session` and `moc` entries
2. Define the exact five-key `taxonomy_roles` map; `session` and `moc` self-map, while `fact`/`insight`/`source` may share a destination
3. Ensure every skill resolves semantic roles through `taxonomy_roles` before reading `config.taxonomy`; never consume built-in type keys directly
4. Add the taxonomy option to `setup` Step 3 and extend the role-map regression tests
5. Document a copy/paste-safe config in all README languages

## Reporting Issues

Include:
- Which skill failed
- Your `config.json` (remove vault name if private)
- Obsidian version and CLI version
- Error output

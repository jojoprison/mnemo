# Contributing to mnemo

## Adding a New Skill

The canonical skill set is fixed in code, and CLAUDE.md § Compatibility Rules names it. An eighth skill is not a drop-in addition: every registry in step 5 has to be widened first, otherwise `scripts/lint-skills.py` fails with `canonical skills mismatch; missing=[], extra=['{skill-name}']`. Most work here is editing one of the existing skills, and the steps below apply to that too.

1. Create `plugins/mnemo/skills/{skill-name}/SKILL.md`
2. Follow the frontmatter format:

```yaml
---
name: skill-name
description: "Use when [trigger situation]. Invoke for [action]."
---
```

The directory and `name` must match and use lowercase letters, digits, and single hyphens only. Canonical skills are user-invocable by default, so omit `user-invocable` unless there is a concrete reason to hide one. Claude-only `model` / `context` extensions are allowed when routing genuinely needs them; Codex UI metadata belongs in `agents/openai.yaml` and its `default_prompt` must explicitly mention `$mnemo:{skill-name}`.

3. Satisfy the body contract the gate actually enforces:
   - The invocation marker — the literal, backticked `🧠 mn:{skill-name} (mnemo) → running` — appears **exactly once**, right after the H1 and above `## Portable paths` (`scripts/test-runtime-compat.py`, glob over every `skills/*/SKILL.md`)
   - Exactly one `## Portable paths` section, the only place `${CLAUDE_PLUGIN_ROOT}` may appear (also exactly once); every other bundled path is written `<mnemo-root>/…` (`scripts/lint-skills.py`)
   - Copy both from an existing skill rather than retyping them

   Section names below are convention, not linted — follow them so skills read alike:
   - **Prerequisites & config** — what must be installed/running plus the `~/.mnemo/config.json` fields the skill reads (one combined section; that is what the existing skills use)
   - **Workflow** — step-by-step with exact CLI commands
   - **Gotchas** — real failure points, edge cases

4. Config fields: use `{vault}`, `{links_section}`, and semantic `taxonomy_roles` lookups — never hardcode built-in type keys. Resolve a role to a `taxonomy` entry, then use that entry's prefix/tag.

5. Add `agents/openai.yaml`, update README.md in English, Russian, and Chinese, and widen every place that pins the canonical set: `CANONICAL_SKILLS` in `scripts/lint-skills.py`, the separate copy plus the literal skill count in `scripts/test-fresh-install.py`, and the skill count in the `description` of `plugins/mnemo/.claude-plugin/plugin.json`. (The `canonical` tuple in `scripts/test-runtime-compat.py` belongs to a synthetic fixture plugin and is not part of this list.)

   **Writing `[[wikilink]]` examples.** The linter's private-leak guard rejects links that name a concrete note, because links into a maintainer's own vault have reached a public PR here before — they are dead for every reader and expose what is in that vault. Prefer a shape that cannot name a real note: `[[{hub_name}]]`, `[[Session — …]]`, `[[wikilinks]]`. If your example genuinely needs a concrete title, invent one and add it to `scripts/wikilink-allowlist.txt`; if the name is a note you actually keep, state the fact in prose instead of linking to it. The same guard rejects absolute home paths — write `~/`, `${VAR}`, or `/Users/<you>/`.

6. Run the complete gate before opening a PR. **The canonical command list lives in one place — `TESTING.md` § Automated gate** — because a hand-kept copy here drifted out of date three times while new suites shipped unlisted. Run every command in that block, in order, and do not re-copy it here.

   CI pins and installs both tested runtime loaders, makes the isolated compatibility/fresh-install checks mandatory, and runs the same glob over every suite. Release workstations must use the same strict gate; schema validation alone does not detect loader composition or packaging failures.

## Skill Design Principles

- **Bundled adapters for every vault operation** — indexed reads/search/orphans/backlinks run through `plugins/mnemo/scripts/safe-read.py`, which invokes the CLI with argv (`shell=False`); all Markdown writes use `plugins/mnemo/scripts/vault-write.py` with JSON stdin and optimistic atomic guards
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

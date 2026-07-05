# mnemo Agent Instructions

mnemo is a dual-runtime Agent Skills plugin for Codex and Claude Code. Keep Claude Code compatibility intact while adding Codex support.

**Design philosophy & non-goals:** read `docs/design-decisions.md` first — the one principle everything follows (human-authored vault, non-destructive, in-agent) and the features deliberately **not** shipped (auto-ingest, web-search imputation, `hot.md`), each with an on-philosophy way to add it if you want it.

## Compatibility Rules

- Do not remove `plugins/mnemo/.claude-plugin/plugin.json` or `plugins/mnemo/commands/mn/*`; Claude users rely on `/mn:*`.
- Codex support is additive: keep `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` beside the Claude manifest.
- Shared skills live in `plugins/mnemo/skills/*/SKILL.md`; avoid forked copies unless behavior must diverge by runtime.
- Runtime-specific behavior belongs in scripts or `references/`, not duplicated skill bodies.

## Memory Backends

- Obsidian is the primary user-visible memory store.
- claude-mem is optional and may be intentionally disabled for CPU/RAM reasons. Do not auto-start ChromaDB, the claude-mem worker, or repair claude-mem unless the user explicitly asks.
- In Codex, fallback local memory goes under `~/.codex/memories/`.
- In Claude Code, fallback local memory goes under `~/.claude/projects/<slug>/memory/`.

## Verification

- Run `python3 scripts/lint-skills.py` after editing any skill, manifest, script reference, or plugin metadata.
- Run `python3 plugins/mnemo/scripts/session-scan.py` once without runtime env vars to verify graceful fallback.
- Preserve shell-safety: never pass arbitrary markdown through `obsidian create content="..."` or `obsidian append content="..."`.

## Releasing

### Versioning & approval gate

mnemo follows [SemVer](https://semver.org) from **1.0.0** (first stable). **The default for every release is a patch bump (`1.1.z`) — even for new features.**

- **patch** (`1.1.z`) — the default for **everything**: bug fixes, docs, refactors, **and new skills / flags / user-visible behavior**. An agent may cut a patch release autonomously. When a change "feels like a minor", still ship it as a patch and just say so.
- **minor** (`1.y.0`) / **major** (`x.0.0`) — the middle and first digits move **ONLY on the maintainer's explicit instruction** ("bump the minor now", "this one's a minor / major"). Never raise them on your own judgment, even when plain SemVer would call the change a minor. No instruction → it's a patch.

This gate is about the *version bump*, not the work: implement, commit, and cut patch releases freely; just never touch the minor/major digit unless the maintainer told you to in this conversation.

### Release steps

- Bump the version in **all three** manifests together: `plugins/mnemo/.claude-plugin/plugin.json`, `plugins/mnemo/.codex-plugin/plugin.json`, and `.claude-plugin/marketplace.json`.
- Add a dated section to `CHANGELOG.md` (Keep a Changelog format); keep the `[Unreleased]` section and the version compare-links at the bottom in sync.
- **Always create and push an annotated git tag `vX.Y.Z` for every new version** — `git tag -a vX.Y.Z -m "…" && git push origin vX.Y.Z`. This is easy to forget; a missing tag breaks the CHANGELOG compare-links and skips the GitHub Release. `.github/workflows/release.yml` mirrors the tag's CHANGELOG section into a GitHub Release on push.
- After releasing, run `claude plugin update mnemo@mnemo` to pick it up locally — the loaded plugin cache lags the repo.

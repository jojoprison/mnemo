#!/usr/bin/env python3
"""Validate mnemo skill and plugin metadata.

Checks:
1. Frontmatter parses (YAML between --- markers).
2. Required fields present: name, description.
3. model field (if present) is in whitelist: haiku, sonnet, opus, inherit.
4. context field (if present) is in whitelist: fork.
5. context: fork + model: inherit is contradictory (rejected).
6. File length ≤ 500 lines (skill-creator best practice).
7. Any `references/*.md` path mentioned in the body actually exists.
8. Any `scripts/*.{sh,py}` path mentioned resolves to an existing file.
9. Any `assets/*` path mentioned resolves.
10. Claude and Codex plugin manifests parse and point to existing skills.
11. Agent Skills names match their directories and the shared naming spec.
12. mnemo exposes exactly seven canonical short skills with Codex UI metadata.
13. Claude and Codex keep their intentional runtime namespace contract.
14. Skill bodies never route generated markdown through inline Obsidian CLI writes.
15. Skill bodies route every dynamic Obsidian CLI operation through the argv adapter.
16. Shared hooks use only documented Codex events; Claude-only hooks are additive.

Exit codes:
  0 — all SKILL.md valid
  1 — one or more violations found
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_WHITELIST = {"haiku", "sonnet", "opus", "inherit"}
CONTEXT_WHITELIST = {"fork"}
MAX_LINES = 500
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CANONICAL_SKILLS = {"ask", "save", "session", "review", "connect", "setup", "health"}
OPENAI_INTERFACE_FIELDS = {"display_name", "short_description", "default_prompt"}
CODEX_HOOK_EVENTS = {
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "PreCompact",
    "PostCompact",
    "UserPromptSubmit",
    "SubagentStart",
    "SubagentStop",
    "Stop",
    "SessionStart",
}
STALE_INTERNAL_NAMES = {
    "vault-search",
    "memory-routing",
    "session-notes",
    "session-review",
    "link-discovery",
    "initial-setup",
    "vault-health",
    "mnemo:mn:",
}
REF_RE = re.compile(r"references/([a-zA-Z0-9_\-]+\.md)")
SCRIPT_RE = re.compile(r"scripts/([a-zA-Z0-9_\-]+\.(?:sh|py))")
ASSET_RE = re.compile(r"assets/([a-zA-Z0-9_\-.]+)")
INLINE_OBSIDIAN_WRITE_RE = re.compile(
    r"(?im)^[ \t]*(?:\$[ \t]*)?obsidian[ \t]+(?:create|append|prepend)\b"
    r"[^\r\n]*\bcontent[ \t]*="
)
DIRECT_OBSIDIAN_CLI_RE = re.compile(
    r"(?im)^[ \t]*(?:\$[ \t]*)?obsidian[ \t]+"
    r"(?:search|read|orphans|unresolved|backlinks|tags|files|vault|eval|create|append|prepend)\b"
)


def has_inline_obsidian_write(text: str) -> bool:
    """Detect shell-unsafe Obsidian writes that interpolate generated content."""
    return INLINE_OBSIDIAN_WRITE_RE.search(text) is not None


def has_direct_obsidian_cli(text: str) -> bool:
    """Require the argv-based adapter for all dynamic Obsidian CLI operations."""
    return DIRECT_OBSIDIAN_CLI_RE.search(text) is not None


def parse_frontmatter(text: str) -> tuple[dict[str, str] | None, str]:
    if not text.startswith("---\n"):
        return None, "no opening --- marker"
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, "no closing --- marker"
    fm_raw = text[4:end]
    fm: dict[str, str] = {}
    for line in fm_raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm, ""


def check_skill(path: str) -> list[str]:
    issues: list[str] = []
    try:
        with open(path) as f:
            text = f.read()
    except OSError as e:
        return [f"cannot read: {e}"]

    lines = text.count("\n") + 1
    if lines > MAX_LINES:
        issues.append(f"{lines} lines > {MAX_LINES} (progressive disclosure: extract to references/)")

    fm, err = parse_frontmatter(text)
    if fm is None:
        issues.append(f"frontmatter: {err}")
        return issues

    for required in ("name", "description"):
        if required not in fm:
            issues.append(f"frontmatter missing required field: {required}")

    name = fm.get("name", "")
    skill_dir = os.path.basename(os.path.dirname(path))
    if name and name != skill_dir:
        issues.append(f"frontmatter name '{name}' must match parent directory '{skill_dir}'")
    if name and (len(name) > 64 or not SKILL_NAME_RE.fullmatch(name)):
        issues.append("name must be 1-64 lowercase letters, digits, or single hyphens")

    description = fm.get("description", "")
    if len(description) > 1024:
        issues.append(f"description is {len(description)} chars > 1024")

    model = fm.get("model")
    if model and model not in MODEL_WHITELIST:
        issues.append(f"model '{model}' not in whitelist {sorted(MODEL_WHITELIST)}")

    context = fm.get("context")
    if context and context not in CONTEXT_WHITELIST:
        issues.append(f"context '{context}' not in whitelist {sorted(CONTEXT_WHITELIST)}")

    if context == "fork" and model == "inherit":
        issues.append("context: fork + model: inherit is contradictory (fork creates isolated subagent; pick a concrete model)")

    if has_inline_obsidian_write(text):
        issues.append(
            "generated markdown must use scripts/vault-write.py, never inline "
            "obsidian create/append/prepend content= shell arguments"
        )
    if has_direct_obsidian_cli(text):
        issues.append(
            "direct Obsidian CLI commands are forbidden in skill bodies; route dynamic "
            "values through scripts/safe-read.py or markdown writes through scripts/vault-write.py"
        )

    plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(path)))
    for match in REF_RE.finditer(text):
        ref_name = match.group(1)
        ref_path = os.path.join(plugin_dir, "references", ref_name)
        if not os.path.exists(ref_path):
            issues.append(f"references/{ref_name} referenced but file missing")

    for match in SCRIPT_RE.finditer(text):
        script_name = match.group(1)
        script_path = os.path.join(plugin_dir, "scripts", script_name)
        if not os.path.exists(script_path):
            issues.append(f"scripts/{script_name} referenced but file missing")

    for match in ASSET_RE.finditer(text):
        asset_name = match.group(1)
        asset_path = os.path.join(plugin_dir, "assets", asset_name)
        if not os.path.exists(asset_path):
            issues.append(f"assets/{asset_name} referenced but file missing")

    return issues


def parse_simple_openai_yaml(path: str) -> tuple[dict[str, str] | None, str]:
    """Parse the flat `interface` string fields used by mnemo's openai.yaml files."""
    try:
        with open(path) as f:
            lines = f.read().splitlines()
    except OSError as e:
        return None, str(e)

    if not lines or lines[0].strip() != "interface:":
        return None, "missing top-level interface mapping"

    values: dict[str, str] = {}
    for line in lines[1:]:
        match = re.fullmatch(r'  ([a-z_]+): "([^"\\]*(?:\\.[^"\\]*)*)"', line)
        if not match:
            return None, f"unsupported or unquoted line: {line!r}"
        values[match.group(1)] = match.group(2)
    return values, ""


def command_hook_commands(hooks: dict) -> list[str]:
    commands: list[str] = []
    for matchers in hooks.get("hooks", {}).values():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                if hook.get("type") == "command":
                    commands.append(str(hook.get("command", "")))
    return commands


def check_mnemo_contract() -> list[str]:
    issues: list[str] = []
    plugin_dir = os.path.join(REPO_ROOT, "plugins", "mnemo")
    skills_dir = os.path.join(plugin_dir, "skills")
    actual = {
        name
        for name in os.listdir(skills_dir)
        if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md"))
    }
    if actual != CANONICAL_SKILLS:
        missing = sorted(CANONICAL_SKILLS - actual)
        extra = sorted(actual - CANONICAL_SKILLS)
        issues.append(f"canonical skills mismatch; missing={missing}, extra={extra}")

    legacy_commands = os.path.join(plugin_dir, "commands")
    if os.path.exists(legacy_commands):
        issues.append("legacy commands/ facade must be removed; canonical skills own the UI")
    if os.path.exists(os.path.join(plugin_dir, "hooks", "codex-hooks.json")):
        issues.append("forked Codex hook manifest must be removed; Codex uses hooks/hooks.json")

    for name in sorted(CANONICAL_SKILLS):
        skill_path = os.path.join(skills_dir, name, "SKILL.md")
        if os.path.isfile(skill_path):
            with open(skill_path) as f:
                skill_text = f.read()
            fm, _ = parse_frontmatter(skill_text)
            if fm and fm.get("user-invocable", "true").lower() == "false":
                issues.append(f"{name}: canonical skill must remain user-invocable")
            if skill_text.count("## Portable paths") != 1:
                issues.append(f"{name}: must define exactly one Portable paths contract")
            if skill_text.count("${CLAUDE_PLUGIN_ROOT}") != 1:
                issues.append(f"{name}: CLAUDE_PLUGIN_ROOT may appear only in Portable paths")
            if "<mnemo-root>" not in skill_text:
                issues.append(f"{name}: bundled paths must use <mnemo-root>")
            if "!`" in skill_text or "```!" in skill_text:
                issues.append(f"{name}: Claude-only shell preprocessing is not cross-runtime")
            if "$ARGUMENTS" in skill_text:
                issues.append(f"{name}: Claude-only $ARGUMENTS placeholder is not cross-runtime")
            if ".claude/plugins/cache" in skill_text or ".codex/plugins/cache" in skill_text:
                issues.append(f"{name}: skill body must resolve <mnemo-root>, not hunt plugin caches")

        metadata_path = os.path.join(skills_dir, name, "agents", "openai.yaml")
        metadata, err = parse_simple_openai_yaml(metadata_path)
        if metadata is None:
            issues.append(f"{name}: invalid agents/openai.yaml: {err}")
            continue
        if set(metadata) != OPENAI_INTERFACE_FIELDS:
            issues.append(
                f"{name}: openai.yaml fields must be exactly {sorted(OPENAI_INTERFACE_FIELDS)}"
            )
        expected_display = f"mn:{name}"
        if metadata.get("display_name") != expected_display:
            issues.append(f"{name}: display_name must be '{expected_display}'")
        short = metadata.get("short_description", "")
        if not 25 <= len(short) <= 64:
            issues.append(f"{name}: short_description must be 25-64 chars (got {len(short)})")
        prompt = metadata.get("default_prompt", "")
        if f"$mnemo:{name}" not in prompt:
            issues.append(f"{name}: default_prompt must mention $mnemo:{name}")
        if len(prompt) > 128:
            issues.append(f"{name}: default_prompt must be at most 128 chars")

    def load_json(path: str) -> dict:
        with open(path) as f:
            return json.load(f)

    claude_manifest = load_json(os.path.join(plugin_dir, ".claude-plugin", "plugin.json"))
    codex_manifest = load_json(os.path.join(plugin_dir, ".codex-plugin", "plugin.json"))
    claude_market = load_json(os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json"))
    codex_market = load_json(os.path.join(REPO_ROOT, ".agents", "plugins", "marketplace.json"))
    if claude_manifest.get("name") != "mn":
        issues.append("Claude runtime namespace must be 'mn'")
    if claude_manifest.get("displayName") != "mnemo":
        issues.append("Claude displayName must preserve the public 'mnemo' brand")
    if codex_manifest.get("name") != "mnemo":
        issues.append("Codex plugin namespace must remain 'mnemo'")
    expected_claude_hooks = ["./hooks/claude-hooks.json"]
    if claude_manifest.get("hooks") != expected_claude_hooks:
        issues.append(
            "Claude manifest hooks must add only ./hooks/claude-hooks.json; "
            "Claude auto-loads the standard hooks/hooks.json"
        )
    if "hooks" in codex_manifest:
        issues.append("Codex manifest must use default hooks/hooks.json discovery")
    if claude_market.get("plugins", [{}])[0].get("name") != "mnemo":
        issues.append("Claude marketplace install ID must remain 'mnemo'")
    if codex_market.get("plugins", [{}])[0].get("name") != "mnemo":
        issues.append("Codex marketplace install ID must remain 'mnemo'")
    versions = {
        claude_manifest.get("version"),
        codex_manifest.get("version"),
        claude_market.get("plugins", [{}])[0].get("version"),
    }
    if len(versions) != 1:
        issues.append(f"manifest versions must match (got {sorted(str(v) for v in versions)})")
    for prompt in codex_manifest.get("interface", {}).get("defaultPrompt", []):
        if "/mn:" in prompt:
            issues.append("Codex defaultPrompt must use $mnemo:* rather than Claude slash syntax")

    hooks_path = os.path.join(plugin_dir, "hooks", "hooks.json")
    hooks = load_json(hooks_path)
    claude_hooks_path = os.path.join(plugin_dir, "hooks", "claude-hooks.json")
    claude_hooks = load_json(claude_hooks_path)
    unexpected_hook_keys = sorted(set(hooks) - {"hooks"})
    if unexpected_hook_keys:
        issues.append(
            "shared hooks manifest must keep a legacy-compatible top level; "
            f"unexpected keys: {', '.join(unexpected_hook_keys)}"
        )
    shared_events = set(hooks.get("hooks", {}))
    unsupported_events = sorted(shared_events - CODEX_HOOK_EVENTS)
    if unsupported_events:
        issues.append(
            "shared hooks manifest contains Codex-unsupported events: "
            + ", ".join(unsupported_events)
        )
    if shared_events != {"SessionStart", "Stop"}:
        issues.append("shared hooks manifest must define exactly SessionStart and Stop")
    if set(claude_hooks) != {"hooks"}:
        issues.append("Claude-only hooks manifest must contain only the hooks key")
    claude_events = set(claude_hooks.get("hooks", {}))
    if claude_events != {"UserPromptExpansion"}:
        issues.append("Claude-only hooks manifest must define exactly UserPromptExpansion")
    if shared_events & claude_events:
        issues.append("hook events must be defined once, never duplicated across manifests")

    hook_commands = command_hook_commands(hooks) + command_hook_commands(claude_hooks)
    if not hook_commands:
        issues.append("shared hooks manifest must define command hooks")
    for command in hook_commands:
        if "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}" not in command:
            issues.append(
                "every hook command must resolve PLUGIN_ROOT with "
                "CLAUDE_PLUGIN_ROOT fallback"
            )
    for manifest in (hooks, claude_hooks):
        for event, matchers in manifest.get("hooks", {}).items():
            for matcher in matchers:
                for handler in matcher.get("hooks", []):
                    if "async" in handler:
                        issues.append(f"{event}: hook handler must not declare async")

    for relative in ("skills/setup/SKILL.md", "references/config-schema.md"):
        path = os.path.join(plugin_dir, relative)
        with open(path) as f:
            text = f.read()
        if re.search(r"separator[^\n]{0,120}(?:or |, )`/`", text, re.IGNORECASE):
            issues.append(f"{relative}: slash cannot be presented as a valid filename separator")

    for root, _, files in os.walk(plugin_dir):
        if os.path.basename(root) in {".claude-plugin", ".codex-plugin"}:
            continue
        for filename in files:
            if not filename.endswith((".md", ".py", ".sh", ".json", ".yaml", ".yml")):
                continue
            path = os.path.join(root, filename)
            with open(path, errors="replace") as f:
                text = f.read()
            for stale in STALE_INTERNAL_NAMES:
                if stale in text:
                    rel = os.path.relpath(path, REPO_ROOT)
                    issues.append(f"stale internal name '{stale}' in {rel}")

    return issues


def check_plugin_manifest(path: str) -> list[str]:
    issues: list[str] = []
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [f"manifest parse failed: {e}"]

    for required in ("name", "version", "description"):
        if not data.get(required):
            issues.append(f"manifest missing required field: {required}")

    skills_path = data.get("skills")
    if skills_path:
        manifest_dir = os.path.dirname(path)
        plugin_dir = os.path.dirname(manifest_dir)
        candidates = [
            os.path.abspath(os.path.join(manifest_dir, skills_path)),
            os.path.abspath(os.path.join(plugin_dir, skills_path)),
        ]
        resolved = next((candidate for candidate in candidates if os.path.isdir(candidate)), candidates[0])
        if not os.path.isdir(resolved):
            issues.append(f"skills path does not exist: {skills_path}")

    return issues


def check_marketplace(path: str) -> list[str]:
    issues: list[str] = []
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [f"marketplace parse failed: {e}"]

    if not data.get("name"):
        issues.append("marketplace missing name")
    plugins = data.get("plugins", [])
    if not isinstance(plugins, list) or not plugins:
        issues.append("marketplace plugins must be a non-empty list")
        return issues

    for idx, plugin in enumerate(plugins):
        if not plugin.get("name"):
            issues.append(f"plugin {idx} missing name")
        source = plugin.get("source")
        if isinstance(source, dict):
            path_value = source.get("path")
        else:
            path_value = plugin.get("source")
        if path_value and isinstance(path_value, str) and path_value.startswith("."):
            candidates = [
                os.path.abspath(os.path.join(os.path.dirname(path), path_value)),
                os.path.abspath(os.path.join(REPO_ROOT, path_value)),
            ]
            resolved = next((candidate for candidate in candidates if os.path.isdir(candidate)), candidates[0])
            if not os.path.isdir(resolved):
                issues.append(f"plugin {idx} source path missing: {path_value}")

    return issues


def main() -> int:
    pattern = os.path.join(REPO_ROOT, "plugins", "*", "skills", "*", "SKILL.md")
    skills = sorted(glob.glob(pattern))
    if not skills:
        print(f"No SKILL.md found under {pattern}")
        return 1

    had_issues = False
    for path in skills:
        rel = os.path.relpath(path, REPO_ROOT)
        issues = check_skill(path)
        if issues:
            had_issues = True
            print(f"\n❌ {rel}")
            for issue in issues:
                print(f"   • {issue}")
        else:
            print(f"✅ {rel}")

    metadata_files = [
        os.path.join(REPO_ROOT, "plugins", "mnemo", ".claude-plugin", "plugin.json"),
        os.path.join(REPO_ROOT, "plugins", "mnemo", ".codex-plugin", "plugin.json"),
    ]
    for path in metadata_files:
        rel = os.path.relpath(path, REPO_ROOT)
        issues = check_plugin_manifest(path)
        if issues:
            had_issues = True
            print(f"\n❌ {rel}")
            for issue in issues:
                print(f"   • {issue}")
        else:
            print(f"✅ {rel}")

    marketplace_files = [
        os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json"),
        os.path.join(REPO_ROOT, ".agents", "plugins", "marketplace.json"),
    ]
    for path in marketplace_files:
        rel = os.path.relpath(path, REPO_ROOT)
        issues = check_marketplace(path)
        if issues:
            had_issues = True
            print(f"\n❌ {rel}")
            for issue in issues:
                print(f"   • {issue}")
        else:
            print(f"✅ {rel}")

    contract_issues = check_mnemo_contract()
    if contract_issues:
        had_issues = True
        print("\n❌ mnemo dual-runtime contract")
        for issue in contract_issues:
            print(f"   • {issue}")
    else:
        print("✅ mnemo dual-runtime contract")

    print()
    if had_issues:
        print("LINT FAILED — fix the issues above.")
        return 1
    print(f"LINT PASSED — {len(skills)} SKILL.md files, zero violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

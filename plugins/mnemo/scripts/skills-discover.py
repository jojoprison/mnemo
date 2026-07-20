#!/usr/bin/env python3
"""Auto-discover installed skills across Claude Code, Codex, and this project.

Used by review to build the "don't hallucinate skills" allowlist. Results are
cached for 300s in a private per-user temp directory, keyed by runtime and
project root so nested working directories share the correct inventory.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from functools import lru_cache

from cache_utils import atomic_write_text, cache_path, configured_root, is_fresh, read_text
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None

HOME = os.path.expanduser("~")
CLAUDE_ROOT = configured_root("CLAUDE_CONFIG_DIR", ".claude")
CODEX_ROOT = configured_root("CODEX_HOME", ".codex")
IS_CODEX = any(
    os.environ.get(k)
    for k in (
        "PLUGIN_ROOT",
        "CODEX_THREAD_ID",
        "CODEX_SESSION_ID",
        "CODEX_CI",
        "CODEX_SANDBOX",
    )
)
CLAUDE_ONLY_ROOTS = (
    os.path.join(CLAUDE_ROOT, "skills"),
    os.path.join(CLAUDE_ROOT, "plugins"),
)
CODEX_ONLY_ROOTS = (
    os.path.join(CODEX_ROOT, "plugins/cache"),
    os.path.join(CODEX_ROOT, ".tmp/marketplaces"),
    os.path.join(CODEX_ROOT, "skills"),
    os.path.join(HOME, ".agents/skills"),
    "/etc/codex/skills",
)

NAME_RE = re.compile(r'^name:\s*["\']?(.+?)["\']?\s*$', re.M)
DESC_RE = re.compile(r'^description:\s*["\']?(.+?)["\']?\s*$', re.M)
DISCOVERY_CACHE_RE = re.compile(r"\nTOTAL_SKILLS: \d+\n\Z")


@lru_cache(maxsize=None)
def find_project_root(start: str) -> str:
    """Find the nearest git root without assuming the helper runs from repo root."""
    current = os.path.realpath(start)
    while True:
        if os.path.lexists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.realpath(start)
        current = parent


def project_root() -> str:
    return find_project_root(os.getcwd())


def project_bases() -> list[str]:
    """Return CWD and each parent through the git root, matching runtime scopes."""
    root = project_root()
    current = os.path.realpath(os.getcwd())
    bases: list[str] = []
    while True:
        bases.append(current)
        if current == root:
            return bases
        parent = os.path.dirname(current)
        if parent == current:
            return [root]
        current = parent


def discovery_patterns() -> list[str]:
    patterns = [
        # Claude Code user/plugin scopes.
        os.path.join(CLAUDE_ROOT, "skills/*/SKILL.md"),
        os.path.join(CLAUDE_ROOT, "plugins/*/skills/*/SKILL.md"),
        os.path.join(CLAUDE_ROOT, "plugins/cache/*/*/*/skills/*/SKILL.md"),
        os.path.join(CLAUDE_ROOT, "plugins/marketplaces/*/plugins/*/skills/*/SKILL.md"),
        # Codex documented and plugin scopes.
        os.path.join(HOME, ".agents/skills/*/SKILL.md"),
        "/etc/codex/skills/*/SKILL.md",
        os.path.join(CODEX_ROOT, "skills/*/SKILL.md"),
        os.path.join(CODEX_ROOT, "plugins/cache/*/*/*/skills/*/SKILL.md"),
        os.path.join(CODEX_ROOT, ".tmp/marketplaces/*/plugins/*/skills/*/SKILL.md"),
    ]
    for base in project_bases():
        patterns.extend(
            (
                os.path.join(base, ".agents/skills/*/SKILL.md"),
                os.path.join(base, ".claude/skills/*/SKILL.md"),
            )
        )
    patterns.append(os.path.join(project_root(), "plugins/*/skills/*/SKILL.md"))
    return patterns


def disabled_codex_plugins() -> set[str]:
    """Return explicit disabled Codex plugin ids like superpowers@marketplace."""
    if tomllib is None:
        return set()

    config_path = codex_config_path()
    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    except OSError:
        return set()

    disabled: set[str] = set()
    for key, value in config.get("plugins", {}).items():
        if isinstance(value, dict) and value.get("enabled") is False:
            disabled.add(key)
    return disabled


def codex_config_path() -> str:
    return os.path.join(CODEX_ROOT, "config.toml")


def codex_plugin_id(path: str) -> str:
    """Map cache/temp skill paths back to plugin@marketplace ids."""
    coords = cache_coordinates(path)
    if coords and coords[0] == "codex":
        _, marketplace, plugin, _, _ = coords
        return f"{plugin}@{marketplace}"

    abs_path = os.path.abspath(path)

    for tmp_root in (os.path.join(CODEX_ROOT, ".tmp/marketplaces"),):
        tmp_prefix = tmp_root + os.sep
        if abs_path.startswith(tmp_prefix):
            rel = abs_path[len(tmp_prefix):].split(os.sep)
            if len(rel) >= 3 and rel[1] == "plugins":
                marketplace, plugin = rel[0], rel[2]
                return f"{plugin}@{marketplace}"

    return ""


def runtime_roots(home: str | None = None) -> tuple[str, str]:
    """Return Claude/Codex roots; an explicit home preserves legacy test callers."""
    if home is None:
        return CLAUDE_ROOT, CODEX_ROOT
    return (
        configured_root("CLAUDE_CONFIG_DIR", ".claude", home),
        configured_root("CODEX_HOME", ".codex", home),
    )


def cache_coordinates(
    path: str, home: str | None = None
) -> tuple[str, str, str, str, str] | None:
    """Return runtime, marketplace, plugin, version, and version root for cache paths."""
    abs_path = os.path.abspath(path)
    claude_root, codex_root = runtime_roots(home)
    for runtime, cache_root in (
        ("claude", os.path.join(claude_root, "plugins/cache")),
        ("codex", os.path.join(codex_root, "plugins/cache")),
    ):
        prefix = cache_root + os.sep
        if not abs_path.startswith(prefix):
            continue
        rel = abs_path[len(prefix):].split(os.sep)
        if len(rel) < 4:
            return None
        marketplace, plugin, version = rel[:3]
        version_root = os.path.join(cache_root, marketplace, plugin, version)
        return runtime, marketplace, plugin, version, version_root
    return None


def select_current_cache_paths(paths: list[str], home: str | None = None) -> list[str]:
    """Keep one newest cache generation per plugin."""
    grouped: dict[tuple[str, str, str], dict[str, list[str]]] = {}
    passthrough: list[str] = []
    for path in paths:
        coords = cache_coordinates(path, home)
        if not coords:
            passthrough.append(path)
            continue
        runtime, marketplace, plugin, _version, version_root = coords
        grouped.setdefault((runtime, marketplace, plugin), {}).setdefault(version_root, []).append(path)

    selected = list(passthrough)
    for versions in grouped.values():
        newest_root = max(
            versions,
            key=lambda root: (safe_mtime(root), root),
        )
        selected.extend(versions[newest_root])
    order = {path: idx for idx, path in enumerate(paths)}
    return sorted(selected, key=lambda path: order[path])


def safe_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


@lru_cache(maxsize=None)
def namespace_for_root(plugin_root: str, codex_first: bool) -> str:
    """Read one runtime namespace per plugin root, not once per skill."""
    manifest_dirs = (
        (".codex-plugin", ".claude-plugin")
        if codex_first
        else (".claude-plugin", ".codex-plugin")
    )
    for manifest_dir in manifest_dirs:
        manifest = os.path.join(plugin_root, manifest_dir, "plugin.json")
        try:
            with open(manifest) as f:
                name = json.load(f).get("name", "")
        except (OSError, json.JSONDecodeError):
            continue
        if name:
            return str(name)
    return ""


def plugin_namespace(path: str) -> str:
    """Read the active runtime's component namespace for a skill path."""
    plugin_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path))))
    return namespace_for_root(plugin_root, IS_CODEX)


def local_plugin_names(paths: list[str]) -> set[str]:
    """Return plugin folder names contributed by this working tree."""
    names: set[str] = set()
    for path in paths:
        if not is_repo_local_plugin(path):
            continue
        name = plugin_package_name(path)
        if name:
            names.add(name)
    return names


def plugin_package_name(path: str, home: str | None = None) -> str:
    """Return the marketplace/repo plugin folder name for a skill path."""
    coords = cache_coordinates(path, home)
    if coords:
        return coords[2]

    abs_path = os.path.abspath(path)
    repo_plugins = os.path.join(project_root(), "plugins")
    claude_root, codex_root = runtime_roots(home)
    roots = (
        repo_plugins,
        os.path.join(codex_root, ".tmp/marketplaces"),
        os.path.join(claude_root, "plugins/marketplaces"),
    )
    for root in roots:
        prefix = root + os.sep
        if not abs_path.startswith(prefix):
            continue
        rel = abs_path[len(prefix):].split(os.sep)
        if root == repo_plugins and len(rel) >= 3 and rel[1] == "skills":
            return rel[0]
        if len(rel) >= 4 and rel[1] == "plugins" and rel[3] == "skills":
            return rel[2]
    return ""


def is_repo_local_plugin(path: str) -> bool:
    plugins_root = os.path.join(project_root(), "plugins") + os.sep
    return os.path.abspath(path).startswith(plugins_root)


def is_codex_user_skill(path: str) -> bool:
    """Recognize Codex user-scope skills without assuming a `.codex` dirname."""
    candidate = os.path.realpath(path)
    roots = (
        os.path.join(CODEX_ROOT, "skills"),
        os.path.join(HOME, ".agents/skills"),
    )
    return any(
        candidate.startswith(os.path.realpath(root) + os.sep)
        for root in roots
    )


def skip_for_runtime(path: str) -> bool:
    """Exclude skill roots that the active runtime cannot load."""
    abs_path = os.path.realpath(path)
    project_roots = tuple(
        os.path.join(base, ".claude/skills" if IS_CODEX else ".agents/skills")
        for base in project_bases()
    )
    roots = (
        CLAUDE_ONLY_ROOTS + project_roots
        if IS_CODEX
        else CODEX_ONLY_ROOTS + project_roots
    )
    return any(abs_path.startswith(os.path.realpath(root) + os.sep) for root in roots)


def discover() -> list[str]:
    skills: list[str] = []
    candidate_paths: list[str] = []
    seen_paths: set[str] = set()
    disabled_plugins = disabled_codex_plugins()
    for pat in discovery_patterns():
        for path in glob.glob(pat):
            if path in seen_paths:
                continue
            if skip_for_runtime(path):
                continue
            seen_paths.add(path)
            candidate_paths.append(path)

    local_plugins = local_plugin_names(candidate_paths)
    candidate_paths = select_current_cache_paths(candidate_paths)
    seen_qualified: set[str] = set()
    for path in candidate_paths:
        if (
            plugin_package_name(path) in local_plugins
            and not is_repo_local_plugin(path)
        ):
            continue
        if skip_for_runtime(path):
            continue
        if codex_plugin_id(path) in disabled_plugins:
            continue
        try:
            with open(path) as f:
                head = f.read(600)
        except OSError:
            continue
        name_m = NAME_RE.search(head)
        if not name_m:
            continue
        name = name_m.group(1).strip()
        desc_m = DESC_RE.search(head)
        desc = desc_m.group(1).strip()[:100] if desc_m else ""

        plugin = plugin_namespace(path)
        if not plugin and is_codex_user_skill(path):
            plugin = "user"

        qualified = f"{plugin}:{name}" if plugin else name
        if qualified not in seen_qualified:
            seen_qualified.add(qualified)
            skills.append(f"{qualified} — {desc}")
    skills.sort()
    return skills


def main() -> int:
    runtime = "codex" if IS_CODEX else "claude"
    result_path = cache_path("skills-discover", f"{runtime}\0{project_root()}", "txt")

    cached = read_text(result_path) if is_fresh(result_path, 300) else None
    if cached is not None and DISCOVERY_CACHE_RE.search(cached):
        sys.stdout.write(cached)
        return 0

    skills = discover()
    out = "\n".join(skills) + f"\n\nTOTAL_SKILLS: {len(skills)}\n"
    atomic_write_text(result_path, out)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

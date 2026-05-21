#!/usr/bin/env python3
"""Auto-discover installed skills across Claude Code, Codex, and this project.

Used by session-review to build the "don't hallucinate skills" allowlist.
Cached to /tmp/mnemo-skills-discover-{cwd_hash}.txt for 300s — skill inventory
rarely changes within a session.
"""
from __future__ import annotations

import glob
import hashlib
import os
import re
import sys
import time
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None

HOME = os.path.expanduser("~")
IS_CODEX = any(os.environ.get(k) for k in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI", "CODEX_SANDBOX"))
PATTERNS = [
    # Claude Code user/plugin scopes.
    os.path.join(HOME, ".claude/skills/*/SKILL.md"),
    os.path.join(HOME, ".claude/plugins/*/skills/*/SKILL.md"),
    os.path.join(HOME, ".claude/plugins/cache/*/*/*/skills/*/SKILL.md"),
    os.path.join(HOME, ".claude/plugins/marketplaces/*/plugins/*/skills/*/SKILL.md"),
    # Codex documented scopes.
    ".agents/skills/*/SKILL.md",
    os.path.join(HOME, ".agents/skills/*/SKILL.md"),
    "/etc/codex/skills/*/SKILL.md",
    # Codex plugin/cache compatibility scopes used by current Codex builds.
    os.path.join(HOME, ".codex/skills/*/SKILL.md"),
    os.path.join(HOME, ".codex/plugins/cache/*/*/*/skills/*/SKILL.md"),
    os.path.join(HOME, ".codex/.tmp/marketplaces/*/plugins/*/skills/*/SKILL.md"),
    ".claude/skills/*/SKILL.md",
    "plugins/*/skills/*/SKILL.md",
]

NAME_RE = re.compile(r'^name:\s*["\']?(.+?)["\']?\s*$', re.M)
DESC_RE = re.compile(r'^description:\s*["\']?(.+?)["\']?\s*$', re.M)


def disabled_codex_plugins() -> set[str]:
    """Return explicit disabled Codex plugin ids like superpowers@marketplace."""
    if tomllib is None:
        return set()

    config_path = os.path.join(HOME, ".codex/config.toml")
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


def codex_plugin_id(path: str) -> str:
    """Map cache/temp skill paths back to plugin@marketplace ids."""
    abs_path = os.path.abspath(path)

    cache_roots = [os.path.join(HOME, ".codex/plugins/cache")]
    if IS_CODEX:
        cache_roots.append(os.path.join(HOME, ".claude/plugins/cache"))
    for cache_root in cache_roots:
        cache_prefix = cache_root + os.sep
        if abs_path.startswith(cache_prefix):
            rel = abs_path[len(cache_prefix):].split(os.sep)
            if len(rel) >= 2:
                marketplace, plugin = rel[0], rel[1]
                return f"{plugin}@{marketplace}"

    tmp_roots = [os.path.join(HOME, ".codex/.tmp/marketplaces")]
    if IS_CODEX:
        tmp_roots.append(os.path.join(HOME, ".claude/plugins/marketplaces"))
    for tmp_root in tmp_roots:
        tmp_prefix = tmp_root + os.sep
        if abs_path.startswith(tmp_prefix):
            rel = abs_path[len(tmp_prefix):].split(os.sep)
            if len(rel) >= 3 and rel[1] == "plugins":
                marketplace, plugin = rel[0], rel[2]
                return f"{plugin}@{marketplace}"

    return ""


def discover() -> list[str]:
    skills: list[str] = []
    seen: set[str] = set()
    disabled_plugins = disabled_codex_plugins()
    for pat in PATTERNS:
        for path in glob.glob(pat):
            if path in seen:
                continue
            seen.add(path)
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

            parts = path.replace(HOME, "~").split("/")
            plugin = ""
            if "plugins" in parts:
                idx = parts.index("plugins")
                candidate = parts[idx + 1] if idx + 1 < len(parts) else ""
                if candidate == "marketplaces" and idx + 3 < len(parts):
                    plugin = parts[idx + 3]
                else:
                    plugin = candidate
            elif ".agents" in parts or ".codex" in parts:
                plugin = "user"

            qualified = f"{plugin}:{name}" if plugin else name
            if qualified not in seen:
                seen.add(qualified)
                skills.append(f"{qualified} — {desc}")
    skills.sort()
    return skills


def main() -> int:
    cwd_hash = hashlib.md5(os.getcwd().encode()).hexdigest()[:10]
    cache_path = f"/tmp/mnemo-skills-discover-{cwd_hash}.txt"

    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < 300:
        with open(cache_path) as f:
            sys.stdout.write(f.read())
        return 0

    skills = discover()
    out = "\n".join(skills) + f"\n\nTOTAL_SKILLS: {len(skills)}\n"
    try:
        with open(cache_path, "w") as f:
            f.write(out)
    except OSError:
        pass
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

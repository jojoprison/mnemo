#!/usr/bin/env python3
"""Resolve the Claude Code autocompact window and report how close the current
session is to it, for hooks/mnemo-autocompact-nudge.sh.

Claude Code only (see docs/design-decisions.md, "Proactive nudges via hooks"):
the effective autocompact threshold is min(settings.autoCompactWindow, the
model's context window), resolved env -> settings -> per-model default, and
Claude Code itself caches the resolved number in ~/.claude.json under
autoCompactWindowsCache. mnemo ships no per-model table — any hardcoded
default would be wrong for someone, since windows range 200k-1M — so W comes
ONLY from sources Claude Code already resolved. If none apply, resolve_window
returns None and the hook stays silent rather than guessing.

Usage: context-window.py TRANSCRIPT_PATH
Prints one tab-separated line: LEVEL\tUSED\tWINDOW
  LEVEL is "unknown" (W or usage unresolved), "none", "warn", or "critical".
"""
from __future__ import annotations

import json
import os
import sys

MARGIN_WARN = 50_000
MARGIN_CRITICAL = 10_000


def _load_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _claude_config_dir() -> str:
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.expanduser("~/.claude")


def resolve_window(cwd: str) -> int | None:
    """env -> project/user settings.json -> ~/.claude.json cache. None if unresolved."""
    env_value = os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    if env_value:
        try:
            parsed = int(env_value)
            if parsed > 0:
                return parsed
        except ValueError:
            pass

    for path in (
        os.path.join(cwd, ".claude", "settings.local.json"),
        os.path.join(cwd, ".claude", "settings.json"),
        os.path.join(_claude_config_dir(), "settings.json"),
    ):
        data = _load_json(path)
        window = data.get("autoCompactWindow") if isinstance(data, dict) else None
        if isinstance(window, (int, float)) and window > 0:
            return int(window)

    data = _load_json(os.path.join(os.path.expanduser("~"), ".claude.json"))
    cache = data.get("autoCompactWindowsCache") if isinstance(data, dict) else None
    if isinstance(cache, (int, float)) and cache > 0:
        return int(cache)
    if isinstance(cache, dict):
        # Shape unconfirmed (never observed non-null) — defensively handle a
        # possible per-model map by taking any positive value it holds.
        for value in cache.values():
            if isinstance(value, (int, float)) and value > 0:
                return int(value)
    return None


def last_usage_tokens(transcript_path: str) -> int | None:
    """Total tokens on the most recent assistant turn's usage block, or None.

    Stop hooks get no token count in stdin (see [[Atom — Stop-хук Claude Code
    не получает токены в stdin]]) — the transcript is the only source.
    """
    total = None
    try:
        with open(transcript_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                message = entry.get("message") if isinstance(entry, dict) else None
                if not isinstance(message, dict) or message.get("role") != "assistant":
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                tokens = sum(
                    usage.get(field) or 0
                    for field in (
                        "input_tokens",
                        "cache_creation_input_tokens",
                        "cache_read_input_tokens",
                    )
                )
                if tokens:
                    total = tokens
    except OSError:
        return None
    return total


def level_for(used: int | None, window: int | None) -> str:
    """none < warn < critical.

    Margins clamp down (never up) on a small window, so the warn/critical
    bands can't eat the whole window when W is small.
    """
    if used is None or window is None or window <= 0:
        return "unknown"
    critical = min(MARGIN_CRITICAL, max(1, window // 10))
    warn = min(MARGIN_WARN, max(critical + 1, window // 4))
    remaining = window - used
    if remaining <= critical:
        return "critical"
    if remaining <= warn:
        return "warn"
    return "none"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: context-window.py TRANSCRIPT_PATH", file=sys.stderr)
        return 2
    used = last_usage_tokens(sys.argv[1])
    window = resolve_window(os.getcwd())
    level = level_for(used, window)
    print("\t".join([
        level,
        str(used) if used is not None else "",
        str(window) if window is not None else "",
    ]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

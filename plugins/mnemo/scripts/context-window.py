#!/usr/bin/env python3
"""Resolve the Claude Code autocompact window and report how close the current
session is to it, for hooks/mnemo-autocompact-nudge.sh.

Claude Code only (see docs/design-decisions.md, "Proactive nudges via hooks").
Claude Code resolves the window as env -> settings -> its own per-model cache
-> the model's context window, and the effective threshold is the minimum of
the configured value and that context window. This module mirrors that, with
one deliberate difference: it never *guesses* the context window.

Why it cannot simply read the model: the transcript records the model id
without its `[1m]` suffix, so a 1M session and a 200k session are written
identically. Assuming 200k for a 1M session would block a turn at 15% full,
which is worse than staying quiet. So the ceiling is claimed only when Claude
Code's own 1M-access cache proves the account cannot have one; otherwise the
window must be configured explicitly, and an unresolved window means silence.

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

# Claude Code validates autoCompactWindow as an int in [100k, 1M] and ignores
# anything outside it — trusting a wider value would nudge against a window
# that is not in force.
WINDOW_MIN = 100_000
WINDOW_MAX = 1_000_000

# Default context window when the account provably has no 1M access.
DEFAULT_CONTEXT_WINDOW = 200_000

# Claude Code compacts before the window is full: it holds back room for the
# reply (min(max_output, 20_000)) plus a 13_000 safety margin.
MAX_OUTPUT_RESERVE = 20_000
SAFETY_RESERVE = 13_000


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


def _valid_window(value) -> int | None:
    """An int in [100k, 1M], the range Claude Code itself accepts."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = int(value)
    return number if WINDOW_MIN <= number <= WINDOW_MAX else None


def _claude_state_path() -> str:
    return os.path.join(_claude_config_dir(), os.pardir, ".claude.json")


def _claude_state() -> dict:
    # ~/.claude.json sits beside ~/.claude, and follows CLAUDE_CONFIG_DIR with it.
    data = _load_json(os.path.normpath(_claude_state_path()))
    return data if isinstance(data, dict) else {}


def context_window_ceiling() -> int | None:
    """The model's context window, or None when it cannot be established.

    Only the provable direction is used: if Claude Code's own 1M-access cache
    says this account has no large-context access, the ceiling is the standard
    window. Access present, cache absent, or an unfamiliar shape all mean "not
    established" — the caller then stays silent instead of guessing low.
    """
    cache = _claude_state().get("s1mAccessCache")
    if not isinstance(cache, dict) or not cache:
        return None
    for entry in cache.values():
        if not isinstance(entry, dict) or not isinstance(entry.get("hasAccess"), bool):
            return None
        if entry["hasAccess"]:
            return None
    return DEFAULT_CONTEXT_WINDOW


def _cached_window(model: str | None) -> int | None:
    """autoCompactWindowsCache keyed by model, the way Claude Code reads it.

    A number filed under another model is that model's window; borrowing it is
    how a 1M value silences a 200k session, or a 200k value fires a false
    critical on a 1M one.
    """
    cache = _claude_state().get("autoCompactWindowsCache")
    if not isinstance(cache, dict) or not model:
        return None
    entry = cache.get(model)
    if isinstance(entry, dict):
        entry = entry.get("default")
    return _valid_window(entry)


def _settings_chain(cwd: str):
    """Settings files in Claude Code's own precedence order, nearest first."""
    for path in (
        os.path.join(cwd, ".claude", "settings.local.json"),
        os.path.join(cwd, ".claude", "settings.json"),
        os.path.join(_claude_config_dir(), "settings.local.json"),
        os.path.join(_claude_config_dir(), "settings.json"),
    ):
        data = _load_json(path)
        if isinstance(data, dict):
            yield data


def autocompact_enabled(cwd: str) -> bool:
    """False only when a setting says so — with autocompact off there is no
    window to warn about, and the warning's own wording would be untrue."""
    for data in _settings_chain(cwd):
        value = data.get("autoCompactEnabled")
        if isinstance(value, bool):
            return value
    return True


def _configured_window(cwd: str, model: str | None) -> int | None:
    """env -> project/user settings.json -> Claude Code's per-model cache."""
    env_value = os.environ.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW")
    if env_value:
        try:
            window = _valid_window(int(env_value))
        except ValueError:
            window = None
        if window is not None:
            return window

    for data in _settings_chain(cwd):
        window = _valid_window(data.get("autoCompactWindow"))
        if window is not None:
            return window

    return _cached_window(model)


def resolve_window(
    cwd: str, transcript_path: str | None = None, model: str | None = None
) -> int | None:
    """The window actually in force, or None when it cannot be established.

    Mirrors Claude Code: a configured value is a *ceiling request*, not the
    threshold — the effective window is min(configured, context window). A 460k
    setting on a 200k session therefore resolves to 200k, which is exactly the
    case where an unclamped value would nudge long after the real compaction.
    """
    if not autocompact_enabled(cwd):
        return None
    if model is None and transcript_path:
        model = last_model(transcript_path)
    configured = _configured_window(cwd, model)
    ceiling = context_window_ceiling()
    if configured is None:
        return ceiling
    if ceiling is None:
        return configured
    return min(configured, ceiling)


def scan_transcript(transcript_path: str) -> tuple[int | None, str | None]:
    """One pass over the transcript for (tokens used, model of the last turn).

    Stop hooks carry no token count in stdin — the transcript is the only
    source, and it is read once because a long session's file reaches hundreds
    of megabytes. The token sum is the same one Claude Code uses for its own
    status line: input + cache_creation + cache_read, output_tokens excluded.
    """
    total = None
    model = None
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
                if isinstance(message.get("model"), str) and message["model"]:
                    model = message["model"]
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
        return None, None
    return total, model


def last_usage_tokens(transcript_path: str) -> int | None:
    return scan_transcript(transcript_path)[0]


def last_model(transcript_path: str) -> str | None:
    return scan_transcript(transcript_path)[1]


def compaction_reserve(window: int) -> int:
    """Tokens Claude Code holds back before the window is full.

    Its own arithmetic is `window - min(max_output, 20_000) - 13_000`. The
    reserve is additionally clamped against a small window, so it can never
    swallow the whole thing.
    """
    return min(MAX_OUTPUT_RESERVE + SAFETY_RESERVE, max(1, window // 4))


def level_for(used: int | None, window: int | None) -> str:
    """none < warn < critical.

    Bands are measured from the point compaction actually happens, not from the
    window itself: measured from W, "critical" would sit past a threshold the
    session can never reach, making the whole band dead. Margins clamp down
    (never up) on a small window, so they can't eat the whole thing either.
    """
    if used is None or window is None or window <= 0:
        return "unknown"
    if used > window:
        # A session cannot hold more than its window, so the window resolved
        # here is not the one in force. Silence beats blocking on a bad reading.
        return "unknown"
    threshold = max(1, window - compaction_reserve(window))
    critical = min(MARGIN_CRITICAL, max(1, threshold // 10))
    warn = min(MARGIN_WARN, max(critical + 1, threshold // 4))
    remaining = threshold - used
    if remaining <= critical:
        return "critical"
    if remaining <= warn:
        return "warn"
    return "none"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: context-window.py TRANSCRIPT_PATH", file=sys.stderr)
        return 2
    used, model = scan_transcript(sys.argv[1])
    window = resolve_window(os.getcwd(), model=model)
    level = level_for(used, window)
    print("\t".join([
        level,
        str(used) if used is not None else "",
        str(window) if window is not None else "",
    ]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

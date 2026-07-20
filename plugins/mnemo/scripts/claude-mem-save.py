#!/usr/bin/env python3
"""Probe claude-mem or save one observation from shell-safe JSON stdin."""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, NamedTuple

from cache_utils import configured_root


MAX_INPUT_BYTES = 1024 * 1024


class ClaudeMemProbe(NamedTuple):
    version: str
    stale: int
    path: str


def required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def optional_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def version_key(value: str) -> list[tuple[int, int | str]]:
    # Tagged tuples remain comparable even if cache directory names mix
    # numeric and non-numeric components (for example, prerelease builds).
    return [
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", value)
    ]


def claude_mem_cache_root(home: str | None = None) -> Path:
    config_root = configured_root("CLAUDE_CONFIG_DIR", ".claude", home)
    return Path(config_root) / "plugins/cache/thedotmack/claude-mem"


def claude_mem_probe(home: str | None = None) -> ClaudeMemProbe:
    root = claude_mem_cache_root(home)
    try:
        installed = root.is_dir()
    except OSError:
        installed = False
    if not installed:
        return ClaudeMemProbe("", 0, "")

    try:
        versions = [path.name for path in root.iterdir() if path.is_dir()]
    except OSError:
        versions = []
    latest = max(versions, key=version_key) if versions else ""
    return ClaudeMemProbe(latest, max(0, len(versions) - 1), str(root))


def claude_mem_version(home: str | None = None) -> str:
    return claude_mem_probe(home).version or "unknown"


def print_claude_mem_probe(home: str | None = None) -> None:
    probe = claude_mem_probe(home)
    print("version:" + (f" {probe.version}" if probe.version else ""))
    print(f"stale: {probe.stale}")
    print("path:" + (f" {probe.path}" if probe.path else ""))


def build_payload(value: dict[str, Any], *, version: str | None = None) -> tuple[str, dict[str, Any]]:
    url = required_text(value, "url").rstrip("/")
    item_type = required_text(value, "type")
    project = required_text(value, "project")
    summary = required_text(value, "summary")
    note = optional_text(value, "note")
    vault = optional_text(value, "vault")
    detected = version or claude_mem_version()
    text = f"{summary} [note: {note or '—'} | vault: {vault or '—'} | cm: {detected}]"
    return f"{url}/api/memory/save", {
        "text": text,
        "metadata": {
            "type": item_type,
            "project": project,
            "obsidian_note": note,
            "obsidian_vault": vault,
            "claude_mem_version": detected,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--probe"]:
        print_claude_mem_probe()
        return 0
    if args:
        print("usage: claude-mem-save.py [--probe]", file=sys.stderr)
        return 2

    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        print("claude-mem-save: input exceeds 1 MiB", file=sys.stderr)
        return 2
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("input must be a JSON object")
        url, payload = build_payload(value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"claude-mem-save: {exc}", file=sys.stderr)
        return 2

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            sys.stdout.buffer.write(response.read())
            return 0
    except urllib.error.HTTPError as exc:
        sys.stdout.buffer.write(exc.read())
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"claude-mem-save: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

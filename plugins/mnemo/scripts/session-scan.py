#!/usr/bin/env python3
"""Scan Claude Code or Codex session JSONL for tool usage and modified files.

Reads CLAUDE_SESSION_ID, CODEX_THREAD_ID, or legacy CODEX_SESSION_ID from env.
If none is present, falls back to the newest Codex rollout JSONL for the current cwd.

Two-layer caching in a private per-user temp directory:
- Fresh cache (<60s old) → reuse as-is, no re-read.
- Older cache + stored byte offset → read only appended JSONL bytes since
  offset, merge into cached aggregate. Works because JSONL is append-only.
"""
from __future__ import annotations

import glob
import io
import json
import os
import re
import sys
import time

from cache_utils import atomic_write_json, cache_path, configured_root, is_fresh, read_json


FRESH_TTL = 60  # seconds
CODEX_SKILL_RE = re.compile(
    r"(?im)^\s*(?:(?:please\s+)?(?:use|run|invoke)\s+)?\$"
    r"([a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?::[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)?)"
    r"(?![\w:*-])"
)
SIGNAL_RE = re.compile(
    r"fixed|solved|resolved|root cause|decided|gotcha|починил|решил|разобрал|決定",
    re.IGNORECASE,
)
CLAUDE_COMMAND_RE = re.compile(
    r"<command-name>\s*/([a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
    r"(?::[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)?)\s*</command-name>",
    re.IGNORECASE,
)


def safe_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def find_claude_jsonl(session_id: str) -> str | None:
    config_root = configured_root("CLAUDE_CONFIG_DIR", ".claude")
    for d in glob.glob(os.path.join(config_root, "projects/*/")):
        candidate = os.path.join(d, session_id + ".jsonl")
        if os.path.exists(candidate):
            return candidate
    return None


def find_codex_jsonl(session_id: str = "") -> str | None:
    config_root = configured_root("CODEX_HOME", ".codex")
    filename = f"*{glob.escape(session_id)}*.jsonl" if session_id else "*.jsonl"
    candidates = sorted(
        glob.glob(os.path.join(config_root, "sessions/**", filename), recursive=True),
        key=safe_mtime,
        reverse=True,
    )
    cwd = os.getcwd()
    for path in candidates:
        if session_id and session_id not in os.path.basename(path):
            continue
        try:
            with open(path) as f:
                for _ in range(20):
                    line = f.readline()
                    if not line:
                        break
                    msg = json.loads(line)
                    payload = msg.get("payload", {})
                    if msg.get("type") == "session_meta" and payload.get("cwd") == cwd:
                        return path
        except (OSError, json.JSONDecodeError):
            continue
    # Never fall back to an unrelated task. With a runtime session id, only
    # that exact task in this cwd is valid; without one, the loop above has
    # already selected the newest task whose session_meta cwd matches.
    return None


def empty_acc() -> dict:
    return {
        "tools": {},
        "skills": [],
        "commits": 0,
        "files_written": [],
        "errors": 0,
        "signals": 0,
    }


def valid_acc(value: object) -> bool:
    """Reject poisoned or stale cache shapes before they influence review."""
    if not isinstance(value, dict):
        return False
    counters = ("commits", "errors", "signals")
    if any(not isinstance(value.get(key), int) or value[key] < 0 for key in counters):
        return False
    tools = value.get("tools")
    if not isinstance(tools, dict) or any(
        not isinstance(key, str) or not isinstance(count, int) or count < 0
        for key, count in tools.items()
    ):
        return False
    return all(
        isinstance(value.get(key), list)
        and all(isinstance(item, str) for item in value[key])
        for key in ("skills", "files_written")
    )


def non_documentation_text(text: str) -> str:
    """Remove fenced examples and quoted documentation before skill detection."""
    lines: list[str] = []
    fence = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else ""
        if marker:
            if not fence:
                fence = marker
            elif fence == marker:
                fence = ""
            continue
        if fence or stripped.startswith(">"):
            continue
        lines.append(line)
    return "\n".join(lines)


def parse_claude_message(msg: dict, acc: dict) -> None:
    tools = acc["tools"]
    skills = acc["skills"]
    files_written = set(acc["files_written"])
    content = msg.get("message", {}).get("content", [])
    if isinstance(content, str):
        if SIGNAL_RE.search(content):
            acc["signals"] = acc.get("signals", 0) + 1
        for skill in CLAUDE_COMMAND_RE.findall(content):
            if skill not in skills:
                skills.append(skill)
        return
    if not isinstance(content, list):
        return
    text = "\n".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )
    if SIGNAL_RE.search(text):
        acc["signals"] = acc.get("signals", 0) + 1
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "tool_use":
            name = block.get("name", "")
            tools[name] = tools.get(name, 0) + 1
            inp = block.get("input", {})
            if name == "Skill":
                s = inp.get("skill", "")
                if s:
                    skills.append(s)
            elif name in ("Write", "Edit"):
                fp = inp.get("file_path", "")
                if fp:
                    files_written.add(fp)
            elif name == "Bash":
                cmd = inp.get("command", "")
                if "git commit" in cmd:
                    acc["commits"] = acc.get("commits", 0) + 1
        elif btype == "tool_result" and block.get("is_error"):
            acc["errors"] = acc.get("errors", 0) + 1
    acc["files_written"] = sorted(files_written)


def parse_codex_message(msg: dict, acc: dict) -> None:
    if msg.get("type") != "response_item":
        return
    payload = msg.get("payload", {})
    payload_type = payload.get("type")

    if payload_type == "message":
        texts: list[str] = []
        for block in payload.get("content", []):
            if not isinstance(block, dict):
                continue
            text = block.get("text") or block.get("input_text") or block.get("output_text") or ""
            if text:
                texts.append(str(text))
        combined = "\n".join(texts)
        if payload.get("role") in ("user", "assistant") and SIGNAL_RE.search(combined):
            acc["signals"] = acc.get("signals", 0) + 1
        if payload.get("role") == "user":
            for skill in CODEX_SKILL_RE.findall(non_documentation_text(combined)):
                if skill not in acc["skills"]:
                    acc["skills"].append(skill)
        return

    if payload_type in ("function_call", "custom_tool_call"):
        name = payload.get("name", "")
        if not name:
            return
        tools = acc["tools"]
        tools[name] = tools.get(name, 0) + 1
        if name == "apply_patch":
            acc["files_written"] = sorted(set(acc["files_written"]) | {"patch"})
            return
        if name not in ("exec", "exec_command", "spawn_agent"):
            return

        raw_input = payload.get("input") or payload.get("arguments") or ""
        if isinstance(raw_input, dict):
            args = raw_input
            raw_text = json.dumps(raw_input)
        else:
            raw_text = str(raw_input)
            try:
                args = json.loads(raw_text or "{}")
            except json.JSONDecodeError:
                args = {}
        if name == "exec" and "apply_patch" in raw_text:
            acc["files_written"] = sorted(set(acc["files_written"]) | {"patch"})
        elif name == "exec_command":
            cmd = args.get("cmd", "")
            if "git commit" in cmd:
                acc["commits"] = acc.get("commits", 0) + 1
        elif name == "exec" and "git commit" in raw_text:
            acc["commits"] = acc.get("commits", 0) + 1
        elif name == "spawn_agent":
            agent_type = args.get("agent_type", "default")
            acc["skills"].append(f"subagent:{agent_type}")
    elif payload_type in ("function_call_output", "custom_tool_call_output"):
        output = payload.get("output", "")
        if "Process exited with code 1" in output or "Error:" in output:
            acc["errors"] = acc.get("errors", 0) + 1


def parse_lines(handle, acc: dict) -> None:
    """Accumulate counts from each JSONL line. Modifies acc in place."""
    for line in handle:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "message" in msg:
            parse_claude_message(msg, acc)
        else:
            parse_codex_message(msg, acc)


def session_cache_paths(session_id: str, jsonl_path: str):
    identity = f"{os.path.realpath(jsonl_path)}\0{session_id}"
    return (
        cache_path("session-scan", identity, "json"),
        cache_path("session-offset", identity, "json"),
    )


def scan_incremental(jsonl_path: str, session_id: str) -> dict:
    result_path, offset_path = session_cache_paths(session_id, jsonl_path)

    prev_acc: dict | None = None
    prev_offset = 0

    cached_acc = read_json(result_path)
    cached_offset = read_json(offset_path)
    if valid_acc(cached_acc) and isinstance(cached_offset, dict):
        offset_value = cached_offset.get("offset")
        if isinstance(offset_value, int) and offset_value >= 0:
            prev_acc = cached_acc
            prev_offset = offset_value

    try:
        file_size = os.path.getsize(jsonl_path)
    except OSError:
        return prev_acc or empty_acc()

    # Previous offset beyond file size → file rotated / truncated; re-scan from 0.
    if prev_offset > file_size:
        prev_acc = None
        prev_offset = 0

    acc = prev_acc if prev_acc is not None else empty_acc()

    # Offsets are bytes, matching getsize(). Do not advance past a JSONL record
    # that is still being appended; otherwise its completed form is lost forever.
    with open(jsonl_path, "rb") as handle:
        handle.seek(prev_offset)
        chunk = handle.read()

    consumed = len(chunk)
    if chunk and not chunk.endswith(b"\n"):
        tail_start = chunk.rfind(b"\n") + 1
        tail = chunk[tail_start:]
        try:
            json.loads(tail.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            chunk = chunk[:tail_start]
            consumed = tail_start

    parse_lines(io.StringIO(chunk.decode("utf-8", errors="replace")), acc)
    new_offset = prev_offset + consumed

    atomic_write_json(result_path, acc)
    atomic_write_json(offset_path, {"offset": new_offset, "mtime": time.time()})

    return acc


def render(result: dict) -> None:
    tools = result.get("tools", {})
    print(f"TOTAL_TOOL_CALLS: {sum(tools.values())}")
    for t, c in sorted(tools.items(), key=lambda x: -x[1])[:20]:
        print(f"  {t}: {c}")
    skills = result.get("skills", [])
    print(f"\nSKILLS_INVOKED: {', '.join(skills) if skills else 'none'}")
    files_written = result.get("files_written", [])
    print(f"FILES_MODIFIED: {len(files_written)}")
    if files_written:
        exts: dict[str, int] = {}
        for fp in files_written:
            ext = os.path.splitext(fp)[1] or "no-ext"
            exts[ext] = exts.get(ext, 0) + 1
        exts_str = ", ".join(f"{e}({c})" for e, c in sorted(exts.items(), key=lambda x: -x[1]))
        print(f"  Extensions: {exts_str}")
        for fp in files_written[:15]:
            print(f"  {fp}")
    print(f"COMMITS: {result.get('commits', 0)}")
    print(f"ERRORS_SEEN: {result.get('errors', 0)}")
    print(f"WORTH_SAVING_SIGNALS: {result.get('signals', 0)}")


def stop_summary(jsonl_path: str) -> tuple[int, int, int]:
    """Return actual save/session invocations and message-level save signals."""
    acc = empty_acc()
    try:
        with open(jsonl_path) as handle:
            parse_lines(handle, acc)
    except OSError:
        return 0, 0, 0
    skills = set(acc.get("skills", []))
    saved = bool(skills & {"save", "mn:save", "mnemo:save"})
    sessioned = bool(skills & {"session", "mn:session", "mnemo:session"})
    return int(saved), int(sessioned), int(acc.get("signals", 0))


def runtime_session_id() -> str:
    return (
        os.environ.get("CLAUDE_SESSION_ID")
        or os.environ.get("CODEX_THREAD_ID")
        or os.environ.get("CODEX_SESSION_ID", "")
    )


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--stop-summary":
        print(*stop_summary(sys.argv[2]))
        return 0
    if len(sys.argv) > 1:
        print("usage: session-scan.py [--stop-summary JSONL]", file=sys.stderr)
        return 2

    session_id = runtime_session_id()
    if not session_id:
        jsonl_path = find_codex_jsonl()
        if not jsonl_path:
            print("SESSION_ID: not available")
            return 0
        session_id = os.path.splitext(os.path.basename(jsonl_path))[0]
    else:
        jsonl_path = find_claude_jsonl(session_id) or find_codex_jsonl(session_id)

    if not jsonl_path:
        print("JSONL: not found — use conversation context for analysis")
        return 0

    result_path, _ = session_cache_paths(session_id, jsonl_path)
    cached_acc = read_json(result_path) if is_fresh(result_path, FRESH_TTL) else None
    if valid_acc(cached_acc):
        render(cached_acc)
        return 0

    result = scan_incremental(jsonl_path, session_id)
    render(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

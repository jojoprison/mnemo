#!/usr/bin/env python3
"""Scan Claude Code or Codex session JSONL for tool usage and modified files.

Reads CLAUDE_SESSION_ID or CODEX_SESSION_ID from env. If neither is present,
falls back to the newest Codex rollout JSONL for the current cwd.

Two-layer caching:
- Fresh cache (<60s old) → reuse as-is, no re-read.
- Older cache + stored byte offset → read only appended JSONL bytes since
  offset, merge into cached aggregate. Works because JSONL is append-only.

Files under /tmp/:
- mnemo-session-scan-{id}.json — aggregated result
- mnemo-session-offset-{id}.json — {"offset": N, "mtime": ...}
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time


FRESH_TTL = 60  # seconds


def find_claude_jsonl(session_id: str) -> str | None:
    home = os.path.expanduser("~")
    for d in glob.glob(os.path.join(home, ".claude/projects/*/")):
        candidate = os.path.join(d, session_id + ".jsonl")
        if os.path.exists(candidate):
            return candidate
    return None


def find_codex_jsonl(session_id: str = "") -> str | None:
    home = os.path.expanduser("~")
    candidates = sorted(
        glob.glob(os.path.join(home, ".codex/sessions/**/*.jsonl"), recursive=True),
        key=os.path.getmtime,
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
    return candidates[0] if candidates else None


def empty_acc() -> dict:
    return {
        "tools": {},
        "skills": [],
        "commits": 0,
        "files_written": [],
        "errors": 0,
    }


def parse_claude_message(msg: dict, acc: dict) -> None:
    tools = acc["tools"]
    skills = acc["skills"]
    files_written = set(acc["files_written"])
    content = msg.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return
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
    if payload.get("type") == "function_call":
        name = payload.get("name", "")
        if not name:
            return
        tools = acc["tools"]
        tools[name] = tools.get(name, 0) + 1
        try:
            args = json.loads(payload.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        if name == "apply_patch":
            acc["files_written"] = sorted(set(acc["files_written"]) | {"patch"})
        elif name == "exec_command":
            cmd = args.get("cmd", "")
            if "git commit" in cmd:
                acc["commits"] = acc.get("commits", 0) + 1
        elif name == "spawn_agent":
            agent_type = args.get("agent_type", "default")
            acc["skills"].append(f"subagent:{agent_type}")
    elif payload.get("type") == "function_call_output":
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


def scan_incremental(jsonl_path: str, session_id: str) -> dict:
    cache_path = f"/tmp/mnemo-session-scan-{session_id}.json"
    offset_path = f"/tmp/mnemo-session-offset-{session_id}.json"

    prev_acc: dict | None = None
    prev_offset = 0

    if os.path.exists(cache_path) and os.path.exists(offset_path):
        try:
            with open(cache_path) as f:
                prev_acc = json.load(f)
            with open(offset_path) as f:
                prev_offset = int(json.load(f).get("offset", 0))
        except (OSError, ValueError, json.JSONDecodeError):
            prev_acc = None
            prev_offset = 0

    try:
        file_size = os.path.getsize(jsonl_path)
    except OSError:
        return prev_acc or empty_acc()

    # Previous offset beyond file size → file rotated / truncated; re-scan from 0.
    if prev_offset > file_size:
        prev_acc = None
        prev_offset = 0

    acc = prev_acc if prev_acc is not None else empty_acc()

    with open(jsonl_path) as f:
        f.seek(prev_offset)
        parse_lines(f, acc)
        new_offset = f.tell()

    try:
        with open(cache_path, "w") as f:
            json.dump(acc, f)
        with open(offset_path, "w") as f:
            json.dump({"offset": new_offset, "mtime": time.time()}, f)
    except OSError:
        pass

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


def main() -> int:
    session_id = os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CODEX_SESSION_ID", "")
    if not session_id:
        jsonl_path = find_codex_jsonl()
        if not jsonl_path:
            print("SESSION_ID: not available")
            return 0
        session_id = os.path.splitext(os.path.basename(jsonl_path))[0]
    else:
        jsonl_path = find_claude_jsonl(session_id) or find_codex_jsonl(session_id)

    cache_path = f"/tmp/mnemo-session-scan-{session_id}.json"
    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < FRESH_TTL:
        try:
            with open(cache_path) as f:
                render(json.load(f))
            return 0
        except (OSError, json.JSONDecodeError):
            pass  # fall through to re-scan

    if not jsonl_path:
        print("JSONL: not found — use conversation context for analysis")
        return 0

    result = scan_incremental(jsonl_path, session_id)
    render(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

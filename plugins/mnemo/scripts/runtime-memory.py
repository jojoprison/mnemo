#!/usr/bin/env python3
"""Bounded, read-only recall across Claude Code and Codex local memories.

The helper never writes, caches, follows symlinks, scans transcript bodies, or
falls back to another project.  Runtime memory is untrusted evidence; Obsidian
remains mnemo's human-authored source of truth.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, NamedTuple


SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 16_384
MAX_QUERY_BYTES = 8_192
MAX_FILE_BYTES = 256 * 1024
MAX_SESSION_METADATA_BYTES = 64 * 1024
MAX_GLOBAL_SCAN_BYTES = 4 * 1024 * 1024
MAX_GLOBAL_FILES = 200
MAX_INDEX_LINKS = 50
HARD_MAX_HITS = 7
HARD_MAX_EXCERPT_BYTES = 12_288
HARD_MAX_OUTPUT_BYTES = 32_768
PER_HIT_BYTES = 2_048

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]+)?\)")
TASK_GROUP_RE = re.compile(r"(?m)^# Task Group: (.+?)\s*$")
CWD_RE = re.compile(r"(?:^|[;\s])cwd=([^;,\n]+)")
SECRET_NAME_PARTS = (
    "credential",
    "password",
    "secret",
    "token",
    "api-key",
    "api_key",
    "apikey",
    "private-key",
    "private_key",
    "ssh-key",
    "ssh_key",
    "id_rsa",
    "access-token",
    "refresh-token",
    "break-glass",
    "keychain",
    ".env",
)


class ProjectContext(NamedTuple):
    current_root: Path
    canonical_root: Path
    common_dir: Path
    project_id: str


class Limits(NamedTuple):
    max_hits: int
    max_excerpt_bytes: int


def _run_git(cwd: Path, *args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def project_context(cwd: Path) -> ProjectContext | None:
    try:
        resolved_cwd = cwd.resolve(strict=True)
    except OSError:
        return None
    top_raw = _run_git(resolved_cwd, "rev-parse", "--show-toplevel")
    common_raw = _run_git(resolved_cwd, "rev-parse", "--git-common-dir")
    if not top_raw or not common_raw:
        return None
    try:
        current_root = Path(top_raw).resolve(strict=True)
        common_path = Path(common_raw)
        if not common_path.is_absolute():
            # Git reports --git-common-dir relative to the invocation cwd, not
            # necessarily relative to the repository top level.
            common_path = resolved_cwd / common_path
        common_dir = common_path.resolve(strict=True)
    except OSError:
        return None
    canonical_root = common_dir.parent if common_dir.name == ".git" else current_root
    project_id = hashlib.sha256(str(common_dir).encode()).hexdigest()[:16]
    return ProjectContext(current_root, canonical_root, common_dir, project_id)


def _same_project(candidate_cwd: str, context: ProjectContext) -> bool:
    try:
        candidate = Path(candidate_cwd).expanduser().resolve(strict=True)
    except OSError:
        return False
    if candidate in {context.current_root, context.canonical_root}:
        return True
    other = project_context(candidate)
    return other is not None and other.common_dir == context.common_dir


def _owned_by_current_user(path_stat: os.stat_result) -> bool:
    return not hasattr(path_stat, "st_uid") or path_stat.st_uid == os.getuid()


def _safe_directory(path: Path) -> Path | None:
    try:
        if path.is_symlink():
            return None
        resolved = path.resolve(strict=True)
        info = path.stat()
    except OSError:
        return None
    if not stat.S_ISDIR(info.st_mode) or not _owned_by_current_user(info):
        return None
    return resolved


def _safe_contained_path(
    root: Path,
    candidate: Path,
    expected_type: Callable[[int], bool],
) -> Path | None:
    safe_root = _safe_directory(root)
    if safe_root is None:
        return None
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return None
    current = root
    try:
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                return None
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(safe_root)
        info = candidate.stat()
    except (OSError, ValueError):
        return None
    if not expected_type(info.st_mode) or not _owned_by_current_user(info):
        return None
    return resolved


def _safe_subdirectory(root: Path, candidate: Path) -> Path | None:
    return _safe_contained_path(root, candidate, stat.S_ISDIR)


def _safe_file_path(root: Path, candidate: Path) -> Path | None:
    return _safe_contained_path(root, candidate, stat.S_ISREG)


def _read_file(
    root: Path,
    candidate: Path,
    *,
    limit: int,
    allow_larger: bool = False,
) -> tuple[str | None, str | None]:
    safe_path = _safe_file_path(root, candidate)
    if safe_path is None:
        return None, "unsafe_path"
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(safe_path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not _owned_by_current_user(info):
                return None, "unsafe_file"
            if not allow_larger and info.st_size > limit:
                return None, "oversized_file"
            data = os.read(fd, limit + 1)
        finally:
            os.close(fd)
    except OSError:
        return None, "read_failed"
    if len(data) > limit:
        data = data[:limit]
        reason = "truncated_file"
    else:
        reason = None
    return data.decode("utf-8", errors="replace"), reason


def _mtime(path: Path) -> str:
    try:
        value = path.stat().st_mtime
    except OSError:
        return ""
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _claude_slug(path: Path) -> str:
    return str(path).replace(os.sep, "-")


def _extract_session_cwd(obj: Any) -> str | None:
    if not isinstance(obj, dict):
        return None
    for candidate in (
        obj.get("cwd"),
        (obj.get("session_meta") or {}).get("cwd")
        if isinstance(obj.get("session_meta"), dict)
        else None,
        (obj.get("payload") or {}).get("cwd")
        if isinstance(obj.get("payload"), dict)
        else None,
    ):
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _verified_claude_project(
    projects_root: Path,
    project_dir: Path,
    context: ProjectContext,
) -> bool:
    safe_project = _safe_subdirectory(projects_root, project_dir)
    if safe_project is None:
        return False
    try:
        sessions = sorted(
            (
                path
                for path in safe_project.iterdir()
                if path.name.endswith(".jsonl") and not path.is_symlink()
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:20]
    except OSError:
        return False
    for session in sessions:
        text, _ = _read_file(
            safe_project,
            session,
            limit=MAX_SESSION_METADATA_BYTES,
            allow_larger=True,
        )
        if text is None:
            continue
        # Session metadata is at the start. Never search or return transcript bodies.
        for line in text.splitlines()[:32]:
            try:
                cwd = _extract_session_cwd(json.loads(line))
            except json.JSONDecodeError:
                continue
            if cwd and _same_project(cwd, context):
                return True
    return False


def _claude_config_dir(home: Path, env: dict[str, str]) -> Path:
    raw = env.get("CLAUDE_CONFIG_DIR")
    if not raw:
        return home / ".claude"
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw) if Path(raw).is_absolute() else home / raw


def _claude_memory_root(
    home: Path,
    env: dict[str, str],
    context: ProjectContext,
) -> tuple[Path | None, str | None]:
    config_dir = _claude_config_dir(home, env)
    projects_root = config_dir / "projects"
    safe_projects = _safe_subdirectory(config_dir, projects_root)
    if safe_projects is None:
        return None, "claude_project_unverified"
    candidates = [
        safe_projects / _claude_slug(context.canonical_root),
    ]
    if context.current_root != context.canonical_root:
        candidates.append(safe_projects / _claude_slug(context.current_root))
    for project_dir in dict.fromkeys(candidates):
        if not _verified_claude_project(safe_projects, project_dir, context):
            continue
        memory_dir = project_dir / "memory"
        safe_memory = _safe_subdirectory(project_dir, memory_dir)
        if safe_memory is not None:
            return safe_memory, None
    return None, "claude_project_unverified"


def _term_score(text: str, terms: list[str]) -> int:
    folded = text.casefold()
    score = 0
    for term in terms:
        count = folded.count(term.casefold())
        if count:
            score += 10 + min(count, 20)
    return score


def _truncate_utf8(text: str, byte_limit: int) -> tuple[str, bool]:
    encoded = text.encode("utf-8")
    if len(encoded) <= byte_limit:
        return text, False
    return encoded[:byte_limit].decode("utf-8", errors="ignore"), True


def _excerpt(text: str, terms: list[str], byte_limit: int = PER_HIT_BYTES) -> tuple[str, bool]:
    folded = text.casefold()
    positions = [folded.find(term.casefold()) for term in terms]
    positions = [position for position in positions if position >= 0]
    start = max(0, (min(positions) if positions else 0) - 280)
    sample = text[start : start + byte_limit * 2]
    return _truncate_utf8(sample.strip(), byte_limit)


def _hit(
    *,
    backend: str,
    context: ProjectContext,
    path: Path,
    title: str,
    text: str,
    terms: list[str],
    score: int,
    section: str = "",
) -> tuple[dict[str, Any], bool]:
    excerpt, truncated = _excerpt(text, terms)
    return (
        {
            "backend": backend,
            "project_id": context.project_id,
            "source_path": str(path),
            "section": section,
            "title": title,
            "updated_at": _mtime(path),
            "trust": "runtime-generated-untrusted",
            "score": score,
            "excerpt": excerpt,
        },
        truncated,
    )


def _markdown_links(index_text: str) -> list[tuple[str, str, str]]:
    links: list[tuple[str, str, str]] = []
    for line in index_text.splitlines():
        for match in LINK_RE.finditer(line):
            label, target = match.groups()
            if "://" in target or target.startswith(("/", "~")):
                continue
            links.append((label, target, line))
            if len(links) >= MAX_INDEX_LINKS:
                return links
    return links


def _claude_project_hits(
    memory_dir: Path,
    context: ProjectContext,
    terms: list[str],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    hits: list[dict[str, Any]] = []
    warnings: list[str] = []
    truncated = False
    index_path = memory_dir / "MEMORY.md"
    index_text, reason = _read_file(memory_dir, index_path, limit=MAX_FILE_BYTES)
    if index_text is None:
        return [], [f"claude_index_{reason or 'unavailable'}"], reason == "oversized_file"
    if reason:
        warnings.append(f"claude_index_{reason}")
        truncated = True
    index_score = _term_score(index_text, terms)
    if index_score:
        item, clipped = _hit(
            backend="claude-project",
            context=context,
            path=index_path,
            title="MEMORY.md",
            text=index_text,
            terms=terms,
            score=index_score,
        )
        hits.append(item)
        truncated |= clipped

    index_links = _markdown_links(index_text)
    indexes = [(index_path, index_text, index_links)]
    archive_target = next(
        (
            target
            for _, target, _ in index_links
            if Path(target).name == "MEMORY-archive-index.md"
        ),
        None,
    )
    if archive_target:
        archive_path = memory_dir / archive_target
        archive_text, archive_reason = _read_file(
            memory_dir, archive_path, limit=MAX_FILE_BYTES
        )
        if archive_text is not None:
            indexes.append((archive_path, archive_text, _markdown_links(archive_text)))
        if archive_reason:
            warnings.append(f"claude_archive_{archive_reason}")
            truncated = True

    seen_targets: set[Path] = set()
    candidates: list[tuple[int, str, str]] = []
    for _, _, links in indexes:
        for label, target, line in links:
            target_path = Path(target)
            if target_path.name == "MEMORY-archive-index.md":
                continue
            score = _term_score(f"{label} {target} {line}", terms)
            if score:
                candidates.append((score, target, label))
    candidates.sort(key=lambda item: (-item[0], item[1]))

    for link_score, target, label in candidates:
        candidate = memory_dir / target
        try:
            canonical = candidate.resolve(strict=False)
        except OSError:
            continue
        if canonical in seen_targets:
            continue
        seen_targets.add(canonical)
        text, read_reason = _read_file(memory_dir, candidate, limit=MAX_FILE_BYTES)
        if text is None:
            if read_reason == "oversized_file":
                truncated = True
            continue
        if read_reason:
            truncated = True
        score = _term_score(text, terms)
        item, clipped = _hit(
            backend="claude-project",
            context=context,
            path=candidate,
            title=label or Path(target).name,
            text=text,
            terms=terms,
            score=link_score + score,
        )
        # A topic is relevant when its index entry matches even if the topic
        # body uses different wording. The index is Claude's native routing
        # contract; do not require the query to be duplicated in the body.
        hits.append(item)
        truncated |= clipped
    return hits, warnings, truncated


def _is_secret_name(path: Path) -> bool:
    folded = path.name.casefold()
    return any(part in folded for part in SECRET_NAME_PARTS)


def _claude_global_hits(
    home: Path,
    env: dict[str, str],
    context: ProjectContext,
    terms: list[str],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    config_dir = _claude_config_dir(home, env)
    root = _safe_subdirectory(config_dir, config_dir / "memory")
    if root is None:
        return [], [], False
    hits: list[dict[str, Any]] = []
    scanned = 0
    truncated = False
    try:
        files = sorted(
            (
                path
                for path in root.iterdir()
                if path.suffix.casefold() == ".md"
                and not path.is_symlink()
                and not _is_secret_name(path)
            ),
            key=lambda path: path.name.casefold(),
        )
    except OSError:
        return [], ["claude_global_unavailable"], False
    if len(files) > MAX_GLOBAL_FILES:
        files = files[:MAX_GLOBAL_FILES]
        truncated = True
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_BYTES or scanned + size > MAX_GLOBAL_SCAN_BYTES:
            truncated = True
            continue
        scanned += size
        text, reason = _read_file(root, path, limit=MAX_FILE_BYTES)
        if text is None:
            continue
        if reason:
            truncated = True
        if not _term_score(f"{path.name}\n{text}", terms):
            continue
        score = _term_score(text, terms)
        item, clipped = _hit(
            backend="claude-global",
            context=context,
            path=path,
            title=path.stem,
            text=text,
            terms=terms,
            score=score,
        )
        hits.append(item)
        truncated |= clipped
    return hits, [], truncated


def _codex_home(home: Path, env: dict[str, str]) -> Path:
    raw = env.get("CODEX_HOME")
    if not raw:
        return home / ".codex"
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw) if Path(raw).is_absolute() else home / raw


def _codex_memory_root(home: Path, env: dict[str, str]) -> Path | None:
    config_dir = _codex_home(home, env)
    return _safe_subdirectory(config_dir, config_dir / "memories")


def _task_groups(text: str) -> list[tuple[str, str]]:
    matches = list(TASK_GROUP_RE.finditer(text))
    groups: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        groups.append((match.group(1).strip(), text[match.start() : end]))
    return groups


def _codex_group_matches(group: str, context: ProjectContext) -> bool:
    metadata = group.split("\n## ", 1)[0]
    paths = CWD_RE.findall(metadata)
    for value in paths:
        raw = value.strip()
        candidates = [raw]
        # Generated Codex summaries sometimes annotate a real cwd with prose,
        # e.g. "cwd=/repo and user-level configuration". Try only explicit
        # delimiter prefixes, and still require each resulting path to exist
        # and resolve to the exact same git common directory.
        for marker in (" and ", " or ", " (", " [", " — "):
            if marker in raw:
                candidates.append(raw.split(marker, 1)[0].strip())
        if any(_same_project(candidate, context) for candidate in dict.fromkeys(candidates)):
            return True
    return False


def _codex_project_hits(
    home: Path,
    env: dict[str, str],
    context: ProjectContext,
    terms: list[str],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    root = _codex_memory_root(home, env)
    if root is None:
        return [], [], False
    path = root / "MEMORY.md"
    text, reason = _read_file(root, path, limit=MAX_FILE_BYTES)
    if text is None:
        warning = [] if reason in {"unsafe_path", "read_failed"} else [f"codex_{reason}"]
        return [], warning, reason == "oversized_file"
    hits: list[dict[str, Any]] = []
    matched_scope = False
    truncated = reason is not None
    for title, group in _task_groups(text):
        if not _codex_group_matches(group, context):
            continue
        matched_scope = True
        score = _term_score(group, terms)
        if not score:
            continue
        item, clipped = _hit(
            backend="codex-project",
            context=context,
            path=path,
            title=title,
            section=f"Task Group: {title}",
            text=group,
            terms=terms,
            score=score,
        )
        hits.append(item)
        truncated |= clipped
    warnings = [] if matched_scope else ["codex_project_unverified"]
    return hits, warnings, truncated


def _settings(config: dict[str, Any]) -> tuple[bool, str, Limits]:
    recall = config.get("recall") if isinstance(config, dict) else None
    runtime = recall.get("runtimeMemory") if isinstance(recall, dict) else None
    if not isinstance(runtime, dict) or runtime.get("enabled") is not True:
        return False, "off", Limits(5, HARD_MAX_EXCERPT_BYTES)
    global_sources = runtime.get("globalSources", "explicit")
    if global_sources not in {"off", "explicit"}:
        global_sources = "off"
    max_hits = runtime.get("maxHits", 5)
    max_bytes = runtime.get("maxExcerptBytes", HARD_MAX_EXCERPT_BYTES)
    if not isinstance(max_hits, int):
        max_hits = 5
    if not isinstance(max_bytes, int):
        max_bytes = HARD_MAX_EXCERPT_BYTES
    return (
        True,
        global_sources,
        Limits(
            max(1, min(max_hits, HARD_MAX_HITS)),
            max(256, min(max_bytes, HARD_MAX_EXCERPT_BYTES)),
        ),
    )


def _normalize_terms(terms: list[str]) -> list[str]:
    normalized: list[str] = []
    seen_folded: set[str] = set()
    total = 0
    for value in terms[:8]:
        if not isinstance(value, str):
            continue
        term = " ".join(value.split()).strip()
        if not term:
            continue
        encoded = term.encode("utf-8")
        if total + len(encoded) > MAX_QUERY_BYTES:
            break
        total += len(encoded)
        folded = term.casefold()
        if folded not in seen_folded:
            normalized.append(term)
            seen_folded.add(folded)
    return normalized


def _finalize(
    runtime: str,
    context: ProjectContext | None,
    candidates: list[dict[str, Any]],
    warnings: list[str],
    truncated: bool,
    limits: Limits,
) -> dict[str, Any]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(
        candidates,
        key=lambda hit: (-int(hit.get("score", 0)), hit["backend"], hit["source_path"]),
    ):
        key = (item["source_path"], item.get("section", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    selected: list[dict[str, Any]] = []
    remaining = limits.max_excerpt_bytes
    for item in deduped:
        if len(selected) >= limits.max_hits or remaining <= 0:
            truncated = True
            break
        excerpt, clipped = _truncate_utf8(item["excerpt"], remaining)
        if not excerpt:
            truncated = True
            break
        copy = dict(item)
        copy["excerpt"] = excerpt
        selected.append(copy)
        remaining -= len(excerpt.encode("utf-8"))
        truncated |= clipped
    if len(selected) < len(deduped):
        truncated = True

    envelope = {
        "schema_version": SCHEMA_VERSION,
        "runtime": runtime,
        "project_id": context.project_id if context else "",
        "hits": selected,
        "warnings": list(dict.fromkeys(warnings)),
        "truncated": truncated,
    }
    encoded = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
    if len(encoded) > HARD_MAX_OUTPUT_BYTES:
        envelope["hits"] = []
        envelope["warnings"].append("output_budget_exceeded")
        envelope["truncated"] = True
    return envelope


def search(
    terms: list[str],
    *,
    cwd: Path,
    home: Path,
    runtime: str,
    config: dict[str, Any],
    include_global: bool = False,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    enabled, global_sources, limits = _settings(config)
    context = project_context(cwd)
    if not enabled:
        return _finalize(runtime, context, [], [], False, limits)
    if runtime not in {"claude", "codex"}:
        return _finalize(runtime, context, [], ["unknown_runtime"], False, limits)
    if context is None:
        return _finalize(runtime, None, [], ["not_a_git_project"], False, limits)
    normalized = _normalize_terms(terms)
    if not normalized:
        return _finalize(runtime, context, [], ["empty_query"], False, limits)
    active_env = dict(os.environ if env is None else env)

    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    truncated = False
    if runtime == "codex":
        memory_dir, warning = _claude_memory_root(home, active_env, context)
        if memory_dir is not None:
            hits, source_warnings, source_truncated = _claude_project_hits(
                memory_dir, context, normalized
            )
            candidates.extend(hits)
            warnings.extend(source_warnings)
            truncated |= source_truncated
        elif warning:
            warnings.append(warning)
        if include_global and global_sources == "explicit":
            hits, source_warnings, source_truncated = _claude_global_hits(
                home, active_env, context, normalized
            )
            candidates.extend(hits)
            warnings.extend(source_warnings)
            truncated |= source_truncated
    else:
        hits, source_warnings, source_truncated = _codex_project_hits(
            home, active_env, context, normalized
        )
        candidates.extend(hits)
        warnings.extend(source_warnings)
        truncated |= source_truncated
    return _finalize(runtime, context, candidates, warnings, truncated, limits)


def status(
    *,
    cwd: Path,
    home: Path,
    runtime: str,
    config: dict[str, Any],
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    enabled, global_sources, _ = _settings(config)
    context = project_context(cwd)
    counterpart = "claude-project" if runtime == "codex" else "codex-project"
    available = False
    reason = "disabled" if not enabled else "not_a_git_project"
    active_env = dict(os.environ if env is None else env) if enabled else {}
    if enabled and context is not None and runtime == "codex":
        memory_dir, warning = _claude_memory_root(home, active_env, context)
        available = memory_dir is not None
        reason = "available" if available else (warning or "unavailable")
    elif enabled and context is not None and runtime == "claude":
        root = _codex_memory_root(home, active_env)
        text = None
        if root is not None:
            text, _ = _read_file(root, root / "MEMORY.md", limit=MAX_FILE_BYTES)
        if root is not None and text is not None:
            available = any(
                _codex_group_matches(group, context) for _, group in _task_groups(text)
            )
        reason = "available" if available else "codex_project_unverified"
    elif enabled and runtime not in {"claude", "codex"}:
        reason = "unknown_runtime"
    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": enabled,
        "runtime": runtime,
        "project_id": context.project_id if context else "",
        "counterpart": {
            "backend": counterpart,
            "available": available,
            "reason": reason,
        },
        "global_sources": global_sources,
    }


def _load_config(home: Path) -> dict[str, Any]:
    root = home / ".mnemo"
    text, _ = _read_file(root, root / "config.json", limit=64 * 1024)
    if text is None:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _detect_runtime(env: dict[str, str]) -> str:
    if any(env.get(name) for name in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_HOME")):
        return "codex"
    if any(env.get(name) for name in ("CLAUDE_SESSION_ID", "CLAUDE_PLUGIN_ROOT")):
        return "claude"
    return "unknown"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    if command not in {"search", "status"}:
        print("usage: runtime-memory.py {search|status}", file=sys.stderr)
        return 2
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        print("runtime-memory: input exceeds 16 KiB", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        print("runtime-memory: invalid JSON", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("runtime-memory: JSON object required", file=sys.stderr)
        return 2
    home = Path.home()
    config = _load_config(home)
    runtime = payload.get("runtime") or _detect_runtime(dict(os.environ))
    if command == "status":
        result = status(
            cwd=Path.cwd(),
            home=home,
            runtime=str(runtime),
            config=config,
        )
    else:
        terms = payload.get("terms", [])
        if not isinstance(terms, list):
            terms = []
        result = search(
            terms,
            cwd=Path.cwd(),
            home=home,
            runtime=str(runtime),
            config=config,
            include_global=payload.get("include_global") is True,
        )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

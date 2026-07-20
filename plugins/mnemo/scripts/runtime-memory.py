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
MAX_CLAUDE_STATE_BYTES = 1024 * 1024
MAX_CLAUDE_PROJECT_KEYS = 2_048
MAX_CLAUDE_COLLISION_KEYS = 8
MAX_GLOBAL_SCAN_BYTES = 4 * 1024 * 1024
MAX_GLOBAL_FILES = 200
MAX_GLOBAL_DIR_ENTRIES = 256
MAX_INDEX_LINKS = 50
MAX_STATUS_LINE_BYTES = 8 * 1024
CLAUDE_INDEX_HARD_LINES = 200
# Claude documents this as 25 KB and its UI historically renders it as
# approximately 24.4 KiB, so the boundary is 25,000 decimal bytes.
CLAUDE_INDEX_HARD_BYTES = 25_000
HARD_MAX_HITS = 7
HARD_MAX_EXCERPT_BYTES = 12_288
HARD_MAX_OUTPUT_BYTES = 32_768
PER_HIT_BYTES = 2_048
OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)(?:#[^)]+)?\)")
TASK_GROUP_RE = re.compile(r"^# Task Group: (.+?)\s*$")
APPLIES_TO_RE = re.compile(r"(?m)^applies_to\s*:\s*(.*?)\s*$")
CWD_RE = re.compile(r"(?:^|[;\s])cwd=([^;,\n]+)")
HTML_BLOCK_TAG_RE = re.compile(
    r"^[ ]{0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|"
    r"center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|"
    r"figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|"
    r"legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|"
    r"param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|"
    r"track|ul)(?:\s|/?>|$)",
    re.IGNORECASE,
)
HTML_GENERIC_TAG_RE = re.compile(r"^[ ]{0,3}</?[A-Za-z][^>]*>[ \t]*$")
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


class VerifiedRoot(NamedTuple):
    path: Path
    fd: int


class TaskGroup(NamedTuple):
    title: str
    text: str
    metadata: str


class StructureEvent(NamedTuple):
    kind: str
    title: str = ""


class MarkdownVisibilityFilter:
    """Track Markdown regions that cannot carry routing or scope controls.

    The control view is deliberately conservative: YAML frontmatter, fenced
    code, HTML comments, and CommonMark raw HTML blocks are opaque. Claude's
    loaded-size view uses the same state machine with fences/raw HTML enabled,
    because current Claude docs strip only frontmatter and block HTML comments
    before applying the MEMORY.md load limits.
    """

    def __init__(self, *, ignore_fences: bool = True, ignore_raw_html: bool = True) -> None:
        self._hide_fences = ignore_fences
        self._ignore_raw_html = ignore_raw_html
        self._fence_char = ""
        self._fence_length = 0
        self._frontmatter = False
        self._html_comment = False
        self._html_close = ""
        self._line_number = 0

    @staticmethod
    def _marker(line: str) -> tuple[str, int, str] | None:
        content = line.rstrip("\r\n")
        stripped = content.lstrip(" ")
        if len(content) - len(stripped) > 3 or not stripped:
            return None
        marker = stripped[0]
        if marker not in {"`", "~"}:
            return None
        length = len(stripped) - len(stripped.lstrip(marker))
        if length < 3:
            return None
        return marker, length, stripped[length:]

    def visible(self, line: str) -> bool:
        content = line.rstrip("\r\n")
        first_line = self._line_number == 0
        self._line_number += 1

        if self._frontmatter:
            if content in {"---", "..."}:
                self._frontmatter = False
            return False
        if first_line and content.removeprefix("\ufeff") == "---":
            self._frontmatter = True
            return False

        stripped = content.lstrip(" ")
        block_indented = len(content) - len(stripped) <= 3

        # Track fences even in Claude's loaded-size view. Fenced content counts
        # toward the load limit, and HTML comment markers inside it are literal.
        marker = self._marker(line)
        if self._fence_char:
            if marker is not None:
                char, length, remainder = marker
                if (
                    char == self._fence_char
                    and length >= self._fence_length
                    and not remainder.strip(" \t")
                ):
                    self._fence_char = ""
                    self._fence_length = 0
            return not self._hide_fences

        if self._html_comment:
            if "-->" in content:
                self._html_comment = False
            return False

        if self._html_close:
            if self._html_close == "blank":
                if not content.strip():
                    self._html_close = ""
                return False
            if self._html_close.casefold() in content.casefold():
                self._html_close = ""
            return False

        if marker is not None:
            char, length, info = marker
            # CommonMark permits info strings on both fence types, but a
            # backtick fence's info string cannot itself contain a backtick.
            if char != "`" or "`" not in info:
                self._fence_char = char
                self._fence_length = length
                return not self._hide_fences

        if block_indented and stripped.startswith("<!--"):
            if "-->" not in stripped[4:]:
                self._html_comment = True
            return False

        if self._ignore_raw_html and block_indented:
            lowered = stripped.casefold()
            raw_tag = re.match(r"<(script|pre|style|textarea)(?:\s|>|$)", stripped, re.I)
            if raw_tag:
                close = f"</{raw_tag.group(1)}>"
                if close.casefold() not in lowered:
                    self._html_close = close
                return False
            if stripped.startswith("<?"):
                if "?>" not in stripped[2:]:
                    self._html_close = "?>"
                return False
            if stripped.startswith("<![CDATA["):
                if "]]>" not in stripped[9:]:
                    self._html_close = "]" + "]>"
                return False
            if re.match(r"<![A-Z]", stripped):
                if ">" not in stripped[2:]:
                    self._html_close = ">"
                return False
            if HTML_BLOCK_TAG_RE.match(content) or HTML_GENERIC_TAG_RE.match(content):
                self._html_close = "blank"
                return False

        return True


class MarkdownTaskGroupParser:
    """Incrementally expose task-group structure from the safe control view."""

    def __init__(self) -> None:
        self._visibility = MarkdownVisibilityFilter()

    def feed(self, line: str) -> StructureEvent:
        if not self._visibility.visible(line):
            return StructureEvent("ignored")

        content = line.rstrip("\r\n")
        match = TASK_GROUP_RE.fullmatch(content)
        if match:
            return StructureEvent("task_group", match.group(1).strip())
        if content.startswith("## "):
            return StructureEvent("section")
        return StructureEvent("text")


def _markdown_control_text(text: str) -> str:
    visibility = MarkdownVisibilityFilter()
    return "".join(
        line for line in text.splitlines(keepends=True) if visibility.visible(line)
    )


def _claude_loaded_index_text(text: str) -> str:
    visibility = MarkdownVisibilityFilter(ignore_fences=False, ignore_raw_html=False)
    return "".join(
        line for line in text.splitlines(keepends=True) if visibility.visible(line)
    )


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
    except (OSError, ValueError):
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


def _open_absolute_directory(path: Path) -> tuple[int | None, str | None]:
    """Open an absolute directory one component at a time without symlinks."""
    required = ("O_DIRECTORY", "O_NOFOLLOW")
    if (
        os.name != "posix"
        or any(not hasattr(os, name) for name in required)
        or not OPEN_SUPPORTS_DIR_FD
    ):
        return None, "descriptor_traversal_unsupported"
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    if not path.is_absolute():
        return None, "unsafe_path"
    fd: int | None = None
    try:
        fd = os.open(os.sep, flags)
        for part in path.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd, None
    except OSError:
        if fd is not None:
            os.close(fd)
        return None, "unsafe_path"


def _open_verified_root(root: Path) -> tuple[VerifiedRoot | None, str | None]:
    """Capture one owned directory inode for a bounded read operation."""
    root_lexical = Path(os.path.abspath(os.fspath(root)))
    safe_root = _safe_directory(root_lexical)
    if safe_root is None:
        return None, "unsafe_path"
    try:
        expected = safe_root.stat()
    except OSError:
        return None, "unsafe_path"
    root_fd, reason = _open_absolute_directory(safe_root)
    if root_fd is None:
        return None, reason
    try:
        opened = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not _owned_by_current_user(opened)
            or (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino)
        ):
            os.close(root_fd)
            return None, "unsafe_path"
    except OSError:
        os.close(root_fd)
        return None, "unsafe_path"
    return VerifiedRoot(root_lexical, root_fd), None


def _open_contained_file(
    root: Path,
    candidate: Path,
    *,
    verified_root: VerifiedRoot | None = None,
) -> tuple[int | None, str | None]:
    """Open a regular file beneath root using descriptor-relative traversal.

    Every component below the captured root is opened with O_NOFOLLOW. This
    closes the check/open gap where an intermediate directory could otherwise
    be replaced by a symlink after validation.
    """
    root_lexical = Path(os.path.abspath(os.fspath(root)))
    candidate_lexical = Path(os.path.abspath(os.fspath(candidate)))
    try:
        relative = candidate_lexical.relative_to(root_lexical)
    except ValueError:
        return None, "unsafe_path"
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        return None, "unsafe_path"

    if verified_root is None:
        captured_root, reason = _open_verified_root(root_lexical)
        if captured_root is None:
            return None, reason
        current_fd = captured_root.fd
    else:
        if root_lexical != verified_root.path:
            return None, "unsafe_path"
        try:
            current_fd = os.dup(verified_root.fd)
        except OSError:
            return None, "unsafe_path"
    try:
        opened_root = os.fstat(current_fd)
        if (
            not stat.S_ISDIR(opened_root.st_mode)
            or not _owned_by_current_user(opened_root)
        ):
            return None, "unsafe_path"

        directory_flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
        )
        for part in relative.parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            info = os.fstat(next_fd)
            if not stat.S_ISDIR(info.st_mode) or not _owned_by_current_user(info):
                os.close(next_fd)
                return None, "unsafe_path"
            os.close(current_fd)
            current_fd = next_fd

        file_flags = (
            os.O_RDONLY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        file_fd = os.open(relative.parts[-1], file_flags, dir_fd=current_fd)
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or not _owned_by_current_user(info):
            os.close(file_fd)
            return None, "unsafe_file"
        return file_fd, None
    except OSError:
        return None, "read_failed"
    finally:
        os.close(current_fd)


def _read_stable_bytes(
    root: Path,
    candidate: Path,
    *,
    limit: int,
    verified_root: VerifiedRoot | None = None,
) -> tuple[bytes | None, os.stat_result | None, str | None]:
    fd, reason = _open_contained_file(
        root,
        candidate,
        verified_root=verified_root,
    )
    if fd is None:
        return None, None, reason
    try:
        before = os.fstat(fd)
        if before.st_size > limit:
            return None, before, "oversized_file"
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
    except OSError:
        return None, None, "read_failed"
    finally:
        os.close(fd)

    data = b"".join(chunks)
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if len(data) > limit or len(data) != before.st_size or before_identity != after_identity:
        return None, after, "changed_during_read"
    return data, after, None


def _read_file_bytes(
    root: Path,
    candidate: Path,
    *,
    limit: int,
    verified_root: VerifiedRoot | None = None,
) -> tuple[bytes | None, int | None, str | None]:
    data, metadata, reason = _read_stable_bytes(
        root,
        candidate,
        limit=limit,
        verified_root=verified_root,
    )
    return data, metadata.st_size if metadata is not None else None, reason


def _read_file_with_metadata(
    root: Path,
    candidate: Path,
    *,
    limit: int,
    verified_root: VerifiedRoot | None = None,
) -> tuple[str | None, os.stat_result | None, str | None]:
    data, metadata, reason = _read_stable_bytes(
        root,
        candidate,
        limit=limit,
        verified_root=verified_root,
    )
    if data is None:
        return None, metadata, reason
    return data.decode("utf-8", errors="replace"), metadata, reason


def _read_file(
    root: Path,
    candidate: Path,
    *,
    limit: int,
    verified_root: VerifiedRoot | None = None,
) -> tuple[str | None, str | None]:
    text, _, reason = _read_file_with_metadata(
        root,
        candidate,
        limit=limit,
        verified_root=verified_root,
    )
    return text, reason


def _mtime(metadata: os.stat_result) -> str:
    return datetime.fromtimestamp(metadata.st_mtime, timezone.utc).isoformat()


def _claude_slug(path: Path) -> str:
    return str(path).replace(os.sep, "-")


def _claude_state_path(home: Path, config_dir: Path) -> tuple[Path, Path]:
    default_dir = home / ".claude"
    if config_dir == default_dir:
        return home, home / ".claude.json"
    return config_dir, config_dir / ".claude.json"


def _claude_registered_projects(
    home: Path,
    env: dict[str, str],
) -> list[str] | None:
    """Return Claude's exact project registry keys without opening transcripts."""
    config_dir = _claude_config_dir(home, env)
    state_root, state_path = _claude_state_path(home, config_dir)
    text, _ = _read_file(state_root, state_path, limit=MAX_CLAUDE_STATE_BYTES)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    projects = value.get("projects") if isinstance(value, dict) else None
    if not isinstance(projects, dict) or len(projects) > MAX_CLAUDE_PROJECT_KEYS:
        return None
    keys = [key for key in projects if isinstance(key, str) and Path(key).is_absolute()]
    return keys if len(keys) == len(projects) else None


def _verified_claude_project(
    projects_root: Path,
    project_dir: Path,
    context: ProjectContext,
    registered_projects: list[str],
) -> bool:
    safe_project = _safe_subdirectory(projects_root, project_dir)
    if safe_project is None:
        return False
    matching_keys = [
        key
        for key in registered_projects
        if _claude_slug(Path(key)) == safe_project.name
    ]
    if not matching_keys or len(matching_keys) > MAX_CLAUDE_COLLISION_KEYS:
        return False
    # Claude's flattened directory key is lossy. Accept it only when every
    # exact app-state key that maps to the candidate resolves to this git
    # common directory; mixed or stale collisions fail closed.
    return all(_same_project(key, context) for key in matching_keys)


def _configured_runtime_home(
    home: Path,
    env: dict[str, str],
    variable: str,
    default: str,
) -> Path:
    raw = env.get(variable)
    if not raw:
        return home / default
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw) if Path(raw).is_absolute() else home / raw


def _claude_config_dir(home: Path, env: dict[str, str]) -> Path:
    return _configured_runtime_home(home, env, "CLAUDE_CONFIG_DIR", ".claude")


def _read_claude_settings(
    root: Path,
    settings_path: Path,
) -> tuple[dict[str, Any] | None, str]:
    try:
        settings_path.lstat()
    except FileNotFoundError:
        return None, "absent"
    except (OSError, ValueError):
        return None, "invalid"
    text, reason = _read_file(root, settings_path, limit=MAX_CLAUDE_STATE_BYTES)
    if text is None or reason is not None:
        return None, "invalid"
    try:
        settings = json.loads(text)
    except json.JSONDecodeError:
        return None, "invalid"
    if not isinstance(settings, dict):
        return None, "invalid"
    return settings, "present"


def _claude_user_memory_setting(
    home: Path,
    env: dict[str, str],
    context: ProjectContext,
) -> tuple[str, Path | None]:
    """Resolve only settings whose effective meaning can be proven locally.

    Claude can also apply managed policy and an arbitrary --settings file, and
    project/local autoMemoryDirectory values depend on workspace trust. Those
    effective inputs are not exposed to this child process. Visible disable
    controls are therefore honored fail-closed, while a visible project/local
    directory override returns an explicit unresolved state instead of guessing.
    """
    if env.get("CLAUDE_CODE_DISABLE_CLAUDE_MDS") == "1":
        return "claude_memory_files_disabled", None

    disable_auto = env.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")
    force_enabled = disable_auto == "0"
    if disable_auto == "1":
        return "claude_auto_memory_disabled", None

    config_dir = _claude_config_dir(home, env)
    visible_settings: list[tuple[str, dict[str, Any]]] = []
    settings_locations = (
        ("user", config_dir, config_dir / "settings.json"),
        (
            "project",
            context.current_root,
            context.current_root / ".claude/settings.json",
        ),
        (
            "local",
            context.current_root,
            context.current_root / ".claude/settings.local.json",
        ),
    )
    for scope, root, settings_path in settings_locations:
        settings, state = _read_claude_settings(root, settings_path)
        if state == "invalid":
            return "claude_auto_memory_invalid", None
        if settings is not None:
            visible_settings.append((scope, settings))

    for _, settings in visible_settings:
        if "autoMemoryEnabled" not in settings:
            continue
        enabled = settings["autoMemoryEnabled"]
        if not isinstance(enabled, bool):
            return "claude_auto_memory_invalid", None
        if enabled is False and not force_enabled:
            return "claude_auto_memory_disabled", None

    for scope, settings in visible_settings:
        if scope != "user" and "autoMemoryDirectory" in settings:
            raw = settings["autoMemoryDirectory"]
            if not isinstance(raw, str) or not raw or "\x00" in raw:
                return "claude_auto_memory_invalid", None
            return "claude_auto_memory_effective_settings_unresolved", None

    user_settings = next(
        (settings for scope, settings in visible_settings if scope == "user"),
        {},
    )
    if "autoMemoryDirectory" not in user_settings:
        return "absent", None
    raw = user_settings["autoMemoryDirectory"]
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        return "claude_auto_memory_invalid", None
    if raw.startswith("~/"):
        candidate = home / raw[2:].lstrip("/")
    else:
        candidate = Path(raw)
        if not candidate.is_absolute():
            return "claude_auto_memory_invalid", None
    safe_candidate = _safe_directory(candidate)
    if safe_candidate is None:
        return "claude_auto_memory_invalid", None
    return "custom", safe_candidate


def _claude_memory_root(
    home: Path,
    env: dict[str, str],
    context: ProjectContext,
    *,
    allow_unscoped_custom: bool = False,
) -> tuple[Path | None, str | None]:
    override_state, override_path = _claude_user_memory_setting(home, env, context)
    if override_state == "custom":
        # A user-level override points to one literal directory and carries no
        # repository identity. Claude may inspect it as its own effective
        # active memory, but the cross-runtime bridge cannot prove that it
        # belongs to the current git repository and therefore fails closed.
        if allow_unscoped_custom:
            return override_path, None
        return None, "claude_auto_memory_unscoped"
    if override_state != "absent":
        return None, override_state

    config_dir = _claude_config_dir(home, env)
    projects_root = config_dir / "projects"
    safe_projects = _safe_subdirectory(config_dir, projects_root)
    if safe_projects is None:
        return None, "claude_project_unverified"
    registered_projects = _claude_registered_projects(home, env)
    if registered_projects is None:
        return None, "claude_project_unverified"
    candidates = [
        safe_projects / _claude_slug(context.canonical_root),
    ]
    if context.current_root != context.canonical_root:
        candidates.append(safe_projects / _claude_slug(context.current_root))
    for project_dir in dict.fromkeys(candidates):
        if not _verified_claude_project(
            safe_projects, project_dir, context, registered_projects
        ):
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
    metadata: os.stat_result,
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
            "updated_at": _mtime(metadata),
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
    verified_root, reason = _open_verified_root(memory_dir)
    if verified_root is None:
        return [], [f"claude_index_{reason or 'unavailable'}"], False
    try:
        return _claude_project_hits_scoped(
            memory_dir,
            verified_root,
            context,
            terms,
        )
    finally:
        os.close(verified_root.fd)


def _claude_project_hits_scoped(
    memory_dir: Path,
    verified_root: VerifiedRoot,
    context: ProjectContext,
    terms: list[str],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    hits: list[dict[str, Any]] = []
    warnings: list[str] = []
    truncated = False
    index_path = memory_dir / "MEMORY.md"
    index_text, index_metadata, reason = _read_file_with_metadata(
        memory_dir,
        index_path,
        limit=MAX_FILE_BYTES,
        verified_root=verified_root,
    )
    if index_text is None:
        return [], [f"claude_index_{reason or 'unavailable'}"], reason == "oversized_file"
    assert index_metadata is not None
    if reason:
        warnings.append(f"claude_index_{reason}")
        truncated = True
    index_control = _markdown_control_text(index_text)
    index_score = _term_score(index_control, terms)
    if index_score:
        item, clipped = _hit(
            backend="claude-project",
            context=context,
            path=index_path,
            metadata=index_metadata,
            title="MEMORY.md",
            text=index_control,
            terms=terms,
            score=index_score,
        )
        hits.append(item)
        truncated |= clipped

    index_links = _markdown_links(index_control)
    indexes = [(index_path, index_control, index_links)]
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
        archive_text, _, archive_reason = _read_file_with_metadata(
            memory_dir,
            archive_path,
            limit=MAX_FILE_BYTES,
            verified_root=verified_root,
        )
        if archive_text is not None:
            archive_control = _markdown_control_text(archive_text)
            indexes.append(
                (archive_path, archive_control, _markdown_links(archive_control))
            )
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
        lexical = Path(os.path.normpath(os.fspath(candidate)))
        if lexical in seen_targets:
            continue
        seen_targets.add(lexical)
        text, metadata, read_reason = _read_file_with_metadata(
            memory_dir,
            candidate,
            limit=MAX_FILE_BYTES,
            verified_root=verified_root,
        )
        if text is None:
            if read_reason == "oversized_file":
                truncated = True
            continue
        assert metadata is not None
        if read_reason:
            truncated = True
        score = _term_score(text, terms)
        item, clipped = _hit(
            backend="claude-project",
            context=context,
            path=candidate,
            metadata=metadata,
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
    if env.get("CLAUDE_CODE_DISABLE_CLAUDE_MDS") == "1":
        return [], ["claude_memory_files_disabled"], False
    config_dir = _claude_config_dir(home, env)
    root = _safe_subdirectory(config_dir, config_dir / "memory")
    if root is None:
        return [], [], False
    verified_root, reason = _open_verified_root(root)
    if verified_root is None:
        return [], [f"claude_global_{reason or 'unavailable'}"], False
    try:
        return _claude_global_hits_scoped(
            root,
            verified_root,
            context,
            terms,
        )
    finally:
        os.close(verified_root.fd)


def _claude_global_hits_scoped(
    root: Path,
    verified_root: VerifiedRoot,
    context: ProjectContext,
    terms: list[str],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    hits: list[dict[str, Any]] = []
    scanned = 0
    truncated = False
    try:
        entries: list[Path] = []
        with os.scandir(verified_root.fd) as scan:
            for entry in scan:
                if len(entries) >= MAX_GLOBAL_DIR_ENTRIES:
                    return [], ["claude_global_entry_budget"], True
                entries.append(root / entry.name)
    except OSError:
        return [], ["claude_global_unavailable"], False
    files = sorted(
        (
            path
            for path in entries
            if path.suffix.casefold() == ".md"
            and not path.is_symlink()
            and not _is_secret_name(path)
        ),
        key=lambda path: path.name.casefold(),
    )
    if len(files) > MAX_GLOBAL_FILES:
        files = files[:MAX_GLOBAL_FILES]
        truncated = True
    for path in files:
        remaining_budget = MAX_GLOBAL_SCAN_BYTES - scanned
        if remaining_budget <= 0:
            truncated = True
            break
        data, metadata, reason = _read_stable_bytes(
            root,
            path,
            limit=min(MAX_FILE_BYTES, remaining_budget),
            verified_root=verified_root,
        )
        if data is None:
            if reason in {"oversized_file", "changed_during_read"}:
                truncated = True
            continue
        assert metadata is not None
        size = metadata.st_size
        if scanned + size > MAX_GLOBAL_SCAN_BYTES:
            truncated = True
            continue
        scanned += size
        text = data.decode("utf-8", errors="replace")
        if not _term_score(f"{path.name}\n{text}", terms):
            continue
        score = _term_score(text, terms)
        item, clipped = _hit(
            backend="claude-global",
            context=context,
            path=path,
            metadata=metadata,
            title=path.stem,
            text=text,
            terms=terms,
            score=score,
        )
        hits.append(item)
        truncated |= clipped
    return hits, [], truncated


def _codex_home(home: Path, env: dict[str, str]) -> Path:
    return _configured_runtime_home(home, env, "CODEX_HOME", ".codex")


def _codex_memory_root(home: Path, env: dict[str, str]) -> Path | None:
    config_dir = _codex_home(home, env)
    return _safe_subdirectory(config_dir, config_dir / "memories")


def _task_groups(text: str) -> list[TaskGroup]:
    parser = MarkdownTaskGroupParser()
    groups: list[TaskGroup] = []
    title = ""
    visible_lines: list[str] = []
    metadata_lines: list[str] = []
    in_metadata = False

    def finish() -> None:
        if title:
            groups.append(
                TaskGroup(title, "".join(visible_lines), "".join(metadata_lines))
            )

    for line in text.splitlines(keepends=True):
        event = parser.feed(line)
        if event.kind == "task_group":
            finish()
            title = event.title
            visible_lines = [line]
            metadata_lines = []
            in_metadata = bool(title)
            continue
        if not title or event.kind == "ignored":
            continue
        visible_lines.append(line)
        if in_metadata:
            if event.kind == "section":
                in_metadata = False
            elif event.kind == "text" and line.startswith("applies_to"):
                metadata_lines.append(line)
    finish()
    return groups


def _codex_group_matches(
    metadata: str,
    context: ProjectContext,
    cache: dict[str, bool] | None = None,
) -> bool:
    applies_to = APPLIES_TO_RE.findall(metadata)
    if len(applies_to) != 1:
        return False
    scope = applies_to[0].strip()
    if not scope.startswith("cwd="):
        return False
    if len(re.findall(r"(?:^|[;\s])cwd=", scope)) != 1:
        return False
    paths = CWD_RE.findall(scope)
    if len(paths) != 1:
        return False
    raw = paths[0].strip()
    candidates = [raw]
    # Generated Codex summaries sometimes annotate a real cwd with prose,
    # e.g. "cwd=/repo and user-level configuration". Try only explicit
    # delimiter prefixes, and still require each resulting path to exist
    # and resolve to the exact same git common directory.
    for marker in (" and ", " or ", " (", " [", " — "):
        if marker in raw:
            candidates.append(raw.split(marker, 1)[0].strip())
    for candidate in dict.fromkeys(candidates):
        if cache is not None and candidate in cache:
            matches = cache[candidate]
        else:
            matches = _same_project(candidate, context)
            if cache is not None:
                cache[candidate] = matches
        if matches:
            return True
    return False


def _codex_status_has_matching_group(
    root: Path,
    path: Path,
    context: ProjectContext,
) -> bool:
    """Inspect only task-group headers and scope metadata for health status."""
    fd, _ = _open_contained_file(root, path)
    if fd is None:
        return False
    try:
        info = os.fstat(fd)
        if info.st_size > MAX_FILE_BYTES:
            os.close(fd)
            return False
        stream = os.fdopen(fd, "rb", buffering=0)
    except OSError:
        os.close(fd)
        return False

    parser = MarkdownTaskGroupParser()
    in_group = False
    metadata_lines: list[str] = []
    bytes_read = 0
    try:
        with stream:
            while True:
                if bytes_read >= MAX_FILE_BYTES:
                    if stream.read(1):
                        return False
                    break
                remaining = MAX_FILE_BYTES - bytes_read
                raw = stream.readline(min(MAX_STATUS_LINE_BYTES, remaining) + 1)
                if not raw:
                    break
                bytes_read += len(raw)
                if (
                    bytes_read > MAX_FILE_BYTES
                    or len(raw) > MAX_STATUS_LINE_BYTES
                    or not raw.endswith(b"\n")
                ):
                    return False
                line = raw.decode("utf-8", errors="replace")
                event = parser.feed(line)
                if event.kind == "task_group":
                    if in_group and _codex_group_matches(
                        "".join(metadata_lines), context
                    ):
                        return True
                    in_group = bool(event.title)
                    metadata_lines = []
                    continue
                if not in_group:
                    continue
                if event.kind == "section":
                    if _codex_group_matches("".join(metadata_lines), context):
                        return True
                    in_group = False
                    metadata_lines = []
                    continue
                if event.kind == "text" and line.startswith("applies_to"):
                    metadata_lines.append(line)
        return in_group and _codex_group_matches("".join(metadata_lines), context)
    except OSError:
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
    verified_root, root_reason = _open_verified_root(root)
    if verified_root is None:
        return [], [f"codex_{root_reason or 'unavailable'}"], False
    try:
        return _codex_project_hits_scoped(
            root,
            verified_root,
            context,
            terms,
        )
    finally:
        os.close(verified_root.fd)


def _codex_project_hits_scoped(
    root: Path,
    verified_root: VerifiedRoot,
    context: ProjectContext,
    terms: list[str],
) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = root / "MEMORY.md"
    text, metadata, reason = _read_file_with_metadata(
        root,
        path,
        limit=MAX_FILE_BYTES,
        verified_root=verified_root,
    )
    if text is None:
        warning = [] if reason in {"unsafe_path", "read_failed"} else [f"codex_{reason}"]
        return [], warning, reason == "oversized_file"
    assert metadata is not None
    hits: list[dict[str, Any]] = []
    matched_scope = False
    had_relevant_group = False
    truncated = reason is not None
    scope_cache: dict[str, bool] = {}
    for task_group in _task_groups(text):
        score = _term_score(task_group.text, terms)
        if not score:
            continue
        had_relevant_group = True
        if not _codex_group_matches(task_group.metadata, context, scope_cache):
            continue
        matched_scope = True
        item, clipped = _hit(
            backend="codex-project",
            context=context,
            path=path,
            metadata=metadata,
            title=task_group.title,
            section=f"Task Group: {task_group.title}",
            text=task_group.text,
            terms=terms,
            score=score,
        )
        hits.append(item)
        truncated |= clipped
    # Status reports overall counterpart availability separately. Search only
    # warns when query-relevant evidence existed but none proved this project;
    # irrelevant history must not trigger either Git probes or a false warning.
    warnings = (
        [] if matched_scope or not had_relevant_group else ["codex_project_unverified"]
    )
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
        if root is not None:
            available = _codex_status_has_matching_group(
                root, root / "MEMORY.md", context
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


def claude_index_status(
    *,
    cwd: Path,
    home: Path,
    warn_kb: int = 22,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Inspect Claude's discoverable MEMORY.md index without returning content.

    The helper cannot observe managed policy or an arbitrary --settings input,
    so "discoverable" is intentionally narrower than Claude's effective
    settings. Visible project/local directory overrides fail closed upstream.
    """
    empty_metrics = {
        "bytes": None,
        "lines": None,
        "raw_bytes": None,
        "raw_lines": None,
        "hard_limit_bytes": CLAUDE_INDEX_HARD_BYTES,
        "hard_limit_lines": CLAUDE_INDEX_HARD_LINES,
        "over_hard_limit": False,
        "warning_reasons": [],
    }
    context = project_context(cwd)
    if context is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "available": False,
            "reason": "not_a_git_project",
            "memory_dir": "",
            **empty_metrics,
            "warn_kb": warn_kb,
            "warning": False,
        }

    active_env = dict(os.environ if env is None else env)
    memory_dir, root_warning = _claude_memory_root(
        home,
        active_env,
        context,
        allow_unscoped_custom=True,
    )
    if memory_dir is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "available": False,
            "reason": root_warning or "unavailable",
            "memory_dir": "",
            **empty_metrics,
            "warn_kb": warn_kb,
            "warning": False,
        }

    data, raw_size, reason = _read_file_bytes(
        memory_dir,
        memory_dir / "MEMORY.md",
        limit=MAX_FILE_BYTES,
    )
    if data is None:
        warning_reasons = ["uninspectable_index"] if raw_size is not None else []
        return {
            "schema_version": SCHEMA_VERSION,
            "available": False,
            "reason": reason or "unavailable",
            "memory_dir": str(memory_dir),
            **empty_metrics,
            "raw_bytes": raw_size,
            "warn_kb": warn_kb,
            "warning": bool(warning_reasons),
            "warning_reasons": warning_reasons,
        }

    raw_text = data.decode("utf-8", errors="surrogateescape")
    loaded_text = _claude_loaded_index_text(raw_text)
    loaded_size = len(loaded_text.encode("utf-8", errors="surrogateescape"))
    loaded_lines = len(loaded_text.splitlines())
    over_bytes = loaded_size > CLAUDE_INDEX_HARD_BYTES
    over_lines = loaded_lines > CLAUDE_INDEX_HARD_LINES
    early_warning = loaded_size > warn_kb * 1024
    warning_reasons: list[str] = []
    if over_bytes:
        warning_reasons.append("hard_byte_limit")
    if over_lines:
        warning_reasons.append("hard_line_limit")
    if early_warning:
        warning_reasons.append("early_byte_threshold")
    return {
        "schema_version": SCHEMA_VERSION,
        "available": True,
        "reason": "available",
        "memory_dir": str(memory_dir),
        "bytes": loaded_size,
        "lines": loaded_lines,
        "raw_bytes": raw_size,
        "raw_lines": len(raw_text.splitlines()),
        "hard_limit_bytes": CLAUDE_INDEX_HARD_BYTES,
        "hard_limit_lines": CLAUDE_INDEX_HARD_LINES,
        "over_hard_limit": over_bytes or over_lines,
        "warn_kb": warn_kb,
        "warning": bool(warning_reasons),
        "warning_reasons": warning_reasons,
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
    if command not in {"search", "status", "claude-index-status"}:
        print(
            "usage: runtime-memory.py {search|status|claude-index-status}",
            file=sys.stderr,
        )
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
    if command == "claude-index-status":
        memory_config = config.get("memory")
        configured_warn_kb = (
            memory_config.get("indexWarnKB", 22)
            if isinstance(memory_config, dict)
            else 22
        )
        raw_warn_kb = payload.get("warn_kb", configured_warn_kb)
        warn_kb = (
            max(0, min(raw_warn_kb, 1024 * 1024))
            if isinstance(raw_warn_kb, int) and not isinstance(raw_warn_kb, bool)
            else 22
        )
        result = claude_index_status(
            cwd=Path.cwd(),
            home=home,
            warn_kb=warn_kb,
        )
    elif command == "status":
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

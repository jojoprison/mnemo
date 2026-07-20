#!/usr/bin/env python3
"""Atomic, shell-free Obsidian vault writes for both mnemo runtimes.

The Obsidian CLI is used only to discover the configured vault root. Markdown
is then written through descriptor-relative filesystem operations: this avoids
shell parsing and CLI argument-size/escaping hazards while retaining a narrow,
verified vault containment boundary. Requests and responses are JSON; note
content is never printed or passed to the CLI.
"""
from __future__ import annotations

from collections import Counter
import errno
import datetime as dt
import ctypes
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised through the platform guard
    fcntl = None  # type: ignore[assignment]


MAX_INPUT_BYTES = 1024 * 1024
MAX_NOTE_BYTES = 8 * 1024 * 1024
MAX_PATH_BYTES = 4096
MAX_COMPONENT_BYTES = 255
CLI_TIMEOUT_SECONDS = 15
RESERVED_DIRS = {".obsidian", ".trash"}
VALID_ACTIONS = {"create", "replace", "insert", "append", "archive-handoff"}
DATE_HEADER_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
OPEN_TODO_RE = re.compile(r"\[ \]")
HEADER_PENDING_RE = re.compile(
    r"В ПРОЦЕССЕ|НЕ закры|не закрыт|незакры|жд[еёo]м|отложено"
    r"|WAITING|PENDING|IN PROGRESS|TODO|BLOCKED",
    re.IGNORECASE,
)
HANDOFF_GUARD_MARK = "SIZE-GUARD"


class WriteError(Exception):
    """Expected, user-facing failure with a stable machine code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class CurrentFile:
    fd: int
    body: str
    raw: bytes
    metadata: os.stat_result
    sha256: str


def fail(code: str, message: str) -> None:
    raise WriteError(code, message)


def load_payload() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        fail("input_error", "input exceeds 1 MiB")
    try:
        value = json.loads(raw or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("input_error", "input must be valid UTF-8 JSON")
    if not isinstance(value, dict):
        fail("input_error", "input must be a JSON object")
    return value


def string(
    payload: dict[str, Any],
    key: str,
    *,
    allow_empty: bool = False,
) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or (not allow_empty and not value):
        suffix = " string" if allow_empty else " non-empty string"
        fail("input_error", f"{key} must be a{suffix}")
    if "\0" in value:
        fail("input_error", f"{key} contains NUL")
    return value


def optional_string(
    payload: dict[str, Any],
    key: str,
    *,
    allow_empty: bool = False,
) -> str | None:
    if key not in payload:
        return None
    return string(payload, key, allow_empty=allow_empty)


def boolean(payload: dict[str, Any], key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        fail("input_error", f"{key} must be a boolean")
    return value


def nonnegative_integer(payload: dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        fail("input_error", f"{key} must be a non-negative integer")
    return value


def expected_hash(payload: dict[str, Any]) -> str | None:
    value = optional_string(payload, "expected_sha256")
    if value is None:
        return None
    normalized = value.casefold()
    if len(normalized) != 64 or any(ch not in "0123456789abcdef" for ch in normalized):
        fail("input_error", "expected_sha256 must be a 64-character hex digest")
    return normalized


def ensure_text_size(value: str, field: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > MAX_NOTE_BYTES:
        fail("input_error", f"{field} exceeds the note size limit")
    return encoded


def current_uid() -> int | None:
    getter = getattr(os, "geteuid", None)
    return getter() if getter is not None else None


def check_owner(metadata: os.stat_result, kind: str) -> None:
    if not _owned_metadata(metadata):
        fail("unsafe_path", f"{kind} is not owned by the current user")


def ensure_supported_platform() -> None:
    """Reject platforms where the containment/locking contract is unavailable."""
    required_dir_fd = (os.open, os.stat, os.mkdir, os.unlink, os.link, os.rename)
    if (
        os.name != "posix"
        or fcntl is None
        or not getattr(os, "O_NOFOLLOW", 0)
        or not getattr(os, "O_DIRECTORY", 0)
        or any(function not in os.supports_dir_fd for function in required_dir_fd)
    ):
        fail(
            "unsupported_platform",
            "secure direct vault writes are unavailable on this platform",
        )


def discover_vault(vault: str) -> Path:
    if any(char in vault for char in ("\0", "\r", "\n")):
        fail("input_error", "vault contains a control character")
    try:
        result = subprocess.run(
            ["obsidian", "vault", f"vault={vault}"],
            check=False,
            capture_output=True,
            shell=False,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        fail("vault_unavailable", "unable to resolve the Obsidian vault")
    if result.returncode != 0:
        fail("vault_unavailable", "unable to resolve the Obsidian vault")

    raw_path: str | None = None
    for line in result.stdout.splitlines():
        field, separator, value = line.partition("\t")
        if field == "path" and separator and value:
            raw_path = value
            break
    if raw_path is None:
        fail("vault_unavailable", "Obsidian did not return a vault path")

    lexical = Path(raw_path).expanduser()
    if not lexical.is_absolute():
        fail("vault_unavailable", "Obsidian returned a non-absolute vault path")
    try:
        lexical_metadata = os.lstat(lexical)
    except OSError:
        fail("vault_unavailable", "the resolved vault is unavailable")
    if stat.S_ISLNK(lexical_metadata.st_mode):
        fail("unsafe_path", "the vault root must not be a symlink")
    if not stat.S_ISDIR(lexical_metadata.st_mode):
        fail("vault_unavailable", "the resolved vault is not a directory")
    check_owner(lexical_metadata, "vault root")
    try:
        root = lexical.resolve(strict=True)
    except OSError:
        fail("vault_unavailable", "the resolved vault is unavailable")
    return root


def normalize_note(note: str) -> tuple[str, ...]:
    if any(char in note for char in ("\0", "\r", "\n")):
        fail("unsafe_path", "note path contains a control character")
    # Reject Windows syntax explicitly even on POSIX so the contract remains
    # fail-closed when the same plugin is moved between runtimes/platforms.
    windows = PureWindowsPath(note)
    if windows.is_absolute() or windows.drive or "\\" in note:
        fail("unsafe_path", "note path must use relative POSIX components")
    path = PurePosixPath(note)
    if path.is_absolute() or note.startswith("/"):
        fail("unsafe_path", "note path must be relative")
    if not note or note.endswith("/") or "//" in note:
        fail("unsafe_path", "note path is not canonical")

    raw_parts = note.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        fail("unsafe_path", "note path contains an unsafe component")
    if any(part.casefold() in RESERVED_DIRS for part in raw_parts):
        fail("unsafe_path", "note path enters a reserved vault directory")
    if not raw_parts[-1].endswith(".md"):
        raw_parts[-1] += ".md"
    if sum(len(part.encode("utf-8")) + 1 for part in raw_parts) > MAX_PATH_BYTES:
        fail("unsafe_path", "note path is too long")
    if any(len(part.encode("utf-8")) > MAX_COMPONENT_BYTES for part in raw_parts):
        fail("unsafe_path", "note path component is too long")
    return tuple(raw_parts)


def validate_create_filename(parts: tuple[str, ...]) -> None:
    stem = parts[-1][:-3]  # normalize_note guarantees the `.md` suffix.
    if not stem or "#" in stem or "." in stem:
        fail(
            "unsafe_path",
            "new note filename stem must be non-empty and contain neither '#' nor '.'",
        )


def verify_lexical_containment(root: Path, parts: tuple[str, ...]) -> None:
    lexical = root.joinpath(*parts)
    try:
        lexical.relative_to(root)
        lexical.parent.resolve(strict=False).relative_to(root)
    except (OSError, ValueError):
        fail("unsafe_path", "note path escapes the vault")


def directory_flags() -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    return flags


def open_parent(
    root: Path,
    parent_parts: tuple[str, ...],
    *,
    create: bool,
) -> int:
    try:
        current = os.open(root, directory_flags())
    except OSError:
        fail("unsafe_path", "unable to open the vault root safely")
    try:
        check_owner(os.fstat(current), "vault root")
        for component in parent_parts:
            try:
                child = os.open(component, directory_flags(), dir_fd=current)
            except FileNotFoundError:
                if not create:
                    fail("not_found", "note parent directory does not exist")
                try:
                    os.mkdir(component, 0o700, dir_fd=current)
                    os.fsync(current)
                    child = os.open(component, directory_flags(), dir_fd=current)
                except FileExistsError:
                    # A concurrent creator won the race; open and validate it.
                    try:
                        child = os.open(component, directory_flags(), dir_fd=current)
                    except OSError:
                        fail("unsafe_path", "note parent changed during traversal")
                except OSError:
                    fail("unsafe_path", "unable to create note parent safely")
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                    fail("unsafe_path", "note parent contains a symlink or non-directory")
                fail("unsafe_path", "unable to traverse note parent safely")

            try:
                metadata = os.fstat(child)
                if not stat.S_ISDIR(metadata.st_mode):
                    fail("unsafe_path", "note parent component is not a directory")
                check_owner(metadata, "note parent")
            except Exception:
                os.close(child)
                raise
            os.close(current)
            current = child
        return current
    except Exception:
        os.close(current)
        raise


def target_metadata(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        fail("unsafe_path", "unable to inspect note target safely")
    if stat.S_ISLNK(metadata.st_mode):
        fail("unsafe_path", "note target must not be a symlink")
    return metadata


def read_current(parent_fd: int, name: str) -> CurrentFile:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        fail("not_found", "note does not exist")
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            fail("unsafe_path", "note target must be a regular non-symlink file")
        fail("unsafe_path", "unable to open note safely")

    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            fail("unsafe_path", "note target must be a regular file")
        check_owner(metadata, "note target")
        if metadata.st_size > MAX_NOTE_BYTES:
            fail("input_error", "existing note exceeds the note size limit")
        assert fcntl is not None  # ensured before any vault operation
        fcntl.flock(fd, fcntl.LOCK_EX)
        raw = read_fd_bounded(fd, MAX_NOTE_BYTES)
        if len(raw) > MAX_NOTE_BYTES:
            fail("input_error", "existing note exceeds the note size limit")
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError:
            fail("input_error", "existing note is not valid UTF-8")
        return CurrentFile(
            fd=fd,
            body=body,
            raw=raw,
            metadata=metadata,
            sha256=hashlib.sha256(raw).hexdigest(),
        )
    except Exception:
        os.close(fd)
        raise


def assert_preconditions(current: CurrentFile, payload: dict[str, Any]) -> None:
    wanted = expected_hash(payload)
    if wanted is not None and wanted != current.sha256:
        fail("precondition_failed", "note changed since the caller read it")


def read_fd_bounded(fd: int, maximum: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = maximum + 1
    while remaining:
        chunk = os.read(fd, min(64 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def assert_unchanged(parent_fd: int, name: str, current: CurrentFile) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        probe = os.open(name, flags, dir_fd=parent_fd)
    except OSError:
        fail("precondition_failed", "note changed during the write")
    try:
        metadata = os.fstat(probe)
        identity = (metadata.st_dev, metadata.st_ino)
        original_identity = (current.metadata.st_dev, current.metadata.st_ino)
        if identity != original_identity:
            fail("precondition_failed", "note changed during the write")
        if (
            metadata.st_size != current.metadata.st_size
            or metadata.st_mtime_ns != current.metadata.st_mtime_ns
            or stat.S_IMODE(metadata.st_mode) != stat.S_IMODE(current.metadata.st_mode)
        ):
            fail("precondition_failed", "note changed during the write")
        raw = read_fd_bounded(probe, MAX_NOTE_BYTES)
        if len(raw) > MAX_NOTE_BYTES or hashlib.sha256(raw).hexdigest() != current.sha256:
            fail("precondition_failed", "note changed during the write")
    finally:
        os.close(probe)


def unique_temp_name() -> str:
    return f".mnemo-write-{os.getpid()}-{secrets.token_hex(12)}.tmp"


def write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            fail("io_error", "unable to write the temporary note")
        view = view[written:]


def write_temp(parent_fd: int, data: bytes, mode: int) -> str:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    for _ in range(16):
        name = unique_temp_name()
        try:
            fd = os.open(name, flags, 0o600, dir_fd=parent_fd)
        except FileExistsError:
            continue
        except OSError:
            fail("io_error", "unable to create a private temporary note")
        try:
            os.fchmod(fd, mode)
            write_all(fd, data)
            os.fsync(fd)
        except Exception:
            os.close(fd)
            try:
                os.unlink(name, dir_fd=parent_fd)
            except OSError:
                pass
            raise
        os.close(fd)
        return name
    fail("io_error", "unable to allocate a private temporary note")


def unlink_temp(parent_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass
    except OSError:
        # The target write has already failed or succeeded atomically; never
        # mask that outcome with a cleanup-only error.
        pass


def atomic_create(parent_fd: int, name: str, raw: bytes) -> None:
    existing = target_metadata(parent_fd, name)
    if existing is not None:
        fail("conflict", "note already exists")
    temp = write_temp(parent_fd, raw, 0o600)
    linked = False
    try:
        try:
            os.link(
                temp,
                name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
            linked = True
        except FileExistsError:
            fail("conflict", "note appeared during create")
        except OSError:
            fail("io_error", "unable to publish the new note atomically")
        os.fsync(parent_fd)
    finally:
        unlink_temp(parent_fd, temp)
        if linked:
            os.fsync(parent_fd)


def atomic_exchange(parent_fd: int, first: str, second: str) -> None:
    """Atomically swap two directory entries without discarding either inode."""
    libc = ctypes.CDLL(None, use_errno=True)
    encoded_first = os.fsencode(first)
    encoded_second = os.fsencode(second)
    if sys.platform == "darwin":
        operation = getattr(libc, "renameatx_np", None)
    elif sys.platform.startswith("linux"):
        operation = getattr(libc, "renameat2", None)
    else:  # guarded by ensure_supported_platform; keep the primitive explicit
        operation = None
    if operation is None:
        fail("unsupported_platform", "atomic exchange is unavailable on this platform")
    operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    operation.restype = ctypes.c_int
    if operation(parent_fd, encoded_first, parent_fd, encoded_second, 2) != 0:
        error = ctypes.get_errno()
        if error in {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL}:
            fail("unsupported_platform", "the vault filesystem lacks atomic exchange")
        fail("io_error", "unable to exchange the note atomically")


def current_matches(current: CurrentFile, metadata: os.stat_result, raw: bytes) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and _owned_metadata(metadata)
        and (metadata.st_dev, metadata.st_ino)
        == (current.metadata.st_dev, current.metadata.st_ino)
        and stat.S_IMODE(metadata.st_mode) == stat.S_IMODE(current.metadata.st_mode)
        and hashlib.sha256(raw).hexdigest() == current.sha256
    )


def entry_matches(
    metadata: os.stat_result,
    raw: bytes,
    expected_metadata: os.stat_result,
    expected_raw: bytes,
) -> bool:
    return (
        stat.S_ISREG(metadata.st_mode)
        and _owned_metadata(metadata)
        and (metadata.st_dev, metadata.st_ino)
        == (expected_metadata.st_dev, expected_metadata.st_ino)
        and stat.S_IMODE(metadata.st_mode) == stat.S_IMODE(expected_metadata.st_mode)
        and raw == expected_raw
    )


def _owned_metadata(metadata: os.stat_result) -> bool:
    uid = current_uid()
    return uid is None or metadata.st_uid == uid


def read_private_entry(parent_fd: int, name: str) -> tuple[os.stat_result, bytes]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError:
        fail("io_error", "unable to verify the displaced note")
    try:
        metadata = os.fstat(fd)
        raw = read_fd_bounded(fd, MAX_NOTE_BYTES)
    finally:
        os.close(fd)
    if len(raw) > MAX_NOTE_BYTES:
        fail("input_error", "displaced note exceeds the note size limit")
    if not stat.S_ISREG(metadata.st_mode) or not _owned_metadata(metadata):
        fail("io_error", "displaced note is not a safe regular file")
    return metadata, raw


def preserve_conflict(parent_fd: int, name: str) -> None:
    """Give a displaced concurrent version a durable, non-temporary name."""
    conflict = f".mnemo-conflict-{os.getpid()}-{secrets.token_hex(8)}"
    try:
        os.rename(
            name,
            conflict,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
    except OSError:
        # The private entry is already durable. Leave it in place rather than
        # risking deletion when a friendlier recovery name cannot be created.
        pass
    os.fsync(parent_fd)


def atomic_replace(
    parent_fd: int,
    name: str,
    current: CurrentFile,
    raw: bytes,
) -> None:
    mode = stat.S_IMODE(current.metadata.st_mode)
    temp = write_temp(parent_fd, raw, mode)
    cleanup_temp = True
    try:
        published_metadata, published_raw = read_private_entry(parent_fd, temp)
        assert_unchanged(parent_fd, name, current)
        atomic_exchange(parent_fd, temp, name)
        # The private entry now holds the displaced public version. Preserve it
        # on every unexpected verification failure until we can prove it is the
        # exact version the caller read.
        cleanup_temp = False
        displaced_metadata, displaced_raw = read_private_entry(parent_fd, temp)
        if not current_matches(current, displaced_metadata, displaced_raw):
            # Restore the displaced version only while our published inode is
            # still public. A later writer wins and remains at the public path;
            # the earlier displaced version is retained as a conflict copy.
            public_metadata, public_raw = read_private_entry(parent_fd, name)
            if not entry_matches(
                public_metadata,
                public_raw,
                published_metadata,
                published_raw,
            ):
                preserve_conflict(parent_fd, temp)
                fail(
                    "precondition_failed",
                    "note changed during publish; a conflict copy was preserved",
                )
            atomic_exchange(parent_fd, temp, name)
            os.fsync(parent_fd)
            private_metadata, private_raw = read_private_entry(parent_fd, temp)
            if not entry_matches(
                private_metadata,
                private_raw,
                published_metadata,
                published_raw,
            ):
                # A second writer replaced our public inode between the check
                # and rollback exchange. Put that newer version back, provided
                # the first displaced version is still public, then retain the
                # latter as a conflict copy.
                rollback_metadata, rollback_raw = read_private_entry(parent_fd, name)
                if entry_matches(
                    rollback_metadata,
                    rollback_raw,
                    displaced_metadata,
                    displaced_raw,
                ):
                    atomic_exchange(parent_fd, temp, name)
                    os.fsync(parent_fd)
                preserve_conflict(parent_fd, temp)
                fail(
                    "precondition_failed",
                    "note changed during publish; a conflict copy was preserved",
                )
            cleanup_temp = True
            fail("precondition_failed", "note changed during publish")
        cleanup_temp = True
        os.fsync(parent_fd)
    finally:
        if cleanup_temp:
            unlink_temp(parent_fd, temp)


def unique_occurrence(body: str, needle: str, label: str) -> int:
    first = body.find(needle)
    if first < 0 or body.find(needle, first + 1) >= 0:
        fail("precondition_failed", f"{label} must occur exactly once")
    return first


def transform_replace(current: CurrentFile, payload: dict[str, Any]) -> str:
    old = string(payload, "old_str")
    new = string(payload, "new_str", allow_empty=True)
    position = unique_occurrence(current.body, old, "old_str")
    return current.body[:position] + new + current.body[position + len(old) :]


def transform_insert(current: CurrentFile, payload: dict[str, Any]) -> str:
    anchor = string(payload, "anchor")
    content = string(payload, "content", allow_empty=True)
    position = optional_string(payload, "position") or "after"
    if position not in {"before", "after"}:
        fail("input_error", "position must be 'before' or 'after'")
    index = unique_occurrence(current.body, anchor, "anchor")
    if "expected_line" in payload:
        line = payload["expected_line"]
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            fail("input_error", "expected_line must be a positive integer")
        actual_line = current.body.count("\n", 0, index) + 1
        if line != actual_line:
            fail("precondition_failed", "anchor is not on the expected line")
    insertion = index if position == "before" else index + len(anchor)
    return current.body[:insertion] + content + current.body[insertion:]


def transform_append(current: CurrentFile, payload: dict[str, Any]) -> str:
    tail = optional_string(payload, "expected_tail")
    if tail is None and "expected_sha256" not in payload:
        fail("input_error", "append requires expected_tail or expected_sha256")
    if tail is not None and not current.body.endswith(tail):
        fail("precondition_failed", "note no longer has the expected tail")
    return current.body + string(payload, "content", allow_empty=True)


def split_handoff(body: str) -> tuple[str, list[str]]:
    match = re.search(r"^## \d{4}-\d{2}-\d{2}", body, re.MULTILINE)
    if match is None:
        return body, []
    header = body[: match.start()]
    dated = body[match.start() :]
    blocks = [
        block
        for block in re.split(
            r"(?=^## \d{4}-\d{2}-\d{2})",
            dated,
            flags=re.MULTILINE,
        )
        if block.strip()
    ]
    return header, blocks


def handoff_block_date(block: str) -> dt.date | None:
    match = DATE_HEADER_RE.match(block)
    if match is None:
        return None
    try:
        return dt.date.fromisoformat(match.group(1))
    except ValueError:
        return None


def join_blocks(blocks: list[str]) -> str:
    return "".join(block if block.endswith("\n") else block + "\n" for block in blocks)


def archive_header(handoff_note: str, archive_note: str) -> str:
    return (
        "---\ntype: meta\ntags: [meta, handoff, archive, cold]\n---\n\n"
        f"# {Path(archive_note).name}\n\n"
        f"> ❄️ Cold archive of [[{handoff_note}]] — closed blocks, NOT read at "
        "session start. Detail lives in linked session notes; this is a verbatim "
        f"chronological backstop. Fresh / open items stay in hot [[{handoff_note}]].\n\n"
    )


def plan_handoff_archive(
    body: str,
    archive_body: str | None,
    *,
    handoff_note: str,
    archive_note: str,
    max_kb: int,
    keep_days: int,
    today: dt.date,
) -> tuple[bytes, bytes, int, int]:
    header, blocks = split_handoff(body)
    cutoff = today - dt.timedelta(days=keep_days)
    hot: list[str] = []
    cold: list[str] = []
    for block in blocks:
        block_date = handoff_block_date(block)
        first_line = block.split("\n", 1)[0]
        keep = (
            block_date is None
            or block_date >= cutoff
            or OPEN_TODO_RE.search(block) is not None
            or HEADER_PENDING_RE.search(first_line) is not None
        )
        (hot if keep else cold).append(block)

    if not cold:
        return b"", b"", 0, len(hot)

    new_header = header
    if HANDOFF_GUARD_MARK not in header:
        guard = (
            f"\n🛡️ **SIZE-GUARD (check at mn:session):** handoff >{max_kb}KB → "
            f"move CLOSED blocks older than ~{keep_days}d to [[{archive_note}]]; "
            "open `- [ ]` + recent stay hot. The bundled `vault-write.py` archive "
            f"action applies this guard atomically. 🔎 missing entry → read [[{archive_note}]].\n\n"
        )
        frontmatter = re.match(r"^(---\n.*?\n---\n)", header, re.DOTALL)
        if frontmatter is None:
            new_header = guard + header
        else:
            new_header = (
                header[: frontmatter.end()] + guard + header[frontmatter.end() :]
            )
    new_handoff = new_header + join_blocks(hot)

    if archive_body is None:
        new_archive = archive_header(handoff_note, archive_note) + join_blocks(cold)
    else:
        archive_prefix, existing_blocks = split_handoff(archive_body)
        archive_history = archive_body[len(archive_prefix) :]
        # If a previous run published the archive but crashed before trimming
        # the handoff, retrying must remove the hot copy without duplicating it.
        archived_blocks = Counter(
            block.rstrip("\n") for block in existing_blocks
        )
        missing: list[str] = []
        for block in cold:
            canonical = block.rstrip("\n")
            if archived_blocks[canonical]:
                archived_blocks[canonical] -= 1
            else:
                missing.append(block)
        if archive_prefix and missing:
            archive_prefix = archive_prefix.rstrip("\n") + "\n\n"
        new_archive = archive_prefix + join_blocks(missing) + archive_history
    new_handoff_raw = ensure_text_size(new_handoff, "resulting handoff")
    new_archive_raw = ensure_text_size(new_archive, "resulting handoff archive")
    return new_handoff_raw, new_archive_raw, len(cold), len(hot)


def create_backup(
    parent_fd: int,
    name: str,
    raw: bytes,
    stamp: str,
) -> str:
    base = f"{name}.bak-{stamp}"
    for sequence in range(1, 100):
        candidate = base if sequence == 1 else f"{base}-{sequence}"
        try:
            atomic_create(parent_fd, candidate, raw)
            return candidate
        except WriteError as exc:
            if exc.code != "conflict":
                raise
    fail("conflict", "unable to allocate a unique handoff backup")


def archive_handoff(
    payload: dict[str, Any],
    vault: Path,
    handoff_parts: tuple[str, ...],
) -> dict[str, Any]:
    max_kb = nonnegative_integer(payload, "max_kb", 40)
    keep_days = nonnegative_integer(payload, "keep_days", 14)
    raw_today = optional_string(payload, "today")
    try:
        today = dt.date.fromisoformat(raw_today) if raw_today else dt.date.today()
    except ValueError:
        fail("input_error", "today must be YYYY-MM-DD")

    handoff_note = "/".join(handoff_parts)[:-3]
    raw_archive = optional_string(payload, "archive")
    if raw_archive is None:
        archive_parts = (*handoff_parts[:-1], f"{handoff_parts[-1][:-3]} Archive.md")
    else:
        archive_parts = normalize_note(raw_archive)
    archive_note = "/".join(archive_parts)[:-3]
    if archive_parts == handoff_parts:
        fail("input_error", "handoff and archive notes must be different")
    verify_lexical_containment(vault, archive_parts)

    handoff_parent = open_parent(vault, handoff_parts[:-1], create=False)
    archive_parent: int | None = None
    handoff_current: CurrentFile | None = None
    archive_current: CurrentFile | None = None
    try:
        handoff_current = read_current(handoff_parent, handoff_parts[-1])
        assert_preconditions(handoff_current, payload)
        if len(handoff_current.raw) <= max_kb * 1024:
            return {
                "ok": True,
                "action": "archive-handoff",
                "note": "/".join(handoff_parts),
                "archive": "/".join(archive_parts),
                "archived_blocks": 0,
                "hot_blocks": sum(
                    1
                    for _ in re.finditer(
                        r"^## \d{4}-\d{2}-\d{2}",
                        handoff_current.body,
                        re.MULTILINE,
                    )
                ),
                "backup": None,
                "noop": "under_size_limit",
            }

        archive_parent = open_parent(vault, archive_parts[:-1], create=False)
        archive_metadata = target_metadata(archive_parent, archive_parts[-1])
        if archive_metadata is not None:
            if (archive_metadata.st_dev, archive_metadata.st_ino) == (
                handoff_current.metadata.st_dev,
                handoff_current.metadata.st_ino,
            ):
                fail("input_error", "handoff and archive notes must not share a file")
            archive_current = read_current(archive_parent, archive_parts[-1])
            existing_archive = archive_current.body
        else:
            existing_archive = None
        handoff_raw, archive_raw, cold_count, hot_count = plan_handoff_archive(
            handoff_current.body,
            existing_archive,
            handoff_note=handoff_note,
            archive_note=archive_note,
            max_kb=max_kb,
            keep_days=keep_days,
            today=today,
        )
        if cold_count == 0:
            return {
                "ok": True,
                "action": "archive-handoff",
                "note": "/".join(handoff_parts),
                "archive": "/".join(archive_parts),
                "archived_blocks": 0,
                "hot_blocks": hot_count,
                "backup": None,
                "noop": "no_closed_old_blocks",
            }

        backup = create_backup(
            handoff_parent,
            handoff_parts[-1],
            handoff_current.raw,
            today.isoformat(),
        )
        if archive_current is None:
            validate_create_filename(archive_parts)
            atomic_create(archive_parent, archive_parts[-1], archive_raw)
        elif archive_raw != archive_current.raw:
            atomic_replace(
                archive_parent,
                archive_parts[-1],
                archive_current,
                archive_raw,
            )
        atomic_replace(
            handoff_parent,
            handoff_parts[-1],
            handoff_current,
            handoff_raw,
        )
        return {
            "ok": True,
            "action": "archive-handoff",
            "note": "/".join(handoff_parts),
            "archive": "/".join(archive_parts),
            "archived_blocks": cold_count,
            "hot_blocks": hot_count,
            "backup": "/".join((*handoff_parts[:-1], backup)),
            "bytes": len(handoff_raw),
            "sha256": hashlib.sha256(handoff_raw).hexdigest(),
            "previous_sha256": handoff_current.sha256,
        }
    finally:
        if archive_current is not None:
            os.close(archive_current.fd)
        if handoff_current is not None:
            os.close(handoff_current.fd)
        if archive_parent is not None:
            os.close(archive_parent)
        os.close(handoff_parent)


def write(payload: dict[str, Any]) -> dict[str, Any]:
    action = string(payload, "action")
    if action not in VALID_ACTIONS:
        fail(
            "input_error",
            "action must be create, replace, insert, append, or archive-handoff",
        )
    ensure_supported_platform()
    vault = discover_vault(string(payload, "vault"))
    parts = normalize_note(string(payload, "note"))
    if action == "archive-handoff":
        verify_lexical_containment(vault, parts)
        return archive_handoff(payload, vault, parts)
    create_raw: bytes | None = None
    if action == "create":
        validate_create_filename(parts)
        create_raw = ensure_text_size(
            string(payload, "content", allow_empty=True),
            "content",
        )
    verify_lexical_containment(vault, parts)
    parent_fd = open_parent(
        vault,
        parts[:-1],
        create=boolean(payload, "create_parents"),
    )
    name = parts[-1]
    relative = "/".join(parts)
    try:
        if action == "create":
            assert create_raw is not None
            raw = create_raw
            atomic_create(parent_fd, name, raw)
            before_hash = None
        else:
            current = read_current(parent_fd, name)
            try:
                assert_preconditions(current, payload)
                if action == "replace":
                    body = transform_replace(current, payload)
                elif action == "insert":
                    body = transform_insert(current, payload)
                else:
                    body = transform_append(current, payload)
                raw = ensure_text_size(body, "resulting note")
                atomic_replace(parent_fd, name, current, raw)
                before_hash = current.sha256
            finally:
                os.close(current.fd)
    finally:
        os.close(parent_fd)

    return {
        "ok": True,
        "action": action,
        "note": relative,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "previous_sha256": before_hash,
    }


def emit(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    try:
        emit(write(load_payload()))
        return 0
    except WriteError as exc:
        emit({"ok": False, "error": {"code": exc.code, "message": exc.message}})
        return 2
    except Exception:
        # Fail closed without leaking note content, subprocess diagnostics, or
        # Python tracebacks into an agent transcript.
        emit(
            {
                "ok": False,
                "error": {
                    "code": "internal_error",
                    "message": "vault write failed unexpectedly",
                },
            }
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Private, symlink-safe cache primitives shared by mnemo helper scripts."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import time
from pathlib import Path
from typing import Any


def _uid() -> int:
    return os.getuid() if hasattr(os, "getuid") else 0


def private_cache_dir() -> Path:
    """Return a per-user 0700 temp directory, rejecting symlinks or foreign owners."""
    root = Path(tempfile.gettempdir()) / f"mnemo-{_uid()}"
    try:
        root.mkdir(mode=0o700)
    except FileExistsError:
        pass

    info = root.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise OSError(f"unsafe mnemo cache directory: {root}")
    if hasattr(os, "getuid") and info.st_uid != _uid():
        raise OSError(f"mnemo cache directory has a foreign owner: {root}")
    root.chmod(0o700)
    return root


def cache_path(kind: str, identity: str, suffix: str) -> Path | None:
    """Build a non-sensitive cache path; caller identities are represented by a hash."""
    digest = hashlib.sha256(identity.encode("utf-8", "surrogatepass")).hexdigest()[:24]
    try:
        return private_cache_dir() / f"{kind}-{digest}.{suffix}"
    except OSError:
        return None


def _open_private(path: Path | None):
    if path is None:
        raise OSError("private cache unavailable")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        os.close(fd)
        raise OSError(f"cache is not a regular file: {path}")
    if hasattr(os, "getuid") and info.st_uid != _uid():
        os.close(fd)
        raise OSError(f"cache has a foreign owner: {path}")
    if stat.S_IMODE(info.st_mode) & 0o077:
        os.close(fd)
        raise OSError(f"cache permissions are too broad: {path}")
    return os.fdopen(fd)


def read_json(path: Path | None) -> Any | None:
    try:
        with _open_private(path) as handle:
            return json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def read_text(path: Path | None) -> str | None:
    try:
        with _open_private(path) as handle:
            return handle.read()
    except (OSError, UnicodeError):
        return None


def _atomic_write(path: Path | None, content: str) -> bool:
    if path is None:
        return False
    temp_path: str | None = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        return True
    except OSError:
        return False
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def atomic_write_json(path: Path | None, value: Any) -> bool:
    return _atomic_write(path, json.dumps(value))


def atomic_write_text(path: Path | None, value: str) -> bool:
    return _atomic_write(path, value)


def is_fresh(path: Path | None, ttl: float) -> bool:
    if path is None:
        return False
    try:
        with _open_private(path) as handle:
            age = max(0.0, time.time() - os.fstat(handle.fileno()).st_mtime)
        return age < ttl
    except OSError:
        return False

#!/usr/bin/env python3
"""Shell-free adapters for mnemo's dynamic read/index operations.

The action is a static CLI argument. Untrusted vault names, note names, search
terms, and paths arrive as JSON on stdin, then are passed as argv elements (or
JSON-escaped JavaScript literals) without a shell.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


MAX_INPUT_BYTES = 1024 * 1024
SKIP_DIRS = {".obsidian", ".trash"}


class InputError(ValueError):
    pass


def load_payload() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise InputError("input exceeds 1 MiB")
    try:
        value = json.loads(raw or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(f"invalid JSON input: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError("input must be a JSON object")
    return value


def text(payload: dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or (not allow_empty and not value):
        raise InputError(f"{key} must be a non-empty string")
    if "\0" in value:
        raise InputError(f"{key} contains NUL")
    return value


def integer(payload: dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise InputError(f"{key} must be a non-negative integer")
    return value


def strings(payload: dict[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise InputError(f"{key} must be a non-empty string array")
    if any(not isinstance(item, str) or not item or "\0" in item for item in value):
        raise InputError(f"{key} must contain only non-empty strings without NUL")
    return value


def run(argv: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=False,
        text=True,
        capture_output=capture,
    )


def run_obsidian(parts: list[str]) -> int:
    return run(["obsidian", *parts]).returncode


def resolve_vault_path(vault: str) -> Path:
    result = run(["obsidian", "vault", f"vault={vault}"], capture=True)
    if result.returncode != 0:
        raise InputError(result.stderr.strip() or "unable to resolve vault")
    for line in result.stdout.splitlines():
        field, separator, value = line.partition("\t")
        if field == "path" and separator:
            root = Path(value).expanduser().resolve()
            if root.is_dir():
                return root
            raise InputError("resolved vault path is not a directory")
    raise InputError("obsidian vault output did not contain a path")


def vault_root(payload: dict[str, Any]) -> Path:
    # Filesystem scans stay anchored to a vault resolved by Obsidian. Accepting
    # an arbitrary caller-supplied path would defeat that containment boundary.
    root = resolve_vault_path(text(payload, "vault"))
    if not root.is_dir():
        raise InputError("vault_path must resolve to a directory")
    return root


def markdown_files(root: Path):
    for path in root.rglob("*.md"):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        # Never let a vault-local symlink turn a read-only scan into disclosure
        # of an arbitrary file outside the vault.
        if not path.is_symlink() and path.is_file():
            yield path, relative


OBSIDIAN_ACTIONS = {
    "search",
    "read",
    "orphans",
    "unresolved",
    "tags",
    "files-total",
    "backlinks",
    "top-unresolved",
    "shared-targets",
    "resolved-backlink-count",
}


def obsidian_action(action: str, payload: dict[str, Any]) -> int | None:
    if action not in OBSIDIAN_ACTIONS:
        return None
    vault = text(payload, "vault")
    if action == "search":
        return run_obsidian(["search", f"query={text(payload, 'query')}", f"vault={vault}"])
    if action == "read":
        return run_obsidian(["read", f"file={text(payload, 'file')}", f"vault={vault}"])
    if action == "orphans":
        return run_obsidian(["orphans", f"vault={vault}"])
    if action == "unresolved":
        return run_obsidian(["unresolved", f"vault={vault}"])
    if action == "tags":
        return run_obsidian(["tags", "counts", "sort=count", f"vault={vault}"])
    if action == "files-total":
        return run_obsidian(["files", "ext=md", f"vault={vault}", "total"])
    if action == "backlinks":
        return run_obsidian(["backlinks", f"file={text(payload, 'file')}", f"vault={vault}"])
    if action == "top-unresolved":
        code = (
            "(()=>{const u=app.metadataCache.unresolvedLinks;const f={};"
            "Object.values(u).forEach(l=>Object.keys(l).forEach(t=>f[t]=(f[t]||0)+1));"
            "return JSON.stringify(Object.entries(f).sort((a,b)=>b[1]-a[1]).slice(0,10));})()"
        )
        return run_obsidian(["eval", f"code={code}", f"vault={vault}"])
    if action == "shared-targets":
        note = json.dumps(text(payload, "note_path"))
        code = (
            "(()=>{const rl=app.metadataCache.resolvedLinks;"
            f"const t=Object.keys(rl[{note}]||{{}});const r={{}};"
            f"for(const[f,l]of Object.entries(rl)){{if(f==={note})continue;"
            "const s=Object.keys(l).filter(x=>t.includes(x));if(s.length>=2)r[f]=s;}"
            "return JSON.stringify(r);})()"
        )
        return run_obsidian(["eval", f"code={code}", f"vault={vault}"])
    if action == "resolved-backlink-count":
        target = json.dumps(text(payload, "target"))
        code = (
            "(()=>{let n=0;for(const f of app.vault.getMarkdownFiles()){"
            "const rl=app.metadataCache.resolvedLinks[f.path]||{};"
            f"for(const k in rl)if(k.endsWith({target}))n++;}}return n;}})()"
        )
        return run_obsidian(["eval", f"code={code}", f"vault={vault}"])
    raise AssertionError(f"unhandled Obsidian action: {action}")


def action_vault_path(payload: dict[str, Any]) -> int:
    print(resolve_vault_path(text(payload, "vault")))
    return 0


def action_grep_concepts(payload: dict[str, Any]) -> int:
    root = vault_root(payload)
    needles = [item.casefold() for item in strings(payload, "concepts")]
    for path, relative in markdown_files(root):
        try:
            body = path.read_text(errors="replace").casefold()
        except OSError:
            continue
        if any(needle in body for needle in needles):
            print(relative)
    return 0


def action_missing_links(payload: dict[str, Any]) -> int:
    root = vault_root(payload)
    heading = text(payload, "links_section")
    prefixes = strings(payload, "prefixes")
    for path, relative in markdown_files(root):
        if not path.name.startswith(tuple(prefixes)):
            continue
        try:
            body = path.read_text(errors="replace")
        except OSError:
            continue
        if heading not in body:
            print(relative)
    return 0


def action_bad_filenames(payload: dict[str, Any]) -> int:
    root = vault_root(payload)
    for path, relative in markdown_files(root):
        # Check the note filename without the expected Markdown extension.
        # A period inside the stem breaks Obsidian CLI creation/resolution, but
        # the terminal `.md` itself is valid and must not flag every note.
        if "#" in path.stem or "." in path.stem:
            print(relative)
    return 0


def action_moc_names(payload: dict[str, Any]) -> int:
    root = vault_root(payload)
    prefix = text(payload, "prefix")
    for path, _ in markdown_files(root):
        if path.name.startswith(prefix):
            print(path.stem)
    return 0


def safe_note_path(root: Path, note: str) -> tuple[Path, str]:
    relative = note if note.endswith(".md") else f"{note}.md"
    lexical = root / relative
    if lexical.is_symlink():
        raise InputError("note path must not be a symlink")
    candidate = lexical.resolve()
    try:
        clean_relative = str(candidate.relative_to(root))
    except ValueError as exc:
        raise InputError("note escapes vault_path") from exc
    return candidate, clean_relative


def action_note_date(payload: dict[str, Any]) -> int:
    root = vault_root(payload)
    candidate, relative = safe_note_path(root, text(payload, "note"))
    if not candidate.is_file():
        raise InputError("note does not exist")

    inside = run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture=True)
    if inside.returncode == 0:
        changed = run(
            ["git", "-C", str(root), "log", "-1", "--format=%cs", "--", relative],
            capture=True,
        )
        if changed.returncode == 0 and changed.stdout.strip():
            print(changed.stdout.strip())
            return 0
    print(dt.date.fromtimestamp(candidate.stat().st_mtime).isoformat())
    return 0


def action_review_candidates(payload: dict[str, Any]) -> int:
    script = Path(__file__).with_name("review-candidates.py")
    root = vault_root(payload)
    limit = integer(payload, "limit", 30)
    return run([sys.executable, str(script), str(root), "--limit", str(limit)]).returncode


def action_git_log_grep(payload: dict[str, Any]) -> int:
    return run(
        ["git", "log", "--oneline", "-n", "15", "-i", f"--grep={text(payload, 'term')}"]
    ).returncode


def action_git_log_path(payload: dict[str, Any]) -> int:
    return run(
        ["git", "log", "--oneline", "-n", "10", "--", text(payload, "pathspec")]
    ).returncode


ACTIONS = {
    "vault-path": action_vault_path,
    "grep-concepts": action_grep_concepts,
    "missing-links": action_missing_links,
    "bad-filenames": action_bad_filenames,
    "moc-names": action_moc_names,
    "note-date": action_note_date,
    "review-candidates": action_review_candidates,
    "git-log-grep": action_git_log_grep,
    "git-log-path": action_git_log_path,
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: safe-read.py ACTION < payload.json", file=sys.stderr)
        return 2
    action = sys.argv[1]
    try:
        payload = load_payload()
        obsidian_result = obsidian_action(action, payload)
        if obsidian_result is not None:
            return obsidian_result
        handler = ACTIONS.get(action)
        if handler is None:
            raise InputError(f"unsupported action: {action}")
        return handler(payload)
    except InputError as exc:
        print(f"safe-read: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"safe-read: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

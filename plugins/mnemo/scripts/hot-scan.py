#!/usr/bin/env python3
"""Collect still-open tails from recent session notes into a small digest.

This is the *reader* the handoff never had. Measured on the live vault
(2026-07-25): `Meta — Session Handoff` was read for continuity in 6% of
sessions, because nothing automatic could read it — 805 KiB exceeds both the
256 KB and the 25000-token caps of a file read. A digest small enough to inject
at SessionStart turns "forward state" from an artifact nobody opens into one
line of context every session.

Two failure classes are designed against, both measured, not assumed:

- **"Live" is not always a checkbox** (the v1.1.10 class). Pending sections
  carry flat bullets with no `- [ ]` — 90 of them across 14 handoff blocks.
  A `- [ ]`-only scan silently drops them, which is exactly the bug the
  archiver's prose-pending detector was added to fix. So inside a pending
  section a bare `- bullet` counts too; outside one, only an explicit `- [ ]`.

- **Sizing in characters** under-counts a Cyrillic vault by ~34% (UTF-8 is
  ~1.35 B/char here). Every cap in this file is in BYTES.

Read-only: never writes, never follows symlinks out of the vault, never runs a
shell. Stdlib only (system pip is PEP-668 locked).

Usage:
    hot-scan.py <vault-path> [--project NAME] [--window-days N] [--max-kb N]
                [--handoff NOTE] [--config PATH] [--json] [--today YYYY-MM-DD]

Default output is the injectable digest text; `--json` returns the structure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys

DEFAULT_WINDOW_DAYS = 7
DEFAULT_MAX_KB = 8
MAX_ITEM_CHARS = 200
SKIP_DIRS = {".obsidian", ".trash", ".git", "node_modules"}

# A heading that opens a section of unfinished work. Deliberately generous:
# missing a pending section costs a lost tail, a false positive costs one noisy
# line. Russian and English, because the vault is both.
PENDING_HEADING_RE = re.compile(
    r"^#{1,6}\s*.*(?:"
    r"pending|next\s*steps?|to\s?-?do|follow[\s-]?up|open\s+(?:items?|threads?)|"
    r"остал|жд[её]м|хвост|незакрыт|в\s+процессе|не\s+закры"
    r")",
    re.IGNORECASE,
)
OPEN_CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[\s\]\s*(.+?)\s*$")
CLOSED_CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[[xX~-]\]")
FLAT_BULLET_RE = re.compile(r"^\s*[-*]\s+(?!\[)(.+?)\s*$")
HEADING_RE = re.compile(r"^#{1,6}\s")
# A bullet already carrying a done/rejected marker is not a tail.
DONE_MARKER_RE = re.compile(r"^\s*(?:✅|❌|~~|DONE\b|СДЕЛАНО\b)", re.IGNORECASE)

STALE_PREMISE_WARNING = (
    "⚠️ премиса могла протухнуть — сверь с origin/main и Linear перед действием."
)


def parse_frontmatter(path: str) -> dict[str, str] | None:
    """Minimal scalar parse of a leading `---` block; {} when absent."""
    try:
        with open(path, encoding="utf-8") as handle:
            if handle.readline().strip() != "---":
                return {}
            fields: dict[str, str] = {}
            for index, line in enumerate(handle):
                if index >= 100 or line.strip() == "---":
                    break
                key, _, value = line.partition(":")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and value:
                    fields[key] = value
            return fields
    except OSError:
        return None


def parse_date(value: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def clip(text: str) -> str:
    """Bound one item so a single runaway line cannot eat the whole cap."""
    return text if len(text) <= MAX_ITEM_CHARS else text[: MAX_ITEM_CHARS - 1] + "…"


def extract_tails(body: str) -> list[str]:
    """Open tails from a note body.

    Inside a pending section: any bullet. Outside it: only an explicit `- [ ]`
    (a bare bullet elsewhere is narrative — Findings, links, evidence).
    """
    tails: list[str] = []
    in_pending = False
    for line in body.splitlines():
        if HEADING_RE.match(line):
            in_pending = bool(PENDING_HEADING_RE.match(line))
            continue
        if CLOSED_CHECKBOX_RE.match(line):
            continue
        open_box = OPEN_CHECKBOX_RE.match(line)
        if open_box:
            text = open_box.group(1).strip()
            if text and not DONE_MARKER_RE.match(text):
                tails.append(clip(text))
            continue
        if not in_pending:
            continue
        bullet = FLAT_BULLET_RE.match(line)
        if bullet:
            text = bullet.group(1).strip()
            if text and not DONE_MARKER_RE.match(text):
                tails.append(clip(text))
    return tails


def split_handoff_blocks(body: str) -> list[tuple[dt.date, str]]:
    """Dated `## YYYY-MM-DD` blocks of the legacy handoff, if one is scanned."""
    blocks: list[tuple[dt.date, str]] = []
    for chunk in re.split(r"(?m)(?=^## \d{4}-\d{2}-\d{2})", body):
        match = re.match(r"## (\d{4}-\d{2}-\d{2})", chunk)
        if match is None:
            continue
        date = parse_date(match.group(1))
        if date is not None:
            blocks.append((date, chunk))
    return blocks


def scan_vault(
    vault: str,
    *,
    cutoff: dt.date,
    project: str | None,
) -> list[dict]:
    """Every open tail from session notes dated on/after `cutoff`."""
    found: list[dict] = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            fields = parse_frontmatter(path)
            if not fields or fields.get("type") != "session":
                continue
            date = parse_date(fields.get("date", ""))
            if date is None or date < cutoff:
                continue
            note_project = fields.get("project") or "—"
            if project and note_project != project:
                continue
            try:
                with open(path, encoding="utf-8") as handle:
                    body = handle.read()
            except OSError:
                continue
            for text in extract_tails(body):
                found.append({
                    "text": text,
                    "project": note_project,
                    "date": date.isoformat(),
                    "note": name[:-3],
                })
    return found


def scan_handoff(path: str, *, cutoff: dt.date, project: str | None) -> list[dict]:
    """Open tails from the legacy block-format handoff, window-limited.

    Kept as an opt-in source: 66% of its open items are not covered by any
    session note, so until the migration lands they exist nowhere else.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
    except OSError:
        return []
    found: list[dict] = []
    for date, chunk in split_handoff_blocks(body):
        if date < cutoff:
            continue
        header = chunk.split("\n", 1)[0]
        # `## 2026-07-25 — mnemo: …` → "mnemo"; the project is prose here, so
        # this is a best-effort label, never a filter people depend on.
        label = re.sub(r"^## \d{4}-\d{2}-\d{2}\s*[—-]?\s*", "", header)
        block_project = re.split(r"[::]", label, maxsplit=1)[0].strip()[:40] or "—"
        if project and block_project != project:
            continue
        for text in extract_tails(chunk):
            found.append({
                "text": text,
                "project": block_project,
                "date": date.isoformat(),
                "note": None,
            })
    return found


def dedupe(items: list[dict]) -> list[dict]:
    """Same tail recorded in both a session note and the handoff — keep one."""
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        # Compare the WHOLE normalized text: truncating the key merges distinct
        # tails that happen to share a prefix (a long quoted path, a repeated
        # "Проверить, что …" opener) — a silent loss, not a dedupe.
        key = re.sub(r"\W+", "", item["text"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def build_groups(items: list[dict]) -> list[dict]:
    """Group by project, newest project first, newest item first inside it."""
    by_project: dict[str, list[dict]] = {}
    for item in items:
        by_project.setdefault(item["project"], []).append(item)
    groups = []
    for name, group_items in by_project.items():
        group_items.sort(key=lambda i: i["date"], reverse=True)
        groups.append({
            "project": name,
            "count": len(group_items),
            "newest": group_items[0]["date"],
            "items": group_items,
        })
    groups.sort(key=lambda g: g["newest"], reverse=True)
    return groups


def render(groups: list[dict], *, window_days: int, max_bytes: int) -> tuple[str, list[dict]]:
    """Render the digest under a hard BYTE cap, dropping oldest items first.

    Returns the text plus the groups that actually survived the cap, so the
    JSON payload can never claim more than the digest shows.
    """
    if not groups:
        return "", []

    total = sum(g["count"] for g in groups)
    head = f"📌 Открытые хвосты: {total} (окно {window_days} дн.)"
    tail = STALE_PREMISE_WARNING

    def compose(items: list[dict]) -> tuple[str, list[dict]]:
        surviving = build_groups(items)
        lines = [head]
        for group in surviving:
            lines.append(f"{group['project']} · {group['count']}:")
            lines.extend(f"  · {item['text']}" for item in group["items"])
        # Say plainly when the cap hid most of the list: a digest showing 43 of
        # 234 without saying so reads like the whole picture.
        if len(items) < total:
            lines.append(f"(показано {len(items)} из {total} — остальное "
                         "в pending-секциях session-заметок)")
        lines.append(tail)
        return "\n".join(lines), surviving

    # Newest first, so dropping from the end drops the oldest.
    ranked = sorted(
        (item for group in groups for item in group["items"]),
        key=lambda i: i["date"],
        reverse=True,
    )
    # Measure the RENDERED text, not the sum of item costs: every group adds a
    # header line, so per-item accounting silently overshoots the cap once the
    # digest spans several projects (measured: 8335 B against an 8192 B cap).
    while ranked:
        text, surviving = compose(ranked)
        if len(text.encode()) <= max_bytes:
            return text, surviving
        ranked.pop()
    return "", []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Digest of still-open tails from recent session notes.")
    parser.add_argument("vault_path", help="path to the Obsidian vault root")
    parser.add_argument("--project", help="keep only this project's tails")
    parser.add_argument("--window-days", type=int, help=f"default {DEFAULT_WINDOW_DAYS}")
    parser.add_argument("--max-kb", type=int, help=f"hard byte cap, default {DEFAULT_MAX_KB}")
    parser.add_argument("--handoff", help="also scan this legacy handoff note (path)")
    parser.add_argument("--config", default="~/.mnemo/config.json")
    parser.add_argument("--json", action="store_true", help="emit the structure")
    parser.add_argument("--today", help="override today's date (tests)")
    args = parser.parse_args()

    vault = os.path.expanduser(args.vault_path)
    if not os.path.isdir(vault):
        print(f"error: not a directory: {vault}", file=sys.stderr)
        return 1

    config: dict = {}
    try:
        with open(os.path.expanduser(args.config)) as handle:
            config = json.load(handle).get("hot", {}) or {}
    except (OSError, json.JSONDecodeError, AttributeError):
        config = {}

    def setting(name: str, cli_value, fallback: int) -> int:
        if cli_value is not None:
            return cli_value
        try:
            return int(config.get(name, fallback))
        except (TypeError, ValueError):
            return fallback

    window_days = setting("windowDays", args.window_days, DEFAULT_WINDOW_DAYS)
    max_kb = setting("maxKB", args.max_kb, DEFAULT_MAX_KB)

    today = parse_date(args.today) if args.today else dt.date.today()
    if today is None:
        print("error: --today must be YYYY-MM-DD", file=sys.stderr)
        return 1
    cutoff = today - dt.timedelta(days=window_days)

    items = scan_vault(vault, cutoff=cutoff, project=args.project)
    if args.handoff:
        items += scan_handoff(
            os.path.expanduser(args.handoff), cutoff=cutoff, project=args.project)
    items = dedupe(items)

    groups = build_groups(items)
    digest, surviving = render(
        groups, window_days=window_days, max_bytes=max_kb * 1024)

    if args.json:
        print(json.dumps({
            "digest": digest,
            "groups": surviving,
            "total": sum(g["count"] for g in groups),
            "shown": sum(g["count"] for g in surviving),
            "windowDays": window_days,
            "maxKB": max_kb,
            "bytes": len(digest.encode()),
        }, ensure_ascii=False))
    elif digest:
        print(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())

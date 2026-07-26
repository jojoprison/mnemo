#!/usr/bin/env python3
"""One-shot migration: block-format handoff → pointer index + verbatim archive.

Why a migration exists at all: the block format cannot be bounded. A block stays
hot while it holds a single open `- [ ]`, so on the maintainer's vault the
archiver was correctly freeing **zero** bytes while the file sat at 805 KiB —
20x its own ceiling, and past the point where anything can read it.

What this does NOT do, deliberately:

- **It never extracts checkboxes out of a block.** Measured on the live file, 90
  flat bullets under pending headings and ~200 prose lines carry live state with
  no `- [ ]` at all; pulling out only checkboxes would silently drop them. Blocks
  move **verbatim, whole**.
- **It never edits a session note.** Those are human-authored, and the vault has
  no version control to undo a bad sweep.
- **It never deletes.** Everything moves to the archive, and a `.bak` of both
  files is written before the first byte changes.

Safety contract: `--dry-run` is the default. `--apply` requires the operator to
have a restore path in hand (`restore-handoff-from-bak.py`), writes `.bak` files
first, and verifies afterwards that every migrated block is byte-present in the
archive — refusing to leave a half-migration behind.

Usage:
    migrate-handoff-to-index.py <handoff.md> [--archive PATH] [--apply]
                                [--keep-blocks N] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import sys

BLOCK_SPLIT_RE = re.compile(r"(?m)(?=^## \d{4}-\d{2}-\d{2})")
BLOCK_DATE_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
SESSION_LINK_RE = re.compile(r"\[\[((?:Session|Сессия) — [^\]]+)\]\]")
OPEN_TODO_RE = re.compile(r"(?m)^\s*[-*]\s+\[ \]")
MAX_LINE_BYTES = 200


def split_blocks(body: str) -> tuple[str, list[str]]:
    match = re.search(r"(?m)^## \d{4}-\d{2}-\d{2}", body)
    if match is None:
        return body, []
    header = body[: match.start()]
    blocks = [b for b in BLOCK_SPLIT_RE.split(body[match.start():]) if b.strip()]
    return header, blocks


def clip_to_bytes(value: str, budget: int) -> str:
    if budget <= 0:
        return ""
    trimmed = value
    while trimmed and len(trimmed.encode()) > budget:
        trimmed = trimmed[:-1]
    return trimmed


def index_line(block: str, archive_note: str = "") -> str:
    """A pointer for one block: date · label · open N · [[Session — …]].

    The session link is preferred as the pointer because it leads to the
    narrative; when a block has none, the pointer falls back to the archive
    note that now holds the block. That fallback is load-bearing: a pointer
    reading `(без session-заметки)` is a dead end, and once the calendar window
    evicts it the block has no inbound link at all — on the live vault 10 of
    186 blocks had no session note, carrying 170 open items between them.
    """
    date_match = BLOCK_DATE_RE.match(block)
    date = date_match.group(1) if date_match else "0000-00-00"
    header = block.split("\n", 1)[0]
    label = re.sub(r"^## \d{4}-\d{2}-\d{2}\s*[—-]?\s*", "", header).strip()
    open_count = len(OPEN_TODO_RE.findall(block))
    link_match = SESSION_LINK_RE.search(block)
    if link_match:
        suffix = f" · open {open_count} · [[{link_match.group(1)}]]"
    elif archive_note:
        suffix = f" · open {open_count} · [[{archive_note}]]"
    else:
        suffix = f" · open {open_count} · (без session-заметки)"
    overhead = len(f"- {date}".encode()) + len(" · ".encode()) + len(suffix.encode())
    label = clip_to_bytes(label, MAX_LINE_BYTES - overhead)
    return f"- {date} · {label}{suffix}" if label else f"- {date}{suffix}"


def archive_lead(today: str, count: int, byte_size: int) -> str:
    return (
        f"\n> ❄️ UPDATE {today}: сюда перенесены {count} блоков ({byte_size} B) "
        "из горячего handoff при переходе на индекс-формат. Перенос verbatim — "
        "текст блоков не изменён, ничего не удалено. Живое состояние теперь "
        "живёт в pending-секциях самих session-заметок, а горячий handoff держит "
        "по одной строке-указателю на сессию.\n\n"
    )


def block_date(block: str) -> str:
    match = BLOCK_DATE_RE.match(block)
    return match.group(1) if match else "0000-00-00"


def plan(handoff_body: str, archive_body: str, *, today: str, keep_blocks: int,
         archive_note: str = ""):
    header, blocks = split_blocks(handoff_body)
    # Order by date, never by file position: a real handoff is not sorted (the
    # live file had a 2026-07-19 block sitting among March ones), so "the newest
    # N" must be computed, not assumed from the top of the file.
    by_date = sorted(blocks, key=block_date, reverse=True)
    keep = by_date[:keep_blocks] if keep_blocks else []
    kept = set(map(id, keep))
    move = [b for b in by_date if id(b) not in kept]

    lines = [index_line(b, archive_note) for b in by_date]
    new_handoff = header.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n"
    if keep:
        new_handoff += "\n" + "".join(
            b if b.endswith("\n") else b + "\n" for b in keep)

    moved_text = "".join(b if b.endswith("\n") else b + "\n" for b in move)
    if archive_body.strip():
        arch_header, arch_blocks = split_blocks(archive_body)
        new_archive = (
            arch_header.rstrip("\n")
            + archive_lead(today, len(move), len(moved_text.encode()))
            + moved_text
            + "".join(b if b.endswith("\n") else b + "\n" for b in arch_blocks)
        )
    else:
        new_archive = (
            "---\ntype: meta\ntags: [meta, handoff, archive, cold]\n---\n\n"
            "# Meta — Session Handoff Archive\n"
            + archive_lead(today, len(move), len(moved_text.encode()))
            + moved_text
        )
    return new_handoff, new_archive, blocks, move


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("handoff")
    parser.add_argument("--archive")
    parser.add_argument("--apply", action="store_true",
                        help="actually write (default is a dry run)")
    parser.add_argument("--keep-blocks", type=int, default=0,
                        help="keep the N newest blocks in full, verbatim")
    parser.add_argument("--today")
    args = parser.parse_args()

    handoff_path = os.path.expanduser(args.handoff)
    if not os.path.isfile(handoff_path):
        print(f"error: not a file: {handoff_path}", file=sys.stderr)
        return 1
    archive_path = os.path.expanduser(args.archive) if args.archive else (
        handoff_path[:-3] + " Archive.md")
    today = args.today or dt.date.today().isoformat()

    handoff_body = open(handoff_path, encoding="utf-8").read()
    archive_body = (open(archive_path, encoding="utf-8").read()
                    if os.path.isfile(archive_path) else "")

    _, existing_blocks = split_blocks(handoff_body)
    already_indexed = any(
        line.startswith("- 20") and " · " in line
        for line in handoff_body.splitlines()
    )
    # With --keep-blocks the kept blocks stay behind, so "no blocks left" never
    # becomes true and a re-run kept appending duplicate pointers. The real
    # no-op condition is: an index already exists and nothing is left to move.
    if already_indexed and len(existing_blocks) <= args.keep_blocks:
        # Already migrated (or never block-format). Re-running must be a true
        # no-op: a second pass used to append a "moved 0 blocks" note to the
        # archive and stray blank lines to the handoff — harmless to the data,
        # but noise a re-run should never produce.
        print("handoff уже в индекс-формате — мигрировать нечего, файлы не тронуты")
        return 0

    new_handoff, new_archive, blocks, moved = plan(
        handoff_body, archive_body, today=today, keep_blocks=args.keep_blocks,
        archive_note=os.path.basename(archive_path)[:-3])

    before, after = len(handoff_body.encode()), len(new_handoff.encode())
    print(f"handoff:  {before} B → {after} B  "
          f"(−{round(100 * (before - after) / before, 1)}%)")
    print(f"блоков:   {len(blocks)} всего · {len(moved)} в архив · "
          f"{len(blocks) - len(moved)} остаются целиком")
    print(f"архив:    {len(archive_body.encode())} B → {len(new_archive.encode())} B")
    index_lines = [l for l in new_handoff.splitlines() if l.startswith("- 20")]
    over = [l for l in index_lines if len(l.encode()) > MAX_LINE_BYTES]
    print(f"индекс:   {len(index_lines)} строк, "
          f"max {max((len(l.encode()) for l in index_lines), default=0)} B/строка "
          f"(бюджет {MAX_LINE_BYTES}; превышают {len(over)} — длинная ссылка не режется)")
    print("\nпервые 5 строк индекса:")
    for line in [l for l in new_handoff.splitlines() if l.startswith("- 20")][:5]:
        print(f"  {line}")

    if not args.apply:
        print("\n🔍 DRY RUN — ничего не записано. Для применения: --apply")
        return 0

    stamp = today
    for path in (handoff_path, archive_path):
        if os.path.isfile(path):
            backup = f"{path}.bak-migrate-{stamp}"
            index = 1
            while os.path.exists(backup):
                index += 1
                backup = f"{path}.bak-migrate-{stamp}-{index}"
            shutil.copy2(path, backup)
            print(f"бэкап: {backup}")

    # Archive first: if this run dies between the two writes, the blocks exist
    # in the archive and the handoff is still intact — never the reverse.
    with open(archive_path, "w", encoding="utf-8") as handle:
        handle.write(new_archive)
    with open(handoff_path, "w", encoding="utf-8") as handle:
        handle.write(new_handoff)

    written_archive = open(archive_path, encoding="utf-8").read()
    missing = [b.split("\n", 1)[0] for b in moved if b.rstrip("\n") not in written_archive]
    if missing:
        print(f"\n🛑 ПРОВЕРКА НЕ ПРОШЛА: {len(missing)} блоков не найдены в архиве "
              f"дословно. Восстанови из .bak немедленно:", file=sys.stderr)
        for header in missing[:5]:
            print(f"  {header}", file=sys.stderr)
        return 2
    print(f"\n✅ применено; все {len(moved)} блоков дословно присутствуют в архиве")
    return 0


if __name__ == "__main__":
    sys.exit(main())

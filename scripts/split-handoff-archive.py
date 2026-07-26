#!/usr/bin/env python3
"""Split a monolithic handoff archive into per-month notes plus a small hub.

A cold archive is not harmless just because nothing reads it at startup. The
live one is 717 KiB (1.5 MiB after migration), which makes it:

- **unreadable** — a file read refuses past 256 KB / 25,000 tokens, so the
  "you can always find it in the archive" promise silently fails,
- **noisy** — a vault-wide content scan matches it on nearly any query (it
  appeared in 3 of 3 probes), so it crowds recall results with a hit nobody can
  then open.

Per-month notes fix both without deleting anything: each part stays whole and
verbatim, and the hub keeps one navigable line per month. Same safety contract
as the migration — `--dry-run` by default, `.bak` before writing, and a
verbatim-presence check afterwards.

Usage:
    split-handoff-archive.py <archive.md> [--apply] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import os
import re
import shutil
import sys

BLOCK_SPLIT_RE = re.compile(r"(?m)(?=^## \d{4}-\d{2}-\d{2})")
BLOCK_DATE_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
OPEN_TODO_RE = re.compile(r"(?m)^\s*[-*]\s+\[ \]")


def split_blocks(body: str) -> tuple[str, list[str]]:
    match = re.search(r"(?m)^## \d{4}-\d{2}-\d{2}", body)
    if match is None:
        return body, []
    return body[: match.start()], [
        b for b in BLOCK_SPLIT_RE.split(body[match.start():]) if b.strip()
    ]


def month_of(block: str) -> str:
    match = BLOCK_DATE_RE.match(block)
    return match.group(1)[:7] if match else "undated"


def part_body(hub_name: str, month: str, blocks: list[str]) -> str:
    opens = sum(len(OPEN_TODO_RE.findall(b)) for b in blocks)
    return (
        f"---\ntype: meta\ntags: [meta, handoff, archive, cold]\ndate: {month}-01\n---\n\n"
        f"# {hub_name} {month}\n\n"
        f"> ❄️ Холодный архив за {month}: {len(blocks)} блоков, {opens} незакрытых пунктов. "
        f"Текст перенесён дословно. Навигация — [[{hub_name}]].\n\n"
        + "".join(b if b.endswith("\n") else b + "\n" for b in blocks)
    )


def hub_body(hub_name: str, prefix: str, months: dict[str, list[str]], today: str) -> str:
    lines = [
        f"> ❄️ UPDATE {today}: архив разбит помесячно — монолит перестал открываться "
        "(чтение файла отказывает после 256 KB) и засорял поиск попаданием на любой запрос. "
        "Блоки перенесены дословно, ничего не удалено.\n",
        "",
        "| Месяц | Блоков | Незакрытых | Размер |",
        "|---|---|---|---|",
    ]
    for month in sorted(months, reverse=True):
        blocks = months[month]
        opens = sum(len(OPEN_TODO_RE.findall(b)) for b in blocks)
        size = sum(len(b.encode()) for b in blocks)
        lines.append(
            f"| [[{hub_name} {month}]] | {len(blocks)} | {opens} | {round(size / 1024)} KB |")
    lines += ["", "## Связи", "", f"- [[{hub_name.replace(' Archive', '')}]] — горячий индекс"]
    return prefix.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("archive")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--today")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing parts (each is backed up first)")
    parser.add_argument("--max-part-bytes", type=int, default=200 * 1024,
                        help="split a month once it exceeds this (default 200 KB, "
                             "under the 256 KB read limit)")
    args = parser.parse_args()

    path = os.path.expanduser(args.archive)
    if not os.path.isfile(path):
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1
    today = args.today or dt.date.today().isoformat()
    directory, filename = os.path.split(path)
    hub_name = filename[:-3]

    body = open(path, encoding="utf-8").read()
    prefix, blocks = split_blocks(body)
    if not blocks:
        print("в архиве нет датированных блоков — делить нечего")
        return 0

    by_month: dict[str, list[str]] = collections.defaultdict(list)
    for block in blocks:
        by_month[month_of(block)].append(block)

    # A month is not automatically a readable unit: on the live archive June
    # alone was 425 KB, still past the 256 KB read limit. Split any oversized
    # month into numbered parts so every piece can actually be opened.
    months: dict[str, list[str]] = {}
    for month in sorted(by_month):
        month_blocks = by_month[month]
        if sum(len(b.encode()) for b in month_blocks) <= args.max_part_bytes:
            months[month] = month_blocks
            continue
        part, used, index = [], 0, 1
        for block in month_blocks:
            size = len(block.encode())
            # Check BEFORE adding: closing the part after the overflow let one
            # part reach 204819 B against a 204800 B ceiling.
            if part and used + size > args.max_part_bytes:
                months[f"{month} ч{index}"] = part
                part, used, index = [], 0, index + 1
            part.append(block)
            used += size
        if part:
            months[f"{month} ч{index}"] = part

    print(f"архив: {len(body.encode())} B · {len(blocks)} блоков · {len(months)} месяцев")
    print(f"{'месяц':<10} {'блоков':>7} {'размер':>10}")
    for month in sorted(months, reverse=True):
        size = sum(len(b.encode()) for b in months[month])
        print(f"{month:<10} {len(months[month]):>7} {size:>9} B")
    new_hub = hub_body(hub_name, prefix, months, today)
    print(f"\nхаб станет {len(new_hub.encode())} B (было {len(body.encode())} B)")
    biggest = max(len(part_body(hub_name, m, b).encode()) for m, b in months.items())
    print(f"крупнейшая часть: {biggest} B "
          f"({'читаема' if biggest < 256 * 1024 else '🛑 всё ещё за пределом чтения 256 KB'})")

    if not args.apply:
        print("\n🔍 DRY RUN — ничего не записано. Для применения: --apply")
        return 0

    # A part that already exists holds blocks from an earlier split. Overwriting
    # it destroys them silently — and a later migration appends new blocks to the
    # hub, so a second split is a realistic accident, not a hypothetical one.
    collisions = [
        f"{hub_name} {month}.md" for month in months
        if os.path.isfile(os.path.join(directory, f"{hub_name} {month}.md"))
    ]
    if collisions and not args.force:
        print(f"\n🛑 {len(collisions)} частей уже существуют — перезапись стёрла бы "
              f"их блоки. Проверь и запусти с --force (каждая часть будет "
              f"забэкаплена):", file=sys.stderr)
        for name in collisions[:5]:
            print(f"  {name}", file=sys.stderr)
        return 3

    backup = f"{path}.bak-split-{today}"
    index = 1
    while os.path.exists(backup):
        index += 1
        backup = f"{path}.bak-split-{today}-{index}"
    shutil.copy2(path, backup)
    print(f"бэкап: {backup}")

    # Parts first: a crash between writes must leave the monolith intact.
    written = []
    for month, month_blocks in months.items():
        part_path = os.path.join(directory, f"{hub_name} {month}.md")
        if os.path.isfile(part_path):
            shutil.copy2(part_path, f"{part_path}.bak-split-{today}")
        with open(part_path, "w", encoding="utf-8") as handle:
            handle.write(part_body(hub_name, month, month_blocks))
        written.append((part_path, month_blocks))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(new_hub)

    missing = 0
    for part_path, month_blocks in written:
        content = open(part_path, encoding="utf-8").read()
        missing += sum(1 for b in month_blocks if b.rstrip("\n") not in content)
    if missing:
        print(f"\n🛑 ПРОВЕРКА НЕ ПРОШЛА: {missing} блоков отсутствуют дословно. "
              f"Восстанови: cp '{backup}' '{path}'", file=sys.stderr)
        return 2
    print(f"\n✅ применено; {len(blocks)} блоков дословно разложены по {len(months)} частям")
    return 0


if __name__ == "__main__":
    sys.exit(main())

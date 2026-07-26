#!/usr/bin/env python3
"""Give every handoff pointer a live target.

A migrated handoff can hold pointers that link nowhere — blocks whose text
never mentioned a `[[Session — …]]` note. While the index kept everything they
were merely ugly. Once rotation is calendar-based they become a data problem:
the window evicts the pointer, and the block it described keeps no inbound link
at all. Measured on the live vault: 10 of 186 blocks, 170 open items between
them.

This finds those pointers and repoints them at the archive note that actually
holds the block — the exact monthly part when the archive has been split, the
hub otherwise. Read-only by default.

    python3 scripts/relink-orphan-pointers.py "<vault>/Meta — Session Handoff.md"
    python3 scripts/relink-orphan-pointers.py "…" --apply
"""
import argparse
import os
import re
import sys

POINTER_RE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) · ")
LINK_RE = re.compile(r"\[\[[^\]]+\]\]")
BLOCK_DATE_RE = re.compile(r"(?m)^## (\d{4}-\d{2}-\d{2})")
MAX_LINE_BYTES = 200


def clip_to_bytes(value: str, budget: int) -> str:
    """Longest prefix fitting `budget` UTF-8 bytes — bytes, never characters."""
    if budget <= 0:
        return ""
    if len(value.encode()) <= budget:
        return value
    room = budget - len("…".encode())
    trimmed = value
    while trimmed and len(trimmed.encode()) > room:
        trimmed = trimmed[:-1]
    trimmed = trimmed.rstrip()
    return trimmed + "…" if len(trimmed) >= 12 else ""


def archive_index(vault: str, hub_name: str) -> dict[str, str]:
    """date -> note holding that date's block. Parts win over the hub.

    Sorted so a later part cannot silently shadow an earlier one for a date
    they both contain: the first note found for a date keeps it.
    """
    found: dict[str, str] = {}
    for name in sorted(os.listdir(vault)):
        if not name.endswith(".md") or not name.startswith(hub_name):
            continue
        note = name[:-3]
        try:
            text = open(os.path.join(vault, name), encoding="utf-8").read()
        except OSError:
            continue
        for match in BLOCK_DATE_RE.finditer(text):
            found.setdefault(match.group(1), note)
    return found


def relink(line: str, target: str) -> str:
    """Replace the dead tail of a pointer with a link, keeping it in budget."""
    head, _, _ = line.partition(" · open ")
    open_match = re.search(r" · open (\d+)", line)
    count = open_match.group(1) if open_match else "0"
    suffix = f" · open {count} · [[{target}]]"
    budget = MAX_LINE_BYTES - len(suffix.encode())
    return clip_to_bytes(head, budget) + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handoff")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    path = os.path.expanduser(args.handoff)
    if not os.path.isfile(path):
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1
    vault = os.path.dirname(path)
    hub_name = os.path.basename(path)[:-3] + " Archive"

    body = open(path, encoding="utf-8").read()
    by_date = archive_index(vault, hub_name)

    out, fixed, unresolved = [], 0, []
    for line in body.split("\n"):
        match = POINTER_RE.match(line)
        if match is None or LINK_RE.search(line):
            out.append(line)
            continue
        target = by_date.get(match.group(1))
        if target is None:
            unresolved.append(line[:90])
            out.append(line)
            continue
        out.append(relink(line, target))
        fixed += 1

    print(f"указателей без ссылки: {fixed + len(unresolved)} · "
          f"перепривязано: {fixed} · без блока в архиве: {len(unresolved)}")
    for line in unresolved:
        print(f"  ⚠️  {line}")
    if not fixed:
        print("нечего менять")
        return 0
    if not args.apply:
        print("DRY RUN — запусти с --apply, чтобы записать")
        return 0

    new_body = "\n".join(out)
    backup = path + ".bak-relink"
    with open(backup, "w", encoding="utf-8") as handle:
        handle.write(body)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(new_body)
    print(f"записано · бэкап: {os.path.basename(backup)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

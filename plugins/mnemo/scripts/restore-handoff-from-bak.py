#!/usr/bin/env python3
"""Restore a handoff (and its archive) from the backups a migration wrote.

This exists so the migration is reversible *before* it is ever run — the vault
is not under version control, Time Machine is not configured on this machine,
and Obsidian's File Recovery keeps only its own snapshot cadence. A migration
whose undo has not been rehearsed is not a migration, it is a gamble.

Default is a dry run: it shows which backup would be restored where, and how
the sizes compare. `--apply` restores, and before overwriting it saves the
*current* file as `.pre-restore-<stamp>` — so even an unwanted restore is itself
undoable.

Usage:
    restore-handoff-from-bak.py <handoff.md> [--archive PATH] [--stamp STR]
                                [--list] [--apply]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
import shutil
import sys


BLOCK_RE = re.compile(r"(?m)^## \d{4}-\d{2}-\d{2}")


def backups_for(path: str) -> list[str]:
    return sorted(glob.glob(f"{path}.bak*"), key=os.path.getmtime, reverse=True)


def looks_pre_migration(candidate: str, current: str) -> bool:
    """Is this backup actually worth restoring, or a post-migration snapshot?

    "Newest" is the wrong criterion: running the migration twice writes a fresh
    backup of the ALREADY migrated file, and picking by mtime then silently
    restores the index over the index — an undo that undoes nothing. A useful
    backup either still holds dated `## YYYY-MM-DD` blocks (the pre-migration
    shape) or is simply bigger than what is on disk now.
    """
    try:
        with open(candidate, encoding="utf-8", errors="ignore") as handle:
            head = handle.read(200_000)
    except OSError:
        return False
    if BLOCK_RE.search(head):
        return True
    current_size = os.path.getsize(current) if os.path.isfile(current) else 0
    return os.path.getsize(candidate) > current_size


def pick(path: str, stamp: str | None) -> str | None:
    candidates = backups_for(path)
    if not candidates:
        return None
    if stamp:
        # An explicit stamp is the operator overriding the heuristic on purpose.
        matching = [c for c in candidates if stamp in c]
        return matching[0] if matching else None
    useful = [c for c in candidates if looks_pre_migration(c, path)]
    if useful:
        return useful[0]
    print(f"⚠️  {os.path.basename(path)}: все бэкапы выглядят пост-миграционными "
          f"(нет блоков и не крупнее текущего файла). Укажи --stamp явно, "
          f"если уверен.", file=sys.stderr)
    return None


def describe(path: str, backup: str | None) -> None:
    current = os.path.getsize(path) if os.path.isfile(path) else 0
    if backup is None:
        print(f"  {os.path.basename(path)}: бэкапов не найдено (сейчас {current} B)")
        return
    size = os.path.getsize(backup)
    when = dt.datetime.fromtimestamp(os.path.getmtime(backup)).isoformat(timespec="seconds")
    print(f"  {os.path.basename(path)}: сейчас {current} B → восстановится {size} B")
    print(f"    из {os.path.basename(backup)} ({when})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("handoff")
    parser.add_argument("--archive")
    parser.add_argument("--stamp", help="substring of the backup name to pick")
    parser.add_argument("--list", action="store_true", help="list backups and exit")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    handoff = os.path.expanduser(args.handoff)
    archive = os.path.expanduser(args.archive) if args.archive else (
        handoff[:-3] + " Archive.md")
    targets = [handoff] + ([archive] if os.path.isfile(archive)
                           or backups_for(archive) else [])

    if args.list:
        for path in targets:
            print(os.path.basename(path))
            for backup in backups_for(path):
                when = dt.datetime.fromtimestamp(os.path.getmtime(backup))
                print(f"  {os.path.getsize(backup):>9} B  {when:%Y-%m-%d %H:%M}  "
                      f"{os.path.basename(backup)}")
        return 0

    chosen = {path: pick(path, args.stamp) for path in targets}
    print("План восстановления:")
    for path in targets:
        describe(path, chosen[path])

    if not any(chosen.values()):
        print("\n🛑 нечего восстанавливать", file=sys.stderr)
        return 1
    if not args.apply:
        print("\n🔍 DRY RUN — ничего не записано. Для применения: --apply")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for path, backup in chosen.items():
        if backup is None:
            continue
        if os.path.isfile(path):
            shutil.copy2(path, f"{path}.pre-restore-{stamp}")
        shutil.copy2(backup, path)
        print(f"✅ {os.path.basename(path)} ← {os.path.basename(backup)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

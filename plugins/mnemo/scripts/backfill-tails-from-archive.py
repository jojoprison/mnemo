#!/usr/bin/env python3
"""Move still-open tails from cold archive blocks into their session notes.

Pre-reform sessions wrote their unfinished work into the shared handoff, not
into their own note. After migration those tails sit in cold archive parts,
where the digest deliberately does not look — so a tail from three days ago can
be invisible while the reform claims tails are visible by default.

Measured on the live vault (2026-07-27, 7-day window): 136 open items in
archived blocks, **105 already present** in their session note under different
wording, **31 missing**. So this is a small, surgical backfill — not a mass
rewrite of human notes. Only genuinely missing items are appended, each marked
with the date of the block it came from.

Coverage is fuzzy on purpose: the note usually phrases the same tail
differently, and a literal comparison reports 0% when the truth is 77%. That
same check makes a second run a no-op — once appended, an item is covered.

    python3 scripts/backfill-tails-from-archive.py "<vault>"
    python3 scripts/backfill-tails-from-archive.py "<vault>" --since-days 7 --apply
"""
import argparse
import datetime as dt
import difflib
import os
import re
import sys

ARCHIVE_PREFIX = "Meta — Session Handoff Archive"
BLOCK_RE = re.compile(r"(?m)^## (\d{4}-\d{2}-\d{2})")
OPEN_RE = re.compile(r"(?m)^\s*[-*]\s+\[ \]\s*(.+)$")
LINK_RE = re.compile(r"\[\[((?:Session|Сессия) — [^\]]+)\]\]")
HEADING_RE = re.compile(r"^#{1,6}\s")
PENDING_HEADING_RE = re.compile(
    r"^#{1,6}\s*.*(?:pending|next\s*steps?|to\s?-?do|follow[\s-]?up|"
    r"open\s+(?:items?|threads?)|остал|жд[её]м|хвост|незакрыт|не\s+закры)",
    re.IGNORECASE,
)
DEFAULT_THRESHOLD = 0.55


def clean(text: str) -> str:
    text = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", text)
    return re.sub(r"[*`_#]", "", text).strip().lower()


def blocks_in_window(vault: str, cutoff: str) -> list[tuple[str, str]]:
    """(date, block text) for archived blocks newer than cutoff."""
    found: list[tuple[str, str]] = []
    for name in sorted(os.listdir(vault)):
        if not (name.startswith(ARCHIVE_PREFIX) and name.endswith(".md")):
            continue
        text = open(os.path.join(vault, name), encoding="utf-8").read()
        marks = list(BLOCK_RE.finditer(text))
        for i, mark in enumerate(marks):
            if mark.group(1) < cutoff:
                continue
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            found.append((mark.group(1), text[mark.start():end]))
    return found


def missing_items(block: str, note_body: str, threshold: float) -> list[str]:
    note_items = [clean(x) for x in OPEN_RE.findall(note_body)]
    missing = []
    for raw in OPEN_RE.findall(block):
        candidate = clean(raw)
        best = max(
            (difflib.SequenceMatcher(None, candidate, other).ratio()
             for other in note_items),
            default=0.0,
        )
        if best < threshold:
            missing.append(raw.strip())
    return missing


def append_to_pending(body: str, items: list[str], block_date: str) -> str:
    """Append items at the END of the pending section, as plain `- [ ]` lines.

    Never as a sub-heading: any heading closes the pending section, so a
    `### backfilled` block would push the very items it carries back out of the
    digest's view.
    """
    additions = [f"- [ ] {item} — _из архива handoff ({block_date})_"
                 for item in items]
    lines = body.split("\n")
    start = next((i for i, line in enumerate(lines)
                  if PENDING_HEADING_RE.match(line)), None)
    if start is None:
        anchor = next((i for i, line in enumerate(lines)
                       if line.startswith("## Связи")), len(lines))
        block = ["## Next steps / pending", ""] + additions + [""]
        return "\n".join(lines[:anchor] + block + lines[anchor:])
    end = next((i for i in range(start + 1, len(lines))
                if HEADING_RE.match(lines[i])), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[:end] + additions + lines[end:])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vault")
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--today")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    vault = os.path.expanduser(args.vault)
    if not os.path.isdir(vault):
        print(f"error: not a directory: {vault}", file=sys.stderr)
        return 1
    today = (dt.date.fromisoformat(args.today) if args.today else dt.date.today())
    cutoff = (today - dt.timedelta(days=args.since_days)).isoformat()

    planned: dict[str, tuple[str, list[str]]] = {}
    orphan_blocks = 0
    for date, block in blocks_in_window(vault, cutoff):
        if not OPEN_RE.search(block):
            continue
        link = LINK_RE.search(block)
        path = os.path.join(vault, f"{link.group(1)}.md") if link else None
        if path is None or not os.path.isfile(path):
            orphan_blocks += 1
            continue
        body = open(path, encoding="utf-8").read()
        gaps = missing_items(block, body, args.threshold)
        if not gaps:
            continue
        note, existing = planned.get(path, (date, []))
        planned[path] = (max(note, date), existing + gaps)

    total = sum(len(items) for _, items in planned.values())
    print(f"окно: с {cutoff} · заметок к правке: {len(planned)} · "
          f"пунктов к переносу: {total} · блоков без заметки: {orphan_blocks}")
    for path, (date, items) in sorted(planned.items()):
        print(f"  {os.path.basename(path)[:70]} ← {len(items)} ({date})")
    if not planned:
        print("нечего переносить — хвосты уже в своих заметках")
        return 0
    if not args.apply:
        print("DRY RUN — запусти с --apply, чтобы записать")
        return 0

    for path, (date, items) in sorted(planned.items()):
        body = open(path, encoding="utf-8").read()
        with open(path + ".bak-backfill", "w", encoding="utf-8") as handle:
            handle.write(body)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(append_to_pending(body, items, date))
    print(f"записано в {len(planned)} заметок (рядом с каждой — .bak-backfill)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

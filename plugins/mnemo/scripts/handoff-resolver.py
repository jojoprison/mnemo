#!/usr/bin/env python3
"""Report-only triage view of a block-format session handoff.

A handoff grows because the archiver may never touch a block that still holds an
open `- [ ]` — an unkept promise must not slip silently into cold storage. So the
file is not cleaned by archiving harder; it is cleaned by *deciding* what those
open items still mean. This script produces that worklist, plus honest
arithmetic about what deciding can actually buy.

It is deliberately **offline and read-only**: no network, no writes, no shell.
Whether a PR merged or an issue closed is a question for an agent with the right
credentials — this script only says which items carry an answerable anchor.

Two measured properties shape the output (live vault, 2026-07-25):

- **Anchor inheritance lies.** Counting anchors found in a block *header* as the
  item's own inflates "resolvable" from 27.6% to 60.6%. Item anchors and
  inherited anchors are reported separately; only item anchors count.
- **One anchorless item pins a whole block.** Blocks are classed by payoff, so
  the report never promises bytes the archiver would refuse to free.

The keep-hot rule itself is imported from `vault-write.py` rather than copied:
a second implementation would drift from the archiver it is predicting.

Usage:
    handoff-resolver.py <handoff-path> [--keep-days N] [--limit N]
                        [--json] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WRITER_PATH = os.path.join(SCRIPT_DIR, "vault-write.py")

# Anchors an external arbiter could actually answer.
LINEAR_RE = re.compile(r"\b([A-Z]{2,7})-(\d{1,5})\b")
PR_STRONG_RE = re.compile(r"(?:\bPR\s*#?|\bpull/|\bpull request\s*#?)(\d{1,6})\b", re.IGNORECASE)
PR_BARE_RE = re.compile(r"(?<![\w/])#(\d{1,6})\b")
PATH_RE = re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|md|json|ya?ml|sh|sql|toml)\b")
# Words that mark a tail nothing automated can close: it lives with a person.
PEOPLE_RE = re.compile(
    r"\b(?:спроси|спросить|уточни|уточнить|написать|отправить|позвонить|"
    r"договорить|обсудить|дождаться|ask|email)\w*", re.IGNORECASE)


def load_writer():
    """Import the shipped writer so the keep-hot invariant has ONE home."""
    name = "mnemo_vault_write"
    spec = importlib.util.spec_from_file_location(name, WRITER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load vault-write.py")
    module = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: the writer declares a dataclass, and dataclass
    # resolution looks the module up in sys.modules while the module body runs.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def anchors_of(text: str) -> dict[str, list[str]]:
    linear = sorted({f"{m.group(1)}-{m.group(2)}" for m in LINEAR_RE.finditer(text)})
    pr = sorted({m.group(1) for m in PR_STRONG_RE.finditer(text)}
                | {m.group(1) for m in PR_BARE_RE.finditer(text)})
    paths = sorted({m.group(0) for m in PATH_RE.finditer(text)})
    return {"linear": linear, "pr": pr, "path": paths}


def has_external_anchor(anchors: dict[str, list[str]]) -> bool:
    """Only Linear keys and PR numbers can be settled by an external arbiter.

    A file path proves the tail is about code, not that anything closed it.
    """
    return bool(anchors["linear"] or anchors["pr"])


def analyse(body: str, *, writer, today: dt.date, keep_days: int) -> dict:
    header, blocks = writer.split_handoff(body)
    cutoff = today - dt.timedelta(days=keep_days)

    block_rows: list[dict] = []
    items: list[dict] = []
    for chunk in blocks:
        date = writer.handoff_block_date(chunk)
        first_line = chunk.split("\n", 1)[0]
        inherited = anchors_of(first_line)
        prose_live = writer.HEADER_PENDING_RE.search(first_line) is not None
        size = len(chunk.encode())

        open_texts = [
            line.split("- [ ]", 1)[1].strip() if "- [ ]" in line else line.strip()
            for line in chunk.splitlines()
            if writer.OPEN_TODO_RE.search(line)
        ]
        block_items = []
        for text in open_texts:
            own = anchors_of(text)
            resolvable = has_external_anchor(own)
            block_items.append({
                "text": text[:300],
                "block_date": date.isoformat() if date else None,
                "anchors": own,
                "inherited": inherited,
                "resolvable": resolvable,
                "needs_person": bool(PEOPLE_RE.search(text)),
            })

        fresh = date is None or date >= cutoff
        if fresh:
            payoff = "fresh"
        elif prose_live:
            # Prose-live blocks stay hot even with every checkbox closed, so
            # resolving their items frees nothing. Never promise those bytes.
            payoff = "prose-pinned"
        elif not block_items:
            payoff = "already-cold"
        elif all(i["resolvable"] for i in block_items):
            payoff = "fully-resolvable"
        elif any(i["resolvable"] for i in block_items):
            payoff = "partial"
        else:
            payoff = "no-anchor"

        block_rows.append({
            "date": date.isoformat() if date else None,
            "bytes": size,
            "open": len(block_items),
            "prose_live": prose_live,
            "payoff": payoff,
            "header": first_line[:160],
        })
        items.extend(block_items)

    freed = sum(b["bytes"] for b in block_rows if b["payoff"] == "fully-resolvable")
    total = len(body.encode())
    resolvable_items = sum(1 for i in items if i["resolvable"])
    anchorless = sum(
        1 for i in items
        if not (i["anchors"]["linear"] or i["anchors"]["pr"] or i["anchors"]["path"])
    )

    by_payoff: dict[str, dict] = {}
    for row in block_rows:
        entry = by_payoff.setdefault(row["payoff"], {"blocks": 0, "bytes": 0, "open": 0})
        entry["blocks"] += 1
        entry["bytes"] += row["bytes"]
        entry["open"] += row["open"]

    return {
        "bytes": total,
        "header_bytes": len(header.encode()),
        "blocks_total": len(block_rows),
        "open_total": len(items),
        "keep_days": keep_days,
        "anchors": {
            "resolvable": resolvable_items,
            "resolvable_share": round(resolvable_items / len(items), 4) if items else 0,
            "none": anchorless,
            "needs_person": sum(1 for i in items if i["needs_person"]),
        },
        "ceiling": {
            "current_bytes": total,
            "freed_bytes": freed,
            "freed_pct": round(100 * freed / total, 2) if total else 0,
            "floor_bytes": total - freed,
        },
        "classes": by_payoff,
        "blocks": block_rows,
        "items": items,
    }


def render(report: dict, limit: int) -> str:
    lines = [
        f"handoff: {report['bytes']} B · {report['blocks_total']} блоков · "
        f"{report['open_total']} открытых (keepDays={report['keep_days']})",
        "",
        "Что даст полный резолв открытых пунктов:",
        f"  освободится {report['ceiling']['freed_bytes']} B "
        f"({report['ceiling']['freed_pct']}%) → пол {report['ceiling']['floor_bytes']} B",
        "",
        "Блоки по классу выигрыша:",
    ]
    order = ["fully-resolvable", "partial", "no-anchor", "prose-pinned", "fresh", "already-cold"]
    for name in order:
        entry = report["classes"].get(name)
        if entry:
            lines.append(
                f"  {name:<18} {entry['blocks']:>4} блоков · {entry['bytes']:>8} B · "
                f"{entry['open']:>4} открытых")
    anchors = report["anchors"]
    lines += [
        "",
        f"Якоря: резолвимо внешним арбитром {anchors['resolvable']}/{report['open_total']} "
        f"({round(100 * anchors['resolvable_share'], 1)}%) · "
        f"без якоря {anchors['none']} · требует человека {anchors['needs_person']}",
        "",
        f"Первые {limit} пунктов с якорем (кандидаты на проверку):",
    ]
    shown = 0
    for item in report["items"]:
        if not item["resolvable"] or shown >= limit:
            continue
        keys = ", ".join(item["anchors"]["linear"] + [f"#{n}" for n in item["anchors"]["pr"]])
        lines.append(f"  [{item['block_date']}] {keys} — {item['text'][:110]}")
        shown += 1
    lines.append("")
    lines.append("Report-only: ничего не изменено. Решения принимает человек.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report-only triage view of a block-format handoff.")
    parser.add_argument("handoff_path")
    parser.add_argument("--keep-days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--today", help="override today's date (tests)")
    args = parser.parse_args()

    path = os.path.expanduser(args.handoff_path)
    if not os.path.isfile(path):
        print(f"error: not a file: {path}", file=sys.stderr)
        return 1
    try:
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
    except OSError as error:
        print(f"error: cannot read {path}: {error}", file=sys.stderr)
        return 1

    try:
        writer = load_writer()
    except Exception as error:  # noqa: BLE001 — a broken import must not traceback
        print(f"error: cannot load vault-write.py: {error}", file=sys.stderr)
        return 1

    if args.today:
        try:
            today = dt.date.fromisoformat(args.today)
        except ValueError:
            print("error: --today must be YYYY-MM-DD", file=sys.stderr)
            return 1
    else:
        today = dt.date.today()

    report = analyse(body, writer=writer, today=today, keep_days=args.keep_days)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(render(report, args.limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())

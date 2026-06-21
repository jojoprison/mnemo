#!/usr/bin/env python3
"""Detect notes due for review (content-staleness candidates), type-aware.

Pure-filesystem scan of an Obsidian vault. Unlike orphan detection (a
*structural* signal from the metadata graph), this is a *temporal* signal:
a note is a review candidate when it has gone untouched longer than the
threshold for its type.

Effective age is measured from the most recent of `date` (creation) or
`reviewed` (the snooze stamp written when someone confirms a note is still
valid). The threshold is, in precedence order:

  1. per-note `ttl: <days>` in frontmatter (dosu-style soft contract), else
  2. `review.staleDays.<type>` from ~/.mnemo/config.json, else
  3. `review.staleDays.default` (or a bare integer `review.staleDays`), else
  4. 30 (matches the legacy hardcoded vault-health behavior).

A note with `reviewed` newer than `today - threshold` is NOT a candidate —
that is the guilt-debt fix: confirming a note resets its clock instead of it
nagging forever.

Usage: review-candidates.py <vault-path> [--limit N] [--config PATH]
Output (tab-separated, sorted most-overdue first):
  CANDIDATES\t<total>
  THRESHOLDS\t<json of resolved per-type thresholds>
  <overdue_days>\t<type>\t<anchor-date>\t<anchor-src>\t<relpath>
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

DEFAULT_STALE_DAYS = 30


def load_thresholds(config_path: str) -> tuple[dict, int]:
    """Return (per_type_map, default_days). Backward compatible: a missing
    `review` section reproduces the legacy uniform 30-day behavior."""
    try:
        with open(os.path.expanduser(config_path)) as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}, DEFAULT_STALE_DAYS

    review = cfg.get("review", {})
    stale = review.get("staleDays", {})
    if isinstance(stale, int):  # bare integer form: one value for everything
        return {}, stale
    if not isinstance(stale, dict):
        return {}, DEFAULT_STALE_DAYS

    default = stale.get("default", DEFAULT_STALE_DAYS)
    try:
        default = int(default)
    except (TypeError, ValueError):
        default = DEFAULT_STALE_DAYS
    per_type = {}
    for k, v in stale.items():
        if k == "default":
            continue
        try:
            per_type[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return per_type, default


def parse_frontmatter(path: str) -> dict | None:
    """Minimal YAML scalar parse of a leading `---` block. stdlib only
    (system pip is PEP-668 locked). Returns {} if no frontmatter, None on
    read error. Only scalar keys we care about are extracted."""
    try:
        with open(path, encoding="utf-8") as f:
            first = f.readline()
            if first.strip() != "---":
                return {}
            fields: dict[str, str] = {}
            for line in f:
                if line.strip() == "---":
                    break
                if ":" not in line:
                    continue
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and val:
                    fields[key] = val
            return fields
    except OSError:
        return None


def parse_date(value: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: review-candidates.py <vault-path> [--limit N] [--config PATH]",
              file=sys.stderr)
        return 1

    vault_path = ""
    limit = 50
    config_path = "~/.mnemo/config.json"
    i = 0
    positional = []
    while i < len(args):
        a = args[i]
        if a == "--limit" and i + 1 < len(args):
            try:
                limit = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif a == "--config" and i + 1 < len(args):
            config_path = args[i + 1]
            i += 2
        else:
            positional.append(a)
            i += 1
    if not positional:
        print("error: vault path required", file=sys.stderr)
        return 1
    vault_path = positional[0]
    if not os.path.isdir(vault_path):
        print(f"error: not a directory: {vault_path}", file=sys.stderr)
        return 1

    per_type, default_days = load_thresholds(config_path)
    today = dt.date.today()

    candidates = []  # (overdue_days, type, anchor_iso, anchor_src, relpath)
    seen_types = set()
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if d not in (".obsidian", ".trash", ".git")]
        for name in files:
            if not name.endswith(".md"):
                continue
            full = os.path.join(root, name)
            fm = parse_frontmatter(full)
            if not fm:
                continue
            created = parse_date(fm.get("date", ""))
            if created is None:
                continue  # no usable creation date → cannot judge age
            reviewed = parse_date(fm.get("reviewed", ""))
            ntype = fm.get("type", "untyped")
            seen_types.add(ntype)

            # threshold precedence: per-note ttl → per-type → default
            threshold = None
            ttl_raw = fm.get("ttl")
            if ttl_raw is not None:
                try:
                    threshold = int(ttl_raw)
                except (TypeError, ValueError):
                    threshold = None
            if threshold is None:
                threshold = per_type.get(ntype, default_days)

            if reviewed and reviewed >= created:
                anchor, anchor_src = reviewed, "reviewed"
            else:
                anchor, anchor_src = created, "date"

            overdue = (today - anchor).days - threshold
            if overdue > 0:
                rel = os.path.relpath(full, vault_path)
                candidates.append((overdue, ntype, anchor.isoformat(), anchor_src, rel))

    candidates.sort(key=lambda c: c[0], reverse=True)

    resolved = {t: per_type.get(t, default_days) for t in sorted(seen_types)}
    resolved["default"] = default_days
    print(f"CANDIDATES\t{len(candidates)}")
    print(f"THRESHOLDS\t{json.dumps(resolved, ensure_ascii=False)}")
    for c in candidates[:limit]:
        print(f"{c[0]}\t{c[1]}\t{c[2]}\t{c[3]}\t{c[4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

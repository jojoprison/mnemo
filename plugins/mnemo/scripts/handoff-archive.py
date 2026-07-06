#!/usr/bin/env python3
"""Archive old, closed blocks from the session Handoff note into a cold archive.

The handoff is a LIVE index (what to pick up next), not a permanent store. Left
un-rotated it grows into a multi-MB log that is a token bomb every time it is read
and buries the few live pending items under months of closed history.

This helper keeps it thin. A dated `## YYYY-MM-DD ...` block stays HOT if it is
recent (within --keep-days) OR still has an open `- [ ]` checkbox (a live pending
item). Everything older AND closed is moved verbatim into the archive note (cold —
never read at session start; its durable detail already lives in the linked
`Session — …` notes). Reversible: the handoff is backed up before any write.

Design mirrors the vault's MEMORY.md size-guard discipline (thin hot index + cold
archive + header pointer), applied to a prose log instead of a table index.

Safety:
- Dry-run by default; pass --execute to apply.
- No-op when the handoff is at/under --max-kb (safe to call every /mn:session).
- NEVER archives a block that has an open `- [ ]` (verified before writing; aborts
  with exit 2 if that invariant is somehow violated).
- Verbatim cut-paste (no rewriting) + timestamped backup = one-command undo.

Usage:
  handoff-archive.py --vault-path "$(get-vault-path.sh <vault>)" \
      --handoff "Meta — Session Handoff" [--max-kb 40] [--keep-days 14] [--execute]

Exit codes: 0 = ok (or no-op), 2 = safety abort / bad input.
"""
import argparse
import datetime
import os
import re
import shutil
import sys

DATE_HEADER = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
OPEN_TODO = re.compile(r'\[ \]')
# A block can be LIVE via prose in its header, not only via a `- [ ]` checkbox
# (e.g. "— В ПРОЦЕССЕ", "— WAITING FEEDBACK", "(PENDING ответ)"). Keep those hot too,
# else a genuinely-open item silently drops into cold storage. Header-level only —
# a body "Pending:" section is too noisy (most done blocks carry one).
HEADER_PENDING = re.compile(
    r'В ПРОЦЕССЕ|НЕ закры|не закрыт|незакры|жд[еёo]м|отложено'
    r'|WAITING|PENDING|IN PROGRESS|TODO|BLOCKED',
    re.IGNORECASE,
)
GUARD_MARK = 'SIZE-GUARD'


def parse(text):
    """Split into (header-before-first-dated-block, [dated blocks])."""
    m = re.search(r'^## \d{4}-\d{2}-\d{2}', text, re.M)
    if not m:
        return text, []
    header, body = text[:m.start()], text[m.start():]
    blocks = [b for b in re.split(r'(?=^## \d{4}-\d{2}-\d{2})', body, flags=re.M) if b.strip()]
    return header, blocks


def block_date(b):
    m = DATE_HEADER.match(b)
    if not m:
        return None
    try:
        return datetime.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def kb(chunks):
    return sum(len(c.encode('utf-8')) for c in chunks) / 1024


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--vault-path', required=True, help='absolute path to the Obsidian vault')
    ap.add_argument('--handoff', default='Meta — Session Handoff', help='handoff note name (no .md)')
    ap.add_argument('--archive', default=None, help='archive note name (default: "<handoff> Archive")')
    ap.add_argument('--max-kb', type=float, default=40.0, help='no-op when handoff is at/under this (default 40)')
    ap.add_argument('--keep-days', type=int, default=14, help='keep blocks newer than this hot (default 14)')
    ap.add_argument('--today', default=None, help='YYYY-MM-DD override (testing)')
    ap.add_argument('--execute', action='store_true', help='apply changes; otherwise dry-run')
    a = ap.parse_args(argv)

    handoff_path = os.path.join(a.vault_path, a.handoff + '.md')
    archive_name = a.archive or (a.handoff + ' Archive')
    archive_path = os.path.join(a.vault_path, archive_name + '.md')

    if not os.path.isfile(handoff_path):
        print(f'no-op: handoff not found ({handoff_path})')
        return 0
    size_kb = os.path.getsize(handoff_path) / 1024
    if size_kb <= a.max_kb:
        print(f'no-op: handoff {size_kb:.0f}KB <= max {a.max_kb:.0f}KB')
        return 0

    try:
        today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    except ValueError:
        print(f'bad --today: {a.today}', file=sys.stderr)
        return 2
    cutoff = today - datetime.timedelta(days=a.keep_days)

    text = open(handoff_path, encoding='utf-8').read()
    header, blocks = parse(text)
    hot, cold = [], []
    for b in blocks:
        d = block_date(b)
        header = b.split('\n', 1)[0]
        # HOT if: undated, recent, carries a live `- [ ]` checkbox, OR its header signals
        # still-open (prose). COLD only when none of these hold (provably safe to cool).
        keep = (d is None) or (d >= cutoff) or bool(OPEN_TODO.search(b)) or bool(HEADER_PENDING.search(header))
        (hot if keep else cold).append(b)

    danger = [b for b in cold if OPEN_TODO.search(b)]  # must be empty by construction
    cold_dates = sorted(d for d in map(block_date, cold) if d)

    print(f'handoff {size_kb:.0f}KB / {len(blocks)} blocks | cutoff hot >= {cutoff}')
    print(f'HOT  {len(hot)} blocks / {kb(hot):.0f}KB')
    span = f' ({cold_dates[0]}..{cold_dates[-1]})' if cold_dates else ''
    print(f'COLD {len(cold)} blocks / {kb(cold):.0f}KB{span}')
    if danger:
        print(f'ABORT: {len(danger)} cold block(s) have an open [ ] — safety invariant violated', file=sys.stderr)
        return 2
    if not cold:
        print('no-op: nothing older-and-closed to archive')
        return 0
    if not a.execute:
        print('[dry-run] pass --execute to apply')
        return 0

    # --- apply (reversible) ---
    stamp = today.isoformat()
    shutil.copy2(handoff_path, handoff_path + f'.bak-{stamp}')

    new_header = header
    if GUARD_MARK not in header:
        guard = (
            f'\n🛡️ **SIZE-GUARD (check at /mn:session):** handoff >{a.max_kb:.0f}KB → move CLOSED blocks '
            f'older than ~{a.keep_days}d to [[{archive_name}]]; open `- [ ]` + recent stay hot. '
            f'Run `scripts/handoff-archive.py --execute`. 🔎 missing entry → read [[{archive_name}]].\n\n'
        )
        fm = re.match(r'^(---\n.*?\n---\n)', header, re.S)
        new_header = header[:fm.end()] + guard + header[fm.end():] if fm else guard + header

    open(handoff_path, 'w', encoding='utf-8').write(new_header + ''.join(hot))

    if os.path.isfile(archive_path):
        prev = open(archive_path, encoding='utf-8').read()
        pm = re.search(r'^## \d{4}-\d{2}-\d{2}', prev, re.M)
        a_hdr, a_body = (prev[:pm.start()], prev[pm.start():]) if pm else (prev, '')
        open(archive_path, 'w', encoding='utf-8').write(a_hdr + ''.join(cold) + a_body)
    else:
        a_hdr = (
            '---\ntype: meta\ntags: [meta, handoff, archive, cold]\n---\n\n'
            f'# {archive_name}\n\n'
            f'> ❄️ Cold archive of [[{a.handoff}]] — closed blocks, NOT read at session start. '
            f'Detail lives in the linked `Session — …` notes; this is a verbatim chronological backstop. '
            f'Fresh / open items stay in hot [[{a.handoff}]].\n\n'
        )
        open(archive_path, 'w', encoding='utf-8').write(a_hdr + ''.join(cold))

    print(f'archived {len(cold)} blocks -> {archive_name} | handoff now {os.path.getsize(handoff_path) / 1024:.0f}KB '
          f'| backup {os.path.basename(handoff_path)}.bak-{stamp}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

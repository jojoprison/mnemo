#!/usr/bin/env python3
"""Tests for vault-write.py's handoff-index-upsert action.

The index format exists because the block format cannot be bounded. A block is
kept hot by a single open `- [ ]`, so on a real vault the archiver legitimately
freed **zero** bytes while the file sat 20x over its ceiling (measured
2026-07-25: 805 KiB, 863 open items). An index line is a pointer: its size is a
function of the number of sessions, not of how much was written in them.

Pinned here:

- **Idempotency keys on the session link.** A second `/mn:session` for the same
  session must refresh its line, never append a twin — the old `read`+`old_str`
  contract could not do this reliably, because a large handoff read returns a
  preview and the section to copy is simply not in it.
- **Every bound is in BYTES.** A 150-character Cyrillic line is ~270 bytes; a
  char-counted cap silently admits ~2x what it promises. One test writes exactly
  such a line and fails if the accounting is done in characters.
- **The link is never truncated.** Trimming a line must sacrifice the project
  label, never the `[[Session — …]]` pointer — a cut wikilink is a dead link,
  which is worse than a long line.
- **The block path is untouched.** `archive-handoff` keeps its own regression
  suite (`test-handoff-archive.py`, written after the v1.1.11 corruption
  incident); this action must not disturb it.

Stdlib-only (unittest + subprocess) — run directly:

    python3 scripts/test-handoff-index.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'plugins', 'mnemo', 'scripts', 'vault-write.py')

HEADER = (
    '---\ntype: meta\ntags: [meta, handoff]\n---\n\n'
    '# Meta — Session Handoff\n\n'
    '> 🔥 HOT index. Detail lives in the linked session notes.\n\n'
)
INDEX_LINE_RE = re.compile(r'^- \d{4}-\d{2}-\d{2} · ')


class FakeVault:
    """A vault dir plus a stub `obsidian` CLI that resolves it."""

    def __init__(self, tmp: str) -> None:
        self.root = os.path.join(tmp, 'vault')
        os.makedirs(self.root)
        self.bin = os.path.join(tmp, 'bin')
        os.makedirs(self.bin)
        cli = os.path.join(self.bin, 'obsidian')
        with open(cli, 'w', encoding='utf-8') as handle:
            handle.write(f'#!/bin/sh\nprintf "name\\tmain\\npath\\t{self.root}\\n"\n')
        os.chmod(cli, 0o755)

    def env(self) -> dict:
        env = dict(os.environ)
        env['PATH'] = self.bin + os.pathsep + env['PATH']
        return env


class IndexUpsertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = FakeVault(self.tmp.name)
        self.note = 'Meta — Session Handoff'
        self.path = os.path.join(self.vault.root, f'{self.note}.md')
        self.write_handoff(HEADER)

    def write_handoff(self, body: str) -> None:
        with open(self.path, 'w', encoding='utf-8') as handle:
            handle.write(body)

    def read_handoff(self) -> str:
        with open(self.path, encoding='utf-8') as handle:
            return handle.read()

    def index_lines(self) -> list[str]:
        return [l for l in self.read_handoff().splitlines() if INDEX_LINE_RE.match(l)]

    def upsert(self, *, session_note: str, date: str, project: str = 'mnemo',
               open_count: int = 0, expect_ok: bool = True, **extra) -> dict:
        payload = {
            'action': 'handoff-index-upsert',
            'vault': 'main',
            'note': self.note,
            'session_note': session_note,
            'date': date,
            'project': project,
            'open_count': open_count,
        }
        payload.update(extra)
        result = subprocess.run(
            [sys.executable, SCRIPT], input=json.dumps(payload),
            capture_output=True, text=True, env=self.vault.env())
        parsed = json.loads(result.stdout)
        if expect_ok:
            self.assertTrue(parsed.get('ok'), parsed)
        return parsed

    # --- basic upsert -----------------------------------------------------

    def test_first_upsert_creates_the_line(self):
        self.upsert(session_note='Session — 2026-07-25 реформа', date='2026-07-25',
                    open_count=3)
        lines = self.index_lines()
        self.assertEqual(1, len(lines))
        self.assertIn('[[Session — 2026-07-25 реформа]]', lines[0])
        self.assertIn('open 3', lines[0])
        self.assertIn('mnemo', lines[0])

    def test_header_is_preserved_verbatim(self):
        self.upsert(session_note='Session — A', date='2026-07-25')
        self.assertTrue(self.read_handoff().startswith(HEADER.rstrip('\n')))

    def test_second_upsert_of_same_session_updates_in_place(self):
        """The idempotency property the read+old_str contract could not hold."""
        self.upsert(session_note='Session — A', date='2026-07-25', open_count=1)
        self.upsert(session_note='Session — A', date='2026-07-25', open_count=4)
        lines = self.index_lines()
        self.assertEqual(1, len(lines), lines)
        self.assertIn('open 4', lines[0])
        self.assertNotIn('open 1', lines[0])

    def test_distinct_sessions_get_distinct_lines(self):
        self.upsert(session_note='Session — A', date='2026-07-25')
        self.upsert(session_note='Session — B', date='2026-07-25')
        self.assertEqual(2, len(self.index_lines()))

    def test_lines_are_sorted_newest_first(self):
        for note, date in (('Session — old', '2026-07-01'),
                           ('Session — new', '2026-07-25'),
                           ('Session — mid', '2026-07-10')):
            self.upsert(session_note=note, date=date)
        dates = [l.split(' · ')[0][2:] for l in self.index_lines()]
        self.assertEqual(sorted(dates, reverse=True), dates)

    # --- bounds -----------------------------------------------------------

    def test_rotation_drops_the_oldest_line(self):
        for day in range(1, 6):
            self.upsert(session_note=f'Session — {day}', date=f'2026-07-0{day}')
        self.upsert(session_note='Session — 6', date='2026-07-06', max_lines=3)
        lines = self.index_lines()
        self.assertEqual(3, len(lines))
        self.assertIn('Session — 6', lines[0])
        self.assertNotIn('Session — 1', '\n'.join(lines))

    def test_line_budget_is_bytes_not_characters(self):
        """150 Cyrillic chars ≈ 270 B: a char-counted budget lets it through."""
        self.upsert(session_note='Session — тест', date='2026-07-25',
                    project='я' * 150, max_line_bytes=200)
        for line in self.index_lines():
            self.assertLessEqual(len(line.encode('utf-8')), 200, line)

    def test_trimming_never_cuts_the_session_link(self):
        long_note = 'Session — ' + 'ю' * 90
        self.upsert(session_note=long_note, date='2026-07-25',
                    project='проект' * 20, max_line_bytes=200)
        body = self.read_handoff()
        self.assertIn(f'[[{long_note}]]', body)

    def test_hard_cap_bounds_the_whole_file(self):
        for day in range(1, 10):
            self.upsert(session_note=f'Session — {"ж" * 60} {day}',
                        date=f'2026-07-0{day}', project='проект-длинный',
                        hard_cap_bytes=len(HEADER.encode()) + 900)
        self.assertLessEqual(len(self.read_handoff().encode('utf-8')),
                             len(HEADER.encode()) + 900)

    # --- validation --------------------------------------------------------

    def test_rejects_session_note_with_wikilink_breaking_characters(self):
        result = self.upsert(session_note='Session — bad]] injection', date='2026-07-25',
                             expect_ok=False)
        self.assertFalse(result.get('ok'))
        self.assertEqual('input_error', result['error']['code'])

    def test_rejects_malformed_date(self):
        result = self.upsert(session_note='Session — A', date='25.07.2026',
                             expect_ok=False)
        self.assertFalse(result.get('ok'))

    def test_rejects_negative_open_count(self):
        result = self.upsert(session_note='Session — A', date='2026-07-25',
                             open_count=-1, expect_ok=False)
        self.assertFalse(result.get('ok'))

    def test_missing_handoff_fails_closed_without_creating_it(self):
        os.remove(self.path)
        result = self.upsert(session_note='Session — A', date='2026-07-25',
                             expect_ok=False)
        self.assertFalse(result.get('ok'))
        self.assertFalse(os.path.exists(self.path))

    # --- coexistence with the block path -----------------------------------

    def test_block_format_content_is_left_alone(self):
        """Upserting into a still-block-format handoff must not eat the blocks."""
        blocks = HEADER + '## 2026-05-01 — старый блок\n- [ ] незакрытое\n'
        self.write_handoff(blocks)
        self.upsert(session_note='Session — A', date='2026-07-25')
        body = self.read_handoff()
        self.assertIn('## 2026-05-01 — старый блок', body)
        self.assertIn('- [ ] незакрытое', body)
        self.assertEqual(1, len(self.index_lines()))


if __name__ == '__main__':
    unittest.main(verbosity=2)

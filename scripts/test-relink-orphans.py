#!/usr/bin/env python3
"""Tests for relink-orphan-pointers.py.

The pointer with no link was cosmetic while the index kept everything. Under a
calendar window it is a data problem: eviction removes the last inbound link to
a block nobody can then find. Run directly:

    python3 scripts/test-relink-orphans.py
"""
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'plugins', 'mnemo', 'scripts', 'relink-orphan-pointers.py')

HEADER = '---\ntype: meta\n---\n\n# Meta — Session Handoff\n\n'


def write(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def read(path: str) -> str:
    with open(path, encoding='utf-8') as handle:
        return handle.read()


class RelinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = self.tmp.name
        self.handoff = os.path.join(self.vault, 'Meta — Session Handoff.md')
        write(self.handoff, HEADER + '\n'.join([
            '- 2026-07-20 · researches-j · open 3 · (без session-заметки)',
            '- 2026-04-05 · BTS · open 5 · (без session-заметки)',
            '- 2026-07-19 · mnemo · open 1 · [[Session — 2026-07-19 живая]]',
        ]) + '\n')
        write(os.path.join(self.vault, 'Meta — Session Handoff Archive 2026-07 ч1.md'),
              '---\n---\n\n## 2026-07-20 — блок\n- [ ] хвост\n')
        write(os.path.join(self.vault, 'Meta — Session Handoff Archive 2026-04.md'),
              '---\n---\n\n## 2026-04-05 — блок\n- [ ] хвост\n')

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        result = subprocess.run([sys.executable, SCRIPT, self.handoff, *args],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        return result

    def test_dry_run_writes_nothing(self):
        before = read(self.handoff)
        result = self.run_script()
        self.assertIn('DRY RUN', result.stdout)
        self.assertEqual(before, read(self.handoff))

    def test_orphan_points_at_the_part_holding_its_block(self):
        self.run_script('--apply')
        body = read(self.handoff)
        self.assertIn('[[Meta — Session Handoff Archive 2026-07 ч1]]', body)
        self.assertIn('[[Meta — Session Handoff Archive 2026-04]]', body)
        self.assertNotIn('без session-заметки', body)

    def test_live_pointers_are_untouched(self):
        self.run_script('--apply')
        self.assertIn('- 2026-07-19 · mnemo · open 1 · '
                      '[[Session — 2026-07-19 живая]]', read(self.handoff))

    def test_open_count_survives_the_rewrite(self):
        self.run_script('--apply')
        body = read(self.handoff)
        self.assertIn('· open 3 ·', body)
        self.assertIn('· open 5 ·', body)

    def test_relinked_line_respects_the_byte_budget(self):
        write(self.handoff, HEADER
              + '- 2026-04-05 · ' + 'я' * 200 + ' · open 5 · (без session-заметки)\n')
        self.run_script('--apply')
        for line in read(self.handoff).splitlines():
            if line.startswith('- 20'):
                self.assertLessEqual(len(line.encode()), 200, line)

    def test_pointer_with_no_block_anywhere_is_reported_not_guessed(self):
        write(self.handoff, HEADER
              + '- 2025-01-01 · древний · open 2 · (без session-заметки)\n')
        result = self.run_script('--apply')
        self.assertIn('без блока в архиве: 1', result.stdout)
        self.assertIn('без session-заметки', read(self.handoff))

    def test_backup_precedes_the_write(self):
        before = read(self.handoff)
        self.run_script('--apply')
        self.assertEqual(before, read(self.handoff + '.bak-relink'))

    def test_second_run_is_a_no_op(self):
        self.run_script('--apply')
        after_first = read(self.handoff)
        result = self.run_script('--apply')
        self.assertIn('нечего менять', result.stdout)
        self.assertEqual(after_first, read(self.handoff))


if __name__ == '__main__':
    unittest.main(verbosity=2)

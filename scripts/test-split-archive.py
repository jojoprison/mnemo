#!/usr/bin/env python3
"""Tests for split-handoff-archive.py.

The archive is cold, not harmless: at 717 KiB it is past the 256 KB read limit,
so "it's all still in the archive" is a promise nothing can keep. Splitting must
therefore produce parts that are actually openable — and must not lose a byte
doing it.

Run directly:

    python3 scripts/test-split-archive.py
"""
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'scripts', 'split-handoff-archive.py')

PREFIX = '---\ntype: meta\n---\n\n# Meta — Session Handoff Archive\n\n'


def block(date: str, filler: int = 0) -> str:
    body = ('текст ' * filler) + '\n' if filler else ''
    return f'## {date} — блок {date}\n- [ ] хвост {date}\n{body}\n'


def write(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def read(path: str) -> str:
    with open(path, encoding='utf-8') as handle:
        return handle.read()


class SplitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.archive = os.path.join(self.tmp.name, 'Meta — Session Handoff Archive.md')
        self.blocks = [block('2026-03-01'), block('2026-04-02'), block('2026-04-20')]
        write(self.archive, PREFIX + ''.join(self.blocks))

    def run_split(self, *args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [sys.executable, SCRIPT, self.archive, '--today', '2026-07-25', *args],
            capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        return result

    def parts(self) -> list[str]:
        return sorted(f for f in os.listdir(self.tmp.name)
                      if f.startswith('Meta — Session Handoff Archive 2026'))

    def test_dry_run_writes_nothing(self):
        before = read(self.archive)
        result = self.run_split()
        self.assertIn('DRY RUN', result.stdout)
        self.assertEqual(before, read(self.archive))
        self.assertEqual([], self.parts())

    def test_creates_one_part_per_month(self):
        self.run_split('--apply')
        self.assertEqual(2, len(self.parts()), self.parts())

    def test_blocks_land_verbatim_in_their_month(self):
        self.run_split('--apply')
        april = read(os.path.join(self.tmp.name, 'Meta — Session Handoff Archive 2026-04.md'))
        self.assertIn(self.blocks[1].rstrip('\n'), april)
        self.assertIn(self.blocks[2].rstrip('\n'), april)
        self.assertNotIn('2026-03-01', april)

    def test_hub_shrinks_and_links_every_part(self):
        self.run_split('--apply')
        hub = read(self.archive)
        self.assertLess(len(hub.encode()), 2048)
        for part in self.parts():
            self.assertIn(f'[[{part[:-3]}]]', hub)

    def test_backup_is_written_before_applying(self):
        original = read(self.archive)
        self.run_split('--apply')
        backups = [f for f in os.listdir(self.tmp.name) if '.bak-split-' in f]
        self.assertTrue(backups)
        self.assertEqual(original, read(os.path.join(self.tmp.name, backups[0])))

    def test_oversized_month_is_split_into_readable_parts(self):
        """A month is not automatically a readable unit — June was 425 KB."""
        big = [block(f'2026-06-{day:02d}', filler=400) for day in range(1, 13)]
        write(self.archive, PREFIX + ''.join(big))
        self.run_split('--apply', '--max-part-bytes', '20000')
        parts = self.parts()
        self.assertGreater(len(parts), 1, parts)
        for part in parts:
            size = os.path.getsize(os.path.join(self.tmp.name, part))
            self.assertLessEqual(size, 256 * 1024)

    def test_nothing_is_lost_across_the_split(self):
        self.run_split('--apply')
        combined = read(self.archive) + ''.join(
            read(os.path.join(self.tmp.name, p)) for p in self.parts())
        for chunk in self.blocks:
            for line in chunk.splitlines():
                if line.strip():
                    self.assertIn(line, combined, line)

    def test_second_split_refuses_to_clobber_existing_parts(self):
        """Overwriting a part destroys the blocks an earlier split put there."""
        self.run_split('--apply')
        april = os.path.join(self.tmp.name, 'Meta — Session Handoff Archive 2026-04.md')
        before = read(april)
        # A later migration appends new blocks to the hub — a realistic re-split.
        write(self.archive, PREFIX + block('2026-04-25'))
        result = subprocess.run(
            [sys.executable, SCRIPT, self.archive, '--today', '2026-07-25', '--apply'],
            capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('уже существуют', result.stderr)
        self.assertEqual(before, read(april))

    def test_force_backs_up_each_part_before_overwriting(self):
        self.run_split('--apply')
        april = os.path.join(self.tmp.name, 'Meta — Session Handoff Archive 2026-04.md')
        before = read(april)
        write(self.archive, PREFIX + block('2026-04-25'))
        self.run_split('--apply', '--force')
        backups = [f for f in os.listdir(self.tmp.name)
                   if f.startswith('Meta — Session Handoff Archive 2026-04.md.bak')]
        self.assertTrue(backups, os.listdir(self.tmp.name))
        self.assertEqual(before, read(os.path.join(self.tmp.name, backups[0])))

    def test_parts_never_exceed_the_declared_ceiling(self):
        big = [block(f'2026-06-{day:02d}', filler=400) for day in range(1, 13)]
        write(self.archive, PREFIX + ''.join(big))
        self.run_split('--apply', '--max-part-bytes', '20000')
        for part in self.parts():
            size = sum(len(b.encode()) for b in
                       read(os.path.join(self.tmp.name, part)).split('## ')[1:])
            self.assertLessEqual(size, 20000, part)

    def test_part_frontmatter_date_is_a_real_date(self):
        big = [block(f'2026-06-{day:02d}', filler=400) for day in range(1, 13)]
        write(self.archive, PREFIX + ''.join(big))
        self.run_split('--apply', '--max-part-bytes', '20000')
        for part in self.parts():
            body = read(os.path.join(self.tmp.name, part))
            date_line = [l for l in body.splitlines() if l.startswith('date:')][0]
            self.assertRegex(date_line, r'^date: \d{4}-\d{2}-\d{2}$', part)

    def test_every_part_carries_a_links_section(self):
        self.run_split('--apply')
        for part in self.parts():
            body = read(os.path.join(self.tmp.name, part))
            self.assertIn('## Связи', body, part)
            self.assertIn('[[Meta — Session Handoff Archive]]', body)

    def test_archive_without_blocks_is_a_no_op(self):
        write(self.archive, PREFIX)
        before = read(self.archive)
        result = self.run_split('--apply')
        self.assertIn('делить нечего', result.stdout)
        self.assertEqual(before, read(self.archive))


if __name__ == '__main__':
    unittest.main(verbosity=2)

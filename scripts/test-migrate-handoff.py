#!/usr/bin/env python3
"""Tests for the one-shot handoff migration and its restore path.

An irreversible sweep over a vault with no version control earns more scrutiny
than ordinary code, so these tests pin the safety contract itself, not just the
happy path:

- dry run is the default and writes nothing,
- blocks move **verbatim and whole** — never checkbox-extracted, because live
  state also lives in flat bullets and prose (90 + ~200 occurrences measured),
- nothing is deleted: every migrated block is byte-present in the archive,
- a `.bak` exists before the first write, and restore actually brings the file
  back byte-for-byte.

Run directly:

    python3 scripts/test-migrate-handoff.py
"""
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATE = os.path.join(REPO, 'scripts', 'migrate-handoff-to-index.py')
RESTORE = os.path.join(REPO, 'scripts', 'restore-handoff-from-bak.py')

HEADER = '---\ntype: meta\n---\n\n🛡️ SIZE-GUARD line.\n\n'
BLOCK_A = (
    '## 2026-05-01 — старый блок про деплой\n'
    'Проза, которая держит состояние без чекбокса.\n'
    '- [ ] незакрытый пункт\n'
    '- плоский буллет без чекбокса\n'
    'Нарратив: [[Session — 2026-05-01 деплой]]\n\n'
)
BLOCK_B = (
    '## 2026-07-24 — свежий блок\n'
    '- [x] сделано\n'
    '- [ ] ещё нет\n\n'
)


def write(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def read(path: str) -> str:
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, script, *args],
                          capture_output=True, text=True)


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.handoff = os.path.join(self.tmp.name, 'Handoff.md')
        self.archive = os.path.join(self.tmp.name, 'Handoff Archive.md')
        write(self.handoff, HEADER + BLOCK_A + BLOCK_B)

    def migrate(self, *args: str) -> subprocess.CompletedProcess:
        result = run(MIGRATE, self.handoff, '--archive', self.archive,
                     '--today', '2026-07-25', *args)
        self.assertEqual(0, result.returncode, result.stderr)
        return result

    # --- safety ------------------------------------------------------------

    def test_dry_run_is_the_default_and_writes_nothing(self):
        before = read(self.handoff)
        result = self.migrate()
        self.assertIn('DRY RUN', result.stdout)
        self.assertEqual(before, read(self.handoff))
        self.assertFalse(os.path.exists(self.archive))

    def test_apply_writes_a_backup_first(self):
        original = read(self.handoff)
        self.migrate('--apply')
        backups = [f for f in os.listdir(self.tmp.name) if '.bak-migrate-' in f]
        self.assertTrue(backups, os.listdir(self.tmp.name))
        self.assertEqual(original, read(os.path.join(self.tmp.name, backups[0])))

    def test_blocks_move_verbatim_and_whole(self):
        """Not checkbox-extracted: prose and flat bullets must survive."""
        self.migrate('--apply')
        archive = read(self.archive)
        self.assertIn('Проза, которая держит состояние без чекбокса.', archive)
        self.assertIn('- плоский буллет без чекбокса', archive)
        self.assertIn(BLOCK_A.rstrip('\n'), archive)

    def test_nothing_is_lost_between_the_two_files(self):
        self.migrate('--apply')
        combined = read(self.handoff) + read(self.archive)
        for line in (BLOCK_A + BLOCK_B).splitlines():
            if line.strip():
                self.assertIn(line, combined, line)

    def test_verification_reports_success(self):
        result = self.migrate('--apply')
        self.assertIn('дословно присутствуют в архиве', result.stdout)

    def test_second_run_is_a_true_no_op(self):
        """A re-run used to append a "moved 0 blocks" note and blank lines."""
        self.migrate('--apply')
        handoff_after, archive_after = read(self.handoff), read(self.archive)
        result = self.migrate('--apply')
        self.assertIn('мигрировать нечего', result.stdout)
        self.assertEqual(handoff_after, read(self.handoff))
        self.assertEqual(archive_after, read(self.archive))
        self.assertNotIn('0 блоков', read(self.archive))

    def test_second_run_with_keep_blocks_does_not_duplicate_pointers(self):
        """--keep-blocks leaves blocks behind, so "no blocks left" never fired
        and each re-run appended another copy of every pointer."""
        self.migrate('--apply', '--keep-blocks', '1')
        first = len([l for l in read(self.handoff).splitlines() if l.startswith('- 20')])
        self.migrate('--apply', '--keep-blocks', '1')
        self.migrate('--apply', '--keep-blocks', '1')
        after = len([l for l in read(self.handoff).splitlines() if l.startswith('- 20')])
        self.assertEqual(first, after)

    def test_second_run_writes_no_extra_backup(self):
        self.migrate('--apply')
        before = len([f for f in os.listdir(self.tmp.name) if '.bak-migrate-' in f])
        self.migrate('--apply')
        after = len([f for f in os.listdir(self.tmp.name) if '.bak-migrate-' in f])
        self.assertEqual(before, after)

    # --- the index ---------------------------------------------------------

    def test_handoff_becomes_an_index(self):
        self.migrate('--apply')
        body = read(self.handoff)
        self.assertTrue(body.startswith(HEADER.rstrip('\n')))
        lines = [l for l in body.splitlines() if l.startswith('- 20')]
        self.assertEqual(2, len(lines))
        self.assertIn('[[Session — 2026-05-01 деплой]]', lines[1])
        self.assertIn('open 1', lines[1])

    def test_index_lines_stay_within_the_byte_budget(self):
        write(self.handoff, HEADER + '## 2026-05-01 — ' + 'щ' * 300 + '\n- [ ] x\n')
        self.migrate('--apply')
        for line in read(self.handoff).splitlines():
            if line.startswith('- 20'):
                self.assertLessEqual(len(line.encode('utf-8')), 200)

    def test_block_without_session_link_is_still_indexed(self):
        write(self.handoff, HEADER + BLOCK_B)
        self.migrate('--apply')
        line = [l for l in read(self.handoff).splitlines() if l.startswith('- 20')][0]
        self.assertIn('без session-заметки', line)

    def test_keep_blocks_leaves_the_newest_in_full(self):
        """"Newest" is by date, not by position — a real handoff is unsorted."""
        self.migrate('--apply', '--keep-blocks', '1')
        body = read(self.handoff)
        self.assertIn('## 2026-07-24 — свежий блок', body)
        self.assertNotIn('## 2026-05-01', body)
        self.assertIn('## 2026-05-01 — старый блок про деплой', read(self.archive))

    def test_existing_archive_content_is_preserved(self):
        write(self.archive, '---\ntype: meta\n---\n\n## 2026-01-01 — древний\nстарое\n')
        self.migrate('--apply')
        archive = read(self.archive)
        self.assertIn('## 2026-01-01 — древний', archive)
        self.assertIn('UPDATE 2026-07-25', archive)

    # --- restore ------------------------------------------------------------

    def test_restore_brings_the_file_back_byte_for_byte(self):
        original = read(self.handoff)
        self.migrate('--apply')
        self.assertNotEqual(original, read(self.handoff))
        result = run(RESTORE, self.handoff, '--archive', self.archive, '--apply')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(original, read(self.handoff))

    def test_restore_dry_run_writes_nothing(self):
        self.migrate('--apply')
        migrated = read(self.handoff)
        result = run(RESTORE, self.handoff, '--archive', self.archive)
        self.assertIn('DRY RUN', result.stdout)
        self.assertEqual(migrated, read(self.handoff))

    def test_restore_keeps_the_pre_restore_copy(self):
        self.migrate('--apply')
        migrated = read(self.handoff)
        run(RESTORE, self.handoff, '--archive', self.archive, '--apply')
        saved = [f for f in os.listdir(self.tmp.name) if '.pre-restore-' in f]
        self.assertTrue(saved)
        self.assertEqual(migrated, read(os.path.join(self.tmp.name, saved[0])))

    def test_restore_skips_a_post_migration_backup(self):
        """The undo that undid nothing: a second migration run backs up the
        ALREADY migrated file, and picking the newest backup by mtime then
        restores the index over the index."""
        original = read(self.handoff)
        self.migrate('--apply')
        migrated = read(self.handoff)
        # Simulate the second run's backup: newest on disk, but useless.
        decoy = self.handoff + '.bak-migrate-2026-07-26'
        write(decoy, migrated)
        os.utime(decoy, (2 ** 31, 2 ** 31))  # far future → newest by mtime
        result = run(RESTORE, self.handoff, '--archive', self.archive, '--apply')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(original, read(self.handoff))

    def test_restore_warns_when_every_backup_is_post_migration(self):
        self.migrate('--apply')
        migrated = read(self.handoff)
        for name in os.listdir(self.tmp.name):
            if '.bak-migrate-' in name:
                write(os.path.join(self.tmp.name, name), migrated)
        result = run(RESTORE, self.handoff, '--archive', self.archive)
        self.assertIn('пост-миграционными', result.stderr)

    def test_restore_without_backups_fails_closed(self):
        lonely = os.path.join(self.tmp.name, 'Nothing.md')
        write(lonely, 'x')
        result = run(RESTORE, lonely, '--apply')
        self.assertNotEqual(0, result.returncode)
        self.assertEqual('x', read(lonely))


if __name__ == '__main__':
    unittest.main(verbosity=2)

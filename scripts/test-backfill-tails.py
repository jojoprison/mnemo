#!/usr/bin/env python3
"""Tests for backfill-tails-from-archive.py.

The property that matters is not "items were appended" but "the digest can now
see them": a heading closes a pending section, so an appended sub-heading would
push the backfilled tails straight back out of view. One test asserts that by
running hot-scan's own section parser over the result.

    python3 scripts/test-backfill-tails.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'plugins', 'mnemo', 'scripts', 'backfill-tails-from-archive.py')
HOT_SCAN = os.path.join(REPO, 'plugins', 'mnemo', 'scripts', 'hot-scan.py')


def load_hot_scan():
    spec = importlib.util.spec_from_file_location('hot_scan', HOT_SCAN)
    module = importlib.util.module_from_spec(spec)
    sys.modules['hot_scan'] = module
    spec.loader.exec_module(module)
    return module


def write(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def read(path: str) -> str:
    with open(path, encoding='utf-8') as handle:
        return handle.read()


NOTE_WITH_PENDING = """---
type: session
---

# Session — 2026-07-25 разбор

## Next steps / pending

- [ ] дожать PR 51 по провенансу

## Связи

- [[MOC — mnemo]]
"""

NOTE_WITHOUT_PENDING = """---
type: session
---

# Session — 2026-07-24 другое

Текст без секции хвостов.

## Связи

- [[MOC — mnemo]]
"""


class BackfillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault = self.tmp.name
        self.note = os.path.join(self.vault, 'Session — 2026-07-25 разбор.md')
        write(self.note, NOTE_WITH_PENDING)
        write(os.path.join(self.vault, 'Meta — Session Handoff Archive 2026-07.md'),
              '---\n---\n\n'
              '## 2026-07-25 — разбор\n'
              '- [ ] дожать PR 51 провенанс (тот же хвост, другими словами)\n'
              '- [ ] пополнить баланс fal на 0.81\n'
              '- [ ] переписать сториборд под fal.ai\n'
              '[[Session — 2026-07-25 разбор]]\n')

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [sys.executable, SCRIPT, self.vault, '--today', '2026-07-27', *args],
            capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        return result

    def test_dry_run_writes_nothing(self):
        before = read(self.note)
        result = self.run_script()
        self.assertIn('DRY RUN', result.stdout)
        self.assertEqual(before, read(self.note))

    def test_only_missing_items_are_appended(self):
        """The reworded duplicate must not come back as a second checkbox."""
        self.run_script('--apply')
        body = read(self.note)
        self.assertIn('пополнить баланс fal', body)
        self.assertIn('переписать сториборд', body)
        self.assertEqual(1, body.count('дожать PR 51'), body)

    def test_appended_items_land_inside_the_pending_section(self):
        """Asserted with hot-scan's own parser: a heading would close the
        section and hide exactly the items this script exists to surface."""
        self.run_script('--apply')
        hot = load_hot_scan()
        in_pending, seen = False, []
        for line in read(self.note).split('\n'):
            if hot.HEADING_RE.match(line):
                in_pending = bool(hot.PENDING_HEADING_RE.match(line))
                continue
            if in_pending and line.strip().startswith('- ['):
                seen.append(line)
        self.assertTrue(any('пополнить баланс fal' in l for l in seen), seen)
        self.assertTrue(any('переписать сториборд' in l for l in seen), seen)

    def test_provenance_is_visible_on_each_line(self):
        self.run_script('--apply')
        self.assertIn('_из архива handoff (2026-07-25)_', read(self.note))

    def test_links_section_is_not_disturbed(self):
        self.run_script('--apply')
        body = read(self.note)
        self.assertIn('## Связи', body)
        self.assertLess(body.index('пополнить баланс fal'), body.index('## Связи'))

    def test_note_without_pending_gets_one(self):
        note = os.path.join(self.vault, 'Session — 2026-07-24 другое.md')
        write(note, NOTE_WITHOUT_PENDING)
        write(os.path.join(self.vault, 'Meta — Session Handoff Archive 2026-07.md'),
              '---\n---\n\n## 2026-07-24 — другое\n- [ ] новый хвост\n'
              '[[Session — 2026-07-24 другое]]\n')
        self.run_script('--apply')
        body = read(note)
        self.assertIn('## Next steps / pending', body)
        self.assertLess(body.index('новый хвост'), body.index('## Связи'))

    def test_second_run_is_a_no_op(self):
        self.run_script('--apply')
        after = read(self.note)
        result = self.run_script('--apply')
        self.assertIn('нечего переносить', result.stdout)
        self.assertEqual(after, read(self.note))

    def test_window_excludes_older_blocks(self):
        write(os.path.join(self.vault, 'Meta — Session Handoff Archive 2026-07.md'),
              '---\n---\n\n## 2026-07-01 — старое\n- [ ] древний хвост\n'
              '[[Session — 2026-07-25 разбор]]\n')
        self.run_script('--apply')
        self.assertNotIn('древний хвост', read(self.note))

    def test_backup_precedes_the_write(self):
        before = read(self.note)
        self.run_script('--apply')
        self.assertEqual(before, read(self.note + '.bak-backfill'))

    def test_block_without_a_note_is_reported_not_dropped_silently(self):
        write(os.path.join(self.vault, 'Meta — Session Handoff Archive 2026-07.md'),
              '---\n---\n\n## 2026-07-25 — безымянный\n- [ ] висячий хвост\n')
        result = self.run_script()
        self.assertIn('блоков без заметки: 1', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)

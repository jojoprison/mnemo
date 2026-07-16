#!/usr/bin/env python3
"""Regression tests for plugins/mnemo/scripts/handoff-archive.py.

Covers the v1.1.11 header-corruption class: the archiver silently corrupted the
live handoff on every --execute run (glued `## date## date` headers, eaten doc
header, duplicate stray headers piling up in the archive). Two root causes:

1. Loop-variable shadowing: `header = b.split(...)` inside the block loop
   overwrote the parsed document header, so the rewritten handoff started with
   the LAST block's first header line (no trailing newline) glued to the first
   hot block — and the real doc header (frontmatter + guard) was lost.
2. `''.join(blocks)` without newline normalization: a block that does not end
   with `\n` (typically the last block of the file) glues the next `## header`
   onto its tail in both the handoff and the archive.

Stdlib-only (unittest + subprocess), no framework — run directly:

    python3 scripts/test-handoff-archive.py
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'plugins', 'mnemo', 'scripts', 'handoff-archive.py')

DOC_HEADER = (
    '---\ntype: meta\ntags: [meta, handoff]\n---\n\n'
    '\U0001f6e1️ **SIZE-GUARD (check at /mn:session):** existing guard line.\n\n'
)
FRESH_BLOCK = (
    '## 2026-07-15 fresh closed block\n'
    'Recent work, stays hot by date.\n\n'
)
OLD_OPEN_BLOCK = (
    '## 2026-05-01 old but still open\n'
    'Has a live checkbox, must stay hot.\n'
    '- [ ] pending item\n\n'
)
# Deliberately NO trailing newline: the last block of a real file often lacks it,
# and this is what glued headers in production.
OLD_CLOSED_LAST_BLOCK = (
    '## 2026-03-25 old closed research\n'
    'Done long ago, must go cold.'
)


def run_archiver(vault, today='2026-07-16', extra=()):
    return subprocess.run(
        [sys.executable, SCRIPT, '--vault-path', vault, '--handoff', 'Handoff',
         '--max-kb', '0', '--keep-days', '14', '--today', today, '--execute', *extra],
        capture_output=True, text=True,
    )


def write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


class HandoffArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        self.handoff = os.path.join(self.vault, 'Handoff.md')
        self.archive = os.path.join(self.vault, 'Handoff Archive.md')

    def tearDown(self):
        self.tmp.cleanup()

    def assert_no_glued_headers(self, text, where):
        glued = re.findall(r'\S(## \d{4}-\d{2}-\d{2})', text)
        self.assertFalse(glued, f'{where}: glued header(s) {glued!r}')

    def test_doc_header_survives_and_nothing_glues(self):
        """Loop-shadowing regression: doc header must survive, no `## x## y` glue."""
        write(self.handoff, DOC_HEADER + FRESH_BLOCK + OLD_OPEN_BLOCK + OLD_CLOSED_LAST_BLOCK)
        res = run_archiver(self.vault)
        self.assertEqual(res.returncode, 0, res.stderr)

        after = read(self.handoff)
        self.assertTrue(after.startswith('---\ntype: meta'), 'doc frontmatter was eaten')
        self.assertEqual(after.count('SIZE-GUARD'), 1, 'guard must not duplicate')
        self.assert_no_glued_headers(after, 'handoff')
        # Cold header must leave the handoff entirely (no stray orphan line).
        self.assertNotIn('## 2026-03-25', after)
        # Hot blocks intact, in order.
        self.assertIn('## 2026-07-15 fresh closed block', after)
        self.assertIn('- [ ] pending item', after)

        archived = read(self.archive)
        self.assertEqual(archived.count('## 2026-03-25 old closed research'), 1)
        self.assert_no_glued_headers(archived, 'archive')

    def test_archive_append_does_not_glue_on_missing_trailing_newline(self):
        """Join-normalization regression: cold block w/o trailing \\n + existing archive."""
        write(self.archive,
              '---\ntype: meta\n---\n\n# Handoff Archive\n\n> cold\n\n'
              '## 2026-01-01 previously archived\nold body\n')
        write(self.handoff, DOC_HEADER + FRESH_BLOCK + OLD_CLOSED_LAST_BLOCK)
        res = run_archiver(self.vault)
        self.assertEqual(res.returncode, 0, res.stderr)

        archived = read(self.archive)
        self.assert_no_glued_headers(archived, 'archive')
        # Newest-first prepend: fresh cold block before previously archived one.
        self.assertLess(archived.index('## 2026-03-25'), archived.index('## 2026-01-01'))
        self.assertEqual(archived.count('## 2026-03-25 old closed research'), 1)

    def test_repeated_runs_do_not_accumulate_stray_headers(self):
        """Production symptom: every run added another stray copy of the last header."""
        write(self.handoff, DOC_HEADER + FRESH_BLOCK + OLD_OPEN_BLOCK + OLD_CLOSED_LAST_BLOCK)
        self.assertEqual(run_archiver(self.vault).returncode, 0)
        first_pass = read(self.handoff)
        # Second run: nothing left to archive; handoff must be byte-stable.
        res = run_archiver(self.vault)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(read(self.handoff), first_pass, 'handoff must be idempotent when nothing to archive')
        self.assertEqual(read(self.archive).count('## 2026-03-25 old closed research'), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)

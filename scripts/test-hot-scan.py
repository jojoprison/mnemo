#!/usr/bin/env python3
"""Tests for hot-scan.py — the open-thread digest that feeds the SessionStart nudge.

Pins the two failure classes measured on the live vault (2026-07-25):

1. **v1.1.10 blind spot.** "Live" is not always a `- [ ]`. A pending section may
   hold flat bullets (`- foo`) with no checkbox — 90 such bullets across 14
   handoff blocks, plus 200 prose lines. A scanner that only greps `- [ ]`
   reproduces the exact bug the archiver was patched for in v1.1.10.

2. **Byte-vs-char sizing.** Cyrillic in UTF-8 is ~1.35 B/char, so `len(str)`
   under-counts a Russian vault by a third. Every cap here is in BYTES.

Stdlib-only (unittest + subprocess) — run directly:

    python3 scripts/test-hot-scan.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'plugins', 'mnemo', 'scripts', 'hot-scan.py')


def write(path: str, body: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(body)


def session_note(date: str, project: str, body: str) -> str:
    return (
        f'---\ntype: session\ntags: [session]\ndate: {date}\n'
        f'project: {project}\n---\n\n# Заголовок\n\n{body}\n'
    )


def run(vault: str, *args: str) -> dict:
    """Run hot-scan in --json mode and return the parsed payload."""
    proc = subprocess.run(
        [sys.executable, SCRIPT, vault, '--json', '--today', '2026-07-25', *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f'exit {proc.returncode}: {proc.stderr}')
    return json.loads(proc.stdout)


class HotScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def texts(self, payload: dict) -> list[str]:
        return [item['text'] for group in payload['groups'] for item in group['items']]

    # --- extraction ------------------------------------------------------

    def test_extracts_open_checkbox_from_pending_section(self):
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo',
            '## Next steps / pending\n\n- [ ] проверить ре-пин интерактивно\n'))
        self.assertIn('проверить ре-пин интерактивно', self.texts(run(self.vault)))

    def test_extracts_flat_bullet_without_checkbox(self):
        """v1.1.10 class: live work is not always a checkbox."""
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'bts',
            '### ⏳ Pending\n\n- Вернуть TARGET на боевой 62214\n'))
        self.assertIn('Вернуть TARGET на боевой 62214', self.texts(run(self.vault)))

    def test_recognises_russian_pending_headings(self):
        for heading in ('## Осталось', '## Ждём', '## Хвосты', '## Что осталось'):
            with self.subTest(heading=heading):
                write(os.path.join(self.vault, 'a.md'), session_note(
                    '2026-07-24', 'p', f'{heading}\n\n- уникальный хвост\n'))
                self.assertIn('уникальный хвост', self.texts(run(self.vault)))

    def test_ignores_closed_checkbox(self):
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo',
            '## Next steps / pending\n\n- [x] уже сделано\n- [ ] ещё нет\n'))
        texts = self.texts(run(self.vault))
        self.assertIn('ещё нет', texts)
        self.assertNotIn('уже сделано', texts)

    def test_ignores_bullets_outside_pending_sections(self):
        """A flat bullet under Findings is narrative, not a tail."""
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo',
            '## Findings\n\n- это вывод, а не хвост\n\n'
            '## Next steps / pending\n\n- [ ] это хвост\n'))
        texts = self.texts(run(self.vault))
        self.assertIn('это хвост', texts)
        self.assertNotIn('это вывод, а не хвост', texts)

    def test_open_checkbox_outside_pending_still_counts(self):
        """An explicit `- [ ]` is unambiguous wherever it sits."""
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo', '## Findings\n\n- [ ] явный незакрытый пункт\n'))
        self.assertIn('явный незакрытый пункт', self.texts(run(self.vault)))

    def test_links_section_is_not_a_pending_section(self):
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo', '## Связи\n\n- [[MOC — mnemo]]\n'))
        self.assertEqual([], self.texts(run(self.vault)))

    # --- grouping & window ----------------------------------------------

    def test_groups_by_project_frontmatter(self):
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo', '## Pending\n\n- хвост mnemo\n'))
        write(os.path.join(self.vault, 'b.md'), session_note(
            '2026-07-24', 'bts-holding', '## Pending\n\n- хвост bts\n'))
        groups = {g['project']: [i['text'] for i in g['items']] for g in run(self.vault)['groups']}
        self.assertEqual(['хвост mnemo'], groups['mnemo'])
        self.assertEqual(['хвост bts'], groups['bts-holding'])

    def test_window_days_excludes_old_notes(self):
        write(os.path.join(self.vault, 'old.md'), session_note(
            '2026-06-01', 'mnemo', '## Pending\n\n- старый хвост\n'))
        write(os.path.join(self.vault, 'new.md'), session_note(
            '2026-07-24', 'mnemo', '## Pending\n\n- свежий хвост\n'))
        texts = self.texts(run(self.vault, '--window-days', '7'))
        self.assertIn('свежий хвост', texts)
        self.assertNotIn('старый хвост', texts)

    def test_project_filter_keeps_only_requested_project(self):
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo', '## Pending\n\n- хвост mnemo\n'))
        write(os.path.join(self.vault, 'b.md'), session_note(
            '2026-07-24', 'bts', '## Pending\n\n- хвост bts\n'))
        payload = run(self.vault, '--project', 'mnemo')
        self.assertEqual(['mnemo'], [g['project'] for g in payload['groups']])

    def test_non_session_notes_are_ignored(self):
        write(os.path.join(self.vault, 'atom.md'),
              '---\ntype: atom\ndate: 2026-07-24\n---\n\n## Pending\n\n- не сессия\n')
        self.assertEqual([], self.texts(run(self.vault)))

    # --- byte cap (the len() trap) ---------------------------------------

    def test_cap_is_measured_in_bytes_not_characters(self):
        """150 Cyrillic chars ≈ 270 bytes. A char-counting cap keeps too much."""
        item = 'я' * 150
        for i in range(6):
            write(os.path.join(self.vault, f'n{i}.md'), session_note(
                '2026-07-24', 'p', f'## Pending\n\n- {item} {i}\n'))
        payload = run(self.vault, '--max-kb', '1')
        self.assertLessEqual(len(payload['digest'].encode('utf-8')), 1024)

    def test_cap_drops_oldest_first(self):
        """Three equal-cost items, room for two — the oldest one goes."""
        filler = 'с' * 160
        for date, marker in (('2026-07-19', 'СТАРОЕ'),
                             ('2026-07-22', 'СРЕДНЕЕ'),
                             ('2026-07-25', 'НОВОЕ')):
            write(os.path.join(self.vault, f'{marker}.md'), session_note(
                date, 'p', f'## Pending\n\n- {filler} {marker}\n'))
        payload = run(self.vault, '--max-kb', '1')
        digest = payload['digest']
        self.assertIn('НОВОЕ', digest)
        self.assertIn('СРЕДНЕЕ', digest)
        self.assertNotIn('СТАРОЕ', digest)
        self.assertLessEqual(len(digest.encode('utf-8')), 1024)
        self.assertEqual(3, payload['total'])
        self.assertEqual(2, payload['shown'])

    # --- digest shape -----------------------------------------------------

    def test_digest_carries_stale_premise_warning(self):
        """The 21.07 dead-premise incident is designed into the output."""
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo', '## Pending\n\n- хвост\n'))
        self.assertIn('протухн', run(self.vault)['digest'])

    def test_empty_vault_yields_empty_digest_and_exit_zero(self):
        payload = run(self.vault)
        self.assertEqual([], payload['groups'])
        self.assertEqual('', payload['digest'])

    def test_missing_vault_exits_nonzero_without_traceback(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT, os.path.join(self.vault, 'nope'), '--json'],
            capture_output=True, text=True)
        self.assertNotEqual(0, proc.returncode)
        self.assertNotIn('Traceback', proc.stderr)

    def test_cap_holds_across_many_groups(self):
        """Regression: per-item accounting ignored per-group header lines and
        overshot the cap (measured 8335 B against 8192 B on the live vault)."""
        for i in range(12):
            write(os.path.join(self.vault, f'p{i}.md'), session_note(
                '2026-07-24', f'проект-номер-{i}',
                '## Pending\n\n- ' + 'ю' * 120 + f' хвост {i}\n'))
        payload = run(self.vault, '--max-kb', '2')
        self.assertLessEqual(len(payload['digest'].encode('utf-8')), 2048)
        self.assertGreater(payload['shown'], 0)

    def test_shared_prefix_items_are_not_deduped_away(self):
        """Regression: a prefix-truncated dedupe key merged distinct tails."""
        prefix = 'проверить что всё сходится в ' + 'д' * 130
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'p', f'## Pending\n\n- {prefix} ПЕРВЫЙ\n- {prefix} ВТОРОЙ\n'))
        texts = self.texts(run(self.vault))
        self.assertEqual(2, len(texts), texts)

    def test_identical_tail_from_two_sources_is_deduped(self):
        for name in ('a.md', 'b.md'):
            write(os.path.join(self.vault, name), session_note(
                '2026-07-24', 'p', '## Pending\n\n- ровно один и тот же хвост\n'))
        self.assertEqual(1, len(self.texts(run(self.vault))))

    def test_counts_are_reported_per_group(self):
        write(os.path.join(self.vault, 'a.md'), session_note(
            '2026-07-24', 'mnemo', '## Pending\n\n- один\n- два\n'))
        group = run(self.vault)['groups'][0]
        self.assertEqual(2, group['count'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

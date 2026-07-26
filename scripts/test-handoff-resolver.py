#!/usr/bin/env python3
"""Tests for handoff-resolver.py — the report-only triage view of a handoff.

Report-only forever: it never writes, never calls the network. What it produces
is a worklist plus honest arithmetic about what triage can and cannot buy.

Two measured findings are pinned here as behaviour:

1. **Anchor inheritance lies.** Counting an anchor found in the *block header*
   as the checkbox's own anchor inflates "resolvable" from 27.6% to 60.6% —
   e.g. a tail about `docs/plans/...` counted as resolvable merely because its
   block header ended with "(PR 8)". Item anchors and inherited anchors are
   reported as separate fields, and only item anchors count as resolvable.

2. **One unresolvable checkbox pins a whole block.** The archiver keeps a block
   HOT if *any* `- [ ]` remains, so a block that is 90% resolvable frees zero
   bytes. Block payoff classes must reflect that, otherwise the report promises
   space it cannot deliver.

Stdlib-only (unittest + subprocess), run directly:

    python3 scripts/test-handoff-resolver.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'plugins', 'mnemo', 'scripts', 'handoff-resolver.py')

HEADER = '---\ntype: meta\n---\n\n🛡️ SIZE-GUARD line.\n\n'


def write(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def run(path: str, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, SCRIPT, path, '--json', '--today', '2026-07-25', *args],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(f'exit {proc.returncode}: {proc.stderr}')
    return json.loads(proc.stdout)


class ResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'handoff.md')

    def blocks_by_date(self, payload: dict) -> dict:
        return {b['date']: b for b in payload['blocks']}

    # --- parsing ---------------------------------------------------------

    def test_counts_blocks_and_open_items(self):
        write(self.path, HEADER +
              '## 2026-05-01 — старый блок\n- [ ] первый\n- [x] закрытый\n\n'
              '## 2026-07-24 — свежий блок\n- [ ] второй\n')
        payload = run(self.path)
        self.assertEqual(2, payload['blocks_total'])
        self.assertEqual(2, payload['open_total'])

    def test_sizes_are_bytes_not_characters(self):
        """Cyrillic is ~2 B/char in UTF-8; a char count under-reports by a third."""
        body = HEADER + '## 2026-05-01 — блок\n- [ ] ' + 'я' * 500 + '\n'
        write(self.path, body)
        payload = run(self.path)
        self.assertEqual(len(body.encode('utf-8')), payload['bytes'])
        self.assertGreater(payload['bytes'], len(body))

    def test_prose_live_block_is_flagged(self):
        write(self.path, HEADER + '## 2026-05-01 — сервер (WAITING ответа)\nтекст без чекбоксов\n')
        block = self.blocks_by_date(run(self.path))['2026-05-01']
        self.assertTrue(block['prose_live'])
        self.assertEqual(0, block['open'])

    # --- anchors ---------------------------------------------------------

    def test_extracts_linear_and_pr_anchors_from_item_text(self):
        write(self.path, HEADER + '## 2026-05-01 — блок\n'
              '- [ ] добить BTS-250 и смержить PR #443\n')
        item = run(self.path)['items'][0]
        self.assertIn('BTS-250', item['anchors']['linear'])
        self.assertIn('443', item['anchors']['pr'])

    def test_header_anchor_is_inherited_not_owned(self):
        """The 60.6% artifact: an anchor in the header is not the item's anchor."""
        write(self.path, HEADER + '## 2026-07-25 — ACP: предполёт (PR 8)\n'
              '- [ ] Фаза-0 из docs/plans/acp-buildout-state.md\n')
        item = run(self.path)['items'][0]
        self.assertEqual([], item['anchors']['pr'])
        self.assertIn('8', item['inherited']['pr'])
        self.assertFalse(item['resolvable'])

    def test_item_without_any_anchor_is_reported_as_such(self):
        write(self.path, HEADER + '## 2026-05-01 — блок\n'
              '- [ ] Уточнить у Леонида кто реальный заказчик\n')
        payload = run(self.path)
        self.assertFalse(payload['items'][0]['resolvable'])
        self.assertEqual(1, payload['anchors']['none'])

    def test_resolvable_share_counts_only_item_anchors(self):
        write(self.path, HEADER + '## 2026-05-01 — блок про BTS-1\n'
              '- [ ] с якорем BTS-250\n- [ ] без якоря вообще\n')
        payload = run(self.path)
        self.assertEqual(1, payload['anchors']['resolvable'])
        self.assertEqual(0.5, payload['anchors']['resolvable_share'])

    # --- payoff arithmetic ------------------------------------------------

    def test_block_with_one_unresolvable_item_is_partial(self):
        """One anchorless tail pins the whole block — payoff must say so."""
        write(self.path, HEADER + '## 2026-05-01 — блок\n'
              '- [ ] BTS-250 закрыть\n- [ ] спросить Наталью\n')
        block = self.blocks_by_date(run(self.path))['2026-05-01']
        self.assertEqual('partial', block['payoff'])

    def test_block_with_all_anchored_items_is_fully_resolvable(self):
        write(self.path, HEADER + '## 2026-05-01 — блок\n'
              '- [ ] BTS-250 закрыть\n- [ ] смержить PR #443\n')
        block = self.blocks_by_date(run(self.path))['2026-05-01']
        self.assertEqual('fully-resolvable', block['payoff'])

    def test_fresh_blocks_are_not_counted_as_payoff(self):
        """A block inside keepDays stays hot regardless — it is not a saving."""
        write(self.path, HEADER + '## 2026-07-24 — свежий\n- [ ] BTS-250\n')
        payload = run(self.path, '--keep-days', '14')
        self.assertEqual('fresh', self.blocks_by_date(payload)['2026-07-24']['payoff'])
        self.assertEqual(0, payload['ceiling']['freed_bytes'])

    def test_ceiling_reports_what_full_resolution_would_free(self):
        old_resolvable = '## 2026-05-01 — блок\n- [ ] BTS-250 закрыть\n'
        old_pinned = '## 2026-05-02 — блок\n- [ ] спросить Наталью\n'
        write(self.path, HEADER + old_resolvable + '\n' + old_pinned)
        ceiling = run(self.path, '--keep-days', '14')['ceiling']
        self.assertEqual(len(old_resolvable.encode()) + 1, ceiling['freed_bytes'])
        self.assertGreater(ceiling['floor_bytes'], 0)

    # --- safety -----------------------------------------------------------

    def test_never_modifies_the_file(self):
        body = HEADER + '## 2026-05-01 — блок\n- [ ] BTS-250\n'
        write(self.path, body)
        before = os.stat(self.path)
        run(self.path)
        after = os.stat(self.path)
        self.assertEqual(body, open(self.path, encoding='utf-8').read())
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)

    def test_missing_file_exits_nonzero_without_traceback(self):
        proc = subprocess.run(
            [sys.executable, SCRIPT, os.path.join(self.tmp.name, 'nope.md'), '--json'],
            capture_output=True, text=True)
        self.assertNotEqual(0, proc.returncode)
        self.assertNotIn('Traceback', proc.stderr)

    def test_handoff_without_dated_blocks_is_not_a_crash(self):
        write(self.path, HEADER + 'просто текст без блоков\n')
        payload = run(self.path)
        self.assertEqual(0, payload['blocks_total'])
        self.assertEqual(0, payload['open_total'])

    def test_uses_the_shipped_hot_invariant(self):
        """Regression guard: the resolver must not re-implement keep-hot.

        vault-write.py owns `keep = fresh OR open- [ ] OR prose-pending`. A copy
        here would drift the day that rule changes, and the report would then
        promise savings the archiver refuses to make.
        """
        source = open(SCRIPT, encoding='utf-8').read()
        self.assertIn('vault-write.py', source)
        self.assertNotIn('re.compile(r"\\[ \\]")', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)

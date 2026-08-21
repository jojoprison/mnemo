#!/usr/bin/env python3
"""Regression tests for the private-leak guard in scripts/lint-skills.py.

Two links to the maintainer's private Obsidian notes reached a public PR during
the v1.2.14 review and were caught by hand. mnemo is a plugin *about* Obsidian,
so the repo is full of legitimate `[[wikilink]]` examples — a blanket ban is not
an option. The guard therefore allows only shapes that cannot name a real note
(placeholders, single ASCII words) plus an explicit allowlist of the illustrative
names already in the docs; anything else has to be added deliberately, which is
exactly the moment a reviewer gets to ask "is this a link into someone's vault?".

Pins:
1. The live repo passes both sweeps (positive control for the whole ruleset).
2. The actual PR #39 link is caught, and so is any other concrete note name.
3. Placeholders / single ASCII words / allowlisted names pass.
4. A sweep that finds no wikilinks at all fails loudly instead of reporting
   "clean" — a silent zero from a broken sweep is indistinguishable from a
   clean repo.
5. Machine-local home paths are caught by the same pass.

Stdlib-only (unittest), run directly:

    python3 scripts/test-lint-wikilinks.py
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts/lint-skills.py"


def load_module():
    name = f"mnemo_test_lint_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = load_module()


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LiveRepoIsClean(unittest.TestCase):
    """Positive control: the guard must pass on the repo it ships with."""

    def test_repo_has_no_private_wikilinks(self):
        self.assertEqual(lint.check_wikilinks(str(REPO_ROOT)), [])

    def test_repo_has_no_machine_local_paths(self):
        self.assertEqual(lint.check_local_paths(str(REPO_ROOT)), [])

    def test_allowlist_has_no_dead_entries(self):
        # An allowlist entry whose note name no longer appears anywhere is a
        # standing permission for a link nobody reviews — it should be removed.
        allow = lint.load_wikilink_allowlist()
        self.assertTrue(allow, "allowlist file is missing or empty")
        seen = set()
        for path in lint.iter_text_files(str(REPO_ROOT)):
            try:
                text = Path(path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            seen.update(m.group(1) for m in lint.WIKILINK_RE.finditer(text))
        self.assertEqual(sorted(allow - seen), [])


class GuardIsWiredIntoTheLinter(unittest.TestCase):
    """A guard nobody calls is worth exactly nothing — pin the call site too."""

    def _run_lint(self):
        return subprocess.run(
            [sys.executable, str(MODULE_PATH)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )

    def test_clean_repo_passes(self):
        proc = self._run_lint()
        self.assertIn("private-leak guard", proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_a_planted_violation_actually_fails_the_lint(self):
        # Asserting that the guard's line appears in the output is not enough:
        # it prints "✅" just the same when the call has been removed. Only a
        # planted violation proves main() still runs the sweep.
        planted = REPO_ROOT / "docs" / f".lint-selfcheck-{uuid.uuid4().hex}.md"
        planted.write_text("[[Atom — planted violation for the self-check]]\n", encoding="utf-8")
        self.addCleanup(planted.unlink, missing_ok=True)
        proc = self._run_lint()
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(planted.name, proc.stdout)


class CatchesPrivateLinks(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_catches_the_link_that_reached_pr_39(self):
        write(
            self.root,
            "README.md",
            "threshold is `min(...)` — see "
            "[[Atom — Окно автокомпакта Claude Code равно min настройки и контекста модели]] — and it ranges\n",
        )
        issues = lint.check_wikilinks(str(self.root))
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("README.md", issues[0])
        self.assertIn("Окно автокомпакта", issues[0])

    def test_catches_the_second_pr_39_link_wrapped_across_lines(self):
        # The real one was split by the source wrap; a line-by-line sweep reports
        # this file clean, which is why the scan reads whole files.
        write(
            self.root,
            "plugins/mnemo/scripts/x.py",
            '"""Stop hooks get no token count in stdin (see [[Atom — Stop-хук Claude Code\n'
            'не получает токены в stdin]]) — the transcript is the only source."""\n',
        )
        issues = lint.check_wikilinks(str(self.root))
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("Stop-хук Claude Code не получает токены", issues[0])

    def test_catches_a_concrete_english_note_name(self):
        # The class is not "Cyrillic" — an English note name is just as private.
        write(self.root, "docs/x.md", "background: [[Atom — mnemo autocompact window]]\n")
        self.assertEqual(len(lint.check_wikilinks(str(self.root))), 1)

    def test_catches_a_single_cyrillic_word(self):
        # A one-word name passes only when it is plain ASCII (a term like
        # [[wikilinks]]); Cyrillic means it names a real note in this vault.
        write(self.root, "docs/x.md", "см. [[Автокомпакт]]\n")
        self.assertEqual(len(lint.check_wikilinks(str(self.root))), 1)

    def test_reports_file_and_line(self):
        write(self.root, "docs/x.md", "first\nsecond\n[[Atom — some real note]]\n")
        issues = lint.check_wikilinks(str(self.root))
        self.assertIn("docs/x.md:3", issues[0])

    def test_message_names_both_ways_out(self):
        # errors that teach: the reader must learn what to do, not just that
        # something is wrong.
        write(self.root, "docs/x.md", "[[Atom — some real note]]\n")
        message = lint.check_wikilinks(str(self.root))[0]
        self.assertIn("wikilink-allowlist.txt", message)


class AllowsSafeShapes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_allows_placeholders(self):
        write(
            self.root,
            "docs/x.md",
            "[[{hub_name}]] [[Session — …]] [[Session — ...]] [[{fact_prefix}API X v2]]\n",
        )
        self.assertEqual(lint.check_wikilinks(str(self.root)), [])

    def test_allows_single_ascii_words(self):
        write(self.root, "docs/x.md", "[[wikilinks]] [[link]] [[Note]] [[foo.md]] [[LangGraph]]\n")
        self.assertEqual(lint.check_wikilinks(str(self.root)), [])

    def test_allows_regex_fragments_in_code(self):
        # The literal in relink-orphan-pointers.py:24 — the regex sees `[[^\]]+]]`
        # inside it and must not read that as a note name.
        write(self.root, "s.py", 'LINK_RE = re.compile(r"\\[\\[[^\\]]+\\]\\]")\n[[wikilinks]]\n')
        self.assertEqual(lint.check_wikilinks(str(self.root)), [])

    def test_allows_allowlisted_names(self):
        entry = sorted(lint.load_wikilink_allowlist())[0]
        write(self.root, "docs/x.md", f"[[{entry}]]\n")
        self.assertEqual(lint.check_wikilinks(str(self.root)), [])

    def test_skips_gitignored_plans(self):
        # docs/plans/ is gitignored working state, full of real note names; it
        # never ships, so scanning it would only produce noise.
        write(self.root, "docs/plans/state.md", "[[Atom — private working note]]\n")
        write(self.root, "docs/x.md", "[[wikilinks]]\n")
        self.assertEqual(lint.check_wikilinks(str(self.root)), [])


class SweepIntegrity(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_a_sweep_that_finds_nothing_fails_instead_of_passing(self):
        # A zero from the sweep is a statement about the sweep, not the repo:
        # wrong extension list, wrong root, wrong regex all look like "clean".
        write(self.root, "docs/x.md", "no links here\n")
        issues = lint.check_wikilinks(str(self.root))
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("no wikilinks", issues[0].lower())

    def test_scans_every_shipped_text_extension(self):
        for rel in ("a.md", "b.py", "c.sh", "d.json", "e.yaml", "f.yml", "g.txt"):
            write(self.root, rel, "[[Atom — a real note name]]\n")
        self.assertEqual(len(lint.check_wikilinks(str(self.root))), 7)


class CatchesMachineLocalPaths(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_catches_absolute_home_path(self):
        write(self.root, "docs/x.md", "run `python3 /Users/someone/Documents/projects/mnemo/x.py`\n")
        issues = lint.check_local_paths(str(self.root))
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("docs/x.md:1", issues[0])

    def test_catches_windows_and_linux_home_paths(self):
        write(self.root, "a.md", "C:\\Users\\someone\\vault\n")
        write(self.root, "b.md", "/home/someone/.mnemo/config.json\n")
        self.assertEqual(len(lint.check_local_paths(str(self.root))), 2)

    def test_allows_tilde_and_env_forms(self):
        # `~/.mnemo/config.json` and `${CODEX_HOME:-~/.codex}` are portable and
        # used throughout the docs on purpose.
        write(
            self.root,
            "docs/x.md",
            "config lives at `~/.mnemo/config.json`, Codex at `${CODEX_HOME:-~/.codex}/memories/`\n",
        )
        self.assertEqual(lint.check_local_paths(str(self.root)), [])

    def test_allows_generic_placeholder_users(self):
        write(self.root, "docs/x.md", "/Users/<you>/Documents · /Users/$USER/vault\n")
        self.assertEqual(lint.check_local_paths(str(self.root)), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

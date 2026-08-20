#!/usr/bin/env python3
"""Tests for mnemo-context.sh — the SessionStart nudge plus open-tails digest.

The digest half is new: it is the first automatic reader the handoff/forward
state ever had (measured 2026-07-25: continuity reads happened in 6% of
sessions, because 805 KiB cannot be read at all). These tests pin the
properties that make injecting it safe:

- it never costs the nudge — any failure degrades to nudge-only,
- it is gated (`hooks.hotDigest`) and scoped (`hot.scope`),
- it stays under the byte cap it advertises.

The Obsidian CLI is mocked on PATH, so the tests neither need Obsidian running
nor touch the real vault.

Stdlib-only (unittest + subprocess), run directly:

    python3 scripts/test-context-hook.py
"""
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "plugins", "mnemo", "hooks", "mnemo-context.sh")
PLUGIN_ROOT = os.path.join(REPO, "plugins", "mnemo")

# Seed fixtures at today's date: the digest only reads sessions inside
# hot-scan's window (DEFAULT_WINDOW_DAYS = 7), so a hardcoded date turns every
# digest assertion green-on-empty the moment it ages out of that window.
TODAY = dt.date.today().isoformat()

SESSION_NOTE = (
    "---\ntype: session\ntags: [session]\ndate: {date}\nproject: {project}\n---\n\n"
    "# Заголовок\n\n## Next steps / pending\n\n- [ ] {tail}\n"
)


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class ContextHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = self.tmp.name
        os.makedirs(os.path.join(self.home, ".mnemo"))

        self.vault = os.path.join(self.home, "vault")
        os.makedirs(self.vault)
        write(os.path.join(self.vault, "s.md"), SESSION_NOTE.format(
            date=TODAY, project="mnemo", tail="уникальный незакрытый хвост"))
        write(os.path.join(self.vault, "other.md"), SESSION_NOTE.format(
            date=TODAY, project="другой-проект", tail="чужой хвост"))

        # Mock the Obsidian CLI: `obsidian vault vault=<name>` → tab-separated path.
        self.bin = os.path.join(self.home, "bin")
        os.makedirs(self.bin)
        self.obsidian = os.path.join(self.bin, "obsidian")
        self.write_cli(f'printf "name\\tmain\\npath\\t{self.vault}\\n"')

    def write_cli(self, body: str) -> None:
        write(self.obsidian, f"#!/bin/sh\n{body}\n")
        os.chmod(self.obsidian, 0o755)

    def config(self, **overrides) -> None:
        payload = {"vault": "main"}
        payload.update(overrides)
        write(os.path.join(self.home, ".mnemo", "config.json"), json.dumps(payload))

    def run_hook(self, cwd: str | None = None) -> str:
        env = dict(os.environ)
        env["HOME"] = self.home
        env["PATH"] = self.bin + os.pathsep + env["PATH"]
        env["CLAUDE_PLUGIN_ROOT"] = PLUGIN_ROOT
        env.pop("PLUGIN_ROOT", None)
        env.pop("CODEX_THREAD_ID", None)
        env.pop("CODEX_SESSION_ID", None)
        result = subprocess.run(
            ["bash", HOOK], capture_output=True, text=True, env=env,
            cwd=cwd or REPO, stdin=subprocess.DEVNULL)
        self.assertEqual(0, result.returncode, result.stderr)
        if not result.stdout.strip():
            return ""
        payload = json.loads(result.stdout)
        return payload.get("hookSpecificOutput", {}).get("additionalContext", "")

    # --- the digest ------------------------------------------------------

    def test_digest_is_injected_next_to_the_nudge(self):
        self.config()
        context = self.run_hook()
        self.assertIn("mnemo memory is set up here", context)
        self.assertIn("уникальный незакрытый хвост", context)

    def test_digest_carries_the_stale_premise_warning(self):
        self.config()
        self.assertIn("протухн", self.run_hook())

    def test_project_scope_is_the_default(self):
        """Run from the mnemo repo → only the mnemo project's tails."""
        self.config()
        context = self.run_hook()
        self.assertIn("уникальный незакрытый хвост", context)
        self.assertNotIn("чужой хвост", context)

    def test_scope_all_shows_every_project(self):
        self.config(hot={"scope": "all"})
        context = self.run_hook()
        self.assertIn("уникальный незакрытый хвост", context)
        self.assertIn("чужой хвост", context)

    # --- gates -----------------------------------------------------------

    def test_hot_digest_gate_suppresses_only_the_digest(self):
        self.config(hooks={"hotDigest": False})
        context = self.run_hook()
        self.assertIn("mnemo memory is set up here", context)
        self.assertNotIn("уникальный незакрытый хвост", context)

    def test_session_start_gate_suppresses_everything(self):
        self.config(hooks={"sessionStartNudge": False})
        self.assertEqual("", self.run_hook())

    # --- degradation ------------------------------------------------------

    def test_missing_obsidian_cli_keeps_the_nudge(self):
        self.config()
        os.remove(self.obsidian)
        context = self.run_hook()
        self.assertIn("mnemo memory is set up here", context)
        self.assertNotIn("📌", context)

    def test_failing_obsidian_cli_keeps_the_nudge(self):
        self.config()
        self.write_cli("exit 3")
        self.assertIn("mnemo memory is set up here", self.run_hook())

    def test_garbage_from_obsidian_cli_keeps_the_nudge(self):
        self.config()
        self.write_cli('printf "surprise\\n"')
        context = self.run_hook()
        self.assertIn("mnemo memory is set up here", context)
        self.assertNotIn("📌", context)

    def test_no_vault_key_stays_silent(self):
        write(os.path.join(self.home, ".mnemo", "config.json"), json.dumps({}))
        self.assertEqual("", self.run_hook())

    def test_digest_respects_the_byte_cap(self):
        self.config(hot={"scope": "all", "maxKB": 1})
        for i in range(20):
            write(os.path.join(self.vault, f"n{i}.md"), SESSION_NOTE.format(
                date=TODAY, project="mnemo", tail="я" * 150 + f" {i}"))
        context = self.run_hook()
        # Assert the digest rendered at all: an empty one trivially fits any cap,
        # so without this the cap assertion passes while measuring nothing.
        self.assertIn("📌", context)
        digest = context.split("📌", 1)[1]
        self.assertTrue(digest.strip())
        self.assertLessEqual(len("📌".encode() + digest.encode()), 1024)


if __name__ == "__main__":
    unittest.main(verbosity=2)

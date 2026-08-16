#!/usr/bin/env python3
"""Regression tests for mnemo-autocompact-nudge.sh (hooks.autocompactNudge).

Pins:
1. Opt-in only: silent unless hooks.autocompactNudge is explicitly true.
2. Claude Code only: no-ops (never blocks) under a Codex runtime.
3. Blocks once entering "warn" and once entering "critical" — the anti-loop
   marker stores the highest severity already nudged, so re-crossing the same
   level is silent but escalating to a higher one nudges again.
4. Silent when the window can't be resolved (no guessed default) or the
   stop_hook_active recursion flag is set.

Stdlib-only (unittest + subprocess), run directly:

    python3 scripts/test-autocompact-nudge.py
"""
import json
import os
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "plugins", "mnemo", "hooks", "mnemo-autocompact-nudge.sh")

WINDOW = 600000


def transcript_with_usage(used_tokens):
    return json.dumps({
        "message": {
            "role": "assistant",
            "usage": {"input_tokens": used_tokens, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
        }
    }) + "\n"


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class AutocompactNudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = self.tmp.name
        os.makedirs(os.path.join(home, ".mnemo"), exist_ok=True)
        write(os.path.join(home, ".mnemo", "config.json"), json.dumps({"hooks": {"autocompactNudge": True}}))
        self.home = home
        # Anti-loop markers live in a shared per-user cache keyed on session_id
        # (NOT under HOME) — see test-stop-nudge.py for the same reasoning.
        self.uniq = os.path.basename(home.rstrip("/"))
        self.transcript = os.path.join(home, "t.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, payload, window=WINDOW, codex=False, extra_env=None):
        env = {k: v for k, v in os.environ.items() if k not in ("PLUGIN_ROOT", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CLAUDE_CODE_AUTO_COMPACT_WINDOW")}
        env["HOME"] = self.home
        if window is not None:
            env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(window)
        if codex:
            env["CODEX_THREAD_ID"] = "codex-thread-x"
        if extra_env:
            env.update(extra_env)
        res = subprocess.run(
            ["bash", HOOK], input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=15
        )
        return res.stdout.strip()

    def test_silent_when_not_opted_in(self):
        write(os.path.join(self.home, ".mnemo", "config.json"), json.dumps({"hooks": {}}))
        write(self.transcript, transcript_with_usage(WINDOW - 5000))
        out = json.loads(self.run_hook({"session_id": f"s-off-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}))
        self.assertNotEqual(out.get("decision"), "block")

    def test_no_op_on_codex_even_when_critical(self):
        write(self.transcript, transcript_with_usage(WINDOW - 5000))
        out = json.loads(self.run_hook({"session_id": f"s-codex-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}, codex=True))
        self.assertNotEqual(out.get("decision"), "block")
        self.assertNotIn("suppressOutput", out)  # codex-format pass()

    def test_silent_below_warn_margin(self):
        write(self.transcript, transcript_with_usage(WINDOW - 200000))
        out = json.loads(self.run_hook({"session_id": f"s-far-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}))
        self.assertNotEqual(out.get("decision"), "block")

    def test_blocks_and_recommends_review_full_at_warn(self):
        write(self.transcript, transcript_with_usage(WINDOW - 40000))
        out = json.loads(self.run_hook({"session_id": f"s-warn-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}))
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("/mn:review --full", out["reason"])
        self.assertIn("approaching", out["reason"])

    def test_blocks_with_stronger_wording_at_critical(self):
        write(self.transcript, transcript_with_usage(WINDOW - 5000))
        out = json.loads(self.run_hook({"session_id": f"s-crit-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}))
        self.assertEqual(out.get("decision"), "block")
        self.assertIn("very close", out["reason"])

    def test_does_not_renudge_same_severity_twice(self):
        write(self.transcript, transcript_with_usage(WINDOW - 40000))
        p = {"session_id": f"s-dedup-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}
        first = json.loads(self.run_hook(p))
        second = json.loads(self.run_hook(p))
        self.assertEqual(first.get("decision"), "block")
        self.assertNotEqual(second.get("decision"), "block")

    def test_escalates_from_warn_to_critical(self):
        session = f"s-escalate-{self.uniq}"
        write(self.transcript, transcript_with_usage(WINDOW - 40000))
        warn = json.loads(self.run_hook({"session_id": session, "transcript_path": self.transcript, "stop_hook_active": False}))
        self.assertEqual(warn.get("decision"), "block")
        self.assertIn("approaching", warn["reason"])

        write(self.transcript, transcript_with_usage(WINDOW - 5000))
        critical = json.loads(self.run_hook({"session_id": session, "transcript_path": self.transcript, "stop_hook_active": False}))
        self.assertEqual(critical.get("decision"), "block")
        self.assertIn("very close", critical["reason"])

    def test_silent_when_window_unresolved(self):
        write(self.transcript, transcript_with_usage(500000))
        out = json.loads(self.run_hook({"session_id": f"s-nowindow-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}, window=None))
        self.assertNotEqual(out.get("decision"), "block")

    def test_stop_hook_active_recursion_guard_passes(self):
        write(self.transcript, transcript_with_usage(WINDOW - 5000))
        out = json.loads(self.run_hook({"session_id": f"s-recur-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": True}))
        self.assertNotEqual(out.get("decision"), "block")

    def test_silent_when_transcript_missing(self):
        out = json.loads(self.run_hook({"session_id": f"s-nofile-{self.uniq}", "transcript_path": os.path.join(self.home, "nope.jsonl"), "stop_hook_active": False}))
        self.assertNotEqual(out.get("decision"), "block")


if __name__ == "__main__":
    unittest.main(verbosity=2)

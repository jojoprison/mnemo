#!/usr/bin/env python3
"""Regression tests for mnemo-stop-nudge.sh (v1.2.9).

Pins the v1.2.9 behavior:
1. The nudge recommends the ONE-command close-out `/mn:review --full`
   (Codex: `$mnemo:review --full`), not save+session listed separately.
2. The anti-loop governor blocks at most once per session (marker keyed on
   session_id; in Codex, where the Stop payload may omit session_id, it falls
   back to CODEX_THREAD_ID so it dedups instead of re-nudging every Stop).
3. It stays silent unless worth-saving signals ≥3 AND save/session are missing.

Stdlib-only (unittest + subprocess), run directly:

    python3 scripts/test-stop-nudge.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(REPO, "plugins", "mnemo", "hooks", "mnemo-stop-nudge.sh")

# 3 signal-bearing messages (SIGNAL_RE: fixed/resolved/decided/gotcha/...) → signals=3.
SIGNAL_TRANSCRIPT = "\n".join(
    json.dumps({"message": {"role": "assistant", "content": [{"type": "text", "text": t}]}})
    for t in ("we finally fixed the auth bug", "root cause resolved", "decided on Redis, gotcha noted")
) + "\n"

# Same 3 signals BUT with save + session skills invoked → both ran → no nudge.
BOTH_RAN_TRANSCRIPT = SIGNAL_TRANSCRIPT + "\n".join(
    json.dumps({"message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": s}}]}})
    for s in ("save", "session")
) + "\n"

# Below the worth-saving threshold (1 signal < 3) → silent.
LOW_SIGNAL_TRANSCRIPT = json.dumps(
    {"message": {"role": "assistant", "content": [{"type": "text", "text": "just fixed a typo"}]}}
) + "\n"


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class StopNudgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Isolated HOME so the gate reads OUR config, not the real user's.
        home = self.tmp.name
        os.makedirs(os.path.join(home, ".mnemo"), exist_ok=True)
        write(os.path.join(home, ".mnemo", "config.json"), json.dumps({"hooks": {"stopNudge": True}}))
        self.home = home
        # Anti-loop markers live in a shared per-user cache keyed on session_id (NOT under
        # HOME), so identical ids would collide across test runs. Derive a per-run-unique
        # suffix from the temp dir name so each run uses fresh marker keys.
        self.uniq = os.path.basename(home.rstrip("/"))
        self.transcript = os.path.join(home, "t.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, payload, codex=False, thread=None):
        env = {k: v for k, v in os.environ.items() if k not in ("PLUGIN_ROOT", "CODEX_THREAD_ID", "CODEX_SESSION_ID")}
        env["HOME"] = self.home
        if codex:
            env["CODEX_THREAD_ID"] = thread or "codex-thread-x"
        res = subprocess.run(
            ["bash", HOOK], input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=15
        )
        return res.stdout.strip()

    def test_nudge_recommends_review_full_claude(self):
        write(self.transcript, SIGNAL_TRANSCRIPT)
        out = self.run_hook({"session_id": f"s-claude-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False})
        data = json.loads(out)
        self.assertEqual(data.get("decision"), "block")
        self.assertIn("/mn:review --full", data["reason"])
        self.assertNotIn("/mn:save and /mn:session", data["reason"])  # no longer lists them separately

    def test_nudge_uses_codex_syntax(self):
        write(self.transcript, SIGNAL_TRANSCRIPT)
        out = self.run_hook({"session_id": f"s-codex-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}, codex=True)
        self.assertIn("$mnemo:review --full", json.loads(out)["reason"])

    def test_blocks_at_most_once_per_session(self):
        write(self.transcript, SIGNAL_TRANSCRIPT)
        p = {"session_id": f"s-dedup-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}
        first = json.loads(self.run_hook(p))
        second = json.loads(self.run_hook(p))
        self.assertEqual(first.get("decision"), "block")
        self.assertTrue(second.get("continue"))  # second Stop passes through
        self.assertNotEqual(second.get("decision"), "block")

    def test_codex_dedups_on_thread_when_session_id_missing(self):
        """The v1.2.9 fix: unstable/absent Codex session_id keys on CODEX_THREAD_ID."""
        write(self.transcript, SIGNAL_TRANSCRIPT)
        p = {"session_id": "unknown", "transcript_path": self.transcript, "stop_hook_active": False}
        first = json.loads(self.run_hook(p, codex=True, thread=f"thread-{self.uniq}"))
        second = json.loads(self.run_hook(p, codex=True, thread=f"thread-{self.uniq}"))
        self.assertEqual(first.get("decision"), "block")
        self.assertTrue(second.get("continue"))

    def test_silent_below_signal_threshold(self):
        write(self.transcript, LOW_SIGNAL_TRANSCRIPT)
        out = json.loads(self.run_hook({"session_id": f"s-low-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}))
        self.assertNotEqual(out.get("decision"), "block")

    def test_silent_when_save_and_session_already_ran(self):
        write(self.transcript, BOTH_RAN_TRANSCRIPT)
        out = json.loads(self.run_hook({"session_id": f"s-both-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": False}))
        self.assertNotEqual(out.get("decision"), "block")

    def test_stop_hook_active_recursion_guard_passes(self):
        write(self.transcript, SIGNAL_TRANSCRIPT)
        out = json.loads(self.run_hook({"session_id": f"s-recur-{self.uniq}", "transcript_path": self.transcript, "stop_hook_active": True}))
        self.assertNotEqual(out.get("decision"), "block")


if __name__ == "__main__":
    unittest.main(verbosity=2)

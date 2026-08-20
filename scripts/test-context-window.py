#!/usr/bin/env python3
"""Regression tests for plugins/mnemo/scripts/context-window.py — the token/window
resolver behind hooks/mnemo-autocompact-nudge.sh.

Pins:
1. Window resolution order: env CLAUDE_CODE_AUTO_COMPACT_WINDOW -> project-local
   settings.json -> project-shared settings.json -> user settings.json ->
   ~/.claude.json autoCompactWindowsCache -> None (silence, never a guess).
2. Usage parsing reads the LAST assistant turn's usage from the transcript,
   ignoring non-assistant lines and lines with no usage block.
3. level_for clamps warn/critical margins down (never up) on a small window,
   and reports "unknown" whenever usage or window is unresolved.

Stdlib-only (unittest), run directly:

    python3 scripts/test-context-window.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "plugins/mnemo/scripts/context-window.py"


def load_module():
    name = f"mnemo_test_context_window_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cw = load_module()


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")


def usage_line(input_tokens=0, cache_creation=0, cache_read=0, role="assistant"):
    return json.dumps({
        "message": {
            "role": role,
            "usage": {
                "input_tokens": input_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            },
        }
    })


class LastUsageTokensTest(unittest.TestCase):
    def test_none_when_file_missing(self):
        self.assertIsNone(cw.last_usage_tokens("/nonexistent/path.jsonl"))

    def test_none_when_no_usage_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            write(path, json.dumps({"message": {"role": "assistant", "content": []}}) + "\n")
            self.assertIsNone(cw.last_usage_tokens(str(path)))

    def test_sums_usage_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            write(path, usage_line(100, 20, 5) + "\n")
            self.assertEqual(cw.last_usage_tokens(str(path)), 125)

    def test_ignores_non_assistant_and_malformed_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            content = "\n".join([
                "not json at all",
                json.dumps({"message": {"role": "user", "usage": {"input_tokens": 999999}}}),
                usage_line(100, 0, 0),
            ]) + "\n"
            write(path, content)
            self.assertEqual(cw.last_usage_tokens(str(path)), 100)

    def test_takes_last_assistant_usage_not_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            content = usage_line(100) + "\n" + usage_line(50000) + "\n"
            write(path, content)
            self.assertEqual(cw.last_usage_tokens(str(path)), 50000)


class ResolveWindowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.path.join(self.tmp.name, "project")
        os.makedirs(self.cwd)
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)
        self.env_patch = mock.patch.dict(os.environ, {"HOME": self.home}, clear=False)
        self.env_patch.start()
        for key in ("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "CLAUDE_CONFIG_DIR"):
            os.environ.pop(key, None)

    def tearDown(self):
        self.env_patch.stop()
        self.tmp.cleanup()

    def transcript(self, model: str = "claude-opus-5") -> str:
        path = Path(self.tmp.name) / f"{model}.jsonl"
        write(path, json.dumps({"message": {"role": "assistant", "model": model}}) + "\n")
        return str(path)

    def test_none_when_nothing_resolves(self):
        self.assertIsNone(cw.resolve_window(self.cwd))

    def test_env_var_wins_over_everything(self):
        write(Path(self.cwd) / ".claude" / "settings.json", {"autoCompactWindow": 111111})
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "222222"}):
            self.assertEqual(cw.resolve_window(self.cwd), 222222)

    def test_project_local_settings_before_shared(self):
        write(Path(self.cwd) / ".claude" / "settings.json", {"autoCompactWindow": 300000})
        write(Path(self.cwd) / ".claude" / "settings.local.json", {"autoCompactWindow": 400000})
        self.assertEqual(cw.resolve_window(self.cwd), 400000)

    def test_falls_back_to_user_settings(self):
        write(Path(self.home) / ".claude" / "settings.json", {"autoCompactWindow": 500000})
        self.assertEqual(cw.resolve_window(self.cwd), 500000)

    def test_cache_is_read_by_the_active_model_key(self):
        # autoCompactWindowsCache is a per-model map, and Claude Code reads the
        # entry for the model in play — never "any positive value it holds".
        write(
            Path(self.home) / ".claude.json",
            {"autoCompactWindowsCache": {"claude-opus-5": 600000}},
        )
        transcript = self.transcript(model="claude-opus-5")
        self.assertEqual(cw.resolve_window(self.cwd, transcript), 600000)

    def test_cache_entry_may_be_an_object_with_a_default(self):
        write(
            Path(self.home) / ".claude.json",
            {"autoCompactWindowsCache": {"claude-opus-5": {"default": 700000}}},
        )
        transcript = self.transcript(model="claude-opus-5")
        self.assertEqual(cw.resolve_window(self.cwd, transcript), 700000)

    def test_another_models_cache_entry_is_never_borrowed(self):
        # Borrowing a foreign entry is how a 1M number lands on a 200k session
        # (silence forever) or a 200k number on a 1M one (a false critical).
        write(
            Path(self.home) / ".claude.json",
            {"autoCompactWindowsCache": {"claude-sonnet-4-6": 1000000}},
        )
        transcript = self.transcript(model="claude-opus-5")
        self.assertIsNone(cw.resolve_window(self.cwd, transcript))

    def test_null_cache_resolves_to_none(self):
        write(Path(self.home) / ".claude.json", {"autoCompactWindowsCache": None})
        self.assertIsNone(cw.resolve_window(self.cwd))

    def test_settings_beat_cache(self):
        write(Path(self.home) / ".claude" / "settings.json", {"autoCompactWindow": 500000})
        write(
            Path(self.home) / ".claude.json",
            {"autoCompactWindowsCache": {"claude-opus-5": 600000}},
        )
        self.assertEqual(cw.resolve_window(self.cwd, self.transcript()), 500000)

    # --- validation: Claude Code accepts only int in [100k, 1M] -------------

    def test_out_of_range_env_is_ignored_like_claude_code_does(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "5000"}):
            self.assertIsNone(cw.resolve_window(self.cwd))
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "9000000"}):
            self.assertIsNone(cw.resolve_window(self.cwd))

    def test_out_of_range_settings_value_is_ignored(self):
        write(Path(self.home) / ".claude" / "settings.json", {"autoCompactWindow": 42})
        self.assertIsNone(cw.resolve_window(self.cwd))

    # --- account ceiling: the default that makes the feature work at all ----

    def test_without_large_context_access_the_model_default_applies(self):
        # A proven-200k account needs no configuration for the nudge to work.
        write(Path(self.home) / ".claude.json", {"s1mAccessCache": {"acct": {"hasAccess": False}}})
        self.assertEqual(cw.resolve_window(self.cwd), 200000)

    def test_large_context_access_stays_silent_rather_than_guessing(self):
        # The transcript records the model without its [1m] suffix, so a 1M
        # session is indistinguishable from a 200k one. Assuming 200k would
        # block the turn at 15% full, so an unproven ceiling means silence.
        write(Path(self.home) / ".claude.json", {"s1mAccessCache": {"acct": {"hasAccess": True}}})
        self.assertIsNone(cw.resolve_window(self.cwd))

    def test_unreadable_access_cache_stays_silent(self):
        write(Path(self.home) / ".claude.json", {"s1mAccessCache": {"acct": {"other": 1}}})
        self.assertIsNone(cw.resolve_window(self.cwd))

    def test_configured_window_is_clamped_to_the_account_ceiling(self):
        # The measured failure this clamp exists for: a 460k setting on a 200k
        # session never takes effect, and an unclamped nudge would fire late.
        write(Path(self.home) / ".claude.json", {"s1mAccessCache": {"acct": {"hasAccess": False}}})
        write(Path(self.home) / ".claude" / "settings.json", {"autoCompactWindow": 460000})
        self.assertEqual(cw.resolve_window(self.cwd), 200000)

    def test_configured_window_below_the_ceiling_is_kept(self):
        write(Path(self.home) / ".claude.json", {"s1mAccessCache": {"acct": {"hasAccess": False}}})
        write(Path(self.home) / ".claude" / "settings.json", {"autoCompactWindow": 150000})
        self.assertEqual(cw.resolve_window(self.cwd), 150000)


class LastModelTest(unittest.TestCase):
    def test_reads_the_last_assistant_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            write(path, "\n".join([
                json.dumps({"message": {"role": "assistant", "model": "old-model"}}),
                json.dumps({"message": {"role": "user", "model": "never-this"}}),
                json.dumps({"message": {"role": "assistant", "model": "claude-opus-5"}}),
            ]) + "\n")
            self.assertEqual(cw.last_model(str(path)), "claude-opus-5")

    def test_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            write(path, json.dumps({"message": {"role": "assistant"}}) + "\n")
            self.assertIsNone(cw.last_model(str(path)))


class LevelForTest(unittest.TestCase):
    def test_unknown_when_usage_missing(self):
        self.assertEqual(cw.level_for(None, 600000), "unknown")

    def test_unknown_when_window_missing(self):
        self.assertEqual(cw.level_for(100, None), "unknown")

    def test_none_when_far_from_window(self):
        self.assertEqual(cw.level_for(100000, 600000), "none")

    def test_bands_are_measured_from_the_real_compaction_point(self):
        # Claude Code compacts before the window is full — it reserves room for
        # the reply plus a safety margin. Measured from W, "critical" would sit
        # ~23k past a point the session can never reach, i.e. be unreachable.
        threshold = 600000 - cw.compaction_reserve(600000)
        self.assertEqual(cw.level_for(threshold - 40000, 600000), "warn")
        self.assertEqual(cw.level_for(threshold - 5000, 600000), "critical")
        self.assertEqual(cw.level_for(threshold + 1, 600000), "critical")

    def test_critical_is_reachable_on_a_default_window(self):
        # The regression this guards: with bands measured from W, autocompact
        # fires first and "critical" never happens on a real session.
        threshold = 200000 - cw.compaction_reserve(200000)
        self.assertEqual(cw.level_for(threshold, 200000), "critical")

    def test_reserve_matches_claude_codes_own_arithmetic(self):
        # W - min(max_output, 20000) - 13000
        self.assertEqual(cw.compaction_reserve(200000), 33000)
        self.assertEqual(cw.compaction_reserve(1000000), 33000)

    def test_usage_above_the_window_means_the_window_is_wrong(self):
        # A session cannot hold more than its window, so this can only mean the
        # resolved window is not the one in force. Reporting "critical" there
        # would block the turn on a false reading; "unknown" keeps it quiet.
        self.assertEqual(cw.level_for(300000, 200000), "unknown")
        self.assertEqual(cw.level_for(200001, 200000), "unknown")
        self.assertNotEqual(cw.level_for(200000, 200000), "unknown")

    def test_margins_clamp_down_on_small_window(self):
        # window=20000: uncapped critical (10000) and warn (50000) would each
        # eat more than the whole window, and so would a full 33000 reserve.
        # Everything clamps down against the window instead.
        self.assertLess(cw.compaction_reserve(20000), 20000)
        self.assertEqual(cw.level_for(1000, 20000), "none")
        self.assertEqual(cw.level_for(19000, 20000), "critical")


if __name__ == "__main__":
    unittest.main(verbosity=2)

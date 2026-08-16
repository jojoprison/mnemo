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

    def test_falls_back_to_claude_json_cache_number(self):
        write(Path(self.home) / ".claude.json", {"autoCompactWindowsCache": 600000})
        self.assertEqual(cw.resolve_window(self.cwd), 600000)

    def test_null_cache_resolves_to_none(self):
        write(Path(self.home) / ".claude.json", {"autoCompactWindowsCache": None})
        self.assertIsNone(cw.resolve_window(self.cwd))

    def test_settings_beat_cache(self):
        write(Path(self.home) / ".claude" / "settings.json", {"autoCompactWindow": 500000})
        write(Path(self.home) / ".claude.json", {"autoCompactWindowsCache": 600000})
        self.assertEqual(cw.resolve_window(self.cwd), 500000)


class LevelForTest(unittest.TestCase):
    def test_unknown_when_usage_missing(self):
        self.assertEqual(cw.level_for(None, 600000), "unknown")

    def test_unknown_when_window_missing(self):
        self.assertEqual(cw.level_for(100, None), "unknown")

    def test_none_when_far_from_window(self):
        self.assertEqual(cw.level_for(100000, 600000), "none")

    def test_warn_within_default_margin(self):
        self.assertEqual(cw.level_for(600000 - 40000, 600000), "warn")

    def test_critical_within_default_margin(self):
        self.assertEqual(cw.level_for(600000 - 5000, 600000), "critical")

    def test_margins_clamp_down_on_small_window(self):
        # window=20000: uncapped critical (10000) and warn (50000) would each
        # eat more than the whole window. Clamped: critical=min(10000,2000)=2000,
        # warn=min(50000,5000)=5000.
        self.assertEqual(cw.level_for(20000 - 6000, 20000), "none")
        self.assertEqual(cw.level_for(20000 - 3000, 20000), "warn")
        self.assertEqual(cw.level_for(20000 - 1000, 20000), "critical")


if __name__ == "__main__":
    unittest.main(verbosity=2)

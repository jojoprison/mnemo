#!/usr/bin/env python3
"""Regression tests for runtime-owned configuration roots."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPTS = REPO_ROOT / "plugins/mnemo/scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))

import cache_utils  # noqa: E402 - plugin script directory must be importable first


def load_module(relative_path: str):
    name = f"mnemo_test_{Path(relative_path).stem.replace('-', '_')}_{uuid.uuid4().hex}"
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedRootHelperTests(unittest.TestCase):
    def test_configured_root_honors_overrides_home_defaults_and_explicit_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            pinned_home = Path(tmp) / "pinned"
            override = "~/custom-codex"
            with mock.patch.dict(
                os.environ,
                {"HOME": str(home), "CODEX_HOME": override},
                clear=False,
            ):
                self.assertEqual(
                    cache_utils.configured_root("CODEX_HOME", ".codex"),
                    str(home / "custom-codex"),
                )
                self.assertEqual(
                    cache_utils.configured_root("CODEX_HOME", ".codex", pinned_home),
                    str(pinned_home / ".codex"),
                )

            with mock.patch.dict(
                os.environ,
                {"HOME": str(home), "CODEX_HOME": ""},
                clear=False,
            ):
                self.assertEqual(
                    cache_utils.configured_root("CODEX_HOME", ".codex"),
                    str(home / ".codex"),
                )


class SessionRootTests(unittest.TestCase):
    def test_session_scan_honors_both_runtime_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude_root = root / "claude-profile"
            codex_root = root / "codex-profile"
            session_id = "session-custom-root"

            claude_log = claude_root / "projects/repo" / f"{session_id}.jsonl"
            claude_log.parent.mkdir(parents=True)
            claude_log.write_text("{}\n")

            codex_log = codex_root / "sessions/2026/07/20" / f"rollout-{session_id}.jsonl"
            codex_log.parent.mkdir(parents=True)
            codex_log.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"cwd": str(REPO_ROOT)},
                    }
                )
                + "\n"
            )

            with mock.patch.dict(
                os.environ,
                {
                    "CLAUDE_CONFIG_DIR": str(claude_root),
                    "CODEX_HOME": str(codex_root),
                },
                clear=False,
            ):
                module = load_module("plugins/mnemo/scripts/session-scan.py")
                with mock.patch.object(module.os, "getcwd", return_value=str(REPO_ROOT)):
                    self.assertEqual(module.find_claude_jsonl(session_id), str(claude_log))
                    self.assertEqual(module.find_codex_jsonl(session_id), str(codex_log))


class DiscoveryRootTests(unittest.TestCase):
    def test_skill_discovery_honors_both_runtime_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            claude_root = root / "claude-profile"
            codex_root = root / "codex-profile"
            user_skill = codex_root / "skills/home-test/SKILL.md"
            user_skill.parent.mkdir(parents=True)
            user_skill.write_text(
                "---\nname: home-test\ndescription: custom CODEX_HOME fixture\n---\n"
            )
            with mock.patch.dict(
                os.environ,
                {
                    "CLAUDE_CONFIG_DIR": str(claude_root),
                    "CODEX_HOME": str(codex_root),
                    "CODEX_THREAD_ID": "thread-custom-root",
                },
                clear=False,
            ):
                module = load_module("plugins/mnemo/scripts/skills-discover.py")

            patterns = module.discovery_patterns()
            self.assertTrue(any(str(claude_root / "skills") in path for path in patterns))
            self.assertTrue(any(str(codex_root / "skills") in path for path in patterns))
            self.assertEqual(module.codex_config_path(), str(codex_root / "config.toml"))
            discovered = module.discover()
            self.assertTrue(
                any(item.startswith("user:home-test —") for item in discovered),
                discovered,
            )


class ClaudeMemRootTests(unittest.TestCase):
    def test_claude_mem_probe_honors_claude_config_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            claude_root = Path(tmp) / "claude-profile"
            cache = claude_root / "plugins/cache/thedotmack/claude-mem/12.4.0"
            cache.mkdir(parents=True)
            (cache.parent / "12.3.9").mkdir()
            (cache.parent / "README.txt").write_text("not a version directory")
            with mock.patch.dict(
                os.environ,
                {"CLAUDE_CONFIG_DIR": str(claude_root)},
                clear=False,
            ):
                module = load_module("plugins/mnemo/scripts/claude-mem-save.py")
                self.assertEqual(
                    module.claude_mem_probe(),
                    ("12.4.0", 1, str(cache.parent)),
                )
                self.assertEqual(module.claude_mem_version(), "12.4.0")

                result = subprocess.run(
                    ["bash", str(PLUGIN_SCRIPTS / "check-cm-version.sh")],
                    check=False,
                    text=True,
                    capture_output=True,
                    env=os.environ.copy(),
                )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.splitlines(),
                ["version: 12.4.0", "stale: 1", f"path: {cache.parent}"],
            )

    def test_shell_probe_expands_tilde_prefixed_config_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache = home / "claude-profile/plugins/cache/thedotmack/claude-mem/12.5.0"
            cache.mkdir(parents=True)
            env = os.environ.copy()
            env.update({"HOME": str(home), "CLAUDE_CONFIG_DIR": "~/claude-profile"})

            result = subprocess.run(
                ["bash", str(PLUGIN_SCRIPTS / "check-cm-version.sh")],
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.splitlines(),
                ["version: 12.5.0", "stale: 0", f"path: {cache.parent}"],
            )

    def test_missing_claude_mem_is_a_successful_empty_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update({"HOME": tmp})
            env.pop("CLAUDE_CONFIG_DIR", None)

            result = subprocess.run(
                ["bash", str(PLUGIN_SCRIPTS / "check-cm-version.sh")],
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.splitlines(),
                ["version:", "stale: 0", "path:"],
            )


class ClaudeIndexStatusTests(unittest.TestCase):
    def _status_for_index(
        self,
        root: Path,
        content: str,
        *,
        warn_kb: int = 1024 * 1024,
    ) -> dict:
        module = load_module("plugins/mnemo/scripts/runtime-memory.py")
        home = root / "home"
        config_root = home / ".claude"
        memory_root = root / "custom-memory"
        repo = root / "repo"
        config_root.mkdir(parents=True)
        memory_root.mkdir()
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (config_root / "settings.json").write_text(
            json.dumps({"autoMemoryDirectory": str(memory_root)})
        )
        (memory_root / "MEMORY.md").write_text(content)
        return module.claude_index_status(
            cwd=repo,
            home=home,
            warn_kb=warn_kb,
            env={},
        )

    def test_hard_line_limit_is_exact_and_cannot_be_hidden_by_early_warning(self) -> None:
        for line_count, expected in ((200, False), (201, True)):
            with self.subTest(line_count=line_count), tempfile.TemporaryDirectory() as tmp:
                payload = self._status_for_index(
                    Path(tmp),
                    "x\n" * line_count,
                )

                self.assertEqual(payload["lines"], line_count)
                self.assertEqual(payload["over_hard_limit"], expected)
                self.assertEqual(payload["warning"], expected)
                self.assertEqual(
                    "hard_line_limit" in payload["warning_reasons"],
                    expected,
                )

    def test_hard_byte_limit_is_exact_and_cannot_be_hidden_by_early_warning(self) -> None:
        for byte_count, expected in ((25_000, False), (25_001, True)):
            with self.subTest(byte_count=byte_count), tempfile.TemporaryDirectory() as tmp:
                payload = self._status_for_index(Path(tmp), "x" * byte_count)

                self.assertEqual(payload["bytes"], byte_count)
                self.assertEqual(payload["over_hard_limit"], expected)
                self.assertEqual(payload["warning"], expected)
                self.assertEqual(
                    "hard_byte_limit" in payload["warning_reasons"],
                    expected,
                )

    def test_metrics_strip_frontmatter_and_block_html_comments_before_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live = "# Memory\n- remembered\n"
            content = (
                "---\n"
                + "metadata: "
                + "f" * 15_000
                + "\n---\n"
                + "<!--\n"
                + "c" * 15_000
                + "\n-->\n"
                + live
            )
            payload = self._status_for_index(Path(tmp), content)

            self.assertEqual(payload["bytes"], len(live.encode()))
            self.assertEqual(payload["lines"], len(live.splitlines()))
            self.assertEqual(payload["raw_bytes"], len(content.encode()))
            self.assertFalse(payload["over_hard_limit"])
            self.assertFalse(payload["warning"])

    def test_html_comment_markers_inside_fences_still_count_toward_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            content = "```html\n<!--\n" + "x" * 25_000 + "\n-->\n```\n"
            payload = self._status_for_index(Path(tmp), content)

            self.assertEqual(payload["bytes"], len(content.encode()))
            self.assertEqual(payload["lines"], len(content.splitlines()))
            self.assertTrue(payload["over_hard_limit"])
            self.assertIn("hard_byte_limit", payload["warning_reasons"])

    def test_file_metrics_resist_intermediate_symlink_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module = load_module("plugins/mnemo/scripts/runtime-memory.py")
            root = Path(tmp)
            memory_root = root / "memory"
            nested = memory_root / "nested"
            nested.mkdir(parents=True)
            safe = "safe\n"
            (nested / "MEMORY.md").write_text(safe)
            outside = root / "outside"
            outside.mkdir()
            (outside / "MEMORY.md").write_text("OUTSIDE-METRICS-CONTENT\n")
            moved = memory_root / "nested-original"
            real_open = module.os.open
            swapped = False

            def racing_open(path, *args, **kwargs):
                nonlocal swapped
                if not swapped and Path(path).name == "MEMORY.md":
                    swapped = True
                    nested.rename(moved)
                    nested.symlink_to(outside, target_is_directory=True)
                return real_open(path, *args, **kwargs)

            with mock.patch.object(module.os, "open", side_effect=racing_open):
                data, size, reason = module._read_file_bytes(
                    memory_root,
                    nested / "MEMORY.md",
                    limit=module.MAX_FILE_BYTES,
                )

            self.assertTrue(swapped)
            self.assertEqual(data, safe.encode())
            self.assertEqual(size, len(safe.encode()))
            self.assertIsNone(reason)

    def test_metadata_probe_reuses_effective_auto_memory_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            config_root = home / ".claude"
            memory_root = root / "custom-memory"
            repo = root / "repo"
            config_root.mkdir(parents=True)
            (home / ".mnemo").mkdir(parents=True)
            memory_root.mkdir()
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (config_root / "settings.json").write_text(
                json.dumps({"autoMemoryDirectory": str(memory_root)})
            )
            (home / ".mnemo" / "config.json").write_text(
                json.dumps({"memory": {"indexWarnKB": 0}})
            )
            index = "# Memory\n" + "- remembered\n" * 8
            (memory_root / "MEMORY.md").write_text(index)
            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "CLAUDE_CONFIG_DIR": str(config_root),
                }
            )

            result = subprocess.run(
                [
                    "python3",
                    str(PLUGIN_SCRIPTS / "runtime-memory.py"),
                    "claude-index-status",
                ],
                cwd=repo,
                input="{}",
                check=False,
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["available"], True)
            self.assertEqual(payload["bytes"], len(index.encode()))
            self.assertEqual(payload["lines"], len(index.splitlines()))
            self.assertEqual(payload["warning"], True)
            self.assertEqual(payload["warn_kb"], 0)
            self.assertEqual(Path(payload["memory_dir"]).resolve(), memory_root.resolve())


if __name__ == "__main__":
    unittest.main()

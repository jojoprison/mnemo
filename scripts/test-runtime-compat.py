#!/usr/bin/env python3
"""Regression tests for Claude/Codex runtime compatibility helpers."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SCRIPTS = REPO_ROOT / "plugins/mnemo/scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))

import cache_utils  # noqa: E402 - plugin script directory must be importable first


def load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


session_scan = load_module("mnemo_session_scan", "plugins/mnemo/scripts/session-scan.py")
skills_discover = load_module("mnemo_skills_discover", "plugins/mnemo/scripts/skills-discover.py")
claude_mem_save = load_module("mnemo_claude_mem_save", "plugins/mnemo/scripts/claude-mem-save.py")
safe_read = load_module("mnemo_safe_read", "plugins/mnemo/scripts/safe-read.py")
skill_lint = load_module("mnemo_skill_lint", "scripts/lint-skills.py")


class SessionScanTests(unittest.TestCase):
    def test_codex_custom_tool_calls_and_explicit_skill_are_recorded(self) -> None:
        acc = session_scan.empty_acc()
        session_scan.parse_codex_message(
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "name": "exec",
                    "input": "await tools.apply_patch('*** Begin Patch')",
                },
            },
            acc,
        )
        session_scan.parse_codex_message(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Please use $mnemo:save now; compare $mnemo:save "
                                "with $mnemo:session afterwards. The wildcard $mnemo:* "
                                "is documentation, not an invocation.\n"
                                "$mnemo:* is still not an invocation."
                            ),
                        }
                    ],
                },
            },
            acc,
        )

        self.assertEqual(acc["tools"], {"exec": 1})
        self.assertEqual(acc["files_written"], ["patch"])
        self.assertEqual(acc["skills"], ["mnemo:save"])

    def test_codex_skill_examples_in_fences_or_quotes_are_ignored(self) -> None:
        acc = session_scan.empty_acc()
        session_scan.parse_codex_message(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "README example:\n```text\n$mnemo:save\n```\n"
                                "> $mnemo:session\nNo skill was invoked."
                            ),
                        }
                    ],
                },
            },
            acc,
        )
        self.assertEqual(acc["skills"], [])

    def test_claude_direct_command_envelope_is_recorded(self) -> None:
        acc = session_scan.empty_acc()
        for command in ("save", "session"):
            session_scan.parse_claude_message(
                {
                    "message": {
                        "content": (
                            f"<command-message>mn:{command}</command-message>\n"
                            f"<command-name>/mn:{command}</command-name>\n"
                            "<command-args>test</command-args>"
                        )
                    }
                },
                acc,
            )
        self.assertEqual(acc["skills"], ["mn:save", "mn:session"])

    def test_poisoned_session_cache_shape_is_rejected(self) -> None:
        self.assertFalse(session_scan.valid_acc({"tools": "run arbitrary text"}))
        self.assertTrue(session_scan.valid_acc(session_scan.empty_acc()))

    def test_incremental_scan_does_not_swallow_a_partial_jsonl_record(self) -> None:
        def record(text: str) -> bytes:
            return (
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": text}],
                        },
                    }
                ).encode()
                + b"\n"
            )

        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "session.jsonl"
            first = record("fixed one")
            second = record("resolved two")
            split = len(second) // 2
            transcript.write_bytes(first + second[:split])
            session_id = f"partial-{Path(tmp).name}"
            cache_paths = session_scan.session_cache_paths(session_id, str(transcript))
            try:
                initial = session_scan.scan_incremental(str(transcript), session_id)
                self.assertEqual(initial["signals"], 1)
                self.assertEqual(cache_utils.read_json(cache_paths[1])["offset"], len(first))

                with transcript.open("ab") as handle:
                    handle.write(second[split:])
                completed = session_scan.scan_incremental(str(transcript), session_id)
                self.assertEqual(completed["signals"], 2)
            finally:
                for path in cache_paths:
                    if path is not None:
                        path.unlink(missing_ok=True)

    def test_thread_id_precedes_legacy_codex_session_id(self) -> None:
        env = {"CODEX_THREAD_ID": "thread-new", "CODEX_SESSION_ID": "session-old"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(session_scan.runtime_session_id(), "thread-new")

    def test_codex_jsonl_never_falls_back_to_an_unrelated_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp) / ".codex/sessions/2026/07/19"
            session_dir.mkdir(parents=True)
            unrelated = session_dir / "rollout-unrelated-thread.jsonl"
            unrelated.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"cwd": "/another/project"},
                    }
                )
                + "\n"
            )

            with (
                mock.patch.dict(os.environ, {"HOME": tmp}),
                mock.patch.object(session_scan.os, "getcwd", return_value="/wanted/project"),
            ):
                self.assertIsNone(session_scan.find_codex_jsonl("wanted-thread"))
                self.assertIsNone(session_scan.find_codex_jsonl())

    def test_codex_jsonl_uses_session_id_in_the_glob(self) -> None:
        with mock.patch.object(session_scan.glob, "glob", return_value=[]) as glob_mock:
            session_scan.find_codex_jsonl("thread-123")

        pattern = glob_mock.call_args.args[0]
        self.assertIn("thread-123", pattern)


class SkillsDiscoverTests(unittest.TestCase):
    def test_only_newest_cache_generation_is_scanned_and_manifest_sets_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / ".codex/plugins/cache/mnemo/mnemo"
            old_root = cache / "1.1.11"
            new_root = cache / "1.2.0"
            old_skill = old_root / "skills/mn-save/SKILL.md"
            new_skill = new_root / "skills/save/SKILL.md"
            for path, name in ((old_skill, "mn:save"), (new_skill, "save")):
                path.parent.mkdir(parents=True)
                path.write_text(f"---\nname: {name}\ndescription: test skill\n---\n")
            manifest = new_root / ".codex-plugin/plugin.json"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest.write_text(json.dumps({"name": "mnemo"}))
            os.utime(old_root, (1, 1))
            os.utime(new_root, (2, 2))

            selected = skills_discover.select_current_cache_paths(
                [str(old_skill), str(new_skill)], home=tmp
            )

            self.assertEqual(selected, [str(new_skill)])
            self.assertEqual(skills_discover.plugin_namespace(str(new_skill)), "mnemo")

    def test_claude_namespace_does_not_depend_on_codex_worktree_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugin = Path(tmp) / ".codex/worktrees/abc/project/plugins/mnemo"
            skill = plugin / "skills/save/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: save\ndescription: test skill\n---\n")
            for manifest_dir, name in ((".claude-plugin", "mn"), (".codex-plugin", "mnemo")):
                manifest = plugin / manifest_dir / "plugin.json"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(json.dumps({"name": name}))

            with mock.patch.object(skills_discover, "IS_CODEX", False):
                self.assertEqual(skills_discover.plugin_namespace(str(skill)), "mn")

    def test_claude_excludes_project_agents_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_skill = Path(tmp) / ".agents/skills/codex-only/SKILL.md"
            project_skill.parent.mkdir(parents=True)
            project_skill.write_text("---\nname: codex-only\ndescription: test\n---\n")
            with mock.patch.object(skills_discover, "IS_CODEX", False):
                old_cwd = os.getcwd()
                try:
                    os.chdir(tmp)
                    self.assertTrue(skills_discover.skip_for_runtime(str(project_skill)))
                finally:
                    os.chdir(old_cwd)

    def test_nested_cwd_discovers_repo_plugin_and_shadows_installed_copy(self) -> None:
        canonical = ("ask", "save", "session", "review", "connect", "setup", "health")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            plugin = root / "plugins/mnemo"
            manifest = plugin / ".codex-plugin/plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"name": "mnemo"}))
            for name in canonical:
                skill = plugin / f"skills/{name}/SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text(f"---\nname: {name}\ndescription: local {name}\n---\n")
            nested = root / "docs/reference"
            nested.mkdir(parents=True)

            old_cwd = os.getcwd()
            try:
                os.chdir(nested)
                with mock.patch.object(skills_discover, "IS_CODEX", True):
                    found = skills_discover.discover()
            finally:
                os.chdir(old_cwd)

        local = [entry.split(" — ", 1)[0] for entry in found if entry.startswith("mnemo:")]
        self.assertEqual(local, [f"mnemo:{name}" for name in sorted(canonical)])

    def test_codex_excludes_all_claude_only_skill_roots(self) -> None:
        user_claude_paths = (
            Path(skills_discover.HOME) / ".claude/skills/claude-only/SKILL.md",
            Path(skills_discover.HOME)
            / ".claude/plugins/local/skills/claude-only/SKILL.md",
            Path(skills_discover.HOME)
            / ".claude/plugins/cache/store/plugin/1.0.0/skills/claude-only/SKILL.md",
        )
        with mock.patch.object(skills_discover, "IS_CODEX", True):
            for path in user_claude_paths:
                with self.subTest(path=path):
                    self.assertTrue(skills_discover.skip_for_runtime(str(path)))

            with tempfile.TemporaryDirectory() as tmp:
                project_skill = Path(tmp) / ".claude/skills/claude-only/SKILL.md"
                old_cwd = os.getcwd()
                try:
                    os.chdir(tmp)
                    self.assertTrue(skills_discover.skip_for_runtime(str(project_skill)))
                finally:
                    os.chdir(old_cwd)


class PrivateCacheTests(unittest.TestCase):
    def test_cache_is_private_and_atomic_write_replaces_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(cache_utils.tempfile, "gettempdir", return_value=tmp):
                path = cache_utils.cache_path("test", "identity", "txt")
                assert path is not None
                self.assertTrue(cache_utils.atomic_write_text(path, "first"))
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

                victim = Path(tmp) / "victim"
                victim.write_text("untouched")
                path.unlink()
                path.symlink_to(victim)
                self.assertTrue(cache_utils.atomic_write_text(path, "replacement"))
                self.assertEqual(victim.read_text(), "untouched")
                self.assertFalse(path.is_symlink())
                self.assertEqual(cache_utils.read_text(path), "replacement")

    def test_world_readable_cache_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cache.txt"
            path.write_text("poison")
            path.chmod(0o644)
            self.assertIsNone(cache_utils.read_text(path))

class SkillLintTests(unittest.TestCase):
    def test_every_command_hook_must_use_the_portable_root(self) -> None:
        hooks = {
            "hooks": {
                "SessionStart": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": '"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/ok.sh"',
                            },
                            {"type": "command", "command": '"${CLAUDE_PLUGIN_ROOT}/bad.sh"'},
                        ]
                    }
                ]
            }
        }
        commands = skill_lint.command_hook_commands(hooks)
        portable = "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}"
        self.assertEqual(len(commands), 2)
        self.assertFalse(all(portable in command for command in commands))

    def test_health_gates_claude_state_out_of_codex(self) -> None:
        health = (REPO_ROOT / "plugins/mnemo/skills/health/SKILL.md").read_text()
        step_zero = health.split("### Step 0:", 1)[1].split("### Step 1:", 1)[0]
        step_ten = health.split("### Step 10:", 1)[1].split("## Gotchas", 1)[0]

        for step in (step_zero, step_ten):
            self.assertIn("**Claude Code only.**", step)
            self.assertIn("In Codex, skip this step", step)
        self.assertIn("never scan `~/.claude/projects/`", step_ten)

    def test_inline_obsidian_writes_with_generated_content_are_banned(self) -> None:
        malicious = 'obsidian append file="{MOC}" content="- [[x"; touch /tmp/pwn; echo "]]"'
        self.assertTrue(skill_lint.has_inline_obsidian_write(malicious))
        for skill in (REPO_ROOT / "plugins/mnemo/skills").glob("*/SKILL.md"):
            self.assertFalse(skill_lint.has_inline_obsidian_write(skill.read_text()), skill)

    def test_direct_obsidian_cli_is_banned_from_skill_bodies(self) -> None:
        self.assertTrue(
            skill_lint.has_direct_obsidian_cli('obsidian backlinks file="{vault_note}"')
        )
        for skill in (REPO_ROOT / "plugins/mnemo/skills").glob("*/SKILL.md"):
            self.assertFalse(skill_lint.has_direct_obsidian_cli(skill.read_text()), skill)

    def test_every_skill_body_carries_its_invocation_marker(self) -> None:
        for skill in sorted((REPO_ROOT / "plugins/mnemo/skills").glob("*/SKILL.md")):
            name = skill.parent.name
            marker = f"`🧠 mn:{name} (mnemo) → running`"
            body = skill.read_text()
            self.assertEqual(body.count(marker), 1, skill)
            # marker must sit right after the H1, ahead of Portable paths, so it loads first
            self.assertLess(body.index(marker), body.index("## Portable paths"), skill)

    def test_runtime_hook_manifests_compose_without_duplicate_events(self) -> None:
        plugin = REPO_ROOT / "plugins/mnemo"
        shared = json.loads((plugin / "hooks/hooks.json").read_text())
        claude_only = json.loads((plugin / "hooks/claude-hooks.json").read_text())
        claude_manifest = json.loads((plugin / ".claude-plugin/plugin.json").read_text())
        codex_manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text())

        self.assertEqual(set(shared), {"hooks"})
        self.assertEqual(set(shared["hooks"]), {"SessionStart", "Stop"})
        self.assertEqual(set(claude_only), {"hooks"})
        self.assertEqual(set(claude_only["hooks"]), {"UserPromptExpansion"})
        self.assertTrue(set(shared["hooks"]).isdisjoint(claude_only["hooks"]))
        self.assertEqual(
            claude_manifest["hooks"],
            ["./hooks/hooks.json", "./hooks/claude-hooks.json"],
        )
        self.assertNotIn("hooks", codex_manifest)
        for manifest in (shared, claude_only):
            for groups in manifest["hooks"].values():
                for group in groups:
                    for handler in group.get("hooks", []):
                        self.assertNotIn("async", handler)


class HookCompatibilityTests(unittest.TestCase):
    def _configured_home(self, tmp: str, *, stop_nudge: bool = False) -> None:
        config = Path(tmp) / ".mnemo/config.json"
        config.parent.mkdir(parents=True)
        config.write_text(
            json.dumps(
                {
                    "vault": "main",
                    "hooks": {
                        "sessionStartNudge": True,
                        "stopNudge": stop_nudge,
                    },
                }
            )
        )

    def test_session_start_hook_uses_each_runtime_schema_and_syntax(self) -> None:
        script = REPO_ROOT / "plugins/mnemo/hooks/mnemo-context.sh"
        with tempfile.TemporaryDirectory() as tmp:
            self._configured_home(tmp)
            base_env = {"HOME": tmp, "PATH": os.environ.get("PATH", "")}

            claude = subprocess.run(
                ["bash", str(script)],
                check=True,
                capture_output=True,
                text=True,
                env=base_env,
            )
            claude_payload = json.loads(claude.stdout)
            claude_message = claude_payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("/mn:ask", claude_message)
            self.assertNotIn("systemMessage", claude_payload)

            codex_env = {**base_env, "PLUGIN_ROOT": str(REPO_ROOT / "plugins/mnemo")}
            codex = subprocess.run(
                ["bash", str(script)],
                check=True,
                capture_output=True,
                text=True,
                env=codex_env,
            )
            codex_payload = json.loads(codex.stdout)
            codex_message = codex_payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("$mnemo:ask", codex_message)
            self.assertNotIn("systemMessage", codex_payload)

    def test_skill_echo_hook_announces_mn_commands_only_and_respects_gate(self) -> None:
        script = REPO_ROOT / "plugins/mnemo/hooks/mnemo-skill-echo.sh"
        expansion = json.dumps(
            {
                "hook_event_name": "UserPromptExpansion",
                "expansion_type": "slash_command",
                "command_name": "mn:save",
                "command_args": "",
                "command_source": "plugin",
                "prompt": "/mn:save",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            self._configured_home(tmp)
            env = {"HOME": tmp, "PATH": os.environ.get("PATH", "")}

            announced = subprocess.run(
                ["bash", str(script)],
                input=expansion,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            payload = json.loads(announced.stdout)
            self.assertIn("/mn:save", payload["systemMessage"])
            self.assertTrue(payload["continue"])

            foreign = subprocess.run(
                ["bash", str(script)],
                input=expansion.replace("mn:save", "commit"),
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertNotIn("systemMessage", json.loads(foreign.stdout))

            (Path(tmp) / ".mnemo/config.json").write_text(
                json.dumps({"vault": "main", "hooks": {"invocationEcho": False}})
            )
            gated = subprocess.run(
                ["bash", str(script)],
                input=expansion,
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertNotIn("systemMessage", json.loads(gated.stdout))

            no_config = subprocess.run(
                ["bash", str(script)],
                input=expansion,
                check=True,
                capture_output=True,
                text=True,
                env={"HOME": tmp + "/nowhere", "PATH": os.environ.get("PATH", "")},
            )
            self.assertIn("/mn:save", json.loads(no_config.stdout)["systemMessage"])

            malformed = subprocess.run(
                ["bash", str(script)],
                input="{not-json",
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            malformed_payload = json.loads(malformed.stdout)
            self.assertTrue(malformed_payload["continue"])
            self.assertTrue(malformed_payload["suppressOutput"])

    def test_prewarm_uses_codex_session_id_from_minimal_hook_input(self) -> None:
        script = REPO_ROOT / "plugins/mnemo/hooks/prewarm.sh"
        with tempfile.TemporaryDirectory() as tmp:
            session_id = f"prewarm-{Path(tmp).name}"
            transcript = Path(tmp) / f".codex/sessions/2026/07/19/rollout-{session_id}.jsonl"
            transcript.parent.mkdir(parents=True)
            records = [
                {
                    "type": "session_meta",
                    "payload": {"cwd": str(REPO_ROOT)},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "fixed from prewarm"}],
                    },
                },
            ]
            transcript.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            cache_paths = session_scan.session_cache_paths(session_id, str(transcript))
            env = {
                "HOME": tmp,
                "PATH": os.environ.get("PATH", ""),
                "PLUGIN_ROOT": str(REPO_ROOT / "plugins/mnemo"),
                "TMPDIR": tempfile.gettempdir(),
            }
            try:
                prewarm = subprocess.run(
                    ["bash", str(script)],
                    input=json.dumps({"session_id": session_id}),
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=REPO_ROOT,
                )
                cached = None
                for _ in range(50):
                    cached = cache_utils.read_json(cache_paths[0])
                    if session_scan.valid_acc(cached):
                        break
                    time.sleep(0.02)
                self.assertTrue(
                    session_scan.valid_acc(cached),
                    (prewarm.stdout, prewarm.stderr, cache_paths, cached),
                )
                self.assertEqual(cached["signals"], 1)
            finally:
                for path in cache_paths:
                    if path is not None:
                        path.unlink(missing_ok=True)

    def test_plugin_root_alone_selects_codex_discovery_namespace(self) -> None:
        script = REPO_ROOT / "plugins/mnemo/scripts/skills-discover.py"
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(script)],
                check=True,
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                env={
                    "HOME": tmp,
                    "PATH": os.environ.get("PATH", ""),
                    "PLUGIN_ROOT": str(REPO_ROOT / "plugins/mnemo"),
                },
            )
        mnemo_ids = [line.split(" — ", 1)[0] for line in result.stdout.splitlines() if line.startswith("mnemo:")]
        self.assertEqual(
            mnemo_ids,
            [f"mnemo:{name}" for name in sorted(("ask", "save", "session", "review", "connect", "setup", "health"))],
        )

    def test_stop_hook_uses_codex_block_schema_and_syntax(self) -> None:
        script = REPO_ROOT / "plugins/mnemo/hooks/mnemo-stop-nudge.sh"
        with tempfile.TemporaryDirectory() as tmp:
            self._configured_home(tmp, stop_nudge=True)
            transcript = Path(tmp) / "transcript.jsonl"
            records = [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "fixed one"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "resolved two"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "decided three"}],
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "custom_tool_call",
                        "name": "exec",
                        "input": "docs mention mnemo:save and mnemo:session",
                    },
                },
            ]
            transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")
            session_id = f"mnemo-test-{Path(tmp).name}"
            marker = cache_utils.cache_path("stop-nudged", session_id, "marker")
            env = {
                "HOME": tmp,
                "PATH": os.environ.get("PATH", ""),
                "PLUGIN_ROOT": str(REPO_ROOT / "plugins/mnemo"),
            }
            try:
                result = subprocess.run(
                    ["bash", str(script)],
                    input=json.dumps(
                        {"session_id": session_id, "transcript_path": str(transcript)}
                    ),
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )
                payload = json.loads(result.stdout)
                self.assertEqual(payload["decision"], "block")
                self.assertIn("$mnemo:save", payload["reason"])
                self.assertIn("$mnemo:session", payload["reason"])

                second = subprocess.run(
                    ["bash", str(script)],
                    input=json.dumps(
                        {"session_id": session_id, "transcript_path": str(transcript)}
                    ),
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertTrue(json.loads(second.stdout)["continue"])

                active_session = f"active-{Path(tmp).name}"
                active_marker = cache_utils.cache_path("stop-nudged", active_session, "marker")
                active = subprocess.run(
                    ["bash", str(script)],
                    input=json.dumps(
                        {
                            "session_id": active_session,
                            "transcript_path": str(transcript),
                            "stop_hook_active": True,
                        }
                    ),
                    check=True,
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertTrue(json.loads(active.stdout)["continue"])
                if active_marker is not None:
                    self.assertFalse(active_marker.exists())
            finally:
                if marker is not None:
                    marker.unlink(missing_ok=True)


class SafeReadTests(unittest.TestCase):
    def test_filesystem_scans_skip_symlinked_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "vault"
            root.mkdir()
            outside = Path(tmp) / "outside.md"
            outside.write_text("secret")
            (root / "inside.md").write_text("memory")
            (root / "linked.md").symlink_to(outside)

            found = [relative.as_posix() for _, relative in safe_read.markdown_files(root)]
            self.assertEqual(found, ["inside.md"])
            with self.assertRaises(safe_read.InputError):
                safe_read.safe_note_path(root, "linked")

    def test_vault_values_are_argv_data_not_shell_or_javascript(self) -> None:
        helper = REPO_ROOT / "plugins/mnemo/scripts/safe-read.py"
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "obsidian"
            fake.write_text(
                "#!/usr/bin/env python3\n"
                "import json,sys\n"
                "print(json.dumps(sys.argv[1:]))\n"
            )
            fake.chmod(0o755)
            victim = Path(tmp) / "PWNED"
            note = 'MOC — $(touch PWNED); "quoted".md'
            vault = 'main"; touch PWNED; echo "'
            env = {
                "HOME": tmp,
                "PATH": tmp + os.pathsep + os.environ.get("PATH", ""),
            }

            backlinks = subprocess.run(
                [sys.executable, str(helper), "backlinks"],
                input=json.dumps({"file": note, "vault": vault}),
                check=True,
                capture_output=True,
                text=True,
                env=env,
                cwd=tmp,
            )
            self.assertEqual(
                json.loads(backlinks.stdout),
                ["backlinks", f"file={note}", f"vault={vault}"],
            )
            self.assertFalse(victim.exists())

            note_path = "folder/x');app.vault.delete('danger');//.md"
            shared = subprocess.run(
                [sys.executable, str(helper), "shared-targets"],
                input=json.dumps({"note_path": note_path, "vault": "main"}),
                check=True,
                capture_output=True,
                text=True,
                env=env,
                cwd=tmp,
            )
            argv = json.loads(shared.stdout)
            code = next(arg.removeprefix("code=") for arg in argv if arg.startswith("code="))
            self.assertIn(json.dumps(note_path), code)
            self.assertFalse(victim.exists())

    def test_claude_mem_payload_preserves_shell_metacharacters_as_data(self) -> None:
        summary = 'fixed `deploy`; $(touch PWNED); "quoted"'
        url, payload = claude_mem_save.build_payload(
            {
                "url": "http://127.0.0.1:37777",
                "type": "gotcha",
                "project": "mnemo",
                "summary": summary,
                "note": "Atom — shell safety",
                "vault": "main",
            },
            version="12.3.9",
        )
        self.assertEqual(url, "http://127.0.0.1:37777/api/memory/save")
        self.assertTrue(payload["text"].startswith(summary))
        self.assertEqual(payload["metadata"]["claude_mem_version"], "12.3.9")
        self.assertEqual(len(sorted(["12.3.9", "v12-preview"], key=claude_mem_save.version_key)), 2)


if __name__ == "__main__":
    unittest.main()

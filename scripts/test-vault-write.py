#!/usr/bin/env python3
"""Black-box security and optimistic-write tests for vault-write.py."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
WRITER = REPO_ROOT / "plugins/mnemo/scripts/vault-write.py"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_writer_module():
    spec = importlib.util.spec_from_file_location("mnemo_vault_write", WRITER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VaultWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir(mode=0o700)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.cli_log = self.root / "obsidian-argv.jsonl"
        cli = self.bin_dir / "obsidian"
        cli.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['FAKE_OBSIDIAN_LOG'], 'a', encoding='utf-8') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1:] == ['vault', 'vault=main']:\n"
            "    print('path\\t' + os.environ['FAKE_OBSIDIAN_VAULT'])\n"
            "    raise SystemExit(0)\n"
            "print('unexpected argv', file=sys.stderr)\n"
            "raise SystemExit(64)\n",
            encoding="utf-8",
        )
        cli.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_OBSIDIAN_LOG": str(self.cli_log),
            "FAKE_OBSIDIAN_VAULT": str(self.vault),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_writer(
        self,
        payload: dict | None = None,
        *,
        raw: bytes | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        if raw is None:
            raw = json.dumps(payload).encode("utf-8")
        result = subprocess.run(
            ["python3", str(WRITER)],
            input=raw,
            capture_output=True,
            env=self.env,
            check=False,
        )
        stdout = result.stdout.decode("utf-8", errors="replace")
        try:
            body = json.loads(stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - clearer failure
            self.fail(
                f"writer did not return one JSON result: rc={result.returncode}, "
                f"stdout={stdout!r}, stderr={result.stderr!r}: {exc}"
            )
        return result, body

    def assert_error(self, payload: dict, code: str) -> dict:
        result, body = self.run_writer(payload)
        self.assertNotEqual(result.returncode, 0, body)
        self.assertEqual(body.get("ok"), False, body)
        self.assertEqual(body.get("error", {}).get("code"), code, body)
        self.assertNotIn("content", json.dumps(body).casefold())
        return body

    def test_create_keeps_shell_syntax_inert_and_content_out_of_cli_argv(self) -> None:
        marker_a = self.root / "backtick-ran"
        marker_b = self.root / "dollar-ran"
        content = (
            "# Shell-safe\n\n"
            f"`touch {marker_a}`\n"
            f"$(touch {marker_b})\n"
        )

        result, body = self.run_writer(
            {
                "action": "create",
                "vault": "main",
                "note": "Inbox/Shell-safe",
                "content": content,
                "create_parents": True,
            }
        )

        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body["ok"], True)
        self.assertEqual(body["note"], "Inbox/Shell-safe.md")
        self.assertEqual((self.vault / "Inbox/Shell-safe.md").read_text(), content)
        self.assertFalse(marker_a.exists())
        self.assertFalse(marker_b.exists())
        calls = [json.loads(line) for line in self.cli_log.read_text().splitlines()]
        self.assertEqual(calls, [["vault", "vault=main"]])
        self.assertNotIn(content, self.cli_log.read_text())
        mode = stat.S_IMODE((self.vault / "Inbox/Shell-safe.md").stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_handoff_archive_is_owned_by_the_canonical_writer(self) -> None:
        handoff = self.vault / "Handoff.md"
        handoff.write_text(
            "---\ntype: meta\n---\n\n"
            "## 2026-01-01 closed\nDone.\n"
            "## 2026-07-20 open\n- [ ] keep me\n"
        )
        original = handoff.read_bytes()

        result, body = self.run_writer(
            {
                "action": "archive-handoff",
                "vault": "main",
                "note": "Handoff",
                "max_kb": 0,
                "keep_days": 14,
                "today": "2026-07-20",
            }
        )

        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(body["action"], "archive-handoff")
        self.assertEqual(body["archived_blocks"], 1)
        self.assertNotIn("2026-01-01", handoff.read_text())
        self.assertIn("- [ ] keep me", handoff.read_text())
        self.assertIn("2026-01-01", (self.vault / "Handoff Archive.md").read_text())
        backup = self.vault / body["backup"]
        self.assertTrue(backup.is_file())
        self.assertEqual(backup.read_bytes(), original)

    def test_create_requires_explicit_parent_creation(self) -> None:
        payload = {
            "action": "create",
            "vault": "main",
            "note": "Missing/Note",
            "content": "body",
        }
        self.assert_error(payload, "not_found")
        self.assertFalse((self.vault / "Missing").exists())

        payload["create_parents"] = True
        result, body = self.run_writer(payload)
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual((self.vault / "Missing/Note.md").read_text(), "body")

    def test_create_fails_closed_if_target_exists(self) -> None:
        target = self.vault / "Existing.md"
        target.write_text("original")

        self.assert_error(
            {
                "action": "create",
                "vault": "main",
                "note": "Existing",
                "content": "replacement",
            },
            "conflict",
        )
        self.assertEqual(target.read_text(), "original")

    def test_create_preserves_target_that_appears_during_publish(self) -> None:
        writer = load_writer_module()
        parent_fd = os.open(self.vault, os.O_RDONLY | os.O_DIRECTORY)

        def publish_competitor(
            source,
            target,
            *,
            src_dir_fd,
            dst_dir_fd,
            follow_symlinks,
        ):
            self.assertEqual(target, "Raced.md")
            competitor_fd = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=dst_dir_fd,
            )
            try:
                os.write(competitor_fd, b"competitor")
                os.fsync(competitor_fd)
            finally:
                os.close(competitor_fd)
            raise FileExistsError

        try:
            with mock.patch.object(writer.os, "link", side_effect=publish_competitor):
                with self.assertRaises(writer.WriteError) as raised:
                    writer.atomic_create(parent_fd, "Raced.md", b"mnemo")
        finally:
            os.close(parent_fd)

        self.assertEqual(raised.exception.code, "conflict")
        self.assertEqual((self.vault / "Raced.md").read_bytes(), b"competitor")
        self.assertEqual(list(self.vault.glob(".mnemo-write-*.tmp")), [])

    def test_create_rejects_hash_or_dot_but_legacy_notes_remain_editable(self) -> None:
        for note in ("Bad#Name", "Bad.Name", ".md"):
            with self.subTest(create=note):
                self.assert_error(
                    {
                        "action": "create",
                        "vault": "main",
                        "note": note,
                        "content": "new",
                    },
                    "unsafe_path",
                )
                self.assertFalse((self.vault / f"{note}.md").exists())

    def test_invalid_create_payload_does_not_leave_parent_directories(self) -> None:
        result, body = self.run_writer(
            {
                "action": "create",
                "vault": "main",
                "note": "Must-not-exist/Note",
                "create_parents": True,
            }
        )
        self.assertNotEqual(result.returncode, 0, body)
        self.assertEqual(body.get("error", {}).get("code"), "input_error")
        self.assertFalse((self.vault / "Must-not-exist").exists())

        for note in ("Legacy#Name", "Legacy.Name"):
            with self.subTest(replace=note):
                target = self.vault / f"{note}.md"
                target.write_text("old")
                result, body = self.run_writer(
                    {
                        "action": "replace",
                        "vault": "main",
                        "note": note,
                        "old_str": "old",
                        "new_str": "updated",
                    }
                )
                self.assertEqual(result.returncode, 0, body)
                self.assertEqual(target.read_text(), "updated")

    def test_rejects_absolute_traversal_windows_and_reserved_paths(self) -> None:
        for note in (
            "/tmp/escape",
            "../escape",
            "folder/../../escape",
            r"C:\\escape",
            r"folder\\escape",
            ".obsidian/plugins/escape",
            ".trash/escape",
        ):
            with self.subTest(note=note):
                self.assert_error(
                    {
                        "action": "create",
                        "vault": "main",
                        "note": note,
                        "content": "must not escape",
                        "create_parents": True,
                    },
                    "unsafe_path",
                )

    def test_rejects_symlink_parent_and_target(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (self.vault / "Linked").symlink_to(outside, target_is_directory=True)
        self.assert_error(
            {
                "action": "create",
                "vault": "main",
                "note": "Linked/Escape",
                "content": "outside",
            },
            "unsafe_path",
        )
        self.assertFalse((outside / "Escape.md").exists())

        outside_note = outside / "secret.md"
        outside_note.write_text("secret")
        (self.vault / "Alias.md").symlink_to(outside_note)
        self.assert_error(
            {
                "action": "replace",
                "vault": "main",
                "note": "Alias",
                "old_str": "secret",
                "new_str": "leaked",
            },
            "unsafe_path",
        )
        self.assertEqual(outside_note.read_text(), "secret")

    def test_exact_replace_is_atomic_preserves_mode_and_requires_one_match(self) -> None:
        target = self.vault / "Mutable.md"
        original = "alpha\nneedle\nomega\n"
        target.write_text(original)
        target.chmod(0o640)

        result, body = self.run_writer(
            {
                "action": "replace",
                "vault": "main",
                "note": "Mutable",
                "old_str": "needle",
                "new_str": "replacement",
                "expected_sha256": digest(original),
            }
        )
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(target.read_text(), "alpha\nreplacement\nomega\n")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640)

        duplicate = "same\nsame\n"
        target.write_text(duplicate)
        self.assert_error(
            {
                "action": "replace",
                "vault": "main",
                "note": "Mutable",
                "old_str": "same",
                "new_str": "new",
            },
            "precondition_failed",
        )
        self.assertEqual(target.read_text(), duplicate)

        self.assert_error(
            {
                "action": "replace",
                "vault": "main",
                "note": "Mutable",
                "old_str": "missing",
                "new_str": "new",
            },
            "precondition_failed",
        )
        self.assertEqual(target.read_text(), duplicate)

    def test_stale_hash_rejects_raced_replace_even_if_old_text_still_matches(self) -> None:
        target = self.vault / "Race.md"
        caller_view = "anchor\n"
        target.write_text(caller_view)
        stale_hash = digest(caller_view)
        raced_body = "concurrent header\nanchor\n"
        target.write_text(raced_body)

        self.assert_error(
            {
                "action": "replace",
                "vault": "main",
                "note": "Race",
                "old_str": "anchor",
                "new_str": "replacement",
                "expected_sha256": stale_hash,
            },
            "precondition_failed",
        )
        self.assertEqual(target.read_text(), raced_body)

    def test_in_flight_target_change_is_detected_before_atomic_publish(self) -> None:
        writer = load_writer_module()
        target = self.vault / "Live-race.md"
        target.write_text("start\nneedle\n")
        original_write_temp = writer.write_temp

        def write_temp_then_race(parent_fd: int, raw: bytes, mode: int) -> str:
            temp_name = original_write_temp(parent_fd, raw, mode)
            target.write_text("concurrent writer\nneedle\n")
            return temp_name

        with mock.patch.object(writer, "write_temp", side_effect=write_temp_then_race):
            with mock.patch.dict(os.environ, self.env, clear=True):
                with self.assertRaises(writer.WriteError) as raised:
                    writer.write(
                        {
                            "action": "replace",
                            "vault": "main",
                            "note": "Live-race",
                            "old_str": "needle",
                            "new_str": "replacement",
                        }
                    )

        self.assertEqual(raised.exception.code, "precondition_failed")
        self.assertEqual(target.read_text(), "concurrent writer\nneedle\n")
        self.assertEqual(list(self.vault.glob(".mnemo-write-*.tmp")), [])

    def test_change_after_final_check_is_restored_without_data_loss(self) -> None:
        writer = load_writer_module()
        target = self.vault / "Publish-race.md"
        target.write_text("start\nneedle\n")
        real_exchange = writer.atomic_exchange
        raced = False

        def exchange_after_race(parent_fd: int, first: str, second: str) -> None:
            nonlocal raced
            if not raced:
                raced = True
                target.write_text("human update\nneedle\n")
            real_exchange(parent_fd, first, second)

        with mock.patch.object(writer, "atomic_exchange", side_effect=exchange_after_race):
            with mock.patch.dict(os.environ, self.env, clear=True):
                with self.assertRaises(writer.WriteError) as raised:
                    writer.write(
                        {
                            "action": "replace",
                            "vault": "main",
                            "note": "Publish-race",
                            "old_str": "needle",
                            "new_str": "replacement",
                        }
                    )

        self.assertEqual(raised.exception.code, "precondition_failed")
        self.assertEqual(target.read_text(), "human update\nneedle\n")
        self.assertEqual(list(self.vault.glob(".mnemo-write-*.tmp")), [])
        self.assertEqual(list(self.vault.glob(".mnemo-conflict-*")), [])

    def test_second_publish_racer_stays_public_and_first_is_preserved(self) -> None:
        writer = load_writer_module()
        target = self.vault / "Double-publish-race.md"
        target.write_text("start\nneedle\n")
        real_exchange = writer.atomic_exchange
        exchanges = 0

        def exchange_after_races(parent_fd: int, first: str, second: str) -> None:
            nonlocal exchanges
            exchanges += 1
            if exchanges == 1:
                target.write_text("first human update\nneedle\n")
            elif exchanges == 2:
                target.write_text("second human update\nneedle\n")
            real_exchange(parent_fd, first, second)

        with mock.patch.object(writer, "atomic_exchange", side_effect=exchange_after_races):
            with mock.patch.dict(os.environ, self.env, clear=True):
                with self.assertRaises(writer.WriteError) as raised:
                    writer.write(
                        {
                            "action": "replace",
                            "vault": "main",
                            "note": "Double-publish-race",
                            "old_str": "needle",
                            "new_str": "replacement",
                        }
                    )

        self.assertEqual(raised.exception.code, "precondition_failed")
        self.assertEqual(target.read_text(), "second human update\nneedle\n")
        conflicts = list(self.vault.glob(".mnemo-conflict-*"))
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].read_text(), "first human update\nneedle\n")
        self.assertEqual(list(self.vault.glob(".mnemo-write-*.tmp")), [])

    def test_insert_requires_unique_anchor_and_optional_line_expectation(self) -> None:
        target = self.vault / "Handoff.md"
        original = "# Handoff\n\n## Pending\n- first\n"
        target.write_text(original)

        result, body = self.run_writer(
            {
                "action": "insert",
                "vault": "main",
                "note": "Handoff",
                "anchor": "## Pending\n",
                "content": "- inserted\n",
                "position": "after",
                "expected_line": 3,
                "expected_sha256": digest(original),
            }
        )
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(
            target.read_text(),
            "# Handoff\n\n## Pending\n- inserted\n- first\n",
        )

        current = target.read_text()
        self.assert_error(
            {
                "action": "insert",
                "vault": "main",
                "note": "Handoff",
                "anchor": "## Pending\n",
                "content": "- wrong line\n",
                "position": "before",
                "expected_line": 2,
            },
            "precondition_failed",
        )
        self.assertEqual(target.read_text(), current)

        target.write_text("marker\nmarker\n")
        self.assert_error(
            {
                "action": "insert",
                "vault": "main",
                "note": "Handoff",
                "anchor": "marker",
                "content": "new",
                "position": "after",
            },
            "precondition_failed",
        )

    def test_append_is_never_blind_and_accepts_tail_or_hash_precondition(self) -> None:
        target = self.vault / "Session.md"
        original = "# Session\nlast known line\n"
        target.write_text(original)

        self.assert_error(
            {
                "action": "append",
                "vault": "main",
                "note": "Session",
                "content": "new line\n",
            },
            "input_error",
        )
        self.assertEqual(target.read_text(), original)

        result, body = self.run_writer(
            {
                "action": "append",
                "vault": "main",
                "note": "Session",
                "content": "new line\n",
                "expected_tail": "last known line\n",
            }
        )
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(target.read_text(), original + "new line\n")

        current = target.read_text()
        self.assert_error(
            {
                "action": "append",
                "vault": "main",
                "note": "Session",
                "content": "must not land\n",
                "expected_tail": "stale tail\n",
            },
            "precondition_failed",
        )
        self.assertEqual(target.read_text(), current)

        result, body = self.run_writer(
            {
                "action": "append",
                "vault": "main",
                "note": "Session",
                "content": "hash guarded\n",
                "expected_sha256": digest(current),
            }
        )
        self.assertEqual(result.returncode, 0, body)
        self.assertEqual(target.read_text(), current + "hash guarded\n")

    def test_rejects_oversize_and_invalid_json_with_machine_readable_errors(self) -> None:
        oversized = b'{"action":"create","content":"' + b"x" * (1024 * 1024) + b'"}'
        result, body = self.run_writer(raw=oversized)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(body["ok"], False)
        self.assertEqual(body["error"]["code"], "input_error")

        result, body = self.run_writer(raw=b"not-json")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(body["ok"], False)
        self.assertEqual(body["error"]["code"], "input_error")

    def test_vault_discovery_failure_is_generic_and_does_not_echo_cli_stderr(self) -> None:
        bad_cli = self.bin_dir / "obsidian"
        bad_cli.write_text(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('credential-bearing diagnostic', file=sys.stderr)\n"
            "raise SystemExit(1)\n"
        )
        bad_cli.chmod(0o755)

        body = self.assert_error(
            {
                "action": "create",
                "vault": "main",
                "note": "Nope",
                "content": "secret content",
            },
            "vault_unavailable",
        )
        self.assertNotIn("credential-bearing", json.dumps(body))
        self.assertNotIn("secret content", json.dumps(body))

    def test_unsupported_platform_fails_before_vault_discovery_or_write(self) -> None:
        writer = load_writer_module()
        with mock.patch.object(writer, "fcntl", None):
            with mock.patch.object(writer, "discover_vault") as discover:
                with self.assertRaises(writer.WriteError) as raised:
                    writer.write(
                        {
                            "action": "create",
                            "vault": "main",
                            "note": "Must-not-write",
                            "content": "body",
                        }
                    )

        self.assertEqual(raised.exception.code, "unsupported_platform")
        discover.assert_not_called()
        self.assertFalse((self.vault / "Must-not-write.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

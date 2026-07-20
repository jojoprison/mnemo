#!/usr/bin/env python3
"""Fresh-install loader/package E2E for Claude Code and Codex.

This test deliberately stops at the plugin-loader boundary. It installs the local
repository into isolated runtime homes, inspects the resulting installed cache,
and smokes one packaged helper. It never starts a model session or calls an API.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SOURCE = REPO_ROOT / "plugins/mnemo"
CANONICAL_SKILLS = {"ask", "save", "session", "review", "connect", "setup", "health"}
LEGACY_SKILL_DIRS = {
    "vault-search",
    "memory-routing",
    "session-notes",
    "session-review",
    "link-discovery",
    "initial-setup",
    "vault-health",
}
REQUIRE_LOADERS = os.environ.get("MNEMO_REQUIRE_RUNTIME_LOADERS") == "1"


def isolated_env(root: Path, *, runtime: str | None) -> dict[str, str]:
    """Return a minimal environment that cannot discover the user's runtime state."""
    home = root / "home"
    tmp = root / "tmp"
    xdg = root / "xdg"
    for path in (home, tmp, xdg / "config", xdg / "cache", xdg / "data"):
        path.mkdir(parents=True, exist_ok=True)

    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "TMPDIR": str(tmp),
        "XDG_CONFIG_HOME": str(xdg / "config"),
        "XDG_CACHE_HOME": str(xdg / "cache"),
        "XDG_DATA_HOME": str(xdg / "data"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "NO_COLOR": "1",
        "CI": "1",
    }
    if runtime == "claude":
        claude_home = root / "claude"
        claude_home.mkdir(parents=True)
        env["CLAUDE_CONFIG_DIR"] = str(claude_home)
    elif runtime == "codex":
        codex_home = root / "codex"
        codex_home.mkdir(parents=True)
        env["CODEX_HOME"] = str(codex_home)
    return env


def run_cli(command: list[str], *, env: dict[str, str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run one non-interactive loader command with bounded, diagnostic failure."""
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    if completed.returncode != 0:
        rendered = " ".join(command[:4])
        raise AssertionError(
            f"loader command failed ({completed.returncode}): {rendered}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def frontmatter_name(text: str) -> str | None:
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        return None
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("\"'")
    return None


def packaged_files(directory: Path) -> set[str]:
    return {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


class FreshInstallLoaderE2E(unittest.TestCase):
    """Loader/package E2E 7x2; intentionally not a command/model invocation test."""

    maxDiff = None

    def loader(self, name: str) -> str:
        executable = shutil.which(name)
        if executable:
            return executable
        reason = f"{name} plugin loader is not installed"
        if REQUIRE_LOADERS:
            self.fail(f"{reason}; MNEMO_REQUIRE_RUNTIME_LOADERS=1")
        self.skipTest(reason)

    def installed_root(self, runtime_home: Path, manifest: str, namespace: str) -> Path:
        cache_root = runtime_home / "plugins/cache"
        candidates: list[Path] = []
        if cache_root.is_dir():
            for manifest_path in cache_root.rglob(manifest):
                try:
                    metadata = json.loads(manifest_path.read_text())
                except (OSError, json.JSONDecodeError):
                    continue
                plugin_root = manifest_path.parent.parent
                if metadata.get("name") == namespace and (plugin_root / "skills").is_dir():
                    candidates.append(plugin_root.resolve())
        unique = sorted(set(candidates))
        self.assertEqual(
            len(unique),
            1,
            f"expected exactly one installed {namespace} cache under {cache_root}, got {unique}",
        )
        return unique[0]

    def assert_package_contract(self, plugin_root: Path, *, runtime: str) -> None:
        skills_root = plugin_root / "skills"
        actual_skill_dirs = {path.name for path in skills_root.iterdir() if path.is_dir()}
        self.assertEqual(actual_skill_dirs, CANONICAL_SKILLS)
        self.assertTrue(actual_skill_dirs.isdisjoint(LEGACY_SKILL_DIRS))
        self.assertFalse((plugin_root / "commands").exists())

        skill_bodies = list(skills_root.rglob("SKILL.md"))
        self.assertEqual(len(skill_bodies), 7)
        for name in sorted(CANONICAL_SKILLS):
            skill_dir = skills_root / name
            bodies = list(skill_dir.rglob("SKILL.md"))
            self.assertEqual(len(bodies), 1, f"{runtime}:{name} must have one SKILL body")
            body = bodies[0].read_text()
            self.assertEqual(frontmatter_name(body), name)
            marker = f"🧠 mn:{name} (mnemo) → running"
            self.assertEqual(body.count(marker), 1, f"{runtime}:{name} invocation marker")

            openai_yaml = skill_dir / "agents/openai.yaml"
            self.assertTrue(openai_yaml.is_file(), f"{runtime}:{name} openai UI metadata")
            interface = openai_yaml.read_text()
            self.assertRegex(interface, rf'(?m)^  display_name: "mn:{re.escape(name)}"$')
            self.assertIn(f"$mnemo:{name}", interface)

        for bundled_dir in ("scripts", "assets", "references", "hooks"):
            source_files = packaged_files(PLUGIN_SOURCE / bundled_dir)
            installed_files = packaged_files(plugin_root / bundled_dir)
            self.assertTrue(source_files, f"source {bundled_dir}/ must not be empty")
            self.assertTrue(
                source_files <= installed_files,
                f"{runtime} install omitted {bundled_dir}: {sorted(source_files - installed_files)}",
            )

    def assert_helper_smoke(self, plugin_root: Path, root: Path) -> None:
        smoke_cwd = root / "empty-project"
        smoke_cwd.mkdir()
        env = isolated_env(root / "helper", runtime=None)
        completed = run_cli(
            [shutil.which("python3") or "python3", str(plugin_root / "scripts/session-scan.py")],
            env=env,
            cwd=smoke_cwd,
        )
        self.assertIn("SESSION_ID: not available", completed.stdout)
        self.assertNotIn("JSONL:", completed.stdout)

    def test_claude_fresh_install_package_7x2(self) -> None:
        claude = self.loader("claude")
        with tempfile.TemporaryDirectory(prefix="mnemo-fresh-claude-") as temporary:
            root = Path(temporary)
            env = isolated_env(root, runtime="claude")
            run_cli(
                [claude, "plugin", "marketplace", "add", str(REPO_ROOT)],
                env=env,
                cwd=REPO_ROOT,
            )
            run_cli(
                [claude, "plugin", "install", "mnemo@mnemo", "--scope", "user"],
                env=env,
                cwd=REPO_ROOT,
            )
            installed = run_cli(
                [claude, "plugin", "list"],
                env=env,
                cwd=REPO_ROOT,
            )
            self.assertIn("mnemo@mnemo", installed.stdout)
            self.assertIn("Status: ✔ enabled", installed.stdout)
            details = run_cli(
                [claude, "plugin", "details", "mnemo@mnemo"],
                env=env,
                cwd=REPO_ROOT,
            )
            self.assertRegex(details.stdout, r"(?m)^mnemo \(mn\) \S+$")
            inventory = re.search(r"(?m)^  Skills \(7\)  (.+)$", details.stdout)
            self.assertIsNotNone(inventory, "Claude loader did not expose exactly seven skills")
            assert inventory is not None
            self.assertEqual(set(inventory.group(1).split(", ")), CANONICAL_SKILLS)
            plugin_root = self.installed_root(root / "claude", ".claude-plugin/plugin.json", "mn")
            self.assertNotEqual(plugin_root, PLUGIN_SOURCE.resolve())
            self.assert_package_contract(plugin_root, runtime="claude")
            self.assert_helper_smoke(plugin_root, root)

    def test_codex_fresh_install_package_7x2(self) -> None:
        codex = self.loader("codex")
        with tempfile.TemporaryDirectory(prefix="mnemo-fresh-codex-") as temporary:
            root = Path(temporary)
            env = isolated_env(root, runtime="codex")
            marketplace = run_cli(
                [codex, "plugin", "marketplace", "add", str(REPO_ROOT), "--json"],
                env=env,
                cwd=REPO_ROOT,
            )
            marketplace_result = json.loads(marketplace.stdout)
            self.assertEqual(marketplace_result["marketplaceName"], "mnemo")
            self.assertEqual(Path(marketplace_result["installedRoot"]).resolve(), REPO_ROOT)
            installed = run_cli(
                [codex, "plugin", "add", "mnemo@mnemo", "--json"],
                env=env,
                cwd=REPO_ROOT,
            )
            install_result = json.loads(installed.stdout)
            self.assertEqual(install_result["pluginId"], "mnemo@mnemo")
            self.assertEqual(install_result["name"], "mnemo")
            self.assertEqual(install_result["marketplaceName"], "mnemo")
            plugin_root = self.installed_root(root / "codex", ".codex-plugin/plugin.json", "mnemo")
            self.assertEqual(Path(install_result["installedPath"]).resolve(), plugin_root)
            self.assertNotEqual(plugin_root, PLUGIN_SOURCE.resolve())
            listed = run_cli(
                [codex, "plugin", "list", "--json"],
                env=env,
                cwd=REPO_ROOT,
            )
            installed_plugins = json.loads(listed.stdout)["installed"]
            self.assertEqual(len(installed_plugins), 1)
            self.assertEqual(installed_plugins[0]["pluginId"], "mnemo@mnemo")
            self.assertIs(installed_plugins[0]["installed"], True)
            self.assertIs(installed_plugins[0]["enabled"], True)
            self.assert_package_contract(plugin_root, runtime="codex")
            self.assert_helper_smoke(plugin_root, root)


def selected_suite(runtime: str) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    if runtime == "all":
        return loader.loadTestsFromTestCase(FreshInstallLoaderE2E)
    method = f"test_{runtime}_fresh_install_package_7x2"
    return unittest.TestSuite([FreshInstallLoaderE2E(method)])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime",
        choices=("all", "claude", "codex"),
        default="all",
        help="run both loaders or one isolated runtime loader",
    )
    arguments = parser.parse_args()
    outcome = unittest.TextTestRunner(verbosity=2).run(selected_suite(arguments.runtime))
    raise SystemExit(0 if outcome.wasSuccessful() else 1)

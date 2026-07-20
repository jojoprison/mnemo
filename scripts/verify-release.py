#!/usr/bin/env python3
"""Verify that mnemo's release metadata has one coherent version."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MANIFEST = Path("plugins/mnemo/.claude-plugin/plugin.json")
CODEX_MANIFEST = Path("plugins/mnemo/.codex-plugin/plugin.json")
MARKETPLACE_MANIFEST = Path(".claude-plugin/marketplace.json")
CHANGELOG = Path("CHANGELOG.md")
SEMVER_RE = re.compile(
    r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


class ContractError(ValueError):
    """A release artifact disagrees with the release contract."""


def load_json(relative_path: Path) -> dict:
    path = REPO_ROOT / relative_path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot read {relative_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"{relative_path} must contain a JSON object")
    return data


def manifest_versions() -> tuple[dict[str, object], dict]:
    claude = load_json(CLAUDE_MANIFEST)
    codex = load_json(CODEX_MANIFEST)
    marketplace = load_json(MARKETPLACE_MANIFEST)

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        raise ContractError(f"{MARKETPLACE_MANIFEST}: plugins must be a list")
    entries = [entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == "mnemo"]
    if len(entries) != 1:
        raise ContractError(
            f"{MARKETPLACE_MANIFEST}: expected exactly one mnemo plugin, found {len(entries)}"
        )

    versions = {
        str(CLAUDE_MANIFEST): claude.get("version"),
        str(CODEX_MANIFEST): codex.get("version"),
        str(MARKETPLACE_MANIFEST): entries[0].get("version"),
    }
    return versions, claude


def one_reference_link(changelog: str, label: str) -> str:
    pattern = re.compile(rf"(?m)^\[{re.escape(label)}\]:\s+(\S+)\s*$")
    matches = pattern.findall(changelog)
    if len(matches) != 1:
        raise ContractError(
            f"{CHANGELOG}: expected exactly one [{label}] compare-link, found {len(matches)}"
        )
    return matches[0]


def verify_changelog(expected: str, repository: str) -> None:
    path = REPO_ROOT / CHANGELOG
    try:
        changelog = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractError(f"cannot read {CHANGELOG}: {exc}") from exc

    heading_re = re.compile(r"(?m)^## \[([^]]+)](?: - (\d{4}-\d{2}-\d{2}))?\s*$")
    headings = list(heading_re.finditer(changelog))
    target = [match for match in headings if match.group(1) == expected]
    if len(target) != 1 or target[0].group(2) is None:
        raise ContractError(f"{CHANGELOG}: expected exactly one dated [{expected}] section")
    try:
        date.fromisoformat(target[0].group(2))
    except ValueError as exc:
        raise ContractError(
            f"{CHANGELOG}: [{expected}] has invalid date {target[0].group(2)!r}"
        ) from exc

    release_headings = [match.group(1) for match in headings if match.group(1) != "Unreleased"]
    target_index = release_headings.index(expected)
    previous = release_headings[target_index + 1] if target_index + 1 < len(release_headings) else None

    repository = repository.rstrip("/")
    expected_unreleased = f"{repository}/compare/v{expected}...HEAD"
    actual_unreleased = one_reference_link(changelog, "Unreleased")
    if actual_unreleased != expected_unreleased:
        raise ContractError(
            f"{CHANGELOG}: [Unreleased] must be {expected_unreleased}, got {actual_unreleased}"
        )

    expected_release = (
        f"{repository}/compare/v{previous}...v{expected}"
        if previous
        else f"{repository}/releases/tag/v{expected}"
    )
    actual_release = one_reference_link(changelog, expected)
    if actual_release != expected_release:
        raise ContractError(
            f"{CHANGELOG}: [{expected}] must be {expected_release}, got {actual_release}"
        )


def verify_release(requested_version: str | None) -> str:
    versions, claude_manifest = manifest_versions()
    expected = (requested_version or str(versions[str(CLAUDE_MANIFEST)])).removeprefix("v")
    if not SEMVER_RE.fullmatch(expected):
        raise ContractError(f"invalid release version: {expected!r}")

    mismatches = {path: version for path, version in versions.items() if version != expected}
    if mismatches:
        rendered = ", ".join(f"{path}={version!r}" for path, version in mismatches.items())
        raise ContractError(f"v{expected} disagrees with manifests: {rendered}")

    repository = claude_manifest.get("repository")
    if not isinstance(repository, str) or not repository.startswith("https://"):
        raise ContractError(f"{CLAUDE_MANIFEST}: repository must be an https URL")
    verify_changelog(expected, repository)
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", help="expected version, with optional leading v")
    args = parser.parse_args()
    try:
        version = verify_release(args.version)
    except ContractError as exc:
        parser.exit(1, f"release contract failed: {exc}\n")
    print(f"release contract verified for v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Static regressions for dual-runtime write routing in canonical skills."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS = REPO_ROOT / "plugins/mnemo/skills"
ROLE_KEYS = {"fact", "insight", "source", "session", "moc"}


def skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text()


class BundledVaultWriterContractTests(unittest.TestCase):
    def test_every_vault_writing_skill_has_the_same_bundled_fallback(self) -> None:
        for name in ("save", "session", "setup", "connect", "health"):
            with self.subTest(skill=name):
                body = skill(name)
                self.assertIn("scripts/vault-write.py", body)
                self.assertIn("JSON", body)

    def test_codex_generated_memory_is_never_a_manual_write_target(self) -> None:
        save = skill("save")
        session = skill("session")

        for body in (save, session):
            self.assertIn("generated state", body)
            self.assertIn("CODEX_HOME", body)
        self.assertIn("read-only", save)
        self.assertNotIn("write the filled summary to the local fallback memory", session)
        self.assertNotIn("~/.codex/memories/session-", session)

    def test_claude_rules_routing_stays_intact_while_item_four_is_deferred(self) -> None:
        save = skill("save")
        design = (REPO_ROOT / "docs/design-decisions.md").read_text()

        self.assertIn("### Step 3.5: `.claude/rules/`", save)
        self.assertIn("**Codex / AGENTS.md gotcha:**", save)
        self.assertIn("**Codex caveat acknowledged, not solved here.**", design)
        deferred = save[save.index("### Step 3.5:") : save.index("### Step 4:")]
        self.assertEqual(
            hashlib.sha256(deferred.encode()).hexdigest(),
            "990081f71679bd0a6f2dfee6124de99ac7c30bb15a0e930657322c0567ccbeb5",
        )

    def test_taxonomy_roles_are_end_to_end_and_templates_are_runtime_neutral(self) -> None:
        ask = skill("ask")
        session = skill("session")
        connect = skill("connect")
        template = (REPO_ROOT / "plugins/mnemo/assets/session-template.md").read_text()

        self.assertIn("role: insight", ask)
        self.assertNotIn("type: molecule", ask)
        self.assertNotIn("config `taxonomy.molecule`", ask)
        self.assertIn("taxonomy_roles", session)
        self.assertIn("taxonomy_roles", connect)
        for placeholder in (
            "{session_type}",
            "{session_tag}",
            "{session_id}",
            "{mapped_moc_note}",
        ):
            self.assertIn(placeholder, template)
        self.assertNotIn("{CLAUDE_SESSION_ID}", template)
        self.assertNotIn("[[MOC —", template)

    def test_every_taxonomy_consumer_requires_the_exact_role_contract(self) -> None:
        for name in ("ask", "save", "session", "connect", "setup", "health"):
            with self.subTest(skill=name):
                body = skill(name)
                self.assertIn("taxonomy_roles", body)
                for role in ROLE_KEYS:
                    self.assertIn(f"`{role}`", body)
                self.assertIn("session → session", body)
                self.assertIn("moc → moc", body)

    def test_default_config_has_exact_roles_and_functional_self_maps(self) -> None:
        config = json.loads((REPO_ROOT / "config.example.json").read_text())
        roles = config["taxonomy_roles"]

        self.assertEqual(set(roles), ROLE_KEYS)
        self.assertTrue(set(roles.values()) <= set(config["taxonomy"]))
        self.assertEqual(roles["session"], "session")
        self.assertEqual(roles["moc"], "moc")


class ReviewFullContractTests(unittest.TestCase):
    """Pin the v1.2.8 `review --full` one-command close-out invariants."""

    def test_full_flag_mode_and_new_phases_present(self) -> None:
        review = skill("review")
        self.assertIn("Detect `--full`", review)
        self.assertIn("FULL mode", review)
        self.assertIn("Session Origin Anchor", review)
        self.assertIn("Step 9: Full Pass — Execute Chain + Verify", review)

    def test_full_is_consent_not_the_killed_implicit_autorun(self) -> None:
        review = skill("review")
        # v0.16.0 no-implicit-autorun stays intact on the DEFAULT path.
        self.assertIn("No auto-run", review)
        # --full is explicit consent, explicitly distinguished from the killed autorun.
        self.assertIn("implicit autorun removed in v0.16.0", review)
        self.assertIn("consent, not autorun", review)

    def test_chain_order_excludes_health_and_injects_depth_contract(self) -> None:
        review = skill("review")
        self.assertIn("references/depth-contract.md", review)
        self.assertIn("**excluded**", review)  # health never auto-chained
        # Chain runs save -> session -> connect in that order.
        s, se, c = (review.index(f"**{x}**") for x in ("save", "session", "connect"))
        self.assertLess(s, se)
        self.assertLess(se, c)

    def test_verify_is_grounded_binary_and_never_links(self) -> None:
        review = skill("review")
        self.assertIn("**binary**", review)          # non-orphan check, not link count
        self.assertIn("never add a link here", review)
        self.assertIn("memory-not-CI", review)        # prod/e2e reported, never run

    def test_depth_contract_routes_mental_model_to_save_not_narrative(self) -> None:
        contract = (REPO_ROOT / "plugins/mnemo/references/depth-contract.md").read_text()
        self.assertIn("one kind → one home", contract)
        self.assertIn("not** the session narrative", contract)
        self.assertIn("auto-ingest fork", contract)

    def test_session_carries_depth_routing_and_own_note_check(self) -> None:
        session = skill("session")
        self.assertIn("references/depth-contract.md", session)
        self.assertIn("own-note self-check", session)
        self.assertIn("Own-note self-check only", session)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Regression contracts for Cygnus fifth-job completion across rebirths."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CHARACTER = ROOT / "gms-server/src/main/java/org/gms/client/Character.java"
LOGIN_HANDLER = (
    ROOT
    / "gms-server/src/main/java/org/gms/net/server/channel/handlers/PlayerLoggedinHandler.java"
)


class CygnusFifthJobRebirthContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.character = CHARACTER.read_text(encoding="utf-8")
        cls.login_handler = LOGIN_HANDLER.read_text(encoding="utf-8")

    def test_completion_uses_a_permanent_character_marker(self) -> None:
        self.assertIn(
            'CYGNUS_FIFTH_JOB_COMPLETED_KEY = "cygnus_fifth_job_completed"',
            self.character,
        )
        self.assertIn("ExtendType.CHARACTER_EXTEND.getType()", self.character)
        self.assertIn("public boolean hasCompletedCygnusFifthJob()", self.character)
        self.assertIn("private void markCygnusFifthJobCompleted()", self.character)

    def test_all_fifth_jobs_fall_back_to_their_third_job(self) -> None:
        expected = {
            "DAWNWARRIOR4": "DAWNWARRIOR3",
            "BLAZEWIZARD4": "BLAZEWIZARD3",
            "WINDARCHER4": "WINDARCHER3",
            "NIGHTWALKER4": "NIGHTWALKER3",
            "THUNDERBREAKER4": "THUNDERBREAKER3",
        }
        for fifth_job, third_job in expected.items():
            self.assertIn(
                f"case {fifth_job} -> Job.{third_job};",
                self.character,
            )

    def test_rebirth_does_not_auto_advance_a_first_time_character(self) -> None:
        start = self.character.index("public void changeJobAndLevel(")
        end = self.character.index("private void resetSkillsAndResetSP(", start)
        method = self.character[start:end]

        self.assertIn(
            "boolean completedCygnusFifthJob = hasCompletedCygnusFifthJob();",
            method,
        )
        self.assertIn(
            "if (!completedCygnusFifthJob && isCygnusFifthJob(nextJob))",
            method,
        )
        self.assertIn("nextJob = getCygnusThirdJob(nextJob);", method)
        self.assertIn(
            "nextJob = Job.changeJobByLevel(getJob(), level);\n"
            "        }\n"
            "        if (!completedCygnusFifthJob",
            method,
        )

    def test_normal_fifth_job_transition_records_completion_before_mastery(self) -> None:
        start = self.character.index("public synchronized void changeJob(")
        end = self.character.index("public void broadcastAcquaintances(", start)
        method = self.character[start:end]

        self.assertIn(
            "boolean wasCygnusFifthJob = isCygnusFifthJob(job);",
            method,
        )
        self.assertIn(
            "if (wasCygnusFifthJob || isCygnusFifthJob(newJob))",
            method,
        )
        self.assertLess(
            method.index("markCygnusFifthJobCompleted();"),
            method.index("setMasteries(this.job.getId());"),
        )

    def test_mastery_and_login_grants_require_completion(self) -> None:
        masteries_start = self.character.index("public void setMasteries(")
        masteries_end = self.character.index("private void broadcastChangeJob", masteries_start)
        masteries = self.character[masteries_start:masteries_end]
        self.assertGreaterEqual(masteries.count("hasCompletedCygnusFifthJob()"), 4)

        grant_methods = (
            "grantDawnWarriorVViAttacks",
            "grantBlazeWizardVViAttacks",
            "grantNightWalkerVViSkills",
            "grantWindArcherVViAttacks",
            "grantThunderBreakerVViAttacks",
        )
        for index, method_name in enumerate(grant_methods):
            start = self.login_handler.index(f"private static void {method_name}(")
            if index + 1 < len(grant_methods):
                end = self.login_handler.index(
                    f"private static void {grant_methods[index + 1]}(", start
                )
            else:
                end = len(self.login_handler)
            method = self.login_handler[start:end]
            self.assertIn("!player.hasCompletedCygnusFifthJob()", method, method_name)


if __name__ == "__main__":
    unittest.main()

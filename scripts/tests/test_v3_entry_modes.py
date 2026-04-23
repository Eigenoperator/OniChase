#!/usr/bin/env python3

from __future__ import annotations

import unittest

from scripts.tests.v3_browser_test_utils import run_v3_probe


class V3EntryModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_v3_probe("entry-modes")

    def test_entry_offers_quick_tutorial_and_advanced_modes(self) -> None:
        initial = self.result["initial"]
        self.assertIn("Quick Play", initial["quickText"])
        self.assertIn("Tutorial", initial["tutorialText"])
        self.assertIn("Advanced Setup", initial["advancedText"])
        self.assertTrue(initial["advancedHidden"])
        self.assertTrue(initial["singleRunnerHidden"])

    def test_advanced_setup_reveals_existing_single_and_multiplayer_controls(self) -> None:
        advanced = self.result["advanced"]
        self.assertFalse(advanced["hidden"])
        self.assertEqual(advanced["expanded"], "true")
        self.assertEqual(advanced["singleRunnerText"], "Play Runner")
        self.assertEqual(advanced["createRoomText"], "Create Room")

    def test_tutorial_enters_guided_runner_planning(self) -> None:
        tutorial = self.result["tutorial"]
        self.assertTrue(tutorial["entryHidden"])
        self.assertFalse(tutorial["guideHidden"])
        self.assertEqual(tutorial["activeMode"], "runner")
        self.assertEqual(tutorial["startTime"], "06:00")
        self.assertEqual(tutorial["endTime"], "08:00")
        self.assertIn("Line", tutorial["guideText"])
        self.assertIn("Train", tutorial["guideText"])
        self.assertIn("Alight", tutorial["guideText"])
        self.assertIn("Through-service", tutorial["guideText"])

    def test_quick_play_generates_short_game_starter_plans(self) -> None:
        quick = self.result["quick"]
        self.assertTrue(quick["entryHidden"])
        self.assertEqual(quick["activeMode"], "runner")
        self.assertEqual(quick["startTime"], "06:00")
        self.assertEqual(quick["endTime"], "08:00")
        self.assertTrue(quick["clockRunning"])
        self.assertLessEqual(quick["planningSecondsRemaining"], 30)
        self.assertGreaterEqual(quick["runnerStepCount"], 2)
        self.assertGreaterEqual(quick["hunterStepCount"], 2)
        self.assertIn("東京", quick["runnerStart"])
        self.assertIn("新宿", quick["hunterStart"])
        self.assertNotIn("No plan yet", quick["planText"])


if __name__ == "__main__":
    unittest.main()

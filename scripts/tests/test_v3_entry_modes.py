#!/usr/bin/env python3

from __future__ import annotations

import unittest

from scripts.tests.v3_browser_test_utils import run_v3_probe


class V3EntryModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_v3_probe("entry-modes")

    def test_entry_offers_tutorial_and_advanced_modes_only(self) -> None:
        initial = self.result["initial"]
        self.assertFalse(initial["quickButtonExists"])
        self.assertFalse(initial["bodyHasQuickPlay"])
        self.assertEqual(initial["entryChoiceCount"], 2)
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
        self.assertIn("Valid Plan", tutorial["guideText"])
        self.assertIn("DEMONSTRATIONS", tutorial["guideText"])
        self.assertIn("Demo A", tutorial["guideText"])
        self.assertIn("東京", tutorial["guideText"])
        self.assertIn("山手線", tutorial["guideText"])
        self.assertIn("渋谷", tutorial["guideText"])
        self.assertIn("Demo B", tutorial["guideText"])
        self.assertIn("池袋", tutorial["guideText"])
        self.assertIn("副都心線", tutorial["guideText"])
        self.assertIn("東急東横線", tutorial["guideText"])
        self.assertIn("Through-service", tutorial["guideText"])
        self.assertIn("same_node", tutorial["guideText"])
        self.assertIn("same_train", tutorial["guideText"])


if __name__ == "__main__":
    unittest.main()

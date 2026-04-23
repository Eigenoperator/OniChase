#!/usr/bin/env python3

from __future__ import annotations

import unittest

from scripts.tests.v3_browser_test_utils import run_v3_probe


class V3ReplayUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_v3_probe("replay-core")

    def test_replay_panel_is_visible_and_uses_canonical_record(self) -> None:
        initial = self.result["initial"]
        self.assertTrue(initial["resultSectionHidden"])
        self.assertFalse(initial["visibleTextHasEmptyCopy"])
        self.assertEqual(initial["resultCardText"], "")
        self.assertEqual(initial["replayListText"], "")
        self.assertEqual(initial["replaySummaryText"], "")
        self.assertFalse(self.result["resultSectionHidden"])
        self.assertFalse(self.result["toolbarReplayHidden"])
        self.assertEqual(self.result["schemaVersion"], "v3.replay.1")
        self.assertEqual(self.result["datasetName"], "v3-tokyo")
        self.assertTrue(self.result["gameRulesVersion"])
        self.assertEqual(self.result["sourceKind"], "v3_browser_local")
        self.assertEqual(self.result["sharePayloadPrefix"], "j1.")

    def test_replay_preserves_capture_and_event_context(self) -> None:
        self.assertEqual(self.result["captureType"], "same_node")
        self.assertEqual(self.result["captureCheckType"], "same_node")
        self.assertEqual(self.result["decodedCaptureType"], "same_node")
        self.assertGreaterEqual(self.result["eventCount"], 2)
        self.assertGreaterEqual(self.result["phaseEventCount"], 1)
        self.assertEqual(self.result["replayRowCount"], self.result["eventCount"])
        self.assertEqual(self.result["selectedEventType"], "CAPTURE")

    def test_replay_summary_answers_core_questions(self) -> None:
        summary = self.result["summaryText"]
        self.assertIn("RUNNER", summary)
        self.assertIn("HUNTER", summary)
        self.assertIn("CAPTURE", summary)
        self.assertIn("東京", summary)
        self.assertIn("same_node", summary)
        self.assertIn("Hunter closed the gap", summary)
        self.assertIn("Capture: same_node", self.result["resultText"])


if __name__ == "__main__":
    unittest.main()

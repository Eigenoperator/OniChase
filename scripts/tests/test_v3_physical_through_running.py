#!/usr/bin/env python3

from __future__ import annotations

import unittest

from scripts.tests.v3_browser_test_utils import run_v3_probe


class V3PhysicalThroughRunningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_v3_probe("physical-through-running")

    def test_fukutoshin_departures_do_not_borrow_saikyo_kawagoe(self) -> None:
        self.assertEqual(self.result["fukutoshinBadRows"], [])

    def test_shinkansen_and_ordinary_lines_do_not_merge(self) -> None:
        shinkansen = self.result["shinkansen"]
        self.assertGreater(shinkansen["ordinaryRowCount"], 0)
        self.assertGreater(shinkansen["shinkansenRowCount"], 0)
        self.assertTrue(shinkansen["hasTohokuShinkansenRoute"])
        self.assertEqual(shinkansen["ordinaryWithShinkansen"], [])
        self.assertEqual(shinkansen["shinkansenWithOrdinary"], [])
        self.assertEqual(shinkansen["tokaidoWithOtherShinkansen"], [])

    def test_parallel_ordinary_lines_do_not_merge_into_yamanote(self) -> None:
        self.assertEqual(self.result["yamanoteWithParallelOrdinary"], [])

    def test_boundary_segments_choose_physical_running_line(self) -> None:
        for item in self.result["boundarySegments"]:
            with self.subTest(pair=f"{item['fromName']}->{item['toName']}"):
                self.assertGreater(len(item["matches"]), 0)
                for match in item["matches"]:
                    self.assertEqual(match["chosenRoute"], item["expectedRoute"], match)

    def test_transfer_equivalence_and_same_train_capture_stay_strict(self) -> None:
        self.assertIsNotNone(self.result["equivalentStationPair"])
        self.assertIsNone(self.result["equivalentStationCapture"])
        self.assertIsNone(self.result["sameTrainCapture"])


if __name__ == "__main__":
    unittest.main()

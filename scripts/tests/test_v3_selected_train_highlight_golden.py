#!/usr/bin/env python3

from __future__ import annotations

import unittest

from scripts.tests.v3_browser_test_utils import run_v3_probe


class V3SelectedTrainHighlightGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_v3_probe("selected-train-highlight")

    def test_ikebukuro_fukutoshin_through_service_highlights_future_physical_routes(self) -> None:
        fukutoshin = self.result["fukutoshin"]
        self.assertEqual(fukutoshin["departure"], "17:01")
        self.assertEqual(fukutoshin["startSequence"], 7)
        self.assertEqual(fukutoshin["selectedStopCount"], 14)
        self.assertEqual(fukutoshin["path"]["count"], 13)
        self.assertEqual(
            fukutoshin["path"]["byRoute"],
            {
                "副都心線": 3,
                "東急東横線": 6,
                "横浜高速鉄道みなとみらい21線": 4,
            },
        )
        self.assertTrue(fukutoshin["broadRouteHidden"])
        self.assertTrue(fukutoshin["routeStopHaloHidden"])
        self.assertEqual(fukutoshin["badDepartureRows"], [])

    def test_tokyo_yamanote_highlight_stays_on_whole_future_loop(self) -> None:
        yamanote = self.result["yamanote"]
        self.assertEqual(yamanote["uniqueRoutes"], ["山手線"])
        self.assertEqual(yamanote["selectedStopCount"], 54)
        self.assertEqual(yamanote["featureCount"], 53)
        self.assertEqual(yamanote["segmentCount"], 53)
        self.assertFalse(yamanote["builtGlobalGraph"])
        self.assertLess(yamanote["setSelectedTripMs"], 1000)
        self.assertLess(yamanote["tripPathMs"], 500)


if __name__ == "__main__":
    unittest.main()

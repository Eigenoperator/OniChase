#!/usr/bin/env python3

from __future__ import annotations

import unittest

from scripts.tests.v3_browser_test_utils import ROOT, run_v3_probe


class V3AxiomTests(unittest.TestCase):
    def test_axioms_record_physical_through_running_rules(self) -> None:
        source = (ROOT / "AXIOMS.md").read_text(encoding="utf-8")
        required_lines = [
            "Shinkansen services are never merged by broad JR family, shared station, or shared corridor.",
            "Different named Shinkansen routes must remain separately classified by their own Shinkansen route name.",
            "Non-Shinkansen through-running exists only when trains actually run on the same physical track and stop at the same platform/boarding face.",
            "Shared operators, shared station groups, transfer permission, nearby geometry, or parallel corridors do not by themselves make two lines through-running equivalents.",
            "Ordinary lines such as Tokaido Line, Yokosuka Line, Yamanote Line, and Keihin-Tohoku Line must remain separate categories",
        ]
        for line in required_lines:
            with self.subTest(line=line):
                self.assertIn(line, source)

    def test_public_and_local_v3_pages_stay_identical(self) -> None:
        public_page = (ROOT / "docs" / "v3.html").read_text(encoding="utf-8")
        local_page = (ROOT / "ui" / "v3_maplibre.html").read_text(encoding="utf-8")
        self.assertEqual(public_page, local_page)

    def test_tokyo_major_lines_remain_separate_in_route_choices(self) -> None:
        result = run_v3_probe("axioms")
        choices = set(result["tokyoRouteChoices"])
        for route_title in [
            "山手線",
            "京浜東北線・根岸線",
            "東海道線",
            "横須賀線",
            "東海道・山陽新幹線",
            "東北・北海道新幹線",
        ]:
            with self.subTest(route_title=route_title):
                self.assertIn(route_title, choices)
        self.assertEqual(result["metroNumberedTitles"], [])
        self.assertGreater(result["routeCount"], 100)
        self.assertGreater(result["stationGroupCount"], 1000)
        self.assertGreater(result["tripCount"], 40000)


if __name__ == "__main__":
    unittest.main()

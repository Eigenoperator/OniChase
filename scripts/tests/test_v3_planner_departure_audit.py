#!/usr/bin/env python3

from __future__ import annotations

import unittest

from scripts.ingest.audit_v3_planner_departures import FOCUS_OPERATORS, build_audit


class V3PlannerDepartureAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_audit()
        cls.summary = cls.report["summary"]
        cls.operator_reports = {
            item["operatorId"]: item
            for item in cls.report["operatorReports"]
        }

    def test_core_summary_shape(self) -> None:
        self.assertGreater(self.summary["station_group_count"], 1000)
        self.assertGreater(self.summary["route_count"], 100)
        self.assertGreater(self.summary["trip_count"], 40000)

    def test_same_operator_forbidden_borrowing_is_zero(self) -> None:
        self.assertEqual(self.summary["forbidden_same_operator_borrow_count"], 0)
        self.assertEqual(self.report["samples"]["forbiddenSameOperatorBorrow"], [])

    def test_no_boardable_trip_stop_disappears_from_planner(self) -> None:
        self.assertGreaterEqual(self.summary["unsurfaced_boardable_trip_stop_count"], len(self.report["samples"]["unsurfacedBoardableTripStops"]))
        self.assertGreater(self.summary["unsurfaced_boardable_trip_stop_count"], 0)

    def test_focus_operators_are_present(self) -> None:
        for operator_id in FOCUS_OPERATORS:
            with self.subTest(operator_id=operator_id):
                self.assertIn(operator_id, self.operator_reports)
                self.assertGreater(self.operator_reports[operator_id]["boardableDepartureCount"], 0)

    def test_keikyu_station_route_pairs_remain_boardable(self) -> None:
        self.assertEqual(self.operator_reports["keikyu"]["noBoardableStationRoutePairCount"], 0)


if __name__ == "__main__":
    unittest.main()

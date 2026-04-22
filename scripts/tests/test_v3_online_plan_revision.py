#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.engine import v2_online_room_server as room_server  # noqa: E402


class V3OnlinePlanRevisionTests(unittest.TestCase):
    def test_room_server_ignores_stale_plan_revision(self) -> None:
        registry = room_server.RoomRegistry()
        room = registry.create_room("06:00", "18:00")
        registry.join(room.room_id, "runner", "Runner")

        first_steps = [{"type": "WAIT_UNTIL", "until_hhmm": "06:05"}]
        room = registry.submit_plan(room.room_id, "runner", "SG_TOKYO", first_steps, plan_revision=2)
        self.assertEqual(room.players["runner"].steps, first_steps)
        self.assertEqual(room.players["runner"].plan_revision, 2)

        registry.set_ready(room.room_id, "runner", True)
        stale_steps = [{"type": "WAIT_UNTIL", "until_hhmm": "06:10"}]
        room = registry.submit_plan(room.room_id, "runner", "SG_SHINJUKU", stale_steps, plan_revision=1)
        self.assertEqual(room.players["runner"].steps, first_steps)
        self.assertEqual(room.players["runner"].start_station_id, "SG_TOKYO")
        self.assertEqual(room.players["runner"].plan_revision, 2)
        self.assertTrue(room.players["runner"].ready)

        newer_steps = [{"type": "WAIT_UNTIL", "until_hhmm": "06:15"}]
        room = registry.submit_plan(room.room_id, "runner", "SG_SHINJUKU", newer_steps, plan_revision=3)
        self.assertEqual(room.players["runner"].steps, newer_steps)
        self.assertEqual(room.players["runner"].start_station_id, "SG_SHINJUKU")
        self.assertEqual(room.players["runner"].plan_revision, 3)
        self.assertFalse(room.players["runner"].ready)

        payload = room_server.room_payload(room, "runner")
        self.assertEqual(payload["self"]["plan_revision"], 3)

    def test_v3_clients_guard_against_stale_plan_responses(self) -> None:
        for relative_path in ("docs/v3.html", "ui/v3_maplibre.html"):
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIn("plan_revision: submitSeq", source)
                self.assertIn("if (submitSeq === state.online.planSubmitSeq)", source)
                self.assertIn("localPlanDirty = true", source)
                self.assertIn("preserveLocalPlan", source)
                self.assertIn("syncStateFromRoom(data.room, { acceptSelfPlan: true })", source)


if __name__ == "__main__":
    unittest.main()

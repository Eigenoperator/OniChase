#!/usr/bin/env python3

from __future__ import annotations

import unittest

from scripts.dev.normalize_v3_replay_record import DATASET_NAME, normalize_records, validate_collection
from scripts.tests.v3_browser_test_utils import ROOT


HEAVY_RECORDS = ROOT / "reports" / "v3_public_battle_records_20260422_161132.json"


class V3ReplayRecordSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import json

        cls.source_payload = json.loads(HEAVY_RECORDS.read_text(encoding="utf-8"))
        cls.collection = normalize_records(cls.source_payload, HEAVY_RECORDS)

    def test_heavy_public_records_normalize_to_canonical_replays(self) -> None:
        self.assertEqual(self.collection["schema_version"], "v3.replay.collection.1")
        self.assertEqual(len(self.collection["replays"]), 10)
        self.assertEqual(self.collection["completed_count"], 10)
        self.assertEqual(validate_collection(self.collection), [])

    def test_replay_records_have_required_game_context(self) -> None:
        replay = self.collection["replays"][0]
        self.assertEqual(replay["schema_version"], "v3.replay.1")
        self.assertEqual(replay["dataset_name"], DATASET_NAME)
        self.assertTrue(replay["dataset_id"])
        self.assertTrue(replay["game_rules_version"])
        self.assertEqual(replay["source"]["kind"], "v3_public_battle_record")
        self.assertEqual(set(replay["players"]), {"runner", "hunter"})
        self.assertEqual(set(replay["plans"]), {"runner", "hunter"})
        self.assertTrue(replay["initial_state"]["carriers"])
        self.assertGreaterEqual(len(replay["events"]), 2)

    def test_capture_expectations_are_preserved(self) -> None:
        by_index = {replay["scenario"]["index"]: replay for replay in self.collection["replays"]}
        self.assertEqual(by_index[1]["result"]["capture"]["type"], "same_node")
        self.assertEqual(by_index[1]["capture_checks"][-1]["capture_type"], "same_node")
        self.assertEqual(by_index[2]["result"]["capture"]["type"], "same_train")
        self.assertEqual(by_index[2]["capture_checks"][-1]["capture_type"], "same_train")
        self.assertIsNone(by_index[3]["result"]["capture"])
        self.assertEqual(by_index[3]["capture_checks"], [])


if __name__ == "__main__":
    unittest.main()

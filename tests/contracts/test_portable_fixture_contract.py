from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import pandas as pd


class PortableFixtureContractTest(unittest.TestCase):
    def test_fixture_hashes_and_scope(self) -> None:
        root = Path(__file__).resolve().parents[2]
        manifest_path = root / "tests/fixtures/fixture_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertFalse(manifest["production_use_allowed"])
        for item in manifest["files"]:
            path = root / item["relative_path"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
            self.assertEqual(digest, item["sha256"])
            self.assertEqual(path.stat().st_size, item["size_bytes"])

        master = pd.read_csv(
            root / "tests/fixtures/forecasting/regional_energy_master.csv"
        )
        self.assertEqual(len(master), 476)
        self.assertEqual(master["region_id"].nunique(), 34)
        self.assertEqual(sorted(master["year"].unique()), list(range(2011, 2025)))
        rows_2016 = master.loc[master["year"].eq(2016)]
        self.assertTrue(rows_2016["distributed_electricity_gwh"].isna().all())
        self.assertTrue(rows_2016["local_generation_gwh"].isna().all())


if __name__ == "__main__":
    unittest.main()

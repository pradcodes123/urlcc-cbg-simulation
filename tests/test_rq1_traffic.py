"""Tests for experiments/rq1_traffic.py (experiment driver)."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.simulation import (HIGH_URLLC_ARRIVAL_RATE,  # noqa: E402
                               LOW_URLLC_ARRIVAL_RATE,
                               MEDIUM_URLLC_ARRIVAL_RATE)
from experiments.rq1_traffic import (CSV_COLUMNS, run_rq1,  # noqa: E402
                                     save_rq1_results)

EXPECTED_RATES = {"low": LOW_URLLC_ARRIVAL_RATE,
                  "medium": MEDIUM_URLLC_ARRIVAL_RATE,
                  "high": HIGH_URLLC_ARRIVAL_RATE}


class TestRq1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.small = run_rq1(num_runs=2)
        cls.rows = run_rq1(num_runs=5)

    def test_two_runs_gives_six_rows_in_level_order(self):
        self.assertEqual(len(self.small), 6)
        self.assertEqual([r["traffic_level"] for r in self.small],
                         ["low", "low", "medium", "medium", "high", "high"])

    def test_three_levels_occur(self):
        self.assertEqual({r["traffic_level"] for r in self.rows}, set(EXPECTED_RATES))

    def test_arrival_rates_match_configuration(self):
        self.assertEqual(EXPECTED_RATES, {"low": 0.05, "medium": 0.20, "high": 0.50})
        for r in self.rows:
            self.assertEqual(r["arrival_rate"], EXPECTED_RATES[r["traffic_level"]])

    def test_each_level_has_num_runs_rows(self):
        for level in EXPECTED_RATES:
            with self.subTest(level=level):
                level_rows = [r for r in self.rows if r["traffic_level"] == level]
                self.assertEqual(len(level_rows), 5)
                self.assertEqual([r["run"] for r in level_rows], list(range(5)))

    def test_seeds_are_deterministic(self):
        self.assertEqual(run_rq1(num_runs=5), self.rows)
        self.assertEqual(run_rq1(num_runs=2, base_seed=10), run_rq1(num_runs=2, base_seed=10))
        shifted = run_rq1(num_runs=2, base_seed=10)
        self.assertEqual([r["seed"] for r in shifted if r["traffic_level"] == "low"], [10, 11])
        self.assertEqual([r["seed"] for r in self.rows if r["traffic_level"] == "high"],
                         [0, 1, 2, 3, 4])

    def test_rows_contain_all_fields(self):
        for r in self.rows:
            self.assertEqual(tuple(r), CSV_COLUMNS)

    def test_preemption_fraction_is_not_fixed(self):
        fractions = {r["preemption_fraction"] for r in self.rows}
        self.assertGreater(len(fractions), 1)
        by_level = {lvl: {r["preemption_fraction"] for r in self.rows
                          if r["traffic_level"] == lvl} for lvl in EXPECTED_RATES}
        self.assertTrue(any(len(v) > 1 for v in by_level.values()))
        for r in self.rows:  # amount equals preempted/total, derived from traffic
            self.assertAlmostEqual(r["preemption_fraction"],
                                   r["preempted_positions"] / r["total_embb_positions"])

    def test_csv_header_and_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rq1.csv"
            save_rq1_results(self.rows, str(path))
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        self.assertEqual(len(rows) - 1, len(self.rows))
        self.assertEqual(rows[1][1], "low")
        self.assertEqual(rows[-1][1], "high")

    def test_invalid_arguments_raise(self):
        for bad in (0, -1, 2.5, "5", None, True):
            with self.subTest(num_runs=bad):
                with self.assertRaises(ValueError):
                    run_rq1(num_runs=bad)
        for bad in (-1, 1.5, None, True):
            with self.subTest(base_seed=bad):
                with self.assertRaises(ValueError):
                    run_rq1(num_runs=1, base_seed=bad)


if __name__ == "__main__":
    unittest.main()
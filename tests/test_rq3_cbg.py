"""Tests for experiments/rq3_cbg.py (experiment driver).

These tests check the design (only cbg_count varies) and plumbing. They
deliberately do NOT assert which CBG configuration yields more affected CBGs,
failed CBGs or retransmission overhead.
"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE  # noqa: E402
from experiments.rq3_cbg import (  # noqa: E402
    CBG_COUNTS,
    CSV_COLUMNS,
    PREEMPTION_FRACTION,
    run_rq3,
    save_rq3_results,
)

expected_count = round(288 * PREEMPTION_FRACTION)
expected_fraction = expected_count / 288

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

class TestRq3(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.small = run_rq3(num_runs=2)
        cls.rows = run_rq3(num_runs=5)

    def by_cbg(self, cbg_count):
        return [r for r in self.rows if r["cbg_count"] == cbg_count]

    def test_two_runs_gives_six_rows_in_cbg_order(self):
        self.assertEqual(len(self.small), 6)
        self.assertEqual([r["cbg_count"] for r in self.small], [2, 2, 4, 4, 8, 8])

    def test_correct_cbg_configurations_occur(self):
        self.assertEqual(CBG_COUNTS, (2, 4, 8))
        self.assertEqual({r["cbg_count"] for r in self.rows}, {2, 4, 8})

    def test_each_configuration_has_num_runs_rows(self):
        for c in CBG_COUNTS:
            with self.subTest(cbg_count=c):
                rows = self.by_cbg(c)
                self.assertEqual(len(rows), 5)
                self.assertEqual([r["run"] for r in rows], list(range(5)))

    def test_rows_contain_exactly_csv_columns(self):
        for r in self.rows:
            self.assertEqual(tuple(r), CSV_COLUMNS)

    def test_same_arrival_rate_for_all_configurations(self):
        self.assertEqual({r["arrival_rate"] for r in self.rows}, {MEDIUM_URLLC_ARRIVAL_RATE})

    def test_same_preemption_fraction_for_all_configurations(self):
        fractions = {r["preemption_fraction"] for r in self.rows}
        self.assertEqual(len(fractions), 1)
        self.assertAlmostEqual(fractions.pop(), expected_fraction)

    def test_same_preempted_positions_per_run_across_configurations(self):
        for run in range(5):
            with self.subTest(run=run):
                counts = {self.by_cbg(c)[run]["preempted_positions"] for c in CBG_COUNTS}
                seeds = {self.by_cbg(c)[run]["seed"] for c in CBG_COUNTS}
                self.assertEqual(counts, {expected_count})
                self.assertEqual(seeds, {run})
        self.assertEqual({r["total_embb_positions"] for r in self.rows}, {288})

    def test_same_cb_exposure_per_run_across_configurations(self):
        # Random preemption depends only on the seed, so the affected CBs of run i
        # are identical for every CBG count (only the grouping differs).
        for run in range(5):
            with self.subTest(run=run):
                self.assertEqual(
                    len({self.by_cbg(c)[run]["affected_cb_count"] for c in CBG_COUNTS}), 1)

    def test_results_deterministic_for_same_base_seed(self):
        self.assertEqual(run_rq3(num_runs=5), self.rows)
        shifted = run_rq3(num_runs=2, base_seed=10)
        self.assertEqual(shifted, run_rq3(num_runs=2, base_seed=10))
        self.assertEqual([r["seed"] for r in shifted if r["cbg_count"] == 8], [10, 11])

    def test_csv_header_and_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rq3.csv"
            save_rq3_results(self.rows, str(path))
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        self.assertEqual(len(rows) - 1, len(self.rows))
        self.assertEqual(rows[1][1], "2")
        self.assertEqual(rows[-1][1], "8")

    def test_invalid_arguments_raise(self):
        for bad in (0, -1, 2.5, "5", None, True):
            with self.subTest(num_runs=bad):
                with self.assertRaises(ValueError):
                    run_rq3(num_runs=bad)
        for bad in (-1, 1.5, None, True):
            with self.subTest(base_seed=bad):
                with self.assertRaises(ValueError):
                    run_rq3(num_runs=1, base_seed=bad)


if __name__ == "__main__":
    unittest.main()
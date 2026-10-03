"""Tests for experiments/rq2_patterns.py (experiment driver).

These tests check the design (same amount, different pattern) and plumbing only.
They deliberately do NOT assert which pattern affects more CBs/CBGs.
"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE  # noqa: E402
from experiments.rq2_patterns import (  # noqa: E402
    CSV_COLUMNS,
    PATTERNS,
    PREEMPTION_FRACTION,
    run_rq2,
    save_rq2_results,
)

expected_count = round(288 * PREEMPTION_FRACTION)
expected_fraction = expected_count / 288


class TestRq2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.small = run_rq2(num_runs=2)
        cls.rows = run_rq2(num_runs=5)

    def by_pattern(self, pattern):
        return [r for r in self.rows if r["preemption_pattern"] == pattern]

    def test_two_runs_gives_six_rows_in_pattern_order(self):
        self.assertEqual(len(self.small), 6)
        self.assertEqual([r["preemption_pattern"] for r in self.small],
                         ["concentrated", "concentrated", "distributed",
                          "distributed", "random", "random"])

    def test_all_patterns_occur(self):
        self.assertEqual({r["preemption_pattern"] for r in self.rows},
                         {"concentrated", "distributed", "random"})
        self.assertEqual(PATTERNS, ("concentrated", "distributed", "random"))

    def test_each_pattern_has_num_runs_rows(self):
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                rows = self.by_pattern(pattern)
                self.assertEqual(len(rows), 5)
                self.assertEqual([r["run"] for r in rows], list(range(5)))

    def test_rows_contain_expected_fields(self):
        for r in self.rows:
            self.assertEqual(tuple(r), CSV_COLUMNS)

    def test_same_arrival_rate_for_all_patterns(self):
        self.assertEqual({r["arrival_rate"] for r in self.rows},
                         {MEDIUM_URLLC_ARRIVAL_RATE})

    def test_same_preemption_fraction_for_all_patterns(self):
        fractions = {r["preemption_fraction"] for r in self.rows}
        self.assertEqual(len(fractions), 1)
        self.assertAlmostEqual(fractions.pop(), expected_fraction)

    def test_preempted_positions_identical_across_patterns_per_run(self):
        for run in range(5):
            with self.subTest(run=run):
                counts = {self.by_pattern(p)[run]["preempted_positions"] for p in PATTERNS}
                seeds = {self.by_pattern(p)[run]["seed"] for p in PATTERNS}
                self.assertEqual(len(counts), 1)
                self.assertEqual(counts.pop(), expected_count)
                self.assertEqual(seeds, {run})

    def test_results_deterministic_for_same_base_seed(self):
        self.assertEqual(run_rq2(num_runs=5), self.rows)
        self.assertEqual(run_rq2(num_runs=2, base_seed=10), run_rq2(num_runs=2, base_seed=10))
        shifted = run_rq2(num_runs=2, base_seed=10)
        self.assertEqual([r["seed"] for r in shifted if r["preemption_pattern"] == "random"],
                         [10, 11])

    def test_csv_header_and_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rq2.csv"
            save_rq2_results(self.rows, str(path))
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        self.assertEqual(len(rows) - 1, len(self.rows))
        self.assertEqual(rows[1][1], "concentrated")
        self.assertEqual(rows[-1][1], "random")

    def test_invalid_arguments_raise(self):
        for bad in (0, -1, 2.5, "5", None, True):
            with self.subTest(num_runs=bad):
                with self.assertRaises(ValueError):
                    run_rq2(num_runs=bad)
        for bad in (-1, 1.5, None, True):
            with self.subTest(base_seed=bad):
                with self.assertRaises(ValueError):
                    run_rq2(num_runs=1, base_seed=bad)


if __name__ == "__main__":
    unittest.main()
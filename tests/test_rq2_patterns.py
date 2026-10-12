
"""Tests for experiments/rq2_patterns.py (experiment driver).

These tests check experiment design, reproducibility, and output plumbing.
They do not assume which preemption pattern causes the greatest damage.
"""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE  # noqa: E402
from experiments.rq2_patterns import (  # noqa: E402
    CONDITIONS,
    CONTROL,
    CSV_COLUMNS,
    PATTERNS,
    PREEMPTION_FRACTION,
    run_rq2,
    save_rq2_results,
)

TOTAL_POSITIONS = 288
EXPECTED_COUNT = round(TOTAL_POSITIONS * PREEMPTION_FRACTION)
EXPECTED_FRACTION = EXPECTED_COUNT / TOTAL_POSITIONS


class TestRq2(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.small = run_rq2(num_runs=2)
        cls.rows = run_rq2(num_runs=5)

    def by_condition(self, condition):
        return [
            r for r in self.rows
            if r["preemption_pattern"] == condition
        ]

    def test_two_runs_gives_eight_rows_in_condition_order(self):
        self.assertEqual(len(self.small), 8)
        self.assertEqual(
            [r["preemption_pattern"] for r in self.small],
            [
                CONTROL, CONTROL,
                "concentrated", "concentrated",
                "distributed", "distributed",
                "random", "random",
            ],
        )

    def test_control_and_all_patterns_occur(self):
        self.assertEqual(
            {r["preemption_pattern"] for r in self.rows},
            set(CONDITIONS),
        )
        self.assertEqual(
            PATTERNS,
            ("concentrated", "distributed", "random"),
        )

    def test_each_condition_has_num_runs_rows(self):
        for condition in CONDITIONS:
            with self.subTest(condition=condition):
                rows = self.by_condition(condition)
                self.assertEqual(len(rows), 5)
                self.assertEqual(
                    [r["run"] for r in rows],
                    list(range(5)),
                )

    def test_rows_contain_expected_fields(self):
        for r in self.rows:
            self.assertEqual(tuple(r), CSV_COLUMNS)

    def test_same_arrival_rate_for_all_conditions(self):
        self.assertEqual(
            {r["arrival_rate"] for r in self.rows},
            {MEDIUM_URLLC_ARRIVAL_RATE},
        )

    def test_pattern_preemption_fraction_is_fixed(self):
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                fractions = {
                    r["preemption_fraction"]
                    for r in self.by_condition(pattern)
                }
                self.assertEqual(len(fractions), 1)
                self.assertAlmostEqual(
                    fractions.pop(),
                    EXPECTED_FRACTION,
                )

    def test_preempted_positions_match_across_patterns_per_run(self):
        for run in range(5):
            with self.subTest(run=run):
                rows = {
                    pattern: self.by_condition(pattern)[run]
                    for pattern in PATTERNS
                }
                counts = {
                    row["preempted_positions"]
                    for row in rows.values()
                }
                seeds = {row["seed"] for row in rows.values()}

                self.assertEqual(len(counts), 1)
                self.assertEqual(counts.pop(), EXPECTED_COUNT)
                self.assertEqual(seeds, {run})

    def test_control_has_no_preemption_or_retransmission_cost(self):
        control_rows = self.by_condition(CONTROL)
        self.assertEqual(len(control_rows), 5)

        for row in control_rows:
            with self.subTest(seed=row["seed"]):
                self.assertEqual(row["preempted_positions"], 0)
                self.assertEqual(row["preemption_fraction"], 0.0)
                self.assertEqual(row["affected_cb_count"], 0)
                self.assertEqual(row["affected_cbg_count"], 0)
                self.assertEqual(row["retransmission_positions"], 0)
                self.assertEqual(row["failed_cbg_count"], 0)
                self.assertEqual(
                    row["final_delivery_success_rate"],
                    1.0,
                )

    def test_results_deterministic_for_same_base_seed(self):
        self.assertEqual(run_rq2(num_runs=5), self.rows)
        self.assertEqual(
            run_rq2(num_runs=2, base_seed=10),
            run_rq2(num_runs=2, base_seed=10),
        )

        shifted = run_rq2(num_runs=2, base_seed=10)
        self.assertEqual(
            [
                r["seed"] for r in shifted
                if r["preemption_pattern"] == CONTROL
            ],
            [10, 11],
        )
        self.assertEqual(
            [
                r["seed"] for r in shifted
                if r["preemption_pattern"] == "random"
            ],
            [10, 11],
        )

    def test_csv_header_and_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rq2.csv"
            save_rq2_results(self.rows, str(path))

            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        self.assertEqual(len(rows) - 1, len(self.rows))
        self.assertEqual(rows[1][1], CONTROL)
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

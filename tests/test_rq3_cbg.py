
"""Tests for experiments/rq3_cbg.py (experiment driver).

Tests verify experiment design, matched seeds, reproducibility, and CSV
output. They do not assume which CBG configuration causes more damage.
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
    CONDITIONS,
    CONTROL,
    CSV_COLUMNS,
    PREEMPTED,
    PREEMPTION_FRACTION,
    run_rq3,
    save_rq3_results,
)

TOTAL_POSITIONS = 288
EXPECTED_COUNT = round(TOTAL_POSITIONS * PREEMPTION_FRACTION)
EXPECTED_FRACTION = EXPECTED_COUNT / TOTAL_POSITIONS


class TestRq3(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.small = run_rq3(num_runs=2)
        cls.rows = run_rq3(num_runs=5)

    def by_condition(self, cbg_count, condition):
        return [
            r for r in self.rows
            if r["cbg_count"] == cbg_count
            and r["condition"] == condition
        ]

    def test_two_runs_gives_twelve_rows_in_order(self):
        self.assertEqual(len(self.small), 12)

        expected = []
        for cbg_count in CBG_COUNTS:
            for condition in CONDITIONS:
                expected.extend(
                    [(condition, cbg_count)] * 2
                )

        actual = [
            (r["condition"], r["cbg_count"])
            for r in self.small
        ]
        self.assertEqual(actual, expected)

    def test_correct_configurations_and_conditions_occur(self):
        self.assertEqual(CBG_COUNTS, (2, 4, 8))
        self.assertEqual(CONDITIONS, (CONTROL, PREEMPTED))
        self.assertEqual(
            {r["cbg_count"] for r in self.rows},
            {2, 4, 8},
        )
        self.assertEqual(
            {r["condition"] for r in self.rows},
            {CONTROL, PREEMPTED},
        )

    def test_each_configuration_condition_has_num_runs_rows(self):
        for cbg_count in CBG_COUNTS:
            for condition in CONDITIONS:
                with self.subTest(
                    cbg_count=cbg_count,
                    condition=condition,
                ):
                    rows = self.by_condition(cbg_count, condition)
                    self.assertEqual(len(rows), 5)
                    self.assertEqual(
                        [r["run"] for r in rows],
                        list(range(5)),
                    )

    def test_rows_contain_exactly_csv_columns(self):
        for row in self.rows:
            self.assertEqual(tuple(row), CSV_COLUMNS)

    def test_same_arrival_rate_for_all_runs(self):
        self.assertEqual(
            {r["arrival_rate"] for r in self.rows},
            {MEDIUM_URLLC_ARRIVAL_RATE},
        )

    def test_preempted_condition_uses_fixed_fraction(self):
        rows = [r for r in self.rows if r["condition"] == PREEMPTED]

        for row in rows:
            with self.subTest(
                cbg_count=row["cbg_count"],
                seed=row["seed"],
            ):
                self.assertEqual(
                    row["preempted_positions"],
                    EXPECTED_COUNT,
                )
                self.assertAlmostEqual(
                    row["preemption_fraction"],
                    EXPECTED_FRACTION,
                )

    def test_control_has_zero_preemption_and_retransmission_cost(self):
        control_rows = [r for r in self.rows if r["condition"] == CONTROL]

        self.assertEqual(len(control_rows), 15)

        for row in control_rows:
            with self.subTest(
                cbg_count=row["cbg_count"],
                seed=row["seed"],
            ):
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

    def test_same_preempted_positions_across_cbg_counts(self):
        for run in range(5):
            with self.subTest(run=run):
                rows = [
                    self.by_condition(cbg_count, PREEMPTED)[run]
                    for cbg_count in CBG_COUNTS
                ]
                self.assertEqual(
                    {row["preempted_positions"] for row in rows},
                    {EXPECTED_COUNT},
                )
                self.assertEqual(
                    {row["seed"] for row in rows},
                    {run},
                )
                self.assertEqual(
                    {row["total_embb_positions"] for row in rows},
                    {TOTAL_POSITIONS},
                )

    def test_same_cb_exposure_across_cbg_counts(self):
        for run in range(5):
            with self.subTest(run=run):
                affected_counts = {
                    self.by_condition(cbg_count, PREEMPTED)[run][
                        "affected_cb_count"
                    ]
                    for cbg_count in CBG_COUNTS
                }
                self.assertEqual(len(affected_counts), 1)

    def test_results_deterministic_for_same_base_seed(self):
        self.assertEqual(run_rq3(num_runs=5), self.rows)

        shifted = run_rq3(num_runs=2, base_seed=10)
        self.assertEqual(
            shifted,
            run_rq3(num_runs=2, base_seed=10),
        )

        self.assertEqual(
            {r["seed"] for r in shifted},
            {10, 11},
        )

    def test_csv_header_and_row_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rq3.csv"
            save_rq3_results(self.rows, str(path))

            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))

        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        self.assertEqual(len(rows) - 1, len(self.rows))
        self.assertEqual(rows[1][1], CONTROL)
        self.assertEqual(rows[-1][1], PREEMPTED)

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

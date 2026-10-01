"""Tests for experiments/baseline.py (no-preemption baseline)."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.baseline import (CSV_COLUMNS, run_baseline,  # noqa: E402
                                  save_baseline_results)
from src.metrics import SimulationMetrics  # noqa: E402


class TestBaseline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.results = run_baseline(num_runs=5)

    def test_returns_requested_number_of_metrics(self):
        self.assertEqual(len(self.results), 5)
        self.assertTrue(
            all(
                isinstance(m, SimulationMetrics)
                for m in self.results
            )
        )

    def test_zero_preemption(self):
        for m in self.results:
            self.assertEqual(m.preempted_positions, 0)
            self.assertEqual(m.preemption_fraction, 0.0)
            self.assertEqual(m.total_embb_positions, 288)

    def test_zero_affected_cbs_and_cbgs(self):
        for m in self.results:
            self.assertEqual(m.affected_cb_count, 0)
            self.assertEqual(m.affected_cbg_count, 0)

    def test_zero_failed_cbgs(self):
        for m in self.results:
            self.assertEqual(m.failed_cbg_count, 0)

    def test_zero_retransmission(self):
        for m in self.results:
            self.assertEqual(m.retransmission_positions, 0)
            self.assertEqual(m.retransmission_overhead, 0.0)

    def test_delivery_efficiency_is_one(self):
        for m in self.results:
            self.assertEqual(
                m.embb_delivery_efficiency,
                1.0,
            )

    def test_deterministic_for_same_base_seed(self):
        self.assertEqual(
            run_baseline(num_runs=5, base_seed=7),
            run_baseline(num_runs=5, base_seed=7),
        )
        self.assertEqual(
            run_baseline(num_runs=5),
            self.results,
        )

    def test_invalid_arguments_raise(self):
        for bad in (0, -1, 2.5, "5", None, True):
            with self.subTest(num_runs=bad):
                with self.assertRaises(ValueError):
                    run_baseline(num_runs=bad)

        for bad in (-1, 1.5, "0", None, True):
            with self.subTest(base_seed=bad):
                with self.assertRaises(ValueError):
                    run_baseline(
                        num_runs=1,
                        base_seed=bad,
                    )

    def test_csv_header_and_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.csv"

            save_baseline_results(
                self.results,
                str(path),
            )

            with open(
                path,
                newline="",
                encoding="utf-8",
            ) as f:
                rows = list(csv.reader(f))

        self.assertEqual(
            tuple(rows[0]),
            CSV_COLUMNS,
        )

        self.assertEqual(
            list(rows[0]),
            [
                "run",
                "preempted_positions",
                "total_embb_positions",
                "preemption_fraction",
                "affected_cb_count",
                "affected_cbg_count",
                "failed_cbg_count",
                "retransmission_positions",
                "retransmission_overhead",
                "embb_delivery_efficiency",
            ],
        )

        self.assertEqual(
            len(rows) - 1,
            len(self.results),
        )

        self.assertEqual(
            [r[0] for r in rows[1:]],
            ["0", "1", "2", "3", "4"],
        )

        for row in rows[1:]:
            self.assertEqual(
                row[1],
                "0",
            )  # preempted_positions

            self.assertEqual(
                row[2],
                "288",
            )  # total_embb_positions

            self.assertEqual(
                float(row[3]),
                0.0,
            )  # preemption_fraction

            self.assertEqual(
                [row[4], row[5], row[6], row[7]],
                ["0"] * 4,
            )

            self.assertEqual(
                float(row[8]),
                0.0,
            )  # retransmission_overhead

            self.assertEqual(
                float(row[9]),
                1.0,
            )  # embb_delivery_efficiency


if __name__ == "__main__":
    unittest.main()
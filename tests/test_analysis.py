"""Tests for the descriptive analysis and plotting layer."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analysis import analyze_results, plots  # noqa: E402


class TestAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)

        cls.baseline = pd.DataFrame({
            "preempted_positions": [0, 0],
            "affected_cb_count": [0, 0],
            "affected_cbg_count": [0, 0],
            "failed_cbg_count": [0, 0],
            "retransmission_positions": [0, 0],
            "retransmission_overhead": [0.0, 0.0],
            "embb_delivery_efficiency": [1.0, 1.0],
        })

        common = {
            "preempted_positions": [10, 20, 30, 10, 20, 30],
            "preemption_fraction": [0.1] * 6,
            "affected_cb_count": [2, 3, 4, 2, 3, 4],
            "affected_cbg_count": [1, 2, 3, 1, 2, 3],
            "failed_cbg_count": [0, 1, 0, 0, 0, 1],
            "retransmission_positions": [0, 72, 0, 0, 0, 72],
            "retransmission_overhead": [0.0, 0.25, 0.0, 0.0, 0.0, 0.25],
            "embb_delivery_efficiency": [
                1.0,
                100.0 / 125.0,
                1.0,
                1.0,
                1.0,
                100.0 / 125.0,
            ],
        }

        cls.rq1 = pd.DataFrame({
            "traffic_level": [
                "low",
                "medium",
                "high",
                "low",
                "medium",
                "high",
            ],
            **common,
        })

        cls.rq2 = pd.DataFrame({
            "preemption_pattern": [
                "concentrated",
                "distributed",
                "random",
            ] * 2,
            **common,
        })

        cls.rq3 = pd.DataFrame({
            "cbg_count": [2, 4, 8, 2, 4, 8],
            "seed": [0, 0, 0, 1, 1, 1],
            **common,
        })

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_missing_file_raises(self):
        old = analyze_results.RESULTS_DIR
        try:
            analyze_results.RESULTS_DIR = self.root / "missing"
            with self.assertRaises(FileNotFoundError):
                analyze_results.load_results("does_not_exist.csv")
        finally:
            analyze_results.RESULTS_DIR = old

    def test_baseline_summary(self):
        summary = analyze_results.analyze_baseline(self.baseline)

        self.assertEqual(summary.loc[0, "n"], 2)
        self.assertEqual(
            summary.loc[0, "mean_retransmission_overhead"],
            0.0,
        )
        self.assertEqual(
            summary.loc[0, "mean_embb_delivery_efficiency"],
            1.0,
        )

    def test_rq1_has_three_traffic_levels(self):
        summary = analyze_results.analyze_rq1(self.rq1)

        self.assertEqual(
            set(summary["traffic_level"]),
            {"low", "medium", "high"},
        )

    def test_rq2_has_three_patterns(self):
        summary = analyze_results.analyze_rq2(self.rq2)

        self.assertEqual(
            set(summary["preemption_pattern"]),
            {
                "concentrated",
                "distributed",
                "random",
            },
        )

    def test_rq3_has_three_cbg_counts(self):
        summary = analyze_results.analyze_rq3(self.rq3)

        self.assertEqual(
            set(summary["cbg_count"]),
            {2, 4, 8},
        )

    def test_summary_columns_exist(self):
        summary = analyze_results.analyze_rq1(self.rq1)

        expected = {
            "traffic_level",
            "n",
            "mean_preempted_positions",
            "mean_affected_cb_count",
            "mean_affected_cbg_count",
            "mean_failed_cbg_count",
            "mean_retransmission_positions",
            "mean_retransmission_overhead",
            "mean_embb_delivery_efficiency",
            "std_embb_delivery_efficiency",
            "runs_with_failure",
        }

        self.assertTrue(
            expected.issubset(summary.columns)
        )

    def test_processed_output_can_be_created(self):
        old = analyze_results.PROCESSED_DIR

        try:
            output_dir = self.root / "processed"
            analyze_results.PROCESSED_DIR = output_dir

            summary = analyze_results.analyze_rq3(self.rq3)

            path = analyze_results._write_summary(
                summary,
                "rq3_summary.csv",
            )

            self.assertTrue(path.is_file())

        finally:
            analyze_results.PROCESSED_DIR = old

    def test_plotting_functions_create_files(self):
        output_dir = self.root / "figures"

        baseline_path = plots.plot_baseline(
            self.baseline,
            output_dir,
        )

        rq1_paths = plots.plot_rq1(
            self.rq1,
            output_dir,
        )

        rq2_paths = plots.plot_rq2(
            self.rq2,
            output_dir,
        )

        rq3_paths = plots.plot_rq3(
            self.rq3,
            output_dir,
        )

        paths = [
            baseline_path,
            *rq1_paths,
            *rq2_paths,
            *rq3_paths,
        ]

        # 1 baseline + 4 RQ1 + 4 RQ2 + 4 RQ3
        self.assertEqual(len(paths), 13)

        for path in paths:
            self.assertTrue(path.is_file())
            self.assertGreater(
                path.stat().st_size,
                0,
            )


if __name__ == "__main__":
    unittest.main()
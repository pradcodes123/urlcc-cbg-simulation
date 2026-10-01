"""Descriptive analysis for the URLLC-CBG simulation experiments.

This module reads the raw experiment CSV files and produces descriptive
summaries only. It deliberately does not perform hypothesis tests or make
claims about statistical significance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

RESULTS_DIR = Path("results/raw")
PROCESSED_DIR = Path("results/processed")

BASELINE_FILE = "baseline.csv"
RQ1_FILE = "rq1_traffic.csv"
RQ2_FILE = "rq2_patterns.csv"
RQ3_FILE = "rq3_cbg.csv"


def load_results(filename: str) -> pd.DataFrame:
    """Load one raw result CSV from ``results/raw``."""
    path = RESULTS_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"Raw result file not found: {path}")
    return pd.read_csv(path)


def _validate_columns(
        df: pd.DataFrame,
        required: Iterable[str],
        name: str,
) -> None:
    """Raise ValueError if required columns are missing."""
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def _mean_std_summary(
        df: pd.DataFrame,
        group_column: str,
        name: str,
        *,
        include_preemption: bool = False,
) -> pd.DataFrame:
    """Create a descriptive mean/std summary grouped by one variable."""
    required = [
        group_column,
        "preempted_positions",
        "preemption_fraction",
        "affected_cb_count",
        "affected_cbg_count",
        "failed_cbg_count",
        "retransmission_positions",
        "retransmission_overhead",
        "embb_delivery_efficiency",
    ]

    _validate_columns(df, required, name)

    grouped = df.groupby(group_column, sort=False)

    summary = grouped.agg(
        n=(group_column, "size"),
        mean_preempted_positions=("preempted_positions", "mean"),
        std_preempted_positions=("preempted_positions", "std"),
        mean_preemption_fraction=("preemption_fraction", "mean"),
        mean_affected_cb_count=("affected_cb_count", "mean"),
        std_affected_cb_count=("affected_cb_count", "std"),
        mean_affected_cbg_count=("affected_cbg_count", "mean"),
        std_affected_cbg_count=("affected_cbg_count", "std"),
        mean_failed_cbg_count=("failed_cbg_count", "mean"),
        mean_retransmission_positions=("retransmission_positions", "mean"),
        mean_retransmission_overhead=("retransmission_overhead", "mean"),
        std_retransmission_overhead=("retransmission_overhead", "std"),
        mean_embb_delivery_efficiency=(
            "embb_delivery_efficiency",
            "mean",
        ),
        std_embb_delivery_efficiency=(
            "embb_delivery_efficiency",
            "std",
        ),
    ).reset_index()

    failed_runs = grouped["failed_cbg_count"].apply(
        lambda s: int((s > 0).sum())
    )

    summary["runs_with_failure"] = summary[group_column].map(
        failed_runs
    )

    if not include_preemption:
        # Keep the preemption columns because they provide useful
        # descriptive context for all three RQs.
        pass

    return summary


def analyze_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Return one descriptive summary row for the no-preemption baseline."""
    required = [
        "preempted_positions",
        "affected_cb_count",
        "affected_cbg_count",
        "failed_cbg_count",
        "retransmission_positions",
        "retransmission_overhead",
        "embb_delivery_efficiency",
    ]

    _validate_columns(df, required, "baseline")

    return pd.DataFrame(
        [{
            "n": len(df),
            "mean_preempted_positions": (
                df["preempted_positions"].mean()
            ),
            "mean_affected_cb_count": (
                df["affected_cb_count"].mean()
            ),
            "mean_affected_cbg_count": (
                df["affected_cbg_count"].mean()
            ),
            "mean_failed_cbg_count": (
                df["failed_cbg_count"].mean()
            ),
            "mean_retransmission_positions": (
                df["retransmission_positions"].mean()
            ),
            "mean_retransmission_overhead": (
                df["retransmission_overhead"].mean()
            ),
            "mean_embb_delivery_efficiency": (
                df["embb_delivery_efficiency"].mean()
            ),
        }]
    )


def analyze_rq1(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize RQ1 by URLLC traffic level."""
    _validate_columns(df, ["traffic_level"], "RQ1")
    return _mean_std_summary(df, "traffic_level", "RQ1")


def analyze_rq2(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize RQ2 by spatial preemption pattern."""
    _validate_columns(df, ["preemption_pattern"], "RQ2")
    return _mean_std_summary(df, "preemption_pattern", "RQ2")


def analyze_rq3(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize RQ3 by configured number of CBGs."""
    _validate_columns(df, ["cbg_count"], "RQ3")
    return _mean_std_summary(df, "cbg_count", "RQ3")


def _write_summary(
        summary: pd.DataFrame,
        filename: str,
) -> Path:
    """Write one processed summary CSV."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / filename
    summary.to_csv(path, index=False)
    return path


def main() -> None:
    """Analyze all raw experiment files and write summaries."""
    baseline = analyze_baseline(
        load_results(BASELINE_FILE)
    )
    rq1 = analyze_rq1(
        load_results(RQ1_FILE)
    )
    rq2 = analyze_rq2(
        load_results(RQ2_FILE)
    )
    rq3 = analyze_rq3(
        load_results(RQ3_FILE)
    )

    paths = [
        _write_summary(
            baseline,
            "baseline_summary.csv",
        ),
        _write_summary(
            rq1,
            "rq1_summary.csv",
        ),
        _write_summary(
            rq2,
            "rq2_summary.csv",
        ),
        _write_summary(
            rq3,
            "rq3_summary.csv",
        ),
    ]

    print("\nBaseline summary")
    print(baseline.to_string(index=False))

    print("\nRQ1 summary")
    print(rq1.to_string(index=False))

    print("\nRQ2 summary")
    print(rq2.to_string(index=False))

    print("\nRQ3 summary")
    print(rq3.to_string(index=False))

    print("\nWritten:")
    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
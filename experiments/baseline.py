"""No-preemption baseline for eMBB (reference experiment, not RQ1/RQ2/RQ3).

Runs the default simulation with ``preemption_fraction = 0.0`` over
deterministic seeds ``base_seed + i`` and stores one CSV row per run. With zero
preemption every damage-related metric must be exactly zero.

Run from the project root:  python -m experiments.baseline
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from config.simulation import make_default_config
from src.metrics import SimulationMetrics
from src.simulation import run_simulation

CSV_COLUMNS = (
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
)

DEFAULT_OUTPUT_PATH = "results/raw/baseline.csv"


def run_baseline(
        num_runs: int = 30,
        base_seed: int = 0,
) -> list[SimulationMetrics]:
    """Run ``num_runs`` zero-preemption trials with seeds ``base_seed + i``."""
    if (
        isinstance(num_runs, bool)
        or not isinstance(num_runs, int)
        or num_runs <= 0
    ):
        raise ValueError(
            f"num_runs must be a positive integer, got {num_runs!r}"
        )

    if (
        isinstance(base_seed, bool)
        or not isinstance(base_seed, int)
        or base_seed < 0
    ):
        raise ValueError(
            f"base_seed must be a non-negative integer, got {base_seed!r}"
        )

    config = dataclasses.replace(
        make_default_config(),
        preemption_fraction=0.0,
        num_preempt=None,
    )

    return [
        run_simulation(
            config,
            seed=base_seed + i,
        )
        for i in range(num_runs)
    ]


def save_baseline_results(
        results: list[SimulationMetrics],
        output_path: str,
) -> None:
    """Write one CSV row per run (``run`` is the 0-based run index)."""
    with open(
        output_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)

        for run, metrics in enumerate(results):
            writer.writerow(
                [
                    run,
                    *[
                        getattr(metrics, name)
                        for name in CSV_COLUMNS[1:]
                    ],
                ]
            )


def main() -> None:
    results = run_baseline(
        num_runs=30,
        base_seed=0,
    )

    Path(DEFAULT_OUTPUT_PATH).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_baseline_results(
        results,
        DEFAULT_OUTPUT_PATH,
    )

    all_zero = all(
        metrics.preempted_positions == 0
        and metrics.affected_cb_count == 0
        and metrics.affected_cbg_count == 0
        and metrics.failed_cbg_count == 0
        and metrics.retransmission_positions == 0
        and metrics.retransmission_overhead == 0
        and metrics.embb_delivery_efficiency == 1.0
        for metrics in results
    )

    print(
        f"Baseline: {len(results)} runs, "
        f"{results[0].total_embb_positions} eMBB positions per run"
    )
    print(f"All damage metrics zero: {all_zero}")
    print(f"Saved to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
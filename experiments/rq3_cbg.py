"""RQ3: effect of CBG count on eMBB damage and retransmission.

For each CBG count, compare a no-preemption control against 20% preemption.
All other configuration parameters and random seeds are matched.
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE, make_default_config
from src.simulation import run_simulation

CBG_COUNTS = (2, 4, 8)
CONTROL = "no_preemption"
PREEMPTED = "preempted"
CONDITIONS = (CONTROL, PREEMPTED)
PREEMPTION_FRACTION = 0.20

CSV_COLUMNS = (
    "run",
    "condition",
    "cbg_count",
    "seed",
    "arrival_rate",
    "preempted_positions",
    "total_embb_positions",
    "preemption_fraction",
    "affected_cb_count",
    "affected_cbg_count",
    "failed_cbg_count",
    "retransmission_positions",
    "retransmission_overhead",
    "embb_delivery_efficiency",
    "initial_failed_cbg_count",
    "harq_recovered_cbg_count",
    "initial_cbg_failure_rate",
    "residual_bler",
    "final_delivery_success_rate",
    "harq_retransmission_count",
    "delivered_embb_positions",
    "embb_delivery_rate_per_slot",
)

DEFAULT_OUTPUT_PATH = "results/raw/rq3_cbg.csv"


def run_rq3(num_runs: int = 30, base_seed: int = 0) -> list[dict]:
    """Run matched-seed trials for each CBG count and condition."""
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

    rows: list[dict] = []

    for cbg_count in CBG_COUNTS:
        for condition in CONDITIONS:
            fraction = (
                0.0 if condition == CONTROL else PREEMPTION_FRACTION
            )

            config = make_default_config(
                arrival_rate=MEDIUM_URLLC_ARRIVAL_RATE,
                cbg_count=cbg_count,
                preemption_pattern="random",
                preemption_fraction=fraction,
                num_preempt=None,
            )

            for run in range(num_runs):
                seed = base_seed + run
                metrics = run_simulation(config, seed=seed)

                rows.append({
                    "run": run,
                    "condition": condition,
                    "cbg_count": cbg_count,
                    "seed": seed,
                    "arrival_rate": MEDIUM_URLLC_ARRIVAL_RATE,
                    **dataclasses.asdict(metrics),
                })

    return rows


def save_rq3_results(results: list[dict], output_path: str) -> None:
    """Write one CSV row per simulation run."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(results)


def main() -> None:
    results = run_rq3(num_runs=30, base_seed=0)
    Path(DEFAULT_OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    save_rq3_results(results, DEFAULT_OUTPUT_PATH)

    print(
        f"RQ3: {len(results)} rows, "
        f"CBG configurations: {', '.join(str(c) for c in CBG_COUNTS)}"
    )
    print(
        f"Control: {sum(r['condition'] == CONTROL for r in results)} runs; "
        f"preempted: {sum(r['condition'] == PREEMPTED for r in results)} runs"
    )
    print(f"Saved to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
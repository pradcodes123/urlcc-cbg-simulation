
"""RQ2: effect of the spatial pattern of URLLC preemption on eMBB damage.

Compares a no-preemption control with concentrated, distributed, and random
preemption. The three preemption patterns use the same medium URLLC arrival
rate, CBG count, preemption fraction, and seeds.

Experiment driver only (no statistics or plotting).
Run from the project root: python -m experiments.rq2_patterns
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE, make_default_config
from src.simulation import run_simulation

PATTERNS = ("concentrated", "distributed", "random")
CONTROL = "no_preemption"
CONDITIONS = (CONTROL, *PATTERNS)
PREEMPTION_FRACTION = 0.20

CSV_COLUMNS = (
    "run",
    "preemption_pattern",
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

DEFAULT_OUTPUT_PATH = "results/raw/rq2_patterns.csv"


def run_rq2(num_runs: int = 30, base_seed: int = 0) -> list[dict]:
    """Run trials for the control and each pattern using matched seeds.

    Rows are ordered: control, concentrated, distributed, then random.
    """
    if isinstance(num_runs, bool) or not isinstance(num_runs, int) or num_runs <= 0:
        raise ValueError(f"num_runs must be a positive integer, got {num_runs!r}")
    if isinstance(base_seed, bool) or not isinstance(base_seed, int) or base_seed < 0:
        raise ValueError(f"base_seed must be a non-negative integer, got {base_seed!r}")

    rows: list[dict] = []

    for condition in CONDITIONS:
        if condition == CONTROL:
            config = make_default_config(
                arrival_rate=MEDIUM_URLLC_ARRIVAL_RATE,
                cbg_count=4,
                preemption_pattern="random",
                preemption_fraction=0.0,
                num_preempt=None,
            )
        else:
            config = make_default_config(
                arrival_rate=MEDIUM_URLLC_ARRIVAL_RATE,
                cbg_count=4,
                preemption_pattern=condition,
                preemption_fraction=PREEMPTION_FRACTION,
                num_preempt=None,
            )

        for run in range(num_runs):
            seed = base_seed + run
            metrics = run_simulation(config, seed=seed)
            rows.append({
                "run": run,
                "preemption_pattern": condition,
                "seed": seed,
                "arrival_rate": MEDIUM_URLLC_ARRIVAL_RATE,
                **dataclasses.asdict(metrics),
            })

    return rows


def save_rq2_results(results: list[dict], output_path: str) -> None:
    """Write one CSV row per simulation run."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(results)


def main() -> None:
    results = run_rq2(num_runs=30, base_seed=0)
    Path(DEFAULT_OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    save_rq2_results(results, DEFAULT_OUTPUT_PATH)

    print(
        f"RQ2: {len(results)} rows, conditions: "
        f"{', '.join(CONDITIONS)}"
    )
    print(
        f"Pattern preemption fraction: {PREEMPTION_FRACTION}"
    )
    print(f"Saved to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()

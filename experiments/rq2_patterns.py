"""RQ2: effect of the spatial pattern of URLLC preemption on eMBB damage.

Only ``preemption_pattern`` varies (concentrated / distributed / random).
Fixed: medium URLLC arrival rate, CBG count 4, preemption_fraction 0.20,
num_preempt None, and the SNR-aware decoder at the study operating point
(10 dB). Every pattern therefore preempts the SAME number of eMBB positions;
only their spatial distribution differs.

Experiment driver only (no statistics or plotting).
Run from the project root:  python -m experiments.rq2_patterns
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE, make_default_config
from src.simulation import run_simulation

PATTERNS = ("concentrated", "distributed", "random")
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
)

DEFAULT_OUTPUT_PATH = "results/raw/rq2_patterns.csv"


def run_rq2(num_runs: int = 30, base_seed: int = 0) -> list[dict]:
    """Run ``num_runs`` trials per pattern (seed = ``base_seed + run``).

    Rows are ordered: all concentrated runs, then distributed, then random.
    """
    if isinstance(num_runs, bool) or not isinstance(num_runs, int) or num_runs <= 0:
        raise ValueError(f"num_runs must be a positive integer, got {num_runs!r}")
    if isinstance(base_seed, bool) or not isinstance(base_seed, int) or base_seed < 0:
        raise ValueError(f"base_seed must be a non-negative integer, got {base_seed!r}")

    rows: list[dict] = []
    for pattern in PATTERNS:
        config = make_default_config(arrival_rate=MEDIUM_URLLC_ARRIVAL_RATE, cbg_count=4,
                                     preemption_pattern=pattern,
                                     preemption_fraction=PREEMPTION_FRACTION,
                                     num_preempt=None)
        for run in range(num_runs):
            seed = base_seed + run
            metrics = run_simulation(config, seed=seed)
            rows.append({"run": run, "preemption_pattern": pattern, "seed": seed,
                         "arrival_rate": MEDIUM_URLLC_ARRIVAL_RATE,
                         **dataclasses.asdict(metrics)})
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
    print(f"RQ2: {len(results)} rows, patterns: {', '.join(PATTERNS)}")
    print(f"Preempted positions per run: {results[0]['preempted_positions']} "
          f"of {results[0]['total_embb_positions']} (fraction {PREEMPTION_FRACTION})")
    print(f"Saved to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
"""RQ1: effect of URLLC traffic intensity on eMBB damage and CBG retransmission.

Only ``arrival_rate`` varies (low / medium / high). Everything else is fixed:
default eMBB config, CBG count 4, "random" preemption pattern, decoder
threshold 0.25. With ``preemption_fraction`` and ``num_preempt`` both None, the
preempted amount is derived from the generated URLLC demand, so the preempted
fraction is an outcome of the traffic level, not a fixed parameter.

Experiment driver only (no statistics or plotting).
Run from the project root:  python -m experiments.rq1_traffic
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from config.simulation import (HIGH_URLLC_ARRIVAL_RATE, LOW_URLLC_ARRIVAL_RATE,
                               MEDIUM_URLLC_ARRIVAL_RATE, make_default_config)
from src.simulation import run_simulation

TRAFFIC_LEVELS = (
    ("low", LOW_URLLC_ARRIVAL_RATE),
    ("medium", MEDIUM_URLLC_ARRIVAL_RATE),
    ("high", HIGH_URLLC_ARRIVAL_RATE),
)

CSV_COLUMNS = (
    "run",
    "traffic_level",
    "arrival_rate",
    "seed",
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

DEFAULT_OUTPUT_PATH = "results/raw/rq1_traffic.csv"


def run_rq1(num_runs: int = 30, base_seed: int = 0) -> list[dict]:
    """Run ``num_runs`` trials per traffic level (seed = ``base_seed + run``).

    Rows are ordered: all low runs, then medium, then high.
    """
    if isinstance(num_runs, bool) or not isinstance(num_runs, int) or num_runs <= 0:
        raise ValueError(f"num_runs must be a positive integer, got {num_runs!r}")
    if isinstance(base_seed, bool) or not isinstance(base_seed, int) or base_seed < 0:
        raise ValueError(f"base_seed must be a non-negative integer, got {base_seed!r}")

    rows: list[dict] = []
    for level, rate in TRAFFIC_LEVELS:
        config = make_default_config(arrival_rate=rate, cbg_count=4,
                                     preemption_pattern="random",
                                     preemption_fraction=None, num_preempt=None)
        for run in range(num_runs):
            seed = base_seed + run
            metrics = run_simulation(config, seed=seed)
            rows.append({"run": run, "traffic_level": level, "arrival_rate": rate,
                         "seed": seed, **dataclasses.asdict(metrics)})
    return rows


def save_rq1_results(results: list[dict], output_path: str) -> None:
    """Write one CSV row per simulation run."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    results = run_rq1(num_runs=30, base_seed=0)
    Path(DEFAULT_OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    save_rq1_results(results, DEFAULT_OUTPUT_PATH)
    levels = [lvl for lvl, _ in TRAFFIC_LEVELS]
    print(f"RQ1: {len(results)} rows, traffic levels: {', '.join(levels)}")
    print(f"Saved to {DEFAULT_OUTPUT_PATH}")
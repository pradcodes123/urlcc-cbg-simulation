"""RQ3: effect of the configured number of CBGs on eMBB damage and retransmission.

Only ``cbg_count`` varies (2 / 4 / 8). Fixed: medium URLLC arrival rate,
"random" preemption pattern, preemption_fraction 0.20, num_preempt None,
SNR-aware decoder at the study operating point (10 dB), and default eMBB
configuration (8 code blocks).

Because the random preemption depends only on the seed, run ``i`` preempts the
very same positions under every CBG configuration; only the CB-to-CBG grouping
differs.

Experiment driver only (no statistics or plotting).
Run from the project root:  python -m experiments.rq3_cbg
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE, make_default_config
from src.simulation import run_simulation

CBG_COUNTS = (2, 4, 8)
PREEMPTION_FRACTION = 0.20

CSV_COLUMNS = (
    "run",
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
)

DEFAULT_OUTPUT_PATH = "results/raw/rq3_cbg.csv"


def run_rq3(num_runs: int = 30, base_seed: int = 0) -> list[dict]:
    """Run ``num_runs`` trials per CBG count (seed = ``base_seed + run``).

    Rows are ordered: all 2-CBG runs, then 4-CBG, then 8-CBG.
    """
    if isinstance(num_runs, bool) or not isinstance(num_runs, int) or num_runs <= 0:
        raise ValueError(f"num_runs must be a positive integer, got {num_runs!r}")
    if isinstance(base_seed, bool) or not isinstance(base_seed, int) or base_seed < 0:
        raise ValueError(f"base_seed must be a non-negative integer, got {base_seed!r}")

    rows: list[dict] = []
    for cbg_count in CBG_COUNTS:
        config = make_default_config(arrival_rate=MEDIUM_URLLC_ARRIVAL_RATE,
                                     cbg_count=cbg_count,
                                     preemption_pattern="random",
                                     preemption_fraction=PREEMPTION_FRACTION,
                                     num_preempt=None)
        for run in range(num_runs):
            seed = base_seed + run
            metrics = run_simulation(config, seed=seed)
            rows.append({"run": run, "cbg_count": cbg_count, "seed": seed,
                         "arrival_rate": MEDIUM_URLLC_ARRIVAL_RATE,
                         **dataclasses.asdict(metrics)})
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
    print(f"RQ3: {len(results)} rows, CBG configurations: "
          f"{', '.join(str(c) for c in CBG_COUNTS)}")
    print(f"Preempted positions per run: {results[0]['preempted_positions']} "
          f"of {results[0]['total_embb_positions']} (fraction {PREEMPTION_FRACTION})")
    print(f"Saved to {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
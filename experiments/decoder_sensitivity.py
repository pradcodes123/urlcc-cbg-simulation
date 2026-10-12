
"""RQ2 decoder-SNR sensitivity experiment.

Keeps the original RQ2 traffic, CBG configuration, puncturing fraction,
patterns and seeds fixed. Only decoder SNR changes.

Writes to results/decoder_sensitivity/; never overwrites official results.
Run from the repository root:
    python -m experiments.decoder_sensitivity
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE, make_default_config
from src.simulation import run_simulation

PATTERNS = ("concentrated", "distributed", "random")
SNR_VALUES_DB = (6.0, 10.0, 14.0)
NUM_RUNS = 200
BASE_SEED = 0
PREEMPTION_FRACTION = 0.20

OUTPUT_DIR = Path("results/decoder_sensitivity")
RAW_PATH = OUTPUT_DIR / "raw" / "rq2_decoder_sensitivity.csv"
SUMMARY_PATH = OUTPUT_DIR / "processed" / "rq2_decoder_sensitivity_summary.csv"

METRICS = (
    "preempted_positions",
    "preemption_fraction",
    "affected_cb_count",
    "affected_cbg_count",
    "failed_cbg_count",
    "retransmission_positions",
    "retransmission_overhead",
    "embb_delivery_efficiency",
)


def run_experiment() -> list[dict]:
    rows: list[dict] = []

    for snr_db in SNR_VALUES_DB:
        for pattern in PATTERNS:
            config = make_default_config(
                arrival_rate=MEDIUM_URLLC_ARRIVAL_RATE,
                cbg_count=4,
                preemption_pattern=pattern,
                preemption_fraction=PREEMPTION_FRACTION,
                num_preempt=None,
            )
            config = dataclasses.replace(
                config,
                channel_config=dataclasses.replace(
                    config.channel_config,
                    mean_snr_db=snr_db,
                ),
            )

            for run in range(NUM_RUNS):
                seed = BASE_SEED + run
                metrics = run_simulation(config, seed=seed)
                rows.append({
                    "snr_db": snr_db,
                    "preemption_pattern": pattern,
                    "run": run,
                    "seed": seed,
                    **dataclasses.asdict(metrics),
                })

    return rows


def summarize(rows: list[dict]) -> list[dict]:
    summary: list[dict] = []

    for snr_db in SNR_VALUES_DB:
        for pattern in PATTERNS:
            group = [
                row for row in rows
                if row["snr_db"] == snr_db
                and row["preemption_pattern"] == pattern
            ]

            record = {
                "snr_db": snr_db,
                "preemption_pattern": pattern,
                "n": len(group),
                "runs_with_failure": sum(
                    row["failed_cbg_count"] > 0 for row in group
                ),
            }

            for metric in METRICS:
                values = [float(row[metric]) for row in group]
                record[f"mean_{metric}"] = (
                    sum(values) / len(values) if values else float("nan")
                )

            summary.append(record)

    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows to write to {path}")

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = run_experiment()
    summary = summarize(rows)

    write_csv(RAW_PATH, rows)
    write_csv(SUMMARY_PATH, summary)

    print(f"Runs: {len(rows)} (expected {len(SNR_VALUES_DB) * len(PATTERNS) * NUM_RUNS})")
    print(f"Summary groups: {len(summary)}")
    print(f"Raw results: {RAW_PATH}")
    print(f"Summary: {SUMMARY_PATH}")
    print("\nMean retransmission overhead by SNR and pattern:")

    for row in summary:
        print(
            f"SNR={row['snr_db']:>4.1f} dB | "
            f"{row['preemption_pattern']:<12} | "
            f"overhead={row['mean_retransmission_overhead']:.4f} | "
            f"runs with failure={row['runs_with_failure']}/{row['n']}"
        )


if __name__ == "__main__":
    main()

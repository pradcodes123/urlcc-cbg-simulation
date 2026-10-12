
"""Compare URLLC arrival timing under matched offered load.

Run from the repository root:
    python -m experiments.urllc_burst_patterns
"""

from __future__ import annotations

import csv
import dataclasses
from pathlib import Path

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE, make_default_config
from src.scheduler import SchedulerConfig, schedule_urllc_events
from src.simulation import run_simulation
from src.urllc import generate_urllc_traffic

ARRIVAL_PATTERNS = ("poisson", "evenly_spaced", "bursty")
NUM_RUNS = 200
BASE_SEED = 0
PREEMPTION_FRACTION = 0.20

OUTPUT_DIR = Path("results/urllc_burst_patterns")
RAW_PATH = OUTPUT_DIR / "raw" / "urllc_burst_patterns.csv"
SUMMARY_PATH = OUTPUT_DIR / "processed" / "urllc_burst_patterns_summary.csv"

SCHEDULER_METRICS = (
    "scheduling_success_rate",
    "deadline_miss_rate",
    "capacity_rejection_rate",
    "scheduled_resource_units",
)


def run_experiment() -> list[dict]:
    rows: list[dict] = []

    for pattern in ARRIVAL_PATTERNS:
        for run in range(NUM_RUNS):
            seed = BASE_SEED + run

            config = make_default_config(
                arrival_rate=MEDIUM_URLLC_ARRIVAL_RATE,
                cbg_count=4,
                preemption_pattern="random",
                preemption_fraction=PREEMPTION_FRACTION,
                num_preempt=None,
            )
            config = dataclasses.replace(
                config,
                urllc_arrival_pattern=pattern,
            )

            events = generate_urllc_traffic(
                config.urllc_config,
                seed,
                arrival_pattern=pattern,
            )

            scheduling = schedule_urllc_events(
                events,
                SchedulerConfig(
                    slot_capacity=config.scheduler_slot_capacity,
                    simulation_time=config.urllc_config.simulation_time,
                ),
            )

            count = len(events)
            successes = sum(result.success for result in scheduling)
            deadline_misses = sum(
                result.failure_reason == "deadline_missed"
                for result in scheduling
            )
            capacity_rejections = sum(
                result.failure_reason == "insufficient_capacity"
                for result in scheduling
            )

            metrics = run_simulation(config, seed=seed)

            rows.append({
                "arrival_pattern": pattern,
                "run": run,
                "seed": seed,
                "event_count": count,
                "total_requested_resources": sum(
                    event.resource_demand for event in events
                ),
                "scheduling_success_rate": (
                    successes / count if count else 1.0
                ),
                "deadline_miss_rate": (
                    deadline_misses / count if count else 0.0
                ),
                "capacity_rejection_rate": (
                    capacity_rejections / count if count else 0.0
                ),
                "scheduled_resource_units": sum(
                    result.scheduled_resources for result in scheduling
                ),
                **dataclasses.asdict(metrics),
            })

    return rows


def summarize(rows: list[dict]) -> list[dict]:
    summary: list[dict] = []

    metrics = (
        *SCHEDULER_METRICS,
        "preempted_positions",
        "affected_cbg_count",
        "initial_failed_cbg_count",
        "harq_recovered_cbg_count",
        "failed_cbg_count",
        "retransmission_positions",
        "retransmission_overhead",
        "residual_bler",
        "final_delivery_success_rate",
        "delivered_embb_positions",
        "embb_delivery_rate_per_slot",
        "embb_delivery_efficiency",
    )

    for pattern in ARRIVAL_PATTERNS:
        group = [row for row in rows if row["arrival_pattern"] == pattern]
        record = {
            "arrival_pattern": pattern,
            "n": len(group),
            "mean_event_count": (
                sum(row["event_count"] for row in group) / len(group)
                if group else 0.0
            ),
        }

        for metric in metrics:
            values = [float(row[metric]) for row in group]
            record[f"mean_{metric}"] = (
                sum(values) / len(values) if values else float("nan")
            )

        summary.append(record)

    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows to write to {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = run_experiment()
    summary = summarize(rows)

    expected = len(ARRIVAL_PATTERNS) * NUM_RUNS
    if len(rows) != expected:
        raise RuntimeError(f"Expected {expected} trials, got {len(rows)}")

    write_csv(RAW_PATH, rows)
    write_csv(SUMMARY_PATH, summary)

    print(f"Trials: {len(rows)}")
    print(f"Raw results: {RAW_PATH}")
    print(f"Summary: {SUMMARY_PATH}")

    for row in summary:
        print(
            f"{row['arrival_pattern']:<14} "
            f"events={row['mean_event_count']:.1f} | "
            f"scheduling success={row['mean_scheduling_success_rate']:.3f} | "
            f"deadline misses={row['mean_deadline_miss_rate']:.3f} | "
            f"residual BLER={row['mean_residual_bler']:.4f} | "
            f"overhead={row['mean_retransmission_overhead']:.4f} | "
            f"delivery rate="
            f"{row['mean_embb_delivery_rate_per_slot']:.4f}"
        )


if __name__ == "__main__":
    main()

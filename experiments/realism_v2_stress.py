
"""Stress-test Realism v2 scheduling under tighter capacity and deadlines.

This is separate from the baseline Realism v2 experiment and official RQ1/RQ2/RQ3.
Outputs are written under results/realism_v2_stress/.
"""

from __future__ import annotations

import csv
from dataclasses import replace
from pathlib import Path
from statistics import mean, stdev
from math import sqrt
from typing import Mapping, Sequence

from src.urllc import preset_config, generate_urllc_traffic
from experiments.realism_v2 import (
    TRAFFIC_LEVELS,
    SEEDS,
    schedule_aggregate_demand,
    schedule_deadline_aware_edf,
)

SCENARIOS = (
    ("baseline", 8, 4),
    ("capacity_6", 6, 4),
    ("capacity_4", 4, 4),
    ("capacity_2", 2, 4),
    ("deadline_1", 8, 1),
    ("capacity_6_deadline_1", 6, 1),
)

SIMULATION_SLOTS = 100

RAW_PATH = Path("results/realism_v2_stress/raw/stress_runs.csv")
SUMMARY_PATH = Path("results/realism_v2_stress/processed/stress_summary.csv")

POLICIES = (
    ("aggregate_demand", schedule_aggregate_demand),
    ("deadline_aware_edf", schedule_deadline_aware_edf),
)

METRICS = (
    "event_success_rate",
    "deadline_miss_rate",
    "capacity_rejection_rate",
    "immediate_rejection_rate",
    "unresolved_rate",
    "resource_utilization",
)

RAW_COLUMNS = (
    "scenario",
    "traffic_level",
    "policy",
    "run",
    "seed",
    "simulation_slots",
    "slot_capacity",
    "deadline_window",
    "service_horizon_slots",
    "arrival_rate",
    "event_count",
    "successful_events",
    "deadline_misses",
    "capacity_rejections",
    "immediate_rejections",
    "unresolved_events",
    "scheduled_resource_units",
    "capacity_resource_units",
    *METRICS,
)

SUMMARY_COLUMNS = (
    "scenario",
    "traffic_level",
    "policy",
    "metric",
    "n",
    "mean",
    "std_dev",
    "ci95_low",
    "ci95_high",
)


def run_stress_experiment() -> list[dict]:
    """Run every scenario using identical seeds across policies."""
    rows: list[dict] = []

    for scenario, capacity, deadline_window in SCENARIOS:
        for traffic_level in TRAFFIC_LEVELS:
            config = preset_config(
                traffic_level,
                simulation_time=SIMULATION_SLOTS,
            )

            for run, seed in enumerate(SEEDS):
                original_events = generate_urllc_traffic(config, seed)

                # Preserve arrivals and demands; change only each event's
                # absolute deadline to test the requested latency budget.
                events = tuple(
                    replace(
                        event,
                        deadline=event.arrival_time + deadline_window,
                    )
                    for event in original_events
                )

                # Both policies receive the exact same events for this run.
                for policy, scheduler in POLICIES:
                    metrics = scheduler(
                        events,
                        simulation_slots=SIMULATION_SLOTS,
                        slot_capacity=capacity,
                        deadline_window=deadline_window,
                    )

                    horizon = SIMULATION_SLOTS + deadline_window

                    rows.append({
                        "scenario": scenario,
                        "traffic_level": traffic_level,
                        "policy": policy,
                        "run": run,
                        "seed": seed,
                        "simulation_slots": SIMULATION_SLOTS,
                        "slot_capacity": capacity,
                        "deadline_window": deadline_window,
                        "service_horizon_slots": horizon,
                        "arrival_rate": config.arrival_rate,
                        **metrics,
                    })

    return rows


def save_raw(rows: Sequence[Mapping]) -> None:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)

    with RAW_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=RAW_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: Sequence[Mapping]) -> list[dict]:
    """Calculate descriptive mean and normal-approximation 95% CIs."""
    summaries: list[dict] = []

    for scenario, _, _ in SCENARIOS:
        for traffic_level in TRAFFIC_LEVELS:
            for policy, _ in POLICIES:
                group = [
                    row for row in rows
                    if row["scenario"] == scenario
                    and row["traffic_level"] == traffic_level
                    and row["policy"] == policy
                ]

                for metric in METRICS:
                    values = [float(row[metric]) for row in group]
                    n = len(values)

                    if n == 0:
                        avg = sd = low = high = float("nan")
                    else:
                        avg = mean(values)
                        sd = stdev(values) if n > 1 else 0.0
                        half_width = (
                            1.96 * sd / sqrt(n) if n > 1 else 0.0
                        )
                        low = avg - half_width
                        high = avg + half_width

                    summaries.append({
                        "scenario": scenario,
                        "traffic_level": traffic_level,
                        "policy": policy,
                        "metric": metric,
                        "n": n,
                        "mean": avg,
                        "std_dev": sd,
                        "ci95_low": low,
                        "ci95_high": high,
                    })

    return summaries


def save_summary(rows: Sequence[Mapping]) -> list[dict]:
    summaries = summarize(rows)
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with SUMMARY_PATH.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=SUMMARY_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(summaries)

    return summaries


def main() -> None:
    rows = run_stress_experiment()
    save_raw(rows)
    summaries = save_summary(rows)

    print(f"Completed {len(rows)} stress-test records.")
    print(f"Raw results: {RAW_PATH}")
    print(f"Summary rows: {len(summaries)}")
    print(f"Summary results: {SUMMARY_PATH}")

    print("\nHigh-traffic event success rates:")
    for scenario, _, _ in SCENARIOS:
        for policy, _ in POLICIES:
            match = next(
                row for row in summaries
                if row["scenario"] == scenario
                and row["traffic_level"] == "high"
                and row["policy"] == policy
                and row["metric"] == "event_success_rate"
            )
            print(
                f"  {scenario:24s} {policy:20s} "
                f"{match['mean']:.4f}"
            )


if __name__ == "__main__":
    main()

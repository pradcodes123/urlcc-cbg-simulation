
"""Experimental comparison of aggregate-demand admission and EDF scheduling.

This experiment is separate from official RQ1/RQ2/RQ3.
It uses the existing synthetic URLLC event generator.

It does not model eMBB preemption damage, CBG retransmissions,
or physical-layer 5G NR behaviour.

Run explicitly with:
    python -m experiments.realism_v2
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping, Sequence

from src.urllc import (
    URLLCEvent,
    preset_config,
    generate_urllc_traffic,
)

TRAFFIC_LEVELS = ("low", "medium", "high")
RUN_COUNT = 30
SEEDS = tuple(range(20_260_000, 20_260_000 + RUN_COUNT))

# New arrivals occur in slots [0, 100).
SLOTS_PER_RUN = 100

# The service horizon includes the inclusive deadline tail.
SLOT_CAPACITY = 8

POLICIES = ("aggregate_demand", "deadline_aware_edf")

RAW_OUTPUT_PATH = Path(
    "results/realism_v2/raw/scheduling_runs.csv"
)
PROCESSED_OUTPUT_PATH = Path(
    "results/realism_v2/processed/scheduling_summary.csv"
)

RAW_COLUMNS = (
    "traffic_level",
    "arrival_rate",
    "policy",
    "run",
    "seed",
    "simulation_slots",
    "service_horizon_slots",
    "slot_capacity",
    "event_count",
    "successful_events",
    "deadline_misses",
    "capacity_rejections",
    "immediate_rejections",
    "unresolved_events",
    "scheduled_resource_units",
    "capacity_resource_units",
    "event_success_rate",
    "deadline_miss_rate",
    "capacity_rejection_rate",
    "immediate_rejection_rate",
    "unresolved_rate",
    "resource_utilization",
)

SUMMARY_COLUMNS = (
    "traffic_level",
    "policy",
    "metric",
    "n",
    "mean",
    "std_dev",
    "ci95_low",
    "ci95_high",
)


def _validate_events(events: Sequence[URLLCEvent]) -> None:
    """Validate event identities and basic timing/resource constraints."""
    ids = [event.event_id for event in events]

    if len(ids) != len(set(ids)):
        raise ValueError("URLLC event IDs must be unique")

    for event in events:
        if event.arrival_time < 0 or event.resource_demand <= 0:
            raise ValueError(
                "event arrival times must be non-negative "
                "and demands positive"
            )

        if event.deadline < event.arrival_time:
            raise ValueError(
                "event deadline must be >= arrival_time"
            )


def _validate_scheduler_inputs(
    events: Sequence[URLLCEvent],
    simulation_slots: int,
    slot_capacity: int,
    deadline_window: int,
) -> None:
    """Validate the common contract used by both scheduling policies."""
    _validate_events(events)

    if (
        isinstance(simulation_slots, bool)
        or not isinstance(simulation_slots, int)
        or simulation_slots <= 0
    ):
        raise ValueError(
            "simulation_slots must be a positive integer"
        )

    if (
        isinstance(slot_capacity, bool)
        or not isinstance(slot_capacity, int)
        or slot_capacity <= 0
    ):
        raise ValueError(
            "slot_capacity must be a positive integer"
        )

    if (
        isinstance(deadline_window, bool)
        or not isinstance(deadline_window, int)
        or deadline_window < 0
    ):
        raise ValueError(
            "deadline_window must be a non-negative integer"
        )

    if any(
        event.arrival_time >= simulation_slots
        for event in events
    ):
        raise ValueError(
            "All event arrivals must fall within the simulation window"
        )

    if any(
        event.deadline
        > event.arrival_time + deadline_window
        for event in events
    ):
        raise ValueError(
            "Event deadline exceeds the configured deadline window"
        )


def _capacity_horizon(
    simulation_slots: int,
    deadline_window: int,
) -> int:
    """Return the exclusive end of the service horizon."""
    return simulation_slots + deadline_window


def schedule_aggregate_demand(
    events: Sequence[URLLCEvent],
    simulation_slots: int,
    slot_capacity: int,
    deadline_window: int,
) -> dict:
    """Serve requests in their arrival slot without queueing."""
    _validate_scheduler_inputs(
        events,
        simulation_slots,
        slot_capacity,
        deadline_window,
    )

    service_horizon_slots = _capacity_horizon(
        simulation_slots,
        deadline_window,
    )

    successful_ids: set[int] = set()
    capacity_rejection_ids: set[int] = set()
    immediate_rejection_ids: set[int] = set()
    deadline_miss_ids: set[int] = set()
    unresolved_ids: set[int] = set()

    scheduled_resources = 0

    remaining_capacity = {
        slot: slot_capacity
        for slot in range(simulation_slots)
    }

    for event in sorted(
        events,
        key=lambda e: (e.arrival_time, e.event_id),
    ):
        if event.resource_demand > slot_capacity:
            capacity_rejection_ids.add(event.event_id)
            continue

        available = remaining_capacity[event.arrival_time]

        if event.resource_demand <= available:
            successful_ids.add(event.event_id)
            remaining_capacity[event.arrival_time] -= (
                event.resource_demand
            )
            scheduled_resources += event.resource_demand
        else:
            # This policy never defers rejected requests.
            immediate_rejection_ids.add(event.event_id)

    return _make_metrics(
        events=events,
        successful_ids=successful_ids,
        capacity_rejection_ids=capacity_rejection_ids,
        immediate_rejection_ids=immediate_rejection_ids,
        deadline_miss_ids=deadline_miss_ids,
        unresolved_ids=unresolved_ids,
        scheduled_resource_units=scheduled_resources,
        service_horizon_slots=service_horizon_slots,
        slot_capacity=slot_capacity,
    )


def schedule_deadline_aware_edf(
    events: Sequence[URLLCEvent],
    simulation_slots: int,
    slot_capacity: int,
    deadline_window: int,
) -> dict:
    """Schedule feasible requests using earliest-deadline-first."""
    _validate_scheduler_inputs(
        events,
        simulation_slots,
        slot_capacity,
        deadline_window,
    )

    service_horizon_slots = _capacity_horizon(
        simulation_slots,
        deadline_window,
    )

    successful_ids: set[int] = set()
    capacity_rejection_ids: set[int] = set()
    immediate_rejection_ids: set[int] = set()
    deadline_miss_ids: set[int] = set()
    unresolved_ids: set[int] = set()

    scheduled_resources = 0

    # Requests larger than one slot's capacity can never be served.
    feasible_events = []

    for event in events:
        if event.resource_demand > slot_capacity:
            capacity_rejection_ids.add(event.event_id)
        else:
            feasible_events.append(event)

    arrivals_by_slot: dict[int, list[URLLCEvent]] = {}

    for event in feasible_events:
        arrivals_by_slot.setdefault(
            event.arrival_time, []
        ).append(event)

    pending: list[URLLCEvent] = []

    for slot in range(service_horizon_slots):
        # Release requests arriving in this slot.
        pending.extend(arrivals_by_slot.get(slot, []))

        # Deadlines are inclusive: deadline == slot remains eligible.
        expired = [
            event for event in pending
            if event.deadline < slot
        ]

        for event in expired:
            deadline_miss_ids.add(event.event_id)

        pending = [
            event for event in pending
            if event.deadline >= slot
        ]

        # Deterministic EDF tie-breaking.
        pending.sort(
            key=lambda e: (
                e.deadline,
                e.arrival_time,
                e.event_id,
            )
        )

        remaining_capacity = slot_capacity
        deferred: list[URLLCEvent] = []

        for event in pending:
            if event.resource_demand <= remaining_capacity:
                successful_ids.add(event.event_id)
                remaining_capacity -= event.resource_demand
                scheduled_resources += event.resource_demand
            else:
                deferred.append(event)

        pending = deferred

    # Classify requests left after the final service slot.
    for event in pending:
        if event.deadline >= service_horizon_slots:
            unresolved_ids.add(event.event_id)
        else:
            deadline_miss_ids.add(event.event_id)

    return _make_metrics(
        events=events,
        successful_ids=successful_ids,
        capacity_rejection_ids=capacity_rejection_ids,
        immediate_rejection_ids=immediate_rejection_ids,
        deadline_miss_ids=deadline_miss_ids,
        unresolved_ids=unresolved_ids,
        scheduled_resource_units=scheduled_resources,
        service_horizon_slots=service_horizon_slots,
        slot_capacity=slot_capacity,
    )


def _make_metrics(
    events: Sequence[URLLCEvent],
    successful_ids: set[int],
    capacity_rejection_ids: set[int],
    immediate_rejection_ids: set[int],
    deadline_miss_ids: set[int],
    unresolved_ids: set[int],
    scheduled_resource_units: int,
    service_horizon_slots: int,
    slot_capacity: int,
) -> dict:
    """Calculate metrics and enforce mutually exclusive outcomes."""
    event_ids = {event.event_id for event in events}

    outcome_sets = {
        "successful": successful_ids,
        "capacity_rejections": capacity_rejection_ids,
        "immediate_rejections": immediate_rejection_ids,
        "deadline_misses": deadline_miss_ids,
        "unresolved": unresolved_ids,
    }

    classified_ids: set[int] = set()

    for category, ids in outcome_sets.items():
        if not ids.issubset(event_ids):
            raise ValueError(
                f"{category} contains unknown event IDs"
            )

        if classified_ids.intersection(ids):
            raise ValueError(
                f"Event IDs appear in multiple outcome categories: "
                f"{category}"
            )

        classified_ids.update(ids)

    if classified_ids != event_ids:
        missing = event_ids - classified_ids
        raise ValueError(
            f"Some events have no outcome classification: {missing}"
        )

    event_count = len(events)

    successful = len(successful_ids)
    capacity_rejections = len(capacity_rejection_ids)
    immediate_rejections = len(immediate_rejection_ids)
    deadline_misses = len(deadline_miss_ids)
    unresolved = len(unresolved_ids)

    capacity_units = slot_capacity * service_horizon_slots

    def rate(count: int) -> float:
        return count / event_count if event_count else 0.0

    return {
        "event_count": event_count,
        "successful_events": successful,
        "deadline_misses": deadline_misses,
        "capacity_rejections": capacity_rejections,
        "immediate_rejections": immediate_rejections,
        "unresolved_events": unresolved,
        "scheduled_resource_units": scheduled_resource_units,
        "capacity_resource_units": capacity_units,
        "event_success_rate": rate(successful),
        "deadline_miss_rate": rate(deadline_misses),
        "capacity_rejection_rate": rate(capacity_rejections),
        "immediate_rejection_rate": rate(immediate_rejections),
        "unresolved_rate": rate(unresolved),
        "resource_utilization": (
            scheduled_resource_units / capacity_units
            if capacity_units
            else 0.0
        ),
    }


def run_experiment(
    *,
    run_count: int = RUN_COUNT,
    seeds: Sequence[int] = SEEDS,
    simulation_slots: int = SLOTS_PER_RUN,
    slot_capacity: int = SLOT_CAPACITY,
) -> list[dict]:
    """Run the experiment in memory without writing result files."""
    if (
        isinstance(run_count, bool)
        or not isinstance(run_count, int)
        or run_count <= 0
    ):
        raise ValueError("run_count must be a positive integer")

    if len(seeds) != run_count:
        raise ValueError(
            "the number of seeds must equal run_count"
        )

    if len(set(seeds)) != len(seeds) or any(
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or seed < 0
        for seed in seeds
    ):
        raise ValueError(
            "seeds must be unique non-negative integers"
        )

    if (
        isinstance(simulation_slots, bool)
        or not isinstance(simulation_slots, int)
        or simulation_slots <= 0
    ):
        raise ValueError(
            "simulation_slots must be a positive integer"
        )

    if (
        isinstance(slot_capacity, bool)
        or not isinstance(slot_capacity, int)
        or slot_capacity <= 0
    ):
        raise ValueError(
            "slot_capacity must be a positive integer"
        )

    rows: list[dict] = []

    for level in TRAFFIC_LEVELS:
        config = preset_config(
            level,
            simulation_time=simulation_slots,
        )

        for run, seed in enumerate(seeds):
            events = generate_urllc_traffic(config, seed)

            for policy, scheduler in (
                ("aggregate_demand", schedule_aggregate_demand),
                ("deadline_aware_edf", schedule_deadline_aware_edf),
            ):
                metrics = scheduler(
                    events,
                    simulation_slots=simulation_slots,
                    slot_capacity=slot_capacity,
                    deadline_window=config.deadline,
                )

                rows.append({
                    "traffic_level": level,
                    "arrival_rate": config.arrival_rate,
                    "policy": policy,
                    "run": run,
                    "seed": seed,
                    "simulation_slots": simulation_slots,
                    "service_horizon_slots": _capacity_horizon(
                        simulation_slots,
                        config.deadline,
                    ),
                    "slot_capacity": slot_capacity,
                    **metrics,
                })

    return rows


def save_raw_results(
    rows: Sequence[Mapping],
    output_path: str | Path = RAW_OUTPUT_PATH,
) -> None:
    """Write per-run records only to the separate Realism v2 path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=RAW_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = run_experiment()
    save_raw_results(rows)

    print(
        f"Saved {len(rows)} per-run records to {RAW_OUTPUT_PATH}"
    )
    print(
        "Next, run: python -m analysis.analyze_realism_v2"
    )


if __name__ == "__main__":
    main()

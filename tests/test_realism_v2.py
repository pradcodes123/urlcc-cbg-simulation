"""Tests for the separate realism_v2 scheduling experiment and analysis."""
from __future__ import annotations

import csv
import importlib
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class Event:
    event_id: int
    arrival_time: int
    resource_demand: int
    deadline: int


@pytest.fixture()
def modules(monkeypatch):
    """Provide the documented existing URLLC API without copying project source."""
    src_mod = types.ModuleType("src")
    urllc_mod = types.ModuleType("src.urllc")
    rates = {"low": 0.05, "medium": 0.2, "high": 0.5}

    @dataclass(frozen=True)
    class Config:
        arrival_rate: float
        min_resource_demand: int = 2
        max_resource_demand: int = 8
        deadline: int = 4
        simulation_time: int = 100

    def preset_config(level, simulation_time=100):
        return Config(rates[level], simulation_time=simulation_time)

    def generate_urllc_traffic(config, seed):
        # Stable synthetic fixture: two colliding arrivals and one later arrival.
        return (
            Event(0, 0, 6, 4),
            Event(1, 0, 4, 4),
            Event(2, 1, 2, 5),
        )

    urllc_mod.URLLCEvent = Event
    urllc_mod.preset_config = preset_config
    urllc_mod.generate_urllc_traffic = generate_urllc_traffic
    monkeypatch.setitem(sys.modules, "src", src_mod)
    monkeypatch.setitem(sys.modules, "src.urllc", urllc_mod)
    for name in ("experiments.realism_v2", "analysis.analyze_realism_v2"):
        sys.modules.pop(name, None)
    driver = importlib.import_module("experiments.realism_v2")
    analysis = importlib.import_module("analysis.analyze_realism_v2")
    return driver, analysis


def test_output_schema_and_correct_run_count(modules):
    driver, _ = modules
    rows = driver.run_experiment(run_count=2, seeds=(11, 12), simulation_slots=10)
    assert len(rows) == 3 * 2 * 2
    assert tuple(rows[0].keys()) == driver.RAW_COLUMNS
    assert {(r["traffic_level"], r["policy"]) for r in rows} == {
        (level, policy) for level in driver.TRAFFIC_LEVELS for policy in driver.POLICIES
    }


def test_matched_seeds_and_deterministic_results(modules):
    driver, _ = modules
    first = driver.run_experiment(run_count=2, seeds=(11, 12), simulation_slots=10)
    second = driver.run_experiment(run_count=2, seeds=(11, 12), simulation_slots=10)
    assert first == second
    for level in driver.TRAFFIC_LEVELS:
        for seed in (11, 12):
            pair = [r for r in first if r["traffic_level"] == level and r["seed"] == seed]
            assert {r["policy"] for r in pair} == set(driver.POLICIES)
            assert len({r["event_count"] for r in pair}) == 1



def test_metric_bounds_and_consistency(modules):
    driver, _ = modules
    rows = driver.run_experiment(
        run_count=1, seeds=(3,), simulation_slots=10
    )

    rate_fields = (
        "event_success_rate",
        "deadline_miss_rate",
        "capacity_rejection_rate",
        "immediate_rejection_rate",
        "unresolved_rate",
        "resource_utilization",
    )

    outcome_fields = (
        "successful_events",
        "deadline_misses",
        "capacity_rejections",
        "immediate_rejections",
        "unresolved_events",
    )

    for row in rows:
        for field in rate_fields:
            assert 0.0 <= row[field] <= 1.0

        assert sum(row[field] for field in outcome_fields) == (
            row["event_count"]
        )

        assert row["service_horizon_slots"] == (
            row["simulation_slots"] + 4
        )

        assert row["scheduled_resource_units"] <= (
            row["capacity_resource_units"]
        )

        if row["event_count"]:
            assert row["event_success_rate"] == pytest.approx(
                row["successful_events"] / row["event_count"]
            )




def test_aggregate_summary_statistics(modules):
    _, analysis = modules
    rows = []

    from experiments.realism_v2 import RAW_COLUMNS

    for run, success in enumerate((0.0, 0.5, 1.0)):
        row = {key: 0 for key in RAW_COLUMNS}
        row.update(
            traffic_level="low",
            policy="aggregate_demand",
            event_success_rate=success,
            deadline_miss_rate=0.0,
            capacity_rejection_rate=0.0,
            immediate_rejection_rate=1.0 - success,
            unresolved_rate=0.0,
            resource_utilization=success / 2,
            arrival_rate=0.05,
            run=run,
            seed=run,
        )
        rows.append(row)

    summaries = analysis.aggregate_rows(rows)

    success = next(
        r for r in summaries
        if r["traffic_level"] == "low"
        and r["policy"] == "aggregate_demand"
        and r["metric"] == "event_success_rate"
    )

    assert success["n"] == 3
    assert success["mean"] == pytest.approx(0.5)
    assert success["std_dev"] == pytest.approx(0.5)
    assert success["ci95_low"] < success["mean"] < success["ci95_high"]



def test_raw_file_matches_processed_summary(modules, tmp_path):
    driver, analysis = modules
    rows = driver.run_experiment(run_count=2, seeds=(11, 12), simulation_slots=10)
    raw_path = tmp_path / "raw.csv"
    summary_path = tmp_path / "processed.csv"
    driver.save_raw_results(rows, raw_path)
    summaries = analysis.analyze_files(raw_path, summary_path)
    with raw_path.open(newline="", encoding="utf-8") as f:
        raw = list(csv.DictReader(f))
    with summary_path.open(newline="", encoding="utf-8") as f:
        saved = list(csv.DictReader(f))
    assert len(raw) == len(rows)
    assert len(saved) == len(summaries) == 36
    for saved_row, returned in zip(saved, summaries):
        assert saved_row["traffic_level"] == returned["traffic_level"]
        assert saved_row["policy"] == returned["policy"]
        assert saved_row["metric"] == returned["metric"]
        assert int(saved_row["n"]) == returned["n"]
        assert float(saved_row["mean"]) == pytest.approx(returned["mean"])


def test_edf_can_defer_request_and_avoid_aggregate_collision(modules):
    driver, _ = modules
    events = (
        Event(0, 0, 6, 4),
        Event(1, 0, 4, 4),
    )
    baseline = driver.schedule_aggregate_demand(
        events, simulation_slots=10, slot_capacity=8, deadline_window=4)
    edf = driver.schedule_deadline_aware_edf(
        events, simulation_slots=10, slot_capacity=8, deadline_window=4)
    assert edf["successful_events"] >= baseline["successful_events"]


def test_invalid_seed_count_rejected(modules):
    driver, _ = modules
    with pytest.raises(ValueError):
        driver.run_experiment(run_count=2, seeds=(1,), simulation_slots=10)


def test_duplicate_event_ids_rejected(modules):
    driver, _ = modules
    events = (Event(0, 0, 2, 1), Event(0, 0, 3, 1))
    with pytest.raises(ValueError):
        driver.schedule_deadline_aware_edf(
            events, simulation_slots=5, slot_capacity=8, deadline_window=1)


def test_out_of_window_arrival_rejected(modules):
    driver, _ = modules
    events = (Event(0, 5, 2, 6),)

    with pytest.raises(
        ValueError,
        match="All event arrivals must fall within the simulation window",
    ):
        driver.schedule_deadline_aware_edf(
            events,
            simulation_slots=5,
            slot_capacity=8,
            deadline_window=2,
        )

    with pytest.raises(
        ValueError,
        match="All event arrivals must fall within the simulation window",
    ):
        driver.schedule_aggregate_demand(
            events,
            simulation_slots=5,
            slot_capacity=8,
            deadline_window=2,
        )
        

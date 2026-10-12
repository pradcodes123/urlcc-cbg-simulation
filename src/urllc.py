"""Synthetic URLLC traffic for the URLLC-preemption / CBG study.

A controlled traffic abstraction: Poisson arrivals discretised to simulation
slots, each event carrying an abstract resource demand and a deadline. There is
no MAC/RLC/PDCP, no packets, no scheduler and no physical layer here, and no
preemption logic: the next module consumes these events.

Presets (low / medium / high) are simulation scenarios only. They are NOT
standardized 5G traffic classes, and they differ only in arrival rate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Tuple

import numpy as np

TrafficLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class URLLCEvent:
    """One URLLC arrival (all times are in discrete slots)."""

    event_id: int
    arrival_time: int       # slot in which the event arrives
    resource_demand: int     # requested abstract eligible-RE units
    deadline: int           # absolute slot: arrival_time + relative deadline


@dataclass(frozen=True)
class URLLCConfig:
    """Parameters of the synthetic URLLC traffic."""

    arrival_rate: float          # mean arrivals per slot (Poisson)
    min_resource_demand: int     # inclusive
    max_resource_demand: int     # inclusive
    deadline: int                # relative latency budget, in slots
    simulation_time: int         # number of slots: [0, simulation_time)

    def __post_init__(self) -> None:
        rate = self.arrival_rate
        if (isinstance(rate, bool) or not isinstance(rate, (int, float))
                or not math.isfinite(rate) or rate <= 0):
            raise ValueError(f"arrival_rate must be a positive finite number, got {rate!r}")
        for name in ("min_resource_demand", "max_resource_demand",
                     "deadline", "simulation_time"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")
        if self.max_resource_demand < self.min_resource_demand:
            raise ValueError("max_resource_demand must be >= min_resource_demand")


def preset_config(level: TrafficLevel, simulation_time: int = 100) -> URLLCConfig:
    """Return the preset config for 'low', 'medium' or 'high' load.

    Only the arrival rate differs between levels.
    """
    rates = {"low": 0.05, "medium": 0.2, "high": 0.5}
    if level not in rates:
        raise ValueError(f"Unknown traffic level {level!r}; expected one of {list(rates)}")
    return URLLCConfig(arrival_rate=rates[level], min_resource_demand=2,
                       max_resource_demand=8, deadline=4,
                       simulation_time=simulation_time)



def generate_urllc_traffic(
        config: URLLCConfig,
        seed: int,
        arrival_pattern: str | None = None,
    ) -> Tuple[URLLCEvent, ...]:
        """Generate reproducible URLLC traffic.

        With arrival_pattern=None, preserve the original Poisson process.

        Explicit patterns use the same fixed event count and event demands:
        - poisson: random times, conditional on the fixed event count
        - evenly_spaced: arrivals spread uniformly over the observation window
        - bursty: arrivals grouped around two burst centres
        """
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
            raise ValueError(f"seed must be a non-negative integer, got {seed!r}")

        if arrival_pattern is None:
            rng = np.random.default_rng(seed)
            slots = []
            t = 0.0

            while True:
                t += rng.exponential(1.0 / config.arrival_rate)
                if t >= config.simulation_time:
                    break
                slots.append(int(t))

            demands = rng.integers(
                config.min_resource_demand,
                config.max_resource_demand + 1,
                size=len(slots),
            )

            return tuple(
                URLLCEvent(
                    event_id=i,
                    arrival_time=slot,
                    resource_demand=int(demand),
                    deadline=slot + config.deadline,
                )
                for i, (slot, demand) in enumerate(zip(slots, demands))
            )

        supported = {"poisson", "evenly_spaced", "bursty"}
        if arrival_pattern not in supported:
            raise ValueError(
                f"Unknown arrival_pattern {arrival_pattern!r}; "
                f"expected one of {sorted(supported)}"
            )

        # Explicit patterns have identical event counts across conditions.
        count = int(round(config.arrival_rate * config.simulation_time))

        if count == 0:
            return ()

        # Independent streams keep event demands matched across patterns.
        time_rng = np.random.default_rng([seed, 0x41525249])
        demand_rng = np.random.default_rng([seed, 0x44454D41])

        duration = config.simulation_time

        if arrival_pattern == "poisson":
            # Conditional Poisson arrival times: uniform over the window
            # given the fixed number of arrivals.
            times = np.floor(
                time_rng.uniform(0, duration, size=count)
            ).astype(int)

        elif arrival_pattern == "evenly_spaced":
            times = np.floor(
                (np.arange(count) + 0.5) * duration / count
            ).astype(int)
            times = np.clip(times, 0, duration - 1)

        else:  # bursty
            # Assign events as evenly as possible to two burst centres,
            # then add small random timing jitter.
            burst_count = min(2, count)
            burst_ids = np.arange(count) % burst_count
            centres = (burst_ids + 0.5) * duration / burst_count
            jitter = time_rng.normal(loc=0.0, scale=0.75, size=count)
            times = np.floor(centres + jitter).astype(int)
            times = np.clip(times, 0, duration - 1)

        demands = demand_rng.integers(
            config.min_resource_demand,
            config.max_resource_demand + 1,
            size=count,
        )

        # Keep event IDs tied to matched demands, not arrival order.
        events = [
            URLLCEvent(
                event_id=i,
                arrival_time=int(times[i]),
                resource_demand=int(demands[i]),
                deadline=int(times[i]) + config.deadline,
            )
            for i in range(count)
        ]

        return tuple(sorted(events, key=lambda event: (
            event.arrival_time, event.event_id
        )))


if __name__ == "__main__":
    for level in ("low", "medium", "high"):
        cfg = preset_config(level, simulation_time=100)
        events = generate_urllc_traffic(cfg, seed=42)
        mean_d = sum(e.resource_demand for e in events) / len(events) if events else 0.0
        print(f"{level:>6}: rate={cfg.arrival_rate}/slot, {len(events)} events "
              f"(expected ~{cfg.arrival_rate * cfg.simulation_time:.0f}), "
              f"mean demand={mean_d:.1f}")
        for e in events[:3]:
            print(f"        {e}")
"""Slot-based, deadline-aware scheduling of synthetic URLLC requests.

A controlled scheduling abstraction, NOT a 5G MAC scheduler: no RLC/PDCP, no
HARQ, no channel or physical-layer behaviour, and no preemption of eMBB
resources. It only decides *whether and when* each URLLC request can be served
given a fixed resource capacity per slot.

Conventions
-----------
Time is a sequence of discrete slots ``0 .. simulation_time - 1``; every slot
offers ``slot_capacity`` integer resource units.

* Arrival: an event may be served from slot ``arrival_time`` on, never before.
* Deadline (INCLUSIVE, absolute slot index): an event is eligible in the slots
  ``arrival_time <= slot <= deadline``. Completing in slot ``deadline`` is on
  time; the first slot after it is too late.
* Atomic service: an event must receive its ENTIRE ``resource_demand`` within a
  single slot. It is never partially served, so no resources are ever wasted on
  an event that later fails.
* Priority: earliest-deadline-first (EDF). Pending events are considered in the
  order ``(deadline, arrival_time, event_id)``, which makes ties deterministic.
  In each slot the scheduler walks that order and serves every event that still
  fits into the remaining capacity; an event that does not fit stays pending and
  does not block later events (so a large event cannot starve the slot's spare
  capacity, although it can itself be starved until its deadline).
* ``completion_time`` is the slot in which the event was served.

Failure reasons (``SchedulingResult.failure_reason``)
-----------------------------------------------------
``"insufficient_capacity"``  demand > slot_capacity, so the event can never be
                             served atomically (checked first, regardless of timing).
``"deadline_missed"``        the event was feasible but not served by its deadline
                             (and that deadline lies inside the simulated slots).
``"simulation_ended"``       the simulation ended while the event could still have
                             been served (it arrives at or after ``simulation_time``
                             or its deadline lies beyond the last simulated slot).

The scheduler is deterministic and uses no random numbers. Metrics (success rate,
totals, deadline misses, ...) are intentionally not computed here; every figure
can be derived from the returned results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from src.urllc import URLLCEvent

POLICY_EDF = "earliest_deadline_first"
SUPPORTED_POLICIES = (POLICY_EDF,)

FAIL_INSUFFICIENT_CAPACITY = "insufficient_capacity"
FAIL_DEADLINE_MISSED = "deadline_missed"
FAIL_SIMULATION_ENDED = "simulation_ended"
FAILURE_REASONS = (FAIL_INSUFFICIENT_CAPACITY, FAIL_DEADLINE_MISSED, FAIL_SIMULATION_ENDED)


def _is_int(value: object) -> bool:
    """True for real integers; ``bool`` is deliberately not accepted."""
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class SchedulerConfig:
    """Scheduler parameters."""

    slot_capacity: int                 # resource units available per slot (> 0)
    simulation_time: int               # number of slots: [0, simulation_time) (> 0)
    policy: str = POLICY_EDF           # only "earliest_deadline_first" is supported

    def __post_init__(self) -> None:
        for name in ("slot_capacity", "simulation_time"):
            value = getattr(self, name)
            if not _is_int(value) or value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")
        if self.policy not in SUPPORTED_POLICIES:
            raise ValueError(
                f"Unsupported policy {self.policy!r}; expected one of {list(SUPPORTED_POLICIES)}")


@dataclass(frozen=True)
class SchedulingResult:
    """Outcome of one URLLC event (times are slot indices)."""

    event_id: int
    arrival_time: int
    deadline: int                      # absolute, inclusive
    resource_demand: int
    scheduled_resources: int           # resource_demand if served, else 0
    completion_time: Optional[int]     # slot in which it was served, None if not served
    success: bool
    failure_reason: Optional[str]      # None on success, otherwise one of FAILURE_REASONS

    def __post_init__(self) -> None:
        if self.success:
            ok = (self.completion_time is not None and self.failure_reason is None
                  and self.scheduled_resources == self.resource_demand)
        else:
            ok = (self.completion_time is None and self.failure_reason in FAILURE_REASONS
                  and self.scheduled_resources == 0)
        if not ok:
            raise ValueError(f"inconsistent scheduling result for event {self.event_id}")


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def _validate_events(events: Iterable[URLLCEvent]) -> list[URLLCEvent]:
    """Return the events sorted by (arrival_time, event_id) after validating them.

    Raises:
        TypeError: ``events`` is not an iterable collection, or an item is not a
            ``URLLCEvent``.
        ValueError: a non-integer or out-of-range field, a deadline before the
            arrival, or duplicate event IDs.
    """
    if isinstance(events, (str, bytes)):
        raise TypeError("events must be a collection of URLLCEvent, not a string")
    try:
        items = list(events)
    except TypeError:
        raise TypeError(f"events must be an iterable of URLLCEvent, got {type(events).__name__}")

    seen: set[int] = set()
    for ev in items:
        if not isinstance(ev, URLLCEvent):
            raise TypeError(f"every event must be a URLLCEvent, got {type(ev).__name__}")
        for name in ("event_id", "arrival_time", "resource_demand", "deadline"):
            if not _is_int(getattr(ev, name)):
                raise ValueError(f"event {ev.event_id!r}: {name} must be an integer, "
                                 f"got {getattr(ev, name)!r}")
        if ev.arrival_time < 0:
            raise ValueError(f"event {ev.event_id}: arrival_time must be >= 0")
        if ev.resource_demand <= 0:
            raise ValueError(f"event {ev.event_id}: resource_demand must be > 0")
        if ev.deadline < ev.arrival_time:
            raise ValueError(f"event {ev.event_id}: deadline {ev.deadline} is before "
                             f"arrival_time {ev.arrival_time}")
        if ev.event_id in seen:
            raise ValueError(f"duplicate event_id {ev.event_id}")
        seen.add(ev.event_id)
    return sorted(items, key=lambda e: (e.arrival_time, e.event_id))


# --------------------------------------------------------------------------
# Scheduling
# --------------------------------------------------------------------------
def _served(ev: URLLCEvent, slot: int) -> SchedulingResult:
    return SchedulingResult(ev.event_id, ev.arrival_time, ev.deadline, ev.resource_demand,
                            ev.resource_demand, slot, True, None)


def _failed(ev: URLLCEvent, reason: str) -> SchedulingResult:
    return SchedulingResult(ev.event_id, ev.arrival_time, ev.deadline, ev.resource_demand,
                            0, None, False, reason)


def _priority(ev: URLLCEvent) -> tuple[int, int, int]:
    """EDF order with deterministic tie-breaks: deadline, arrival, event ID."""
    return (ev.deadline, ev.arrival_time, ev.event_id)


def schedule_urllc_events(events: Iterable[URLLCEvent],
                          config: SchedulerConfig) -> list[SchedulingResult]:
    """Schedule URLLC events slot by slot (see the module docstring for the rules).

    Args:
        events: ``URLLCEvent`` objects (any iterable, possibly empty).
        config: scheduler parameters.

    Returns:
        One ``SchedulingResult`` per input event, ordered by
        ``(arrival_time, event_id)``. Invalid or infeasible events are reported
        as failures, never silently dropped.

    Raises:
        TypeError / ValueError: invalid ``config`` type or invalid events.
    """
    if not isinstance(config, SchedulerConfig):
        raise TypeError(f"config must be a SchedulerConfig, got {type(config).__name__}")
    ordered = _validate_events(events)

    results: dict[int, SchedulingResult] = {}
    pending: list[URLLCEvent] = []
    next_arrival = 0                       # index of the first event not yet released

    for slot in range(config.simulation_time):
        # Release events that have arrived (never earlier than their arrival slot).
        while next_arrival < len(ordered) and ordered[next_arrival].arrival_time <= slot:
            ev = ordered[next_arrival]
            next_arrival += 1
            if ev.resource_demand > config.slot_capacity:
                results[ev.event_id] = _failed(ev, FAIL_INSUFFICIENT_CAPACITY)
            else:
                pending.append(ev)

        # The deadline is inclusive: an event is expired only after its deadline slot.
        alive = []
        for ev in pending:
            if ev.deadline < slot:
                results[ev.event_id] = _failed(ev, FAIL_DEADLINE_MISSED)
            else:
                alive.append(ev)

        # Serve in EDF order; events that do not fit stay pending (atomic service).
        remaining = config.slot_capacity
        pending = []
        for ev in sorted(alive, key=_priority):
            if ev.resource_demand <= remaining:
                remaining -= ev.resource_demand
                results[ev.event_id] = _served(ev, slot)
            else:
                pending.append(ev)

    # Events still pending, or arriving after the last slot, were never served.
    last_slot = config.simulation_time - 1
    for ev in pending:
        reason = FAIL_DEADLINE_MISSED if ev.deadline <= last_slot else FAIL_SIMULATION_ENDED
        results[ev.event_id] = _failed(ev, reason)
    for ev in ordered[next_arrival:]:
        reason = (FAIL_INSUFFICIENT_CAPACITY if ev.resource_demand > config.slot_capacity
                  else FAIL_SIMULATION_ENDED)
        results[ev.event_id] = _failed(ev, reason)

    return [results[ev.event_id] for ev in ordered]
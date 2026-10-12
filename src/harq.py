"""A deterministic, simplified HARQ-style protocol state abstraction.

Each attempt occupies one slot: an attempt starting in slot ``s`` completes
in slot ``s + 1``. After a failed attempt, the next attempt starts after both
the configured feedback delay and retransmission delay have elapsed:

    next_start = completion_slot + feedback_delay_slots + retransmission_delay_slots

``total_delay_slots`` is measured from ``initial_slot`` to the final attempt's
``completion_slot`` (so a single attempt has a delay of one slot).

This is not a complete or standards-compliant NR HARQ implementation. It does
not model soft combining, incremental redundancy, redundancy versions, actual
ACK/NACK transmissions, resource scheduling, or a wireless channel. Attempt
outcomes are supplied explicitly by the caller; this module uses no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real
from typing import Hashable, Sequence


@dataclass(frozen=True)
class HARQConfig:
    """Timing and retry-limit configuration for the simplified HARQ model."""

    max_attempts: int
    feedback_delay_slots: int
    retransmission_delay_slots: int

    def __post_init__(self) -> None:
        _require_integer(self.max_attempts, "max_attempts")
        _require_integer(self.feedback_delay_slots, "feedback_delay_slots")
        _require_integer(self.retransmission_delay_slots, "retransmission_delay_slots")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        if self.feedback_delay_slots < 0:
            raise ValueError("feedback_delay_slots must be non-negative")
        if self.retransmission_delay_slots < 0:
            raise ValueError("retransmission_delay_slots must be non-negative")


@dataclass(frozen=True)
class HARQAttempt:
    """Record of one attempt; completion is one slot after its start."""

    attempt_number: int
    start_slot: int
    completion_slot: int
    success: bool
    resource_cost: float


@dataclass(frozen=True)
class HARQResult:
    """Outcome and accounting for one transmission group."""

    entity_id: Hashable
    attempts: tuple[HARQAttempt, ...]
    delivered: bool
    total_resource_cost: float
    total_delay_slots: int
    failure_reason: str | None


def simulate_harq(
    entity_id: Hashable,
    initial_slot: int,
    resource_cost: Real,
    attempt_outcomes: Sequence[bool],
    config: HARQConfig,
) -> HARQResult:
    """Simulate attempts using caller-provided Boolean outcomes.

    Outcomes are consumed only as attempts are made. If success is not reached,
    ``failure_reason`` is ``"max_attempts_reached"`` when the configured attempt
    limit is reached, or ``"outcomes_exhausted"`` when no outcome remains first.
    A failed attempt on the final permitted attempt takes precedence over outcome
    exhaustion because the retry limit has already been reached.
    """
    _validate_entity_id(entity_id)
    _require_integer(initial_slot, "initial_slot")
    if initial_slot < 0:
        raise ValueError("initial_slot must be non-negative")
    _validate_resource_cost(resource_cost)
    if not isinstance(config, HARQConfig):
        raise TypeError("config must be a HARQConfig instance")
    if isinstance(attempt_outcomes, (str, bytes)) or not isinstance(attempt_outcomes, Sequence):
        raise TypeError("attempt_outcomes must be a sequence of Boolean values")
    if any(type(outcome) is not bool for outcome in attempt_outcomes):
        raise TypeError("each attempt outcome must be a Boolean (True or False)")

    attempts: list[HARQAttempt] = []
    start_slot = initial_slot
    delivered = False
    failure_reason: str | None = None

    for index, success in enumerate(attempt_outcomes[: config.max_attempts], start=1):
        completion_slot = start_slot + 1
        attempts.append(
            HARQAttempt(
                attempt_number=index,
                start_slot=start_slot,
                completion_slot=completion_slot,
                success=success,
                resource_cost=float(resource_cost),
            )
        )
        if success:
            delivered = True
            break
        if index == config.max_attempts:
            failure_reason = "max_attempts_reached"
            break
        if index >= len(attempt_outcomes):
            failure_reason = "outcomes_exhausted"
            break
        start_slot = completion_slot + config.feedback_delay_slots + config.retransmission_delay_slots

    if not attempts:
        failure_reason = "outcomes_exhausted"
        total_delay_slots = 0
    else:
        total_delay_slots = attempts[-1].completion_slot - initial_slot
        if not delivered and failure_reason is None:
            # This covers a sequence longer than zero but limited by max_attempts.
            failure_reason = "max_attempts_reached"

    return HARQResult(
        entity_id=entity_id,
        attempts=tuple(attempts),
        delivered=delivered,
        total_resource_cost=sum(attempt.resource_cost for attempt in attempts),
        total_delay_slots=total_delay_slots,
        failure_reason=failure_reason,
    )


def _require_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer (Boolean values are not accepted)")


def _validate_entity_id(entity_id: object) -> None:
    if entity_id is None:
        raise ValueError("entity_id must not be None")
    try:
        hash(entity_id)
    except TypeError as exc:
        raise TypeError("entity_id must be hashable") from exc
    if isinstance(entity_id, Real) and not isinstance(entity_id, bool):
        if not math.isfinite(float(entity_id)):
            raise ValueError("numeric entity_id values must be finite")


def _validate_resource_cost(resource_cost: object) -> None:
    if isinstance(resource_cost, bool) or not isinstance(resource_cost, Real):
        raise TypeError("resource_cost must be a finite non-negative number")
    if not math.isfinite(float(resource_cost)):
        raise ValueError("resource_cost must be finite")
    if resource_cost < 0:
        raise ValueError("resource_cost must be non-negative")

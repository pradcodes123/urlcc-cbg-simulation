"""Basic per-run metrics for the URLLC-preemption / CBG study.

Pure conversion of preemption, decoding and retransmission outputs into
numbers. No physical-layer throughput, BLER, statistics, plotting or
experiment logic.

The eMBB delivery-efficiency metric is a normalized performance proxy based
on retransmission resource consumption. It is not physical-layer throughput
in bits/s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.decoder import CBGDecodingResult
from src.retransmission import RetransmissionRequest


@dataclass(frozen=True)
class SimulationMetrics:
    """Metrics of one simulation run."""

    preempted_positions: int
    total_embb_positions: int
    preemption_fraction: float
    affected_cb_count: int
    affected_cbg_count: int
    failed_cbg_count: int
    retransmission_positions: int
    retransmission_overhead: float
    embb_delivery_efficiency: float


def _check_int(name: str, value: object) -> None:
    """Validate that a value is an integer, excluding booleans."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {value!r}")


def calculate_metrics(
        total_embb_positions: int,
        preempted_positions: int,
        affected_cb_ids: Iterable[int],
        affected_cbg_ids: Iterable[int],
        decoding_results: Iterable[CBGDecodingResult],
        retransmission_requests: Iterable[RetransmissionRequest],
) -> SimulationMetrics:
    """Compute per-run simulation metrics.

    The delivery-efficiency metric is defined as:

        total_embb_positions
        ------------------------------------------
        total_embb_positions + retransmission_positions

    It represents the fraction of the modeled eMBB transmission resource
    that corresponds to the original eMBB data rather than retransmission
    resource consumption.

    This is a normalized performance proxy, not physical-layer throughput
    in bits/s.
    """
    _check_int("total_embb_positions", total_embb_positions)
    _check_int("preempted_positions", preempted_positions)

    if total_embb_positions <= 0:
        raise ValueError(
            f"total_embb_positions must be > 0, "
            f"got {total_embb_positions}"
        )

    if preempted_positions < 0:
        raise ValueError(
            f"preempted_positions must be >= 0, "
            f"got {preempted_positions}"
        )

    if preempted_positions > total_embb_positions:
        raise ValueError(
            f"preempted_positions ({preempted_positions}) exceeds "
            f"total_embb_positions ({total_embb_positions})"
        )

    retx_positions = sum(
        request.num_positions
        for request in retransmission_requests
    )

    delivery_efficiency = (
        total_embb_positions
        / (total_embb_positions + retx_positions)
    )

    return SimulationMetrics(
        preempted_positions=preempted_positions,
        total_embb_positions=total_embb_positions,
        preemption_fraction=(
            preempted_positions / total_embb_positions
        ),
        affected_cb_count=len(set(affected_cb_ids)),
        affected_cbg_count=len(set(affected_cbg_ids)),
        failed_cbg_count=sum(
            1 for result in decoding_results
            if not result.success
        ),
        retransmission_positions=retx_positions,
        retransmission_overhead=(
            retx_positions / total_embb_positions
        ),
        embb_delivery_efficiency=delivery_efficiency,
    )
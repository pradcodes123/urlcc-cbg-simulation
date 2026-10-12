
"""Per-run metrics for the URLLC-preemption / CBG study.

Delivery accounting uses logical eMBB positions, not information bits.
The delivered-position rate is a model-level metric per configured
observation slot; it is not physical-layer throughput in bits/s.
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

    # Defaults preserve compatibility with older constructors.
    initial_failed_cbg_count: int = 0
    harq_recovered_cbg_count: int = 0
    initial_cbg_failure_rate: float = 0.0
    residual_bler: float = 0.0
    final_delivery_success_rate: float = 0.0
    harq_retransmission_count: int = 0

    # Logical data accounting; not a bit/s throughput measurement.
    delivered_embb_positions: int = 0
    embb_delivery_rate_per_slot: float = 0.0


def _check_int(name: str, value: object) -> None:
    """Validate an integer, excluding Boolean values."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {value!r}")


def calculate_metrics(
    total_embb_positions: int,
    preempted_positions: int,
    affected_cb_ids: Iterable[int],
    affected_cbg_ids: Iterable[int],
    initial_decoding_results: Iterable[CBGDecodingResult],
    retransmission_requests: Iterable[RetransmissionRequest],
    final_decoding_results: Iterable[CBGDecodingResult] | None = None,
    harq_retransmission_count: int = 0,
    simulation_time_slots: int = 20,
) -> SimulationMetrics:
    """Compute metrics for one simulation run.

    ``embb_delivery_efficiency`` is defined as:

        total_embb_positions /
        (total_embb_positions + retransmission_positions)

    ``delivered_embb_positions`` sums the logical positions belonging to
    CBGs that succeed after HARQ recovery.

    ``embb_delivery_rate_per_slot`` is:

        delivered_embb_positions / simulation_time_slots

    The rate uses logical positions per configured observation slot. It is
    not throughput in bits/s and does not model a shared eMBB transmission
    schedule or actual NR resource-element timing.

    If ``final_decoding_results`` is omitted, initial decoding results are
    also used as final results for backward compatibility.
    """
    _check_int("total_embb_positions", total_embb_positions)
    _check_int("preempted_positions", preempted_positions)
    _check_int("harq_retransmission_count", harq_retransmission_count)
    _check_int("simulation_time_slots", simulation_time_slots)

    if total_embb_positions <= 0:
        raise ValueError(
            f"total_embb_positions must be > 0, got {total_embb_positions}"
        )

    if not 0 <= preempted_positions <= total_embb_positions:
        raise ValueError(
            "preempted_positions must be between 0 and "
            f"{total_embb_positions}, got {preempted_positions}"
        )

    if harq_retransmission_count < 0:
        raise ValueError("harq_retransmission_count must be >= 0")

    if simulation_time_slots <= 0:
        raise ValueError("simulation_time_slots must be > 0")

    retx_positions = sum(
        request.resource_cost for request in retransmission_requests
    )

    delivery_efficiency = total_embb_positions / (
        total_embb_positions + retx_positions
    )

    initial_results = tuple(initial_decoding_results)
    final_results = (
        initial_results
        if final_decoding_results is None
        else tuple(final_decoding_results)
    )

    if len(initial_results) != len(final_results):
        raise ValueError(
            "Initial and final decoding results must contain "
            "the same number of CBGs"
        )

    initial_by_id = {result.cbg_id: result for result in initial_results}
    final_by_id = {result.cbg_id: result for result in final_results}

    if len(initial_by_id) != len(initial_results):
        raise ValueError("Initial decoding results contain duplicate CBG IDs")

    if len(final_by_id) != len(final_results):
        raise ValueError("Final decoding results contain duplicate CBG IDs")

    if initial_by_id.keys() != final_by_id.keys():
        raise ValueError(
            "Initial and final decoding results must contain the same CBG IDs"
        )

    for result in final_results:
        _check_int("CBG total_positions", result.total_positions)
        if result.total_positions < 0:
            raise ValueError("CBG total_positions must be non-negative")

    initial_failed = sum(
        not result.success for result in initial_by_id.values()
    )
    final_failed = sum(
        not result.success for result in final_by_id.values()
    )

    recovered = sum(
        not initial_by_id[cbg_id].success
        and final_by_id[cbg_id].success
        for cbg_id in initial_by_id
    )

    if any(
        initial_by_id[cbg_id].success and not final_by_id[cbg_id].success
        for cbg_id in initial_by_id
    ):
        raise ValueError(
            "A previously successful CBG cannot fail in this "
            "recovery-only HARQ model"
        )

    n_cbgs = len(initial_results)

    initial_failure_rate = initial_failed / n_cbgs if n_cbgs else 0.0
    residual_bler = final_failed / n_cbgs if n_cbgs else 0.0
    delivery_success_rate = (
        (n_cbgs - final_failed) / n_cbgs if n_cbgs else 0.0
    )

    delivered_positions = sum(
        result.total_positions
        for result in final_results
        if result.success
    )
    delivery_rate = delivered_positions / simulation_time_slots

    return SimulationMetrics(
        preempted_positions=preempted_positions,
        total_embb_positions=total_embb_positions,
        preemption_fraction=preempted_positions / total_embb_positions,
        affected_cb_count=len(set(affected_cb_ids)),
        affected_cbg_count=len(set(affected_cbg_ids)),
        failed_cbg_count=final_failed,
        retransmission_positions=retx_positions,
        retransmission_overhead=retx_positions / total_embb_positions,
        embb_delivery_efficiency=delivery_efficiency,
        initial_failed_cbg_count=initial_failed,
        harq_recovered_cbg_count=recovered,
        initial_cbg_failure_rate=initial_failure_rate,
        residual_bler=residual_bler,
        final_delivery_success_rate=delivery_success_rate,
        harq_retransmission_count=harq_retransmission_count,
        delivered_embb_positions=delivered_positions,
        embb_delivery_rate_per_slot=delivery_rate,
    )

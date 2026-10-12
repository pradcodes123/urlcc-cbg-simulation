"""One complete simulation trial of the URLLC-preemption / CBG study."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from src.cbg import affected_cbg_ids, group_code_blocks
from src.decoder import DecoderConfig, decode_cbgs
from src.embb import EmbbConfig, TransportBlock
from src.metrics import SimulationMetrics, calculate_metrics
from src.preemption import generate_preemption
from src.scheduler import SchedulerConfig, schedule_urllc_events
from src.urllc import URLLCConfig, generate_urllc_traffic

from src.channel import ChannelConfig, generate_channel_samples
from src.harq import HARQConfig, simulate_harq
from src.retransmission import RetransmissionRequest

@dataclass(frozen=True)
class SimulationConfig:
    """All parameters of one simulation trial."""

    embb_config: EmbbConfig
    cbg_count: int
    urllc_config: URLLCConfig
    preemption_pattern: str = "random"
    preemption_fraction: float | None = None
    num_preempt: int | None = None
    decoder_config: DecoderConfig = DecoderConfig()
    scheduler_slot_capacity: int = 16
    urllc_arrival_pattern: str | None = None

    channel_config: ChannelConfig = ChannelConfig(
        mean_snr_db=10.0,
        snr_std_db=2.0,
        min_snr_db=0.0,
        max_snr_db=20.0,
    )
    harq_config: HARQConfig = HARQConfig(
        max_attempts=3,
        feedback_delay_slots=1,
        retransmission_delay_slots=1,
    )

    def __post_init__(self) -> None:
        if isinstance(self.cbg_count, bool) or not isinstance(
            self.cbg_count, int
        ) or self.cbg_count <= 0:
            raise ValueError(
                f"cbg_count must be a positive integer, got {self.cbg_count!r}"
            )

        if isinstance(self.scheduler_slot_capacity, bool) or not isinstance(
            self.scheduler_slot_capacity, int
        ) or self.scheduler_slot_capacity <= 0:
            raise ValueError("scheduler_slot_capacity must be a positive integer")


def run_simulation(
    config: SimulationConfig,
    seed: int | None = None,
) -> SimulationMetrics:
    """Run one reproducible simulation trial."""

    if seed is None:
        seed = int(np.random.SeedSequence().generate_state(1)[0])

    tb = TransportBlock.from_config(config.embb_config)
    cbgs = group_code_blocks(tb, config.cbg_count)
    events = generate_urllc_traffic(
        config.urllc_config,
        seed,
        arrival_pattern=config.urllc_arrival_pattern,
    )

    # Schedule URLLC events subject to per-slot capacity and deadlines.
    scheduler_config = SchedulerConfig(
        slot_capacity=config.scheduler_slot_capacity,
        simulation_time=config.urllc_config.simulation_time,
    )
    scheduling_results = schedule_urllc_events(events, scheduler_config)

    successful_demand = sum(
        result.scheduled_resources
        for result in scheduling_results
        if result.success
    )

    # Explicit experimental mapping: each successfully served abstract URLLC
    # resource-demand unit consumes one eligible mapped eMBB position.
    # Fixed fraction/count settings remain in control for RQ2/RQ3.
    preemption_kwargs = {
        "preemption_fraction": config.preemption_fraction,
        "num_preempt": config.num_preempt,
    }

    if (
        config.preemption_fraction is None
        and config.num_preempt is None
    ):
        preemption_kwargs["num_preempt"] = min(
            successful_demand,
            len(tb.used_positions()),
        )

    preemption = generate_preemption(
        tb,
        events,
        config.preemption_pattern,
        **preemption_kwargs,
        seed=seed,
    )

    cb_ids = tb.affected_cb_ids(preemption.preempted_positions)
    cbg_ids = affected_cbg_ids(cbgs, cb_ids)

    # Generate a reproducible channel sample for each CBG.
    cbg_ids_all = sorted(cbg.cbg_id for cbg in cbgs)
    channel_samples = generate_channel_samples(
        cbg_ids_all,
        config.channel_config,
        seed=seed + 1,
    )
    snr_by_cbg = {
        sample.entity_id: sample.snr_db
        for sample in channel_samples
    }

    decoded = decode_cbgs(
        tb,
        cbgs,
        preemption.preempted_positions,
        config.decoder_config,
        seed=seed,
        snr_db_by_cbg=snr_by_cbg,
    )
    initial_decoded = tuple(decoded)
    if config.decoder_config.model != "snr":
        raise ValueError(
            "HARQ recovery experiments currently require "
            "the stochastic SNR decoder (model='snr')."
        )

    # Simulate retry outcomes using each CBG's initial failure probability.
    # Retries are independent Bernoulli trials with the same probability;
    # no soft combining or time-varying channel is modelled.
    retry_rng = np.random.default_rng([seed, 0x48415251])
    final_decoded = []
    requests = []
    harq_retransmission_count = 0

    for result in initial_decoded:
        cbg = next(g for g in cbgs if g.cbg_id == result.cbg_id)
        cbg_positions = sum(
            len(tb.get_cb(cb_id).positions)
            for cb_id in cbg.cb_ids
        )

        outcomes = [result.success]
        p_fail = result.failure_probability or 0.0

        if result.damage_ratio <= 0.0:
            final_decoded.append(replace(result, success=True))
            continue

        if not result.success:
            for _ in range(config.harq_config.max_attempts - 1):
                outcomes.append(bool(retry_rng.random() >= p_fail))

        harq_result = simulate_harq(
            entity_id=result.cbg_id,
            initial_slot=0,
            resource_cost=cbg_positions,
            attempt_outcomes=outcomes,
            config=config.harq_config,
        )

        final_decoded.append(
            replace(result, success=harq_result.delivered)
        )

        # Charge only retransmission attempts after the initial transmission.
        retry_count = max(0, len(harq_result.attempts) - 1)
        harq_retransmission_count += retry_count
        if retry_count:
            requests.append(
                RetransmissionRequest(
                    cbg_id=result.cbg_id,
                    num_positions=cbg_positions * retry_count,
                )
            )

    
    return calculate_metrics(
        total_embb_positions=preemption.total_embb_positions,
        preempted_positions=preemption.preempted_count,
        affected_cb_ids=cb_ids,
        affected_cbg_ids=cbg_ids,
        initial_decoding_results=initial_decoded,
        final_decoding_results=tuple(final_decoded),
        retransmission_requests=requests,
        harq_retransmission_count=harq_retransmission_count,
        simulation_time_slots=config.urllc_config.simulation_time,
    )

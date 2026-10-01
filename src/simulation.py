"""One complete simulation trial of the URLLC-preemption / CBG study.

Pure orchestration of the existing modules; no experiment loops, statistics,
output files or research-question logic. ``run_simulation`` is one trial.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.cbg import affected_cbg_ids, group_code_blocks
from src.decoder import DecoderConfig, decode_cbgs
from src.embb import EmbbConfig, TransportBlock
from src.metrics import SimulationMetrics, calculate_metrics
from src.preemption import generate_preemption
from src.retransmission import create_retransmission_requests
from src.urllc import URLLCConfig, generate_urllc_traffic


@dataclass(frozen=True)
class SimulationConfig:
    """All parameters of one simulation trial."""

    embb_config: EmbbConfig
    cbg_count: int                          # N, max CBGs (TS 38.214 §5.1.7.1)
    urllc_config: URLLCConfig
    preemption_pattern: str = "random"
    preemption_fraction: float | None = None
    num_preempt: int | None = None
    decoder_config: DecoderConfig = DecoderConfig()

    def __post_init__(self) -> None:
        c = self.cbg_count
        if isinstance(c, bool) or not isinstance(c, int) or c <= 0:
            raise ValueError(f"cbg_count must be a positive integer, got {c!r}")


def run_simulation(config: SimulationConfig, seed: int | None = None) -> SimulationMetrics:
    """Run one trial; the same config and seed always give identical metrics.

    ``seed`` feeds both the URLLC generator and the random preemption pattern.
    If ``seed`` is None, a fresh random seed is drawn (non-reproducible run).
    """
    if seed is None:
        seed = int(np.random.SeedSequence().generate_state(1)[0])

    tb = TransportBlock.from_config(config.embb_config)
    cbgs = group_code_blocks(tb, config.cbg_count)
    events = generate_urllc_traffic(config.urllc_config, seed)
    preemption = generate_preemption(
        tb, events, config.preemption_pattern,
        preemption_fraction=config.preemption_fraction,
        num_preempt=config.num_preempt, seed=seed)

    cb_ids = tb.affected_cb_ids(preemption.preempted_positions)
    cbg_ids = affected_cbg_ids(cbgs, cb_ids)
    decoded = decode_cbgs(tb, cbgs, preemption.preempted_positions, config.decoder_config)
    requests = create_retransmission_requests(decoded, cbgs, tb)

    return calculate_metrics(
        total_embb_positions=preemption.total_embb_positions,
        preempted_positions=preemption.preempted_count,
        affected_cb_ids=cb_ids, affected_cbg_ids=cbg_ids,
        decoding_results=decoded, retransmission_requests=requests)
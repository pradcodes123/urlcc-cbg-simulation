"""Central default parameters and presets for the URLLC-preemption / CBG study.

Configuration only: no simulation, randomness, file output or experiment logic.
``SimulationConfig`` itself lives in ``src/simulation.py`` and is reused here.
"""

from __future__ import annotations

from src.decoder import DecoderConfig
from src.embb import EmbbConfig
from src.simulation import SimulationConfig
from src.urllc import URLLCConfig

# eMBB transport block
DEFAULT_NUM_CODE_BLOCKS = 8
DEFAULT_CODED_POSITIONS_PER_CB = 36

# CBG grouping and decoding
DEFAULT_CBG_COUNT = 4
DEFAULT_FAILURE_THRESHOLD = 0.25
DEFAULT_DECODER_SNR_DB = 10.0

# URLLC traffic (simulation scenarios, not standardized traffic classes)
DEFAULT_URLLC_DEMAND_MIN = 2
DEFAULT_URLLC_DEMAND_MAX = 8
DEFAULT_URLLC_DEADLINE = 4
DEFAULT_SIMULATION_TIME = 20

LOW_URLLC_ARRIVAL_RATE = 0.05
MEDIUM_URLLC_ARRIVAL_RATE = 0.20
HIGH_URLLC_ARRIVAL_RATE = 0.50


def make_default_config(
    *,
    arrival_rate: float = MEDIUM_URLLC_ARRIVAL_RATE,
    cbg_count: int = DEFAULT_CBG_COUNT,
    preemption_pattern: str = "random",
    preemption_fraction: float | None = 0.10,
    num_preempt: int | None = None,
    simulation_time: int = DEFAULT_SIMULATION_TIME,
) -> SimulationConfig:
    """Build a SimulationConfig from the defaults and the supplied overrides.

    Arguments are passed through unchanged; validation is done by the
    underlying config classes. Note: to use ``num_preempt``, also pass
    ``preemption_fraction=None`` (supplying both is rejected at run time).
    """
    return SimulationConfig(
        embb_config=EmbbConfig(
            num_code_blocks=DEFAULT_NUM_CODE_BLOCKS,
            coded_positions_per_cb=DEFAULT_CODED_POSITIONS_PER_CB,
        ),
        cbg_count=cbg_count,
        urllc_config=URLLCConfig(
            arrival_rate=arrival_rate,
            min_resource_demand=DEFAULT_URLLC_DEMAND_MIN,
            max_resource_demand=DEFAULT_URLLC_DEMAND_MAX,
            deadline=DEFAULT_URLLC_DEADLINE,
            simulation_time=simulation_time,
        ),
        preemption_pattern=preemption_pattern,
        preemption_fraction=preemption_fraction,
        num_preempt=num_preempt,
        decoder_config=DecoderConfig(
            failure_threshold=DEFAULT_FAILURE_THRESHOLD,
            model="snr",
            snr_db=DEFAULT_DECODER_SNR_DB,
        ),
    )


if __name__ == "__main__":
    print(make_default_config())  # configuration only; no simulation is run
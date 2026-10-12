
from config.simulation import make_default_config
from src.embb import EmbbConfig
from src.simulation import SimulationConfig, run_simulation
from src.urllc import URLLCConfig


baseline_config = SimulationConfig(
    embb_config=EmbbConfig(),
    cbg_count=4,
    urllc_config=URLLCConfig(
        arrival_rate=0.2,
        min_resource_demand=2,
        max_resource_demand=8,
        deadline=4,
        simulation_time=20,
    ),
    preemption_pattern="random",
    preemption_fraction=0.0,
)

baseline = run_simulation(baseline_config, seed=42)

print(baseline)
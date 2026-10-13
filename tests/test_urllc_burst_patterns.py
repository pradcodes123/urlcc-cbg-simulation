
import unittest
from experiments.urllc_burst_patterns import (
    select_time_aware_preemption,
    slot_to_symbol,
)
from src.embb import TransportBlock
from src.preemption import generate_preemption
from src.scheduler import SchedulerConfig, schedule_urllc_events
from config.simulation import make_default_config
from src.urllc import generate_urllc_traffic, preset_config



class TestURLLCArrivalPatterns(unittest.TestCase):
    def setUp(self):
        self.config = preset_config("medium", simulation_time=20)

    def test_slot_to_symbol_mapping(self):
        from experiments.urllc_burst_patterns import slot_to_symbol

        self.assertEqual(slot_to_symbol(0, 20, 14), 0)
        self.assertEqual(slot_to_symbol(19, 20, 14), 13)
        self.assertEqual(len({slot_to_symbol(s, 20, 14) for s in range(20)}), 14)    

    def test_same_event_count_across_patterns(self):
        patterns = ("poisson", "evenly_spaced", "bursty")
        counts = [
            len(generate_urllc_traffic(self.config, 42, p))
            for p in patterns
        ]
        self.assertEqual(counts, [4, 4, 4])

    def test_demands_matched_by_event_id(self):
        patterns = ("poisson", "evenly_spaced", "bursty")
        events_by_pattern = {
            p: {
                e.event_id: e.resource_demand
                for e in generate_urllc_traffic(self.config, 42, p)
            }
            for p in patterns
        }
        self.assertEqual(
            events_by_pattern["poisson"],
            events_by_pattern["evenly_spaced"],
        )
        self.assertEqual(
            events_by_pattern["poisson"],
            events_by_pattern["bursty"],
        )

    def test_generation_is_reproducible(self):
        for pattern in ("poisson", "evenly_spaced", "bursty"):
            self.assertEqual(
                generate_urllc_traffic(self.config, 123, pattern),
                generate_urllc_traffic(self.config, 123, pattern),
            )

    def test_arrival_times_differ_across_patterns(self):
        patterns = ("poisson", "evenly_spaced", "bursty")
        times = {
            pattern: tuple(
                e.arrival_time
                for e in generate_urllc_traffic(
                    self.config, 42, pattern
                )
            )
            for pattern in patterns
        }

        self.assertEqual(len(set(times.values())), len(patterns))
    def test_unknown_pattern_rejected(self):
        with self.assertRaises(ValueError):
            generate_urllc_traffic(self.config, 42, "invalid")

    
    def test_slot_to_symbol_mapping(self):
        self.assertEqual(slot_to_symbol(0, 20, 14), 0)
        self.assertEqual(slot_to_symbol(19, 20, 14), 13)
        self.assertEqual(
            len({slot_to_symbol(s, 20, 14) for s in range(20)}),
            14,
        )

    def test_time_aware_positions_are_unique_and_eligible(self):
        config = make_default_config(
            cbg_count=4,
            preemption_fraction=None,
            num_preempt=None,
        )
        events = generate_urllc_traffic(
            config.urllc_config, 42, arrival_pattern="bursty"
        )
        scheduling = schedule_urllc_events(
            events,
            SchedulerConfig(
                slot_capacity=config.scheduler_slot_capacity,
                simulation_time=config.urllc_config.simulation_time,
            ),
        )

        selected = select_time_aware_preemption(
            config, events, scheduling, seed=42
        )
        eligible = set(TransportBlock.from_config(config.embb_config).used_positions())

        self.assertEqual(len(selected), len(set(selected)))
        self.assertTrue(set(selected).issubset(eligible))

        successful_ids = {
            result.event_id for result in scheduling if result.success
        }
        allowed_symbols = {
            slot_to_symbol(
                event.arrival_time,
                config.urllc_config.simulation_time,
                config.embb_config.num_symbols,
            )
            for event in events
            if event.event_id in successful_ids
        }
        self.assertTrue(
            all(position.symbol in allowed_symbols for position in selected)
        )
        


if __name__ == "__main__":
    unittest.main()

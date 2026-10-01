"""Tests for src/urllc.py (synthetic URLLC traffic)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.urllc import (URLLCConfig, generate_urllc_traffic,  # noqa: E402
                       preset_config)

LEVELS = ("low", "medium", "high")


def make_config(**overrides) -> URLLCConfig:
    params = dict(arrival_rate=0.5, min_resource_demand=2, max_resource_demand=8,
                  deadline=4, simulation_time=200)
    params.update(overrides)
    return URLLCConfig(**params)


class TestUrllcTraffic(unittest.TestCase):

    def test_same_seed_gives_identical_events(self):
        cfg = make_config()
        self.assertEqual(generate_urllc_traffic(cfg, seed=42),
                         generate_urllc_traffic(cfg, seed=42))

    def test_different_seeds_can_differ(self):
        cfg = make_config()
        self.assertNotEqual(generate_urllc_traffic(cfg, seed=1),
                            generate_urllc_traffic(cfg, seed=2))

    def test_events_sorted_with_unique_ids(self):
        events = generate_urllc_traffic(make_config(), seed=7)
        self.assertTrue(events)
        times = [e.arrival_time for e in events]
        self.assertEqual(times, sorted(times))
        self.assertEqual([e.event_id for e in events], list(range(len(events))))

    def test_resource_demand_within_bounds(self):
        cfg = make_config(min_resource_demand=3, max_resource_demand=5)
        events = generate_urllc_traffic(cfg, seed=3)
        self.assertTrue(events)
        for e in events:
            self.assertGreaterEqual(e.resource_demand, 3)
            self.assertLessEqual(e.resource_demand, 5)
        # Degenerate range min == max is allowed.
        fixed = generate_urllc_traffic(make_config(min_resource_demand=4,
                                                   max_resource_demand=4), seed=3)
        self.assertTrue(all(e.resource_demand == 4 for e in fixed))

    def test_arrival_times_within_simulation_and_deadline_consistent(self):
        cfg = make_config(simulation_time=50, deadline=6)
        for seed in range(5):
            for e in generate_urllc_traffic(cfg, seed=seed):
                self.assertIsInstance(e.arrival_time, int)
                self.assertGreaterEqual(e.arrival_time, 0)
                self.assertLess(e.arrival_time, cfg.simulation_time)
                self.assertEqual(e.deadline, e.arrival_time + cfg.deadline)

    def test_invalid_configurations_raise(self):
        bad_overrides = [
            dict(arrival_rate=0), dict(arrival_rate=-1.0),
            dict(arrival_rate=float("inf")), dict(arrival_rate=float("nan")),
            dict(arrival_rate="0.5"),
            dict(min_resource_demand=0), dict(min_resource_demand=2.5),
            dict(min_resource_demand=9, max_resource_demand=8),
            dict(deadline=0), dict(deadline=-3),
            dict(simulation_time=0), dict(simulation_time=10.0),
            dict(simulation_time=True),
        ]
        for overrides in bad_overrides:
            with self.subTest(**overrides):
                with self.assertRaises(ValueError):
                    make_config(**overrides)

    def test_invalid_seed_raises(self):
        for bad in (None, -1, 1.5, "42", True):
            with self.subTest(seed=bad):
                with self.assertRaises(ValueError):
                    generate_urllc_traffic(make_config(), seed=bad)

    def test_presets_are_valid_and_generate_traffic(self):
        for level in LEVELS:
            with self.subTest(level=level):
                cfg = preset_config(level)
                self.assertIsInstance(cfg, URLLCConfig)
                events = generate_urllc_traffic(cfg, seed=42)
                self.assertTrue(all(0 <= e.arrival_time < cfg.simulation_time
                                    for e in events))
        with self.assertRaises(ValueError):
            preset_config("extreme")

    def test_presets_differ_only_in_arrival_rate_and_load_is_ordered(self):
        cfgs = {lvl: preset_config(lvl, simulation_time=2000) for lvl in LEVELS}
        self.assertEqual(
            {(c.min_resource_demand, c.max_resource_demand, c.deadline)
             for c in cfgs.values()},
            {(2, 8, 4)})
        counts = {lvl: len(generate_urllc_traffic(c, seed=42))
                  for lvl, c in cfgs.items()}
        self.assertLess(counts["low"], counts["medium"])
        self.assertLess(counts["medium"], counts["high"])


if __name__ == "__main__":
    unittest.main()
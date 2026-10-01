"""Tests for config/simulation.py (defaults and presets only)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.simulation import (HIGH_URLLC_ARRIVAL_RATE,  # noqa: E402
                               LOW_URLLC_ARRIVAL_RATE,
                               MEDIUM_URLLC_ARRIVAL_RATE, make_default_config)
from src.simulation import SimulationConfig  # noqa: E402


class TestDefaultConfig(unittest.TestCase):

    def test_default_config_created(self):
        self.assertIsInstance(make_default_config(), SimulationConfig)

    def test_default_embb_config(self):
        e = make_default_config().embb_config
        self.assertEqual(e.num_code_blocks, 8)
        self.assertEqual(e.coded_positions_per_cb, 36)
        self.assertEqual(e.total_coded_positions, 288)

    def test_default_cbg_count(self):
        self.assertEqual(make_default_config().cbg_count, 4)

    def test_default_decoder_threshold(self):
        self.assertEqual(make_default_config().decoder_config.failure_threshold, 0.25)

    def test_default_urllc_and_preemption_values(self):
        cfg = make_default_config()
        u = cfg.urllc_config
        self.assertEqual((u.min_resource_demand, u.max_resource_demand, u.deadline), (2, 8, 4))
        self.assertEqual(u.simulation_time, 20)
        self.assertEqual(u.arrival_rate, 0.20)
        self.assertEqual(cfg.preemption_pattern, "random")
        self.assertEqual(cfg.preemption_fraction, 0.10)
        self.assertIsNone(cfg.num_preempt)

    def test_low_medium_high_arrival_rates(self):
        for rate, expected in ((LOW_URLLC_ARRIVAL_RATE, 0.05),
                               (MEDIUM_URLLC_ARRIVAL_RATE, 0.20),
                               (HIGH_URLLC_ARRIVAL_RATE, 0.50)):
            with self.subTest(rate=expected):
                self.assertEqual(rate, expected)
                self.assertEqual(
                    make_default_config(arrival_rate=rate).urllc_config.arrival_rate,
                    expected)

    def test_custom_arrival_rate_and_simulation_time(self):
        u = make_default_config(arrival_rate=0.33, simulation_time=75).urllc_config
        self.assertEqual(u.arrival_rate, 0.33)
        self.assertEqual(u.simulation_time, 75)

    def test_custom_preemption_settings_passed_through(self):
        cfg = make_default_config(preemption_pattern="distributed",
                                  preemption_fraction=0.30, cbg_count=6)
        self.assertEqual(cfg.preemption_pattern, "distributed")
        self.assertEqual(cfg.preemption_fraction, 0.30)
        self.assertEqual(cfg.cbg_count, 6)
        cfg2 = make_default_config(preemption_pattern="concentrated",
                                   preemption_fraction=None, num_preempt=20)
        self.assertEqual(cfg2.preemption_pattern, "concentrated")
        self.assertIsNone(cfg2.preemption_fraction)
        self.assertEqual(cfg2.num_preempt, 20)

    def test_invalid_values_rejected_by_underlying_configs(self):
        with self.assertRaises(ValueError):
            make_default_config(arrival_rate=0)
        with self.assertRaises(ValueError):
            make_default_config(cbg_count=0)


if __name__ == "__main__":
    unittest.main()
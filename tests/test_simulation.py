"""Tests for src/simulation.py (one complete trial)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cbg import affected_cbg_ids, group_code_blocks  # noqa: E402
from src.decoder import DecoderConfig, decode_cbgs  # noqa: E402
from src.embb import EmbbConfig, TransportBlock  # noqa: E402
from src.metrics import SimulationMetrics  # noqa: E402
from src.preemption import generate_preemption  # noqa: E402
from src.retransmission import create_retransmission_requests  # noqa: E402
from src.simulation import SimulationConfig, run_simulation  # noqa: E402
from src.urllc import URLLCConfig, generate_urllc_traffic  # noqa: E402


def make_config(**overrides) -> SimulationConfig:
    params = dict(
        embb_config=EmbbConfig(),            # 8 CBs x 36 = 288 positions
        cbg_count=4,
        urllc_config=URLLCConfig(arrival_rate=0.2, min_resource_demand=2,
                                 max_resource_demand=8, deadline=4,
                                 simulation_time=20),
        preemption_pattern="random",
        preemption_fraction=0.10,
    )
    params.update(overrides)
    return SimulationConfig(**params)


class TestSimulation(unittest.TestCase):

    def test_valid_config_returns_metrics(self):
        m = run_simulation(make_config(), seed=1)
        self.assertIsInstance(m, SimulationMetrics)
        self.assertEqual(m.total_embb_positions, 288)

    def test_same_seed_identical_metrics(self):
        cfg = make_config()
        self.assertEqual(run_simulation(cfg, seed=42), run_simulation(cfg, seed=42))

    def test_different_seeds_can_differ(self):
        cfg = make_config(preemption_fraction=None)   # amount from random URLLC traffic
        results = {run_simulation(cfg, seed=s) for s in range(10)}
        self.assertGreater(len(results), 1)
        cfg2 = make_config(preemption_fraction=0.10)  # fixed amount, random placement
        results2 = {run_simulation(cfg2, seed=s) for s in range(20)}
        self.assertGreater(len(results2), 1)

    def test_zero_preemption_gives_zero_impact(self):
        for pattern in ("concentrated", "distributed", "random"):
            with self.subTest(pattern=pattern):
                m = run_simulation(make_config(preemption_pattern=pattern,
                                               preemption_fraction=0.0), seed=3)
                self.assertEqual(m.preempted_positions, 0)
                self.assertEqual(m.affected_cb_count, 0)
                self.assertEqual(m.affected_cbg_count, 0)
                self.assertEqual(m.failed_cbg_count, 0)
                self.assertEqual(m.retransmission_positions, 0)
                self.assertEqual(m.retransmission_overhead, 0.0)

    def test_fixed_preemption_fraction_respected(self):
        for pattern in ("concentrated", "distributed", "random"):
            for seed in (1, 2, 3):
                with self.subTest(pattern=pattern, seed=seed):
                    m = run_simulation(make_config(preemption_pattern=pattern,
                                                   preemption_fraction=0.10), seed=seed)
                    self.assertEqual(m.preempted_positions, round(288 * 0.10))
                    self.assertAlmostEqual(m.preemption_fraction, 29 / 288)

    def test_explicit_num_preempt_passed_through(self):
        m = run_simulation(make_config(preemption_fraction=None, num_preempt=20), seed=1)
        self.assertEqual(m.preempted_positions, 20)

    def test_invalid_cbg_count_raises(self):
        for bad in (0, -1, 2.5, "4", None, True):
            with self.subTest(cbg_count=bad):
                with self.assertRaises(ValueError):
                    make_config(cbg_count=bad)

    def test_full_chain_matches_manual_pipeline(self):
        cfg = make_config(preemption_pattern="concentrated", preemption_fraction=None,
                          decoder_config=DecoderConfig(failure_threshold=0.25, model="threshold"))
        seed = 11
        # URLLC -> preemption -> affected CBs -> affected CBGs -> decoder -> retx.
        tb = TransportBlock.from_config(cfg.embb_config)
        cbgs = group_code_blocks(tb, cfg.cbg_count)
        events = generate_urllc_traffic(cfg.urllc_config, seed)
        pre = generate_preemption(tb, events, "concentrated", seed=seed)
        cb_ids = tb.affected_cb_ids(pre.preempted_positions)
        cbg_ids = affected_cbg_ids(cbgs, cb_ids)
        decoded = decode_cbgs(tb, cbgs, pre.preempted_positions, cfg.decoder_config)
        reqs = create_retransmission_requests(decoded, cbgs, tb)

        m = run_simulation(cfg, seed=seed)
        self.assertEqual(m.preempted_positions, sum(e.resource_demand for e in events))
        self.assertEqual(m.preempted_positions, pre.preempted_count)
        self.assertEqual(m.affected_cb_count, len(cb_ids))
        self.assertEqual(m.affected_cbg_count, len(cbg_ids))
        self.assertEqual(m.failed_cbg_count, sum(1 for r in decoded if not r.success))
        self.assertEqual(m.retransmission_positions, sum(r.num_positions for r in reqs))
        # Sanity: failed <= affected <= total; overhead consistent.
        self.assertLessEqual(m.failed_cbg_count, m.affected_cbg_count)
        self.assertLessEqual(m.affected_cbg_count, cfg.cbg_count)
        self.assertAlmostEqual(m.retransmission_overhead,
                               m.retransmission_positions / m.total_embb_positions)

    def test_failure_requires_enough_damage(self):
        # 10 preempted positions concentrated in a 72-position CBG: 10/72 < 0.25.
        m = run_simulation(make_config(preemption_pattern="concentrated",
                                       preemption_fraction=None, num_preempt=10), seed=1)
        self.assertGreaterEqual(m.affected_cbg_count, 1)
        self.assertEqual(m.failed_cbg_count, 0)
        self.assertEqual(m.retransmission_positions, 0)

    def test_seed_none_runs(self):
        self.assertIsInstance(run_simulation(make_config(), seed=None), SimulationMetrics)


if __name__ == "__main__":
    unittest.main()
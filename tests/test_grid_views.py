from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from analysis.grid_views import (
    PATTERNS,
    _grid_arrays,
    _trace_pattern,
    plot_rq2_preemption_cbg_chain_example,
    plot_rq2_resource_grid_patterns,
    rq2_config,
    validate_replay,
)
from src.cbg import group_code_blocks
from src.embb import EmbbConfig, ResourcePosition, TransportBlock
from src.preemption import generate_preemption


class GridViewMappingTests(unittest.TestCase):
    def test_categories_match_actual_mapping_and_preempted_positions(self):
        cfg = EmbbConfig(num_code_blocks=2, coded_positions_per_cb=6,
                         num_symbols=4, num_subcarriers=6,
                         reserved_pattern="first_symbol")
        tb = TransportBlock.from_config(cfg)
        cbgs = group_code_blocks(tb, 2)
        result = generate_preemption(tb, [], "concentrated", num_preempt=3)
        categories, cb_ids, cbg_ids = _grid_arrays(tb, result.preempted_positions, cbgs)
        for s in range(cfg.num_symbols):
            for f in range(cfg.num_subcarriers):
                pos = ResourcePosition(s, f)
                mapped_cb = tb.cb_id_at(pos)
                if mapped_cb is not None:
                    self.assertEqual(cb_ids[s, f], mapped_cb)
                    self.assertEqual(categories[s, f], 3 if pos in result.preempted_positions else 2)
                    self.assertGreaterEqual(cbg_ids[s, f], 0)
                elif cfg.is_reserved(pos):
                    self.assertEqual(categories[s, f], 1)
                else:
                    self.assertEqual(categories[s, f], 0)
        self.assertTrue(set(result.preempted_positions).issubset(set(tb.used_positions())))

    def test_patterns_have_same_count_unique_positions_and_deterministic_results(self):
        cfg = rq2_config("concentrated")
        tb = TransportBlock.from_config(cfg.embb_config)
        counts = []
        for pattern in PATTERNS:
            first = generate_preemption(tb, [], pattern, preemption_fraction=.2, seed=7)
            second = generate_preemption(tb, [], pattern, preemption_fraction=.2, seed=7)
            self.assertEqual(first, second)
            self.assertEqual(len(first.preempted_positions), len(set(first.preempted_positions)))
            self.assertTrue(set(first.preempted_positions).issubset(set(tb.used_positions())))
            counts.append(first.preempted_count)
        self.assertEqual(len(set(counts)), 1)

    def test_random_seed_changes_selection_but_other_patterns_are_seed_invariant(self):
        cfg = rq2_config("random")
        tb = TransportBlock.from_config(cfg.embb_config)
        r1 = generate_preemption(tb, [], "random", preemption_fraction=.2, seed=1)
        r2 = generate_preemption(tb, [], "random", preemption_fraction=.2, seed=2)
        self.assertNotEqual(r1.preempted_positions, r2.preempted_positions)
        for pattern in ("concentrated", "distributed"):
            a = generate_preemption(tb, [], pattern, preemption_fraction=.2, seed=1)
            b = generate_preemption(tb, [], pattern, preemption_fraction=.2, seed=2)
            self.assertEqual(a.preempted_positions, b.preempted_positions)

    def test_edge_cases_zero_full_reserved_interleaved_and_large_candidate_grid(self):
        base = EmbbConfig(num_code_blocks=2, coded_positions_per_cb=3,
                          num_symbols=3, num_subcarriers=4)
        tb = TransportBlock.from_config(base)
        zero = generate_preemption(tb, [], "concentrated", preemption_fraction=0)
        full = generate_preemption(tb, [], "concentrated", preemption_fraction=1)
        self.assertEqual(zero.preempted_count, 0)
        self.assertEqual(full.preempted_count, tb.total_positions)

        reserved_cfg = EmbbConfig(num_code_blocks=2, coded_positions_per_cb=3,
                                  num_symbols=4, num_subcarriers=4,
                                  reserved_pattern="first_symbol")
        reserved_tb = TransportBlock.from_config(reserved_cfg)
        res = generate_preemption(reserved_tb, [], "distributed", num_preempt=2)
        self.assertTrue(all(p.symbol != 0 for p in res.preempted_positions))

        interleaved_cfg = EmbbConfig(num_code_blocks=2, coded_positions_per_cb=3,
                                     num_symbols=4, num_subcarriers=4,
                                     mapping_mode="interleaved")
        interleaved_tb = TransportBlock.from_config(interleaved_cfg)
        interleaved_cbgs = group_code_blocks(interleaved_tb, 2)
        cats, cb_ids, cbg_ids = _grid_arrays(interleaved_tb, [], interleaved_cbgs)
        self.assertEqual(int(np.count_nonzero(cb_ids >= 0)), interleaved_tb.total_positions)
        self.assertEqual(int(np.count_nonzero(cbg_ids >= 0)), interleaved_tb.total_positions)

        # More candidate REs than TB positions: the remaining cells stay unused.
        large_cfg = EmbbConfig(num_code_blocks=1, coded_positions_per_cb=3,
                               num_symbols=5, num_subcarriers=5)
        large_tb = TransportBlock.from_config(large_cfg)
        large_cbgs = group_code_blocks(large_tb, 1)
        cats, _, _ = _grid_arrays(large_tb, [], large_cbgs)
        self.assertGreater(int(np.count_nonzero(cats == 0)), 0)

    def test_replay_matches_simulator_for_all_rq2_patterns_and_seeds(self):
        self.assertEqual(validate_replay(range(30)), 90)

    def test_figures_write_nonempty_png_and_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            first = plot_rq2_resource_grid_patterns(output, seed=0)
            second = plot_rq2_preemption_cbg_chain_example(output, seed=1)
            self.assertGreater(first.stat().st_size, 1000)
            self.assertGreater((output / "rq2_resource_grid_patterns.pdf").stat().st_size, 1000)
            self.assertGreater(second.stat().st_size, 1000)
            self.assertGreater((output / "rq2_preemption_cbg_chain_example.pdf").stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()

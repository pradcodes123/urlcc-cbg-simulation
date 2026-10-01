"""Tests for src/embb.py (abstract eMBB transport-block mapping)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.embb import EmbbConfig, ResourcePosition, TransportBlock  # noqa: E402

ORDERS = ("frequency_first", "time_first")


def make_tb(order: str = "frequency_first") -> TransportBlock:
    cfg = EmbbConfig(num_code_blocks=8, coded_positions_per_cb=36,
                     num_symbols=14, num_subcarriers=24, mapping_order=order)
    return TransportBlock.from_config(cfg)


class TestEmbbMapping(unittest.TestCase):

    def test_each_cb_has_exact_number_of_positions(self):
        for order in ORDERS:
            with self.subTest(order=order):
                tb = make_tb(order)
                n = tb.config.coded_positions_per_cb
                self.assertEqual(tb.num_code_blocks, tb.config.num_code_blocks)
                for cb in tb.code_blocks:
                    self.assertEqual(cb.num_coded_positions, n)
                    self.assertEqual(len(cb.positions), n)
                    self.assertEqual(len(set(cb.positions)), n)  # no repeats inside a CB

    def test_no_two_cbs_share_a_position(self):
        for order in ORDERS:
            with self.subTest(order=order):
                tb = make_tb(order)
                seen = set()
                for cb in tb.code_blocks:
                    overlap = seen & cb.position_set
                    self.assertFalse(overlap, f"CB {cb.cb_id} overlaps: {overlap}")
                    seen |= cb.position_set
                self.assertEqual(len(seen), tb.config.total_coded_positions)

    def test_affected_cb_ids_identifies_partially_hit_cbs(self):
        tb = make_tb("frequency_first")
        # Under this abstract order: CB0 = (0,0)..(1,11), CB1 = (1,12)..(2,23).
        # A single position inside CB0 is a partial hit of CB0 only.
        one = [ResourcePosition(1, 5)]
        self.assertEqual(tb.affected_cb_ids(one), [0])
        self.assertEqual(tb.get_cb(0).count_hit_positions(one), 1)
        self.assertLess(tb.get_cb(0).count_hit_positions(one),
                        tb.get_cb(0).num_coded_positions)  # partial, not full
        self.assertFalse(tb.get_cb(1).is_affected_by(one))

        # Two neighbouring positions straddling the CB0/CB1 boundary hit both partially.
        straddle = [ResourcePosition(1, 11), ResourcePosition(1, 12)]
        self.assertEqual(tb.affected_cb_ids(straddle), [0, 1])
        self.assertEqual(tb.get_cb(0).count_hit_positions(straddle), 1)
        self.assertEqual(tb.get_cb(1).count_hit_positions(straddle), 1)

        # Duplicates and an empty input behave sensibly.
        self.assertEqual(tb.affected_cb_ids(one + one), [0])
        self.assertEqual(tb.affected_cb_ids([]), [])

    def test_unused_grid_positions_return_none(self):
        for order in ORDERS:
            with self.subTest(order=order):
                tb = make_tb(order)
                cfg = tb.config
                used = set(tb.used_positions())
                grid = {ResourcePosition(s, k)
                        for s in range(cfg.num_symbols)
                        for k in range(cfg.num_subcarriers)}
                unused = grid - used
                self.assertEqual(len(unused), cfg.grid_size - cfg.total_coded_positions)
                self.assertTrue(unused, "test config should leave some grid unused")
                for pos in unused:
                    self.assertIsNone(tb.cb_id_at(pos))
                self.assertEqual(tb.affected_cb_ids(unused), [])
                # A position outside the grid is also unmapped.
                self.assertIsNone(tb.cb_id_at(ResourcePosition(999, 999)))
                # Used positions do map to a CB.
                for pos in used:
                    self.assertIsNotNone(tb.cb_id_at(pos))

    def test_same_configuration_gives_identical_mapping(self):
        for order in ORDERS:
            with self.subTest(order=order):
                tb1, tb2 = make_tb(order), make_tb(order)
                self.assertEqual(tb1.code_blocks, tb2.code_blocks)
                self.assertEqual(tb1.used_positions(), tb2.used_positions())
                for cb1, cb2 in zip(tb1.code_blocks, tb2.code_blocks):
                    self.assertEqual(cb1.cb_id, cb2.cb_id)
                    self.assertEqual(cb1.positions, cb2.positions)


if __name__ == "__main__":
    unittest.main()
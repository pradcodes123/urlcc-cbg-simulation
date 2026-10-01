"""Tests for src/cbg.py (TS 38.214 §5.1.7.1 grouping)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cbg import (CodeBlockGroup, affected_cbg_ids, get_cbg_for_cb,  # noqa: E402
                     group_code_blocks)
from src.embb import EmbbConfig, ResourcePosition, TransportBlock  # noqa: E402


def make_tb(c: int, positions_per_cb: int = 4) -> TransportBlock:
    return TransportBlock.from_config(
        EmbbConfig(num_code_blocks=c, coded_positions_per_cb=positions_per_cb))


def as_lists(cbgs):
    return [list(g.cb_ids) for g in cbgs]


class TestCbgGrouping(unittest.TestCase):

    def test_c8_n4(self):
        cbgs = group_code_blocks(make_tb(8), 4)
        self.assertEqual(as_lists(cbgs), [[0, 1], [2, 3], [4, 5], [6, 7]])
        self.assertEqual([g.cbg_id for g in cbgs], [0, 1, 2, 3])

    def test_c_less_than_n(self):
        cbgs = group_code_blocks(make_tb(3), 8)   # M = min(8, 3) = 3
        self.assertEqual(as_lists(cbgs), [[0], [1], [2]])

    def test_c10_n4_not_divisible(self):
        # M=4, M1=2, K1=3, K2=2 -> sizes 3,3,2,2
        cbgs = group_code_blocks(make_tb(10), 4)
        self.assertEqual(as_lists(cbgs),
                         [[0, 1, 2], [3, 4, 5], [6, 7], [8, 9]])

    def test_c_equals_n_and_n_equals_one(self):
        self.assertEqual(as_lists(group_code_blocks(make_tb(4), 4)),
                         [[0], [1], [2], [3]])
        self.assertEqual(as_lists(group_code_blocks(make_tb(5), 1)),
                         [[0, 1, 2, 3, 4]])

    def test_every_cb_appears_exactly_once_and_order_preserved(self):
        for c in range(1, 21):
            for n in range(1, 25):
                with self.subTest(C=c, N=n):
                    cbgs = group_code_blocks(make_tb(c, 2), n)
                    flat = [cb for g in cbgs for cb in g.cb_ids]
                    self.assertEqual(flat, list(range(c)))
                    self.assertEqual(len(cbgs), min(n, c))
                    sizes = [len(g) for g in cbgs]
                    self.assertLessEqual(max(sizes) - min(sizes), 1)

    def test_deterministic_output(self):
        a = group_code_blocks(make_tb(10), 4)
        b = group_code_blocks(make_tb(10), 4)
        self.assertEqual(a, b)

    def test_invalid_max_cbgs_raises(self):
        tb = make_tb(8)
        for bad in (0, -1, -5, 2.5, "4", None, True):
            with self.subTest(max_cbgs=bad):
                with self.assertRaises(ValueError):
                    group_code_blocks(tb, bad)

    def test_empty_transport_block_raises(self):
        empty = TransportBlock(config=EmbbConfig(), code_blocks=())
        with self.assertRaises(ValueError):
            group_code_blocks(empty, 4)

    def test_positions_to_cbs_to_cbgs_chain(self):
        tb = make_tb(8, positions_per_cb=36)
        cbgs = group_code_blocks(tb, 4)
        # (2,23) is the last position of CB1; (3,0) is the first of CB2.
        probe = [ResourcePosition(2, 23), ResourcePosition(3, 0)]
        cb_hit = tb.affected_cb_ids(probe)
        self.assertEqual(cb_hit, [1, 2])
        self.assertEqual(affected_cbg_ids(cbgs, cb_hit), [0, 1])
        # Two CBs inside one CBG -> a single affected CBG.
        self.assertEqual(affected_cbg_ids(cbgs, [4, 5]), [2])
        self.assertEqual(affected_cbg_ids(cbgs, []), [])

    def test_get_cbg_for_cb(self):
        cbgs = group_code_blocks(make_tb(10), 4)
        self.assertEqual([get_cbg_for_cb(cbgs, i) for i in range(10)],
                         [0, 0, 0, 1, 1, 1, 2, 2, 3, 3])
        with self.assertRaises(ValueError):
            get_cbg_for_cb(cbgs, 99)
        with self.assertRaises(ValueError):
            affected_cbg_ids(cbgs, [99])

    def test_cbg_is_immutable_dataclass(self):
        g = CodeBlockGroup(cbg_id=0, cb_ids=(0, 1))
        with self.assertRaises(Exception):
            g.cbg_id = 5  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
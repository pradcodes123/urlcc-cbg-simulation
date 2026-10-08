"""Tests for src/retransmission.py (CBG retransmission requests)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cbg import group_code_blocks  # noqa: E402
from src.decoder import CBGDecodingResult, DecoderConfig, decode_cbgs  # noqa: E402
from src.embb import EmbbConfig, TransportBlock  # noqa: E402
from src.retransmission import (RetransmissionRequest,  # noqa: E402
                                create_retransmission_requests, get_failed_cbgs,
                                retransmission_overhead)


def res(cbg_id: int, success: bool) -> CBGDecodingResult:
    return CBGDecodingResult(cbg_id=cbg_id, total_positions=1, hit_positions=0,
                             damage_ratio=0.0, success=success)


class TestRetransmission(unittest.TestCase):

    def setUp(self):
        # 10 CBs x 4 positions, N=4 -> CBG sizes 3,3,2,2 CBs = 12,12,8,8 positions.
        self.tb = TransportBlock.from_config(
            EmbbConfig(num_code_blocks=10, coded_positions_per_cb=4))
        self.cbgs = group_code_blocks(self.tb, 4)
        self.total = 40

    def make(self, results):
        return create_retransmission_requests(results, self.cbgs, self.tb)

    def test_no_failed_cbgs_no_requests(self):
        results = [res(i, True) for i in range(4)]
        self.assertEqual(get_failed_cbgs(results), ())
        self.assertEqual(self.make(results), ())
        self.assertEqual(self.make([]), ())

    def test_one_failed_cbg_one_request(self):
        reqs = self.make([res(0, True), res(1, False), res(2, True), res(3, True)])
        self.assertEqual(reqs, (RetransmissionRequest(cbg_id=1, num_positions=12),))

    def test_multiple_failed_ordered_by_cbg_id(self):
        results = [res(3, False), res(0, True), res(1, False), res(2, True)]
        self.assertEqual(get_failed_cbgs(results), (1, 3))
        self.assertEqual([r.cbg_id for r in self.make(results)], [1, 3])

    def test_position_count_matches_cbg_positions(self):
        reqs = self.make([res(i, False) for i in range(4)])
        self.assertEqual([r.num_positions for r in reqs], [12, 12, 8, 8])
        for r in reqs:
            expected = sum(len(self.tb.get_cb(cb).positions)
                           for cb in self.cbgs[r.cbg_id].cb_ids)
            self.assertEqual(r.num_positions, expected)
        self.assertEqual(sum(r.num_positions for r in reqs), self.total)

    def test_successful_cbgs_never_produce_requests(self):
        reqs = self.make([res(0, True), res(1, False), res(2, True), res(3, False)])
        self.assertEqual({r.cbg_id for r in reqs}, {1, 3})

    def test_overhead_calculation(self):
        reqs = self.make([res(1, False), res(3, False)])      # 12 + 8 = 20
        self.assertAlmostEqual(retransmission_overhead(reqs, self.total), 0.5)
        self.assertEqual(retransmission_overhead([], self.total), 0.0)
        self.assertEqual(retransmission_overhead(
            self.make([res(i, False) for i in range(4)]), self.total), 1.0)

    def test_invalid_total_positions_raises(self):
        for bad in (0, -5, 2.5, "40", None, True):
            with self.subTest(total=bad):
                with self.assertRaises(ValueError):
                    retransmission_overhead([], bad)

    def test_unknown_failed_cbg_raises(self):
        with self.assertRaises(ValueError):
            self.make([res(99, False)])

    def test_repeated_inputs_identical(self):
        results = [res(3, False), res(1, False), res(0, True)]
        self.assertEqual(self.make(results), self.make(results))
        self.assertEqual(self.make(iter(results)), self.make(results))

    def test_chain_from_decoder(self):
        # Preempt all positions of CBG0 (CBs 0-2): only CBG0 fails.
        hit = [p for cb in self.cbgs[0].cb_ids for p in self.tb.get_cb(cb).positions]
        decoded = decode_cbgs(self.tb, self.cbgs, hit, DecoderConfig(failure_threshold=0.25, model="threshold"))
        reqs = self.make(decoded)
        self.assertEqual(reqs, (RetransmissionRequest(0, 12),))
        self.assertAlmostEqual(retransmission_overhead(reqs, self.total), 0.3)


if __name__ == "__main__":
    unittest.main()
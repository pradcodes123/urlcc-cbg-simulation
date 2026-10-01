"""Tests for src/decoder.py (controlled CBG decoding abstraction)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cbg import group_code_blocks  # noqa: E402
from src.decoder import (CBGDecodingResult, DecoderConfig,  # noqa: E402
                         decode_cbgs)
from src.embb import EmbbConfig, TransportBlock  # noqa: E402


class TestDecoder(unittest.TestCase):

    def setUp(self):
        # 4 CBs x 4 positions, 2 CBGs: CBG0 = CB0,CB1 and CBG1 = CB2,CB3 (8 positions each).
        self.tb = TransportBlock.from_config(
            EmbbConfig(num_code_blocks=4, coded_positions_per_cb=4))
        self.cbgs = group_code_blocks(self.tb, 2)
        self.cbg0_positions = [p for cb_id in self.cbgs[0].cb_ids
                               for p in self.tb.get_cb(cb_id).positions]
        self.cfg = DecoderConfig(failure_threshold=0.25)   # 2 of 8 = exactly 0.25

    def decode(self, positions, cfg=None):
        return decode_cbgs(self.tb, self.cbgs, positions, cfg or self.cfg)

    def test_no_preemption_all_succeed(self):
        for r in self.decode([]):
            self.assertEqual(r.hit_positions, 0)
            self.assertEqual(r.damage_ratio, 0)
            self.assertTrue(r.success)
            self.assertEqual(r.total_positions, 8)

    def test_partial_below_threshold_affected_but_successful(self):
        hit = self.cbg0_positions[:1]                  # 1/8 = 0.125 < 0.25
        r0, r1 = self.decode(hit)
        self.assertEqual(self.tb.affected_cb_ids(hit), [0])   # CBG0 is affected...
        self.assertEqual(r0.hit_positions, 1)
        self.assertAlmostEqual(r0.damage_ratio, 0.125)
        self.assertTrue(r0.success)                    # ...but does not fail
        self.assertEqual(r1.hit_positions, 0)
        self.assertTrue(r1.success)

    def test_damage_exactly_at_threshold_fails(self):
        r0, r1 = self.decode(self.cbg0_positions[:2])  # 2/8 == 0.25
        self.assertEqual(r0.damage_ratio, 0.25)
        self.assertFalse(r0.success)
        self.assertTrue(r1.success)

    def test_damage_above_threshold_fails(self):
        r0, _ = self.decode(self.cbg0_positions[:3])   # 3/8 = 0.375
        self.assertGreater(r0.damage_ratio, 0.25)
        self.assertFalse(r0.success)

    def test_full_preemption_of_cbg_fails(self):
        r0, r1 = self.decode(self.cbg0_positions)
        self.assertEqual(r0.hit_positions, 8)
        self.assertEqual(r0.damage_ratio, 1.0)
        self.assertFalse(r0.success)
        self.assertTrue(r1.success)

    def test_results_ordered_by_cbg_id(self):
        results = decode_cbgs(self.tb, tuple(reversed(self.cbgs)), [], self.cfg)
        self.assertEqual([r.cbg_id for r in results], [0, 1])
        self.assertTrue(all(isinstance(r, CBGDecodingResult) for r in results))

    def test_invalid_thresholds_raise(self):
        for bad in (-0.01, 1.01, -1, 2, float("nan"), float("inf"), "0.25", None, True):
            with self.subTest(threshold=bad):
                with self.assertRaises(ValueError):
                    DecoderConfig(failure_threshold=bad)
        DecoderConfig(0.0)
        DecoderConfig(1.0)   # boundaries are valid

    def test_repeated_inputs_identical(self):
        hit = self.cbg0_positions[:3]
        self.assertEqual(self.decode(hit), self.decode(hit))
        self.assertEqual(self.decode(iter(hit)), self.decode(hit))  # one-shot iterables OK

    def test_default_config_uses_threshold_025(self):
        self.assertEqual(DecoderConfig().failure_threshold, 0.25)
        r0, _ = decode_cbgs(self.tb, self.cbgs, self.cbg0_positions[:2])
        self.assertFalse(r0.success)


if __name__ == "__main__":
    unittest.main()
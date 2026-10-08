"""Tests for src/decoder.py (controlled CBG decoding abstraction).

Two groups: the legacy deterministic threshold model (kept as a selectable
reference) and the default stochastic SNR/erasure model.
"""

import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cbg import group_code_blocks  # noqa: E402
from src.decoder import (CBGDecodingResult, DecoderConfig, SnrLinkModel,  # noqa: E402
                         ThresholdModel, decode_cbgs, make_model)
from src.embb import EmbbConfig, TransportBlock  # noqa: E402


# --------------------------------------------------------------------------
# Legacy deterministic rule (model="threshold")
# --------------------------------------------------------------------------
class TestThresholdModel(unittest.TestCase):

    def setUp(self):
        # 4 CBs x 4 positions, 2 CBGs: CBG0 = CB0,CB1 and CBG1 = CB2,CB3 (8 positions each).
        self.tb = TransportBlock.from_config(
            EmbbConfig(num_code_blocks=4, coded_positions_per_cb=4))
        self.cbgs = group_code_blocks(self.tb, 2)
        self.cbg0_positions = [p for cb_id in self.cbgs[0].cb_ids
                               for p in self.tb.get_cb(cb_id).positions]
        self.cfg = DecoderConfig(failure_threshold=0.25, model="threshold")

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
        self.assertTrue(r1.success)

    def test_damage_exactly_at_threshold_fails(self):
        r0, r1 = self.decode(self.cbg0_positions[:2])  # 2/8 == 0.25
        self.assertEqual(r0.damage_ratio, 0.25)
        self.assertFalse(r0.success)
        self.assertTrue(r1.success)

    def test_damage_above_threshold_and_full_damage_fail(self):
        self.assertFalse(self.decode(self.cbg0_positions[:3])[0].success)
        r0, r1 = self.decode(self.cbg0_positions)
        self.assertEqual(r0.damage_ratio, 1.0)
        self.assertFalse(r0.success)
        self.assertTrue(r1.success)

    def test_threshold_probabilities_are_degenerate_and_need_no_seed(self):
        results = self.decode(self.cbg0_positions[:2])      # no seed supplied
        self.assertEqual([r.failure_probability for r in results], [1.0, 0.0])
        self.assertTrue(all(r.effective_snr_db is None for r in results))
        # Outcome identical for any seed: no randomness involved.
        self.assertEqual(results, decode_cbgs(self.tb, self.cbgs, self.cbg0_positions[:2],
                                              self.cfg, seed=123))

    def test_results_ordered_by_cbg_id(self):
        results = decode_cbgs(self.tb, tuple(reversed(self.cbgs)), [], self.cfg)
        self.assertEqual([r.cbg_id for r in results], [0, 1])
        self.assertTrue(all(isinstance(r, CBGDecodingResult) for r in results))

    def test_repeated_inputs_identical(self):
        hit = self.cbg0_positions[:3]
        self.assertEqual(self.decode(hit), self.decode(hit))
        self.assertEqual(self.decode(iter(hit)), self.decode(hit))  # one-shot iterables OK


# --------------------------------------------------------------------------
# Configuration validation
# --------------------------------------------------------------------------
class TestDecoderConfig(unittest.TestCase):

    def test_invalid_thresholds_raise_for_every_model(self):
        for model in ("snr", "threshold"):
            for bad in (-0.01, 1.01, -1, 2, float("nan"), float("inf"), "0.25", None, True):
                with self.subTest(model=model, threshold=bad):
                    with self.assertRaises(ValueError):
                        DecoderConfig(failure_threshold=bad, model=model)
        DecoderConfig(0.0)
        DecoderConfig(1.0)   # boundaries are valid

    def test_invalid_model_and_link_parameters_raise(self):
        bad_kwargs = [dict(model="ldpc"), dict(model=None),
                      dict(snr_db=float("nan")), dict(snr_db=float("inf")),
                      dict(snr_db="12"), dict(snr_db=True),
                      dict(gap_db=float("nan")), dict(gap_db=None),
                      dict(spectral_efficiency=0), dict(spectral_efficiency=-1.0),
                      dict(spectral_efficiency=float("inf")),
                      dict(sigma_db=0), dict(sigma_db=-0.5), dict(sigma_db=float("nan"))]
        for kwargs in bad_kwargs:
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    DecoderConfig(**kwargs)

    def test_defaults(self):
        cfg = DecoderConfig()
        self.assertEqual(cfg.failure_threshold, 0.25)    # kept for the legacy model
        self.assertEqual(cfg.model, "snr")
        self.assertIsInstance(make_model(cfg), SnrLinkModel)
        self.assertIsInstance(make_model(DecoderConfig(model="threshold")), ThresholdModel)
        self.assertEqual(DecoderConfig(0.3).failure_threshold, 0.3)   # positional use unchanged

    def test_result_dataclass_backward_compatible(self):
        r = CBGDecodingResult(cbg_id=0, total_positions=8, hit_positions=1,
                              damage_ratio=0.125, success=True)
        self.assertIsNone(r.failure_probability)
        self.assertIsNone(r.effective_snr_db)


# --------------------------------------------------------------------------
# Stochastic SNR / erasure model
# --------------------------------------------------------------------------
class TestSnrModel(unittest.TestCase):

    def setUp(self):
        # One CBG of 2 CBs x 50 = 100 positions, so hits k map to damage k/100.
        self.tb = TransportBlock.from_config(
            EmbbConfig(num_code_blocks=2, coded_positions_per_cb=50))
        self.cbgs = group_code_blocks(self.tb, 1)
        self.used = self.tb.used_positions()
        self.cfg = DecoderConfig()                       # default stochastic model
        self.model = make_model(self.cfg)

    def decode(self, hits, seed, cfg=None):
        return decode_cbgs(self.tb, self.cbgs, self.used[:hits], cfg or self.cfg, seed=seed)[0]

    def p_fail(self, damage, **params):
        cfg = DecoderConfig(**params) if params else self.cfg
        return make_model(cfg).evaluate(damage)[0]

    # --- model behaviour ---------------------------------------------------
    def test_zero_damage_good_link_has_very_low_failure_probability(self):
        p, eff_db = self.model.evaluate(0.0)
        self.assertLess(p, 1e-6)
        self.assertGreater(p, 0.0)                       # small but not exactly zero
        self.assertAlmostEqual(eff_db, self.cfg.snr_db, places=9)
        for seed in range(200):                          # and it basically never fails
            self.assertTrue(self.decode(0, seed).success)

    def test_failure_probability_increases_with_damage(self):
        grid = [i / 20 for i in range(21)]
        ps = [self.p_fail(d) for d in grid]
        self.assertTrue(all(a <= b for a, b in zip(ps, ps[1:])))      # non-decreasing
        mid = [self.p_fail(d) for d in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)]
        self.assertTrue(all(a < b for a, b in zip(mid, mid[1:])))     # strictly in transition
        effs = [self.model.evaluate(d)[1] for d in grid[:-1]]
        self.assertTrue(all(a > b for a, b in zip(effs, effs[1:])))   # effective SNR drops

    def test_failure_probability_decreases_with_snr(self):
        ps = [self.p_fail(0.40, snr_db=s) for s in (6.0, 8.0, 10.0, 12.0, 14.0)]
        self.assertTrue(all(a > b for a, b in zip(ps, ps[1:])), ps)

    def test_boundary_zero_and_full_damage(self):
        p0, e0 = self.model.evaluate(0.0)
        p1, e1 = self.model.evaluate(1.0)
        self.assertEqual(p1, 1.0)
        self.assertEqual(e1, -math.inf)
        self.assertLess(p0, p1)
        for seed in range(100):                          # full damage: always fails
            r = self.decode(100, seed)
            self.assertEqual((r.damage_ratio, r.failure_probability, r.success), (1.0, 1.0, False))

    def test_effective_snr_matches_capacity_formula(self):
        # snr_eff = (1 + snr)^(1 - d) - 1, evaluated independently here.
        snr_lin = 10 ** (12.0 / 10)
        expected = 10 * math.log10((1 + snr_lin) ** 0.5 - 1)
        self.assertAlmostEqual(self.model.evaluate(0.5)[1], expected, places=9)

    # --- randomness and reproducibility -----------------------------------
    def test_identical_seed_and_inputs_give_identical_results(self):
        a = decode_cbgs(self.tb, self.cbgs, self.used[:45], self.cfg, seed=7)
        b = decode_cbgs(self.tb, self.cbgs, self.used[:45], self.cfg, seed=7)
        self.assertEqual(a, b)
        c = decode_cbgs(self.tb, self.cbgs, self.used[:45], self.cfg, rng=np.random.default_rng(3))
        d = decode_cbgs(self.tb, self.cbgs, self.used[:45], self.cfg, rng=np.random.default_rng(3))
        self.assertEqual(c, d)

    def test_different_seeds_vary_where_probability_is_intermediate(self):
        p = self.p_fail(0.45)
        self.assertTrue(0.3 < p < 0.7, p)                # mid-transition operating point
        outcomes = {self.decode(45, seed).success for seed in range(50)}
        self.assertEqual(outcomes, {True, False})
        # ...but no variation where the outcome is (practically) certain.
        self.assertEqual({self.decode(0, s).success for s in range(50)}, {True})
        self.assertEqual({self.decode(100, s).success for s in range(50)}, {False})

    def test_failure_frequency_matches_failure_probability(self):
        p = self.p_fail(0.45)
        n = 2000
        freq = sum(not self.decode(45, s).success for s in range(n)) / n
        self.assertAlmostEqual(freq, p, delta=0.04)

    def test_more_damage_never_turns_failure_into_success_for_same_seed(self):
        for seed in range(200):
            fails = [not self.decode(k, seed).success for k in (10, 30, 40, 45, 50, 70, 100)]
            self.assertTrue(all(a <= b for a, b in zip(fails, fails[1:])), (seed, fails))

    def test_one_draw_per_cbg_in_id_order(self):
        # Results for a CBG must not depend on the outcomes of earlier CBGs.
        tb = TransportBlock.from_config(EmbbConfig(num_code_blocks=4, coded_positions_per_cb=25))
        cbgs = group_code_blocks(tb, 4)
        used = tb.used_positions()
        rev = decode_cbgs(tb, tuple(reversed(cbgs)), used[:60], self.cfg, seed=11)
        fwd = decode_cbgs(tb, cbgs, used[:60], self.cfg, seed=11)
        self.assertEqual(rev, fwd)

    # --- result fields and guards -----------------------------------------
    def test_result_reports_probability_and_effective_snr(self):
        r = self.decode(45, seed=1)
        p, eff = self.model.evaluate(0.45)
        self.assertEqual((r.total_positions, r.hit_positions, r.damage_ratio), (100, 45, 0.45))
        self.assertEqual((r.failure_probability, r.effective_snr_db), (p, eff))

    def test_seed_requirements(self):
        args = (self.tb, self.cbgs, self.used[:5], self.cfg)
        with self.assertRaises(ValueError):
            decode_cbgs(*args)                                   # stochastic, no seed
        with self.assertRaises(ValueError):
            decode_cbgs(*args, seed=1, rng=np.random.default_rng(1))
        for bad in (-1, 1.5, "3", True):
            with self.subTest(seed=bad):
                with self.assertRaises(ValueError):
                    decode_cbgs(*args, seed=bad)

    def test_empty_cbg_still_raises(self):
        from src.cbg import CodeBlockGroup
        empty = (CodeBlockGroup(cbg_id=0, cb_ids=()),)
        with self.assertRaises(ValueError):
            decode_cbgs(self.tb, empty, [], self.cfg, seed=1)

    def test_custom_model_can_be_plugged_in(self):
        class AlwaysHalf:
            stochastic = True
            def evaluate(self, damage_ratio):
                return 0.5, None
        freq = sum(not decode_cbgs(self.tb, self.cbgs, [], self.cfg, seed=s,
                                   model=AlwaysHalf())[0].success for s in range(1000)) / 1000
        self.assertAlmostEqual(freq, 0.5, delta=0.06)


if __name__ == "__main__":
    unittest.main()
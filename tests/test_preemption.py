"""Tests for src/preemption.py."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.embb import EmbbConfig, TransportBlock  # noqa: E402
from src.preemption import (PATTERNS, affected_cbs,  # noqa: E402
                            generate_preemption)
from src.urllc import URLLCEvent  # noqa: E402


def make_tb() -> TransportBlock:
    # 8 x 36 = 288 used positions on a 14 x 24 = 336 grid (48 unused).
    return TransportBlock.from_config(EmbbConfig())


def ev(i: int, demand: int) -> URLLCEvent:
    return URLLCEvent(event_id=i, arrival_time=0, resource_demand=demand, deadline=4)


class TestPreemption(unittest.TestCase):

    def setUp(self):
        self.tb = make_tb()

    def test_random_same_seed_identical(self):
        a = generate_preemption(self.tb, [], "random", preemption_fraction=0.1, seed=5)
        b = generate_preemption(self.tb, [], "random", preemption_fraction=0.1, seed=5)
        c = generate_preemption(self.tb, [], "random", preemption_fraction=0.1, seed=6)
        self.assertEqual(a, b)
        self.assertNotEqual(a.preempted_positions, c.preempted_positions)

    def test_requested_equals_selected(self):
        for pat in PATTERNS:
            for frac in (0.05, 0.10, 0.5, 1.0):
                with self.subTest(pattern=pat, fraction=frac):
                    r = generate_preemption(self.tb, [], pat,
                                            preemption_fraction=frac, seed=1)
                    self.assertEqual(r.requested_count, round(288 * frac))
                    self.assertEqual(r.preempted_count, r.requested_count)

    def test_positions_belong_to_transport_block(self):
        used = set(self.tb.used_positions())
        for pat in PATTERNS:
            with self.subTest(pattern=pat):
                r = generate_preemption(self.tb, [], pat, preemption_fraction=0.3, seed=2)
                self.assertTrue(set(r.preempted_positions) <= used)
                self.assertTrue(all(self.tb.cb_id_at(p) is not None
                                    for p in r.preempted_positions))

    def test_all_patterns_select_same_count(self):
        for frac in (0.02, 0.10, 0.33, 0.9):
            with self.subTest(fraction=frac):
                counts = {generate_preemption(self.tb, [], p, preemption_fraction=frac,
                                              seed=3).preempted_count for p in PATTERNS}
                self.assertEqual(len(counts), 1)

    def test_no_duplicates(self):
        for pat in PATTERNS:
            for frac in (0.1, 0.5, 1.0):
                with self.subTest(pattern=pat, fraction=frac):
                    r = generate_preemption(self.tb, [], pat,
                                            preemption_fraction=frac, seed=4)
                    self.assertEqual(len(set(r.preempted_positions)), r.preempted_count)

    def test_zero_preemption_is_empty(self):
        for pat in PATTERNS:
            with self.subTest(pattern=pat):
                r = generate_preemption(self.tb, [], pat, preemption_fraction=0.0, seed=1)
                self.assertEqual(r.preempted_positions, ())
                self.assertEqual(r.preempted_count, 0)
                self.assertEqual(affected_cbs(self.tb, r), [])
        # No fraction and no events -> zero demand -> empty.
        self.assertEqual(generate_preemption(self.tb, [], "concentrated").preempted_count, 0)

    def test_invalid_inputs_raise(self):
        bad_calls = [
            dict(pattern="burst", preemption_fraction=0.1),
            dict(pattern="concentrated", preemption_fraction=-0.1),
            dict(pattern="concentrated", preemption_fraction=1.5),
            dict(pattern="concentrated", preemption_fraction=float("nan")),
            dict(pattern="concentrated", preemption_fraction="0.1"),
            dict(pattern="concentrated", preemption_fraction=0.001),  # rounds to 0
            dict(pattern="random", preemption_fraction=0.1),          # missing seed
            dict(pattern="random", preemption_fraction=0.1, seed=-1),
            dict(pattern="random", preemption_fraction=0.1, seed=1.5),
            dict(pattern="distributed", num_preempt=289),             # > available
            dict(pattern="distributed", num_preempt=-1),
            dict(pattern="distributed", preemption_fraction=0.1, num_preempt=5),
        ]
        for kwargs in bad_calls:
            with self.subTest(**kwargs):
                with self.assertRaises(ValueError):
                    generate_preemption(self.tb, [], **kwargs)
        with self.assertRaises(ValueError):   # demand-derived request too large
            generate_preemption(self.tb, [ev(0, 200), ev(1, 100)], "concentrated")

    def test_affected_cb_ids_from_result(self):
        valid_ids = {cb.cb_id for cb in self.tb.code_blocks}
        for pat in ("concentrated", "distributed"):
            with self.subTest(pattern=pat):
                r = generate_preemption(self.tb, [], pat, preemption_fraction=0.10)
                cbs = affected_cbs(self.tb, r)
                self.assertEqual(cbs, self.tb.affected_cb_ids(r.preempted_positions))
                self.assertTrue(cbs)
                self.assertTrue(set(cbs) <= valid_ids)

    def test_count_from_events_and_explicit_amount(self):
        events = [ev(0, 5), ev(1, 7)]           # same-slot events: demand is summed
        r = generate_preemption(self.tb, events, "distributed")
        self.assertEqual(r.preempted_count, 12)
        r2 = generate_preemption(self.tb, events, "distributed", num_preempt=20)
        self.assertEqual(r2.preempted_count, 20)   # explicit amount overrides events

    def test_concentrated_is_contiguous_and_deterministic(self):
        used = self.tb.used_positions()
        r = generate_preemption(self.tb, [], "concentrated", num_preempt=20)
        start = used.index(r.preempted_positions[0])
        self.assertEqual(list(r.preempted_positions), used[start:start + 20])
        self.assertEqual(r, generate_preemption(self.tb, [], "concentrated", num_preempt=20))


if __name__ == "__main__":
    unittest.main()
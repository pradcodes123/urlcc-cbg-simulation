"""Tests for src/metrics.py."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cbg import affected_cbg_ids, group_code_blocks  # noqa: E402
from src.decoder import CBGDecodingResult, DecoderConfig, decode_cbgs  # noqa: E402
from src.embb import EmbbConfig, TransportBlock  # noqa: E402
from src.metrics import SimulationMetrics, calculate_metrics  # noqa: E402
from src.retransmission import (RetransmissionRequest,  # noqa: E402
                                create_retransmission_requests)


def res(cbg_id: int, success: bool) -> CBGDecodingResult:
    return CBGDecodingResult(
        cbg_id=cbg_id,
        total_positions=1,
        hit_positions=0,
        damage_ratio=0.0,
        success=success,
    )


def calc(
        total=100,
        preempted=0,
        cbs=(),
        cbgs=(),
        results=(),
        requests=(),
):
    return calculate_metrics(
        total,
        preempted,
        cbs,
        cbgs,
        results,
        requests,
    )


class TestMetrics(unittest.TestCase):

    def test_no_preemption_no_failures_all_zero(self):
        m = calc(
            results=[res(0, True), res(1, True)]
        )

        self.assertEqual(
            m,
            SimulationMetrics(
                preempted_positions=0,
                total_embb_positions=100,
                preemption_fraction=0.0,
                affected_cb_count=0,
                affected_cbg_count=0,
                failed_cbg_count=0,
                retransmission_positions=0,
                retransmission_overhead=0.0,
                embb_delivery_efficiency=1.0,
            ),
        )

    def test_preemption_fraction(self):
        self.assertAlmostEqual(
            calc(
                total=288,
                preempted=29,
            ).preemption_fraction,
            29 / 288,
        )

        self.assertEqual(
            calc(
                total=50,
                preempted=50,
            ).preemption_fraction,
            1.0,
        )

    def test_duplicate_cb_ids_counted_once(self):
        self.assertEqual(
            calc(
                cbs=[1, 1, 2, 2, 2, 5]
            ).affected_cb_count,
            3,
        )

    def test_duplicate_cbg_ids_counted_once(self):
        self.assertEqual(
            calc(
                cbgs=iter([0, 0, 3, 3])
            ).affected_cbg_count,
            2,
        )

    def test_failed_cbg_count_from_decoding_results(self):
        m = calc(
            results=[
                res(0, False),
                res(1, True),
                res(2, False),
                res(3, True),
            ]
        )

        self.assertEqual(
            m.failed_cbg_count,
            2,
        )

    def test_retransmission_positions_summed(self):
        reqs = [
            RetransmissionRequest(1, 12),
            RetransmissionRequest(3, 8),
        ]

        self.assertEqual(
            calc(
                requests=reqs
            ).retransmission_positions,
            20,
        )

    def test_retransmission_overhead(self):
        reqs = [
            RetransmissionRequest(1, 12),
            RetransmissionRequest(3, 8),
        ]

        self.assertAlmostEqual(
            calc(
                total=40,
                requests=reqs,
            ).retransmission_overhead,
            0.5,
        )

    def test_delivery_efficiency_no_retransmission(self):
        m = calc(
            total=100,
            preempted=10,
        )

        self.assertEqual(
            m.embb_delivery_efficiency,
            1.0,
        )

    def test_delivery_efficiency_with_retransmission(self):
        reqs = [
            RetransmissionRequest(1, 20)
        ]

        m = calc(
            total=100,
            preempted=10,
            requests=reqs,
        )

        self.assertAlmostEqual(
            m.embb_delivery_efficiency,
            100 / 120,
        )

    def test_realistic_combined_case(self):
        # 10 CBs x 4 positions = 40; N=4 -> CBG sizes
        # 12, 12, 8, 8 positions.
        tb = TransportBlock.from_config(
            EmbbConfig(
                num_code_blocks=10,
                coded_positions_per_cb=4,
            )
        )

        cbgs = group_code_blocks(tb, 4)
        used = tb.used_positions()

        # Hit 4 positions in CB2
        # (CBG0 -> 4/12 >= 0.25, fails)
        #
        # and 1 position in CB8
        # (CBG3 -> 1/8 < 0.25, survives).
        hit = used[8:12] + used[32:33]

        cb_ids = tb.affected_cb_ids(hit)
        cbg_ids = affected_cbg_ids(cbgs, cb_ids)

        decoded = decode_cbgs(
            tb,
            cbgs,
            hit,
            DecoderConfig(failure_threshold=0.25, model="threshold"),
        )

        reqs = create_retransmission_requests(
            decoded,
            cbgs,
            tb,
        )

        m = calculate_metrics(
            len(used),
            len(hit),
            cb_ids + cb_ids,
            cbg_ids,
            decoded,
            reqs,
        )

        self.assertEqual(
            m.preempted_positions,
            5,
        )

        self.assertEqual(
            m.total_embb_positions,
            40,
        )

        self.assertAlmostEqual(
            m.preemption_fraction,
            0.125,
        )

        self.assertEqual(
            m.affected_cb_count,
            2,
        )  # CB2, CB8

        self.assertEqual(
            m.affected_cbg_count,
            2,
        )  # CBG0, CBG3

        self.assertEqual(
            m.failed_cbg_count,
            1,
        )  # CBG0 only

        self.assertEqual(
            m.retransmission_positions,
            12,
        )

        self.assertAlmostEqual(
            m.retransmission_overhead,
            0.3,
        )

        self.assertAlmostEqual(
            m.embb_delivery_efficiency,
            40 / 52,
        )

    def test_invalid_total_positions_raises(self):
        for bad in (0, -1, 2.5, "100", None, True):
            with self.subTest(total=bad):
                with self.assertRaises(ValueError):
                    calc(total=bad)

    def test_negative_preemption_raises(self):
        with self.assertRaises(ValueError):
            calc(preempted=-1)

    def test_preemption_above_total_raises(self):
        with self.assertRaises(ValueError):
            calc(total=100, preempted=101)

    def test_non_integer_preemption_raises(self):
        for bad in (1.5, "3", None, True):
            with self.subTest(preempted=bad):
                with self.assertRaises(ValueError):
                    calc(preempted=bad)

    def test_deterministic(self):
        kwargs = dict(
            total=40,
            preempted=5,
            cbs=[2, 8],
            cbgs=[0, 3],
            results=[
                res(0, False),
                res(3, True),
            ],
            requests=[
                RetransmissionRequest(0, 12)
            ],
        )

        self.assertEqual(
            calc(**kwargs),
            calc(**kwargs),
        )


if __name__ == "__main__":
    unittest.main()
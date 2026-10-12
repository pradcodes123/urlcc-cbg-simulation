
"""Tests for src/metrics.py."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cbg import affected_cbg_ids, group_code_blocks
from src.decoder import CBGDecodingResult, DecoderConfig, decode_cbgs
from src.embb import EmbbConfig, TransportBlock
from src.metrics import SimulationMetrics, calculate_metrics
from src.retransmission import (
    RetransmissionRequest,
    create_retransmission_requests,
)


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
    final_results=None,
    harq_retransmission_count=0,
    simulation_time_slots=20,
):
    return calculate_metrics(
        total_embb_positions=total,
        preempted_positions=preempted,
        affected_cb_ids=cbs,
        affected_cbg_ids=cbgs,
        initial_decoding_results=results,
        retransmission_requests=requests,
        final_decoding_results=final_results,
        harq_retransmission_count=harq_retransmission_count,
        simulation_time_slots=simulation_time_slots,
    )


class TestMetrics(unittest.TestCase):

    def test_no_preemption_no_failures_all_zero(self):
        m = calc(results=[res(0, True), res(1, True)])

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
                initial_failed_cbg_count=0,
                harq_recovered_cbg_count=0,
                initial_cbg_failure_rate=0.0,
                residual_bler=0.0,
                final_delivery_success_rate=1.0,
                harq_retransmission_count=0,
                delivered_embb_positions=2,
                embb_delivery_rate_per_slot=0.1,
            ),
        )

    def test_preemption_fraction(self):
        self.assertAlmostEqual(
            calc(total=288, preempted=29).preemption_fraction,
            29 / 288,
        )
        self.assertEqual(
            calc(total=50, preempted=50).preemption_fraction,
            1.0,
        )

    def test_duplicate_cb_ids_counted_once(self):
        self.assertEqual(calc(cbs=[1, 1, 2, 2, 2, 5]).affected_cb_count, 3)

    def test_duplicate_cbg_ids_counted_once(self):
        self.assertEqual(
            calc(cbgs=iter([0, 0, 3, 3])).affected_cbg_count,
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
        self.assertEqual(m.failed_cbg_count, 2)

    def test_retransmission_positions_summed(self):
        requests = [
            RetransmissionRequest(1, 12),
            RetransmissionRequest(3, 8),
        ]
        self.assertEqual(calc(requests=requests).retransmission_positions, 20)

    def test_retransmission_overhead(self):
        requests = [
            RetransmissionRequest(1, 12),
            RetransmissionRequest(3, 8),
        ]
        self.assertAlmostEqual(
            calc(total=40, requests=requests).retransmission_overhead,
            0.5,
        )

    def test_delivery_efficiency_no_retransmission(self):
        m = calc(total=100, preempted=10)
        self.assertEqual(m.embb_delivery_efficiency, 1.0)

    def test_delivery_efficiency_with_retransmission(self):
        m = calc(
            total=100,
            preempted=10,
            requests=[RetransmissionRequest(1, 20)],
        )
        self.assertAlmostEqual(m.embb_delivery_efficiency, 100 / 120)

    def test_realistic_combined_case(self):
        # 10 CBs x 4 positions = 40; four CBGs contain 12, 12, 8, 8 positions.
        tb = TransportBlock.from_config(
            EmbbConfig(num_code_blocks=10, coded_positions_per_cb=4)
        )
        cbgs = group_code_blocks(tb, 4)
        used = tb.used_positions()

        # Four hits in CB2 make CBG0 fail; one hit in CB8 leaves CBG3 successful.
        hit = used[8:12] + used[32:33]
        cb_ids = tb.affected_cb_ids(hit)
        cbg_ids = affected_cbg_ids(cbgs, cb_ids)

        decoded = decode_cbgs(
            tb,
            cbgs,
            hit,
            DecoderConfig(failure_threshold=0.25, model="threshold"),
        )
        requests = create_retransmission_requests(decoded, cbgs, tb)

        m = calculate_metrics(
            total_embb_positions=len(used),
            preempted_positions=len(hit),
            affected_cb_ids=cb_ids + cb_ids,
            affected_cbg_ids=cbg_ids,
            initial_decoding_results=decoded,
            retransmission_requests=requests,
        )

        self.assertEqual(m.preempted_positions, 5)
        self.assertEqual(m.total_embb_positions, 40)
        self.assertAlmostEqual(m.preemption_fraction, 0.125)
        self.assertEqual(m.affected_cb_count, 2)
        self.assertEqual(m.affected_cbg_count, 2)
        self.assertEqual(m.failed_cbg_count, 1)
        self.assertEqual(m.retransmission_positions, 12)
        self.assertAlmostEqual(m.retransmission_overhead, 0.3)
        self.assertAlmostEqual(m.embb_delivery_efficiency, 40 / 52)

    def test_invalid_total_positions_raises(self):
        for bad in (0, -1, 2.5, "100", None, True):
            with self.subTest(total=bad), self.assertRaises(ValueError):
                calc(total=bad)

    def test_negative_preemption_raises(self):
        with self.assertRaises(ValueError):
            calc(preempted=-1)

    def test_preemption_above_total_raises(self):
        with self.assertRaises(ValueError):
            calc(total=100, preempted=101)

    def test_non_integer_preemption_raises(self):
        for bad in (1.5, "3", None, True):
            with self.subTest(preempted=bad), self.assertRaises(ValueError):
                calc(preempted=bad)

    def test_repeated_retransmissions_charge_each_attempt(self):
        requests = [
            RetransmissionRequest(cbg_id=0, num_positions=24),
            RetransmissionRequest(cbg_id=1, num_positions=8),
        ]
        m = calc(total=100, requests=requests)
        self.assertEqual(m.retransmission_positions, 32)
        self.assertAlmostEqual(m.retransmission_overhead, 0.32)
        self.assertAlmostEqual(m.embb_delivery_efficiency, 100 / 132)

    def test_deterministic(self):
        kwargs = dict(
            total=40,
            preempted=5,
            cbs=[2, 8],
            cbgs=[0, 3],
            results=[res(0, False), res(3, True)],
            requests=[RetransmissionRequest(0, 12)],
        )
        self.assertEqual(calc(**kwargs), calc(**kwargs))

    def test_delivery_rate_when_all_data_is_delivered(self):
        results = [
            CBGDecodingResult(0, 60, 0, 0.0, True),
            CBGDecodingResult(1, 40, 0, 0.0, True),
        ]
        m = calc(
            total=100,
            results=results,
            final_results=results,
            simulation_time_slots=20,
        )
        self.assertEqual(m.delivered_embb_positions, 100)
        self.assertEqual(m.embb_delivery_rate_per_slot, 5.0)

    def test_delivery_rate_counts_only_successful_final_cbgs(self):
        initial = [
            CBGDecodingResult(0, 60, 10, 0.2, False),
            CBGDecodingResult(1, 40, 0, 0.0, False),
        ]
        final = [
            CBGDecodingResult(0, 60, 10, 0.2, True),
            CBGDecodingResult(1, 40, 0, 0.0, False),
        ]
        m = calc(
            total=100,
            preempted=10,
            results=initial,
            final_results=final,
            harq_retransmission_count=1,
            simulation_time_slots=20,
        )
        self.assertEqual(m.delivered_embb_positions, 60)
        self.assertEqual(m.embb_delivery_rate_per_slot, 3.0)
        self.assertEqual(m.harq_recovered_cbg_count, 1)

    def test_delivery_rate_is_zero_when_all_cbgs_fail(self):
        results = [
            CBGDecodingResult(0, 60, 20, 0.5, False),
            CBGDecodingResult(1, 40, 20, 0.5, False),
        ]
        m = calc(
            total=100,
            preempted=40,
            results=results,
            final_results=results,
            simulation_time_slots=20,
        )
        self.assertEqual(m.delivered_embb_positions, 0)
        self.assertEqual(m.embb_delivery_rate_per_slot, 0.0)

    def test_invalid_simulation_duration_raises(self):
        for bad in (0, -1, 2.5, "20", None, True):
            with self.subTest(duration=bad), self.assertRaises(ValueError):
                calc(
                    results=(),
                    simulation_time_slots=bad,
                )

    def test_delivery_rate_uses_configured_duration(self):
        results = [CBGDecodingResult(0, 80, 0, 0.0, True)]
        short = calc(
            total=80, results=results, simulation_time_slots=10
        )
        long = calc(
            total=80, results=results, simulation_time_slots=20
        )
        self.assertEqual(short.delivered_embb_positions, 80)
        self.assertEqual(long.delivered_embb_positions, 80)
        self.assertEqual(short.embb_delivery_rate_per_slot, 8.0)
        self.assertEqual(long.embb_delivery_rate_per_slot, 4.0)


def make_results(failure_count, total=10):
    return tuple(
        CBGDecodingResult(
            cbg_id=i,
            total_positions=10,
            hit_positions=1,
            damage_ratio=0.1,
            success=i >= failure_count,
            failure_probability=0.5,
            effective_snr_db=10.0,
        )
        for i in range(total)
    )


def calculate_for_failures(initial_failures, final_failures):
    return calculate_metrics(
        total_embb_positions=100,
        preempted_positions=0,
        affected_cb_ids=(),
        affected_cbg_ids=(),
        retransmission_requests=(),
        initial_decoding_results=make_results(initial_failures),
        final_decoding_results=make_results(final_failures),
        harq_retransmission_count=3,
    )


def test_harq_metrics_when_failures_are_recovered():
    metrics = calculate_for_failures(4, 1)
    assert metrics.initial_failed_cbg_count == 4
    assert metrics.failed_cbg_count == 1
    assert metrics.harq_recovered_cbg_count == 3
    assert metrics.initial_cbg_failure_rate == 0.40
    assert metrics.residual_bler == 0.10
    assert metrics.final_delivery_success_rate == 0.90
    assert metrics.harq_retransmission_count == 3
    assert metrics.delivered_embb_positions == 90


def test_harq_metrics_when_no_failures_are_recovered():
    metrics = calculate_for_failures(3, 3)
    assert metrics.initial_failed_cbg_count == 3
    assert metrics.failed_cbg_count == 3
    assert metrics.harq_recovered_cbg_count == 0
    assert metrics.initial_cbg_failure_rate == 0.30
    assert metrics.residual_bler == 0.30
    assert metrics.final_delivery_success_rate == 0.70
    assert metrics.delivered_embb_positions == 70


def test_harq_metrics_when_there_are_no_failures():
    metrics = calculate_for_failures(0, 0)
    assert metrics.initial_failed_cbg_count == 0
    assert metrics.failed_cbg_count == 0
    assert metrics.harq_recovered_cbg_count == 0
    assert metrics.initial_cbg_failure_rate == 0.0
    assert metrics.residual_bler == 0.0
    assert metrics.final_delivery_success_rate == 1.0
    assert metrics.delivered_embb_positions == 100


def test_harq_recovery_metrics():
    initial = [res(0, False), res(1, False), res(2, True)]
    final = [res(0, True), res(1, False), res(2, True)]

    m = calculate_metrics(
        total_embb_positions=100,
        preempted_positions=10,
        affected_cb_ids=[],
        affected_cbg_ids=[0, 1],
        initial_decoding_results=initial,
        final_decoding_results=final,
        retransmission_requests=[],
        harq_retransmission_count=1,
    )

    assert m.initial_failed_cbg_count == 2
    assert m.harq_recovered_cbg_count == 1
    assert m.failed_cbg_count == 1
    assert m.initial_cbg_failure_rate == 2 / 3
    assert m.residual_bler == 1 / 3
    assert m.final_delivery_success_rate == 2 / 3
    assert m.harq_retransmission_count == 1
    assert m.delivered_embb_positions == 2

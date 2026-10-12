"""Tests for src/scheduler.py (slot-based, deadline-aware URLLC scheduling).

Metrics are computed here from the returned results only, which also shows that
SchedulingResult carries enough information for them.
"""

import random
import subprocess
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.scheduler import (FAIL_DEADLINE_MISSED, FAIL_INSUFFICIENT_CAPACITY,  # noqa: E402
                           FAIL_SIMULATION_ENDED, SchedulerConfig,
                           SchedulingResult, schedule_urllc_events)
from src.urllc import URLLCConfig, URLLCEvent, generate_urllc_traffic  # noqa: E402


def ev(event_id, arrival, demand, deadline):
    """Shorthand for a URLLCEvent (deadline is an absolute, inclusive slot)."""
    return URLLCEvent(event_id=event_id, arrival_time=arrival,
                      resource_demand=demand, deadline=deadline)


def cfg(capacity=10, time=20, **kwargs):
    return SchedulerConfig(slot_capacity=capacity, simulation_time=time, **kwargs)


def by_id(results):
    return {r.event_id: r for r in results}


def metrics(results):
    """Everything the task asks to be derivable from the results."""
    ok = [r for r in results if r.success]
    return {
        "successes": len(ok),
        "failures": len(results) - len(ok),
        "success_rate": len(ok) / len(results) if results else 0.0,
        "requested": sum(r.resource_demand for r in results),
        "scheduled": sum(r.scheduled_resources for r in results),
        "deadline_misses": sum(r.failure_reason == FAIL_DEADLINE_MISSED for r in results),
    }


def assert_invariants(test, events, results, config):
    """Properties that must hold for every schedule."""
    test.assertEqual(len(results), len(events))                       # one result per event
    test.assertEqual(sorted(r.event_id for r in results), sorted(e.event_id for e in events))
    test.assertEqual([(r.arrival_time, r.event_id) for r in results],
                     sorted((r.arrival_time, r.event_id) for r in results))
    usage = defaultdict(int)
    for r in results:
        if r.success:
            test.assertGreaterEqual(r.completion_time, r.arrival_time)   # not before arrival
            test.assertLessEqual(r.completion_time, r.deadline)          # not after deadline
            test.assertLess(r.completion_time, config.simulation_time)
            usage[r.completion_time] += r.scheduled_resources
    for slot, used in usage.items():                                  # capacity respected
        test.assertLessEqual(used, config.slot_capacity, f"slot {slot} over capacity")
    test.assertEqual(sum(usage.values()),
                     sum(r.resource_demand for r in results if r.success))


class TestBasicScheduling(unittest.TestCase):

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(schedule_urllc_events([], cfg()), [])
        self.assertEqual(schedule_urllc_events(iter(()), cfg()), [])

    def test_events_that_fit_all_succeed(self):
        events = [ev(0, 0, 3, 2), ev(1, 0, 4, 2), ev(2, 1, 5, 3)]
        results = schedule_urllc_events(events, cfg(capacity=10))
        self.assertTrue(all(r.success for r in results))
        self.assertTrue(all(r.failure_reason is None for r in results))
        self.assertEqual([r.completion_time for r in results], [0, 0, 1])
        assert_invariants(self, events, results, cfg(capacity=10))

    def test_event_is_not_scheduled_before_arrival(self):
        results = schedule_urllc_events([ev(0, 3, 2, 6)], cfg())
        self.assertTrue(results[0].success)
        self.assertEqual(results[0].completion_time, 3)       # first possible slot, not 0

    def test_earliest_deadline_first_priority(self):
        # Capacity 5 fits only one of the two events per slot.
        results = by_id(schedule_urllc_events([ev(0, 0, 5, 3), ev(1, 0, 5, 1)],
                                              cfg(capacity=5)))
        self.assertEqual(results[1].completion_time, 0)       # earlier deadline goes first
        self.assertEqual(results[0].completion_time, 1)

    def test_equal_deadlines_resolved_by_arrival_then_event_id(self):
        events = [ev(5, 1, 3, 4), ev(2, 0, 3, 4), ev(9, 0, 3, 4)]
        results = by_id(schedule_urllc_events(events, cfg(capacity=3)))
        self.assertEqual(results[2].completion_time, 0)       # arrival 0, lowest id
        self.assertEqual(results[9].completion_time, 1)       # arrival 0, higher id
        self.assertEqual(results[5].completion_time, 2)       # arrival 1 comes last
        # Independent of the input order.
        shuffled = events[::-1]
        self.assertEqual(schedule_urllc_events(events, cfg(capacity=3)),
                         schedule_urllc_events(shuffled, cfg(capacity=3)))

    def test_event_cannot_succeed_after_its_deadline(self):
        # Slot 0 serves only one of two events; the other must NOT be served in slot 1.
        results = by_id(schedule_urllc_events([ev(0, 0, 2, 0), ev(1, 0, 2, 0)],
                                              cfg(capacity=2)))
        self.assertTrue(results[0].success)
        self.assertFalse(results[1].success)
        self.assertEqual(results[1].failure_reason, FAIL_DEADLINE_MISSED)
        self.assertIsNone(results[1].completion_time)
        self.assertEqual(results[1].scheduled_resources, 0)

    def test_deadline_is_inclusive(self):
        # Served in slot 1 == deadline: on time.
        results = by_id(schedule_urllc_events([ev(0, 0, 4, 1), ev(1, 0, 4, 1)],
                                              cfg(capacity=4)))
        self.assertEqual(sorted(r.completion_time for r in results.values()), [0, 1])
        self.assertTrue(all(r.success for r in results.values()))

    def test_demand_above_capacity_fails_cleanly(self):
        results = schedule_urllc_events([ev(0, 0, 9, 5)], cfg(capacity=4))
        r = results[0]
        self.assertEqual((r.success, r.failure_reason), (False, FAIL_INSUFFICIENT_CAPACITY))
        self.assertEqual((r.completion_time, r.scheduled_resources), (None, 0))

    def test_infeasible_event_does_not_block_feasible_ones(self):
        events = [ev(0, 0, 9, 5), ev(1, 0, 3, 5), ev(2, 1, 4, 5)]
        results = by_id(schedule_urllc_events(events, cfg(capacity=4)))
        self.assertEqual(results[0].failure_reason, FAIL_INSUFFICIENT_CAPACITY)
        self.assertTrue(results[1].success and results[2].success)

    def test_event_that_does_not_fit_this_slot_does_not_block_smaller_ones(self):
        # Slot 0 (capacity 4): X fits, Y does not (3 > 1 left), Z fits into the spare unit.
        events = [ev(0, 0, 3, 1), ev(1, 0, 3, 1), ev(2, 0, 1, 5)]
        results = by_id(schedule_urllc_events(events, cfg(capacity=4)))
        self.assertEqual(results[0].completion_time, 0)
        self.assertEqual(results[2].completion_time, 0)       # backfills the spare unit
        self.assertEqual(results[1].completion_time, 1)       # served later, still on time

    def test_simulation_end_reasons(self):
        # Capacity 2, two slots: A and B are served, C is still pending at its
        # (in-simulation) deadline, D could still have been served after the end.
        events = [ev(0, 0, 2, 1), ev(1, 0, 2, 1), ev(2, 0, 2, 1), ev(3, 0, 2, 9),
                  ev(4, 5, 2, 9), ev(5, 5, 7, 9)]
        results = by_id(schedule_urllc_events(events, cfg(capacity=2, time=2)))
        self.assertTrue(results[0].success and results[1].success)
        self.assertEqual(results[2].failure_reason, FAIL_DEADLINE_MISSED)
        self.assertEqual(results[3].failure_reason, FAIL_SIMULATION_ENDED)
        self.assertEqual(results[4].failure_reason, FAIL_SIMULATION_ENDED)   # arrives too late
        self.assertEqual(results[5].failure_reason, FAIL_INSUFFICIENT_CAPACITY)


class TestInputValidation(unittest.TestCase):

    def test_duplicate_event_ids_rejected(self):
        with self.assertRaises(ValueError):
            schedule_urllc_events([ev(1, 0, 2, 3), ev(1, 1, 2, 4)], cfg())

    def test_invalid_event_types_rejected(self):
        for bad in ([1], ["event"], [None], [{"event_id": 1}], [(0, 0, 1, 2)],
                    [ev(0, 0, 1, 2), object()]):
            with self.subTest(events=bad):
                with self.assertRaises(TypeError):
                    schedule_urllc_events(bad, cfg())
        for bad in (None, 5, "abc"):
            with self.subTest(events=bad):
                with self.assertRaises(TypeError):
                    schedule_urllc_events(bad, cfg())

    def test_invalid_event_fields_rejected(self):
        bad_events = [
            ev(0, 5, 2, 4),          # deadline before arrival
            ev(0, -1, 2, 4),         # negative arrival
            ev(0, 0, 0, 4),          # zero demand
            ev(0, 0, -3, 4),         # negative demand
            ev(0, 0, 2.5, 4),        # non-integer demand
            ev(0, 0.5, 2, 4),        # non-integer arrival
            ev(0, 0, 2, True),       # bool is not an integer
            ev("a", 0, 2, 4),        # non-integer id
        ]
        for bad in bad_events:
            with self.subTest(event=bad):
                with self.assertRaises(ValueError):
                    schedule_urllc_events([bad], cfg())

    def test_invalid_configurations_raise_value_error(self):
        for bad in (0, -1, 2.5, "3", None, True):
            with self.subTest(slot_capacity=bad):
                with self.assertRaises(ValueError):
                    SchedulerConfig(slot_capacity=bad, simulation_time=10)
            with self.subTest(simulation_time=bad):
                with self.assertRaises(ValueError):
                    SchedulerConfig(slot_capacity=4, simulation_time=bad)
        with self.assertRaises(TypeError):
            schedule_urllc_events([], {"slot_capacity": 4})

    def test_unsupported_policies_raise_value_error(self):
        for bad in ("fifo", "EDF", "", None, 1, "earliest_deadline_first "):
            with self.subTest(policy=bad):
                with self.assertRaises(ValueError):
                    SchedulerConfig(slot_capacity=4, simulation_time=10, policy=bad)
        self.assertEqual(SchedulerConfig(4, 10).policy, "earliest_deadline_first")

    def test_result_consistency_is_enforced_and_immutable(self):
        with self.assertRaises(ValueError):    # success without completion time
            SchedulingResult(0, 0, 2, 3, 3, None, True, None)
        with self.assertRaises(ValueError):    # failure with unknown reason
            SchedulingResult(0, 0, 2, 3, 0, None, False, "because")
        r = schedule_urllc_events([ev(0, 0, 3, 2)], cfg())[0]
        with self.assertRaises(Exception):
            r.success = False                  # frozen dataclass


class TestDeterminismAndInvariants(unittest.TestCase):

    def test_repeated_calls_are_identical_and_inputs_untouched(self):
        events = [ev(3, 2, 4, 6), ev(0, 0, 5, 2), ev(1, 0, 5, 2), ev(2, 1, 3, 3)]
        snapshot = list(events)
        a = schedule_urllc_events(events, cfg(capacity=5, time=10))
        b = schedule_urllc_events(events, cfg(capacity=5, time=10))
        self.assertEqual(a, b)
        self.assertEqual(events, snapshot)

    def test_results_ordered_by_arrival_then_event_id(self):
        events = [ev(7, 3, 1, 5), ev(2, 0, 1, 5), ev(1, 3, 1, 5), ev(5, 0, 1, 5)]
        results = schedule_urllc_events(events, cfg())
        self.assertEqual([r.event_id for r in results], [2, 5, 1, 7])

    def test_one_result_per_event_and_invariants_on_generated_traffic(self):
        for level, rate in (("low", 0.05), ("medium", 0.2), ("high", 0.5)):
            for capacity in (4, 8, 16):
                for seed in (1, 2, 3):
                    with self.subTest(level=level, capacity=capacity, seed=seed):
                        urllc_cfg = URLLCConfig(arrival_rate=rate, min_resource_demand=2,
                                                max_resource_demand=8, deadline=4,
                                                simulation_time=60)
                        events = generate_urllc_traffic(urllc_cfg, seed)
                        config = cfg(capacity=capacity, time=urllc_cfg.simulation_time)
                        results = schedule_urllc_events(events, config)
                        assert_invariants(self, events, results, config)
                        self.assertEqual(
                            results, schedule_urllc_events(list(reversed(events)), config))

    def test_invariants_on_random_stress_cases(self):
        rnd = random.Random(12345)                 # local RNG; no global state touched
        for case in range(200):
            n = rnd.randint(0, 25)
            events = []
            for i in range(n):
                arrival = rnd.randint(0, 12)
                events.append(ev(i, arrival, rnd.randint(1, 9), arrival + rnd.randint(0, 6)))
            config = cfg(capacity=rnd.randint(1, 10), time=rnd.randint(1, 16))
            with self.subTest(case=case):
                assert_invariants(self, events, schedule_urllc_events(events, config), config)

    def test_scheduled_resources_agree_with_successes(self):
        events = [ev(0, 0, 3, 0), ev(1, 0, 3, 0), ev(2, 0, 2, 4), ev(3, 1, 9, 4)]
        results = schedule_urllc_events(events, cfg(capacity=4, time=6))
        m = metrics(results)
        self.assertEqual(m["scheduled"], sum(r.resource_demand for r in results if r.success))
        self.assertTrue(all((r.scheduled_resources == r.resource_demand) == r.success
                            for r in results))

    def test_worked_example_and_metrics(self):
        # Capacity 4. All three arrive in slot 0:
        #   B: demand 3, deadline 0   A: demand 3, deadline 1   C: demand 2, deadline 1
        events = [ev(0, 0, 3, 1), ev(1, 0, 3, 0), ev(2, 0, 2, 1)]   # A, B, C
        results = by_id(schedule_urllc_events(events, cfg(capacity=4, time=5)))
        self.assertEqual(results[1].completion_time, 0)   # B first (deadline 0)
        self.assertEqual(results[0].completion_time, 1)   # A cannot fit beside B; served in slot 1
        self.assertEqual(results[2].failure_reason, FAIL_DEADLINE_MISSED)   # C: no room by slot 1
        m = metrics(list(results.values()))
        self.assertEqual((m["successes"], m["failures"], m["deadline_misses"]), (2, 1, 1))
        self.assertAlmostEqual(m["success_rate"], 2 / 3)
        self.assertEqual((m["requested"], m["scheduled"]), (8, 6))


class TestIsolation(unittest.TestCase):

    def test_module_is_standalone_and_leaves_existing_modules_alone(self):
        # Importing the scheduler must not pull in (or integrate with) the other
        # pipeline stages; the existing test-suite is therefore unaffected by it.
        code = ("import sys, src.scheduler\n"
                "banned = ['src.simulation', 'src.preemption', 'src.decoder',\n"
                "          'src.retransmission', 'src.metrics', 'src.cbg', 'src.embb']\n"
                "loaded = [m for m in banned if m in sys.modules]\n"
                "sys.exit(1 if loaded else 0)\n")
        proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
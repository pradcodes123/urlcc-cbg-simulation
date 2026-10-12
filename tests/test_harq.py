import dataclasses

import pytest

from src.harq import HARQAttempt, HARQConfig, HARQResult, simulate_harq


def config(max_attempts=4, feedback=2, retransmission=3):
    return HARQConfig(max_attempts, feedback, retransmission)


def test_immediate_success():
    result = simulate_harq("cbg-1", 10, 12, [True, False], config())
    assert result.delivered is True
    assert result.failure_reason is None
    assert len(result.attempts) == 1
    assert result.attempts[0] == HARQAttempt(1, 10, 11, True, 12.0)
    assert result.total_delay_slots == 1


def test_success_after_one_retry():
    result = simulate_harq(7, 4, 8, [False, True], config())
    assert [a.start_slot for a in result.attempts] == [4, 10]
    assert [a.completion_slot for a in result.attempts] == [5, 11]
    assert result.delivered is True
    assert result.total_delay_slots == 7


def test_success_after_multiple_retries():
    result = simulate_harq("x", 0, 2.5, [False, False, True], config())
    assert [a.attempt_number for a in result.attempts] == [1, 2, 3]
    assert [a.start_slot for a in result.attempts] == [0, 6, 12]
    assert result.delivered is True
    assert result.total_resource_cost == 7.5
    assert result.total_delay_slots == 13


def test_failure_at_maximum_attempts():
    result = simulate_harq("x", 0, 2, [False, False, False, True], config(max_attempts=3))
    assert result.delivered is False
    assert len(result.attempts) == 3
    assert result.failure_reason == "max_attempts_reached"
    assert result.total_resource_cost == 6


def test_outcomes_exhausted_before_success_or_limit():
    result = simulate_harq("x", 0, 1, [False], config(max_attempts=3))
    assert result.delivered is False
    assert len(result.attempts) == 1
    assert result.failure_reason == "outcomes_exhausted"


def test_empty_outcomes_return_no_attempts():
    result = simulate_harq("x", 5, 1, [], config())
    assert result.attempts == ()
    assert result.delivered is False
    assert result.failure_reason == "outcomes_exhausted"
    assert result.total_resource_cost == 0
    assert result.total_delay_slots == 0


def test_resource_cost_is_sum_of_attempts_actually_made():
    result = simulate_harq("x", 0, 4, [False, True, False], config())
    assert result.total_resource_cost == 8
    assert len(result.attempts) == 2


def test_feedback_and_retransmission_delays_are_both_applied():
    result = simulate_harq("x", 8, 1, [False, False, True], config(3, 1, 4))
    assert [a.start_slot for a in result.attempts] == [8, 14, 20]
    assert result.total_delay_slots == 13


def test_zero_delays_allow_next_attempt_after_completion():
    result = simulate_harq("x", 2, 1, [False, True], config(2, 0, 0))
    assert [a.start_slot for a in result.attempts] == [2, 3]


def test_outcomes_after_success_are_not_consumed():
    result = simulate_harq("x", 0, 1, [True, False, False], config())
    assert len(result.attempts) == 1
    assert result.attempts[0].success is True


def test_result_structure_is_deterministic_and_immutable():
    first = simulate_harq("group", 3, 2, [False, True], config())
    second = simulate_harq("group", 3, 2, [False, True], config())
    assert first == second
    assert isinstance(first, HARQResult)
    assert isinstance(first.attempts, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.delivered = False
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.attempts[0].success = False


@pytest.mark.parametrize("field,value", [
    ("max_attempts", 0), ("max_attempts", -1),
    ("max_attempts", True), ("max_attempts", 1.5),
    ("feedback_delay_slots", -1), ("feedback_delay_slots", True),
    ("feedback_delay_slots", 1.2),
    ("retransmission_delay_slots", -1),
    ("retransmission_delay_slots", False),
    ("retransmission_delay_slots", 0.5),
])
def test_invalid_configuration(field, value):
    values = {"max_attempts": 3, "feedback_delay_slots": 1, "retransmission_delay_slots": 1}
    values[field] = value
    with pytest.raises((TypeError, ValueError)):
        HARQConfig(**values)


@pytest.mark.parametrize("initial_slot", [-1, True, 1.5, "1"])
def test_invalid_initial_slot(initial_slot):
    with pytest.raises((TypeError, ValueError)):
        simulate_harq("x", initial_slot, 1, [True], config())


@pytest.mark.parametrize("cost", [-1, True, float("nan"), float("inf"), "2"])
def test_invalid_resource_cost(cost):
    with pytest.raises((TypeError, ValueError)):
        simulate_harq("x", 0, cost, [True], config())


@pytest.mark.parametrize("entity_id", [None, [], float("nan"), float("inf")])
def test_invalid_entity_id(entity_id):
    with pytest.raises((TypeError, ValueError)):
        simulate_harq(entity_id, 0, 1, [True], config())


@pytest.mark.parametrize("outcomes", [[1], [None], ["True"], [True, 0], "True", b"1"])
def test_invalid_outcome_types(outcomes):
    with pytest.raises(TypeError):
        simulate_harq("x", 0, 1, outcomes, config())


def test_invalid_config_object():
    with pytest.raises(TypeError, match="HARQConfig"):
        simulate_harq("x", 0, 1, [True], object())


def test_boolean_entity_id_is_allowed_as_hashable_identifier():
    # Boolean rejection applies to integer configuration/timing fields, not IDs.
    result = simulate_harq(True, 0, 1, [True], config())
    assert result.entity_id is True

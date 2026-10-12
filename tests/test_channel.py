import math

import numpy as np
import pytest

from src.channel import ChannelConfig, ChannelSample, generate_channel_samples


def config(**overrides):
    values = dict(mean_snr_db=10.0, snr_std_db=2.0,
                  min_snr_db=0.0, max_snr_db=20.0)
    values.update(overrides)
    return ChannelConfig(**values)


def test_same_seed_is_reproducible():
    ids = ["cbg-1", "cbg-2", "cbg-3", "cbg-4"]
    assert generate_channel_samples(ids, config(), seed=123) == generate_channel_samples(
        ids, config(), seed=123
    )


def test_different_seeds_generally_vary_samples():
    ids = list(range(100))
    first = generate_channel_samples(ids, config(), seed=1)
    second = generate_channel_samples(ids, config(), seed=2)
    assert [x.snr_db for x in first] != [x.snr_db for x in second]


def test_zero_standard_deviation_returns_clipped_mean():
    ids = ["a", "b", "c"]
    samples = generate_channel_samples(
        ids, config(mean_snr_db=25.0, snr_std_db=0.0), seed=7
    )
    assert [sample.snr_db for sample in samples] == [20.0, 20.0, 20.0]


def test_zero_standard_deviation_in_range_returns_mean():
    samples = generate_channel_samples([1, 2], config(snr_std_db=0.0), seed=7)
    assert [sample.snr_db for sample in samples] == [10.0, 10.0]


def test_all_outputs_are_within_configured_bounds():
    samples = generate_channel_samples(range(1000), config(snr_std_db=30.0), seed=42)
    assert all(0.0 <= sample.snr_db <= 20.0 for sample in samples)


def test_empty_input_returns_empty_list():
    assert generate_channel_samples([], config(), seed=0) == []


def test_duplicate_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        generate_channel_samples(["a", "b", "a"], config(), seed=0)


@pytest.mark.parametrize("kwargs", [
    {"mean_snr_db": math.nan},
    {"mean_snr_db": math.inf},
    {"snr_std_db": -0.1},
    {"snr_std_db": math.inf},
    {"min_snr_db": math.nan},
    {"max_snr_db": math.inf},
    {"min_snr_db": 5.0, "max_snr_db": 5.0},
    {"min_snr_db": 6.0, "max_snr_db": 5.0},
    {"model": "rayleigh"},
])
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises((TypeError, ValueError)):
        config(**kwargs)


def test_non_numeric_configuration_is_rejected():
    with pytest.raises(TypeError):
        config(mean_snr_db="10")


@pytest.mark.parametrize("ids", [[None], [["unhashable"]], [float("nan")]])
def test_invalid_ids_are_rejected(ids):
    with pytest.raises((TypeError, ValueError)):
        generate_channel_samples(ids, config(), seed=0)


def test_one_output_per_input_and_output_type():
    ids = ["block-A", 17, (2, 3)]
    samples = generate_channel_samples(ids, config(), seed=10)
    assert len(samples) == len(ids)
    assert all(isinstance(sample, ChannelSample) for sample in samples)
    assert [sample.entity_id for sample in samples] == ids


def test_output_order_matches_input_order():
    ids = ["third", "first", "second"]
    samples = generate_channel_samples(ids, config(), seed=5)
    assert [sample.entity_id for sample in samples] == ids


def test_config_and_sample_are_immutable():
    cfg = config()
    sample = generate_channel_samples(["x"], cfg, seed=1)[0]
    with pytest.raises((AttributeError, TypeError)):
        cfg.mean_snr_db = 12.0
    with pytest.raises((AttributeError, TypeError)):
        sample.snr_db = 12.0


def test_seed_must_be_a_non_negative_integer():
    for seed, error in [(1.5, TypeError), (True, TypeError), (-1, ValueError)]:
        with pytest.raises(error):
            generate_channel_samples([1], config(), seed=seed)


def test_numpy_generator_is_used_without_changing_global_rng():
    np.random.seed(101)
    before = np.random.random()
    generate_channel_samples([1, 2, 3], config(), seed=9)
    after = np.random.random()
    np.random.seed(101)
    assert before == np.random.random()
    assert after == np.random.random()

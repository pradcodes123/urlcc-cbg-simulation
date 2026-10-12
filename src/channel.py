"""Simple, reproducible statistical channel-quality samples.

This module is a lightweight abstraction for simulation studies, not a physical
wireless-channel simulator. Each entity receives an independent statistical
SNR draw; samples are not time-correlated fading and do not model a waveform.

The ``lognormal_shadowing`` label denotes a simplified model in which SNR is
varied normally in dB (a common statistical shadowing abstraction). It does not
claim to reproduce a complete lognormal propagation or fading process.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Hashable, Iterable

import numpy as np


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Configuration for statistical SNR sampling, with SNR expressed in dB."""

    mean_snr_db: float
    snr_std_db: float
    min_snr_db: float
    max_snr_db: float
    model: str = "lognormal_shadowing"

    def __post_init__(self) -> None:
        numeric_values = {
            "mean_snr_db": self.mean_snr_db,
            "snr_std_db": self.snr_std_db,
            "min_snr_db": self.min_snr_db,
            "max_snr_db": self.max_snr_db,
        }
        for name, value in numeric_values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
                raise TypeError(f"{name} must be a finite number")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")

        if self.snr_std_db < 0:
            raise ValueError("snr_std_db must be non-negative")
        if self.min_snr_db >= self.max_snr_db:
            raise ValueError("min_snr_db must be less than max_snr_db")
        if self.model != "lognormal_shadowing":
            raise ValueError("model must be 'lognormal_shadowing'")


@dataclass(frozen=True, slots=True)
class ChannelSample:
    """One entity's sampled channel quality."""

    entity_id: Hashable
    snr_db: float


def _validate_entity_ids(entity_ids: Iterable[Hashable]) -> list[Hashable]:
    try:
        ids = list(entity_ids)
    except TypeError as exc:
        raise TypeError("entity_ids must be an iterable of hashable IDs") from exc

    seen: set[Hashable] = set()
    for entity_id in ids:
        if entity_id is None:
            raise ValueError("entity IDs must not be None")
        try:
            if entity_id in seen:
                raise ValueError(f"duplicate entity ID: {entity_id!r}")
            seen.add(entity_id)
        except TypeError as exc:
            raise TypeError("entity IDs must be hashable") from exc
        if isinstance(entity_id, (float, np.floating)) and math.isnan(float(entity_id)):
            raise ValueError("entity IDs must not be NaN")
    return ids


def generate_channel_samples(
    entity_ids: Iterable[Hashable], config: ChannelConfig, seed: int
) -> list[ChannelSample]:
    """Generate one independently drawn, clipped SNR sample per entity ID.

    The output order matches the supplied ID order. A local NumPy
    ``default_rng(seed)`` makes output reproducible without changing global RNG
    state. Values are sampled from a normal distribution in dB and clipped to
    ``[min_snr_db, max_snr_db]``. Consequently, when ``snr_std_db`` is zero, the
    output is the configured mean clipped to those bounds, even if the mean is
    outside them.
    """
    if not isinstance(config, ChannelConfig):
        raise TypeError("config must be a ChannelConfig instance")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise TypeError("seed must be an integer")
    if seed < 0:
        raise ValueError("seed must be non-negative")

    ids = _validate_entity_ids(entity_ids)
    if not ids:
        return []

    rng = np.random.default_rng(int(seed))
    values = rng.normal(
        loc=float(config.mean_snr_db),
        scale=float(config.snr_std_db),
        size=len(ids),
    )
    values = np.clip(values, float(config.min_snr_db), float(config.max_snr_db))
    return [ChannelSample(entity_id=entity_id, snr_db=float(snr))
            for entity_id, snr in zip(ids, values, strict=True)]

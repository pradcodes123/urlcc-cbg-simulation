"""Controlled CBG decoding after URLLC preemption (research abstraction).

NOT a real NR PHY decoder: no LDPC, OFDM, MIMO, channel estimation or HARQ
combining. For every CBG the decoder computes

    damage_ratio = hit_positions / total_positions      (unchanged)

and then decides success or failure with a pluggable *decoding model*:

    "snr"       (default) stochastic erasure/outage model, described below
    "threshold" legacy deterministic rule: fail iff damage_ratio >= failure_threshold

"Affected" (hit_positions > 0) and "failed" (decoding fails) stay different
concepts: a CBG can be affected yet still decode successfully.

---------------------------------------------------------------------------
SNR model (``SnrLinkModel``)
---------------------------------------------------------------------------
Assumptions
  A1. Preempted positions are *known erasures* of the CBG's coded symbols (as if
      the UE had received a pre-emption indication). The remaining positions are
      received over an AWGN channel with average SNR ``snr_db``.
  A2. Only the erased FRACTION d = damage_ratio matters, not where the erasures
      sit inside the CBG (ideal interleaving). A CBG is decoded as one coded unit.
  A3. The code operates at spectral efficiency eta (information bits per coded
      symbol) with a fixed implementation gap to capacity.

Model
  1. Capacity of an AWGN channel with an erased fraction d of its symbols is
         C(d) = (1 - d) * log2(1 + snr).
     The *effective SNR* is the SNR of an erasure-free channel with the same
     capacity:   log2(1 + snr_eff) = (1 - d) * log2(1 + snr)
                 =>   snr_eff = (1 + snr)^(1 - d) - 1.
     So snr_eff = snr at d = 0 and snr_eff -> 0 (-inf dB) as d -> 1.
  2. Decoding needs C >= eta, i.e. snr_eff >= 2^eta - 1. A real code needs a
     margin ``gap_db`` above that bound:
         required_db = 10*log10(2^eta - 1) + gap_db.
  3. Link variability: the required SNR (in dB) is treated as Gaussian with mean
     required_db and standard deviation ``sigma_db`` (a standard cumulative-Gaussian
     fit of the BLER "waterfall" curve). With margin = snr_eff_db - required_db:
         P_fail = Q(margin / sigma_db) = 0.5 * erfc(margin / (sigma_db * sqrt(2))).
  4. The outcome is drawn with ONE uniform number u per CBG from a seeded NumPy
     Generator:  failure  <=>  u < P_fail.

Properties: P_fail increases with damage_ratio, decreases with snr_db, is exactly
1 at damage_ratio = 1 (nothing received) and is tiny, but not zero, at zero damage
on a good link. Using the same u for every CBG draw means that, for a fixed seed,
more damage can never turn a failure into a success.

Limitations: parameters are illustrative defaults, not calibrated to NR MCS/BLER
tables; no fading, interference, HARQ combining or per-CB decoding; no per-CBG
channel variation (all randomness is the sigma_db spread plus the Bernoulli draw).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, Sequence

import numpy as np

from src.cbg import CodeBlockGroup
from src.embb import ResourcePosition, TransportBlock

MODELS = ("snr", "threshold")
_DECODER_STREAM_ID = 0xDEC0   # keeps decoder draws independent of URLLC/preemption streams


def _is_real(x: object) -> bool:
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)


@dataclass(frozen=True)
class DecoderConfig:
    """Decoder abstraction parameters.

    ``failure_threshold`` is used only by the legacy ``model="threshold"`` rule
    but is always validated. The remaining fields parametrise the ``"snr"`` model.
    """

    failure_threshold: float = 0.25   # legacy rule: fail if damage_ratio >= this
    model: str = "snr"                # "snr" (stochastic) or "threshold" (legacy)
    snr_db: float = 12.0              # average link SNR
    spectral_efficiency: float = 2.0  # eta: information bits per coded symbol (> 0)
    gap_db: float = 1.0               # implementation gap above the capacity bound
    sigma_db: float = 1.0             # std-dev of the required SNR in dB (> 0)

    def __post_init__(self) -> None:
        t = self.failure_threshold
        if not _is_real(t) or not 0.0 <= t <= 1.0:
            raise ValueError(f"failure_threshold must be in [0.0, 1.0], got {t!r}")
        if self.model not in MODELS:
            raise ValueError(f"model must be one of {list(MODELS)}, got {self.model!r}")
        for name in ("snr_db", "gap_db"):
            if not _is_real(getattr(self, name)):
                raise ValueError(f"{name} must be a finite number, got {getattr(self, name)!r}")
        for name in ("spectral_efficiency", "sigma_db"):
            v = getattr(self, name)
            if not _is_real(v) or v <= 0:
                raise ValueError(f"{name} must be a positive finite number, got {v!r}")


@dataclass(frozen=True)
class CBGDecodingResult:
    """Decoding outcome of one CBG.

    ``failure_probability`` and ``effective_snr_db`` are filled in by the decoder
    (``effective_snr_db`` is None for the legacy threshold model).
    """

    cbg_id: int
    total_positions: int
    hit_positions: int
    damage_ratio: float
    success: bool
    failure_probability: Optional[float] = None
    effective_snr_db: Optional[float] = None


# --------------------------------------------------------------------------
# Decoding models (replaceable): evaluate(damage_ratio) -> (P_fail, snr_eff_db)
# --------------------------------------------------------------------------
class DecodingModel(Protocol):
    """Interface of a decoding model; implement this to plug in a new one."""

    stochastic: bool

    def evaluate(self, damage_ratio: float) -> tuple[float, Optional[float]]:
        """Return (failure probability, effective SNR in dB or None)."""


@dataclass(frozen=True)
class ThresholdModel:
    """Legacy deterministic rule as a degenerate model: P_fail is 0 or 1."""

    failure_threshold: float
    stochastic: bool = False

    def evaluate(self, damage_ratio: float) -> tuple[float, Optional[float]]:
        return (1.0 if damage_ratio >= self.failure_threshold else 0.0), None


@dataclass(frozen=True)
class SnrLinkModel:
    """Erasure-capacity outage model with Gaussian dB spread (see module docstring)."""

    snr_db: float
    spectral_efficiency: float
    gap_db: float
    sigma_db: float
    stochastic: bool = True

    @property
    def required_snr_db(self) -> float:
        """10*log10(2^eta - 1) + gap: SNR needed for an erasure-free CBG."""
        return 10.0 * math.log10(math.expm1(self.spectral_efficiency * math.log(2.0))) \
            + self.gap_db

    def effective_snr_db(self, damage_ratio: float) -> float:
        """SNR (dB) of an erasure-free channel with the same capacity; -inf at d=1."""
        if damage_ratio >= 1.0:
            return -math.inf
        snr_lin = 10.0 ** (self.snr_db / 10.0)
        eff_lin = math.expm1((1.0 - damage_ratio) * math.log1p(snr_lin))
        return 10.0 * math.log10(eff_lin) if eff_lin > 0 else -math.inf

    def evaluate(self, damage_ratio: float) -> tuple[float, Optional[float]]:
        eff_db = self.effective_snr_db(damage_ratio)
        margin = eff_db - self.required_snr_db
        p_fail = 0.5 * math.erfc(margin / (self.sigma_db * math.sqrt(2.0)))
        return min(1.0, max(0.0, p_fail)), eff_db


def make_model(config: DecoderConfig) -> DecodingModel:
    """Build the decoding model selected by ``config.model``."""
    if config.model == "threshold":
        return ThresholdModel(config.failure_threshold)
    return SnrLinkModel(config.snr_db, config.spectral_efficiency,
                        config.gap_db, config.sigma_db)


# --------------------------------------------------------------------------
# Decoding
# --------------------------------------------------------------------------
def decode_cbgs(transport_block: TransportBlock,
                cbgs: Sequence[CodeBlockGroup],
                preempted_positions: Iterable[ResourcePosition],
                config: Optional[DecoderConfig] = None,
                seed: Optional[int] = None,
                rng: Optional[np.random.Generator] = None,
                model: Optional[DecodingModel] = None,
                ) -> tuple[CBGDecodingResult, ...]:
    """Decide success/failure of each CBG from its damage ratio.

    Args:
        config: decoder parameters (default ``DecoderConfig()``).
        seed: non-negative int. A dedicated generator is derived from it, so the
            same seed and inputs give identical results. Required by stochastic
            models, ignored by deterministic ones.
        rng: alternative to ``seed``: a caller-owned Generator (not both).
        model: optional custom ``DecodingModel`` overriding ``config.model``.

    Returns:
        Results ordered by ``cbg_id``. Exactly one uniform number is drawn per
        CBG, in ``cbg_id`` order, so the random stream use does not depend on
        the outcomes.

    Raises:
        ValueError: invalid seed, seed and rng both given, a stochastic model
            without seed/rng, or a CBG with no mapped positions.
    """
    config = config or DecoderConfig()
    model = model or make_model(config)

    if seed is not None and rng is not None:
        raise ValueError("give either seed or rng, not both")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int) or seed < 0):
        raise ValueError(f"seed must be a non-negative integer, got {seed!r}")
    if model.stochastic and seed is None and rng is None:
        raise ValueError("a stochastic decoding model needs a seed (or rng) for reproducibility")
    if model.stochastic and rng is None:
        rng = np.random.default_rng([seed, _DECODER_STREAM_ID])

    preempted = frozenset(preempted_positions)   # consume the iterable once

    results = []
    for cbg in sorted(cbgs, key=lambda g: g.cbg_id):
        cb_list = [transport_block.get_cb(cb_id) for cb_id in cbg.cb_ids]
        total = sum(len(cb.positions) for cb in cb_list)
        if total == 0:
            raise ValueError(f"CBG {cbg.cbg_id} has no mapped resource positions")
        # CB positions are disjoint (enforced by embb.py), so hits just add up.
        hits = sum(len(cb.position_set & preempted) for cb in cb_list)
        ratio = hits / total

        p_fail, eff_db = model.evaluate(ratio)
        # u in [0, 1): p = 1 always fails and p = 0 never fails, so the legacy
        # deterministic rule (p in {0, 1}) is reproduced exactly without randomness.
        u = rng.random() if model.stochastic else 0.5
        failed = u < p_fail
        results.append(CBGDecodingResult(
            cbg_id=cbg.cbg_id, total_positions=total, hit_positions=hits,
            damage_ratio=ratio, success=not failed,
            failure_probability=p_fail, effective_snr_db=eff_db))
    return tuple(results)
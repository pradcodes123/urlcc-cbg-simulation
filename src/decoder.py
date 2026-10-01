"""Controlled CBG decoding after URLLC preemption (research abstraction).

NOT a real NR PHY decoder: no LDPC, modulation, SNR, BLER, channel or MIMO.
A CBG fails when the fraction of its mapped positions that were preempted
reaches a configured threshold:

    damage_ratio = hit_positions / total_positions
    failure      = damage_ratio >= failure_threshold

"Affected" (hit_positions > 0) and "failed" (damage_ratio >= threshold) are
different concepts: a CBG can be affected yet still decode successfully.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from src.cbg import CodeBlockGroup
from src.embb import ResourcePosition, TransportBlock


@dataclass(frozen=True)
class DecoderConfig:
    """Decoder abstraction parameters."""

    failure_threshold: float = 0.25   # CBG fails if damage_ratio >= this

    def __post_init__(self) -> None:
        t = self.failure_threshold
        if (isinstance(t, bool) or not isinstance(t, (int, float))
                or not math.isfinite(t) or not 0.0 <= t <= 1.0):
            raise ValueError(f"failure_threshold must be in [0.0, 1.0], got {t!r}")


@dataclass(frozen=True)
class CBGDecodingResult:
    """Decoding outcome of one CBG."""

    cbg_id: int
    total_positions: int
    hit_positions: int
    damage_ratio: float
    success: bool


def decode_cbgs(transport_block: TransportBlock,
                cbgs: Sequence[CodeBlockGroup],
                preempted_positions: Iterable[ResourcePosition],
                config: Optional[DecoderConfig] = None,
                ) -> tuple[CBGDecodingResult, ...]:
    """Decide success/failure of each CBG from its preemption damage ratio.

    Returns results ordered by ``cbg_id``. Raises ValueError for a CBG with
    no mapped positions.
    """
    config = config or DecoderConfig()
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
        results.append(CBGDecodingResult(
            cbg_id=cbg.cbg_id, total_positions=total, hit_positions=hits,
            damage_ratio=ratio, success=not ratio >= config.failure_threshold))
    return tuple(results)
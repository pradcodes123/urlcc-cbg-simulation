"""URLLC preemption of eMBB resources on the abstract grid (RQ2 building block).

A controlled 5G-NR-inspired abstraction, NOT an NR scheduler. Given a
TransportBlock and URLLC events, it selects WHICH eMBB-occupied positions are
preempted. All patterns preempt the SAME number of positions; only their
spatial distribution differs:

    concentrated : one contiguous run (centred) in the TB's linear order
    distributed  : evenly spaced positions across the whole TB
    random       : uniform random subset (seeded numpy Generator)

Deciding CBG failure (decoder.py) and retransmission (retransmission.py) is
out of scope here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

from src.embb import ResourcePosition, TransportBlock
from src.urllc import URLLCEvent

PATTERNS: Tuple[str, ...] = ("concentrated", "distributed", "random")


@dataclass(frozen=True)
class PreemptionResult:
    """Outcome of one preemption: which eMBB positions were taken."""

    pattern: str
    requested_count: int                      # n resolved from fraction/count/events
    total_embb_positions: int
    preempted_positions: Tuple[ResourcePosition, ...]   # in TB (CB) order
    seed: Optional[int] = None                # only used by "random"

    @property
    def preempted_count(self) -> int:
        return len(self.preempted_positions)

    @property
    def preempted_fraction(self) -> float:
        return self.preempted_count / self.total_embb_positions


def _resolve_count(total: int, urllc_events: Sequence[URLLCEvent],
                   fraction: Optional[float], num_preempt: Optional[int]) -> int:
    """Resolve the number of eMBB positions to preempt, with validation."""
    if fraction is not None and num_preempt is not None:
        raise ValueError("give either preemption_fraction or num_preempt, not both")
    if fraction is not None:
        if (isinstance(fraction, bool) or not isinstance(fraction, (int, float))
                or not math.isfinite(fraction) or not 0 <= fraction <= 1):
            raise ValueError(f"preemption_fraction must be in [0, 1], got {fraction!r}")
        n = round(total * fraction)
        if fraction > 0 and n == 0:
            raise ValueError(
                f"fraction {fraction} of {total} positions rounds to 0; increase it")
    elif num_preempt is not None:
        if isinstance(num_preempt, bool) or not isinstance(num_preempt, int) or num_preempt < 0:
            raise ValueError(f"num_preempt must be a non-negative int, got {num_preempt!r}")
        n = num_preempt
    else:
        # Same-slot events are simultaneous: just sum demand (1 unit = 1 position).
        n = sum(e.resource_demand for e in urllc_events)
    if n > total:
        raise ValueError(f"cannot preempt {n} positions; TB occupies only {total}")
    return n


def _select_indices(pattern: str, total: int, n: int, seed: Optional[int]) -> List[int]:
    """Pick n distinct indices in [0, total) according to the pattern."""
    if n == 0:
        return []
    if pattern == "concentrated":
        start = (total - n) // 2
        return list(range(start, start + n))
    if pattern == "distributed":
        return [(2 * i + 1) * total // (2 * n) for i in range(n)]
    rng = np.random.default_rng(seed)       # "random"
    return sorted(int(i) for i in rng.choice(total, size=n, replace=False))


def generate_preemption(transport_block: TransportBlock,
                        urllc_events: Sequence[URLLCEvent],
                        pattern: str,
                        preemption_fraction: Optional[float] = None,
                        num_preempt: Optional[int] = None,
                        seed: Optional[int] = None) -> PreemptionResult:
    """Select the eMBB positions preempted by URLLC traffic.

    Args:
        transport_block: eMBB TB; only its occupied positions can be preempted.
        urllc_events: used only to derive the amount when neither
            ``preemption_fraction`` nor ``num_preempt`` is supplied.
        pattern: "concentrated", "distributed" or "random".
        preemption_fraction: fraction of eMBB positions to preempt, in [0, 1].
        num_preempt: explicit number of positions (alternative to fraction).
        seed: required (non-negative int) for "random"; ignored otherwise.

    Raises:
        ValueError: on an unknown pattern, bad fraction/count/seed, or a
            request exceeding the available eMBB positions.
    """
    if pattern not in PATTERNS:
        raise ValueError(f"Unknown pattern {pattern!r}; expected one of {list(PATTERNS)}")
    if pattern == "random" and (isinstance(seed, bool) or not isinstance(seed, int)
                                or seed < 0):
        raise ValueError(f"'random' pattern needs a non-negative integer seed, got {seed!r}")

    used = transport_block.used_positions()
    total = len(used)
    n = _resolve_count(total, urllc_events, preemption_fraction, num_preempt)
    indices = _select_indices(pattern, total, n, seed)

    return PreemptionResult(
        pattern=pattern,
        requested_count=n,
        total_embb_positions=total,
        preempted_positions=tuple(used[i] for i in indices),
        seed=seed if pattern == "random" else None,
    )


def affected_cbs(transport_block: TransportBlock, result: PreemptionResult) -> List[int]:
    """Sorted IDs of CBs hit by the preemption (delegates to embb.py)."""
    return transport_block.affected_cb_ids(result.preempted_positions)


if __name__ == "__main__":
    from src.cbg import affected_cbg_ids, group_code_blocks
    from src.embb import EmbbConfig

    tb = TransportBlock.from_config(EmbbConfig())
    cbgs = group_code_blocks(tb, max_cbgs=4)
    for pat in PATTERNS:
        r = generate_preemption(tb, [], pat, preemption_fraction=0.10, seed=42)
        cbs = affected_cbs(tb, r)
        print(f"{pat:>12}: {r.preempted_count}/{r.total_embb_positions} positions, "
              f"CBs {cbs}, CBGs {affected_cbg_ids(cbgs, cbs)}")
"""URLLC preemption of eMBB resources on the logical time-frequency grid.

This module selects eligible eMBB resource elements (REs) to preempt. The
patterns preempt the same number of eligible REs; their time-frequency
placement differs:

* concentrated: a compact rectangle, when possible, around the grid centre;
* distributed: positions sampled across the grid in a deterministic spatial
  ordering, spread over time and frequency;
* random: a uniform random subset of eligible positions (seeded).

This is a controlled resource-allocation abstraction, NOT a 3GPP NR scheduler.
The spatial patterns are experimental definitions, not standardized NR
preemption procedures. Decoding and retransmission accounting are separate.
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
    """Outcome of one preemption: which eligible eMBB REs were taken."""

    pattern: str
    requested_count: int
    total_embb_positions: int
    preempted_positions: Tuple[ResourcePosition, ...]
    seed: Optional[int] = None

    @property
    def preempted_count(self) -> int:
        return len(self.preempted_positions)

    @property
    def preempted_fraction(self) -> float:
        return self.preempted_count / self.total_embb_positions


def _resolve_count(
    total: int,
    urllc_events: Sequence[URLLCEvent],
    fraction: Optional[float],
    num_preempt: Optional[int],
) -> int:
    """Resolve the requested number of eligible REs, with validation."""
    if fraction is not None and num_preempt is not None:
        raise ValueError("give either preemption_fraction or num_preempt, not both")

    if fraction is not None:
        if (
            isinstance(fraction, bool)
            or not isinstance(fraction, (int, float))
            or not math.isfinite(fraction)
            or not 0 <= fraction <= 1
        ):
            raise ValueError(
                f"preemption_fraction must be in [0, 1], got {fraction!r}"
            )
        n = round(total * fraction)
        if fraction > 0 and n == 0:
            raise ValueError(
                f"fraction {fraction} of {total} positions rounds to 0; increase it"
            )
    elif num_preempt is not None:
        if (
            isinstance(num_preempt, bool)
            or not isinstance(num_preempt, int)
            or num_preempt < 0
        ):
            raise ValueError(
                f"num_preempt must be a non-negative int, got {num_preempt!r}"
            )
        n = num_preempt
    else:
        # Demand is expressed in abstract eligible-RE units. Events in this
        # trial are treated as simultaneous; no scheduler/queueing is modeled.
        n = sum(e.resource_demand for e in urllc_events)

    if n > total:
        raise ValueError(
            f"cannot preempt {n} positions; TB occupies only {total}"
        )
    return n


def _position_key(position: ResourcePosition) -> tuple[int, int]:
    return position.symbol, position.subcarrier


def _select_concentrated(
    eligible: Sequence[ResourcePosition], n: int
) -> List[ResourcePosition]:
    """Choose a compact time-frequency region around the grid centre.

    The greedy expansion prefers positions nearest the grid centre, then
    nearest already-selected positions. The result is spatially compact for
    ordinary rectangular allocations, while remaining valid for irregular
    eligible-RE masks. Tie-breaking is deterministic.
    """
    if n == 0:
        return []

    symbols = [p.symbol for p in eligible]
    subcarriers = [p.subcarrier for p in eligible]
    centre_t = (min(symbols) + max(symbols)) / 2
    centre_f = (min(subcarriers) + max(subcarriers)) / 2

    # For small/medium study grids, sorting all eligible REs by their
    # distance from the centre is simple, deterministic, and fast enough.
    ranked = sorted(
        eligible,
        key=lambda p: (
            (p.symbol - centre_t) ** 2 + (p.subcarrier - centre_f) ** 2,
            p.symbol,
            p.subcarrier,
        ),
    )
    return ranked[:n]


def _select_distributed(
    eligible: Sequence[ResourcePosition], n: int
) -> List[ResourcePosition]:
    """Choose positions spread over the ordered time-frequency allocation.

    Candidate REs are ordered by symbol then subcarrier. Selecting midpoint
    quantiles of that order spreads the choices through the grid instead of
    selecting a contiguous interval in the TB's CB-ordered list.
    """
    if n == 0:
        return []
    ordered = sorted(eligible, key=_position_key)
    total = len(ordered)
    indices = [(2 * i + 1) * total // (2 * n) for i in range(n)]
    # For n <= total these midpoint-quantile indices are distinct.
    return [ordered[i] for i in indices]


def _select_random(
    eligible: Sequence[ResourcePosition], n: int, seed: int
) -> List[ResourcePosition]:
    if n == 0:
        return []
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(eligible), size=n, replace=False)
    return [eligible[int(i)] for i in sorted(indices)]


def _select_positions(
    pattern: str,
    eligible: Sequence[ResourcePosition],
    n: int,
    seed: Optional[int],
) -> List[ResourcePosition]:
    if pattern == "concentrated":
        return _select_concentrated(eligible, n)
    if pattern == "distributed":
        return _select_distributed(eligible, n)
    if pattern == "random":
        # Seed validation is performed by generate_preemption.
        assert seed is not None
        return _select_random(eligible, n, seed)
    raise ValueError(f"Unknown pattern {pattern!r}")


def generate_preemption(
    transport_block: TransportBlock,
    urllc_events: Sequence[URLLCEvent],
    pattern: str,
    preemption_fraction: Optional[float] = None,
    num_preempt: Optional[int] = None,
    seed: Optional[int] = None,
) -> PreemptionResult:

    """Select mapped eMBB REs to preempt.

    ``preemption_fraction`` and ``num_preempt`` refer to the number of REs
    mapped to this TB, not the entire candidate grid.

    When neither is supplied, the sum of all generated URLLC event demands
    determines the preemption count. Arrival times and deadlines are not used
    to schedule preemption in this abstraction.

    ``seed`` is required and non-negative for the random pattern.
    """
    if pattern not in PATTERNS:
        raise ValueError(
            f"Unknown pattern {pattern!r}; expected one of {list(PATTERNS)}"
        )
    if pattern == "random" and (
        isinstance(seed, bool) or not isinstance(seed, int) or seed < 0
    ):
        raise ValueError(
            f"'random' pattern needs a non-negative integer seed, got {seed!r}"
        )

    # Restrict selection to resources actually assigned to this TB. Sorting
    # by grid coordinates makes pattern geometry independent of CB list order.
    eligible = sorted(set(transport_block.used_positions()), key=_position_key)
    total = len(eligible)
    n = _resolve_count(total, urllc_events, preemption_fraction, num_preempt)
    selected = _select_positions(pattern, eligible, n, seed)

    # Return selected positions in deterministic grid order for all patterns.
    selected = sorted(selected, key=_position_key)
    return PreemptionResult(
        pattern=pattern,
        requested_count=n,
        total_embb_positions=total,
        preempted_positions=tuple(selected),
        seed=seed if pattern == "random" else None,
    )


def affected_cbs(
    transport_block: TransportBlock, result: PreemptionResult
) -> List[int]:
    """Sorted IDs of CBs hit by the preemption."""
    return transport_block.affected_cb_ids(result.preempted_positions)


if __name__ == "__main__":
    from src.cbg import affected_cbg_ids, group_code_blocks
    from src.embb import EmbbConfig

    tb = TransportBlock.from_config(
        EmbbConfig(
            num_symbols=14,
            num_subcarriers=48,
            reserved_pattern="first_symbol",
        )
    )
    cbgs = group_code_blocks(tb, max_cbgs=4)
    for pat in PATTERNS:
        result = generate_preemption(
            tb, [], pat, preemption_fraction=0.10, seed=42
        )
        cbs = affected_cbs(tb, result)
        print(
            f"{pat:>12}: {result.preempted_count}/{result.total_embb_positions} "
            f"eligible REs, CBs {cbs}, "
            f"CBGs {affected_cbg_ids(cbgs, cbs)}"
        )

"""eMBB Transport Block abstraction for the URLLC-preemption / CBG study.

A controlled 5G-NR-inspired model: no LDPC, modulation, OFDM, MIMO or
physical-layer decoding. One logical Transport Block (TB) is split into
logical Code Blocks (CBs), and each CB's coded positions are deterministically
mapped one-to-one onto logical resource positions (symbol, subcarrier).

IMPORTANT: the mapping is an abstract, deterministic linearisation rule chosen
for experimental control. It is NOT the 3GPP NR resource-element mapping (no
VRB/PRB mapping, DMRS/PTRS overhead, rate matching or interleaving is modelled).

This module knows nothing about URLLC, preemption, or CBGs. It only exposes
the mapping needed to answer: "which CBs use these resource positions?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Literal, Optional, Tuple

# Abstract, deterministic orders for filling the logical grid (not NR RE mapping):
#   "frequency_first": subcarrier index varies fastest, then symbol.
#   "time_first":      symbol index varies fastest, then subcarrier.
MappingOrder = Literal["frequency_first", "time_first"]


@dataclass(frozen=True, order=True)
class ResourcePosition:
    """One logical resource position on an abstract time-frequency grid."""

    symbol: int       # logical time index
    subcarrier: int   # logical frequency index


@dataclass(frozen=True)
class EmbbConfig:
    """Parameters of the eMBB transport block and its resource allocation."""

    num_code_blocks: int = 8
    coded_positions_per_cb: int = 36
    num_symbols: int = 14
    num_subcarriers: int = 24
    mapping_order: MappingOrder = "frequency_first"

    def __post_init__(self) -> None:
        for name in ("num_code_blocks", "coded_positions_per_cb",
                     "num_symbols", "num_subcarriers"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.mapping_order not in ("frequency_first", "time_first"):
            raise ValueError(f"Unknown mapping_order: {self.mapping_order!r}")
        if self.total_coded_positions > self.grid_size:
            raise ValueError(
                f"TB needs {self.total_coded_positions} positions but the "
                f"grid only has {self.grid_size}"
            )

    @property
    def total_coded_positions(self) -> int:
        return self.num_code_blocks * self.coded_positions_per_cb

    @property
    def grid_size(self) -> int:
        return self.num_symbols * self.num_subcarriers

    def index_to_position(self, linear_index: int) -> ResourcePosition:
        """Deterministically convert a linear index to a logical grid position.

        This is an abstract row-major / column-major style rule, not the NR
        resource-element mapping procedure.
        """
        if self.mapping_order == "frequency_first":
            symbol, subcarrier = divmod(linear_index, self.num_subcarriers)
        else:  # time_first
            subcarrier, symbol = divmod(linear_index, self.num_symbols)
        return ResourcePosition(symbol, subcarrier)


@dataclass(frozen=True)
class CodeBlock:
    """A logical Code Block and the resource positions carrying its coded data."""

    cb_id: int
    num_coded_positions: int
    positions: Tuple[ResourcePosition, ...]

    def __post_init__(self) -> None:
        if len(self.positions) != self.num_coded_positions:
            raise ValueError("positions must match num_coded_positions (1:1 mapping)")

    @property
    def position_set(self) -> frozenset:
        """Positions as a set, for fast overlap tests."""
        return frozenset(self.positions)

    def is_affected_by(self, resource_positions: Iterable[ResourcePosition]) -> bool:
        """True if any of the given resource positions carries this CB's data."""
        return not self.position_set.isdisjoint(resource_positions)

    def count_hit_positions(self, resource_positions: Iterable[ResourcePosition]) -> int:
        """Number of this CB's positions contained in the given set."""
        return len(self.position_set.intersection(resource_positions))


@dataclass
class TransportBlock:
    """One logical eMBB Transport Block made of ordered Code Blocks."""

    config: EmbbConfig
    code_blocks: Tuple[CodeBlock, ...]
    _position_to_cb: Dict[ResourcePosition, int] = field(
        init=False, repr=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        for cb in self.code_blocks:
            for pos in cb.positions:
                if pos in self._position_to_cb:
                    raise ValueError(f"Position {pos} mapped to more than one CB")
                self._position_to_cb[pos] = cb.cb_id

    # ---- construction -------------------------------------------------
    @classmethod
    def from_config(cls, config: EmbbConfig) -> "TransportBlock":
        """Build the TB: CB i gets linear indices [i*N, (i+1)*N)."""
        n = config.coded_positions_per_cb
        cbs = tuple(
            CodeBlock(
                cb_id=i,
                num_coded_positions=n,
                positions=tuple(
                    config.index_to_position(k) for k in range(i * n, (i + 1) * n)
                ),
            )
            for i in range(config.num_code_blocks)
        )
        return cls(config=config, code_blocks=cbs)

    # ---- queries ------------------------------------------------------
    @property
    def num_code_blocks(self) -> int:
        return len(self.code_blocks)

    def get_cb(self, cb_id: int) -> CodeBlock:
        return self.code_blocks[cb_id]

    def used_positions(self) -> List[ResourcePosition]:
        """All resource positions occupied by this TB, in CB order."""
        return [p for cb in self.code_blocks for p in cb.positions]

    def cb_id_at(self, position: ResourcePosition) -> Optional[int]:
        """CB ID mapped to a position, or None if the position is unused."""
        return self._position_to_cb.get(position)

    def affected_cb_ids(self, resource_positions: Iterable[ResourcePosition]) -> List[int]:
        """Sorted IDs of CBs having at least one position in the given set."""
        hit = {self._position_to_cb[p] for p in resource_positions
               if p in self._position_to_cb}
        return sorted(hit)


if __name__ == "__main__":
    cfg = EmbbConfig(num_code_blocks=8, coded_positions_per_cb=36,
                     num_symbols=14, num_subcarriers=24,
                     mapping_order="frequency_first")
    tb = TransportBlock.from_config(cfg)

    print(f"eMBB TB: {tb.num_code_blocks} CBs, "
          f"{cfg.total_coded_positions}/{cfg.grid_size} grid positions used, "
          f"abstract order={cfg.mapping_order}\n")

    for cb in tb.code_blocks:
        symbols = sorted({p.symbol for p in cb.positions})
        print(f"CB {cb.cb_id}: {cb.num_coded_positions} positions, "
              f"symbols {symbols[0]}-{symbols[-1]}, "
              f"first={cb.positions[0]}, last={cb.positions[-1]}")

    # Lookup demo only (no preemption logic): which CBs use these positions?
    probe = [ResourcePosition(1, 5), ResourcePosition(6, 0)]
    print(f"\nCBs mapped to {probe}: {tb.affected_cb_ids(probe)}")
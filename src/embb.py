"""eMBB transport-block and time-frequency resource abstraction.

This module models a configurable time-frequency allocation inspired by a
small 5G NR PDSCH allocation. It is NOT a complete NR resource mapper:
VRB/PRB mapping, standards-compliant DM-RS configuration, rate matching,
LDPC coding, scrambling, modulation coding, and PHY processing are not
implemented.

Units used here:
* ResourcePosition: one candidate resource element (RE) coordinate.
* Eligible RE: a candidate RE available to the abstract eMBB data allocation.
* CodeBlock.positions: eligible REs assigned to a logical CB for the study.

For compatibility with the original model, each logical CB position still maps
to one eligible RE. ``modulation_order`` records the assumed bits per
modulation symbol (2 for QPSK), but this module does not pretend that an RE is
one coded bit or implement the bit-to-symbol mapping. The logical CB-to-RE
assignment is an experimental allocation abstraction; it is not NR rate
matching or interleaving.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Literal, Optional, Tuple


MappingOrder = Literal["frequency_first", "time_first"]
MappingMode = Literal["contiguous", "interleaved"]
ReservedPattern = Literal["none", "first_symbol"]


@dataclass(frozen=True, order=True)
class ResourcePosition:
    """One candidate RE on the logical time-frequency grid."""

    symbol: int
    subcarrier: int


@dataclass(frozen=True)
class EmbbConfig:
    """Parameters for a logical eMBB allocation.

    Defaults retain the original 14 x 24 grid and 288 logical CB positions,
    so existing experiments and tests remain compatible. Set
    ``num_subcarriers=48`` for a four-PRB-wide candidate grid. Reserved REs are
    excluded from the available data pool before CB positions are assigned.

    ``reserved_pattern="first_symbol"`` reserves every subcarrier in symbol 0.
    This is a deliberately simple, explicit overhead pattern—not a standards-
    compliant DM-RS configuration.
    """

    num_code_blocks: int = 8
    coded_positions_per_cb: int = 36
    num_symbols: int = 14
    num_subcarriers: int = 24
    mapping_order: MappingOrder = "frequency_first"
    mapping_mode: MappingMode = "contiguous"
    modulation_order: int = 2
    reserved_pattern: ReservedPattern = "none"

    def __post_init__(self) -> None:
        for name in (
            "num_code_blocks",
            "coded_positions_per_cb",
            "num_symbols",
            "num_subcarriers",
            "modulation_order",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")

        if self.mapping_order not in ("frequency_first", "time_first"):
            raise ValueError(f"Unknown mapping_order: {self.mapping_order!r}")
        if self.mapping_mode not in ("contiguous", "interleaved"):
            raise ValueError(f"Unknown mapping_mode: {self.mapping_mode!r}")
        if self.reserved_pattern not in ("none", "first_symbol"):
            raise ValueError(f"Unknown reserved_pattern: {self.reserved_pattern!r}")

        if self.total_coded_positions > self.eligible_re_count:
            raise ValueError(
                f"TB needs {self.total_coded_positions} logical positions but "
                f"only {self.eligible_re_count} eligible REs are available "
                f"({self.grid_size} candidate REs, {self.reserved_re_count} reserved)"
            )

    @property
    def total_coded_positions(self) -> int:
        """Number of logical CB positions in the current abstraction."""
        return self.num_code_blocks * self.coded_positions_per_cb

    @property
    def grid_size(self) -> int:
        """Total candidate REs, including reserved resources."""
        return self.num_symbols * self.num_subcarriers

    @property
    def reserved_re_count(self) -> int:
        """Number of candidate REs excluded by the configured reserve pattern."""
        if self.reserved_pattern == "first_symbol":
            return self.num_subcarriers
        return 0

    @property
    def eligible_re_count(self) -> int:
        return self.grid_size - self.reserved_re_count

    def index_to_position(self, linear_index: int) -> ResourcePosition:
        """Convert a candidate-grid linear index to a coordinate.

        ``frequency_first`` varies subcarrier fastest; ``time_first`` varies
        symbol fastest. This is a logical ordering, not NR RE mapping.
        """
        if isinstance(linear_index, bool) or not isinstance(linear_index, int):
            raise ValueError("linear_index must be an integer")
        if not 0 <= linear_index < self.grid_size:
            raise IndexError(
                f"linear_index {linear_index} outside [0, {self.grid_size})"
            )
        if self.mapping_order == "frequency_first":
            symbol, subcarrier = divmod(linear_index, self.num_subcarriers)
        else:
            subcarrier, symbol = divmod(linear_index, self.num_symbols)
        return ResourcePosition(symbol, subcarrier)

    def position_to_index(self, position: ResourcePosition) -> int:
        """Convert a valid candidate-grid coordinate to a linear index."""
        if not isinstance(position, ResourcePosition):
            raise TypeError("position must be a ResourcePosition")
        if not (
            0 <= position.symbol < self.num_symbols
            and 0 <= position.subcarrier < self.num_subcarriers
        ):
            raise ValueError(f"Position outside grid: {position!r}")
        if self.mapping_order == "frequency_first":
            return position.symbol * self.num_subcarriers + position.subcarrier
        return position.subcarrier * self.num_symbols + position.symbol

    def is_reserved(self, position: ResourcePosition) -> bool:
        """Whether a candidate RE is excluded from the eMBB data pool."""
        # Validate coordinates even for the no-reservation configuration.
        self.position_to_index(position)
        if self.reserved_pattern == "first_symbol":
            return position.symbol == 0
        return False

    def eligible_positions(self) -> Tuple[ResourcePosition, ...]:
        """All data-eligible RE coordinates in configured linear order."""
        return tuple(
            self.index_to_position(i)
            for i in range(self.grid_size)
            if not self.is_reserved(self.index_to_position(i))
        )


@dataclass(frozen=True)
class CodeBlock:
    """A logical CB and the eligible REs assigned to it in this abstraction."""

    cb_id: int
    num_coded_positions: int
    positions: Tuple[ResourcePosition, ...]

    def __post_init__(self) -> None:
        if isinstance(self.cb_id, bool) or not isinstance(self.cb_id, int) or self.cb_id < 0:
            raise ValueError("cb_id must be a non-negative integer")
        if (
            isinstance(self.num_coded_positions, bool)
            or not isinstance(self.num_coded_positions, int)
            or self.num_coded_positions <= 0
        ):
            raise ValueError("num_coded_positions must be a positive integer")
        if len(self.positions) != self.num_coded_positions:
            raise ValueError(
                "positions must match num_coded_positions (one logical CB position per eligible RE)"
            )
        if len(set(self.positions)) != len(self.positions):
            raise ValueError("a code block cannot contain duplicate resource positions")

    @property
    def position_set(self) -> frozenset[ResourcePosition]:
        return frozenset(self.positions)

    def is_affected_by(self, resource_positions: Iterable[ResourcePosition]) -> bool:
        return not self.position_set.isdisjoint(resource_positions)

    def count_hit_positions(self, resource_positions: Iterable[ResourcePosition]) -> int:
        return len(self.position_set.intersection(resource_positions))


@dataclass
class TransportBlock:
    """One logical eMBB TB made of ordered CBs."""

    config: EmbbConfig
    code_blocks: Tuple[CodeBlock, ...]
    _position_to_cb: Dict[ResourcePosition, int] = field(
        init=False, repr=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        seen_cb_ids = set()
        for cb in self.code_blocks:
            if cb.cb_id in seen_cb_ids:
                raise ValueError(f"Duplicate CB ID {cb.cb_id}")
            seen_cb_ids.add(cb.cb_id)
            for pos in cb.positions:
                if self.config.is_reserved(pos):
                    raise ValueError(f"CB {cb.cb_id} uses reserved RE {pos}")
                if pos in self._position_to_cb:
                    raise ValueError(f"Position {pos} mapped to more than one CB")
                self._position_to_cb[pos] = cb.cb_id

    @classmethod
    def from_config(cls, config: EmbbConfig) -> "TransportBlock":
        """Build a TB from eligible REs using the selected abstract CB allocation.

        ``contiguous`` gives each CB a consecutive range in the eligible RE list.
        ``interleaved`` assigns positions round-robin across CBs. Both are
        controlled abstractions, not NR rate matching/interleaving.
        """
        available = config.eligible_positions()
        n = config.coded_positions_per_cb
        c = config.num_code_blocks

        def positions_for_cb(cb_id: int) -> Tuple[ResourcePosition, ...]:
            if config.mapping_mode == "contiguous":
                indices = range(cb_id * n, (cb_id + 1) * n)
            else:
                indices = (cb_id + j * c for j in range(n))
            return tuple(available[k] for k in indices)

        cbs = tuple(
            CodeBlock(
                cb_id=i,
                num_coded_positions=n,
                positions=positions_for_cb(i),
            )
            for i in range(c)
        )
        return cls(config=config, code_blocks=cbs)

    @property
    def num_code_blocks(self) -> int:
        return len(self.code_blocks)

    @property
    def total_positions(self) -> int:
        """Number of eligible REs mapped to this TB."""
        return sum(len(cb.positions) for cb in self.code_blocks)

    def get_cb(self, cb_id: int) -> CodeBlock:
        if isinstance(cb_id, bool) or not isinstance(cb_id, int):
            raise TypeError("cb_id must be an integer")
        if not 0 <= cb_id < len(self.code_blocks):
            raise IndexError(f"cb_id {cb_id} outside [0, {len(self.code_blocks)})")
        cb = self.code_blocks[cb_id]
        if cb.cb_id != cb_id:
            for candidate in self.code_blocks:
                if candidate.cb_id == cb_id:
                    return candidate
            raise IndexError(f"Unknown CB ID {cb_id}")
        return cb

    def used_positions(self) -> List[ResourcePosition]:
        """All REs occupied by this TB, in CB order (legacy-compatible API)."""
        return [p for cb in self.code_blocks for p in cb.positions]

    def cb_id_at(self, position: ResourcePosition) -> Optional[int]:
        return self._position_to_cb.get(position)

    def affected_cb_ids(self, resource_positions: Iterable[ResourcePosition]) -> List[int]:
        hit = {
            self._position_to_cb[p]
            for p in resource_positions
            if p in self._position_to_cb
        }
        return sorted(hit)


if __name__ == "__main__":
    cfg = EmbbConfig(
        num_code_blocks=8,
        coded_positions_per_cb=36,
        num_symbols=14,
        num_subcarriers=48,
        mapping_order="frequency_first",
        mapping_mode="contiguous",
        modulation_order=2,
        reserved_pattern="first_symbol",
    )
    tb = TransportBlock.from_config(cfg)
    print(
        f"eMBB TB: {tb.num_code_blocks} CBs, {tb.total_positions} mapped REs; "
        f"grid={cfg.num_symbols}x{cfg.num_subcarriers} ({cfg.grid_size} candidate REs), "
        f"{cfg.reserved_re_count} reserved, {cfg.eligible_re_count} eligible; "
        f"modulation order={cfg.modulation_order} bits/symbol (assumption)"
    )
    for cb in tb.code_blocks:
        symbols = sorted({p.symbol for p in cb.positions})
        print(
            f"CB {cb.cb_id}: {len(cb.positions)} mapped REs, "
            f"symbols {symbols[0]}-{symbols[-1]}, "
            f"first={cb.positions[0]}, last={cb.positions[-1]}"
        )

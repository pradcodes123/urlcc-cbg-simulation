"""Code Block Group (CBG) grouping for the URLLC-preemption / CBG study.

Implements the CB-to-CBG grouping of 3GPP TS 38.214, Clause 5.1.7.1
("UE procedure for grouping of code blocks to code block groups"):

    C  = number of CBs in the transport block
    N  = configured maximum number of CBGs
    M  = min(N, C)
    M1 = C mod M,  K1 = ceil(C / M),  K2 = floor(C / M)

    CBG m, m = 0..M1-1  : CB indices  m*K1 + k,                 k = 0..K1-1
    CBG m, m = M1..M-1  : CB indices  M1*K1 + (m-M1)*K2 + k,    k = 0..K2-1

(If M1 = 0 then K1 = K2 and the second rule alone gives equal-sized groups.)

No decoding, retransmission, URLLC or preemption logic lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from src.embb import CodeBlock, TransportBlock


@dataclass(frozen=True)
class CodeBlockGroup:
    """A Code Block Group: an ID and the (ordered) IDs of its member CBs."""

    cbg_id: int
    cb_ids: Tuple[int, ...]

    def contains(self, cb_id: int) -> bool:
        return cb_id in self.cb_ids

    def __len__(self) -> int:
        return len(self.cb_ids)


def group_code_blocks(transport_block: TransportBlock,
                      max_cbgs: int) -> Tuple[CodeBlockGroup, ...]:
    """Group the CBs of a transport block into CBGs (TS 38.214 §5.1.7.1).

    Args:
        transport_block: eMBB transport block from ``src.embb``.
        max_cbgs: N, the configured maximum number of CBGs per TB.

    Returns:
        Tuple of ``M = min(N, C)`` CodeBlockGroups, in CBG-ID order, with CB
        ordering preserved.

    Raises:
        ValueError: if ``max_cbgs`` is not a positive integer, the TB has no
            CBs, or the resulting grouping fails validation.
    """
    if isinstance(max_cbgs, bool) or not isinstance(max_cbgs, int) or max_cbgs <= 0:
        raise ValueError(f"max_cbgs must be a positive integer, got {max_cbgs!r}")

    cbs: Sequence[CodeBlock] = transport_block.code_blocks
    c = len(cbs)                       # C
    if c == 0:
        raise ValueError("transport block must contain at least one code block")

    m_total = min(max_cbgs, c)         # M = min(N, C)
    m1 = c % m_total                   # M1 = C mod M
    k1 = -(-c // m_total)              # K1 = ceil(C / M)
    k2 = c // m_total                  # K2 = floor(C / M)

    groups: List[CodeBlockGroup] = []
    for m in range(m_total):
        if m < m1:                     # first M1 groups get K1 CBs
            indices = [m * k1 + k for k in range(k1)]
        else:                          # remaining groups get K2 CBs
            indices = [m1 * k1 + (m - m1) * k2 + k for k in range(k2)]
        groups.append(CodeBlockGroup(
            cbg_id=m,
            cb_ids=tuple(cbs[i].cb_id for i in indices),
        ))

    result = tuple(groups)
    _validate_grouping(result, [cb.cb_id for cb in cbs], max_cbgs)
    return result


def _validate_grouping(cbgs: Sequence[CodeBlockGroup],
                       cb_ids: Sequence[int], max_cbgs: int) -> None:
    """Check the grouping invariants; raise ValueError on any violation."""
    if len(cbgs) != min(max_cbgs, len(cb_ids)):
        raise ValueError("number of CBGs must equal min(max_cbgs, number of CBs)")

    flat = [cb_id for g in cbgs for cb_id in g.cb_ids]
    if len(flat) != len(set(flat)):
        raise ValueError("a CB appears in more than one CBG")
    if sorted(flat) != sorted(cb_ids):
        raise ValueError("every CB must belong to exactly one CBG (IDs not preserved)")
    if flat != list(cb_ids):
        raise ValueError("CB ordering was not preserved by the grouping")
    if any(len(g) == 0 for g in cbgs):
        raise ValueError("empty CBG produced")


def build_cb_to_cbg_map(cbgs: Iterable[CodeBlockGroup]) -> Dict[int, int]:
    """Reverse index: CB ID -> CBG ID."""
    return {cb_id: g.cbg_id for g in cbgs for cb_id in g.cb_ids}


def get_cbg_for_cb(cbgs: Iterable[CodeBlockGroup], cb_id: int) -> int:
    """CBG ID containing the given CB ID (ValueError if the CB is unknown)."""
    mapping = build_cb_to_cbg_map(cbgs)
    if cb_id not in mapping:
        raise ValueError(f"CB {cb_id} does not belong to any CBG")
    return mapping[cb_id]


def affected_cbg_ids(cbgs: Iterable[CodeBlockGroup],
                     cb_ids: Iterable[int]) -> List[int]:
    """Sorted IDs of CBGs containing at least one of the given CB IDs.

    Intended use: ``affected_cbg_ids(cbgs, tb.affected_cb_ids(positions))``.
    """
    mapping = build_cb_to_cbg_map(cbgs)
    hit = set()
    for cb_id in cb_ids:
        if cb_id not in mapping:
            raise ValueError(f"CB {cb_id} does not belong to any CBG")
        hit.add(mapping[cb_id])
    return sorted(hit)


if __name__ == "__main__":
    from src.embb import EmbbConfig, ResourcePosition

    for c, n in ((8, 4), (10, 4)):
        cfg = EmbbConfig(num_code_blocks=c, coded_positions_per_cb=30)
        tb = TransportBlock.from_config(cfg)
        cbgs = group_code_blocks(tb, max_cbgs=n)
        print(f"C={c}, N={n} -> M={len(cbgs)} CBGs")
        for g in cbgs:
            print(f"  CBG{g.cbg_id} -> CBs {list(g.cb_ids)}")

    # Chain demo (lookup only): positions -> CB IDs -> CBG IDs
    cfg = EmbbConfig(num_code_blocks=8, coded_positions_per_cb=36)
    tb = TransportBlock.from_config(cfg)
    cbgs = group_code_blocks(tb, max_cbgs=4)
    probe = [ResourcePosition(2, 23), ResourcePosition(3, 0)]
    cb_hit = tb.affected_cb_ids(probe)
    print(f"\npositions {probe}\n  -> CBs {cb_hit}\n  -> CBGs {affected_cbg_ids(cbgs, cb_hit)}")

"""Abstract CBG-level retransmission accounting.

This module creates one retransmission request for each failed CBG and charges
the full mapped resource-position count of that CBG.

This is a full-CBG retransmission-cost abstraction, NOT a standards-compliant
NR HARQ implementation. It does not model retransmission timing, ACK/NACK,
resource allocation, rate matching, redundancy versions, soft combining, or a
second decoding pass. The resulting overhead is measured in mapped logical
resource positions, not actual NR resource elements or transmitted bits.
"""


from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from src.cbg import CodeBlockGroup
from src.decoder import CBGDecodingResult
from src.embb import TransportBlock


@dataclass(frozen=True)
class RetransmissionRequest:
    """Request to retransmit one CBG."""

    cbg_id: int
    num_positions: int  # Abstract mapped-position cost

    @property
    def resource_cost(self) -> int:
        """Full-CBG retransmission cost in mapped logical positions."""
        return self.num_positions


def get_failed_cbgs(decoding_results: Iterable[CBGDecodingResult]) -> tuple[int, ...]:
    """IDs of CBGs with ``success == False``, ordered by ``cbg_id``."""
    return tuple(sorted({r.cbg_id for r in decoding_results if not r.success}))


def create_retransmission_requests(
        decoding_results: Iterable[CBGDecodingResult],
        cbgs: Sequence[CodeBlockGroup],
        transport_block: TransportBlock,
) -> tuple[RetransmissionRequest, ...]:
    """One request per failed CBG, ordered by ``cbg_id``.

    Raises:
        ValueError: if a failed CBG ID has no matching CodeBlockGroup.
    """
    by_id = {g.cbg_id: g for g in cbgs}
    requests = []
    for cbg_id in get_failed_cbgs(decoding_results):
        if cbg_id not in by_id:
            raise ValueError(f"failed CBG {cbg_id} not found in the supplied CBGs")
        n = sum(len(transport_block.get_cb(cb_id).positions)
                for cb_id in by_id[cbg_id].cb_ids)
        requests.append(RetransmissionRequest(cbg_id=cbg_id, num_positions=n))
    return tuple(requests)


def retransmission_overhead(requests: Iterable[RetransmissionRequest],
                            total_embb_positions: int) -> float:
    """Total retransmitted positions / total eMBB positions."""
    if (isinstance(total_embb_positions, bool) or not isinstance(total_embb_positions, int)
            or total_embb_positions <= 0):
        raise ValueError(
            f"total_embb_positions must be a positive integer, got {total_embb_positions!r}")
    return sum(r.num_positions for r in requests) / total_embb_positions
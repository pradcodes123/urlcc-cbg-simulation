"""Standalone decoder operating-point sensitivity pilot.

This script does not modify official RQ1/RQ2/RQ3 experiments or results.
It uses the existing eMBB/CBG/preemption abstractions and the stochastic
SNR-aware decoder to identify a non-saturated operating regime.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.embb import EmbbConfig, TransportBlock
from src.cbg import group_code_blocks
from src.decoder import DecoderConfig, decode_cbgs
from src.preemption import generate_preemption

TOTAL = 288
PATTERNS = ("concentrated", "distributed", "random")
SNR_VALUES = (8.0, 10.0, 12.0)
FRACTIONS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
CBG_COUNTS = (2, 4, 8)
N_RUNS = 30


def run_trial(pattern: str, fraction: float, snr_db: float, cbg_count: int, seed: int):
    tb = TransportBlock.from_config(EmbbConfig())
    cbgs = group_code_blocks(tb, cbg_count)
    pre = generate_preemption(tb, [], pattern, preemption_fraction=fraction, seed=seed)
    decoded = decode_cbgs(tb, cbgs, pre.preempted_positions,
                          DecoderConfig(snr_db=snr_db), seed=seed)
    failed_ids = {r.cbg_id for r in decoded if not r.success}
    retx_positions = sum(
        sum(len(tb.get_cb(cb_id).positions) for cb_id in cbg.cb_ids)
        for cbg in cbgs if cbg.cbg_id in failed_ids
    )
    return len(failed_ids), retx_positions / TOTAL


def main() -> None:
    rows = []
    for snr in SNR_VALUES:
        for fraction in FRACTIONS:
            for pattern in PATTERNS:
                values = [run_trial(pattern, fraction, snr, 4, seed)
                          for seed in range(N_RUNS)]
                rows.append({
                    "snr_db": snr,
                    "preemption_fraction": fraction,
                    "pattern": pattern,
                    "cbg_count": 4,
                    "runs": N_RUNS,
                    "mean_failed_cbg": np.mean([v[0] for v in values]),
                    "failure_occurrence_rate": np.mean([v[0] > 0 for v in values]),
                    "mean_retransmission_overhead": np.mean([v[1] for v in values]),
                })

    # RQ3 sensitivity at the existing 10% preemption fraction.
    for snr in SNR_VALUES:
        for cbg_count in CBG_COUNTS:
            values = [run_trial("random", 0.10, snr, cbg_count, seed)
                      for seed in range(N_RUNS)]
            rows.append({
                "snr_db": snr,
                "preemption_fraction": 0.10,
                "pattern": "random",
                "cbg_count": cbg_count,
                "runs": N_RUNS,
                "mean_failed_cbg": np.mean([v[0] for v in values]),
                "failure_occurrence_rate": np.mean([v[0] > 0 for v in values]),
                "mean_retransmission_overhead": np.mean([v[1] for v in values]),
            })

    out = ROOT / "sensitivity_pilot.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

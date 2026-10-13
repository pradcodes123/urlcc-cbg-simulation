"""Resource-grid visualisations for the RQ2 preemption-pattern experiment.

All coordinates and outcomes are derived from the existing logical simulation
pipeline. These figures illustrate the project's abstraction; they are not a
complete NR resource mapper, PHY decoder, or standardized preemption procedure.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch, Rectangle
import numpy as np

from config.simulation import MEDIUM_URLLC_ARRIVAL_RATE, make_default_config
from src.cbg import affected_cbg_ids, group_code_blocks
from src.decoder import CBGDecodingResult, decode_cbgs
from src.embb import EmbbConfig, ResourcePosition, TransportBlock
from src.harq import simulate_harq
from src.metrics import SimulationMetrics, calculate_metrics
from src.preemption import PATTERNS, PreemptionResult, generate_preemption
from src.retransmission import RetransmissionRequest
from src.channel import generate_channel_samples
from src.simulation import SimulationConfig, run_simulation
from src.urllc import generate_urllc_traffic

DEFAULT_OUTPUT_DIR = Path("results/figures")
RQ2_PREEMPTION_FRACTION = 0.20
RQ2_CBG_COUNT = 4
RQ2_SEEDS = range(30)

# Okabe-Ito-inspired palette: blue for allocated eMBB, vermillion for punctures.
COLORS = {
    "unused": "#F2F2F2",
    "reserved": "#D8D8D8",
    "embb": "#56B4E9",
    "preempted": "#D55E00",
    "text": "#222222",
    "cb_boundary": "#FFFFFF",
    "cbg_boundary": "#111111",
}
CBG_COLORS = ("#0072B2", "#E69F00", "#009E73", "#CC79A7")
PATTERN_LABELS = {
    "concentrated": "Concentrated",
    "distributed": "Distributed",
    "random": "Random",
}


@dataclass(frozen=True)
class PatternTrace:
    pattern: str
    seed: int
    tb: TransportBlock
    cbgs: tuple
    preemption: PreemptionResult
    initial_results: tuple[CBGDecodingResult, ...]
    final_results: tuple[CBGDecodingResult, ...]
    retry_counts: dict[int, int]
    metrics: SimulationMetrics


def rq2_config(pattern: str, *, preemption_fraction: float = RQ2_PREEMPTION_FRACTION) -> SimulationConfig:
    """Build the exact RQ2 driver configuration from its own source defaults."""
    if pattern not in PATTERNS:
        raise ValueError(f"pattern must be one of {PATTERNS}, got {pattern!r}")
    return make_default_config(
        arrival_rate=MEDIUM_URLLC_ARRIVAL_RATE,
        cbg_count=RQ2_CBG_COUNT,
        preemption_pattern=pattern,
        preemption_fraction=preemption_fraction,
        num_preempt=None,
    )


def _trace_pattern(config: SimulationConfig, seed: int) -> PatternTrace:
    """Replay run_simulation's per-CBG pipeline without changing src/.

    The steps and RNG streams intentionally mirror src/simulation.py. This is
    used for explanatory plotting only; aggregate equality is tested against
    run_simulation to guard against drift.
    """
    tb = TransportBlock.from_config(config.embb_config)
    cbgs = group_code_blocks(tb, config.cbg_count)
    events = generate_urllc_traffic(
        config.urllc_config, seed, arrival_pattern=config.urllc_arrival_pattern
    )
    kwargs = {
        "preemption_fraction": config.preemption_fraction,
        "num_preempt": config.num_preempt,
    }
    if config.preemption_fraction is None and config.num_preempt is None:
        # Keep the same demand-driven fallback as run_simulation.
        from src.scheduler import SchedulerConfig, schedule_urllc_events
        scheduling = schedule_urllc_events(
            events,
            SchedulerConfig(
                slot_capacity=config.scheduler_slot_capacity,
                simulation_time=config.urllc_config.simulation_time,
            ),
        )
        demand = sum(r.scheduled_resources for r in scheduling if r.success)
        kwargs["num_preempt"] = min(demand, len(tb.used_positions()))

    preemption = generate_preemption(
        tb, events, config.preemption_pattern, **kwargs, seed=seed
    )
    cb_ids = tb.affected_cb_ids(preemption.preempted_positions)
    cbg_ids = affected_cbg_ids(cbgs, cb_ids)

    all_cbg_ids = sorted(g.cbg_id for g in cbgs)
    samples = generate_channel_samples(all_cbg_ids, config.channel_config, seed=seed + 1)
    snr_by_cbg = {sample.entity_id: sample.snr_db for sample in samples}
    initial = decode_cbgs(
        tb, cbgs, preemption.preempted_positions, config.decoder_config,
        seed=seed, snr_db_by_cbg=snr_by_cbg,
    )
    if config.decoder_config.model != "snr":
        raise ValueError("RQ2 HARQ replay requires decoder_config.model='snr'")

    retry_rng = np.random.default_rng([seed, 0x48415251])
    final: list[CBGDecodingResult] = []
    requests: list[RetransmissionRequest] = []
    retry_counts: dict[int, int] = {}
    total_retries = 0
    for result in initial:
        cbg = next(g for g in cbgs if g.cbg_id == result.cbg_id)
        cbg_positions = sum(len(tb.get_cb(cb_id).positions) for cb_id in cbg.cb_ids)
        outcomes = [result.success]
        p_fail = result.failure_probability or 0.0
        if result.damage_ratio <= 0.0:
            final.append(replace(result, success=True))
            retry_counts[result.cbg_id] = 0
            continue
        if not result.success:
            for _ in range(config.harq_config.max_attempts - 1):
                outcomes.append(bool(retry_rng.random() >= p_fail))
        harq_result = simulate_harq(
            entity_id=result.cbg_id,
            initial_slot=0,
            resource_cost=cbg_positions,
            attempt_outcomes=outcomes,
            config=config.harq_config,
        )
        final.append(replace(result, success=harq_result.delivered))
        retries = max(0, len(harq_result.attempts) - 1)
        retry_counts[result.cbg_id] = retries
        total_retries += retries
        if retries:
            requests.append(RetransmissionRequest(
                cbg_id=result.cbg_id, num_positions=cbg_positions * retries
            ))

    metrics = calculate_metrics(
        total_embb_positions=preemption.total_embb_positions,
        preempted_positions=preemption.preempted_count,
        affected_cb_ids=cb_ids,
        affected_cbg_ids=cbg_ids,
        initial_decoding_results=initial,
        final_decoding_results=tuple(final),
        retransmission_requests=requests,
        harq_retransmission_count=total_retries,
        simulation_time_slots=config.urllc_config.simulation_time,
    )
    return PatternTrace(
        config.preemption_pattern, seed, tb, tuple(cbgs), preemption,
        tuple(initial), tuple(final), retry_counts, metrics,
    )


def _cbg_lookup(cbgs: Iterable, cb_id: int) -> int:
    for group in cbgs:
        if cb_id in group.cb_ids:
            return group.cbg_id
    raise ValueError(f"CB {cb_id} is not assigned to a CBG")


def _grid_arrays(tb: TransportBlock, preempted: Iterable[ResourcePosition], cbgs: tuple):
    cfg = tb.config
    preempted_set = set(preempted)
    # 0 unused, 1 reserved, 2 allocated eMBB, 3 preempted eMBB.
    categories = np.zeros((cfg.num_symbols, cfg.num_subcarriers), dtype=np.int8)
    cb_ids = np.full(categories.shape, -1, dtype=int)
    cbg_ids = np.full(categories.shape, -1, dtype=int)
    cbg_by_cb = {cb_id: group.cbg_id for group in cbgs for cb_id in group.cb_ids}
    for symbol in range(cfg.num_symbols):
        for subcarrier in range(cfg.num_subcarriers):
            pos = ResourcePosition(symbol, subcarrier)
            if cfg.is_reserved(pos):
                categories[symbol, subcarrier] = 1
            cb_id = tb.cb_id_at(pos)
            if cb_id is not None:
                cb_ids[symbol, subcarrier] = cb_id
                cbg_ids[symbol, subcarrier] = cbg_by_cb[cb_id]
                categories[symbol, subcarrier] = 3 if pos in preempted_set else 2
    return categories, cb_ids, cbg_ids


def _draw_grid(ax, tb: TransportBlock, preemption: PreemptionResult, cbgs: tuple,
               *, show_cb_labels: bool = True, show_cbg_labels: bool = True):
    cfg = tb.config
    categories, cb_ids, cbg_ids = _grid_arrays(tb, preemption.preempted_positions, cbgs)
    cmap = ListedColormap([COLORS["unused"], COLORS["reserved"], COLORS["embb"], COLORS["preempted"]])
    ax.imshow(categories, origin="upper", interpolation="nearest", cmap=cmap,
              vmin=-0.5, vmax=3.5, aspect="auto")
    # Hatch non-eMBB candidate cells so reserved and unused resources remain
    # visually distinct even in grayscale/print.
    for s, f in np.argwhere(categories == 0):
        ax.add_patch(Rectangle((f - .5, s - .5), 1, 1, facecolor="none",
                               edgecolor="#C8C8C8", linewidth=0, hatch=".."))
    for s, f in np.argwhere(categories == 1):
        ax.add_patch(Rectangle((f - .5, s - .5), 1, 1, facecolor="none",
                               edgecolor="#777777", linewidth=.2, hatch="///"))

    # Boundary edges are drawn only when both neighbouring cells are mapped
    # and their CB/CBG IDs differ; this also handles irregular masks correctly.
    if cfg.mapping_mode == "contiguous":
        for s in range(cfg.num_symbols):
            for f in range(cfg.num_subcarriers - 1):
                left, right = cb_ids[s, f], cb_ids[s, f + 1]
                if left >= 0 and right >= 0 and left != right:
                    ax.plot([f + .5, f + .5], [s - .5, s + .5], color=COLORS["cb_boundary"], lw=.75, zorder=5)
                gl, gr = cbg_ids[s, f], cbg_ids[s, f + 1]
                if gl >= 0 and gr >= 0 and gl != gr:
                    ax.plot([f + .5, f + .5], [s - .5, s + .5], color=COLORS["cbg_boundary"], lw=2.0, zorder=6)
        for s in range(cfg.num_symbols - 1):
            for f in range(cfg.num_subcarriers):
                top, bottom = cb_ids[s, f], cb_ids[s + 1, f]
                if top >= 0 and bottom >= 0 and top != bottom:
                    ax.plot([f - .5, f + .5], [s + .5, s + .5], color=COLORS["cb_boundary"], lw=.75, zorder=5)
                gt, gb = cbg_ids[s, f], cbg_ids[s + 1, f]
                if gt >= 0 and gb >= 0 and gt != gb:
                    ax.plot([f - .5, f + .5], [s + .5, s + .5], color=COLORS["cbg_boundary"], lw=2.0, zorder=6)
        if show_cb_labels:
            for cb in tb.code_blocks:
                coords = [(p.subcarrier, p.symbol) for p in cb.positions]
                if coords:
                    x = float(np.mean([v[0] for v in coords])); y = float(np.mean([v[1] for v in coords]))
                    ax.text(x, y, f"CB{cb.cb_id}", ha="center", va="center", fontsize=6.5,
                            color="#17324D", weight="bold", zorder=7)
        if show_cbg_labels:
            for group in cbgs:
                coords = [(p.subcarrier, p.symbol) for cid in group.cb_ids for p in tb.get_cb(cid).positions]
                if coords:
                    x = float(np.mean([v[0] for v in coords])); y = float(np.mean([v[1] for v in coords]))
                    left_x = min(v[0] for v in coords) + 2.0
                    ax.text(left_x, y - 0.32, f"G{group.cbg_id}", ha="center", va="center", fontsize=7.5,
                            color="#FFFFFF", weight="bold", bbox={"boxstyle":"round,pad=0.12", "fc":"#222222", "ec":"none", "alpha":.88}, zorder=8)
    else:
        ax.text(.5, -.18, "Interleaved mapping: CB/CBG boundaries omitted",
                transform=ax.transAxes, ha="center", va="top", fontsize=8)

    ax.set_xlim(-.5, cfg.num_subcarriers - .5)
    ax.set_ylim(cfg.num_symbols - .5, -.5)
    ax.set_xticks(np.arange(0, cfg.num_subcarriers, max(1, cfg.num_subcarriers // 8)))
    ax.set_yticks(np.arange(0, cfg.num_symbols, 1))
    ax.set_xlabel("Logical subcarrier index")
    ax.set_ylabel("Logical OFDM-symbol index")
    ax.set_axisbelow(True)
    ax.set_xticks(np.arange(-.5, cfg.num_subcarriers, 1), minor=True)
    ax.set_yticks(np.arange(-.5, cfg.num_symbols, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=.3, alpha=.75)
    ax.tick_params(which="minor", bottom=False, left=False)
    return categories, cb_ids, cbg_ids


def _common_legend():
    return [
        Patch(facecolor=COLORS["embb"], edgecolor="none", label="eMBB allocated"),
        Patch(facecolor=COLORS["preempted"], edgecolor="none", label="Preempted by URLLC"),
        Patch(facecolor=COLORS["reserved"], edgecolor="#777", hatch="///", label="Reserved"),
        Patch(facecolor=COLORS["unused"], edgecolor="#C8C8C8", hatch="..", label="Unused candidate RE"),
        Patch(facecolor=COLORS["embb"], edgecolor=COLORS["cb_boundary"], label="CB boundary (thin)"),
        Patch(facecolor="white", edgecolor=COLORS["cbg_boundary"], linewidth=2, label="CBG boundary (thick)"),
    ]


def _ensure_same_preemption_count(traces: tuple[PatternTrace, ...]) -> None:
    counts = {trace.preemption.preempted_count for trace in traces}
    if len(counts) != 1:
        raise AssertionError(f"Patterns must use the same preemption count; got {sorted(counts)}")
    for trace in traces:
        if not set(trace.preemption.preempted_positions).issubset(set(trace.tb.used_positions())):
            raise AssertionError(f"{trace.pattern} preempted a position outside the TB allocation")
        if len(set(trace.preemption.preempted_positions)) != trace.preemption.preempted_count:
            raise AssertionError(f"{trace.pattern} produced duplicate preempted positions")


def plot_rq2_resource_grid_patterns(output_dir: Path = DEFAULT_OUTPUT_DIR, *, seed: int = 0,
                                   config_factory=rq2_config) -> Path:
    """Write the matched-count, three-panel RQ2 logical resource-grid figure."""
    traces = tuple(_trace_pattern(config_factory(pattern), seed) for pattern in PATTERNS)
    _ensure_same_preemption_count(traces)
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 6.8), sharex=True, sharey=True)
    for ax, trace in zip(axes, traces):
        _draw_grid(ax, trace.tb, trace.preemption, trace.cbgs)
        total = trace.preemption.total_embb_positions
        hits_cb = trace.tb.affected_cb_ids(trace.preemption.preempted_positions)
        hits_cbg = affected_cbg_ids(trace.cbgs, hits_cb)
        pct = 100 * trace.preemption.preempted_count / total if total else 0
        ax.set_title(
            f"{PATTERN_LABELS[trace.pattern]}\n"
            f"{trace.preemption.preempted_count}/{total} eMBB REs ({pct:.1f}%) · "
            f"{len(hits_cb)}/{len(trace.tb.code_blocks)} CBs · "
            f"{len(hits_cbg)}/{len(trace.cbgs)} CBGs hit",
            fontsize=10, pad=10,
        )
    fig.suptitle(
        f"RQ2 · Spatial preemption patterns on the logical eMBB allocation (seed {seed})",
        fontsize=14, weight="bold", y=.98,
    )
    fig.legend(handles=_common_legend(), loc="lower center", ncol=3, frameon=False,
               bbox_to_anchor=(.5, .045), fontsize=9)
    fig.text(.5, .005,
             "Logical resource-grid abstraction; patterns are experimental definitions, not 3GPP preemption procedures. "
             "Seed affects only the random pattern.", ha="center", va="bottom", fontsize=8.5)
    fig.subplots_adjust(top=.83, bottom=.19, wspace=.14)
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    png = output_dir / "rq2_resource_grid_patterns.png"
    pdf = output_dir / "rq2_resource_grid_patterns.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png


def _find_failure_example_seed() -> int:
    """Lowest RQ2 seed in 0..29 with at least one initial failure per pattern."""
    for seed in RQ2_SEEDS:
        traces = [_trace_pattern(rq2_config(pattern), seed) for pattern in PATTERNS]
        if all(any(not result.success for result in trace.initial_results) for trace in traces):
            return seed
    raise RuntimeError("No seed in 0..29 has an initial CBG failure in all three patterns")


def _draw_chain_grid(ax, trace: PatternTrace):
    cfg = trace.tb.config
    categories, cb_ids, cbg_ids = _grid_arrays(trace.tb, trace.preemption.preempted_positions, trace.cbgs)
    # Colour mapped resources by their actual CBG; punctured REs remain vermillion.
    image = np.zeros((cfg.num_symbols, cfg.num_subcarriers, 4), dtype=float)
    from matplotlib.colors import to_rgba
    for s in range(cfg.num_symbols):
        for f in range(cfg.num_subcarriers):
            cat = categories[s, f]
            if cat == 0: color = COLORS["unused"]
            elif cat == 1: color = COLORS["reserved"]
            elif cat == 3: color = COLORS["preempted"]
            else: color = CBG_COLORS[cbg_ids[s, f] % len(CBG_COLORS)]
            image[s, f] = to_rgba(color)
    ax.imshow(image, origin="upper", interpolation="nearest", aspect="auto")
    for s, f in np.argwhere(categories == 0):
        ax.add_patch(Rectangle((f-.5,s-.5),1,1,facecolor="none",edgecolor="#C8C8C8",linewidth=0,hatch=".."))
    for s, f in np.argwhere(categories == 1):
        ax.add_patch(Rectangle((f-.5,s-.5),1,1,facecolor="none",edgecolor="#777",linewidth=.2,hatch="///"))
    # Strong CBG boundaries, derived from actual CB-to-CBG membership.
    for s in range(cfg.num_symbols):
        for f in range(cfg.num_subcarriers-1):
            if cbg_ids[s,f] >= 0 and cbg_ids[s,f+1] >= 0 and cbg_ids[s,f] != cbg_ids[s,f+1]:
                ax.plot([f+.5,f+.5],[s-.5,s+.5],color="white",lw=1.8,zorder=5)
    for s in range(cfg.num_symbols-1):
        for f in range(cfg.num_subcarriers):
            if cbg_ids[s,f] >= 0 and cbg_ids[s+1,f] >= 0 and cbg_ids[s,f] != cbg_ids[s+1,f]:
                ax.plot([f-.5,f+.5],[s+.5,s+.5],color="white",lw=1.8,zorder=5)
    ax.set_title("Logical resource grid", fontsize=9)
    ax.set_xlabel("Subcarrier"); ax.set_ylabel("Symbol")
    ax.set_xticks(np.arange(0,cfg.num_subcarriers,max(1,cfg.num_subcarriers//6)))
    ax.set_yticks(np.arange(0,cfg.num_symbols,2))
    ax.set_xticks(np.arange(-.5,cfg.num_subcarriers,1),minor=True); ax.set_yticks(np.arange(-.5,cfg.num_symbols,1),minor=True)
    ax.grid(which="minor",color="white",linewidth=.25,alpha=.65); ax.tick_params(which="minor",bottom=False,left=False)


def plot_rq2_preemption_cbg_chain_example(output_dir: Path = DEFAULT_OUTPUT_DIR, *, seed: int | None = None) -> Path:
    """Write an illustrative resource-to-CBG-failure/retransmission chain figure."""
    seed = _find_failure_example_seed() if seed is None else seed
    traces = tuple(_trace_pattern(rq2_config(pattern), seed) for pattern in PATTERNS)
    _ensure_same_preemption_count(traces)
    if not all(any(not r.success for r in t.initial_results) for t in traces):
        raise ValueError("Selected seed must have at least one initial failure for every pattern")

    fig, axes = plt.subplots(3, 3, figsize=(15.5, 11.2), gridspec_kw={"height_ratios":[2.6, .9, 1.5]})
    for col, trace in enumerate(traces):
        _draw_chain_grid(axes[0,col], trace)
        axes[0,col].set_title(f"{PATTERN_LABELS[trace.pattern]} · {trace.preemption.preempted_count} REs", fontsize=10)
        # Middle row: actual preempted logical REs per code block.
        hit_positions = set(trace.preemption.preempted_positions)
        cb_ids = [cb.cb_id for cb in trace.tb.code_blocks]
        counts = [sum(p in hit_positions for p in trace.tb.get_cb(cid).positions) for cid in cb_ids]
        axes[1,col].bar(cb_ids, counts, color="#D55E00", edgecolor="white", linewidth=.5)
        axes[1,col].set_title("Preempted REs per CB", fontsize=9)
        axes[1,col].set_xlabel("CB ID"); axes[1,col].set_ylabel("Hit REs")
        axes[1,col].set_xticks(cb_ids); axes[1,col].grid(axis="y",alpha=.2); axes[1,col].set_axisbelow(True)

        # Bottom row: CBG damage, probability, initial/final outcome and retries.
        initial_by_id = {r.cbg_id:r for r in trace.initial_results}
        final_by_id = {r.cbg_id:r for r in trace.final_results}
        cbg_ids = [g.cbg_id for g in trace.cbgs]
        ratios = [initial_by_id[i].damage_ratio for i in cbg_ids]
        axes[2,col].bar(cbg_ids, ratios, color=[CBG_COLORS[i % len(CBG_COLORS)] for i in cbg_ids], alpha=.88)
        axes[2,col].set_ylim(0,1.28); axes[2,col].set_xticks(cbg_ids)
        axes[2,col].set_xlabel("CBG ID"); axes[2,col].set_ylabel("Damage ratio")
        axes[2,col].set_title("Damage → initial decode → HARQ", fontsize=9)
        axes[2,col].grid(axis="y",alpha=.2); axes[2,col].set_axisbelow(True)
        for x, cbg_id in enumerate(cbg_ids):
            result = initial_by_id[cbg_id]; final = final_by_id[cbg_id]
            p = result.failure_probability
            p_text = "n/a" if p is None else f"p={p:.2f}"
            initial_mark = "S" if result.success else "F"
            final_mark = "S" if final.success else "F"
            axes[2,col].text(
                x, 1.06,
                f"{p_text}\n{initial_mark}→{final_mark}\nr={trace.retry_counts.get(cbg_id,0)}",
                ha="center", va="bottom", fontsize=6.5,
            )
    fig.suptitle(
        f"RQ2 · Preemption-to-CBG outcome chain — illustrative example, seed {seed}\n"
        "Seed selected for failures in all three patterns; not representative of aggregate performance",
        fontsize=13, weight="bold", y=.995,
    )
    legend_handles = [Patch(facecolor=CBG_COLORS[i], label=f"CBG {i}") for i in range(RQ2_CBG_COUNT)]
    legend_handles.extend([
        Patch(facecolor=COLORS["preempted"], label="Preempted RE"),
        Patch(facecolor=COLORS["reserved"], edgecolor="#777", hatch="///", label="Reserved"),
        Patch(facecolor=COLORS["unused"], edgecolor="#C8C8C8", hatch="..", label="Unused"),
    ])
    fig.legend(handles=legend_handles, loc="lower center", ncol=6, frameon=False,
               bbox_to_anchor=(.5,.035), fontsize=8)
    fig.text(.5,.008,
             "S/F = initial/final success/failure; r = retries. Damage ratios/probabilities are model outputs; "
             "HARQ uses the independent-retry abstraction, not a complete NR PHY/HARQ simulation.",ha="center",fontsize=8)
    fig.subplots_adjust(top=.90,bottom=.13,hspace=.45,wspace=.28)
    output_dir=Path(output_dir); output_dir.mkdir(parents=True,exist_ok=True)
    png=output_dir/"rq2_preemption_cbg_chain_example.png"
    pdf=output_dir/"rq2_preemption_cbg_chain_example.pdf"
    fig.savefig(png,dpi=300,bbox_inches="tight"); fig.savefig(pdf,bbox_inches="tight")
    plt.close(fig)
    return png


def validate_replay(seeds: Iterable[int] = RQ2_SEEDS) -> int:
    """Raise AssertionError if analysis replay diverges from simulator metrics."""
    checks = 0
    for pattern in PATTERNS:
        config = rq2_config(pattern)
        for seed in seeds:
            replay = _trace_pattern(config, seed)
            actual = run_simulation(config, seed=seed)
            if replay.metrics != actual:
                raise AssertionError(
                    f"Replay mismatch for pattern={pattern}, seed={seed}:\n"
                    f"replay={replay.metrics}\nactual={actual}"
                )
            checks += 1
    return checks

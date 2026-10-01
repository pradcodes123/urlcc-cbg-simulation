"""Exploratory plots for the URLLC-CBG simulation experiments.

Uses Matplotlib defaults and produces descriptive figures only.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from analysis.analyze_results import (
    BASELINE_FILE,
    RQ1_FILE,
    RQ2_FILE,
    RQ3_FILE,
    load_results,
)

FIGURES_DIR = Path("results/figures")


def _save(
        fig: plt.Figure,
        filename: str,
        output_dir: Path = FIGURES_DIR,
) -> Path:
    """Save and close a figure."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    fig.tight_layout()
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def _categorical_scatter(
        df: pd.DataFrame,
        category: str,
        value: str,
        xlabel: str,
        ylabel: str,
        title: str,
        filename: str,
        output_dir: Path = FIGURES_DIR,
) -> Path:
    """Create a scatter plot for a categorical independent variable."""
    categories = list(dict.fromkeys(df[category].tolist()))
    positions = {
        item: i
        for i, item in enumerate(categories)
    }

    fig, ax = plt.subplots(figsize=(7, 5))

    x = [
        positions[item]
        for item in df[category]
    ]

    ax.scatter(
        x,
        df[value],
        alpha=0.75,
    )

    ax.set_xticks(
        range(len(categories)),
        [str(item) for item in categories],
    )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    return _save(
        fig,
        filename,
        output_dir,
    )


def _numeric_scatter(
        df: pd.DataFrame,
        x_column: str,
        y_column: str,
        xlabel: str,
        ylabel: str,
        title: str,
        filename: str,
        output_dir: Path = FIGURES_DIR,
) -> Path:
    """Create a scatter plot for two numeric variables."""
    fig, ax = plt.subplots(figsize=(7, 5))

    ax.scatter(
        df[x_column],
        df[y_column],
        alpha=0.75,
    )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    return _save(
        fig,
        filename,
        output_dir,
    )


def plot_baseline(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot baseline retransmission overhead across runs."""
    fig, ax = plt.subplots(figsize=(7, 5))

    ax.plot(
        df.index,
        df["retransmission_overhead"],
    )

    ax.set_xlabel("Run")
    ax.set_ylabel("Retransmission overhead")
    ax.set_title("Baseline retransmission overhead")

    return _save(
        fig,
        "baseline_retransmission_overhead.png",
        output_dir,
    )


def plot_rq1(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> list[Path]:
    """Create RQ1 exploratory plots."""
    return [
        _categorical_scatter(
            df,
            "traffic_level",
            "affected_cb_count",
            "URLLC traffic level",
            "Affected CB count",
            "RQ1: affected code blocks by URLLC traffic",
            "rq1_affected_cbs.png",
            output_dir,
        ),
        _categorical_scatter(
            df,
            "traffic_level",
            "affected_cbg_count",
            "URLLC traffic level",
            "Affected CBG count",
            "RQ1: affected CBGs by URLLC traffic",
            "rq1_affected_cbgs.png",
            output_dir,
        ),
        _categorical_scatter(
            df,
            "traffic_level",
            "retransmission_overhead",
            "URLLC traffic level",
            "Retransmission overhead",
            "RQ1: retransmission overhead by URLLC traffic",
            "rq1_retransmission_overhead.png",
            output_dir,
        ),
        _categorical_scatter(
            df,
            "traffic_level",
            "embb_delivery_efficiency",
            "URLLC traffic level",
            "eMBB delivery efficiency",
            "RQ1: eMBB delivery efficiency by URLLC traffic",
            "rq1_embb_delivery_efficiency.png",
            output_dir,
        ),
    ]


def plot_rq2(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> list[Path]:
    """Create RQ2 exploratory plots."""
    return [
        _categorical_scatter(
            df,
            "preemption_pattern",
            "affected_cb_count",
            "Preemption pattern",
            "Affected CB count",
            "RQ2: affected code blocks by preemption pattern",
            "rq2_affected_cbs.png",
            output_dir,
        ),
        _categorical_scatter(
            df,
            "preemption_pattern",
            "affected_cbg_count",
            "Preemption pattern",
            "Affected CBG count",
            "RQ2: affected CBGs by preemption pattern",
            "rq2_affected_cbgs.png",
            output_dir,
        ),
        _categorical_scatter(
            df,
            "preemption_pattern",
            "retransmission_overhead",
            "Preemption pattern",
            "Retransmission overhead",
            "RQ2: retransmission overhead by preemption pattern",
            "rq2_retransmission_overhead.png",
            output_dir,
        ),
        _categorical_scatter(
            df,
            "preemption_pattern",
            "embb_delivery_efficiency",
            "Preemption pattern",
            "eMBB delivery efficiency",
            "RQ2: eMBB delivery efficiency by preemption pattern",
            "rq2_embb_delivery_efficiency.png",
            output_dir,
        ),
    ]


def plot_rq3(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> list[Path]:
    """Create RQ3 exploratory plots."""
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    paths: list[Path] = []

    # CB exposure is expected to be identical across CBG configurations
    # for a given seed in the current paired design, but the observations
    # are plotted directly rather than encoding an expected result.
    for value, ylabel, filename, title in [
        (
            "affected_cb_count",
            "Affected CB count",
            "rq3_affected_cbs.png",
            "RQ3: affected code blocks by CBG configuration",
        ),
        (
            "affected_cbg_count",
            "Affected CBG count",
            "rq3_affected_cbgs.png",
            "RQ3: affected CBGs by CBG configuration",
        ),
        (
            "retransmission_overhead",
            "Retransmission overhead",
            "rq3_retransmission_overhead.png",
            "RQ3: retransmission overhead by CBG configuration",
        ),
        (
            "embb_delivery_efficiency",
            "eMBB delivery efficiency",
            "rq3_embb_delivery_efficiency.png",
            "RQ3: eMBB delivery efficiency by CBG configuration",
        ),
    ]:
        fig, ax = plt.subplots(figsize=(7, 5))

        for seed, group in df.groupby(
                "seed",
                sort=True,
        ):
            group = group.sort_values("cbg_count")

            ax.plot(
                group["cbg_count"],
                group[value],
                alpha=0.25,
            )

        ax.scatter(
            df["cbg_count"],
            df[value],
            alpha=0.75,
        )

        ax.set_xlabel("Number of CBGs")
        ax.set_ylabel(ylabel)
        ax.set_title(title)

        paths.append(
            _save(
                fig,
                filename,
                output_dir,
            )
        )

    return paths


def main() -> None:
    """Generate all exploratory figures from the raw CSV files."""
    paths: list[Path] = []

    paths.append(
        plot_baseline(
            load_results(BASELINE_FILE)
        )
    )

    paths.extend(
        plot_rq1(
            load_results(RQ1_FILE)
        )
    )

    paths.extend(
        plot_rq2(
            load_results(RQ2_FILE)
        )
    )

    paths.extend(
        plot_rq3(
            load_results(RQ3_FILE)
        )
    )

    print("Generated figures:")

    for path in paths:
        print(f"  {path}")


if __name__ == "__main__":
    main()
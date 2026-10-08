"""Meaningful descriptive plots for the URLLC-CBG simulation experiments.

The plots show individual simulation runs together with the mean and

standard deviation for each experimental condition.

No inferential statistics or hypothesis testing are performed here.

"""

from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from analysis.analyze_results import (
    BASELINE_FILE,
    RQ1_FILE,
    RQ2_FILE,
    RQ3_FILE,
    load_results,
)

FIGURES_DIR = Path("results/figures")

# Fixed jitter makes the figures reproducible.

JITTER_SEED = 42
def _save(
        fig: plt.Figure,
        filename: str,
        output_dir: Path = FIGURES_DIR,
) -> Path:

    """Save and close a figure."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    fig.tight_layout()
    fig.savefig(
        path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(fig)
    return path

def _add_mean_std(
        ax: plt.Axes,
        x: float,
        values: pd.Series,
) -> None:

    """Add mean ± standard deviation to an existing plot."""
    mean = values.mean()
    std = values.std(ddof=1)
    ax.errorbar(
        x,
        mean,
        yerr=std,
        fmt="D",
        markersize=7,
        capsize=5,
        linewidth=1.5,
        zorder=4,
    )

    ax.annotate(
        f"{mean:.3f}",
        (x, mean),
        xytext=(0, 9),
        textcoords="offset points",
        ha="center",
        fontsize=9,
    )

def _categorical_summary_plot(
        df: pd.DataFrame,
        category: str,
        value: str,
        xlabel: str,
        ylabel: str,
        title: str,
        filename: str,
        output_dir: Path = FIGURES_DIR,
        ylim: tuple[float, float] | None = None,

) -> Path:

    """Plot individual runs plus mean ± standard deviation.
    Small horizontal jitter prevents overlapping observations from hiding
    repeated values.
    """

    categories = list(dict.fromkeys(df[category].tolist()))
    positions = {
        item: i
        for i, item in enumerate(categories)

    }

    rng = np.random.default_rng(JITTER_SEED)
    fig, ax = plt.subplots(figsize=(7.5, 5.5))

    for category_value in categories:
        group = df[df[category] == category_value]
        x_center = positions[category_value]
        jitter = rng.uniform(
            -0.12,
            0.12,
            size=len(group),
        )

        ax.scatter(
            np.full(len(group), x_center) + jitter,
            group[value],
            alpha=0.55,
            s=35,
            zorder=2,
        )

        _add_mean_std(
            ax,
            x_center,
            group[value],
        )

    ax.set_xticks(
        range(len(categories)),
        [str(item) for item in categories],
    )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.grid(
        axis="y",
        alpha=0.25,
    )

    ax.set_axisbelow(True)
    return _save(
        fig,
        filename,
        output_dir,
    )

def _numeric_summary_plot(
        df: pd.DataFrame,
        x_column: str,
        y_column: str,
        xlabel: str,
        ylabel: str,
        title: str,
        filename: str,
        output_dir: Path = FIGURES_DIR,
        ylim: tuple[float, float] | None = None,

) -> Path:
    """Plot individual runs plus mean ± standard deviation by numeric x."""
    x_values = sorted(df[x_column].unique())
    rng = np.random.default_rng(JITTER_SEED)
    fig, ax = plt.subplots(figsize=(7.5, 5.5))

    for x_value in x_values:
        group = df[df[x_column] == x_value]
        jitter = rng.uniform(
            -0.10,
            0.10,
            size=len(group),
        )

        ax.scatter(
            np.full(len(group), x_value) + jitter,
            group[y_column],
            alpha=0.55,
            s=35,
            zorder=2,
        )

        _add_mean_std(
            ax,
            x_value,
            group[y_column],
        )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(x_values)

    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.grid(
        axis="y",
        alpha=0.25,
    )

    ax.set_axisbelow(True)
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
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    x = np.arange(1, len(df) + 1)
    ax.scatter(
        x,
        df["retransmission_overhead"],
        alpha=0.65,
        s=35,
    )
    mean = df["retransmission_overhead"].mean()
    ax.axhline(
        mean,
        linestyle="--",
        linewidth=1.5,
        label=f"Mean = {mean:.3f}",
    )

    ax.set_xlabel("Run")
    ax.set_ylabel("Retransmission overhead")
    ax.set_title("Baseline: retransmission overhead")
    ax.set_ylim(bottom=0)
    ax.legend()
    ax.grid(
        axis="y",
        alpha=0.25,
    )

    ax.set_axisbelow(True)
    return _save(
        fig,
        "baseline_retransmission_overhead.png",
        output_dir,
    )

def plot_rq1_preemption_fraction(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,

) -> Path:

    """Plot the realized eMBB preemption fraction for each URLLC traffic level."""
    return _categorical_summary_plot(
        df,
        "traffic_level",
        "preemption_fraction",
        "URLLC traffic level",
        "Preemption fraction",
        "RQ1: eMBB preemption fraction by URLLC traffic",
        "rq1_preemption_fraction.png",
        output_dir,
        ylim=(0, 0.30),
    )

def plot_rq1_preemption_vs_overhead(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> Path:

    """Plot the descriptive relationship between preemption and retransmission overhead.
    This is exploratory only: the RQ1 experiment varies traffic level rather than
    directly manipulating preemption fraction as a continuous independent variable.

    """

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    markers = ("o", "s", "^")
    categories = list(dict.fromkeys(df["traffic_level"].tolist()))

    for marker, category in zip(markers, categories):
        group = df[df["traffic_level"] == category]
        ax.scatter(
            group["preemption_fraction"],
            group["retransmission_overhead"],
            marker=marker,
            alpha=0.60,
            s=38,
            label=str(category),
        )

    ax.set_xlabel("Preemption fraction")
    ax.set_ylabel("Retransmission overhead")
    ax.set_title("RQ1: preemption fraction vs retransmission overhead")
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.legend(title="URLLC traffic level")
    ax.grid(axis="both", alpha=0.25)
    ax.set_axisbelow(True)

    return _save(
        fig,
        "rq1_preemption_vs_overhead.png",
        output_dir,
    )

def plot_rq1(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> list[Path]:

    """Create RQ1 descriptive plots."""
    return [
        _categorical_summary_plot(
            df,
            "traffic_level",
            "affected_cb_count",
            "URLLC traffic level",
            "Affected CB count",
            "RQ1: affected code blocks by URLLC traffic",
            "rq1_affected_cbs.png",
            output_dir,
        ),

        _categorical_summary_plot(
            df,
            "traffic_level",
            "affected_cbg_count",
            "URLLC traffic level",
            "Affected CBG count",
            "RQ1: affected CBGs by URLLC traffic",
            "rq1_affected_cbgs.png",
            output_dir,
        ),

        _categorical_summary_plot(
            df,
            "traffic_level",
            "failed_cbg_count",
            "URLLC traffic level",
            "Failed CBG count",
            "RQ1: failed CBGs by URLLC traffic",
            "rq1_failed_cbgs.png",
            output_dir,
        ),
        _categorical_summary_plot(
            df,
            "traffic_level",
            "retransmission_overhead",
            "URLLC traffic level",
            "Retransmission overhead",
            "RQ1: retransmission overhead by URLLC traffic",
            "rq1_retransmission_overhead.png",
            output_dir,
            ylim=(0, 1.05),
        ),
        _categorical_summary_plot(
            df,
            "traffic_level",
            "embb_delivery_efficiency",
            "URLLC traffic level",
            "eMBB delivery efficiency",
            "RQ1: eMBB delivery efficiency by URLLC traffic",
            "rq1_embb_delivery_efficiency.png",
            output_dir,
            ylim=(0, 1.05),
        ),
    ]
def plot_rq2(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,

) -> list[Path]:
    """Create RQ2 descriptive plots."""
    return [
        _categorical_summary_plot(
            df,
            "preemption_pattern",
            "affected_cb_count",
            "Preemption pattern",
            "Affected CB count",
            "RQ2: affected code blocks by preemption pattern",
            "rq2_affected_cbs.png",
            output_dir,
        ),

        _categorical_summary_plot(
            df,
            "preemption_pattern",
            "failed_cbg_count",
            "Preemption pattern",
            "Failed CBG count",
            "RQ2: failed CBGs by preemption pattern",
            "rq2_failed_cbgs.png",
            output_dir,
        ),

        _categorical_summary_plot(
            df,
            "preemption_pattern",
            "retransmission_overhead",
            "Preemption pattern",
            "Retransmission overhead",
            "RQ2: retransmission overhead by preemption pattern",
            "rq2_retransmission_overhead.png",
            output_dir,
            ylim=(0, 0.55),
        ),
        _categorical_summary_plot(
            df,
            "preemption_pattern",
            "embb_delivery_efficiency",
            "Preemption pattern",
            "eMBB delivery efficiency",
            "RQ2: eMBB delivery efficiency by preemption pattern",
            "rq2_embb_delivery_efficiency.png",
            output_dir,
            ylim=(0.6, 1.05),
        ),
    ]

def plot_rq3_failure_occurrence_rate(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,

) -> Path:
    """Plot the proportion of runs with at least one failed CBG for each CBG count."""
    cbg_counts = sorted(df["cbg_count"].unique())
    failure_rates = [
        (df.loc[df["cbg_count"] == count, "failed_cbg_count"] > 0).mean()
        for count in cbg_counts
    ]
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    bars = ax.bar(cbg_counts, failure_rates, alpha=0.75, width=0.9)
    for bar, rate in zip(bars, failure_rates):
        ax.annotate(
            f"{rate:.1%}",
            (bar.get_x() + bar.get_width() / 2, rate),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=9,
        )

    ax.set_xlabel("Number of CBGs")
    ax.set_ylabel("Runs with at least one failed CBG")
    ax.set_title("RQ3: failure occurrence rate by CBG configuration")
    ax.set_xticks(cbg_counts)
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    return _save(
        fig,
        "rq3_failure_occurrence_rate.png",
        output_dir,
    )

def plot_rq3(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> list[Path]:
    
    """Create RQ3 descriptive plots.
    RQ3 focuses on how CBG configuration affects CBG failures and the
    resulting retransmission consequences. Affected-CB and affected-CBG
    plots are intentionally omitted because they are invariant or largely
    determined by the fixed preemption realization in this experiment.
    """

    return [
        _numeric_summary_plot(
            df,
            "cbg_count",
            "failed_cbg_count",
            "Number of CBGs",
            "Failed CBG count",
            "RQ3: failed CBGs by CBG configuration",
            "rq3_failed_cbgs.png",
            output_dir,
            ylim=(-0.15, 4.25),
        ),
        _numeric_summary_plot(
            df,
            "cbg_count",
            "retransmission_overhead",
            "Number of CBGs",
            "Retransmission overhead",
            "RQ3: retransmission overhead by CBG configuration",
            "rq3_retransmission_overhead.png",
            output_dir,
            ylim=(0, 0.55),
        ),
        _numeric_summary_plot(
            df,
            "cbg_count",
            "embb_delivery_efficiency",
            "Number of CBGs",
            "eMBB delivery efficiency",
            "RQ3: eMBB delivery efficiency by CBG configuration",
            "rq3_embb_delivery_efficiency.png",
            output_dir,
            ylim=(0.6, 1.05),
        ),
    ]

def plot_rq2_failure_occurrence_rate(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot the proportion of runs with at least one failed CBG."""
    categories = list(dict.fromkeys(df["preemption_pattern"].tolist()))
    failure_rates = [
        (df.loc[df["preemption_pattern"] == category, "failed_cbg_count"] > 0).mean()
        for category in categories
    ]
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    bars = ax.bar(
        categories,
        failure_rates,
        alpha=0.75,
    )
    for bar, rate in zip(bars, failure_rates):
        ax.annotate(
            f"{rate:.1%}",
            (bar.get_x() + bar.get_width() / 2, rate),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=9,
        )
    ax.set_xlabel("Preemption pattern")
    ax.set_ylabel("Runs with at least one failed CBG")
    ax.set_title("RQ2: failure occurrence rate by preemption pattern")
    ax.set_ylim(0, 1.05)
    ax.grid(
        axis="y",
        alpha=0.25,
    )
    ax.set_axisbelow(True)
    return _save(
        fig,
        "rq2_failure_occurrence_rate.png",
       output_dir,
    )

def plot_rq2_overhead_ecdf(
        df: pd.DataFrame,
        output_dir: Path = FIGURES_DIR,
) -> Path:
    """Plot the empirical cumulative distribution of retransmission overhead."""
    categories = list(dict.fromkeys(df["preemption_pattern"].tolist()))
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    for category in categories:
        values = np.sort(
            df.loc[
                df["preemption_pattern"] == category,
                "retransmission_overhead",
            ].to_numpy()
        )
        cumulative = np.arange(1, len(values) + 1) / len(values)
        ax.step(
            values,
            cumulative,
            where="post",
            linewidth=2,
            label=category,
        )
    ax.set_xlabel("Retransmission overhead")
    ax.set_ylabel("Cumulative proportion of runs")
    ax.set_title("RQ2: empirical distribution of retransmission overhead")
    ax.set_xlim(left=0)
    ax.set_ylim(0, 1.05)
    ax.legend(title="Preemption pattern")
    ax.grid(
        axis="both",
        alpha=0.25,
    )
    ax.set_axisbelow(True)
    return _save(
        fig,
        "rq2_retransmission_overhead_ecdf.png",
        output_dir,
    )

def main() -> None:
    """Generate all descriptive figures from the raw CSV files."""
    paths: list[Path] = []
    paths.append(
        plot_baseline(
            load_results(BASELINE_FILE)
        )
    )
    rq1_df = load_results(RQ1_FILE)
    paths.extend(
        plot_rq1(
            rq1_df
        )
    )
    paths.append(
        plot_rq1_preemption_fraction(
            rq1_df
        )
    )
    paths.append(
        plot_rq1_preemption_vs_overhead(
            rq1_df
        )
    )
    paths.extend(
        plot_rq2(
            load_results(RQ2_FILE)
        )
    )
    rq3_df = load_results(RQ3_FILE)
    paths.extend(
        plot_rq3(
            rq3_df
        )
    )
    paths.append(
        plot_rq3_failure_occurrence_rate(
            rq3_df
        )
    )

    rq2_df = load_results(RQ2_FILE)

    paths.append(
        plot_rq2_failure_occurrence_rate(
            rq2_df
        )
    )

    paths.append(
        plot_rq2_overhead_ecdf(
            rq2_df
        )
    )

    print("Generated figures:")

    for path in paths:
        print(f"  {path}")

if __name__ == "__main__":
    main()

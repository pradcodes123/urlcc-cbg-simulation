"""Unified analysis for the URLLC-CBG simulation experiments.

Reads baseline, RQ1-RQ3, decoder-sensitivity, and scheduling-realism CSVs.

Writes all summaries, RQ2 statistical comparisons, scheduling-realism summaries,

figures, and one Markdown report under results/processed/.

This module never runs simulations or modifies raw experiment data.

"""

from __future__ import annotations

import warnings
import csv
import math
from statistics import mean, stdev
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

import numpy as np

import pandas as pd

from scipy.stats import wilcoxon

from experiments.realism_v2 import (
    RAW_COLUMNS as SCHEDULING_RAW_COLUMNS,
    RAW_OUTPUT_PATH as SCHEDULING_RAW_OUTPUT_PATH,
    TRAFFIC_LEVELS as SCHEDULING_TRAFFIC_LEVELS,
    POLICIES as SCHEDULING_POLICIES,
)

ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "results" / "raw"
RESULTS_DIR = RAW_DIR
PROCESSED_DIR = ROOT / "results" / "processed"

SENSITIVITY_FILE = (

    ROOT / "results" / "decoder_sensitivity" / "raw"

    / "rq2_decoder_sensitivity.csv"

)

SCHEDULING_SUMMARY_FILE = "scheduling_realism_summary.csv"

BASELINE_FILE = "baseline.csv"

RQ1_FILE = "rq1_traffic.csv"

RQ2_FILE = "rq2_patterns.csv"

RQ3_FILE = "rq3_cbg.csv"

PATTERNS = ("concentrated", "distributed", "random")

EXPECTED_SNR_DB = (6.0, 10.0, 14.0)

BOOTSTRAP_REPLICATES = 20_000

BOOTSTRAP_SEED = 20261012

METRIC_COLUMNS = (

    "preempted_positions",

    "preemption_fraction",

    "affected_cb_count",

    "affected_cbg_count",

    "failed_cbg_count",

    "retransmission_positions",

    "retransmission_overhead",

    "embb_delivery_efficiency",

)

# Optional metrics: older CSVs and unit-test fixtures may not contain these.
DELIVERY_METRIC_COLUMNS = (
    "delivered_embb_positions",
    "embb_delivery_rate_per_slot",
)

def require_file(path: Path) -> None:

    """Raise a useful error when an expected input file is absent."""

    if not path.is_file():

        raise FileNotFoundError(f"Required input file not found: {path}")

def load_raw(filename: str) -> pd.DataFrame:

    """Load a CSV from results/raw."""

    path = RAW_DIR / filename

    require_file(path)

    return pd.read_csv(path)


def load_results(filename: str) -> pd.DataFrame:
    """Load an experiment CSV from the results directory."""
    path = RESULTS_DIR / filename
    require_file(path)
    return pd.read_csv(path)


def validate_columns(df: pd.DataFrame, required: Iterable[str], label: str) -> None:

    missing = [column for column in required if column not in df.columns]

    if missing:

        raise ValueError(f"{label} is missing required columns: {missing}")

def normalise_columns(df: pd.DataFrame, label: str) -> pd.DataFrame:

    """Normalise known column-name aliases in a copy of a dataframe."""

    result = df.copy()

    result.columns = [str(column).strip().lower() for column in result.columns]

    aliases = {

        "pattern": "preemption_pattern",

        "puncturing_pattern": "preemption_pattern",

        "seed_id": "seed",

        "run_seed": "seed",

        "failed_cbg": "failed_cbg_count",

        "retransmission_overhead_fraction": "retransmission_overhead",

        "delivery_efficiency": "embb_delivery_efficiency",

    }

    for old, new in aliases.items():

        if old in result.columns and new not in result.columns:

            result = result.rename(columns={old: new})

    validate_columns(

        result,

        ["preemption_pattern", "retransmission_overhead"],

        label,

    )

    result["preemption_pattern"] = (

        result["preemption_pattern"].astype(str).str.strip().str.lower()

    )

    # RQ2 now includes an explicit no-preemption control row. It is valid raw
    # data, although it is intentionally excluded from pairwise pattern tests.
    allowed_conditions = set(PATTERNS) | {"no_preemption"}
    unknown = set(result["preemption_pattern"]) - allowed_conditions

    if unknown:

        raise ValueError(f"{label} contains unknown patterns: {sorted(unknown)}")

    result["retransmission_overhead"] = pd.to_numeric(

        result["retransmission_overhead"], errors="raise"

    )

    if not np.isfinite(result["retransmission_overhead"].to_numpy(dtype=float)).all():

        raise ValueError(f"{label} contains non-finite retransmission overhead values")

    if (result["retransmission_overhead"] < 0).any():

        raise ValueError(f"{label} contains negative retransmission overhead values")

    return result

def descriptive_summary(

    df: pd.DataFrame, group_column: str, label: str

) -> pd.DataFrame:

    """Summarise simulation metrics by the experiment's independent variable."""

    validate_columns(df, [group_column, *METRIC_COLUMNS], label)

    grouped = df.groupby(group_column, sort=False, dropna=False)

    summary = grouped.agg(

        n=(group_column, "size"),

        mean_preempted_positions=("preempted_positions", "mean"),

        std_preempted_positions=("preempted_positions", "std"),

        mean_preemption_fraction=("preemption_fraction", "mean"),

        mean_affected_cb_count=("affected_cb_count", "mean"),

        std_affected_cb_count=("affected_cb_count", "std"),

        mean_affected_cbg_count=("affected_cbg_count", "mean"),

        std_affected_cbg_count=("affected_cbg_count", "std"),

        mean_failed_cbg_count=("failed_cbg_count", "mean"),

        std_failed_cbg_count=("failed_cbg_count", "std"),

        mean_retransmission_positions=("retransmission_positions", "mean"),

        mean_retransmission_overhead=("retransmission_overhead", "mean"),

        std_retransmission_overhead=("retransmission_overhead", "std"),

        mean_embb_delivery_efficiency=("embb_delivery_efficiency", "mean"),

        std_embb_delivery_efficiency=("embb_delivery_efficiency", "std"),

    ).reset_index()

    # Add the new delivery metrics only when the input dataset contains them.
    for column in DELIVERY_METRIC_COLUMNS:
        if column in df.columns:
            summary[f"mean_{column}"] = grouped[column].mean().to_numpy()
            summary[f"std_{column}"] = grouped[column].std().fillna(0.0).to_numpy()

    failure_counts = grouped["failed_cbg_count"].apply(lambda values: int((values > 0).sum()))

    summary["runs_with_failure"] = summary[group_column].map(failure_counts)

    summary["failure_run_fraction"] = summary["runs_with_failure"] / summary["n"]

    return summary


def baseline_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise the no-preemption baseline as a single row."""
    required = [
        column for column in METRIC_COLUMNS
        if column != "preemption_fraction"
    ]
    validate_columns(df, required, "Baseline")

    data = df.copy()
    if "preemption_fraction" not in data.columns:
        data["preemption_fraction"] = 0.0

    row: dict[str, float | int] = {"n": len(data)}

    for column in METRIC_COLUMNS:
        row[f"mean_{column}"] = float(data[column].mean())

        if column in {
            "preempted_positions",
            "affected_cb_count",
            "affected_cbg_count",
            "failed_cbg_count",
            "retransmission_overhead",
            "embb_delivery_efficiency",
        }:
            row[f"std_{column}"] = (
                float(data[column].std()) if len(data) > 1 else 0.0
            )

    # Preserve backward compatibility with baseline CSVs lacking delivery metrics.
    for column in DELIVERY_METRIC_COLUMNS:
        if column in data.columns:
            row[f"mean_{column}"] = float(data[column].mean())
            row[f"std_{column}"] = (
                float(data[column].std()) if len(data) > 1 else 0.0
            )

    row["runs_with_failure"] = int(
        (data["failed_cbg_count"] > 0).sum()
    )
    return pd.DataFrame([row])



def analyze_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """Compatibility wrapper for baseline analysis."""
    return baseline_summary(df)


def analyze_rq1(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise RQ1 by traffic level."""
    return descriptive_summary(df, "traffic_level", "RQ1")


def analyze_rq2(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise RQ2 by preemption pattern."""
    return descriptive_summary(df, "preemption_pattern", "RQ2")


def analyze_rq3(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise RQ3 by CBG count."""
    return descriptive_summary(df, "cbg_count", "RQ3")


def _write_summary(
    summary: pd.DataFrame,
    filename: str,
) -> Path:
    """Write a summary CSV into the processed-results directory."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / filename
    summary.to_csv(path, index=False)
    return path


def validate_pairing(df: pd.DataFrame, group_columns: list[str]) -> None:

    """Require a unique observation per seed and experimental condition."""

    validate_columns(df, [*group_columns, "seed"], "Paired analysis data")

    duplicated = df.duplicated(group_columns + ["seed"], keep=False)

    if duplicated.any():

        examples = df.loc[duplicated, group_columns + ["seed"]].head()

        raise ValueError(

            "Expected one observation per seed and condition; duplicate examples:\n"

            f"{examples.to_string(index=False)}"

        )

def bootstrap_mean_ci(

    values: np.ndarray,

    rng: np.random.Generator,

    replicates: int = BOOTSTRAP_REPLICATES,

) -> tuple[float, float]:

    values = np.asarray(values, dtype=float)

    if values.size == 0:

        return np.nan, np.nan

    sampled = rng.choice(values, size=(replicates, values.size), replace=True)

    low, high = np.quantile(sampled.mean(axis=1), [0.025, 0.975])

    return float(low), float(high)

def paired_bootstrap_ci(

    differences: np.ndarray,

    rng: np.random.Generator,

    replicates: int = BOOTSTRAP_REPLICATES,

) -> tuple[float, float]:

    return bootstrap_mean_ci(differences, rng, replicates)

def holm_adjust(p_values: list[float]) -> list[float]:

    """Holm step-down adjusted p-values, returned in original order."""

    p = np.asarray(p_values, dtype=float)

    if p.size == 0:

        return []

    order = np.argsort(p)

    adjusted_sorted = np.empty(p.size, dtype=float)

    running_max = 0.0

    for rank, index in enumerate(order):

        running_max = max(running_max, (p.size - rank) * p[index])

        adjusted_sorted[rank] = min(1.0, running_max)

    adjusted = np.empty(p.size, dtype=float)

    for rank, index in enumerate(order):

        adjusted[index] = adjusted_sorted[rank]

    return adjusted.tolist()

def paired_wilcoxon_p(differences: np.ndarray) -> float:

    differences = np.asarray(differences, dtype=float)

    differences = differences[np.isfinite(differences)]

    if differences.size == 0:

        return np.nan

    if np.allclose(differences, 0.0):

        return 1.0

    with warnings.catch_warnings():

        warnings.simplefilter("ignore")

        result = wilcoxon(

            differences, alternative="two-sided", zero_method="wilcox", method="auto"

        )

    return float(result.pvalue)

def make_bootstrap_summary(

    df: pd.DataFrame,

    group_columns: list[str],

    rng: np.random.Generator,

) -> pd.DataFrame:

    """Detailed overhead summaries and bootstrap CIs for one or more groupings."""

    rows: list[dict[str, object]] = []

    for keys, group in df.groupby(group_columns, sort=True):

        if not isinstance(keys, tuple):

            keys = (keys,)

        values = group["retransmission_overhead"].to_numpy(dtype=float)

        ci_low, ci_high = bootstrap_mean_ci(values, rng)

        row: dict[str, object] = dict(zip(group_columns, keys))

        row.update({

            "n": int(values.size),

            "mean_overhead": float(values.mean()),

            "std_overhead": float(values.std(ddof=1)) if values.size > 1 else 0.0,

            "median_overhead": float(np.median(values)),

            "min_overhead": float(values.min()),

            "max_overhead": float(values.max()),

            "mean_ci95_low": ci_low,

            "mean_ci95_high": ci_high,

        })

        if "failed_cbg_count" in group.columns:

            failed = pd.to_numeric(group["failed_cbg_count"], errors="raise")

            row["mean_failed_cbg_count"] = float(failed.mean())

            row["runs_with_failure"] = int((failed > 0).sum())

        if "embb_delivery_efficiency" in group.columns:

            row["mean_delivery_efficiency"] = float(

                pd.to_numeric(group["embb_delivery_efficiency"], errors="raise").mean()

            )

        if "delivered_embb_positions" in group.columns:

            row["mean_delivered_embb_positions"] = float(

                pd.to_numeric(group["delivered_embb_positions"], errors="raise").mean()

            )

        if "embb_delivery_rate_per_slot" in group.columns:

            row["mean_embb_delivery_rate_per_slot"] = float(

                pd.to_numeric(group["embb_delivery_rate_per_slot"], errors="raise").mean()

            )

        rows.append(row)

    return pd.DataFrame(rows)

def paired_pattern_comparisons(

        df: pd.DataFrame,

        group_columns: list[str],

        rng: np.random.Generator,

    ) -> pd.DataFrame:

        """Compare each pair of patterns using matched run seeds."""

        comparisons = (

            ("concentrated", "distributed"),

            ("concentrated", "random"),

            ("distributed", "random"),

        )

        rows: list[dict[str, object]] = []

        # Compare patterns separately within each experimental condition.

        for group_key, subset in df.groupby(group_columns, sort=True):

            if not isinstance(group_key, tuple):

                group_key = (group_key,)

            wide = subset.pivot(

                index="seed",

                columns="preemption_pattern",

                values="retransmission_overhead",

            )

            for pattern_a, pattern_b in comparisons:

                if pattern_a not in wide.columns or pattern_b not in wide.columns:

                    raise ValueError(

                        f"Missing pattern in comparison: {pattern_a} vs {pattern_b}"

                    )

                paired = wide[[pattern_a, pattern_b]].dropna()

                if len(paired) < 2:

                    raise ValueError(

                        f"Insufficient paired seeds for {pattern_a} vs "

                        f"{pattern_b}: {len(paired)}"

                    )

                differences = (

                    paired[pattern_a].to_numpy(dtype=float)

                    - paired[pattern_b].to_numpy(dtype=float)

                )

                ci_low, ci_high = paired_bootstrap_ci(differences, rng)

                row: dict[str, object] = dict(zip(group_columns, group_key))

                row.update({

                    "pattern_a": pattern_a,

                    "pattern_b": pattern_b,

                    "contrast": f"{pattern_a} - {pattern_b}",

                    "n_pairs": int(len(differences)),

                    "mean_difference": float(differences.mean()),

                    "ci95_low": ci_low,

                    "ci95_high": ci_high,

                    "p_value": paired_wilcoxon_p(differences),

                })

                rows.append(row)

        result = pd.DataFrame(rows)

        if result.empty:

            raise ValueError("No paired pattern comparisons were generated.")

        # Holm correction: three pairwise tests within each SNR condition.

        grouping = (

            group_columns[0]

            if len(group_columns) == 1

            else group_columns

        )

        result["p_holm"] = np.nan

        for _, indices in result.groupby(grouping, sort=True).groups.items():

            result.loc[indices, "p_holm"] = holm_adjust(

                result.loc[indices, "p_value"].tolist()

            )

        result["significant_holm_0_05"] = result["p_holm"] < 0.05

        return result

def interaction_bootstrap(

    df: pd.DataFrame, rng: np.random.Generator

) -> pd.DataFrame:

    """Bootstrap change in paired pattern differences over adjacent SNR levels."""

    snr_levels = sorted(df["snr_db"].unique())

    if len(snr_levels) < 2:

        raise ValueError("At least two SNR levels are required for interaction analysis")

    wide = df.pivot(

        index="seed", columns=["snr_db", "preemption_pattern"],

        values="retransmission_overhead",

    )

    rows: list[dict[str, object]] = []

    for other in ("distributed", "random"):

        for snr_low, snr_high in zip(snr_levels[:-1], snr_levels[1:]):

            required = [

                (snr_low, "concentrated"), (snr_low, other),

                (snr_high, "concentrated"), (snr_high, other),

            ]

            missing = [column for column in required if column not in wide.columns]

            if missing:

                raise ValueError(f"Missing interaction data for {other}: {missing}")

            paired = wide[required].dropna()

            if len(paired) < 2:

                raise ValueError(f"Insufficient matched seeds for interaction: {len(paired)}")

            diff_low = (

                paired[(snr_low, "concentrated")].to_numpy(dtype=float)

                - paired[(snr_low, other)].to_numpy(dtype=float)

            )

            diff_high = (

                paired[(snr_high, "concentrated")].to_numpy(dtype=float)

                - paired[(snr_high, other)].to_numpy(dtype=float)

            )

            interaction = diff_high - diff_low

            ci_low, ci_high = paired_bootstrap_ci(interaction, rng)

            rows.append({

                "contrast": f"concentrated - {other}",

                "snr_low_db": float(snr_low),

                "snr_high_db": float(snr_high),

                "n_paired_seeds": int(len(interaction)),

                "difference_at_low_snr": float(diff_low.mean()),

                "difference_at_high_snr": float(diff_high.mean()),

                "interaction_change": float(interaction.mean()),

                "bootstrap_ci95_low": ci_low,

                "bootstrap_ci95_high": ci_high,

                "ci_excludes_zero": bool(ci_low > 0 or ci_high < 0),

            })

    return pd.DataFrame(rows)

def plot_sensitivity(summary: pd.DataFrame) -> Path:

    path = PROCESSED_DIR / "rq2_snr_sensitivity.png"

    fig, ax = plt.subplots(figsize=(8.5, 5.5))

    for pattern in PATTERNS:

        group = summary[summary["preemption_pattern"] == pattern].sort_values("snr_db")

        if group.empty:

            continue

        x = group["snr_db"].to_numpy(dtype=float)

        mean = group["mean_overhead"].to_numpy(dtype=float) * 100

        low = group["mean_ci95_low"].to_numpy(dtype=float) * 100

        high = group["mean_ci95_high"].to_numpy(dtype=float) * 100

        ax.plot(x, mean, marker="o", label=pattern.capitalize())

        ax.fill_between(x, low, high, alpha=0.15)

    ax.set(title="Decoder-SNR sensitivity", xlabel="Decoder SNR (dB)",

              ylabel="Mean retransmission overhead (%)")

    ax.set_xticks(sorted(summary["snr_db"].unique()))

    ax.grid(True, alpha=0.3)

    ax.legend()

    fig.tight_layout()

    fig.savefig(path, dpi=200)

    plt.close(fig)

    return path

def plot_pattern_differences(comparisons: pd.DataFrame) -> Path:

    path = PROCESSED_DIR / "rq2_paired_pattern_differences.png"

    selected = comparisons[comparisons["contrast"].isin([

        "concentrated - distributed", "concentrated - random"

    ])].copy()

    fig, ax = plt.subplots(figsize=(9, 5.5))

    offsets = {"concentrated - distributed": -0.12, "concentrated - random": 0.12}

    for contrast, group in selected.groupby("contrast"):

        group = group.sort_values("snr_db")

        x = group["snr_db"].to_numpy(dtype=float) + offsets[contrast]

        y = group["mean_difference"].to_numpy(dtype=float) * 100

        low = group["ci95_low"].to_numpy(dtype=float) * 100

        high = group["ci95_high"].to_numpy(dtype=float) * 100

        ax.errorbar(x, y, yerr=np.vstack([y - low, high - y]), marker="o",

                    capsize=4, label=contrast)

    ax.axhline(0, linewidth=1)

    ax.set(title="Paired pattern differences by decoder SNR", xlabel="Decoder SNR (dB)",

              ylabel="Mean paired overhead difference (percentage points)")

    ax.set_xticks(sorted(selected["snr_db"].unique()))

    ax.grid(True, alpha=0.3)

    ax.legend()

    fig.tight_layout()

    fig.savefig(path, dpi=200)

    plt.close(fig)

    return path

def dataframe_to_markdown(df: pd.DataFrame) -> str:

    """Render a DataFrame as a Markdown table without an extra dependency."""

    def fmt(value: object) -> str:

        if pd.isna(value):

            return ""

        if isinstance(value, (float, np.floating)):

            return f"{value:.4f}"

        return str(value).replace("|", r"\\|").replace("\n", " ")

    headers = [str(column) for column in df.columns]

    rows = [[fmt(value) for value in row] for row in df.itertuples(index=False, name=None)]

    lines = ["| " + " | ".join(headers) + " |",

                "| " + " | ".join("---" for _ in headers) + " |"]

    lines.extend("| " + " | ".join(row) + " |" for row in rows)

    return "\n".join(lines)

SCHEDULING_METRICS = (
    "event_success_rate", "deadline_miss_rate", "capacity_rejection_rate",
    "immediate_rejection_rate", "unresolved_rate", "resource_utilization",
)
SCHEDULING_INTEGER_COLUMNS = (
    "run", "seed", "simulation_slots", "service_horizon_slots", "slot_capacity",
    "event_count", "successful_events", "deadline_misses", "capacity_rejections",
    "immediate_rejections", "unresolved_events", "scheduled_resource_units",
    "capacity_resource_units",
)
SCHEDULING_FLOAT_COLUMNS = ("arrival_rate", *SCHEDULING_METRICS)


def scheduling_realism_summary(rows: Sequence[Mapping]) -> pd.DataFrame:
    """Aggregate scheduling-realism metrics by traffic level, policy, and metric."""
    expected = set(SCHEDULING_RAW_COLUMNS)
    for index, row in enumerate(rows):
        missing = expected - set(row)
        if missing:
            raise ValueError(f"Scheduling raw row {index} is missing columns: {sorted(missing)}")

    summaries: list[dict[str, object]] = []
    for level in SCHEDULING_TRAFFIC_LEVELS:
        for policy in SCHEDULING_POLICIES:
            group = [row for row in rows if row["traffic_level"] == level and row["policy"] == policy]
            for metric in SCHEDULING_METRICS:
                values = [float(row[metric]) for row in group]
                n = len(values)
                avg = mean(values) if n else math.nan
                sd = stdev(values) if n > 1 else (0.0 if n == 1 else math.nan)
                half_width = 1.96 * sd / math.sqrt(n) if n > 1 else (0.0 if n == 1 else math.nan)
                summaries.append({
                    "traffic_level": level, "policy": policy, "metric": metric,
                    "n": n, "mean": avg, "std_dev": sd,
                    "ci95_low": avg - half_width, "ci95_high": avg + half_width,
                })
    return pd.DataFrame(summaries)


def load_scheduling_realism() -> pd.DataFrame:
    """Load the existing scheduling-realism raw CSV and save its summary."""
    raw_path = Path(SCHEDULING_RAW_OUTPUT_PATH)
    if not raw_path.is_absolute():
        raw_path = ROOT / raw_path
    require_file(raw_path)
    with raw_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"Scheduling realism raw file contains no rows: {raw_path}")

    for row_index, row in enumerate(rows):
        missing = set(SCHEDULING_RAW_COLUMNS) - set(row)
        if missing:
            raise ValueError(f"Scheduling raw row {row_index} is missing columns: {sorted(missing)}")
        for field in SCHEDULING_INTEGER_COLUMNS:
            row[field] = int(row[field])
        for field in SCHEDULING_FLOAT_COLUMNS:
            row[field] = float(row[field])

    summary = scheduling_realism_summary(rows)
    summary.to_csv(PROCESSED_DIR / SCHEDULING_SUMMARY_FILE, index=False)
    print(f"Scheduling realism raw input: {raw_path}")
    return summary


def write_report(

    baseline: pd.DataFrame,

    rq1: pd.DataFrame,

    rq2: pd.DataFrame,

    rq3: pd.DataFrame,

    sensitivity_summary: pd.DataFrame,

    comparisons: pd.DataFrame,

    interactions: pd.DataFrame,

    scheduling_summary: pd.DataFrame,

) -> Path:

    path = PROCESSED_DIR / "analysis_report.md"

    sections = [

        "# URLLC-CBG Simulation Analysis", "",

        "## Scope and interpretation", "",

        "This report summarises the existing simulation outputs. It does not run or modify experiments. "

        "The decoder-SNR results describe this stochastic surrogate model and are not calibrated 5G NR BLER or physical-layer results.", "",

        "## Baseline", "", dataframe_to_markdown(baseline), "",

        "## RQ1 — URLLC traffic level", "", dataframe_to_markdown(rq1), "",

        "## RQ2 — Preemption pattern (descriptive results)", "", dataframe_to_markdown(rq2), "",

        "## RQ3 — Number of CBGs", "", dataframe_to_markdown(rq3), "",

        "## Scheduling realism experiment", "",

        "This section summarizes the separate scheduling experiment by traffic level, policy, and metric. Confidence intervals use a normal approximation (mean ± 1.96 × sample SD / √n); they are descriptive, not hypothesis tests.", "",

        dataframe_to_markdown(scheduling_summary), "",

        "## Decoder-SNR sensitivity", "", dataframe_to_markdown(sensitivity_summary), "",

        "## Paired pattern comparisons", "",

        "Differences are pattern A minus pattern B. Positive values indicate greater overhead for pattern A. "

        "Wilcoxon tests are paired by seed; Holm correction is applied to the three pairwise comparisons within each SNR condition. "

        "Confidence intervals use a 20,000-replicate percentile bootstrap.", "",

        dataframe_to_markdown(comparisons), "",

        "## Pattern-by-SNR interaction", "",

        "The interaction is the change in the concentrated-versus-comparison pattern difference across adjacent SNR levels. "

        "An interval containing zero does not establish equivalence; it means this analysis did not resolve a non-zero interaction.", "",

        dataframe_to_markdown(interactions), "",

        "## Limitations", "",

        "The SNR sweep contains only the configured operating points. The decoder is not calibrated against measured or standard-derived NR BLER curves. "

        "Bootstrap intervals quantify simulation run-to-run uncertainty, not model misspecification. Retransmission overhead is a model metric, not a complete throughput or latency measurement. ",

        "The eMBB delivery-rate metric is successfully delivered logical eMBB positions per configured simulation slot. It is a model-level proxy, not physical throughput in bits/s or Mbps, because the simulator does not model a complete shared eMBB transmission timeline.", "",

        f"Bootstrap replicates: {BOOTSTRAP_REPLICATES}",

        f"Bootstrap RNG seed: {BOOTSTRAP_SEED}",

    ]

    path.write_text("\n".join(sections) + "\n", encoding="utf-8")

    return path

def main() -> None:

    """Run all descriptive and extended RQ2 analyses from one entry point."""

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    baseline_raw = load_raw(BASELINE_FILE)

    rq1_raw = load_raw(RQ1_FILE)

    rq2_raw = load_raw(RQ2_FILE)

    rq3_raw = load_raw(RQ3_FILE)

    baseline = baseline_summary(baseline_raw)

    rq1 = descriptive_summary(rq1_raw, "traffic_level", "RQ1")

    rq2 = descriptive_summary(rq2_raw, "preemption_pattern", "RQ2")

    rq3 = descriptive_summary(rq3_raw, "cbg_count", "RQ3")

    # Include the scheduling experiment in this same analysis entry point.
    scheduling_summary = load_scheduling_realism()

    outputs: list[Path] = []

    for summary, filename in (

        (baseline, "baseline_summary.csv"),

        (rq1, "rq1_summary.csv"),

        (rq2, "rq2_summary.csv"),

        (rq3, "rq3_summary.csv"),

    ):

        path = PROCESSED_DIR / filename

        summary.to_csv(path, index=False)

        outputs.append(path)

    outputs.append(PROCESSED_DIR / SCHEDULING_SUMMARY_FILE)

    # The sensitivity experiment is an existing input dataset, not a separate

    # analysis program. It is included here alongside the official RQ1-RQ3 runs.

    require_file(SENSITIVITY_FILE)

    official_rq2 = normalise_columns(rq2_raw, "Official RQ2 raw data")

    sensitivity = normalise_columns(pd.read_csv(SENSITIVITY_FILE), "Decoder sensitivity data")

    validate_columns(official_rq2, ["seed"], "Official RQ2 raw data")

    validate_columns(sensitivity, ["seed", "snr_db"], "Decoder sensitivity data")

    official_rq2["seed"] = pd.to_numeric(official_rq2["seed"], errors="raise").astype(int)

    sensitivity["seed"] = pd.to_numeric(sensitivity["seed"], errors="raise").astype(int)

    sensitivity["snr_db"] = pd.to_numeric(sensitivity["snr_db"], errors="raise")

    observed_snr = set(sensitivity["snr_db"].unique())

    if observed_snr != set(EXPECTED_SNR_DB):

        raise ValueError(f"Expected SNR values {EXPECTED_SNR_DB}; found {sorted(observed_snr)}")

    validate_pairing(official_rq2, ["preemption_pattern"])

    validate_pairing(sensitivity, ["snr_db", "preemption_pattern"])

    rng = np.random.default_rng(BOOTSTRAP_SEED)

    official_rq2_stats = make_bootstrap_summary(

        official_rq2, ["preemption_pattern"], rng

    ).sort_values("preemption_pattern")

    sensitivity_stats = make_bootstrap_summary(

        sensitivity, ["snr_db", "preemption_pattern"], rng

    ).sort_values(["snr_db", "preemption_pattern"])

    comparisons = paired_pattern_comparisons(sensitivity, ["snr_db"], rng).sort_values(

        ["snr_db", "pattern_a", "pattern_b"]

    )

    interactions = interaction_bootstrap(sensitivity, rng)

    extended_outputs = {

        "rq2_bootstrap_summary.csv": official_rq2_stats,

        "decoder_sensitivity_summary.csv": sensitivity_stats,

        "rq2_paired_comparisons.csv": comparisons,

        "rq2_interaction_bootstrap.csv": interactions,

    }

    for filename, frame in extended_outputs.items():

        path = PROCESSED_DIR / filename

        frame.to_csv(path, index=False)

        outputs.append(path)

    outputs.append(plot_sensitivity(sensitivity_stats))

    outputs.append(plot_pattern_differences(comparisons))

    outputs.append(write_report(

        baseline, rq1, rq2, rq3, sensitivity_stats, comparisons, interactions,
        scheduling_summary

    ))

    for label, frame in (

        ("Baseline", baseline), ("RQ1", rq1), ("RQ2", rq2), ("RQ3", rq3),
        ("Scheduling realism", scheduling_summary),

        ("RQ2 paired comparisons (decoder sensitivity)", comparisons),

        ("SNR interaction analysis", interactions),

    ):

        print(f"\n{label}\n{frame.to_string(index=False)}")

    print("\nGenerated outputs:")

    for path in outputs:

        print(f"  {path.relative_to(ROOT)}")

if __name__ == "__main__":

    main()

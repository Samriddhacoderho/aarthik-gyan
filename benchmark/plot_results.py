"""Generate documentation-ready plots from a benchmark JSON result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


PALETTE = {
    "graphrag": "#2563eb",
    "vector": "#f97316",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot benchmark/results/latest.json with pandas, seaborn, and matplotlib."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("benchmark/results/latest.json"),
        help="Benchmark JSON result (default: benchmark/results/latest.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark/results/plots"),
        help="Directory for generated PNG files (default: benchmark/results/plots)",
    )
    parser.add_argument(
        "--format",
        choices=("png", "svg", "pdf"),
        default="png",
        help="Output format for plots (default: png)",
    )
    return parser.parse_args()


def load_result(path: Path) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    with path.open(encoding="utf-8") as handle:
        result = json.load(handle)

    metadata = result.get("metadata", {})
    summary = pd.DataFrame.from_dict(result.get("summary", {}), orient="index")
    summary.index.name = "system"
    records = pd.DataFrame(result.get("records", []))
    if records.empty:
        raise ValueError(f"No per-question records found in {path}")
    return metadata, summary.reset_index(), records


def save_figure(fig: plt.Figure, output_dir: Path, name: str, file_format: str) -> None:
    fig.tight_layout()
    fig.savefig(
        output_dir / f"{name}.{file_format}",
        dpi=220,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


def system_order(metadata: dict[str, Any], values: pd.Series) -> list[str]:
    configured = metadata.get("systems", [])
    return [system for system in configured if system in set(values)] + [
        system for system in values if system not in configured
    ]


def plot_overall_quality(
    summary: pd.DataFrame,
    metadata: dict[str, Any],
    output_dir: Path,
    file_format: str,
) -> None:
    metric_columns = {
        "Evidence recall": "evidence_recall_mean",
        "Retrieval hit rate": "retrieval_hit_rate",
    }
    available = {
        label: column
        for label, column in metric_columns.items()
        if column in summary and summary[column].notna().any()
    }
    if not available:
        return

    plot = summary.melt(
        id_vars="system",
        value_vars=list(available.values()),
        var_name="metric",
        value_name="score",
    )
    plot["metric"] = plot["metric"].map({value: key for key, value in available.items()})
    order = system_order(metadata, summary["system"])

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(
        data=plot,
        x="metric",
        y="score",
        hue="system",
        hue_order=order,
        palette=PALETTE,
        ax=ax,
    )
    ax.set(title="Overall retrieval quality", xlabel="", ylabel="Score")
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend(title="System", frameon=False)
    for container in ax.containers:
        ax.bar_label(container, fmt=lambda value: f"{value:.1%}", padding=3)
    save_figure(fig, output_dir, "01_overall_retrieval_quality", file_format)


def plot_latency(
    summary: pd.DataFrame,
    metadata: dict[str, Any],
    output_dir: Path,
    file_format: str,
) -> None:
    metric_columns = {
        "Median (p50)": "retrieval_latency_ms_p50",
        "Tail (p95)": "retrieval_latency_ms_p95",
    }
    available = [
        column
        for column in metric_columns.values()
        if column in summary and summary[column].notna().any()
    ]
    if not available:
        return

    plot = summary.melt(
        id_vars="system",
        value_vars=available,
        var_name="percentile",
        value_name="milliseconds",
    )
    plot["percentile"] = plot["percentile"].map(
        {value: key for key, value in metric_columns.items()}
    )
    order = system_order(metadata, summary["system"])

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(
        data=plot,
        x="percentile",
        y="milliseconds",
        hue="system",
        hue_order=order,
        palette=PALETTE,
        ax=ax,
    )
    ax.set(
        title="Retrieval latency",
        xlabel="",
        ylabel="Milliseconds (log scale)",
        yscale="log",
    )
    ax.legend(title="System", frameon=False)
    for container in ax.containers:
        ax.bar_label(container, fmt=lambda value: f"{value:,.0f}", padding=3)
    save_figure(fig, output_dir, "02_retrieval_latency", file_format)


def plot_question_type_heatmap(
    summary: pd.DataFrame,
    metadata: dict[str, Any],
    output_dir: Path,
    file_format: str,
) -> None:
    by_type: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        for question_type, metrics in row.get("by_question_type", {}).items():
            by_type.append(
                {
                    "system": row["system"],
                    "question_type": question_type,
                    "evidence_recall": metrics.get("evidence_recall_mean"),
                }
            )
    if not by_type:
        return

    plot = pd.DataFrame(by_type)
    matrix = plot.pivot(index="question_type", columns="system", values="evidence_recall")
    matrix = matrix.reindex(columns=system_order(metadata, matrix.columns))

    fig, ax = plt.subplots(figsize=(9, max(4, len(matrix) * 0.65)))
    sns.heatmap(
        matrix,
        annot=True,
        fmt=".0%",
        cmap="YlGnBu",
        vmin=0,
        vmax=1,
        linewidths=0.5,
        cbar_kws={"label": "Evidence recall"},
        ax=ax,
    )
    ax.set(title="Evidence recall by question type", xlabel="", ylabel="")
    save_figure(fig, output_dir, "03_evidence_recall_by_question_type", file_format)


def plot_success_rate(
    summary: pd.DataFrame,
    metadata: dict[str, Any],
    output_dir: Path,
    file_format: str,
) -> None:
    if "questions" not in summary or "errors" not in summary:
        return
    plot = summary[["system", "questions", "errors"]].copy()
    plot["successful"] = plot["questions"] - plot["errors"]
    plot = plot.set_index("system")[["successful", "errors"]]
    plot = plot.reindex(system_order(metadata, plot.index))

    fig, ax = plt.subplots(figsize=(7, 5))
    plot.plot(
        kind="bar",
        stacked=True,
        color=["#16a34a", "#dc2626"],
        ax=ax,
    )
    ax.set(title="Retrieval execution outcomes", xlabel="", ylabel="Questions")
    ax.legend(["Successful", "Errors"], frameon=False)
    ax.tick_params(axis="x", rotation=0)
    for container in ax.containers:
        ax.bar_label(container, label_type="center", color="white", fontsize=9)
    save_figure(fig, output_dir, "04_retrieval_success_and_errors", file_format)


def plot_record_distribution(
    records: pd.DataFrame,
    metadata: dict[str, Any],
    output_dir: Path,
    file_format: str,
) -> None:
    plot = records.loc[records["error"].isna(), ["system", "evidence_recall"]].copy()
    if plot.empty:
        return
    order = system_order(metadata, plot["system"])

    fig, ax = plt.subplots(figsize=(7, 5))
    sns.boxplot(
        data=plot,
        x="system",
        y="evidence_recall",
        order=order,
        hue="system",
        palette=PALETTE,
        legend=False,
        ax=ax,
    )
    sns.stripplot(
        data=plot,
        x="system",
        y="evidence_recall",
        order=order,
        color="#111827",
        alpha=0.45,
        size=3,
        ax=ax,
    )
    ax.set(
        title="Per-question evidence recall distribution",
        xlabel="",
        ylabel="Evidence recall",
        ylim=(0, 1.05),
    )
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    save_figure(fig, output_dir, "05_per_question_recall_distribution", file_format)


def main() -> None:
    args = parse_args()
    metadata, summary, records = load_result(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")
    plot_overall_quality(summary, metadata, args.output_dir, args.format)
    plot_latency(summary, metadata, args.output_dir, args.format)
    plot_question_type_heatmap(summary, metadata, args.output_dir, args.format)
    plot_success_rate(summary, metadata, args.output_dir, args.format)
    plot_record_distribution(records, metadata, args.output_dir, args.format)

    print(f"Generated plots in {args.output_dir}")


if __name__ == "__main__":
    main()

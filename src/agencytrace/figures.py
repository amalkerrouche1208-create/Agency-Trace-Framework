from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


DEFAULT_ANALYSIS_DIR = Path("data/analysis")
DEFAULT_OUTPUT_DIR = Path("figures")

OUTCOME_INPUT = "target_outcomes_by_ai_share.csv"
CORRELATION_INPUT = "target_behavior_correlations.csv"

TEXT = "#23292C"
GRID = "#E7E4DF"

GROUP_ORDER = (
    "Low",
    "Moderate",
    "High",
)

OUTCOME_ORDER = (
    "direct_adoption",
    "modified_adoption",
    "non_adoption",
    "no_selection",
    "no_suggestion",
)

OUTCOME_LABELS = {
    "direct_adoption": "Direct Adoption",
    "modified_adoption": "Modified Adoption",
    "non_adoption": "Non-Adoption",
    "no_selection": "No Selection",
    "no_suggestion": "No Suggestion",
}


OUTCOME_COLORS = {
    "direct_adoption": "#C95D45",
    "modified_adoption": "#E1B84B",
    "non_adoption": "#6F9B63",
    "no_selection": "#A9ADAC",
    "no_suggestion": "#D3D0C9",
}

HEATMAP_LABELS = (
    "Human Generation\nBefore AI",
    "Consultation\nDensity",
    "AI\nContribution",
    "AI\nRetention",
    "Non-Adoption",
    "Post-AI\nEditing",
    "Reconsultation",
    "Response\nLatency",
    "Transition\nEntropy",
    "Consultation\nBurstiness",
)

HEATMAP_SOURCE_LABELS = (
    "Human Generation Before AI",
    "Consultation Density",
    "AI Contribution",
    "AI Retention",
    "Non-Adoption",
    "Post-AI Editing",
    "Reconsultation",
    "Response Latency",
    "Transition Entropy",
    "Consultation Burstiness",
)


def generate_target_figures(
    *,
    analysis_dir: str | Path = DEFAULT_ANALYSIS_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> None:
    analysis_dir = Path(analysis_dir)
    output_dir = Path(output_dir)

    outcome_path = analysis_dir / OUTCOME_INPUT
    correlation_path = analysis_dir / CORRELATION_INPUT

    _require_file(outcome_path)
    _require_file(correlation_path)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    plot_ai_share_response_outcomes(
        outcome_path,
        output_dir,
    )

    plot_trace_indicator_correlations(
        correlation_path,
        output_dir,
    )

    print()
    print("=" * 78)
    print("AgencyTrace — Target Figure Export")
    print("=" * 78)
    print(f"Analysis directory             : {analysis_dir}")
    print(f"Figure directory               : {output_dir}")
    print()
    print("Generated:")
    print("  ai_share_response_outcomes.png")
    print("  ai_share_response_outcomes.pdf")
    print("  trace_indicator_correlations.png")
    print("  trace_indicator_correlations.pdf")
    print()
    print("=" * 78)
    print("Target figure export completed.")
    print("=" * 78)



def plot_ai_share_response_outcomes(
    csv_path: str | Path,
    output_dir: str | Path,
) -> None:
    csv_path = Path(csv_path)
    output_dir = Path(output_dir)

    rows = _load_outcome_rows(
        csv_path
    )

    group_to_row = {
        row["group"]: row
        for row in rows
    }

    missing_groups = [
        group
        for group in GROUP_ORDER
        if group not in group_to_row
    ]

    if missing_groups:
        raise ValueError(
            "Missing AI-share groups in "
            f"{csv_path}: {missing_groups}"
        )

    values = {
        outcome: np.asarray(
            [
                100.0
                * float(
                    group_to_row[group][
                        outcome
                    ]
                )
                for group in GROUP_ORDER
            ],
            dtype=float,
        )
        for outcome in OUTCOME_ORDER
    }

    totals = np.zeros(
        len(GROUP_ORDER),
        dtype=float,
    )

    for outcome in OUTCOME_ORDER:
        totals += values[outcome]

    if not np.allclose(
        totals,
        100.0,
        atol=1e-6,
    ):
        raise ValueError(
            "Outcome shares do not sum to 100% "
            f"per group: {totals.tolist()}"
        )

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "axes.labelcolor": TEXT,
            "xtick.color": TEXT,
            "ytick.color": TEXT,
            "text.color": TEXT,
        }
    )

    fig, ax = plt.subplots(
        figsize=(9.4, 4.7)
    )

    y = np.arange(
        len(GROUP_ORDER)
    )

    left = np.zeros(
        len(GROUP_ORDER),
        dtype=float,
    )

    for outcome in OUTCOME_ORDER:
        segment = values[
            outcome
        ]

        bars = ax.barh(
            y,
            segment,
            left=left,
            height=0.56,
            color=OUTCOME_COLORS[outcome],
            edgecolor="white",
            linewidth=0.8,
            label=OUTCOME_LABELS[outcome],
        )

        for index, (
            bar,
            percentage,
        ) in enumerate(
            zip(
                bars,
                segment,
            )
        ):
            
            if percentage < 6.5:
                continue

            x = (
                left[index]
                + percentage / 2.0
            )

            color = (
                "white"
                if outcome
                in {
                    "direct_adoption",
                    "non_adoption",
                }
                else TEXT
            )

            ax.text(
                x,
                bar.get_y()
                + bar.get_height() / 2.0,
                f"{percentage:.1f}%",
                ha="center",
                va="center",
                fontsize=9.5,
                fontweight="bold",
                color=color,
            )

        left += segment

    ax.set_yticks(
        y
    )

    ax.set_yticklabels(
        [
            "Low AI Share",
            "Moderate AI Share",
            "High AI Share",
        ]
    )

    
    ax.invert_yaxis()

    ax.set_xlim(
        0,
        100,
    )

    ax.set_xticks(
        np.arange(
            0,
            101,
            20,
        )
    )

    ax.set_xlabel(
        "Share of suggestion requests (%)"
    )

    ax.set_title(
        "Response Outcomes by AI Share",
        fontsize=13,
        fontweight="bold",
        pad=14,
    )

    ax.grid(
        axis="x",
        color=GRID,
        linewidth=0.8,
        alpha=0.8,
    )

    ax.set_axisbelow(
        True
    )

    for spine in (
        "top",
        "right",
        "left",
    ):
        ax.spines[
            spine
        ].set_visible(
            False
        )

    ax.spines[
        "bottom"
    ].set_color(
        "#B9B6B0"
    )

    ax.tick_params(
        axis="y",
        length=0,
        pad=8,
    )

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(
            0.5,
            -0.17,
        ),
        ncol=5,
        frameon=False,
        fontsize=8.8,
        handlelength=1.6,
        columnspacing=1.4,
    )

    fig.subplots_adjust(
        left=0.20,
        right=0.985,
        top=0.84,
        bottom=0.26,
    )

    _save_figure(
        fig,
        output_dir,
        "ai_share_response_outcomes",
    )


# =====================================================================
# Figure 2 — Historical 10 × 10 Spearman correlation heatmap
# =====================================================================


def plot_trace_indicator_correlations(
    csv_path: str | Path,
    output_dir: str | Path,
) -> None:
    csv_path = Path(csv_path)
    output_dir = Path(output_dir)

    (
        row_labels,
        column_labels,
        matrix,
    ) = _load_correlation_matrix(
        csv_path
    )

    if (
        tuple(row_labels)
        != HEATMAP_SOURCE_LABELS
    ):
        raise ValueError(
            "Unexpected heatmap row order.\n"
            f"Expected: {HEATMAP_SOURCE_LABELS}\n"
            f"Observed: {tuple(row_labels)}"
        )

    if (
        tuple(column_labels)
        != HEATMAP_SOURCE_LABELS
    ):
        raise ValueError(
            "Unexpected heatmap column order.\n"
            f"Expected: {HEATMAP_SOURCE_LABELS}\n"
            f"Observed: {tuple(column_labels)}"
        )

    if matrix.shape != (
        10,
        10,
    ):
        raise ValueError(
            "Target correlation matrix must be 10x10; "
            f"got {matrix.shape}."
        )

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 10,
            "axes.labelcolor": TEXT,
            "xtick.color": TEXT,
            "ytick.color": TEXT,
            "text.color": TEXT,
        }
    )

    
    fig, ax = plt.subplots(
        figsize=(8.8, 7.2)
    )

    image = ax.imshow(
        matrix,
        cmap="coolwarm",
        vmin=-1,
        vmax=1,
    )

    indices = np.arange(
        len(
            HEATMAP_LABELS
        )
    )

    ax.set_xticks(
        indices
    )

    ax.set_yticks(
        indices
    )

    ax.set_xticklabels(
        HEATMAP_LABELS,
        rotation=45,
        ha="right",
    )

    ax.set_yticklabels(
        HEATMAP_LABELS
    )

    for i in range(
        matrix.shape[0]
    ):
        for j in range(
            matrix.shape[1]
        ):
            value = matrix[
                i,
                j,
            ]

            if np.isnan(
                value
            ):
                continue

            ax.text(
                j,
                i,
                f"{value:.2f}",
                ha="center",
                va="center",
                fontsize=8.5,
                color=(
                    "white"
                    if abs(value) >= 0.55
                    else "#1D2224"
                ),
            )

    colorbar = fig.colorbar(
        image,
        ax=ax,
        fraction=0.045,
        pad=0.04,
    )

    colorbar.set_label(
        "Spearman ρ"
    )

    for spine in (
        ax.spines.values()
    ):
        spine.set_visible(
            False
        )

    ax.set_xticks(
        np.arange(
            -0.5,
            len(
                HEATMAP_LABELS
            ),
            1,
        ),
        minor=True,
    )

    ax.set_yticks(
        np.arange(
            -0.5,
            len(
                HEATMAP_LABELS
            ),
            1,
        ),
        minor=True,
    )

    ax.grid(
        which="minor",
        color="white",
        linewidth=1.15,
    )

    ax.tick_params(
        which="minor",
        bottom=False,
        left=False,
    )

    _save_figure(
        fig,
        output_dir,
        "trace_indicator_correlations",
    )





def _load_outcome_rows(
    path: Path,
) -> list[dict[str, str]]:
    required = {
        "group",
        *OUTCOME_ORDER,
    }

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle
        )

        fieldnames = set(
            reader.fieldnames
            or []
        )

        missing = (
            required
            - fieldnames
        )

        if missing:
            raise ValueError(
                f"{path} is missing columns: "
                f"{sorted(missing)}"
            )

        rows = list(
            reader
        )

    if not rows:
        raise ValueError(
            f"No rows found in {path}."
        )

    return rows


def _load_correlation_matrix(
    path: Path,
) -> tuple[
    list[str],
    list[str],
    np.ndarray,
]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.reader(
            handle
        )

        rows = list(
            reader
        )

    if len(rows) < 2:
        raise ValueError(
            f"Correlation matrix is empty: {path}"
        )

    header = rows[0]

    if (
        not header
        or header[0]
        != "variable"
    ):
        raise ValueError(
            "Expected first correlation CSV column "
            "to be named 'variable'."
        )

    column_labels = header[
        1:
    ]

    row_labels: list[str] = []
    matrix_rows: list[
        list[float]
    ] = []

    for row in rows[
        1:
    ]:
        if len(row) != len(
            header
        ):
            raise ValueError(
                "Malformed correlation CSV row: "
                f"{row}"
            )

        row_labels.append(
            row[0]
        )

        matrix_rows.append(
            [
                _parse_float(
                    value
                )
                for value in row[
                    1:
                ]
            ]
        )

    matrix = np.asarray(
        matrix_rows,
        dtype=float,
    )

    return (
        row_labels,
        column_labels,
        matrix,
    )


# =====================================================================
# Saving / validation helpers
# =====================================================================


def _save_figure(
    fig: plt.Figure,
    output_dir: Path,
    name: str,
) -> None:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    fig.savefig(
        output_dir
        / f"{name}.png",
        bbox_inches="tight",
        facecolor="white",
        dpi=600,
    )

    fig.savefig(
        output_dir
        / f"{name}.pdf",
        bbox_inches="tight",
        facecolor="white",
    )

    plt.close(
        fig
    )


def _parse_float(
    value: str,
) -> float:
    text = value.strip()

    if text in {
        "",
        "nan",
        "NaN",
        "None",
        "null",
    }:
        return math.nan

    return float(
        text
    )


def _require_file(
    path: Path,
) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"Required analysis file not found: {path}"
        )


# =====================================================================
# CLI
# =====================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the validated AgencyTrace "
            "target figures."
        )
    )

    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=DEFAULT_ANALYSIS_DIR,
        help=(
            "Directory containing the validated "
            "analysis CSV files."
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Directory for PNG/PDF figures."
        ),
    )

    args = parser.parse_args()

    generate_target_figures(
        analysis_dir=args.analysis_dir,
        output_dir=args.out,
    )


if __name__ == "__main__":
    main()

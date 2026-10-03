from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import mean


ANALYSIS_DIR = Path("data/analysis")

METRICS_PATH = ANALYSIS_DIR / "target_behavior_metrics.csv"
OUTCOMES_PATH = ANALYSIS_DIR / "target_request_outcomes.csv"
GROUPS_PATH = ANALYSIS_DIR / "session_ai_share_groups.csv"

CORRELATION_OUTPUT = (
    ANALYSIS_DIR / "target_behavior_correlations.csv"
)

SAMPLE_SIZE_OUTPUT = (
    ANALYSIS_DIR / "target_behavior_sample_sizes.csv"
)

OUTCOME_GROUP_OUTPUT = (
    ANALYSIS_DIR / "target_outcomes_by_ai_share.csv"
)


VARIABLES = [
    "human_generation_before_ai",
    "consultation_density",
    "ai_contribution",
    "ai_retention",
    "non_adoption",
    "post_ai_editing",
    "reconsultation",
    "response_latency",
    "transition_entropy",
    "consultation_burstiness",
]


OUTCOMES = [
    "direct_adoption",
    "modified_adoption",
    "non_adoption",
    "no_selection",
    "no_suggestion",
]


GROUP_ORDER = [
    "Low",
    "Moderate",
    "High",
]


def main() -> None:
    metrics = _read_metrics(
        METRICS_PATH
    )

    groups = _read_groups(
        GROUPS_PATH
    )

    (
        correlations,
        sample_sizes,
    ) = _compute_spearman_matrix(
        metrics
    )

    _write_matrix(
        CORRELATION_OUTPUT,
        VARIABLES,
        correlations,
    )

    _write_int_matrix(
        SAMPLE_SIZE_OUTPUT,
        VARIABLES,
        sample_sizes,
    )

    outcome_rows = (
        _compute_outcomes_by_group(
            groups
        )
    )

    _write_outcome_groups(
        OUTCOME_GROUP_OUTPUT,
        outcome_rows,
    )

    print()
    print("=" * 78)
    print(
        "AgencyTrace — Target Analysis"
    )
    print("=" * 78)

    print(
        f"Sessions analyzed               : "
        f"{len(metrics)}"
    )

    print()

    print(
        "REQUEST OUTCOMES BY AI-SHARE GROUP"
    )
    print("-" * 78)

    for row in outcome_rows:
        print(
            f"{row['group']:<10} "
            f"N={row['total']:<5} "
            f"Direct={row['direct_adoption_share']:.4f} "
            f"Modified={row['modified_adoption_share']:.4f} "
            f"Non={row['non_adoption_share']:.4f} "
            f"NoSel={row['no_selection_share']:.4f} "
            f"NoSug={row['no_suggestion_share']:.4f}"
        )

    print()
    print(
        f"Correlation matrix             : "
        f"{CORRELATION_OUTPUT}"
    )

    print(
        f"Outcome composition            : "
        f"{OUTCOME_GROUP_OUTPUT}"
    )

    print()
    print("=" * 78)
    print(
        "Target analysis completed."
    )
    print("=" * 78)


def _read_metrics(
    path: Path,
) -> list[dict[str, float | None]]:
    rows = []

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle
        )

        for raw in reader:
            row = {
                "session_id":
                    raw["session_id"]
            }

            for variable in VARIABLES:
                row[variable] = (
                    _optional_float(
                        raw[variable]
                    )
                )

            rows.append(
                row
            )

    return rows


def _read_groups(
    path: Path,
) -> dict[str, str]:
    result = {}

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle
        )

        for row in reader:
            result[
                row["session_id"]
            ] = row[
                "ai_share_group"
            ]

    return result


def _compute_outcomes_by_group(
    session_groups: dict[str, str],
) -> list[dict[str, object]]:
    counts = {
        group: {
            outcome: 0
            for outcome in OUTCOMES
        }
        for group in GROUP_ORDER
    }

    with OUTCOMES_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle
        )

        for row in reader:
            session_id = row[
                "session_id"
            ]

            group = session_groups[
                session_id
            ]

            outcome = row[
                "outcome"
            ]

            counts[
                group
            ][
                outcome
            ] += 1

    results = []

    for group in GROUP_ORDER:
        total = sum(
            counts[group].values()
        )

        row: dict[str, object] = {
            "group": group,
            "total": total,
        }

        for outcome in OUTCOMES:
            count = counts[
                group
            ][
                outcome
            ]

            row[
                f"{outcome}_count"
            ] = count

            row[
                f"{outcome}_share"
            ] = (
                count / total
                if total
                else 0.0
            )

        results.append(
            row
        )

    return results


def _compute_spearman_matrix(
    rows: list[
        dict[str, float | None]
    ],
) -> tuple[
    list[list[float]],
    list[list[int]],
]:
    correlations = []
    sample_sizes = []

    for left_name in VARIABLES:
        correlation_row = []
        n_row = []

        for right_name in VARIABLES:
            left = []
            right = []

            for row in rows:
                x = row[
                    left_name
                ]

                y = row[
                    right_name
                ]

                if (
                    x is None
                    or y is None
                ):
                    continue

                if (
                    not math.isfinite(x)
                    or not math.isfinite(y)
                ):
                    continue

                left.append(
                    x
                )

                right.append(
                    y
                )

            correlation_row.append(
                _spearman(
                    left,
                    right,
                )
            )

            n_row.append(
                len(left)
            )

        correlations.append(
            correlation_row
        )

        sample_sizes.append(
            n_row
        )

    return (
        correlations,
        sample_sizes,
    )


def _spearman(
    x: list[float],
    y: list[float],
) -> float:
    if len(x) < 2:
        return math.nan

    return _pearson(
        _rankdata(x),
        _rankdata(y),
    )


def _rankdata(
    values: list[float],
) -> list[float]:
    indexed = sorted(
        enumerate(values),
        key=lambda pair: pair[1],
    )

    ranks = [
        0.0
    ] * len(values)

    i = 0

    while i < len(indexed):
        j = i + 1

        while (
            j < len(indexed)
            and indexed[j][1]
            == indexed[i][1]
        ):
            j += 1

        average_rank = (
            (i + 1)
            + j
        ) / 2.0

        for k in range(
            i,
            j,
        ):
            ranks[
                indexed[k][0]
            ] = average_rank

        i = j

    return ranks


def _pearson(
    x: list[float],
    y: list[float],
) -> float:
    mx = mean(x)
    my = mean(y)

    numerator = sum(
        (a - mx)
        * (b - my)
        for a, b
        in zip(
            x,
            y,
        )
    )

    denominator = math.sqrt(
        sum(
            (a - mx) ** 2
            for a in x
        )
        *
        sum(
            (b - my) ** 2
            for b in y
        )
    )

    if denominator == 0:
        return math.nan

    return (
        numerator
        / denominator
    )


def _write_matrix(
    path: Path,
    names: list[str],
    matrix: list[list[float]],
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "variable",
                *names,
            ]
        )

        for name, row in zip(
            names,
            matrix,
        ):
            writer.writerow(
                [
                    name,
                    *row,
                ]
            )


def _write_int_matrix(
    path: Path,
    names: list[str],
    matrix: list[list[int]],
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "variable",
                *names,
            ]
        )

        for name, row in zip(
            names,
            matrix,
        ):
            writer.writerow(
                [
                    name,
                    *row,
                ]
            )


def _write_outcome_groups(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    fieldnames = list(
        rows[0].keys()
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def _optional_float(
    value: str,
) -> float | None:
    if value in {
        "",
        "None",
        "nan",
        "NaN",
    }:
        return None

    return float(
        value
    )


if __name__ == "__main__":
    main()
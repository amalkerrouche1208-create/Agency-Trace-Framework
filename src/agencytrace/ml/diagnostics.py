from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np

from agencytrace.ml.features import (
    FEATURE_SPECS,
    PROFILE_FEATURES,
)


def _optional_float(
    value: object,
) -> float | None:
    if value is None:
        return None

    text = str(value).strip()

    if text in {
        "",
        "None",
        "nan",
        "NaN",
        "NA",
    }:
        return None

    number = float(text)

    if not math.isfinite(number):
        return None

    return number


def load_feature_rows(
    path: Path,
) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(handle)
        )


def summarize_features(
    rows: list[Mapping[str, object]],
    features: Iterable[str] = PROFILE_FEATURES,
) -> list[dict[str, object]]:
    specs = {
        spec.name: spec
        for spec in FEATURE_SPECS
    }

    summaries: list[
        dict[str, object]
    ] = []

    n_rows = len(rows)

    for name in features:
        values = [
            _optional_float(
                row.get(name)
            )
            for row in rows
        ]

        observed = np.asarray(
            [
                value
                for value in values
                if value is not None
            ],
            dtype=float,
        )

        n_observed = int(
            observed.size
        )

        n_missing = (
            n_rows
            - n_observed
        )

        if n_observed == 0:
            minimum = math.nan
            q1 = math.nan
            median = math.nan
            q3 = math.nan
            maximum = math.nan
            mean = math.nan
            std = math.nan
            skewness = math.nan
            zero_fraction = math.nan
            unique_values = 0

        else:
            minimum = float(
                np.min(observed)
            )

            q1 = float(
                np.quantile(
                    observed,
                    0.25,
                )
            )

            median = float(
                np.median(observed)
            )

            q3 = float(
                np.quantile(
                    observed,
                    0.75,
                )
            )

            maximum = float(
                np.max(observed)
            )

            mean = float(
                np.mean(observed)
            )

            std = float(
                np.std(
                    observed,
                    ddof=0,
                )
            )

            zero_fraction = float(
                np.mean(
                    observed == 0
                )
            )

            unique_values = int(
                np.unique(
                    observed
                ).size
            )

            if std > 0:
                standardized = (
                    observed - mean
                ) / std

                skewness = float(
                    np.mean(
                        standardized**3
                    )
                )

            else:
                skewness = 0.0

        spec = specs.get(name)

        summaries.append(
            {
                "feature": name,
                "family": (
                    spec.family
                    if spec
                    else ""
                ),
                "analysis_role": (
                    spec.leakage_role
                    if spec
                    else ""
                ),
                "n_total": n_rows,
                "n_observed": n_observed,
                "n_missing": n_missing,
                "missing_fraction": (
                    n_missing / n_rows
                    if n_rows
                    else math.nan
                ),
                "zero_fraction_observed": (
                    zero_fraction
                ),
                "unique_values": (
                    unique_values
                ),
                "min": minimum,
                "q1": q1,
                "median": median,
                "q3": q3,
                "max": maximum,
                "mean": mean,
                "std": std,
                "skewness": skewness,
                "zero_dominated": int(
                    math.isfinite(
                        zero_fraction
                    )
                    and zero_fraction
                    >= 0.95
                ),
            }
        )

    return summaries


def _average_ranks(
    values: np.ndarray,
) -> np.ndarray:
    order = np.argsort(
        values,
        kind="mergesort",
    )

    ranks = np.empty(
        len(values),
        dtype=float,
    )

    i = 0

    while i < len(values):
        j = i + 1

        while (
            j < len(values)
            and values[
                order[j]
            ]
            == values[
                order[i]
            ]
        ):
            j += 1

        average_rank = (
            i + j - 1
        ) / 2.0 + 1.0

        ranks[
            order[i:j]
        ] = average_rank

        i = j

    return ranks


def _spearman(
    x: np.ndarray,
    y: np.ndarray,
) -> float:
    if (
        len(x) < 3
        or len(y) < 3
    ):
        return math.nan

    x_ranks = _average_ranks(x)
    y_ranks = _average_ranks(y)

    x_std = float(
        np.std(x_ranks)
    )

    y_std = float(
        np.std(y_ranks)
    )

    if (
        x_std == 0
        or y_std == 0
    ):
        return math.nan

    matrix = np.corrcoef(
        x_ranks,
        y_ranks,
    )

    return float(
        matrix[0, 1]
    )


def compute_spearman_matrix(
    rows: list[Mapping[str, object]],
    features: Iterable[str] = PROFILE_FEATURES,
) -> tuple[
    list[str],
    np.ndarray,
    np.ndarray,
]:
    names = list(features)

    size = len(names)

    correlations = np.full(
        (
            size,
            size,
        ),
        np.nan,
        dtype=float,
    )

    sample_sizes = np.zeros(
        (
            size,
            size,
        ),
        dtype=int,
    )

    for i, left in enumerate(
        names
    ):
        for j, right in enumerate(
            names
        ):
            paired = [
                (
                    _optional_float(
                        row.get(left)
                    ),
                    _optional_float(
                        row.get(right)
                    ),
                )
                for row in rows
            ]

            valid = [
                (
                    x,
                    y,
                )
                for x, y in paired
                if (
                    x is not None
                    and y is not None
                )
            ]

            n = len(valid)

            sample_sizes[
                i,
                j,
            ] = n

            if i == j:
                correlations[
                    i,
                    j,
                ] = (
                    1.0
                    if n > 0
                    else math.nan
                )

                continue

            if n < 3:
                continue

            x_values = np.asarray(
                [
                    x
                    for x, _
                    in valid
                ],
                dtype=float,
            )

            y_values = np.asarray(
                [
                    y
                    for _, y
                    in valid
                ],
                dtype=float,
            )

            correlations[
                i,
                j,
            ] = _spearman(
                x_values,
                y_values,
            )

    return (
        names,
        correlations,
        sample_sizes,
    )


def compute_missingness_patterns(
    rows: list[Mapping[str, object]],
    features: Iterable[str] = PROFILE_FEATURES,
) -> list[dict[str, object]]:
    names = list(features)

    patterns: Counter[
        tuple[str, ...]
    ] = Counter()

    for row in rows:
        missing = tuple(
            name
            for name in names
            if _optional_float(
                row.get(name)
            )
            is None
        )

        patterns[
            missing
        ] += 1

    total = len(rows)

    output: list[
        dict[str, object]
    ] = []

    for missing, count in sorted(
        patterns.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        output.append(
            {
                "missing_features": (
                    ";".join(missing)
                ),
                "missing_count": (
                    len(missing)
                ),
                "sessions": count,
                "session_fraction": (
                    count / total
                    if total
                    else math.nan
                ),
            }
        )

    return output


def strongest_correlations(
    names: list[str],
    matrix: np.ndarray,
    *,
    minimum_absolute_rho: float = 0.70,
) -> list[dict[str, object]]:
    pairs: list[
        dict[str, object]
    ] = []

    for i in range(
        len(names)
    ):
        for j in range(
            i + 1,
            len(names),
        ):
            rho = float(
                matrix[
                    i,
                    j,
                ]
            )

            if not math.isfinite(rho):
                continue

            if (
                abs(rho)
                < minimum_absolute_rho
            ):
                continue

            pairs.append(
                {
                    "feature_a": (
                        names[i]
                    ),
                    "feature_b": (
                        names[j]
                    ),
                    "spearman_rho": rho,
                    "absolute_rho": abs(
                        rho
                    ),
                }
            )

    pairs.sort(
        key=lambda row: (
            -float(
                row[
                    "absolute_rho"
                ]
            ),
            str(
                row[
                    "feature_a"
                ]
            ),
            str(
                row[
                    "feature_b"
                ]
            ),
        )
    )

    return pairs


def _write_dict_rows(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        raise RuntimeError(
            f"No rows to write: {path}"
        )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)


def _write_matrix(
    path: Path,
    names: list[str],
    matrix: np.ndarray,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
                "feature",
                *names,
            ]
        )

        for name, row in zip(
            names,
            matrix,
            strict=True,
        ):
            writer.writerow(
                [
                    name,
                    *[
                        (
                            ""
                            if (
                                isinstance(
                                    value,
                                    float,
                                )
                                and not math.isfinite(
                                    value
                                )
                            )
                            else value
                        )
                        for value in row
                    ],
                ]
            )


def export_feature_diagnostics(
    *,
    dataset: Path,
    output_dir: Path,
) -> None:
    rows = load_feature_rows(
        dataset
    )

    summaries = summarize_features(
        rows
    )

    (
        names,
        correlations,
        sample_sizes,
    ) = compute_spearman_matrix(
        rows
    )

    missingness = (
        compute_missingness_patterns(
            rows
        )
    )

    strongest = (
        strongest_correlations(
            names,
            correlations,
        )
    )

    _write_dict_rows(
        output_dir
        / "feature_diagnostics.csv",
        summaries,
    )

    _write_matrix(
        output_dir
        / "feature_spearman.csv",
        names,
        correlations,
    )

    _write_matrix(
        output_dir
        / "feature_pairwise_n.csv",
        names,
        sample_sizes,
    )

    _write_dict_rows(
        output_dir
        / "missingness_patterns.csv",
        missingness,
    )

    if strongest:
        _write_dict_rows(
            output_dir
            / "strong_correlations.csv",
            strongest,
        )
    else:
        path = (
            output_dir
            / "strong_correlations.csv"
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.writer(handle)

            writer.writerow(
                [
                    "feature_a",
                    "feature_b",
                    "spearman_rho",
                    "absolute_rho",
                ]
            )
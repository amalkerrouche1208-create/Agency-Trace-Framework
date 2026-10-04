from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Mapping

import numpy as np


PRIMARY_CLUSTER_FEATURES: tuple[str, ...] = (
    "log_authored_text_chars",
    "ai_share",
    "ai_retention_ratio",
    "human_generation_before_ai_ratio",
    "selections_per_request",
    "log_median_open_to_selection_ms",
    "consultation_burstiness",
    "log_session_duration_ms",
)


SENSITIVITY_FEATURES: dict[
    str,
    tuple[str, ...],
] = {
    "with_consultation_density": (
        *PRIMARY_CLUSTER_FEATURES,
        "consultation_density_per_1000_authored_chars",
    ),
    "with_dismissal_rate": (
        *PRIMARY_CLUSTER_FEATURES,
        "dismissal_rate",
    ),
    "with_direct_adoption": (
        *PRIMARY_CLUSTER_FEATURES,
        "direct_adoption_share",
    ),
}


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


def load_rows(
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


def select_complete_rows(
    rows: list[Mapping[str, object]],
    features: tuple[str, ...],
) -> list[dict[str, object]]:
    selected: list[
        dict[str, object]
    ] = []

    for row in rows:
        values: dict[
            str,
            float,
        ] = {}

        complete = True

        for feature in features:
            value = _optional_float(
                row.get(feature)
            )

            if value is None:
                complete = False
                break

            values[
                feature
            ] = value

        if not complete:
            continue

        selected.append(
            {
                "session_id": str(
                    row["session_id"]
                ),
                **values,
            }
        )

    return selected


def fit_robust_scaler(
    rows: list[Mapping[str, object]],
    features: tuple[str, ...],
) -> dict[
    str,
    dict[str, float],
]:
    if not rows:
        raise ValueError(
            "Cannot fit scaler on empty data."
        )

    parameters: dict[
        str,
        dict[str, float],
    ] = {}

    for feature in features:
        values = np.asarray(
            [
                float(
                    row[feature]
                )
                for row in rows
            ],
            dtype=float,
        )

        median = float(
            np.median(values)
        )

        q1 = float(
            np.quantile(
                values,
                0.25,
            )
        )

        q3 = float(
            np.quantile(
                values,
                0.75,
            )
        )

        iqr = q3 - q1

        parameters[
            feature
        ] = {
            "median": median,
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
        }

    return parameters


def transform_robust(
    rows: list[Mapping[str, object]],
    features: tuple[str, ...],
    parameters: Mapping[
        str,
        Mapping[str, float],
    ],
) -> list[dict[str, object]]:
    transformed: list[
        dict[str, object]
    ] = []

    for row in rows:
        output: dict[
            str,
            object,
        ] = {
            "session_id": (
                row["session_id"]
            ),
        }

        for feature in features:
            value = float(
                row[feature]
            )

            median = float(
                parameters[
                    feature
                ]["median"]
            )

            iqr = float(
                parameters[
                    feature
                ]["iqr"]
            )

            if iqr == 0:
                scaled = (
                    value - median
                )
            else:
                scaled = (
                    value - median
                ) / iqr

            output[
                feature
            ] = scaled

        transformed.append(
            output
        )

    return transformed


def _write_rows(
    path: Path,
    rows: list[Mapping[str, object]],
    features: tuple[str, ...],
) -> None:
    if not rows:
        raise ValueError(
            f"No rows to write: {path}"
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
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "session_id",
                *features,
            ],
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    name: row[name]
                    for name in [
                        "session_id",
                        *features,
                    ]
                }
            )


def export_primary_matrix(
    *,
    dataset: Path,
    output_dir: Path,
) -> None:
    rows = load_rows(
        dataset
    )

    complete = select_complete_rows(
        rows,
        PRIMARY_CLUSTER_FEATURES,
    )

    scaler = fit_robust_scaler(
        complete,
        PRIMARY_CLUSTER_FEATURES,
    )

    scaled = transform_robust(
        complete,
        PRIMARY_CLUSTER_FEATURES,
        scaler,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    _write_rows(
        output_dir
        / "primary_cluster_raw.csv",
        complete,
        PRIMARY_CLUSTER_FEATURES,
    )

    _write_rows(
        output_dir
        / "primary_cluster_scaled.csv",
        scaled,
        PRIMARY_CLUSTER_FEATURES,
    )

    manifest = {
        "source": str(dataset),
        "total_sessions": len(rows),
        "included_sessions": len(
            complete
        ),
        "excluded_sessions": (
            len(rows)
            - len(complete)
        ),
        "coverage": (
            len(complete)
            / len(rows)
            if rows
            else 0.0
        ),
        "feature_count": len(
            PRIMARY_CLUSTER_FEATURES
        ),
        "features": list(
            PRIMARY_CLUSTER_FEATURES
        ),
        "scaling": (
            "median/IQR robust scaling"
        ),
        "scaler_parameters": scaler,
        "sensitivity_feature_sets": {
            name: list(features)
            for name, features
            in SENSITIVITY_FEATURES.items()
        },
    }

    (
        output_dir
        / "primary_cluster_manifest.json"
    ).write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
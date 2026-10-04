from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from sklearn.metrics import (
    adjusted_rand_score,
)

from agencytrace.ml.clustering import (
    fit_labels,
    load_scaled_matrix,
)
from agencytrace.ml.preprocessing import (
    PRIMARY_CLUSTER_FEATURES,
    SENSITIVITY_FEATURES,
)
from agencytrace.ml.robustness import (
    compare_scalings,
    robust_scale,
)


ML_FEATURES = Path(
    "data/processed/"
    "ml_session_features.csv"
)

PRIMARY_RAW = Path(
    "data/analysis/ml/"
    "primary_cluster_raw.csv"
)

PRIMARY_SCALED = Path(
    "data/analysis/ml/"
    "primary_cluster_scaled.csv"
)

ASSIGNMENTS = Path(
    "data/analysis/ml/clustering/"
    "candidate_assignments.csv"
)

OUTPUT_DIR = Path(
    "data/analysis/ml/clustering"
)

RANDOM_STATE = 42


def load_csv(
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


def load_numeric_matrix(
    rows: list[dict[str, str]],
    session_ids: tuple[str, ...],
    features: tuple[str, ...],
) -> np.ndarray:
    """
    Construct an ordered numeric matrix for a fixed set of
    session IDs and feature names.
    """

    by_session = {
        row["session_id"]: row
        for row in rows
    }

    missing_sessions = [
        session_id
        for session_id in session_ids
        if session_id
        not in by_session
    ]

    if missing_sessions:
        raise ValueError(
            f"{len(missing_sessions)} sessions are missing "
            "from the requested feature table."
        )

    matrix = np.asarray(
        [
            [
                float(
                    by_session[
                        session_id
                    ][feature]
                )
                for feature in features
            ]
            for session_id
            in session_ids
        ],
        dtype=float,
    )

    if matrix.ndim != 2:
        raise ValueError(
            "Expected a 2-D numeric matrix."
        )

    if not np.all(
        np.isfinite(matrix)
    ):
        raise ValueError(
            "Sensitivity matrix contains missing or "
            "non-finite values."
        )

    return matrix


def write_rows(
    path: Path,
    rows: list[dict[str, object]],
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
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def main() -> None:
    primary = load_scaled_matrix(
        PRIMARY_SCALED
    )

    raw_primary_rows = load_csv(
        PRIMARY_RAW
    )

    raw_primary = load_numeric_matrix(
        raw_primary_rows,
        primary.session_ids,
        PRIMARY_CLUSTER_FEATURES,
    )

    all_feature_rows = load_csv(
        ML_FEATURES
    )

    assignment_rows = load_csv(
        ASSIGNMENTS
    )

    assignment_by_session = {
        row["session_id"]: row
        for row in assignment_rows
    }

    missing_assignments = [
        session_id
        for session_id
        in primary.session_ids
        if session_id
        not in assignment_by_session
    ]

    if missing_assignments:
        raise RuntimeError(
            f"{len(missing_assignments)} primary sessions "
            "have no candidate clustering assignment."
        )

    scaling_rows: list[
        dict[str, object]
    ] = []

    feature_rows: list[
        dict[str, object]
    ] = []

    algorithm_rows: list[
        dict[str, object]
    ] = []

    for k in (
        2,
        4,
    ):
        reference = np.asarray(
            [
                int(
                    assignment_by_session[
                        session_id
                    ][
                        f"kmeans_k{k}"
                    ]
                )
                for session_id
                in primary.session_ids
            ],
            dtype=int,
        )

        scaling_rows.extend(
            compare_scalings(
                raw_primary,
                reference,
                k=k,
                random_state=(
                    RANDOM_STATE
                ),
            )
        )

        for (
            name,
            features,
        ) in (
            SENSITIVITY_FEATURES.items()
        ):
            matrix = load_numeric_matrix(
                all_feature_rows,
                primary.session_ids,
                features,
            )

            scaled = robust_scale(
                matrix
            )

            labels, _, _ = fit_labels(
                scaled,
                algorithm="kmeans",
                k=k,
                random_state=(
                    RANDOM_STATE
                ),
            )

            ari = adjusted_rand_score(
                reference,
                labels,
            )

            feature_rows.append(
                {
                    "k": k,
                    "feature_set": name,
                    "feature_count": (
                        len(features)
                    ),
                    "ari_vs_primary": float(
                        ari
                    ),
                }
            )

        for algorithm in (
            "ward",
            "gmm",
        ):
            column = (
                f"{algorithm}_k{k}"
            )

            labels = np.asarray(
                [
                    int(
                        assignment_by_session[
                            session_id
                        ][column]
                    )
                    for session_id
                    in primary.session_ids
                ],
                dtype=int,
            )

            ari = adjusted_rand_score(
                reference,
                labels,
            )

            algorithm_rows.append(
                {
                    "k": k,
                    "algorithm": (
                        algorithm
                    ),
                    "ari_vs_kmeans": float(
                        ari
                    ),
                }
            )

    scaling_path = (
        OUTPUT_DIR
        / "scaling_sensitivity.csv"
    )

    feature_path = (
        OUTPUT_DIR
        / "feature_set_sensitivity.csv"
    )

    algorithm_path = (
        OUTPUT_DIR
        / "algorithm_agreement.csv"
    )

    write_rows(
        scaling_path,
        scaling_rows,
    )

    write_rows(
        feature_path,
        feature_rows,
    )

    write_rows(
        algorithm_path,
        algorithm_rows,
    )

    print()
    print("=" * 82)
    print(
        "AgencyTrace — Cluster Sensitivity Analysis"
    )
    print("=" * 82)

    print()
    print("SCALING")
    print("-" * 82)

    for row in scaling_rows:
        print(
            f"k={row['k']} "
            f"{row['scaling']:<12} "
            f"ARI="
            f"{row['ari_vs_primary']:.3f}"
        )

    print()
    print("FEATURE SETS")
    print("-" * 82)

    for row in feature_rows:
        print(
            f"k={row['k']} "
            f"{row['feature_set']:<30} "
            f"ARI="
            f"{row['ari_vs_primary']:.3f}"
        )

    print()
    print("ALGORITHM AGREEMENT")
    print("-" * 82)

    for row in algorithm_rows:
        print(
            f"k={row['k']} "
            f"{row['algorithm']:<8} "
            f"ARI="
            f"{row['ari_vs_kmeans']:.3f}"
        )

    print()
    print("Generated:")
    print(
        f"  {scaling_path}"
    )
    print(
        f"  {feature_path}"
    )
    print(
        f"  {algorithm_path}"
    )

    print("=" * 82)


if __name__ == "__main__":
    main()
from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from agencytrace.ml.clustering import (
    evaluate_candidate,
    fit_pca,
    load_scaled_matrix,
)


INPUT = Path(
    "data/analysis/ml/"
    "primary_cluster_scaled.csv"
)

OUTPUT_DIR = Path(
    "data/analysis/ml/clustering"
)

ALGORITHMS = (
    "kmeans",
    "ward",
    "gmm",
)

K_VALUES = range(
    2,
    9,
)

STABILITY_REPEATS = 40
STABILITY_FRACTION = 0.80
RANDOM_STATE = 42


def main() -> None:
    data = load_scaled_matrix(
        INPUT
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    evaluations = []

    assignments: dict[
        str,
        list[int],
    ] = {}

    print()
    print("=" * 86)
    print(
        "AgencyTrace — Clustering Candidate Evaluation"
    )
    print("=" * 86)

    print(
        f"Sessions                      : "
        f"{len(data.session_ids)}"
    )

    print(
        f"Features                      : "
        f"{len(data.feature_names)}"
    )

    print(
        f"Stability repeats             : "
        f"{STABILITY_REPEATS}"
    )

    print(
        f"Subsample fraction            : "
        f"{STABILITY_FRACTION:.0%}"
    )

    print()

    for algorithm in ALGORITHMS:
        for k in K_VALUES:
            evaluation, labels = (
                evaluate_candidate(
                    data.values,
                    algorithm=algorithm,
                    k=k,
                    stability_repeats=(
                        STABILITY_REPEATS
                    ),
                    stability_fraction=(
                        STABILITY_FRACTION
                    ),
                    random_state=(
                        RANDOM_STATE
                    ),
                )
            )

            evaluations.append(
                asdict(
                    evaluation
                )
            )

            column = (
                f"{algorithm}_k{k}"
            )

            assignments[
                column
            ] = [
                int(label)
                for label in labels
            ]

            print(
                f"{algorithm:<8} "
                f"k={k}  "
                f"sil={evaluation.silhouette:.3f}  "
                f"CH={evaluation.calinski_harabasz:.1f}  "
                f"DB={evaluation.davies_bouldin:.3f}  "
                f"stability={evaluation.stability_ari_mean:.3f}"
            )

    evaluation_path = (
        OUTPUT_DIR
        / "cluster_evaluation.csv"
    )

    with evaluation_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                evaluations[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            evaluations
        )

    assignment_path = (
        OUTPUT_DIR
        / "candidate_assignments.csv"
    )

    with assignment_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        columns = list(
            assignments.keys()
        )

        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "session_id",
                *columns,
            ]
        )

        for index, session_id in enumerate(
            data.session_ids
        ):
            writer.writerow(
                [
                    session_id,
                    *[
                        assignments[
                            column
                        ][index]
                        for column in columns
                    ],
                ]
            )

    pca, scores = fit_pca(
        data.values,
        feature_names=(
            data.feature_names
        ),
    )

    variance_path = (
        OUTPUT_DIR
        / "pca_explained_variance.csv"
    )

    with variance_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "component",
                "explained_variance_ratio",
                "cumulative_variance_ratio",
            ]
        )

        cumulative = 0.0

        for index, ratio in enumerate(
            pca.explained_variance_ratio_,
            start=1,
        ):
            cumulative += float(
                ratio
            )

            writer.writerow(
                [
                    f"PC{index}",
                    float(ratio),
                    cumulative,
                ]
            )

    loading_path = (
        OUTPUT_DIR
        / "pca_loadings.csv"
    )

    with loading_path.open(
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
                *[
                    f"PC{i}"
                    for i
                    in range(
                        1,
                        pca.components_.shape[
                            0
                        ]
                        + 1,
                    )
                ],
            ]
        )

        for feature_index, feature in enumerate(
            data.feature_names
        ):
            writer.writerow(
                [
                    feature,
                    *[
                        float(
                            pca.components_[
                                component_index,
                                feature_index,
                            ]
                        )
                        for component_index
                        in range(
                            pca.components_.shape[
                                0
                            ]
                        )
                    ],
                ]
            )

    score_path = (
        OUTPUT_DIR
        / "pca_scores.csv"
    )

    with score_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "session_id",
                *[
                    f"PC{i}"
                    for i
                    in range(
                        1,
                        scores.shape[1]
                        + 1,
                    )
                ],
            ]
        )

        for session_id, row in zip(
            data.session_ids,
            scores,
            strict=True,
        ):
            writer.writerow(
                [
                    session_id,
                    *[
                        float(value)
                        for value in row
                    ],
                ]
            )

    print()
    print(
        "Generated:"
    )
    print(
        "  cluster_evaluation.csv"
    )
    print(
        "  candidate_assignments.csv"
    )
    print(
        "  pca_explained_variance.csv"
    )
    print(
        "  pca_loadings.csv"
    )
    print(
        "  pca_scores.csv"
    )

    print("=" * 86)


if __name__ == "__main__":
    main()
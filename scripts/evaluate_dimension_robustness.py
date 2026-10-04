from __future__ import annotations

import csv
from pathlib import Path

from agencytrace.ml.dimensionality import (
    bootstrap_pca_stability,
    component_alignment,
    fit_scaled_pca,
    load_numeric_matrix,
    principal_subspace_similarity,
)
from agencytrace.ml.preprocessing import (
    PRIMARY_CLUSTER_FEATURES,
)


INPUT = Path(
    "data/analysis/ml/"
    "primary_cluster_raw.csv"
)

OUTPUT_DIR = Path(
    "data/analysis/ml/"
    "dimensionality"
)

SCALINGS = (
    "robust",
    "standard",
)

COMPARE_COMPONENTS = 4
BOOTSTRAP_COMPONENTS = 4
BOOTSTRAP_REPEATS = 200
RANDOM_STATE = 42


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
    data = load_numeric_matrix(
        INPUT
    )

    if (
        data.feature_names
        != PRIMARY_CLUSTER_FEATURES
    ):
        raise RuntimeError(
            "Primary feature order does not match "
            "the configured clustering feature set."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = {
        scaling: fit_scaled_pca(
            data.values,
            scaling=scaling,
        )
        for scaling in SCALINGS
    }

    variance_rows: list[
        dict[str, object]
    ] = []

    loading_rows: list[
        dict[str, object]
    ] = []

    score_rows: list[
        dict[str, object]
    ] = []

    for scaling in SCALINGS:
        result = results[
            scaling
        ]

        cumulative = 0.0

        for index, ratio in enumerate(
            result.explained_variance_ratio,
            start=1,
        ):
            cumulative += float(
                ratio
            )

            variance_rows.append(
                {
                    "scaling": scaling,
                    "component": (
                        f"PC{index}"
                    ),
                    "explained_variance_ratio": (
                        float(ratio)
                    ),
                    "cumulative_variance_ratio": (
                        cumulative
                    ),
                }
            )

        for component_index in range(
            result.components.shape[
                0
            ]
        ):
            component = (
                f"PC{component_index + 1}"
            )

            for feature_index, feature in enumerate(
                data.feature_names
            ):
                loading = float(
                    result.components[
                        component_index,
                        feature_index,
                    ]
                )

                loading_rows.append(
                    {
                        "scaling": scaling,
                        "component": component,
                        "feature": feature,
                        "loading": loading,
                        "absolute_loading": abs(
                            loading
                        ),
                    }
                )

        for session_index, session_id in enumerate(
            data.session_ids
        ):
            row: dict[
                str,
                object,
            ] = {
                "scaling": scaling,
                "session_id": (
                    session_id
                ),
            }

            for component_index in range(
                result.scores.shape[
                    1
                ]
            ):
                row[
                    f"PC{component_index + 1}"
                ] = float(
                    result.scores[
                        session_index,
                        component_index,
                    ]
                )

            score_rows.append(
                row
            )

    robust = results[
        "robust"
    ]

    standard = results[
        "standard"
    ]

    alignment = (
        component_alignment(
            robust.components,
            standard.components,
            n_components=(
                COMPARE_COMPONENTS
            ),
        )
    )

    alignment_rows = [
        {
            "reference_scaling": (
                "robust"
            ),
            "candidate_scaling": (
                "standard"
            ),
            "reference_component": (
                f"PC{
                    row[
                        'reference_component'
                    ]
                }"
            ),
            "candidate_component": (
                f"PC{
                    row[
                        'candidate_component'
                    ]
                }"
            ),
            "absolute_cosine": (
                row[
                    "absolute_cosine"
                ]
            ),
        }
        for row in alignment
    ]

    scaling_subspace_rows: list[
        dict[str, object]
    ] = []

    for component_count in range(
        1,
        COMPARE_COMPONENTS + 1,
    ):
        similarity = (
            principal_subspace_similarity(
                robust.components,
                standard.components,
                n_components=(
                    component_count
                ),
            )
        )

        scaling_subspace_rows.append(
            {
                "reference_scaling": (
                    "robust"
                ),
                "candidate_scaling": (
                    "standard"
                ),
                "top_components": (
                    component_count
                ),
                **similarity,
            }
        )

    bootstrap_component_rows: list[
        dict[str, object]
    ] = []

    bootstrap_subspace_rows: list[
        dict[str, object]
    ] = []

    for scaling in SCALINGS:
        (
            component_rows,
            subspace_rows,
        ) = bootstrap_pca_stability(
            data.values,
            scaling=scaling,
            n_components=(
                BOOTSTRAP_COMPONENTS
            ),
            repeats=(
                BOOTSTRAP_REPEATS
            ),
            random_state=(
                RANDOM_STATE
            ),
        )

        bootstrap_component_rows.extend(
            component_rows
        )

        bootstrap_subspace_rows.extend(
            subspace_rows
        )

    paths = {
        "variance": (
            OUTPUT_DIR
            / "pca_variance_by_scaling.csv"
        ),
        "loadings": (
            OUTPUT_DIR
            / "pca_loadings_by_scaling.csv"
        ),
        "scores": (
            OUTPUT_DIR
            / "pca_scores_by_scaling.csv"
        ),
        "alignment": (
            OUTPUT_DIR
            / "pca_scaling_component_alignment.csv"
        ),
        "scaling_subspace": (
            OUTPUT_DIR
            / "pca_scaling_subspace_similarity.csv"
        ),
        "bootstrap_components": (
            OUTPUT_DIR
            / "pca_bootstrap_component_stability.csv"
        ),
        "bootstrap_subspaces": (
            OUTPUT_DIR
            / "pca_bootstrap_subspace_stability.csv"
        ),
    }

    write_rows(
        paths["variance"],
        variance_rows,
    )

    write_rows(
        paths["loadings"],
        loading_rows,
    )

    write_rows(
        paths["scores"],
        score_rows,
    )

    write_rows(
        paths["alignment"],
        alignment_rows,
    )

    write_rows(
        paths[
            "scaling_subspace"
        ],
        scaling_subspace_rows,
    )

    write_rows(
        paths[
            "bootstrap_components"
        ],
        bootstrap_component_rows,
    )

    write_rows(
        paths[
            "bootstrap_subspaces"
        ],
        bootstrap_subspace_rows,
    )

    print()
    print("=" * 86)
    print(
        "AgencyTrace — Continuous-Dimension Robustness"
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
        f"Bootstrap repeats             : "
        f"{BOOTSTRAP_REPEATS}"
    )

    print()
    print(
        "EXPLAINED VARIANCE"
    )
    print("-" * 86)

    for scaling in SCALINGS:
        result = results[
            scaling
        ]

        cumulative = 0.0

        print()
        print(
            scaling.upper()
        )

        for index in range(
            COMPARE_COMPONENTS
        ):
            ratio = float(
                result.explained_variance_ratio[
                    index
                ]
            )

            cumulative += ratio

            print(
                f"  PC{index + 1}: "
                f"{ratio:.3f}  "
                f"cumulative="
                f"{cumulative:.3f}"
            )

    print()
    print(
        "ROBUST vs STANDARD COMPONENT ALIGNMENT"
    )
    print("-" * 86)

    for row in alignment_rows:
        print(
            f"  "
            f"{row['reference_component']} "
            f"<-> "
            f"{row['candidate_component']}  "
            f"|cos|="
            f"{float(row['absolute_cosine']):.3f}"
        )

    print()
    print(
        "ROBUST vs STANDARD SUBSPACE AGREEMENT"
    )
    print("-" * 86)

    for row in scaling_subspace_rows:
        print(
            f"  top-{row['top_components']}  "
            f"mean cosine="
            f"{float(row['mean_principal_cosine']):.3f}  "
            f"minimum cosine="
            f"{float(row['min_principal_cosine']):.3f}"
        )

    print()
    print(
        "BOOTSTRAP COMPONENT STABILITY"
    )
    print("-" * 86)

    for row in bootstrap_component_rows:
        print(
            f"  "
            f"{row['scaling']:<8} "
            f"{row['component']:<4} "
            f"mean |cos|="
            f"{float(row['mean_absolute_cosine']):.3f}  "
            f"p05="
            f"{float(row['p05_absolute_cosine']):.3f}"
        )

    print()
    print(
        "BOOTSTRAP SUBSPACE STABILITY"
    )
    print("-" * 86)

    for row in bootstrap_subspace_rows:
        print(
            f"  "
            f"{row['scaling']:<8} "
            f"top-{row['top_components']}  "
            f"mean="
            f"{float(row['mean_of_mean_principal_cosine']):.3f}  "
            f"p05 minimum="
            f"{float(row['p05_min_principal_cosine']):.3f}"
        )

    print()
    print(
        "Generated:"
    )

    for path in paths.values():
        print(
            f"  {path}"
        )

    print("=" * 86)


if __name__ == "__main__":
    main()
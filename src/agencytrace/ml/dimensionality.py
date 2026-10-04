from __future__ import annotations

import csv
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
from typing import Literal

import numpy as np

from sklearn.decomposition import PCA

from agencytrace.ml.robustness import (
    robust_scale,
    standard_scale,
)


Scaling = Literal[
    "robust",
    "standard",
]


@dataclass(frozen=True, slots=True)
class NumericMatrix:
    session_ids: tuple[str, ...]
    feature_names: tuple[str, ...]
    values: np.ndarray


@dataclass(frozen=True, slots=True)
class PCAResult:
    scaling: str
    components: np.ndarray
    explained_variance_ratio: np.ndarray
    scores: np.ndarray
    scaled_values: np.ndarray


def load_numeric_matrix(
    path: Path,
) -> NumericMatrix:
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if (
            reader.fieldnames is None
            or "session_id"
            not in reader.fieldnames
        ):
            raise ValueError(
                "Expected a session_id column."
            )

        feature_names = tuple(
            name
            for name in reader.fieldnames
            if name != "session_id"
        )

        session_ids: list[str] = []
        rows: list[list[float]] = []

        for row in reader:
            session_ids.append(
                row["session_id"]
            )

            rows.append(
                [
                    float(
                        row[feature]
                    )
                    for feature
                    in feature_names
                ]
            )

    values = np.asarray(
        rows,
        dtype=float,
    )

    if values.ndim != 2:
        raise ValueError(
            "Expected a 2-D numeric matrix."
        )

    if len(values) == 0:
        raise ValueError(
            "Matrix contains no rows."
        )

    if not np.all(
        np.isfinite(values)
    ):
        raise ValueError(
            "Matrix contains non-finite values."
        )

    if len(set(session_ids)) != len(
        session_ids
    ):
        raise ValueError(
            "Duplicate session IDs found."
        )

    return NumericMatrix(
        session_ids=tuple(
            session_ids
        ),
        feature_names=(
            feature_names
        ),
        values=values,
    )


def scale_matrix(
    x: np.ndarray,
    *,
    scaling: Scaling,
) -> np.ndarray:
    if scaling == "robust":
        return robust_scale(x)

    if scaling == "standard":
        return standard_scale(x)

    raise ValueError(
        f"Unknown scaling: {scaling}"
    )


def fit_scaled_pca(
    x: np.ndarray,
    *,
    scaling: Scaling,
) -> PCAResult:
    if x.ndim != 2:
        raise ValueError(
            "Expected a 2-D feature matrix."
        )

    if not np.all(
        np.isfinite(x)
    ):
        raise ValueError(
            "Feature matrix contains "
            "non-finite values."
        )

    scaled = scale_matrix(
        x,
        scaling=scaling,
    )

    model = PCA()

    scores = model.fit_transform(
        scaled
    )

    return PCAResult(
        scaling=scaling,
        components=np.asarray(
            model.components_,
            dtype=float,
        ),
        explained_variance_ratio=(
            np.asarray(
                model.explained_variance_ratio_,
                dtype=float,
            )
        ),
        scores=np.asarray(
            scores,
            dtype=float,
        ),
        scaled_values=np.asarray(
            scaled,
            dtype=float,
        ),
    )


def component_alignment(
    reference_components: np.ndarray,
    candidate_components: np.ndarray,
    *,
    n_components: int,
) -> list[dict[str, object]]:
    """
    Align PCA components using maximum absolute cosine
    similarity.

    PCA signs are arbitrary, so absolute cosine similarity
    is used. Component permutations within the retained
    component set are also allowed.
    """

    if (
        reference_components.ndim != 2
        or candidate_components.ndim != 2
    ):
        raise ValueError(
            "Components must be 2-D."
        )

    if (
        reference_components.shape[1]
        != candidate_components.shape[1]
    ):
        raise ValueError(
            "PCA feature dimensions do not match."
        )

    maximum = min(
        reference_components.shape[0],
        candidate_components.shape[0],
    )

    if not (
        1
        <= n_components
        <= maximum
    ):
        raise ValueError(
            "Invalid n_components."
        )

    reference = (
        reference_components[
            :n_components
        ]
    )

    candidate = (
        candidate_components[
            :n_components
        ]
    )

    similarity = np.abs(
        reference
        @ candidate.T
    )

    best_order: tuple[
        int,
        ...,
    ] | None = None

    best_score = (
        float("-inf")
    )

    for order in permutations(
        range(
            n_components
        )
    ):
        score = sum(
            float(
                similarity[
                    index,
                    order[index],
                ]
            )
            for index
            in range(
                n_components
            )
        )

        if score > best_score:
            best_score = score
            best_order = order

    if best_order is None:
        raise RuntimeError(
            "Component alignment failed."
        )

    output: list[
        dict[str, object]
    ] = []

    for reference_index in range(
        n_components
    ):
        candidate_index = (
            best_order[
                reference_index
            ]
        )

        output.append(
            {
                "reference_component": (
                    reference_index
                    + 1
                ),
                "candidate_component": (
                    candidate_index
                    + 1
                ),
                "absolute_cosine": float(
                    similarity[
                        reference_index,
                        candidate_index,
                    ]
                ),
            }
        )

    return output


def principal_subspace_similarity(
    reference_components: np.ndarray,
    candidate_components: np.ndarray,
    *,
    n_components: int,
) -> dict[str, float]:
    """
    Compare two PCA subspaces using principal-angle
    cosines.

    A value near 1 means that the two retained subspaces
    span nearly the same directions even if individual
    components rotate within that subspace.
    """

    if (
        reference_components.ndim != 2
        or candidate_components.ndim != 2
    ):
        raise ValueError(
            "Components must be 2-D."
        )

    if (
        reference_components.shape[1]
        != candidate_components.shape[1]
    ):
        raise ValueError(
            "PCA feature dimensions do not match."
        )

    maximum = min(
        reference_components.shape[0],
        candidate_components.shape[0],
    )

    if not (
        1
        <= n_components
        <= maximum
    ):
        raise ValueError(
            "Invalid n_components."
        )

    cross = (
        reference_components[
            :n_components
        ]
        @ candidate_components[
            :n_components
        ].T
    )

    singular_values = np.linalg.svd(
        cross,
        compute_uv=False,
    )

    cosines = np.clip(
        singular_values,
        0.0,
        1.0,
    )

    return {
        "mean_principal_cosine": float(
            np.mean(cosines)
        ),
        "min_principal_cosine": float(
            np.min(cosines)
        ),
        "max_principal_cosine": float(
            np.max(cosines)
        ),
    }


def bootstrap_pca_stability(
    x: np.ndarray,
    *,
    scaling: Scaling,
    n_components: int = 4,
    repeats: int = 200,
    random_state: int = 42,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """
    Estimate PCA stability through nonparametric bootstrap
    resampling.

    Scaling is refitted inside every bootstrap sample.
    Component stability uses sign- and permutation-invariant
    absolute cosine similarity.

    Subspace stability is also reported because individual
    PCs can rotate when nearby eigenvalues are similar.
    """

    if repeats < 1:
        raise ValueError(
            "repeats must be >= 1."
        )

    if x.ndim != 2:
        raise ValueError(
            "Expected a 2-D feature matrix."
        )

    if not np.all(
        np.isfinite(x)
    ):
        raise ValueError(
            "Feature matrix contains "
            "non-finite values."
        )

    if not (
        1
        <= n_components
        <= x.shape[1]
    ):
        raise ValueError(
            "Invalid n_components."
        )

    reference = fit_scaled_pca(
        x,
        scaling=scaling,
    )

    rng = np.random.default_rng(
        random_state
    )

    component_values: dict[
        int,
        list[float],
    ] = {
        component: []
        for component in range(
            1,
            n_components + 1,
        )
    }

    subspace_mean_values: dict[
        int,
        list[float],
    ] = {
        component_count: []
        for component_count
        in range(
            1,
            n_components + 1,
        )
    }

    subspace_min_values: dict[
        int,
        list[float],
    ] = {
        component_count: []
        for component_count
        in range(
            1,
            n_components + 1,
        )
    }

    n_samples = len(x)

    for _ in range(
        repeats
    ):
        indices = rng.integers(
            0,
            n_samples,
            size=n_samples,
        )

        bootstrap_x = x[
            indices
        ]

        candidate = fit_scaled_pca(
            bootstrap_x,
            scaling=scaling,
        )

        alignment = component_alignment(
            reference.components,
            candidate.components,
            n_components=(
                n_components
            ),
        )

        for row in alignment:
            component = int(
                row[
                    "reference_component"
                ]
            )

            component_values[
                component
            ].append(
                float(
                    row[
                        "absolute_cosine"
                    ]
                )
            )

        for component_count in range(
            1,
            n_components + 1,
        ):
            similarity = (
                principal_subspace_similarity(
                    reference.components,
                    candidate.components,
                    n_components=(
                        component_count
                    ),
                )
            )

            subspace_mean_values[
                component_count
            ].append(
                similarity[
                    "mean_principal_cosine"
                ]
            )

            subspace_min_values[
                component_count
            ].append(
                similarity[
                    "min_principal_cosine"
                ]
            )

    component_rows: list[
        dict[str, object]
    ] = []

    for component in range(
        1,
        n_components + 1,
    ):
        values = np.asarray(
            component_values[
                component
            ],
            dtype=float,
        )

        component_rows.append(
            {
                "scaling": scaling,
                "component": (
                    f"PC{component}"
                ),
                "reference_explained_variance_ratio": (
                    float(
                        reference.explained_variance_ratio[
                            component - 1
                        ]
                    )
                ),
                "mean_absolute_cosine": float(
                    np.mean(values)
                ),
                "median_absolute_cosine": float(
                    np.median(values)
                ),
                "p05_absolute_cosine": float(
                    np.quantile(
                        values,
                        0.05,
                    )
                ),
                "p95_absolute_cosine": float(
                    np.quantile(
                        values,
                        0.95,
                    )
                ),
                "bootstrap_repeats": (
                    repeats
                ),
            }
        )

    subspace_rows: list[
        dict[str, object]
    ] = []

    for component_count in range(
        1,
        n_components + 1,
    ):
        mean_values = np.asarray(
            subspace_mean_values[
                component_count
            ],
            dtype=float,
        )

        min_values = np.asarray(
            subspace_min_values[
                component_count
            ],
            dtype=float,
        )

        subspace_rows.append(
            {
                "scaling": scaling,
                "top_components": (
                    component_count
                ),
                "mean_of_mean_principal_cosine": (
                    float(
                        np.mean(
                            mean_values
                        )
                    )
                ),
                "p05_mean_principal_cosine": (
                    float(
                        np.quantile(
                            mean_values,
                            0.05,
                        )
                    )
                ),
                "mean_min_principal_cosine": (
                    float(
                        np.mean(
                            min_values
                        )
                    )
                ),
                "p05_min_principal_cosine": (
                    float(
                        np.quantile(
                            min_values,
                            0.05,
                        )
                    )
                ),
                "bootstrap_repeats": (
                    repeats
                ),
            }
        )

    return (
        component_rows,
        subspace_rows,
    )
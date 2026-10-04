from __future__ import annotations

import math

import numpy as np

from agencytrace.ml.dimensionality import (
    bootstrap_pca_stability,
    component_alignment,
    fit_scaled_pca,
    principal_subspace_similarity,
)


def test_pca_explained_variance_sums_to_one() -> None:
    rng = np.random.default_rng(
        42
    )

    x = rng.normal(
        size=(100, 4)
    )

    for scaling in (
        "robust",
        "standard",
    ):
        result = fit_scaled_pca(
            x,
            scaling=scaling,
        )

        assert math.isclose(
            float(
                np.sum(
                    result.explained_variance_ratio
                )
            ),
            1.0,
            rel_tol=1e-10,
        )


def test_component_alignment_handles_sign_flip() -> None:
    reference = np.eye(
        3,
        dtype=float,
    )

    candidate = np.asarray(
        [
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, -1.0],
        ]
    )

    rows = component_alignment(
        reference,
        candidate,
        n_components=3,
    )

    assert all(
        math.isclose(
            float(
                row[
                    "absolute_cosine"
                ]
            ),
            1.0,
        )
        for row in rows
    )


def test_component_alignment_handles_permutation() -> None:
    reference = np.eye(
        3,
        dtype=float,
    )

    candidate = np.asarray(
        [
            [0.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )

    rows = component_alignment(
        reference,
        candidate,
        n_components=3,
    )

    assert all(
        math.isclose(
            float(
                row[
                    "absolute_cosine"
                ]
            ),
            1.0,
        )
        for row in rows
    )


def test_subspace_similarity_is_rotation_invariant() -> None:
    reference = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )

    angle = np.pi / 4.0

    candidate = np.asarray(
        [
            [
                np.cos(angle),
                np.sin(angle),
                0.0,
            ],
            [
                -np.sin(angle),
                np.cos(angle),
                0.0,
            ],
            [
                0.0,
                0.0,
                1.0,
            ],
        ]
    )

    result = (
        principal_subspace_similarity(
            reference,
            candidate,
            n_components=2,
        )
    )

    assert math.isclose(
        result[
            "mean_principal_cosine"
        ],
        1.0,
        abs_tol=1e-12,
    )

    assert math.isclose(
        result[
            "min_principal_cosine"
        ],
        1.0,
        abs_tol=1e-12,
    )


def test_bootstrap_stability_returns_expected_rows() -> None:
    rng = np.random.default_rng(
        42
    )

    latent = rng.normal(
        size=(120, 2)
    )

    noise = rng.normal(
        scale=0.1,
        size=(120, 4)
    )

    x = np.column_stack(
        [
            latent[:, 0]
            + noise[:, 0],
            latent[:, 0]
            + noise[:, 1],
            latent[:, 1]
            + noise[:, 2],
            latent[:, 1]
            + noise[:, 3],
        ]
    )

    (
        component_rows,
        subspace_rows,
    ) = bootstrap_pca_stability(
        x,
        scaling="robust",
        n_components=2,
        repeats=5,
        random_state=42,
    )

    assert len(
        component_rows
    ) == 2

    assert len(
        subspace_rows
    ) == 2

    assert all(
        0.0
        <= float(
            row[
                "mean_absolute_cosine"
            ]
        )
        <= 1.0
        for row in component_rows
    )


def test_bootstrap_subspace_values_are_bounded() -> None:
    rng = np.random.default_rng(
        7
    )

    x = rng.normal(
        size=(80, 4)
    )

    (
        _,
        subspace_rows,
    ) = bootstrap_pca_stability(
        x,
        scaling="standard",
        n_components=3,
        repeats=5,
        random_state=7,
    )

    for row in subspace_rows:
        assert (
            0.0
            <= float(
                row[
                    "mean_of_mean_principal_cosine"
                ]
            )
            <= 1.0
        )

        assert (
            0.0
            <= float(
                row[
                    "p05_min_principal_cosine"
                ]
            )
            <= 1.0
        )
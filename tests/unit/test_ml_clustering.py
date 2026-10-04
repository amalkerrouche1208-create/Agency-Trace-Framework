from __future__ import annotations

import math

import numpy as np

from agencytrace.ml.clustering import (
    cluster_sizes,
    evaluate_candidate,
    fit_pca,
)


def _synthetic_matrix() -> np.ndarray:
    rng = np.random.default_rng(
        42
    )

    left = rng.normal(
        loc=-2.0,
        scale=0.25,
        size=(30, 3),
    )

    right = rng.normal(
        loc=2.0,
        scale=0.25,
        size=(30, 3),
    )

    return np.vstack(
        [
            left,
            right,
        ]
    )


def test_cluster_sizes_partition_rows() -> None:
    labels = np.asarray(
        [0, 0, 1, 1, 1]
    )

    sizes = cluster_sizes(
        labels
    )

    assert sizes == {
        0: 2,
        1: 3,
    }

    assert sum(
        sizes.values()
    ) == 5


def test_kmeans_finds_separated_groups() -> None:
    x = _synthetic_matrix()

    evaluation, labels = (
        evaluate_candidate(
            x,
            algorithm="kmeans",
            k=2,
            stability_repeats=3,
            stability_fraction=0.8,
        )
    )

    assert len(labels) == len(x)

    assert (
        evaluation.silhouette
        > 0.70
    )

    assert (
        evaluation.stability_ari_mean
        > 0.90
    )


def test_ward_finds_separated_groups() -> None:
    x = _synthetic_matrix()

    evaluation, _ = (
        evaluate_candidate(
            x,
            algorithm="ward",
            k=2,
            stability_repeats=3,
        )
    )

    assert (
        evaluation.silhouette
        > 0.70
    )


def test_gmm_reports_information_criteria() -> None:
    x = _synthetic_matrix()

    evaluation, _ = (
        evaluate_candidate(
            x,
            algorithm="gmm",
            k=2,
            stability_repeats=3,
        )
    )

    assert (
        evaluation.aic
        is not None
    )

    assert (
        evaluation.bic
        is not None
    )


def test_pca_variance_sums_to_one() -> None:
    x = _synthetic_matrix()

    pca, scores = fit_pca(
        x,
        feature_names=(
            "a",
            "b",
            "c",
        ),
    )

    assert scores.shape == (
        60,
        3,
    )

    assert math.isclose(
        float(
            np.sum(
                pca.explained_variance_ratio_
            )
        ),
        1.0,
        rel_tol=1e-10,
    )
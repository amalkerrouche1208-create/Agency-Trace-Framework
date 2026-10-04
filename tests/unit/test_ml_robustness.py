from __future__ import annotations

import numpy as np

from agencytrace.ml.robustness import (
    compare_scalings,
    evaluate_feature_drop_robustness,
    robust_scale,
    standard_scale,
)


def test_feature_drop_returns_one_result_per_feature() -> None:
    rng = np.random.default_rng(
        42
    )

    left = rng.normal(
        -2.0,
        0.25,
        size=(20, 3),
    )

    right = rng.normal(
        2.0,
        0.25,
        size=(20, 3),
    )

    x = np.vstack(
        [
            left,
            right,
        ]
    )

    results = (
        evaluate_feature_drop_robustness(
            x,
            (
                "a",
                "b",
                "c",
            ),
            k=2,
        )
    )

    assert len(results) == 3

    assert {
        result.removed_feature
        for result in results
    } == {
        "a",
        "b",
        "c",
    }


def test_feature_drop_ari_is_bounded() -> None:
    rng = np.random.default_rng(
        42
    )

    x = rng.normal(
        size=(50, 4)
    )

    results = (
        evaluate_feature_drop_robustness(
            x,
            (
                "a",
                "b",
                "c",
                "d",
            ),
            k=2,
        )
    )

    assert all(
        -1.0
        <= result.ari_vs_primary
        <= 1.0
        for result in results
    )


def test_standard_scaling_centers_columns() -> None:
    x = np.asarray(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
        ],
        dtype=float,
    )

    scaled = standard_scale(
        x
    )

    assert np.allclose(
        np.mean(
            scaled,
            axis=0,
        ),
        0.0,
    )


def test_robust_scaling_centers_medians() -> None:
    x = np.asarray(
        [
            [1.0, 10.0],
            [2.0, 20.0],
            [3.0, 30.0],
        ],
        dtype=float,
    )

    scaled = robust_scale(
        x
    )

    assert np.allclose(
        np.median(
            scaled,
            axis=0,
        ),
        0.0,
    )


def test_standard_scaling_handles_zero_variance() -> None:
    x = np.asarray(
        [
            [2.0, 1.0],
            [2.0, 2.0],
            [2.0, 3.0],
        ],
        dtype=float,
    )

    scaled = standard_scale(
        x
    )

    assert np.all(
        np.isfinite(
            scaled
        )
    )

    assert np.allclose(
        scaled[:, 0],
        0.0,
    )


def test_robust_scaling_handles_zero_iqr() -> None:
    x = np.asarray(
        [
            [2.0, 1.0],
            [2.0, 2.0],
            [2.0, 3.0],
        ],
        dtype=float,
    )

    scaled = robust_scale(
        x
    )

    assert np.all(
        np.isfinite(
            scaled
        )
    )

    assert np.allclose(
        scaled[:, 0],
        0.0,
    )


def test_compare_scalings_returns_both_variants() -> None:
    rng = np.random.default_rng(
        42
    )

    left = rng.normal(
        -2.0,
        0.25,
        size=(30, 3),
    )

    right = rng.normal(
        2.0,
        0.25,
        size=(30, 3),
    )

    x = np.vstack(
        [
            left,
            right,
        ]
    )

    reference = np.asarray(
        [
            *([0] * 30),
            *([1] * 30),
        ],
        dtype=int,
    )

    results = compare_scalings(
        x,
        reference,
        k=2,
    )

    assert {
        row["scaling"]
        for row in results
    } == {
        "robust",
        "standard",
    }

    assert all(
        -1.0
        <= float(
            row[
                "ari_vs_primary"
            ]
        )
        <= 1.0
        for row in results
    )
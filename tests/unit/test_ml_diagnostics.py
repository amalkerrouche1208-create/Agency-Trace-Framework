from __future__ import annotations

import math

import numpy as np

from agencytrace.ml.diagnostics import (
    _spearman,
    compute_missingness_patterns,
    summarize_features,
)


def test_spearman_perfect_positive() -> None:
    x = np.asarray(
        [1.0, 2.0, 3.0, 4.0]
    )

    y = np.asarray(
        [10.0, 20.0, 30.0, 40.0]
    )

    assert math.isclose(
        _spearman(x, y),
        1.0,
    )


def test_spearman_perfect_negative() -> None:
    x = np.asarray(
        [1.0, 2.0, 3.0, 4.0]
    )

    y = np.asarray(
        [40.0, 30.0, 20.0, 10.0]
    )

    assert math.isclose(
        _spearman(x, y),
        -1.0,
    )


def test_feature_summary_preserves_missingness() -> None:
    rows = [
        {
            "ai_share": "0.1",
        },
        {
            "ai_share": "",
        },
        {
            "ai_share": "0.3",
        },
    ]

    summary = summarize_features(
        rows,
        features=(
            "ai_share",
        ),
    )[0]

    assert (
        summary["n_total"]
        == 3
    )

    assert (
        summary["n_observed"]
        == 2
    )

    assert (
        summary["n_missing"]
        == 1
    )

    assert math.isclose(
        float(
            summary[
                "missing_fraction"
            ]
        ),
        1 / 3,
    )


def test_missingness_patterns() -> None:
    rows = [
        {
            "a": "1",
            "b": "2",
        },
        {
            "a": "",
            "b": "2",
        },
        {
            "a": "",
            "b": "",
        },
    ]

    patterns = (
        compute_missingness_patterns(
            rows,
            features=(
                "a",
                "b",
            ),
        )
    )

    assert sum(
        int(row["sessions"])
        for row in patterns
    ) == 3
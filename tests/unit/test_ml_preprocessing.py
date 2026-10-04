from __future__ import annotations

import math

from agencytrace.ml.preprocessing import (
    fit_robust_scaler,
    select_complete_rows,
    transform_robust,
)


FEATURES = (
    "a",
    "b",
)


def test_complete_case_selection() -> None:
    rows = [
        {
            "session_id": "1",
            "a": "1",
            "b": "2",
        },
        {
            "session_id": "2",
            "a": "",
            "b": "3",
        },
        {
            "session_id": "3",
            "a": "4",
            "b": "5",
        },
    ]

    selected = (
        select_complete_rows(
            rows,
            FEATURES,
        )
    )

    assert len(selected) == 2

    assert [
        row["session_id"]
        for row in selected
    ] == [
        "1",
        "3",
    ]


def test_robust_scaling_centers_median() -> None:
    rows = [
        {
            "session_id": "1",
            "a": 1.0,
        },
        {
            "session_id": "2",
            "a": 2.0,
        },
        {
            "session_id": "3",
            "a": 3.0,
        },
    ]

    features = (
        "a",
    )

    parameters = (
        fit_robust_scaler(
            rows,
            features,
        )
    )

    scaled = transform_robust(
        rows,
        features,
        parameters,
    )

    assert math.isclose(
        float(
            scaled[1]["a"]
        ),
        0.0,
        abs_tol=1e-12,
    )


def test_zero_iqr_is_safe() -> None:
    rows = [
        {
            "session_id": "1",
            "a": 2.0,
        },
        {
            "session_id": "2",
            "a": 2.0,
        },
        {
            "session_id": "3",
            "a": 2.0,
        },
    ]

    features = (
        "a",
    )

    parameters = (
        fit_robust_scaler(
            rows,
            features,
        )
    )

    scaled = transform_robust(
        rows,
        features,
        parameters,
    )

    assert all(
        math.isclose(
            float(row["a"]),
            0.0,
        )
        for row in scaled
    )
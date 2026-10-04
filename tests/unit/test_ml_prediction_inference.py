from __future__ import annotations

import math

import numpy as np

from agencytrace.ml.prediction_inference import (
    PredictionRecord,
    binary_metrics,
    bootstrap_model_improvement,
)


def test_binary_metrics_perfect_prediction() -> None:
    actual = np.asarray(
        [
            0,
            0,
            1,
            1,
        ]
    )

    predicted = actual.copy()

    probability = np.asarray(
        [
            0.05,
            0.10,
            0.90,
            0.95,
        ]
    )

    metrics = binary_metrics(
        actual,
        predicted,
        probability,
    )

    assert metrics is not None

    assert math.isclose(
        metrics[
            "roc_auc"
        ],
        1.0,
    )

    assert math.isclose(
        metrics[
            "average_precision"
        ],
        1.0,
    )

    assert math.isclose(
        metrics[
            "balanced_accuracy"
        ],
        1.0,
    )


def make_rows() -> list[
    PredictionRecord
]:
    rows: list[
        PredictionRecord
    ] = []

    for session_index in range(
        20
    ):
        session_id = (
            f"s{session_index}"
        )

        for selection_index in range(
            2
        ):
            actual = (
                (
                    session_index
                    + selection_index
                )
                % 2
            )

            selection_id = (
                f"x{selection_index}"
            )

            rows.append(
                PredictionRecord(
                    task="test_task",
                    model=(
                        "prior_baseline"
                    ),
                    session_id=(
                        session_id
                    ),
                    selection_id=(
                        selection_id
                    ),
                    actual=actual,
                    predicted=1,
                    positive_probability=(
                        0.5
                    ),
                )
            )

            rows.append(
                PredictionRecord(
                    task="test_task",
                    model="candidate",
                    session_id=(
                        session_id
                    ),
                    selection_id=(
                        selection_id
                    ),
                    actual=actual,
                    predicted=actual,
                    positive_probability=(
                        0.9
                        if actual == 1
                        else 0.1
                    ),
                )
            )

    return rows


def test_bootstrap_detects_better_candidate() -> None:
    rows = make_rows()

    results = (
        bootstrap_model_improvement(
            rows,
            task="test_task",
            candidate_model="candidate",
            repeats=50,
            random_state=42,
        )
    )

    by_metric = {
        str(
            row["metric"]
        ): row
        for row in results
    }

    assert (
        float(
            by_metric[
                "roc_auc"
            ][
                "observed_improvement"
            ]
        )
        > 0
    )

    assert (
        float(
            by_metric[
                "average_precision"
            ][
                "observed_improvement"
            ]
        )
        > 0
    )

    assert (
        float(
            by_metric[
                "balanced_accuracy"
            ][
                "observed_improvement"
            ]
        )
        > 0
    )


def test_brier_improvement_uses_lower_is_better() -> None:
    rows = make_rows()

    results = (
        bootstrap_model_improvement(
            rows,
            task="test_task",
            candidate_model="candidate",
            repeats=20,
            random_state=7,
        )
    )

    brier = next(
        row
        for row in results
        if row[
            "metric"
        ] == "brier_score"
    )

    assert (
        float(
            brier[
                "observed_improvement"
            ]
        )
        > 0
    )


def test_model_alignment_requires_same_observations() -> None:
    rows = make_rows()

    rows = [
        row
        for row in rows
        if not (
            row.model
            == "candidate"
            and row.session_id
            == "s0"
            and row.selection_id
            == "x0"
        )
    ]

    try:
        bootstrap_model_improvement(
            rows,
            task="test_task",
            candidate_model="candidate",
            repeats=5,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected alignment failure."
        )
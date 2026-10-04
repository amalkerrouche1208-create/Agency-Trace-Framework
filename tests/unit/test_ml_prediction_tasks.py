from __future__ import annotations

import numpy as np

from agencytrace.ml.prediction import (
    FEATURE_NAMES,
    InsertionRecord,
    build_prediction_rows,
)
from agencytrace.ml.prediction_tasks import (
    DIRECT_VS_MODIFIED,
    NON_ADOPTION_DETECTION,
    build_binary_dataset,
    grouped_cv_permutation_importance,
    logistic_coefficient_stability,
    task_split_audit,
)


def record(
    session: str,
    selection: str,
    event: int,
    outcome: str,
    *,
    inserted_chars: int = 50,
) -> InsertionRecord:
    return InsertionRecord(
        session_id=session,
        request_id=(
            f"r-{selection}"
        ),
        selection_id=selection,
        request_event_num=(
            event - 1
        ),
        selection_event_num=event,
        selected_index=0,
        inserted_chars=(
            inserted_chars
        ),
        request_to_selection_ms=(
            5000.0
        ),
        open_to_selection_ms=(
            3000.0
        ),
        adoption_outcome=outcome,
    )


# =====================================================================
# Binary task construction
# =====================================================================


def test_direct_vs_modified_excludes_non_adoption() -> None:
    rows = build_prediction_rows(
        [
            record(
                "s1",
                "a",
                10,
                "direct_adoption",
            ),
            record(
                "s1",
                "b",
                20,
                "modified_adoption",
            ),
            record(
                "s1",
                "c",
                30,
                "non_adoption",
            ),
        ]
    )

    (
        x,
        y,
        _,
        selected,
    ) = build_binary_dataset(
        rows,
        task=(
            DIRECT_VS_MODIFIED
        ),
    )

    assert len(
        selected
    ) == 2

    assert x.shape[0] == 2

    assert set(
        y.tolist()
    ) == {
        0,
        1,
    }


def test_non_adoption_detection_uses_all_rows() -> None:
    rows = build_prediction_rows(
        [
            record(
                "s1",
                "a",
                10,
                "direct_adoption",
            ),
            record(
                "s1",
                "b",
                20,
                "modified_adoption",
            ),
            record(
                "s1",
                "c",
                30,
                "non_adoption",
            ),
        ]
    )

    (
        _,
        y,
        _,
        selected,
    ) = build_binary_dataset(
        rows,
        task=(
            NON_ADOPTION_DETECTION
        ),
    )

    assert len(
        selected
    ) == 3

    assert int(
        y.sum()
    ) == 1


def test_binary_grouped_cv_has_no_overlap() -> None:
    outcomes = (
        "direct_adoption",
        "modified_adoption",
        "non_adoption",
    )

    records = []

    for session_index in range(
        30
    ):
        for selection_index in range(
            3
        ):
            records.append(
                record(
                    (
                        f"s"
                        f"{session_index}"
                    ),
                    (
                        f"x"
                        f"{selection_index}"
                    ),
                    (
                        10
                        + selection_index
                    ),
                    outcomes[
                        (
                            session_index
                            + selection_index
                        )
                        % 3
                    ],
                )
            )

    rows = build_prediction_rows(
        records
    )

    for task in (
        DIRECT_VS_MODIFIED,
        NON_ADOPTION_DETECTION,
    ):
        audit = task_split_audit(
            rows,
            task=task,
            n_splits=5,
            random_state=42,
        )

        assert all(
            int(
                row[
                    "session_overlap"
                ]
            )
            == 0
            for row in audit
        )


def test_binary_labels_are_zero_one() -> None:
    rows = build_prediction_rows(
        [
            record(
                "s1",
                "a",
                10,
                "direct_adoption",
            ),
            record(
                "s2",
                "b",
                10,
                "modified_adoption",
            ),
            record(
                "s3",
                "c",
                10,
                "non_adoption",
            ),
        ]
    )

    for task in (
        DIRECT_VS_MODIFIED,
        NON_ADOPTION_DETECTION,
    ):
        _, y, _, _ = (
            build_binary_dataset(
                rows,
                task=task,
            )
        )

        assert set(
            np.unique(
                y
            )
        ).issubset(
            {
                0,
                1,
            }
        )


# =====================================================================
# Predictive explanation
# =====================================================================


def synthetic_signal_rows():
    records = []

    for index in range(
        60
    ):
        if index % 2 == 0:
            outcome = (
                "modified_adoption"
            )

            inserted_chars = 20

        else:
            outcome = (
                "direct_adoption"
            )

            inserted_chars = 200

        records.append(
            record(
                f"s{index}",
                f"x{index}",
                10,
                outcome,
                inserted_chars=(
                    inserted_chars
                ),
            )
        )

    return build_prediction_rows(
        records
    )


def test_permutation_importance_returns_all_features() -> None:
    rows = synthetic_signal_rows()

    summary, folds = (
        grouped_cv_permutation_importance(
            rows,
            task=(
                DIRECT_VS_MODIFIED
            ),
            model_name="logistic",
            n_splits=5,
            permutation_repeats=3,
            random_state=42,
        )
    )

    assert len(
        summary
    ) == (
        len(
            FEATURE_NAMES
        )
        * 2
    )

    assert len(
        folds
    ) == (
        len(
            FEATURE_NAMES
        )
        * 2
        * 5
    )


def test_known_signal_has_positive_importance() -> None:
    rows = synthetic_signal_rows()

    summary, _ = (
        grouped_cv_permutation_importance(
            rows,
            task=(
                DIRECT_VS_MODIFIED
            ),
            model_name="logistic",
            n_splits=5,
            permutation_repeats=5,
            random_state=42,
        )
    )

    signal = next(
        row
        for row in summary
        if (
            row[
                "metric"
            ] == "roc_auc"
            and row[
                "feature"
            ] == "log_inserted_chars"
        )
    )

    assert (
        float(
            signal[
                "mean_importance"
            ]
        )
        > 0
    )


def test_logistic_summary_contains_all_features() -> None:
    rows = synthetic_signal_rows()

    summary, folds = (
        logistic_coefficient_stability(
            rows,
            task=(
                DIRECT_VS_MODIFIED
            ),
            model_names=(
                "logistic",
            ),
            n_splits=5,
            random_state=42,
        )
    )

    assert len(
        summary
    ) == len(
        FEATURE_NAMES
    )

    assert len(
        folds
    ) == (
        len(
            FEATURE_NAMES
        )
        * 5
    )


def test_known_signal_coefficient_points_to_direct() -> None:
    rows = synthetic_signal_rows()

    summary, _ = (
        logistic_coefficient_stability(
            rows,
            task=(
                DIRECT_VS_MODIFIED
            ),
            model_names=(
                "logistic",
            ),
            n_splits=5,
            random_state=42,
        )
    )

    signal = next(
        row
        for row in summary
        if row[
            "feature"
        ] == "log_inserted_chars"
    )

    assert (
        float(
            signal[
                "mean_standardized_coefficient"
            ]
        )
        > 0
    )

    assert (
        float(
            signal[
                "sign_consistency"
            ]
        )
        == 1.0
    )

    assert (
        signal[
            "direction"
        ]
        == "direct_adoption"
    )
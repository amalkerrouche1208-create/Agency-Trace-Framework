from __future__ import annotations

from agencytrace.ml.prediction import (
    FEATURE_NAMES,
    InsertionRecord,
    build_prediction_rows,
    grouped_split_audit,
    rows_to_arrays,
)


def record(
    session: str,
    selection: str,
    event: int,
    outcome: str,
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
        inserted_chars=50,
        request_to_selection_ms=(
            5000.0
        ),
        open_to_selection_ms=(
            3000.0
        ),
        adoption_outcome=outcome,
    )


def test_prediction_features_have_expected_width() -> None:
    rows = build_prediction_rows(
        [
            record(
                "s1",
                "a",
                10,
                "direct_adoption",
            ),
        ]
    )

    assert len(rows) == 1

    assert len(
        rows[0].features
    ) == len(
        FEATURE_NAMES
    )

    assert len(
        FEATURE_NAMES
    ) == 9


def test_prediction_features_exclude_future_and_redundant_metrics() -> None:
    forbidden = {
        "ai_share",
        "ai_retention_ratio",
        "deletion_ratio",
        "surviving_chars",
        "adoption_outcome",
        "session_duration_ms",
        "log_prior_selection_count",
        "open_latency_missing",
    }

    assert not (
        forbidden
        & set(
            FEATURE_NAMES
        )
    )

    assert (
        "log_selection_ordinal"
        in FEATURE_NAMES
    )

    assert (
        "log_open_to_selection_ms"
        in FEATURE_NAMES
    )


def test_rows_to_arrays_preserve_sessions() -> None:
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
        ]
    )

    x, y, groups = (
        rows_to_arrays(
            rows
        )
    )

    assert x.shape == (
        2,
        len(
            FEATURE_NAMES
        ),
    )

    assert y.shape == (
        2,
    )

    assert set(
        groups
    ) == {
        "s1",
        "s2",
    }


def test_grouped_cv_has_no_session_overlap() -> None:
    records = []

    outcomes = (
        "direct_adoption",
        "modified_adoption",
        "non_adoption",
    )

    for session_index in range(
        30
    ):
        session = (
            f"s{session_index}"
        )

        for selection_index in range(
            3
        ):
            records.append(
                record(
                    session,
                    (
                        f"x{selection_index}"
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
                        % len(
                            outcomes
                        )
                    ],
                )
            )

    rows = (
        build_prediction_rows(
            records
        )
    )

    audit = (
        grouped_split_audit(
            rows,
            n_splits=5,
            random_state=42,
        )
    )

    assert len(
        audit
    ) == 5

    assert all(
        int(
            row[
                "session_overlap"
            ]
        )
        == 0
        for row in audit
    )
from __future__ import annotations

import math

import numpy as np

from agencytrace.ml.transitions import (
    SelectionRecord,
    bootstrap_transition_probabilities,
    build_sequences,
    build_session_transition_metrics,
    endpoint_matrix,
    positional_outcome_profile,
    row_probability_matrix,
    transition_count_matrix,
)


def record(
    session: str,
    request: str,
    selection: str,
    event: int,
    outcome: str,
) -> SelectionRecord:
    return SelectionRecord(
        session_id=session,
        request_id=request,
        selection_id=selection,
        request_event_num=(
            event - 1
        ),
        selection_event_num=event,
        adoption_outcome=outcome,
    )


def test_sequence_ordering() -> None:
    records = [
        record(
            "s1",
            "r2",
            "b",
            20,
            "modified_adoption",
        ),
        record(
            "s1",
            "r1",
            "a",
            10,
            "direct_adoption",
        ),
    ]

    sequences = build_sequences(
        records,
        (
            "s1",
        ),
    )

    assert [
        item.selection_id
        for item
        in sequences["s1"]
    ] == [
        "a",
        "b",
    ]


def test_cross_request_excludes_same_request_transition() -> None:
    records = [
        record(
            "s1",
            "r1",
            "a",
            10,
            "direct_adoption",
        ),
        record(
            "s1",
            "r1",
            "b",
            11,
            "modified_adoption",
        ),
        record(
            "s1",
            "r2",
            "c",
            20,
            "direct_adoption",
        ),
    ]

    sequences = build_sequences(
        records,
        (
            "s1",
        ),
    )

    all_counts = (
        transition_count_matrix(
            sequences,
            scope="all",
        )
    )

    cross_counts = (
        transition_count_matrix(
            sequences,
            scope="cross_request",
        )
    )

    assert int(
        all_counts.sum()
    ) == 2

    assert int(
        cross_counts.sum()
    ) == 1


def test_transition_probabilities_sum_to_one() -> None:
    counts = np.asarray(
        [
            [2, 1, 1],
            [1, 2, 1],
            [0, 1, 1],
        ],
        dtype=int,
    )

    probabilities = (
        row_probability_matrix(
            counts
        )
    )

    assert np.allclose(
        np.sum(
            probabilities,
            axis=1,
        ),
        1.0,
    )


def test_session_metrics_include_zero_selection_sessions() -> None:
    records = [
        record(
            "s1",
            "r1",
            "a",
            10,
            "direct_adoption",
        ),
    ]

    sequences = build_sequences(
        records,
        (
            "s1",
            "s2",
        ),
    )

    rows = (
        build_session_transition_metrics(
            sequences
        )
    )

    by_session = {
        row["session_id"]: row
        for row in rows
    }

    assert (
        by_session[
            "s1"
        ][
            "selection_count"
        ]
        == 1
    )

    assert (
        by_session[
            "s2"
        ][
            "selection_count"
        ]
        == 0
    )

    assert (
        by_session[
            "s2"
        ][
            "all_self_transition_rate"
        ]
        is None
    )


def test_endpoint_matrix_uses_first_and_last_outcomes() -> None:
    records = [
        record(
            "s1",
            "r1",
            "a",
            10,
            "direct_adoption",
        ),
        record(
            "s1",
            "r2",
            "b",
            20,
            "modified_adoption",
        ),
        record(
            "s1",
            "r3",
            "c",
            30,
            "non_adoption",
        ),
    ]

    sequences = build_sequences(
        records,
        (
            "s1",
        ),
    )

    counts, _, eligible = (
        endpoint_matrix(
            sequences
        )
    )

    assert eligible == 1

    assert int(
        counts[
            0,
            2,
        ]
    ) == 1


def test_positional_profile_counts_all_eligible_selections() -> None:
    records = [
        record(
            "s1",
            "r1",
            "a",
            10,
            "direct_adoption",
        ),
        record(
            "s1",
            "r2",
            "b",
            20,
            "modified_adoption",
        ),
        record(
            "s1",
            "r3",
            "c",
            30,
            "direct_adoption",
        ),
    ]

    sequences = build_sequences(
        records,
        (
            "s1",
        ),
    )

    rows = (
        positional_outcome_profile(
            sequences
        )
    )

    assert sum(
        int(
            row["count"]
        )
        for row in rows
    ) == 3


def test_bootstrap_probabilities_are_bounded() -> None:
    records = [
        record(
            "s1",
            "r1",
            "a",
            10,
            "direct_adoption",
        ),
        record(
            "s1",
            "r2",
            "b",
            20,
            "direct_adoption",
        ),
        record(
            "s2",
            "r1",
            "c",
            10,
            "modified_adoption",
        ),
        record(
            "s2",
            "r2",
            "d",
            20,
            "direct_adoption",
        ),
    ]

    sequences = build_sequences(
        records,
        (
            "s1",
            "s2",
        ),
    )

    rows = (
        bootstrap_transition_probabilities(
            sequences,
            scope="cross_request",
            repeats=10,
            random_state=42,
        )
    )

    for row in rows:
        probability = row[
            "probability"
        ]

        if probability is not None:
            assert (
                0.0
                <= float(
                    probability
                )
                <= 1.0
            )

        lower = row[
            "ci_2_5"
        ]

        upper = row[
            "ci_97_5"
        ]

        if (
            lower is not None
            and upper is not None
        ):
            assert (
                0.0
                <= float(lower)
                <= float(upper)
                <= 1.0
            )


def test_state_entropy_for_constant_sequence_is_zero() -> None:
    records = [
        record(
            "s1",
            "r1",
            "a",
            10,
            "direct_adoption",
        ),
        record(
            "s1",
            "r2",
            "b",
            20,
            "direct_adoption",
        ),
        record(
            "s1",
            "r3",
            "c",
            30,
            "direct_adoption",
        ),
    ]

    sequences = build_sequences(
        records,
        (
            "s1",
        ),
    )

    row = (
        build_session_transition_metrics(
            sequences
        )[0]
    )

    assert math.isclose(
        float(
            row[
                "state_entropy_normalized"
            ]
        ),
        0.0,
    )
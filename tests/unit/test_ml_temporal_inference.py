from __future__ import annotations

import math

from agencytrace.ml.temporal_inference import (
    _benjamini_hochberg,
    early_late_change,
    permutation_transition_test,
    session_weighted_phase_rows,
)
from agencytrace.ml.transitions import (
    SelectionRecord,
    build_sequences,
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


def test_bh_adjustment_is_bounded() -> None:
    adjusted = (
        _benjamini_hochberg(
            [
                0.01,
                0.03,
                0.20,
            ]
        )
    )

    assert len(adjusted) == 3

    assert all(
        0.0
        <= value
        <= 1.0
        for value in adjusted
    )


def test_session_weighted_phases_preserve_sessions() -> None:
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
        session_weighted_phase_rows(
            sequences
        )
    )

    phases = {
        str(
            row["phase"]
        )
        for row in rows
    }

    assert "early" in phases
    assert "late" in phases


def test_early_late_change_is_session_weighted() -> None:
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
            "s2",
            "r1",
            "c",
            10,
            "direct_adoption",
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

    phase_rows = (
        session_weighted_phase_rows(
            sequences
        )
    )

    results = early_late_change(
        phase_rows,
        bootstrap_repeats=20,
        random_state=42,
    )

    by_state = {
        str(
            row["outcome"]
        ): row
        for row in results
    }

    assert math.isclose(
        float(
            by_state[
                "direct_adoption"
            ][
                "mean_late_minus_early"
            ]
        ),
        -0.5,
    )

    assert math.isclose(
        float(
            by_state[
                "modified_adoption"
            ][
                "mean_late_minus_early"
            ]
        ),
        0.5,
    )


def test_permutation_transition_test_returns_nine_cells() -> None:
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
            "modified_adoption",
        ),
        record(
            "s2",
            "r1",
            "d",
            10,
            "modified_adoption",
        ),
        record(
            "s2",
            "r2",
            "e",
            20,
            "non_adoption",
        ),
        record(
            "s2",
            "r3",
            "f",
            30,
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

    rows, summary = (
        permutation_transition_test(
            sequences,
            repeats=20,
            random_state=42,
        )
    )

    assert len(rows) == 9

    assert (
        0.0
        <= float(
            summary[
                "observed_self_transition_rate"
            ]
        )
        <= 1.0
    )

    assert all(
        0.0
        <= float(
            row[
                "fdr_q"
            ]
        )
        <= 1.0
        for row in rows
    )
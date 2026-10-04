from __future__ import annotations

import math

from agencytrace.ml.features import (
    BEHAVIORAL_FEATURES,
    PROFILE_FEATURES,
    build_session_features,
)


def _sample_row() -> dict[str, str]:
    return {
        "session_id": "test-session",

        "authored_text_chars": "1000",
        "ai_share": "0.25",

        "ai_inserted_chars": "100",
        "ai_surviving_chars": "90",

        "human_generation_before_ai_ratio": "0.40",

        "suggestion_requests": "10",
        "suggestion_selections": "5",
        "dismissed_episodes": "4",
        "suggestion_reopens": "2",
        "multi_selection_episodes": "1",

        "consultation_density_per_1000_authored_chars": "10",

        "median_request_to_selection_ms": "1000",
        "median_open_to_selection_ms": "800",
        "consultation_burstiness": "-0.20",
        "session_duration_ms": "600000",

        "direct_adoptions": "3",
        "modified_adoptions": "2",
    }


def test_build_session_features() -> None:
    features = build_session_features(
        _sample_row()
    )

    assert (
        features["session_id"]
        == "test-session"
    )

    assert math.isclose(
        features["ai_retention_ratio"],
        0.9,
    )

    assert math.isclose(
        features["selections_per_request"],
        0.5,
    )

    assert math.isclose(
        features["dismissal_rate"],
        0.4,
    )

    assert math.isclose(
        features["reopen_rate"],
        0.2,
    )

    assert math.isclose(
        features["multi_selection_rate"],
        0.1,
    )

    assert math.isclose(
        features["direct_adoption_share"],
        0.6,
    )

    assert math.isclose(
        features["modified_adoption_share"],
        0.4,
    )

    assert (
        features["behavioral_complete"]
        == 1
    )

    assert (
        features["profile_complete"]
        == 1
    )


def test_feature_sets_do_not_duplicate_names() -> None:
    assert (
        len(BEHAVIORAL_FEATURES)
        == len(set(BEHAVIORAL_FEATURES))
    )

    assert (
        len(PROFILE_FEATURES)
        == len(set(PROFILE_FEATURES))
    )


def test_missing_ai_insertion_preserves_missing_retention() -> None:
    row = _sample_row()

    row["ai_inserted_chars"] = "0"
    row["ai_surviving_chars"] = "0"

    features = build_session_features(
        row
    )

    assert (
        features["ai_retention_ratio"]
        is None
    )

    assert (
        features["behavioral_complete"]
        == 0
    )


def test_missing_timing_is_preserved() -> None:
    row = _sample_row()

    row[
        "median_request_to_selection_ms"
    ] = ""

    features = build_session_features(
        row
    )

    assert (
        features[
            "log_median_request_to_selection_ms"
        ]
        is None
    )

    assert (
        features["behavioral_complete"]
        == 0
    )


def test_zero_requests_produces_undefined_request_rates() -> None:
    row = _sample_row()

    row["suggestion_requests"] = "0"
    row["suggestion_selections"] = "0"
    row["dismissed_episodes"] = "0"
    row["suggestion_reopens"] = "0"
    row["multi_selection_episodes"] = "0"
    row["direct_adoptions"] = "0"
    row["modified_adoptions"] = "0"

    features = build_session_features(
        row
    )

    assert (
        features["selections_per_request"]
        is None
    )

    assert (
        features["dismissal_rate"]
        is None
    )

    assert (
        features["reopen_rate"]
        is None
    )

    assert (
        features["multi_selection_rate"]
        is None
    )

    assert (
        features["direct_adoption_share"]
        is None
    )

    assert (
        features["modified_adoption_share"]
        is None
    )


def test_selections_per_request_can_exceed_one() -> None:
    row = _sample_row()

    row["suggestion_requests"] = "4"
    row["suggestion_selections"] = "5"

    features = build_session_features(
        row
    )

    assert math.isclose(
        features["selections_per_request"],
        1.25,
    )
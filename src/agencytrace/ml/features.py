from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    name: str
    source: str
    family: str
    description: str
    transform: str = "identity"
    leakage_role: str = "predictor"


BEHAVIORAL_FEATURES: tuple[str, ...] = (
    "log_authored_text_chars",
    "ai_share",
    "ai_retention_ratio",
    "human_generation_before_ai_ratio",
    "selections_per_request",
    "dismissal_rate",
    "reopen_rate",
    "multi_selection_rate",
    "consultation_density_per_1000_authored_chars",
    "log_median_request_to_selection_ms",
    "log_median_open_to_selection_ms",
    "consultation_burstiness",
    "log_session_duration_ms",
)


PROFILE_FEATURES: tuple[str, ...] = (
    *BEHAVIORAL_FEATURES,
    "direct_adoption_share",
    "modified_adoption_share",
)


FEATURE_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        name="log_authored_text_chars",
        source="authored_text_chars",
        family="scale",
        description=(
            "Natural-log-transformed final authored-text length. "
            "Initial/system text is excluded."
        ),
        transform="log1p",
    ),
    FeatureSpec(
        name="ai_share",
        source="ai_share",
        family="authorship",
        description=(
            "Final AI-origin share of authored text."
        ),
    ),
    FeatureSpec(
        name="ai_retention_ratio",
        source=(
            "ai_surviving_chars/ai_inserted_chars"
        ),
        family="retention",
        description=(
            "Fraction of inserted AI-origin characters surviving "
            "in the reconstructed final document. Undefined when "
            "no AI characters were inserted."
        ),
    ),
    FeatureSpec(
        name="human_generation_before_ai_ratio",
        source="human_generation_before_ai_ratio",
        family="authorship",
        description=(
            "Proportion of human inserted text generated before "
            "the first confirmed AI insertion."
        ),
    ),
    FeatureSpec(
        name="selections_per_request",
        source=(
            "suggestion_selections/suggestion_requests"
        ),
        family="consultation",
        description=(
            "Number of observed suggestion selections per "
            "suggestion request. May exceed 1 because an episode "
            "can contain multiple selections."
        ),
    ),
    FeatureSpec(
        name="dismissal_rate",
        source=(
            "dismissed_episodes/suggestion_requests"
        ),
        family="consultation",
        description=(
            "Dismissed suggestion episodes per suggestion request."
        ),
    ),
    FeatureSpec(
        name="reopen_rate",
        source=(
            "suggestion_reopens/suggestion_requests"
        ),
        family="consultation",
        description=(
            "Suggestion reopen events per suggestion request. "
            "This is an event rate and is not constrained to 1."
        ),
    ),
    FeatureSpec(
        name="multi_selection_rate",
        source=(
            "multi_selection_episodes/suggestion_requests"
        ),
        family="consultation",
        description=(
            "Episodes containing multiple selections per "
            "suggestion request."
        ),
    ),
    FeatureSpec(
        name="consultation_density_per_1000_authored_chars",
        source=(
            "consultation_density_per_1000_authored_chars"
        ),
        family="consultation",
        description=(
            "Suggestion-request density normalized by authored "
            "text length."
        ),
    ),
    FeatureSpec(
        name="log_median_request_to_selection_ms",
        source="median_request_to_selection_ms",
        family="timing",
        description=(
            "Natural-log-transformed median latency from request "
            "to selection."
        ),
        transform="log1p",
    ),
    FeatureSpec(
        name="log_median_open_to_selection_ms",
        source="median_open_to_selection_ms",
        family="timing",
        description=(
            "Natural-log-transformed median latency from suggestion "
            "display to selection."
        ),
        transform="log1p",
    ),
    FeatureSpec(
        name="consultation_burstiness",
        source="consultation_burstiness",
        family="timing",
        description=(
            "Burstiness of intervals between suggestion requests."
        ),
    ),
    FeatureSpec(
        name="log_session_duration_ms",
        source="session_duration_ms",
        family="scale",
        description=(
            "Natural-log-transformed session duration."
        ),
        transform="log1p",
    ),
    FeatureSpec(
        name="direct_adoption_share",
        source=(
            "direct_adoptions/suggestion_selections"
        ),
        family="response_use",
        description=(
            "Share of confirmed selections classified as direct "
            "adoption. Undefined when there are no selections."
        ),
        leakage_role="outcome_profile",
    ),
    FeatureSpec(
        name="modified_adoption_share",
        source=(
            "modified_adoptions/suggestion_selections"
        ),
        family="response_use",
        description=(
            "Share of confirmed selections classified as modified "
            "adoption. Undefined when there are no selections."
        ),
        leakage_role="outcome_profile",
    ),
)


def _optional_float(
    value: object,
) -> float | None:
    if value is None:
        return None

    text = str(value).strip()

    if text in {
        "",
        "None",
        "nan",
        "NaN",
        "NA",
    }:
        return None

    number = float(text)

    if not math.isfinite(number):
        return None

    return number


def _ratio(
    numerator: object,
    denominator: object,
) -> float | None:
    num = _optional_float(
        numerator
    )
    den = _optional_float(
        denominator
    )

    if (
        num is None
        or den is None
        or den <= 0
    ):
        return None

    return num / den


def _log1p(
    value: object,
) -> float | None:
    number = _optional_float(
        value
    )

    if (
        number is None
        or number < 0
    ):
        return None

    return math.log1p(
        number
    )


def build_session_features(
    row: Mapping[str, object],
) -> dict[str, object]:
    features: dict[str, object] = {
        "session_id": str(
            row["session_id"]
        ),
    }

    suggestion_requests = _optional_float(
        row.get(
            "suggestion_requests"
        )
    )

    suggestion_selections = _optional_float(
        row.get(
            "suggestion_selections"
        )
    )

    ai_inserted_chars = _optional_float(
        row.get(
            "ai_inserted_chars"
        )
    )

    ai_surviving_chars = _optional_float(
        row.get(
            "ai_surviving_chars"
        )
    )

    features[
        "log_authored_text_chars"
    ] = _log1p(
        row.get(
            "authored_text_chars"
        )
    )

    features[
        "ai_share"
    ] = _optional_float(
        row.get(
            "ai_share"
        )
    )

    features[
        "ai_retention_ratio"
    ] = _ratio(
        ai_surviving_chars,
        ai_inserted_chars,
    )

    features[
        "human_generation_before_ai_ratio"
    ] = _optional_float(
        row.get(
            "human_generation_before_ai_ratio"
        )
    )

    features[
        "selections_per_request"
    ] = _ratio(
        suggestion_selections,
        suggestion_requests,
    )

    features[
        "dismissal_rate"
    ] = _ratio(
        row.get(
            "dismissed_episodes"
        ),
        suggestion_requests,
    )

    features[
        "reopen_rate"
    ] = _ratio(
        row.get(
            "suggestion_reopens"
        ),
        suggestion_requests,
    )

    features[
        "multi_selection_rate"
    ] = _ratio(
        row.get(
            "multi_selection_episodes"
        ),
        suggestion_requests,
    )

    features[
        "consultation_density_per_1000_authored_chars"
    ] = _optional_float(
        row.get(
            "consultation_density_per_1000_authored_chars"
        )
    )

    features[
        "log_median_request_to_selection_ms"
    ] = _log1p(
        row.get(
            "median_request_to_selection_ms"
        )
    )

    features[
        "log_median_open_to_selection_ms"
    ] = _log1p(
        row.get(
            "median_open_to_selection_ms"
        )
    )

    features[
        "consultation_burstiness"
    ] = _optional_float(
        row.get(
            "consultation_burstiness"
        )
    )

    features[
        "log_session_duration_ms"
    ] = _log1p(
        row.get(
            "session_duration_ms"
        )
    )

    features[
        "direct_adoption_share"
    ] = _ratio(
        row.get(
            "direct_adoptions"
        ),
        suggestion_selections,
    )

    features[
        "modified_adoption_share"
    ] = _ratio(
        row.get(
            "modified_adoptions"
        ),
        suggestion_selections,
    )

    features[
        "behavioral_complete"
    ] = int(
        all(
            features.get(name)
            is not None
            for name
            in BEHAVIORAL_FEATURES
        )
    )

    features[
        "profile_complete"
    ] = int(
        all(
            features.get(name)
            is not None
            for name
            in PROFILE_FEATURES
        )
    )

    return features
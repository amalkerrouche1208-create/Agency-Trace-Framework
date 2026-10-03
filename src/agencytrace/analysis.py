from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Iterable

from agencytrace.behavior import (
    OUTCOME_ACCEPT_UNCHANGED,
    OUTCOME_ACCEPTED_MODIFIED,
    OUTCOME_NON_ADOPTION,
    OUTCOME_PRESENTED_NO_SELECTION,
    OUTCOME_REQUEST_WITHOUT_SUGGESTION,
    OUTCOME_LABELS,
    OUTCOME_ORDER,
)


# =====================================================================
# Paths
# =====================================================================

DEFAULT_BEHAVIOR_METRICS = Path(
    "data/processed/target_behavior_metrics.csv"
)

DEFAULT_REQUEST_OUTCOMES = Path(
    "data/processed/request_outcomes.csv"
)

DEFAULT_OUTPUT_DIR = Path(
    "data/analysis"
)


# =====================================================================
# Constants
# =====================================================================

GROUP_ORDER = (
    "Low",
    "Moderate",
    "High",
)


# Exact indicator order used by the target heatmap.
TARGET_INDICATORS = (
    "human_generation_before_ai",
    "consultation_density",
    "ai_contribution",
    "ai_retention",
    "non_adoption",
    "post_ai_editing",
    "reconsultation",
    "response_latency",
    "transition_entropy",
    "consultation_burstiness",
)


TARGET_INDICATOR_LABELS = {
    "human_generation_before_ai": (
        "Human Generation Before AI"
    ),
    "consultation_density": (
        "Consultation Density"
    ),
    "ai_contribution": (
        "AI Contribution"
    ),
    "ai_retention": (
        "AI Retention"
    ),
    "non_adoption": (
        "Non-Adoption"
    ),
    "post_ai_editing": (
        "Post-AI Editing"
    ),
    "reconsultation": (
        "Reconsultation"
    ),
    "response_latency": (
        "Response Latency"
    ),
    "transition_entropy": (
        "Transition Entropy"
    ),
    "consultation_burstiness": (
        "Consultation Burstiness"
    ),
}


# Minimum pairwise sample size used by the original heatmap pipeline.
MIN_CORRELATION_N = 30


# =====================================================================
# Data models
# =====================================================================


@dataclass(frozen=True, slots=True)
class SessionRow:
    """
    One session represented by the ten target behavioral indicators.

    IMPORTANT:
    ai_contribution is the grouping variable used for the target
    Low / Moderate / High AI Share figure.

    It must represent:

        AI inserted chars
        -------------------------------
        human inserted chars + AI chars

    It is intentionally NOT the modern AgencyTrace final-text AI share.
    """

    session_id: str

    human_generation_before_ai: float | None
    consultation_density: float | None
    ai_contribution: float
    ai_retention: float | None
    non_adoption: float | None
    post_ai_editing: float | None
    reconsultation: float | None
    response_latency: float | None
    transition_entropy: float | None
    consultation_burstiness: float | None

    @property
    def ai_share(self) -> float:
        """
        Compatibility alias.

        In target-figure analysis, "AI Share" means the historical
        ai_contribution metric.
        """
        return self.ai_contribution


@dataclass(frozen=True, slots=True)
class RequestOutcomeRow:
    session_id: str
    request_id: str
    request_event_num: int | None
    outcome: str


@dataclass(frozen=True, slots=True)
class AIShareThresholds:
    low_upper: float
    moderate_upper: float


@dataclass(frozen=True, slots=True)
class GroupSummary:
    group: str
    n_sessions: int

    ai_contribution_mean: float
    ai_contribution_median: float

    human_generation_before_ai_mean: float | None
    consultation_density_mean: float | None
    ai_retention_mean: float | None
    non_adoption_mean: float | None
    post_ai_editing_mean: float | None
    reconsultation_mean: float | None
    response_latency_mean: float | None
    transition_entropy_mean: float | None
    consultation_burstiness_mean: float | None


@dataclass(frozen=True, slots=True)
class OutcomeGroupSummary:
    group: str

    n_sessions: int
    n_requests: int

    direct_count: int
    modified_count: int
    non_adoption_count: int
    no_selection_count: int
    no_suggestion_count: int

    direct_share: float
    modified_share: float
    non_adoption_share: float
    no_selection_share: float
    no_suggestion_share: float


# =====================================================================
# Load target behavioral metrics
# =====================================================================


def load_behavior_metrics(
    path: str | Path = DEFAULT_BEHAVIOR_METRICS,
) -> list[SessionRow]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            "\nTarget behavior metrics file not found:\n"
            f"    {path}\n\n"
            "The target analysis intentionally does not fall back to "
            "the modern session_metrics.csv because that would change "
            "the AI-share definition and reproduce the wrong figure."
        )

    rows: list[SessionRow] = []

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        fieldnames = set(
            reader.fieldnames or []
        )

        required = {
            "session_id",
            *TARGET_INDICATORS,
        }

        missing = (
            required
            - fieldnames
        )

        if missing:
            raise ValueError(
                "target_behavior_metrics.csv is missing "
                f"required columns: {sorted(missing)}"
            )

        seen_sessions: set[str] = set()

        for raw in reader:
            session_id = (
                raw["session_id"].strip()
            )

            if not session_id:
                raise ValueError(
                    "Encountered behavior row with empty session_id."
                )

            if session_id in seen_sessions:
                raise ValueError(
                    "Duplicate session_id in behavior metrics: "
                    f"{session_id}"
                )

            seen_sessions.add(
                session_id
            )

            ai_contribution = _required_float(
                raw["ai_contribution"],
                field="ai_contribution",
                session_id=session_id,
            )

            if not (
                0.0
                <= ai_contribution
                <= 1.0
            ):
                raise ValueError(
                    "ai_contribution must be in [0, 1]: "
                    f"{session_id} -> {ai_contribution}"
                )

            rows.append(
                SessionRow(
                    session_id=session_id,

                    human_generation_before_ai=(
                        _optional_float(
                            raw[
                                "human_generation_before_ai"
                            ]
                        )
                    ),

                    consultation_density=(
                        _optional_float(
                            raw[
                                "consultation_density"
                            ]
                        )
                    ),

                    ai_contribution=(
                        ai_contribution
                    ),

                    ai_retention=(
                        _optional_float(
                            raw[
                                "ai_retention"
                            ]
                        )
                    ),

                    non_adoption=(
                        _optional_float(
                            raw[
                                "non_adoption"
                            ]
                        )
                    ),

                    post_ai_editing=(
                        _optional_float(
                            raw[
                                "post_ai_editing"
                            ]
                        )
                    ),

                    reconsultation=(
                        _optional_float(
                            raw[
                                "reconsultation"
                            ]
                        )
                    ),

                    response_latency=(
                        _optional_float(
                            raw[
                                "response_latency"
                            ]
                        )
                    ),

                    transition_entropy=(
                        _optional_float(
                            raw[
                                "transition_entropy"
                            ]
                        )
                    ),

                    consultation_burstiness=(
                        _optional_float(
                            raw[
                                "consultation_burstiness"
                            ]
                        )
                    ),
                )
            )

    if not rows:
        raise ValueError(
            "No target behavior metric rows were loaded."
        )

    return rows


# Compatibility alias for code that previously called
# load_session_metrics().
def load_session_metrics(
    path: str | Path = DEFAULT_BEHAVIOR_METRICS,
) -> list[SessionRow]:
    return load_behavior_metrics(
        path
    )


# =====================================================================
# Load request outcomes
# =====================================================================


def load_request_outcomes(
    path: str | Path = DEFAULT_REQUEST_OUTCOMES,
) -> list[RequestOutcomeRow]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            "\nRequest-outcome file not found:\n"
            f"    {path}\n\n"
            "The stacked figure requires one outcome for every "
            "suggestion-get request."
        )

    rows: list[RequestOutcomeRow] = []

    seen_keys: set[
        tuple[str, str]
    ] = set()

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        fields = set(
            reader.fieldnames or []
        )

        if "session_id" not in fields:
            raise ValueError(
                "request_outcomes.csv must contain session_id."
            )

        if not (
            "outcome" in fields
            or "figure_outcome" in fields
        ):
            raise ValueError(
                "request_outcomes.csv must contain an "
                "'outcome' column."
            )

        for row_number, raw in enumerate(
            reader,
            start=2,
        ):
            session_id = (
                raw["session_id"].strip()
            )

            if not session_id:
                raise ValueError(
                    "Empty session_id in request_outcomes.csv "
                    f"at line {row_number}."
                )

            raw_outcome = (
                raw.get("outcome")
                or raw.get("figure_outcome")
                or ""
            ).strip()

            outcome = _normalize_outcome(
                raw_outcome
            )

            request_id = (
                raw.get("request_id")
                or raw.get("episode_id")
                or raw.get("request_event_num")
                or raw.get("request_event")
                or str(row_number)
            )

            request_id = str(
                request_id
            ).strip()

            request_event_num = (
                _optional_int(
                    raw.get(
                        "request_event_num",
                        raw.get(
                            "request_event",
                            "",
                        ),
                    )
                )
            )

            key = (
                session_id,
                request_id,
            )

            if key in seen_keys:
                raise ValueError(
                    "Duplicate request outcome: "
                    f"{key}"
                )

            seen_keys.add(
                key
            )

            rows.append(
                RequestOutcomeRow(
                    session_id=session_id,
                    request_id=request_id,
                    request_event_num=(
                        request_event_num
                    ),
                    outcome=outcome,
                )
            )

    if not rows:
        raise ValueError(
            "No request outcomes were loaded."
        )

    return rows


# =====================================================================
# AI-contribution tertiles
# =====================================================================


def compute_ai_share_thresholds(
    rows: Iterable[SessionRow],
) -> AIShareThresholds:
    """
    Compute 1/3 and 2/3 quantiles of historical ai_contribution.

    This reproduces the pandas qcut-style tertile boundaries used by
    the target stacked figure.
    """

    values = sorted(
        row.ai_contribution
        for row in rows
        if math.isfinite(
            row.ai_contribution
        )
    )

    if not values:
        raise ValueError(
            "Cannot compute AI-share thresholds from empty data."
        )

    return AIShareThresholds(
        low_upper=_quantile(
            values,
            1.0 / 3.0,
        ),
        moderate_upper=_quantile(
            values,
            2.0 / 3.0,
        ),
    )


def assign_ai_share_group(
    ai_share: float,
    thresholds: AIShareThresholds,
) -> str:
    """
    Historical figure terminology calls ai_contribution "AI Share".
    """

    if ai_share <= thresholds.low_upper:
        return "Low"

    if (
        ai_share
        <= thresholds.moderate_upper
    ):
        return "Moderate"

    return "High"


# =====================================================================
# Group summaries
# =====================================================================


def summarize_ai_share_groups(
    rows: list[SessionRow],
    thresholds: AIShareThresholds,
) -> list[GroupSummary]:

    grouped: dict[
        str,
        list[SessionRow],
    ] = {
        group: []
        for group in GROUP_ORDER
    }

    for row in rows:
        group = assign_ai_share_group(
            row.ai_contribution,
            thresholds,
        )

        grouped[group].append(
            row
        )

    summaries: list[
        GroupSummary
    ] = []

    for group in GROUP_ORDER:
        members = grouped[
            group
        ]

        if not members:
            raise ValueError(
                f"AI-share group {group!r} is empty."
            )

        summaries.append(
            GroupSummary(
                group=group,

                n_sessions=len(
                    members
                ),

                ai_contribution_mean=mean(
                    row.ai_contribution
                    for row in members
                ),

                ai_contribution_median=median(
                    row.ai_contribution
                    for row in members
                ),

                human_generation_before_ai_mean=(
                    _mean_optional(
                        row.human_generation_before_ai
                        for row in members
                    )
                ),

                consultation_density_mean=(
                    _mean_optional(
                        row.consultation_density
                        for row in members
                    )
                ),

                ai_retention_mean=(
                    _mean_optional(
                        row.ai_retention
                        for row in members
                    )
                ),

                non_adoption_mean=(
                    _mean_optional(
                        row.non_adoption
                        for row in members
                    )
                ),

                post_ai_editing_mean=(
                    _mean_optional(
                        row.post_ai_editing
                        for row in members
                    )
                ),

                reconsultation_mean=(
                    _mean_optional(
                        row.reconsultation
                        for row in members
                    )
                ),

                response_latency_mean=(
                    _mean_optional(
                        row.response_latency
                        for row in members
                    )
                ),

                transition_entropy_mean=(
                    _mean_optional(
                        row.transition_entropy
                        for row in members
                    )
                ),

                consultation_burstiness_mean=(
                    _mean_optional(
                        row.consultation_burstiness
                        for row in members
                    )
                ),
            )
        )

    return summaries


# =====================================================================
# Five-way request outcomes by AI-share group
# =====================================================================


def summarize_outcomes_by_ai_share(
    *,
    request_outcomes: list[RequestOutcomeRow],
    session_rows: list[SessionRow],
    thresholds: AIShareThresholds,
) -> list[OutcomeGroupSummary]:

    session_groups = {
        row.session_id: (
            assign_ai_share_group(
                row.ai_contribution,
                thresholds,
            )
        )
        for row in session_rows
    }

    session_counts = {
        group: sum(
            session_group == group
            for session_group
            in session_groups.values()
        )
        for group in GROUP_ORDER
    }

    counts: dict[
        str,
        CounterLike,
    ] = {
        group: {
            outcome: 0
            for outcome in OUTCOME_ORDER
        }
        for group in GROUP_ORDER
    }

    unknown_sessions: set[
        str
    ] = set()

    for row in request_outcomes:
        group = session_groups.get(
            row.session_id
        )

        if group is None:
            unknown_sessions.add(
                row.session_id
            )
            continue

        counts[group][
            row.outcome
        ] += 1

    if unknown_sessions:
        examples = sorted(
            unknown_sessions
        )[:10]

        raise ValueError(
            "Request outcomes reference sessions missing from "
            "target_behavior_metrics.csv. Examples: "
            f"{examples}"
        )

    summaries: list[
        OutcomeGroupSummary
    ] = []

    for group in GROUP_ORDER:
        group_counts = counts[
            group
        ]

        direct = group_counts[
            OUTCOME_ACCEPT_UNCHANGED
        ]

        modified = group_counts[
            OUTCOME_ACCEPTED_MODIFIED
        ]

        non_adoption = group_counts[
            OUTCOME_NON_ADOPTION
        ]

        no_selection = group_counts[
            OUTCOME_PRESENTED_NO_SELECTION
        ]

        no_suggestion = group_counts[
            OUTCOME_REQUEST_WITHOUT_SUGGESTION
        ]

        total = (
            direct
            + modified
            + non_adoption
            + no_selection
            + no_suggestion
        )

        summaries.append(
            OutcomeGroupSummary(
                group=group,

                n_sessions=(
                    session_counts[
                        group
                    ]
                ),

                n_requests=total,

                direct_count=direct,
                modified_count=modified,
                non_adoption_count=(
                    non_adoption
                ),
                no_selection_count=(
                    no_selection
                ),
                no_suggestion_count=(
                    no_suggestion
                ),

                direct_share=_safe_ratio(
                    direct,
                    total,
                ),

                modified_share=_safe_ratio(
                    modified,
                    total,
                ),

                non_adoption_share=_safe_ratio(
                    non_adoption,
                    total,
                ),

                no_selection_share=_safe_ratio(
                    no_selection,
                    total,
                ),

                no_suggestion_share=_safe_ratio(
                    no_suggestion,
                    total,
                ),
            )
        )

    return summaries


# Backward-compatible public name.
def summarize_adoption_by_ai_share(
    *,
    request_outcomes_path: str | Path = DEFAULT_REQUEST_OUTCOMES,
    session_rows: list[SessionRow],
    thresholds: AIShareThresholds,
    **_: object,
) -> list[OutcomeGroupSummary]:

    request_outcomes = (
        load_request_outcomes(
            request_outcomes_path
        )
    )

    return summarize_outcomes_by_ai_share(
        request_outcomes=(
            request_outcomes
        ),
        session_rows=session_rows,
        thresholds=thresholds,
    )


# =====================================================================
# Spearman target heatmap
# =====================================================================


def spearman_correlation_matrix(
    rows: list[SessionRow],
    *,
    min_periods: int = MIN_CORRELATION_N,
) -> tuple[
    list[str],
    list[list[float]],
    list[list[int]],
]:
    """
    Pairwise Spearman correlations over the exact ten target indicators.

    Pairwise missing values are removed independently for each pair.

    A coefficient is returned as NaN when fewer than min_periods valid
    observations are available.
    """

    variables = list(
        TARGET_INDICATORS
    )

    correlations: list[
        list[float]
    ] = []

    sample_sizes: list[
        list[int]
    ] = []

    for left_name in variables:
        correlation_row: list[
            float
        ] = []

        n_row: list[
            int
        ] = []

        for right_name in variables:
            x: list[float] = []
            y: list[float] = []

            for row in rows:
                left = getattr(
                    row,
                    left_name,
                )

                right = getattr(
                    row,
                    right_name,
                )

                if (
                    left is None
                    or right is None
                ):
                    continue

                left = float(
                    left
                )

                right = float(
                    right
                )

                if (
                    not math.isfinite(
                        left
                    )
                    or not math.isfinite(
                        right
                    )
                ):
                    continue

                x.append(
                    left
                )

                y.append(
                    right
                )

            n = len(
                x
            )

            if n < min_periods:
                coefficient = math.nan
            else:
                coefficient = _spearman(
                    x,
                    y,
                )

            correlation_row.append(
                coefficient
            )

            n_row.append(
                n
            )

        correlations.append(
            correlation_row
        )

        sample_sizes.append(
            n_row
        )

    return (
        variables,
        correlations,
        sample_sizes,
    )


# =====================================================================
# Main analysis export
# =====================================================================


def export_analysis_tables(
    *,
    behavior_metrics_path: str | Path = DEFAULT_BEHAVIOR_METRICS,
    request_outcomes_path: str | Path = DEFAULT_REQUEST_OUTCOMES,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,

    # Compatibility arguments from the older analysis.py API.
    session_metrics_path: str | Path | None = None,
    selection_metrics_path: str | Path | None = None,
) -> None:
    """
    Export all tables required for the target heatmap and stacked bar.

    session_metrics_path and selection_metrics_path are accepted only
    for API compatibility. Target-figure analysis intentionally does not
    use the modern selection-level adoption table.
    """

    if session_metrics_path is not None:
        behavior_metrics_path = (
            session_metrics_path
        )

    # selection_metrics_path is deliberately ignored.
    _ = selection_metrics_path

    rows = load_behavior_metrics(
        behavior_metrics_path
    )

    request_outcomes = (
        load_request_outcomes(
            request_outcomes_path
        )
    )

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    thresholds = (
        compute_ai_share_thresholds(
            rows
        )
    )

    group_summary = (
        summarize_ai_share_groups(
            rows,
            thresholds,
        )
    )

    outcome_summary = (
        summarize_outcomes_by_ai_share(
            request_outcomes=(
                request_outcomes
            ),
            session_rows=rows,
            thresholds=thresholds,
        )
    )

    (
        variables,
        correlations,
        sample_sizes,
    ) = spearman_correlation_matrix(
        rows,
        min_periods=(
            MIN_CORRELATION_N
        ),
    )

    # -------------------------------------------------------------
    # Thresholds
    # -------------------------------------------------------------

    _write_thresholds(
        output_dir
        / "ai_share_thresholds.csv",
        thresholds,
    )

    # -------------------------------------------------------------
    # Group membership
    # -------------------------------------------------------------

    _write_group_membership(
        output_dir
        / "session_ai_share_groups.csv",
        rows,
        thresholds,
    )

    # -------------------------------------------------------------
    # Group descriptive summary
    # -------------------------------------------------------------

    _write_group_summary(
        output_dir
        / "ai_share_group_summary.csv",
        group_summary,
    )

    # -------------------------------------------------------------
    # Exact five-way stacked-bar input
    # -------------------------------------------------------------

    _write_outcome_summary(
        output_dir
        / "target_outcomes_by_ai_share.csv",
        outcome_summary,
    )

    # Compatibility alias for earlier figure scripts.
    _write_outcome_summary(
        output_dir
        / "adoption_by_ai_share.csv",
        outcome_summary,
    )

    # -------------------------------------------------------------
    # Exact target heatmap input
    # -------------------------------------------------------------

    _write_matrix(
        output_dir
        / "target_behavior_correlations.csv",
        variables,
        correlations,
        labels=TARGET_INDICATOR_LABELS,
    )

    _write_int_matrix(
        output_dir
        / "target_behavior_sample_sizes.csv",
        variables,
        sample_sizes,
        labels=TARGET_INDICATOR_LABELS,
    )

    # Compatibility aliases.
    _write_matrix(
        output_dir
        / "spearman_correlations.csv",
        variables,
        correlations,
        labels=TARGET_INDICATOR_LABELS,
    )

    _write_int_matrix(
        output_dir
        / "spearman_sample_sizes.csv",
        variables,
        sample_sizes,
        labels=TARGET_INDICATOR_LABELS,
    )

    # -------------------------------------------------------------
    # Console audit
    # -------------------------------------------------------------

    total_requests = sum(
        summary.n_requests
        for summary in outcome_summary
    )

    print()
    print("=" * 82)
    print(
        "AgencyTrace — Target Behavior Analysis"
    )
    print("=" * 82)

    print(
        f"Sessions analyzed               : {len(rows)}"
    )

    print(
        f"Request outcomes analyzed       : {total_requests}"
    )

    print()

    print(
        "AI-share definition             : "
        "historical AI contribution"
    )

    print(
        "                                  "
        "AI inserted / (human inserted + AI inserted)"
    )

    print()

    print(
        f"Low/Moderate threshold          : "
        f"{thresholds.low_upper:.6f}"
    )

    print(
        f"Moderate/High threshold         : "
        f"{thresholds.moderate_upper:.6f}"
    )

    print()

    print(
        "AI-share groups"
    )
    print("-" * 82)

    for summary in group_summary:
        print(
            f"{summary.group:<10} "
            f"n={summary.n_sessions:<4} "
            f"AI contribution mean="
            f"{summary.ai_contribution_mean:.4f}"
        )

    print()

    print(
        "Five-way request outcomes by AI-share group"
    )

    print("-" * 82)

    for summary in outcome_summary:
        print(
            f"{summary.group:<10} "
            f"N={summary.n_requests:<5} "
            f"Direct={summary.direct_share * 100:>5.1f}%  "
            f"Modified={summary.modified_share * 100:>4.1f}%  "
            f"Non={summary.non_adoption_share * 100:>4.1f}%  "
            f"NoSel={summary.no_selection_share * 100:>4.1f}%  "
            f"NoSug={summary.no_suggestion_share * 100:>4.1f}%"
        )

    print()

    print(
        "Expected target pattern:"
    )

    print(
        "Low       ≈ 51.5 / 2.9 / 25.5 / 5.5 / 14.6"
    )

    print(
        "Moderate  ≈ 65.4 / 3.6 / 17.8 / 6.0 / 7.2"
    )

    print(
        "High      ≈ 75.2 / 0.9 / 15.5 / 4.1 / 4.4"
    )

    print()

    print(
        f"Analysis tables                 : {output_dir}"
    )

    print()

    print("=" * 82)
    print(
        "Target behavior analysis completed."
    )
    print("=" * 82)


# =====================================================================
# Statistics
# =====================================================================


def _spearman(
    x: list[float],
    y: list[float],
) -> float:
    if len(x) != len(y):
        raise ValueError(
            "Spearman vectors must have equal length."
        )

    if len(x) < 2:
        return math.nan

    return _pearson(
        _rankdata(x),
        _rankdata(y),
    )


def _rankdata(
    values: list[float],
) -> list[float]:
    """
    Average ranks for ties, equivalent to standard Spearman ranking.
    """

    indexed = sorted(
        enumerate(values),
        key=lambda item: item[1],
    )

    ranks = [
        0.0
    ] * len(
        values
    )

    i = 0

    while i < len(
        indexed
    ):
        j = i + 1

        while (
            j < len(indexed)
            and indexed[j][1]
            == indexed[i][1]
        ):
            j += 1

        rank = (
            (i + 1)
            + j
        ) / 2.0

        for k in range(
            i,
            j,
        ):
            ranks[
                indexed[k][0]
            ] = rank

        i = j

    return ranks


def _pearson(
    x: list[float],
    y: list[float],
) -> float:
    if len(x) < 2:
        return math.nan

    mx = mean(
        x
    )

    my = mean(
        y
    )

    numerator = sum(
        (
            a - mx
        )
        * (
            b - my
        )
        for a, b
        in zip(
            x,
            y,
        )
    )

    sx = sum(
        (
            a - mx
        )
        ** 2
        for a in x
    )

    sy = sum(
        (
            b - my
        )
        ** 2
        for b in y
    )

    denominator = math.sqrt(
        sx * sy
    )

    if denominator == 0:
        return math.nan

    return (
        numerator
        / denominator
    )


# =====================================================================
# Export helpers
# =====================================================================


def _write_thresholds(
    path: Path,
    thresholds: AIShareThresholds,
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "threshold",
                "value",
            ]
        )

        writer.writerow(
            [
                "low_upper",
                thresholds.low_upper,
            ]
        )

        writer.writerow(
            [
                "moderate_upper",
                thresholds.moderate_upper,
            ]
        )


def _write_group_membership(
    path: Path,
    rows: list[SessionRow],
    thresholds: AIShareThresholds,
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "session_id",
                "ai_contribution",
                "ai_share",
                "ai_share_group",
            ]
        )

        for row in sorted(
            rows,
            key=lambda item: (
                item.session_id
            ),
        ):
            group = (
                assign_ai_share_group(
                    row.ai_contribution,
                    thresholds,
                )
            )

            writer.writerow(
                [
                    row.session_id,
                    row.ai_contribution,

                    # Compatibility column:
                    # in this target analysis,
                    # AI Share == ai_contribution.
                    row.ai_contribution,

                    group,
                ]
            )


def _write_group_summary(
    path: Path,
    rows: list[GroupSummary],
) -> None:
    fieldnames = [
        "group",
        "n_sessions",
        "ai_contribution_mean",
        "ai_contribution_median",
        "human_generation_before_ai_mean",
        "consultation_density_mean",
        "ai_retention_mean",
        "non_adoption_mean",
        "post_ai_editing_mean",
        "reconsultation_mean",
        "response_latency_mean",
        "transition_entropy_mean",
        "consultation_burstiness_mean",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: getattr(
                        row,
                        field,
                    )
                    for field
                    in fieldnames
                }
            )


def _write_outcome_summary(
    path: Path,
    rows: list[OutcomeGroupSummary],
) -> None:
    """
    Export both raw counts and proportions.

    The five proportion columns deliberately use the short names
    expected by the target stacked-bar plotting code.
    """

    fieldnames = [
        "group",
        "n_sessions",
        "n_requests",

        "direct_count",
        "modified_count",
        "non_adoption_count",
        "no_selection_count",
        "no_suggestion_count",

        "direct_adoption",
        "modified_adoption",
        "non_adoption",
        "no_selection",
        "no_suggestion",

        "direct_share",
        "modified_share",
        "non_adoption_share",
        "no_selection_share",
        "no_suggestion_share",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    "group": (
                        row.group
                    ),

                    "n_sessions": (
                        row.n_sessions
                    ),

                    "n_requests": (
                        row.n_requests
                    ),

                    "direct_count": (
                        row.direct_count
                    ),

                    "modified_count": (
                        row.modified_count
                    ),

                    "non_adoption_count": (
                        row.non_adoption_count
                    ),

                    "no_selection_count": (
                        row.no_selection_count
                    ),

                    "no_suggestion_count": (
                        row.no_suggestion_count
                    ),

                    "direct_adoption": (
                        row.direct_share
                    ),

                    "modified_adoption": (
                        row.modified_share
                    ),

                    "non_adoption": (
                        row.non_adoption_share
                    ),

                    "no_selection": (
                        row.no_selection_share
                    ),

                    "no_suggestion": (
                        row.no_suggestion_share
                    ),

                    "direct_share": (
                        row.direct_share
                    ),

                    "modified_share": (
                        row.modified_share
                    ),

                    "non_adoption_share": (
                        row.non_adoption_share
                    ),

                    "no_selection_share": (
                        row.no_selection_share
                    ),

                    "no_suggestion_share": (
                        row.no_suggestion_share
                    ),
                }
            )


def _write_matrix(
    path: Path,
    variables: list[str],
    matrix: list[list[float]],
    *,
    labels: dict[str, str] | None = None,
) -> None:
    labels = labels or {}

    display_variables = [
        labels.get(
            variable,
            variable,
        )
        for variable in variables
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "variable",
                *display_variables,
            ]
        )

        for variable, row in zip(
            variables,
            matrix,
        ):
            writer.writerow(
                [
                    labels.get(
                        variable,
                        variable,
                    ),
                    *row,
                ]
            )


def _write_int_matrix(
    path: Path,
    variables: list[str],
    matrix: list[list[int]],
    *,
    labels: dict[str, str] | None = None,
) -> None:
    labels = labels or {}

    display_variables = [
        labels.get(
            variable,
            variable,
        )
        for variable in variables
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(
            handle
        )

        writer.writerow(
            [
                "variable",
                *display_variables,
            ]
        )

        for variable, row in zip(
            variables,
            matrix,
        ):
            writer.writerow(
                [
                    labels.get(
                        variable,
                        variable,
                    ),
                    *row,
                ]
            )


# =====================================================================
# Generic helpers
# =====================================================================


CounterLike = dict[str, int]


def _normalize_outcome(
    value: str,
) -> str:
    normalized = (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    aliases = {
        # Canonical names.
        OUTCOME_ACCEPT_UNCHANGED: (
            OUTCOME_ACCEPT_UNCHANGED
        ),

        OUTCOME_ACCEPTED_MODIFIED: (
            OUTCOME_ACCEPTED_MODIFIED
        ),

        OUTCOME_NON_ADOPTION: (
            OUTCOME_NON_ADOPTION
        ),

        OUTCOME_PRESENTED_NO_SELECTION: (
            OUTCOME_PRESENTED_NO_SELECTION
        ),

        OUTCOME_REQUEST_WITHOUT_SUGGESTION: (
            OUTCOME_REQUEST_WITHOUT_SUGGESTION
        ),

        # Previous AgencyTrace aliases.
        "direct_adoption": (
            OUTCOME_ACCEPT_UNCHANGED
        ),

        "modified_adoption": (
            OUTCOME_ACCEPTED_MODIFIED
        ),

        "no_selection": (
            OUTCOME_PRESENTED_NO_SELECTION
        ),

        "no_suggestion": (
            OUTCOME_REQUEST_WITHOUT_SUGGESTION
        ),

        # Common historical aliases.
        "accepted_unchanged": (
            OUTCOME_ACCEPT_UNCHANGED
        ),

        "accept_modified": (
            OUTCOME_ACCEPTED_MODIFIED
        ),

        "request_without_presented_suggestion": (
            OUTCOME_REQUEST_WITHOUT_SUGGESTION
        ),
    }

    if normalized not in aliases:
        raise ValueError(
            "Unknown request outcome "
            f"{value!r}. Expected one of: "
            f"{list(OUTCOME_ORDER)}"
        )

    return aliases[
        normalized
    ]


def _required_float(
    value: str,
    *,
    field: str,
    session_id: str,
) -> float:
    result = _optional_float(
        value
    )

    if result is None:
        raise ValueError(
            f"Missing required {field!r} for "
            f"session {session_id!r}."
        )

    return result


def _optional_float(
    value: object,
) -> float | None:
    if value is None:
        return None

    text = str(
        value
    ).strip()

    if text in {
        "",
        "None",
        "none",
        "nan",
        "NaN",
        "NA",
        "N/A",
        "null",
    }:
        return None

    result = float(
        text
    )

    if not math.isfinite(
        result
    ):
        return None

    return result


def _optional_int(
    value: object,
) -> int | None:
    if value is None:
        return None

    text = str(
        value
    ).strip()

    if text in {
        "",
        "None",
        "none",
        "nan",
        "NaN",
        "null",
    }:
        return None

    return int(
        float(text)
    )


def _mean_optional(
    values: Iterable[
        float | None
    ],
) -> float | None:
    cleaned = [
        float(value)
        for value in values
        if (
            value is not None
            and math.isfinite(
                float(value)
            )
        )
    ]

    if not cleaned:
        return None

    return mean(
        cleaned
    )


def _safe_ratio(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return (
        numerator
        / denominator
    )


def _quantile(
    sorted_values: list[float],
    probability: float,
) -> float:
    """
    Linear interpolation equivalent to pandas/numpy default quantile
    behavior used by qcut boundary construction.
    """

    if not sorted_values:
        raise ValueError(
            "Cannot compute quantile of empty data."
        )

    if not (
        0.0
        <= probability
        <= 1.0
    ):
        raise ValueError(
            "Quantile probability must be in [0, 1]."
        )

    position = (
        len(sorted_values)
        - 1
    ) * probability

    lower = math.floor(
        position
    )

    upper = math.ceil(
        position
    )

    if lower == upper:
        return sorted_values[
            lower
        ]

    weight = (
        position
        - lower
    )

    return (
        sorted_values[lower]
        * (1.0 - weight)
        + sorted_values[upper]
        * weight
    )


# =====================================================================
# Entry point
# =====================================================================


if __name__ == "__main__":
    export_analysis_tables()
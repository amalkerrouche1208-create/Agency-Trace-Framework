from __future__ import annotations

import csv
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from agencytrace.behavior import (
    OUTCOME_ACCEPT_UNCHANGED,
    OUTCOME_ACCEPTED_MODIFIED,
    OUTCOME_NON_ADOPTION,
    OUTCOME_PRESENTED_NO_SELECTION,
    OUTCOME_REQUEST_WITHOUT_SUGGESTION,
    classify_request_outcomes,
)
from agencytrace.io import load_jsonl_events
from agencytrace.metrics import compute_selection_metrics
from agencytrace.models import Event, EventSource, SuggestionEpisode
from agencytrace.provenance import reconstruct_provenance
from agencytrace.reconstruct import reconstruct_suggestion_episodes


# =====================================================================
# Paths
# =====================================================================

RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")

BEHAVIOR_OUTPUT = OUTPUT_DIR / "target_behavior_metrics.csv"
OUTCOME_OUTPUT = OUTPUT_DIR / "request_outcomes.csv"


# =====================================================================
# Historical target definitions
# =====================================================================

PRE_WINDOW_MS = 30_000
POST_WINDOW_MS = 30_000
RECONSULT_MS = 60_000

DIRECT_RETENTION = 0.90
SURFACE_REVISION = 0.60
TRANSFORMATIVE_REVISION = 0.15


# =====================================================================
# Expected corpus reference
#
# Audit targets only. They are never forced into the output.
# =====================================================================

EXPECTED_SESSIONS = 1_447
EXPECTED_REQUESTS = 18_103

EXPECTED_OUTCOMES = {
    OUTCOME_ACCEPT_UNCHANGED: 12_427,
    OUTCOME_ACCEPTED_MODIFIED: 364,
    OUTCOME_NON_ADOPTION: 3_205,
    OUTCOME_PRESENTED_NO_SELECTION: 878,
    OUTCOME_REQUEST_WITHOUT_SUGGESTION: 1_229,
}


# =====================================================================
# Historical heatmap episode
#
# This deliberately reproduces the original post_ai_analysis.py layer.
# It is separate from AgencyTrace's stronger lifecycle reconstruction.
# =====================================================================


@dataclass(slots=True)
class _HistoricalEpisode:
    session_id: str
    episode_id: int
    request_event_num: int
    request_timestamp: int

    open_event_num: int | None = None
    open_timestamp: int | None = None

    select_event_num: int | None = None
    select_timestamp: int | None = None

    insertion_event_num: int | None = None
    insertion_timestamp: int | None = None

    ai_chars: int = 0
    retained_chars: int = 0
    retention: float | None = None

    pre_ai_generation: int = 0
    pre_ai_deletion: int = 0

    post_ai_edits: int = 0
    response_latency_s: float | None = None
    reconsultation: int = 0

    response_use: str = "No Suggestion"


# =====================================================================
# Main
# =====================================================================


def main() -> None:
    paths = sorted(RAW_DIR.rglob("*.jsonl"))

    if not paths:
        raise SystemExit(
            "No CoAuthor JSONL files found under data/raw/."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    behavior_rows: list[dict[str, object]] = []
    outcome_rows: list[dict[str, object]] = []

    outcome_counts: Counter[str] = Counter()

    total_episodes = 0
    total_selections = 0

    for index, path in enumerate(
        paths,
        start=1,
    ):
        events = load_jsonl_events(path)

        # -------------------------------------------------------------
        # Validated AgencyTrace lifecycle/provenance layer
        #
        # Used for the exact five-way request-outcome reproduction.
        # -------------------------------------------------------------

        episodes = reconstruct_suggestion_episodes(
            events
        )

        provenance = reconstruct_provenance(
            events,
            episodes,
        )

        selection_metrics = compute_selection_metrics(
            episodes,
            provenance,
        )

        total_episodes += len(episodes)
        total_selections += len(selection_metrics)

        outcomes = classify_request_outcomes(
            events=events,
            episodes=episodes,
            selection_metrics=selection_metrics,
        )

        if len(outcomes) != len(episodes):
            raise RuntimeError(
                f"{path.name}: "
                f"{len(episodes)} episodes but "
                f"{len(outcomes)} request outcomes."
            )

        for row in outcomes:
            outcome_counts[row.outcome] += 1

            outcome_rows.append(
                {
                    "session_id": row.session_id,
                    "request_id": row.request_id,
                    "request_event_num": row.request_event_num,
                    "open_event_num": row.open_event_num,
                    "selection_count": row.selection_count,
                    "outcome": row.outcome,
                    "figure_label": row.figure_label,
                }
            )

        # -------------------------------------------------------------
        # Exact historical post-AI indicator layer
        #
        # The target heatmap was produced from a simpler one-request-
        # window episode model. Reproduce that model directly rather
        # than approximating it with modern lifecycle metrics.
        # -------------------------------------------------------------

        behavior_rows.append(
            _historical_session_indicators(
                events=events,
                session_id=path.stem,
            )
        )

        if (
            index % 100 == 0
            or index == len(paths)
        ):
            print(
                f"Processed "
                f"{index}/{len(paths)} sessions..."
            )

    # -----------------------------------------------------------------
    # Deterministic ordering
    # -----------------------------------------------------------------

    behavior_rows.sort(
        key=lambda row: str(
            row["session_id"]
        )
    )

    outcome_rows.sort(
        key=lambda row: (
            str(row["session_id"]),
            int(row["request_event_num"]),
        )
    )

    # -----------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------

    _write_dict_rows(
        BEHAVIOR_OUTPUT,
        behavior_rows,
    )

    _write_dict_rows(
        OUTCOME_OUTPUT,
        outcome_rows,
    )

    _print_audit(
        paths=paths,
        total_episodes=total_episodes,
        total_selections=total_selections,
        behavior_rows=behavior_rows,
        outcome_rows=outcome_rows,
        outcome_counts=outcome_counts,
    )


# =====================================================================
# Exact historical post_ai_analysis.py reproduction
# =====================================================================


def _historical_session_indicators(
    *,
    events: list[Event],
    session_id: str,
) -> dict[str, object]:
    ordered_events = sorted(
        events,
        key=lambda event: event.event_num,
    )

    episodes = _build_historical_episodes(
        ordered_events,
        session_id,
    )

    _track_historical_retention(
        ordered_events,
        episodes,
    )

    _add_historical_temporal_features(
        ordered_events,
        episodes,
    )

    timestamps = [
        event.timestamp_ms
        for event in ordered_events
    ]

    duration_s = (
        (
            max(timestamps)
            - min(timestamps)
        )
        / 1000.0
        if len(timestamps) >= 2
        else math.nan
    )

    human_chars = sum(
        _delta_insert_length(event)
        for event in ordered_events
        if (
            event.event_name == "text-insert"
            and event.source == EventSource.USER
        )
    )

    ai_chars = sum(
        episode.ai_chars
        for episode in episodes
    )

    displayed = [
        episode
        for episode in episodes
        if episode.open_event_num is not None
    ]

    adopted = [
        episode
        for episode in displayed
        if episode.insertion_event_num is not None
    ]

    valid = [
        episode
        for episode in displayed
        if episode.response_use != "No Suggestion"
    ]

    request_times = [
        episode.request_timestamp
        for episode in episodes
    ]

    intervals = [
        (right - left) / 1000.0
        for left, right
        in zip(
            request_times[:-1],
            request_times[1:],
        )
    ]

    states = [
        episode.response_use
        for episode in valid
        if episode.response_use != "No Suggestion"
    ]

    pre_generation = [
        episode.pre_ai_generation
        for episode in episodes
    ]

    retention_values = [
        episode.retention
        for episode in adopted
        if episode.retention is not None
    ]

    post_edit_values = [
        episode.post_ai_edits
        for episode in displayed
    ]

    reconsult_values = [
        episode.reconsultation
        for episode in episodes[:-1]
    ]

    latency_values = [
        episode.response_latency_s
        for episode in displayed
        if episode.response_latency_s is not None
    ]

    return {
        "session_id": session_id,

        "human_generation_before_ai": (
            float(np.median(pre_generation))
            if pre_generation
            else math.nan
        ),

        "consultation_density": (
            len(episodes)
            / (duration_s / 60.0)
            if (
                math.isfinite(duration_s)
                and duration_s > 0
            )
            else math.nan
        ),

        "ai_contribution": (
            ai_chars
            / max(
                human_chars + ai_chars,
                1,
            )
        ),

        "ai_retention": (
            float(np.mean(retention_values))
            if adopted
            else math.nan
        ),

        "non_adoption": (
            sum(
                episode.response_use
                == "Non-Adoption"
                for episode in valid
            )
            / max(len(valid), 1)
        ),

        "post_ai_editing": (
            float(np.median(post_edit_values))
            if displayed
            else math.nan
        ),

        "reconsultation": (
            float(np.mean(reconsult_values))
            if len(episodes) > 1
            else math.nan
        ),

        "response_latency": (
            float(np.median(latency_values))
            if displayed
            else math.nan
        ),

        "transition_entropy": (
            _transition_entropy(states)
        ),

        "consultation_burstiness": (
            _burstiness(intervals)
        ),
    }


def _build_historical_episodes(
    events: list[Event],
    session_id: str,
) -> list[_HistoricalEpisode]:
    """
    Exact request-window logic from the original post_ai_analysis.py:

    - one episode per suggestion-get;
    - window ends at the next suggestion-get;
    - first suggestion-open in the window;
    - first suggestion-select in the window;
    - first API text-insert after that first selection.
    """

    request_indices = [
        index
        for index, event in enumerate(events)
        if event.event_name == "suggestion-get"
    ]

    episodes: list[_HistoricalEpisode] = []

    for order, start in enumerate(
        request_indices,
        start=1,
    ):
        end = (
            request_indices[order]
            if order < len(request_indices)
            else len(events)
        )

        window = events[start:end]
        request = events[start]

        episode = _HistoricalEpisode(
            session_id=session_id,
            episode_id=order,
            request_event_num=request.event_num,
            request_timestamp=request.timestamp_ms,
        )

        open_event = next(
            (
                event
                for event in window
                if event.event_name
                == "suggestion-open"
            ),
            None,
        )

        select_event = next(
            (
                event
                for event in window
                if event.event_name
                == "suggestion-select"
            ),
            None,
        )

        if open_event is not None:
            episode.open_event_num = (
                open_event.event_num
            )

            episode.open_timestamp = (
                open_event.timestamp_ms
            )

            meaningful = next(
                (
                    event
                    for event in window
                    if (
                        event.source
                        == EventSource.USER
                        and event.timestamp_ms
                        >= episode.open_timestamp
                        and event.event_name
                        in {
                            "suggestion-select",
                            "suggestion-close",
                            "text-insert",
                            "text-delete",
                            "cursor-forward",
                            "cursor-backward",
                        }
                    )
                ),
                None,
            )

            if meaningful is not None:
                episode.response_latency_s = (
                    (
                        meaningful.timestamp_ms
                        - episode.open_timestamp
                    )
                    / 1000.0
                )

        if select_event is not None:
            episode.select_event_num = (
                select_event.event_num
            )

            episode.select_timestamp = (
                select_event.timestamp_ms
            )

            insertion = next(
                (
                    event
                    for event in window
                    if (
                        event.event_name
                        == "text-insert"
                        and event.source
                        == EventSource.API
                        and event.event_num
                        > episode.select_event_num
                    )
                ),
                None,
            )

            if insertion is not None:
                episode.insertion_event_num = (
                    insertion.event_num
                )

                episode.insertion_timestamp = (
                    insertion.timestamp_ms
                )

                episode.ai_chars = (
                    _delta_insert_length(
                        insertion
                    )
                )

        episodes.append(
            episode
        )

    return episodes


# =====================================================================
# Historical pre/post temporal features
# =====================================================================


def _add_historical_temporal_features(
    events: list[Event],
    episodes: list[_HistoricalEpisode],
) -> None:
    request_times = [
        episode.request_timestamp
        for episode in episodes
    ]

    for index, episode in enumerate(
        episodes
    ):
        _classify_historical_pre_activity(
            events,
            episode,
        )

        anchor = (
            episode.insertion_timestamp
            or episode.open_timestamp
        )

        if anchor is not None:
            limit = min(
                anchor + POST_WINDOW_MS,
                (
                    request_times[index + 1]
                    if index + 1
                    < len(request_times)
                    else anchor
                    + POST_WINDOW_MS
                ),
            )

            episode.post_ai_edits = sum(
                1
                for event in events
                if (
                    anchor
                    < event.timestamp_ms
                    <= limit
                    and event.source
                    == EventSource.USER
                    and event.event_name
                    in {
                        "text-insert",
                        "text-delete",
                    }
                )
            )

        if index + 1 < len(episodes):
            episode.reconsultation = int(
                (
                    episodes[
                        index + 1
                    ].request_timestamp
                    - episode.request_timestamp
                )
                <= RECONSULT_MS
            )

        episode.response_use = (
            _classify_historical_response_use(
                episode
            )
        )


def _classify_historical_pre_activity(
    events: list[Event],
    episode: _HistoricalEpisode,
) -> None:
    start = (
        episode.request_timestamp
        - PRE_WINDOW_MS
    )

    window = [
        event
        for event in events
        if (
            start
            <= event.timestamp_ms
            < episode.request_timestamp
            and event.source
            == EventSource.USER
        )
    ]

    inserted = sum(
        _delta_insert_length(event)
        for event in window
        if event.event_name == "text-insert"
    )

    deleted = sum(
        _delta_delete_length(event)
        for event in window
        if event.event_name == "text-delete"
    )

    episode.pre_ai_generation = inserted
    episode.pre_ai_deletion = deleted


def _classify_historical_response_use(
    episode: _HistoricalEpisode,
) -> str:
    if episode.open_event_num is None:
        return "No Suggestion"

    if (
        episode.select_event_num is None
        or episode.insertion_event_num
        is None
    ):
        return "Non-Adoption"

    retention = (
        episode.retention
        if episode.retention is not None
        else 0.0
    )

    if retention >= DIRECT_RETENTION:
        return "Direct Retention"

    if retention >= SURFACE_REVISION:
        return "Surface Revision"

    if retention >= TRANSFORMATIVE_REVISION:
        return "Transformative Revision"

    return "Withdrawal"


# =====================================================================
# Historical AI-retention tracker
# =====================================================================


def _track_historical_retention(
    events: list[Event],
    episodes: list[_HistoricalEpisode],
) -> None:
    insertion_map = {
        episode.insertion_event_num:
            episode.episode_id
        for episode in episodes
        if episode.insertion_event_num
        is not None
    }

    intervals: dict[
        int,
        list[tuple[int, int]],
    ] = {}

    for event in events:
        if _event_has_delta(event):
            _apply_historical_delta(
                intervals,
                event,
                insertion_map.get(
                    event.event_num
                ),
            )

    by_id = {
        episode.episode_id:
            episode
        for episode in episodes
    }

    for episode_id, spans in intervals.items():
        episode = by_id[
            episode_id
        ]

        episode.retained_chars = sum(
            end - start
            for start, end
            in spans
        )

        episode.retention = (
            episode.retained_chars
            / episode.ai_chars
            if episode.ai_chars
            else None
        )


def _apply_historical_delta(
    intervals: dict[
        int,
        list[tuple[int, int]],
    ],
    event: Event,
    ai_episode: int | None,
) -> None:
    cursor = 0

    for op in _delta_ops(event):
        retain = _op_value(
            op,
            "retain",
        )

        if retain is not None:
            cursor += int(retain)

        inserted = _op_value(
            op,
            "insert",
        )

        # Exact historical behavior: only string inserts affect the
        # tracked text coordinate system.
        if isinstance(
            inserted,
            str,
        ):
            length = len(
                inserted
            )

            _update_intervals_insert(
                intervals,
                cursor,
                length,
            )

            if (
                ai_episode is not None
                and length > 0
            ):
                intervals.setdefault(
                    ai_episode,
                    [],
                ).append(
                    (
                        cursor,
                        cursor + length,
                    )
                )

            cursor += length

        deleted = _op_value(
            op,
            "delete",
        )

        if deleted is not None:
            _update_intervals_delete(
                intervals,
                cursor,
                int(deleted),
            )


def _update_intervals_insert(
    intervals: dict[
        int,
        list[tuple[int, int]],
    ],
    pos: int,
    length: int,
) -> None:
    if length <= 0:
        return

    for key, spans in list(
        intervals.items()
    ):
        updated: list[
            tuple[int, int]
        ] = []

        for start, end in spans:
            if pos <= start:
                updated.append(
                    (
                        start + length,
                        end + length,
                    )
                )

            elif start < pos < end:
                if start < pos:
                    updated.append(
                        (
                            start,
                            pos,
                        )
                    )

                if pos < end:
                    updated.append(
                        (
                            pos + length,
                            end + length,
                        )
                    )

            else:
                updated.append(
                    (
                        start,
                        end,
                    )
                )

        intervals[key] = updated


def _update_intervals_delete(
    intervals: dict[
        int,
        list[tuple[int, int]],
    ],
    pos: int,
    length: int,
) -> None:
    if length <= 0:
        return

    delete_end = (
        pos + length
    )

    for key, spans in list(
        intervals.items()
    ):
        updated: list[
            tuple[int, int]
        ] = []

        for start, end in spans:
            if end <= pos:
                updated.append(
                    (
                        start,
                        end,
                    )
                )

            elif start >= delete_end:
                updated.append(
                    (
                        start - length,
                        end - length,
                    )
                )

            else:
                if start < pos:
                    updated.append(
                        (
                            start,
                            pos,
                        )
                    )

                if end > delete_end:
                    updated.append(
                        (
                            pos,
                            end - length,
                        )
                    )

        intervals[key] = [
            (
                start,
                end,
            )
            for start, end
            in updated
            if end > start
        ]


# =====================================================================
# Historical statistics
# =====================================================================


def _transition_entropy(
    states: list[str],
) -> float:
    if len(states) < 2:
        return math.nan

    pairs = Counter(
        zip(
            states[:-1],
            states[1:],
        )
    )

    counts = np.asarray(
        list(
            pairs.values()
        ),
        dtype=float,
    )

    if counts.sum() == 0:
        return math.nan

    probabilities = (
        counts
        / counts.sum()
    )

    entropy = float(
        -(
            probabilities
            * np.log2(
                probabilities
            )
        ).sum()
    )

    return (
        entropy
        / math.log2(
            len(probabilities)
        )
        if len(probabilities) > 1
        else 0.0
    )


def _burstiness(
    values: list[float],
) -> float:
    if len(values) < 2:
        return math.nan

    array = np.asarray(
        values,
        dtype=float,
    )

    mean_value = array.mean()
    std_value = array.std(
        ddof=0
    )

    denominator = (
        std_value
        + mean_value
    )

    return (
        float(
            (
                std_value
                - mean_value
            )
            / denominator
        )
        if denominator > 0
        else math.nan
    )


# =====================================================================
# Quill delta helpers
# =====================================================================


def _event_has_delta(
    event: Event,
) -> bool:
    delta = getattr(
        event,
        "text_delta",
        None,
    )

    if delta is None:
        delta = getattr(
            event,
            "textDelta",
            None,
        )

    return (
        isinstance(delta, dict)
        or getattr(
            delta,
            "ops",
            None,
        )
        is not None
    )


def _delta_ops(
    event: Event,
) -> list:
    delta = getattr(
        event,
        "text_delta",
        None,
    )

    if delta is None:
        delta = getattr(
            event,
            "textDelta",
            None,
        )

    if delta is None:
        return []

    if isinstance(
        delta,
        dict,
    ):
        ops = delta.get(
            "ops",
            [],
        )
    else:
        ops = getattr(
            delta,
            "ops",
            None,
        )

    if ops is None:
        return []

    return list(
        ops
    )


def _op_value(
    op,
    name: str,
):
    if isinstance(
        op,
        dict,
    ):
        return op.get(
            name
        )

    return getattr(
        op,
        name,
        None,
    )


def _delta_insert_length(
    event: Event,
) -> int:
    total = 0

    for op in _delta_ops(
        event
    ):
        value = _op_value(
            op,
            "insert",
        )

        if isinstance(
            value,
            str,
        ):
            total += len(
                value
            )

    return total


def _delta_delete_length(
    event: Event,
) -> int:
    total = 0

    for op in _delta_ops(
        event
    ):
        value = _op_value(
            op,
            "delete",
        )

        if isinstance(
            value,
            (int, float),
        ):
            total += int(
                value
            )

    return total


# =====================================================================
# CSV / audit helpers
# =====================================================================


def _write_dict_rows(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    if not rows:
        raise ValueError(
            f"No rows to write to {path}."
        )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def _print_audit(
    *,
    paths: list[Path],
    total_episodes: int,
    total_selections: int,
    behavior_rows: list[
        dict[str, object]
    ],
    outcome_rows: list[
        dict[str, object]
    ],
    outcome_counts: Counter[str],
) -> None:
    print()
    print("=" * 82)
    print(
        "AgencyTrace — Target Behavior Export Audit"
    )
    print("=" * 82)

    print(
        f"Sessions processed              : {len(paths)}"
    )

    print(
        f"Behavior rows                   : {len(behavior_rows)}"
    )

    print(
        f"Suggestion episodes             : {total_episodes}"
    )

    print(
        f"Selection records               : {total_selections}"
    )

    print(
        f"Request outcomes                : {len(outcome_rows)}"
    )

    print()
    print(
        "FIVE-WAY REQUEST OUTCOMES"
    )
    print("-" * 82)

    for outcome in (
        OUTCOME_ACCEPT_UNCHANGED,
        OUTCOME_ACCEPTED_MODIFIED,
        OUTCOME_NON_ADOPTION,
        OUTCOME_PRESENTED_NO_SELECTION,
        OUTCOME_REQUEST_WITHOUT_SUGGESTION,
    ):
        actual = outcome_counts[
            outcome
        ]

        expected = EXPECTED_OUTCOMES[
            outcome
        ]

        difference = (
            actual - expected
        )

        print(
            f"{outcome:<30} "
            f"{actual:>6}  "
            f"reference={expected:>6}  "
            f"diff={difference:+d}"
        )

    print()

    sessions_ok = (
        len(paths)
        == EXPECTED_SESSIONS
    )

    requests_ok = (
        len(outcome_rows)
        == EXPECTED_REQUESTS
    )

    outcome_total_ok = (
        sum(
            outcome_counts.values()
        )
        == EXPECTED_REQUESTS
    )

    exact_reference = all(
        outcome_counts[outcome]
        == expected
        for outcome, expected
        in EXPECTED_OUTCOMES.items()
    )

    print(
        "Corpus session count             : "
        + (
            "PASS"
            if sessions_ok
            else "DIFF"
        )
    )

    print(
        "One outcome per request          : "
        + (
            "PASS"
            if requests_ok
            else "FAIL"
        )
    )

    print(
        "Outcome partition                : "
        + (
            "PASS"
            if outcome_total_ok
            else "FAIL"
        )
    )

    print(
        "Historical five-way replication : "
        + (
            "PASS"
            if exact_reference
            else "DIFF"
        )
    )

    print()
    print(
        f"Behavior CSV                    : {BEHAVIOR_OUTPUT}"
    )

    print(
        f"Request-outcome CSV             : {OUTCOME_OUTPUT}"
    )

    print()
    print("=" * 82)

    if not (
        requests_ok
        and outcome_total_ok
    ):
        raise SystemExit(
            "Target behavior export FAILED "
            "fundamental invariants."
        )

    print(
        "Target behavior export completed."
    )
    print("=" * 82)


if __name__ == "__main__":
    main()

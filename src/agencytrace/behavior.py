from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from statistics import median

from agencytrace.metrics import SelectionMetrics
from agencytrace.models import (
    Event,
    EventSource,
    SuggestionEpisode,
)


# =====================================================================
# Canonical historical five-outcome vocabulary
# =====================================================================

OUTCOME_ACCEPT_UNCHANGED = "accept_unchanged"
OUTCOME_ACCEPTED_MODIFIED = "accepted_modified"
OUTCOME_NON_ADOPTION = "non_adoption"
OUTCOME_PRESENTED_NO_SELECTION = "presented_no_selection"
OUTCOME_REQUEST_WITHOUT_SUGGESTION = "request_without_suggestion"


OUTCOME_ORDER = (
    OUTCOME_ACCEPT_UNCHANGED,
    OUTCOME_ACCEPTED_MODIFIED,
    OUTCOME_NON_ADOPTION,
    OUTCOME_PRESENTED_NO_SELECTION,
    OUTCOME_REQUEST_WITHOUT_SUGGESTION,
)


OUTCOME_LABELS = {
    OUTCOME_ACCEPT_UNCHANGED: "Direct Adoption",
    OUTCOME_ACCEPTED_MODIFIED: "Modified Adoption",
    OUTCOME_NON_ADOPTION: "Non-Adoption",
    OUTCOME_PRESENTED_NO_SELECTION: "No Selection",
    OUTCOME_REQUEST_WITHOUT_SUGGESTION: "No Suggestion",
}


# =====================================================================
# Temporal constants
# =====================================================================

POST_AI_WINDOW_MS = 30_000
RECONSULTATION_WINDOW_MS = 60_000


# =====================================================================
# Session-level target metrics
# =====================================================================


@dataclass(frozen=True, slots=True)
class TargetBehaviorMetrics:
    session_id: str

    human_generation_before_ai: float
    consultation_density: float
    ai_contribution: float
    ai_retention: float | None
    non_adoption: float | None
    post_ai_editing: float | None
    reconsultation: float | None
    response_latency: float | None
    transition_entropy: float | None
    consultation_burstiness: float | None


# =====================================================================
# Request outcome
# =====================================================================


@dataclass(frozen=True, slots=True)
class RequestOutcome:
    """
    One mutually exclusive historical outcome for one suggestion-get.
    """

    session_id: str
    request_id: str

    request_event_num: int
    open_event_num: int | None

    selection_count: int
    outcome: str

    @property
    def figure_label(self) -> str:
        return OUTCOME_LABELS[self.outcome]


# =====================================================================
# Historical five-way classifier
# =====================================================================


def classify_request_outcomes(
    *,
    events: list[Event],
    episodes: list[SuggestionEpisode],
    selection_metrics: list[SelectionMetrics],
) -> list[RequestOutcome]:
    """
    Reproduce the historical CoAuthor episode classifier used for
    outputs/analysis/suggestion_episodes.csv.

    For each suggestion-get window:

        open_event  = first suggestion-open
        select      = first suggestion-select
        close       = first suggestion-close

    If selected:
        recover the selected candidate from the FIRST open event using
        currentHoverIndex from the select event;

        recover the FIRST non-empty API text-insert after the selection
        inside the same request window;

        selected_text == inserted_text
            -> accept_unchanged

        otherwise
            -> accepted_modified

    If not selected:
        open + USER close
            -> non_adoption

        open without USER close
            -> presented_no_selection

        no open
            -> request_without_suggestion

    selection_metrics is retained in the signature for compatibility
    with the rest of AgencyTrace but is intentionally not used by this
    historical classification layer.
    """

    del selection_metrics

    ordered_events = sorted(
        events,
        key=lambda event: (
            event.event_num,
            event.timestamp_ms,
        ),
    )

    request_positions = [
        index
        for index, event in enumerate(
            ordered_events
        )
        if event.event_name == "suggestion-get"
    ]

    episode_by_request_event = {
        episode.request_event_num: episode
        for episode in episodes
    }

    results: list[RequestOutcome] = []

    for request_index, start in enumerate(
        request_positions
    ):
        stop = (
            request_positions[
                request_index + 1
            ]
            if (
                request_index + 1
                < len(request_positions)
            )
            else len(ordered_events)
        )

        window = ordered_events[
            start:stop
        ]

        request_event = window[0]

        episode = episode_by_request_event.get(
            request_event.event_num
        )

        if episode is None:
            raise RuntimeError(
                "No reconstructed episode for "
                f"suggestion-get event "
                f"{request_event.event_num}."
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

        close_event = next(
            (
                event
                for event in window
                if event.event_name
                == "suggestion-close"
            ),
            None,
        )

        selected_text: str | None = None
        inserted_text: str | None = None

        if select_event is not None:
            selected_index = _hover_index(
                select_event
            )

            selected_text = _selected_suggestion(
                open_event,
                selected_index,
            )

            insertion_event = next(
                (
                    event
                    for event in window
                    if (
                        event.event_num
                        > select_event.event_num
                        and event.event_name
                        == "text-insert"
                        and event.source
                        == EventSource.API
                        and _event_inserted_text(
                            event
                        ).strip()
                    )
                ),
                None,
            )

            if insertion_event is not None:
                inserted_text = (
                    _event_inserted_text(
                        insertion_event
                    ).strip()
                )

        # -------------------------------------------------------------
        # Exact historical decision tree
        # -------------------------------------------------------------

        if (
            select_event is not None
            and inserted_text
        ):
            if selected_text == inserted_text:
                outcome = (
                    OUTCOME_ACCEPT_UNCHANGED
                )
            else:
                outcome = (
                    OUTCOME_ACCEPTED_MODIFIED
                )

        elif (
            open_event is not None
            and close_event is not None
            and close_event.source
            == EventSource.USER
        ):
            outcome = OUTCOME_NON_ADOPTION

        elif open_event is not None:
            outcome = (
                OUTCOME_PRESENTED_NO_SELECTION
            )

        else:
            outcome = (
                OUTCOME_REQUEST_WITHOUT_SUGGESTION
            )

        results.append(
            RequestOutcome(
                session_id=episode.session_id,
                request_id=episode.request_id,

                request_event_num=(
                    episode.request_event_num
                ),

                open_event_num=(
                    open_event.event_num
                    if open_event is not None
                    else None
                ),

                selection_count=(
                    1
                    if select_event is not None
                    else 0
                ),

                outcome=outcome,
            )
        )

    if len(results) != len(
        episodes
    ):
        raise RuntimeError(
            "Historical request classification "
            "did not preserve one outcome per "
            "suggestion-get: "
            f"{len(results)} outcomes for "
            f"{len(episodes)} episodes."
        )

    return results


# =====================================================================
# Historical selected candidate extraction
# =====================================================================


def _hover_index(
    event: Event | None,
) -> int | None:
    if event is None:
        return None

    value = event.current_hover_index

    if (
        value is None
        or value == ""
    ):
        return None

    try:
        return int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def _selected_suggestion(
    open_event: Event | None,
    selected_index: int | None,
) -> str | None:
    """
    Historical behavior:

    Candidate list comes from the FIRST suggestion-open event.
    Selection index comes from currentHoverIndex of the select event.
    """

    if (
        open_event is None
        or selected_index is None
    ):
        return None

    candidates = getattr(
        open_event,
        "current_suggestions",
        None,
    )

    if not candidates:
        return None

    if not (
        0
        <= selected_index
        < len(candidates)
    ):
        return None

    candidate = candidates[
        selected_index
    ]

    if isinstance(
        candidate,
        str,
    ):
        return candidate

    if isinstance(
        candidate,
        dict,
    ):
        value = (
            candidate.get("trimmed")
            or candidate.get("original")
        )

        return (
            str(value)
            if value is not None
            else None
        )

    trimmed = getattr(
        candidate,
        "trimmed",
        None,
    )

    if trimmed:
        return str(
            trimmed
        )

    original = getattr(
        candidate,
        "original",
        None,
    )

    if original:
        return str(
            original
        )

    return None


# =====================================================================
# Session-level target behavioral indicators
# =====================================================================


def compute_target_behavior_metrics(
    *,
    events: list[Event],
    episodes: list[SuggestionEpisode],
    selection_metrics: list[SelectionMetrics],
    human_generation_before_ai: float,
    consultation_density: float,
    ai_contribution: float,
    ai_retention: float | None,
    consultation_burstiness: float | None,
) -> TargetBehaviorMetrics:

    if events:
        session_id = events[0].session_id
    elif episodes:
        session_id = episodes[0].session_id
    else:
        session_id = ""

    outcomes = classify_request_outcomes(
        events=events,
        episodes=episodes,
        selection_metrics=selection_metrics,
    )

    non_adoption = _non_adoption_rate(
        outcomes
    )

    post_ai_editing = _post_ai_editing(
        events=events,
        episodes=episodes,
    )

    reconsultation = _reconsultation_rate(
        episodes
    )

    response_latency = _response_latency(
        events=events,
        episodes=episodes,
    )

    transition_entropy = (
        _transition_entropy(
            outcomes
        )
    )

    return TargetBehaviorMetrics(
        session_id=session_id,

        human_generation_before_ai=float(
            human_generation_before_ai
        ),

        consultation_density=float(
            consultation_density
        ),

        ai_contribution=float(
            ai_contribution
        ),

        ai_retention=(
            float(ai_retention)
            if ai_retention is not None
            else None
        ),

        non_adoption=non_adoption,

        post_ai_editing=post_ai_editing,

        reconsultation=reconsultation,

        response_latency=response_latency,

        transition_entropy=transition_entropy,

        consultation_burstiness=(
            float(
                consultation_burstiness
            )
            if consultation_burstiness
            is not None
            else None
        ),
    )


# =====================================================================
# Indicator helpers
# =====================================================================


def _non_adoption_rate(
    outcomes: list[RequestOutcome],
) -> float | None:

    displayed = [
        row
        for row in outcomes
        if row.outcome
        != OUTCOME_REQUEST_WITHOUT_SUGGESTION
    ]

    if not displayed:
        return None

    return (
        sum(
            row.outcome
            == OUTCOME_NON_ADOPTION
            for row in displayed
        )
        / len(displayed)
    )


def _post_ai_editing(
    *,
    events: list[Event],
    episodes: list[SuggestionEpisode],
) -> float | None:

    ordered_events = sorted(
        events,
        key=lambda event: (
            event.event_num,
            event.timestamp_ms,
        ),
    )

    ordered_episodes = sorted(
        episodes,
        key=lambda episode: (
            episode.request_timestamp_ms,
            episode.request_event_num,
        ),
    )

    values: list[int] = []

    event_by_num = {
        event.event_num: event
        for event in ordered_events
    }

    for index, episode in enumerate(
        ordered_episodes
    ):
        if episode.open_event_num is None:
            continue

        anchor_event_num = (
            _episode_anchor_event_num(
                episode
            )
        )

        anchor_event = event_by_num.get(
            anchor_event_num
        )

        if anchor_event is None:
            continue

        anchor_timestamp = (
            anchor_event.timestamp_ms
        )

        limit_timestamp = (
            anchor_timestamp
            + POST_AI_WINDOW_MS
        )

        if (
            index + 1
            < len(ordered_episodes)
        ):
            limit_timestamp = min(
                limit_timestamp,
                ordered_episodes[
                    index + 1
                ].request_timestamp_ms,
            )

        edit_count = sum(
            1
            for event in ordered_events
            if (
                anchor_timestamp
                < event.timestamp_ms
                <= limit_timestamp
                and event.source
                == EventSource.USER
                and event.event_name
                in {
                    "text-insert",
                    "text-delete",
                }
            )
        )

        values.append(
            edit_count
        )

    if not values:
        return None

    return float(
        median(values)
    )


def _reconsultation_rate(
    episodes: list[SuggestionEpisode],
) -> float | None:

    if len(episodes) < 2:
        return None

    ordered = sorted(
        episodes,
        key=lambda episode: (
            episode.request_timestamp_ms,
            episode.request_event_num,
        ),
    )

    flags = [
        int(
            (
                next_episode.request_timestamp_ms
                - current.request_timestamp_ms
            )
            <= RECONSULTATION_WINDOW_MS
        )
        for current, next_episode
        in zip(
            ordered[:-1],
            ordered[1:],
        )
    ]

    if not flags:
        return None

    return (
        sum(flags)
        / len(flags)
    )


def _response_latency(
    *,
    events: list[Event],
    episodes: list[SuggestionEpisode],
) -> float | None:

    ordered_events = sorted(
        events,
        key=lambda event: (
            event.event_num,
            event.timestamp_ms,
        ),
    )

    ordered_episodes = sorted(
        episodes,
        key=lambda episode: (
            episode.request_event_num
        ),
    )

    event_by_num = {
        event.event_num: event
        for event in ordered_events
    }

    meaningful_names = {
        "suggestion-select",
        "suggestion-close",
        "text-insert",
        "text-delete",
        "cursor-forward",
        "cursor-backward",
    }

    latencies: list[float] = []

    for index, episode in enumerate(
        ordered_episodes
    ):
        if episode.open_event_num is None:
            continue

        open_event = event_by_num.get(
            episode.open_event_num
        )

        if open_event is None:
            continue

        next_request_num = (
            ordered_episodes[
                index + 1
            ].request_event_num
            if (
                index + 1
                < len(ordered_episodes)
            )
            else None
        )

        response_event = next(
            (
                event
                for event in ordered_events
                if (
                    event.event_num
                    >= open_event.event_num
                    and (
                        next_request_num is None
                        or event.event_num
                        < next_request_num
                    )
                    and event.source
                    == EventSource.USER
                    and event.event_name
                    in meaningful_names
                    and event.timestamp_ms
                    >= open_event.timestamp_ms
                )
            ),
            None,
        )

        if response_event is None:
            continue

        latency = (
            response_event.timestamp_ms
            - open_event.timestamp_ms
        ) / 1000.0

        if latency >= 0:
            latencies.append(
                latency
            )

    if not latencies:
        return None

    return float(
        median(latencies)
    )


def _transition_entropy(
    outcomes: list[RequestOutcome],
) -> float | None:

    states = [
        row.outcome
        for row in outcomes
        if row.outcome
        != OUTCOME_REQUEST_WITHOUT_SUGGESTION
    ]

    if len(states) < 2:
        return None

    transitions = Counter(
        zip(
            states[:-1],
            states[1:],
        )
    )

    total = sum(
        transitions.values()
    )

    if total <= 0:
        return None

    probabilities = [
        count / total
        for count
        in transitions.values()
    ]

    entropy = -sum(
        probability
        * math.log2(
            probability
        )
        for probability
        in probabilities
        if probability > 0
    )

    transition_types = len(
        probabilities
    )

    if transition_types <= 1:
        return 0.0

    return (
        entropy
        / math.log2(
            transition_types
        )
    )


# =====================================================================
# Event helpers
# =====================================================================


def _episode_anchor_event_num(
    episode: SuggestionEpisode,
) -> int:

    insertion_event_num = getattr(
        episode,
        "insertion_event_num",
        None,
    )

    if insertion_event_num is not None:
        return int(
            insertion_event_num
        )

    if episode.open_event_num is not None:
        return int(
            episode.open_event_num
        )

    return int(
        episode.request_event_num
    )


def _event_inserted_text(
    event: Event,
) -> str:

    delta = getattr(
        event,
        "text_delta",
        None,
    )

    if delta is None:
        return ""

    if isinstance(
        delta,
        dict,
    ):
        ops = delta.get(
            "ops",
            []
        )
    else:
        ops = getattr(
            delta,
            "ops",
            None,
        )

        if ops is None:
            return ""

    pieces: list[str] = []

    for op in ops:
        if isinstance(
            op,
            dict,
        ):
            inserted = op.get(
                "insert"
            )
        else:
            inserted = getattr(
                op,
                "insert",
                None,
            )

        if isinstance(
            inserted,
            str,
        ):
            pieces.append(
                inserted
            )

    return "".join(
        pieces
    )
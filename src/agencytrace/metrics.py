from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import median
from typing import Iterable

from agencytrace.models import (
    Event,
    EventSource,
    SuggestionEpisode,
)
from agencytrace.provenance import (
    HUMAN_ORIGIN,
    SYSTEM_ORIGIN,
    ProvenanceResult,
)


DIRECT_ADOPTION = "direct_adoption"
MODIFIED_ADOPTION = "modified_adoption"
NON_ADOPTION = "non_adoption"


@dataclass(frozen=True, slots=True)
class SelectionMetrics:
    """
    Behavioral metrics for one selected AI suggestion.

    Adoption outcomes are derived from final text provenance.

    direct_adoption
        All AI-origin characters survive and remain one uninterrupted
        selection-specific span in the final document.

    modified_adoption
        Some AI-origin text survives, but at least one character was
        deleted or another provenance unit was inserted inside the
        surviving AI span.

    non_adoption
        No AI-origin textual character from the selection survives.

    The labels describe observable text behavior and do not infer user
    intention.
    """

    session_id: str
    request_id: str
    selection_id: str

    request_event_num: int
    selection_event_num: int
    insert_event_num: int | None

    selected_index: int | None

    inserted_chars: int
    surviving_chars: int
    deleted_chars: int

    retention_ratio: float
    deletion_ratio: float

    final_span_start: int | None
    final_span_end: int | None
    final_span_units: int

    intervening_units: int
    survives_contiguously: bool

    adoption_outcome: str

    request_to_selection_ms: int | None
    open_to_selection_ms: int | None


@dataclass(frozen=True, slots=True)
class SessionMetrics:
    """
    Session-level behavioral measurements derived from validated
    lifecycle reconstruction and character provenance.
    """

    session_id: str

    # ------------------------------------------------------------------
    # Final document composition
    # ------------------------------------------------------------------

    final_text_chars: int

    final_ai_chars: int
    final_human_chars: int
    final_system_chars: int
    final_other_chars: int

    authored_text_chars: int

    # AI / (AI + human)
    ai_share: float

    # AI / complete reconstructed textual document
    document_ai_share: float

    # ------------------------------------------------------------------
    # AI provenance
    # ------------------------------------------------------------------

    ai_inserted_chars: int
    ai_surviving_chars: int
    ai_deleted_chars: int

    ai_retention_ratio: float
    ai_deletion_ratio: float

    # ------------------------------------------------------------------
    # Suggestion lifecycle
    # ------------------------------------------------------------------

    suggestion_requests: int
    suggestion_opens: int
    suggestion_reopens: int
    suggestion_selections: int
    suggestion_insertions: int

    dismissed_episodes: int
    multi_selection_episodes: int

    selection_rate: float

    # ------------------------------------------------------------------
    # Adoption outcomes
    # ------------------------------------------------------------------

    direct_adoptions: int
    modified_adoptions: int
    non_adoptions: int

    direct_adoption_share: float
    modified_adoption_share: float
    non_adoption_share: float

    # ------------------------------------------------------------------
    # Human writing
    # ------------------------------------------------------------------

    human_inserted_chars: int

    human_chars_before_first_ai: int
    human_generation_before_ai_ratio: float

    # ------------------------------------------------------------------
    # Consultation behavior
    # ------------------------------------------------------------------

    consultation_density_per_1000_authored_chars: float

    median_request_to_selection_ms: float | None
    median_open_to_selection_ms: float | None
    mean_request_to_selection_ms: float | None

    consultation_burstiness: float | None

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    session_duration_ms: int | None


# ======================================================================
# Public API
# ======================================================================


def compute_selection_metrics(
    episodes: Iterable[SuggestionEpisode],
    provenance: ProvenanceResult,
) -> list[SelectionMetrics]:
    """
    Derive one behavioral row for every reconstructed AI selection.
    """

    rows: list[SelectionMetrics] = []

    final_positions = _index_final_selection_positions(
        provenance
    )

    for episode in episodes:
        for selection in episode.selections:
            stats = provenance.selections.get(
                selection.selection_id
            )

            if stats is None:
                continue

            inserted = stats.inserted_chars
            surviving = stats.surviving_chars
            deleted = stats.deleted_chars

            positions = final_positions.get(
                selection.selection_id,
                [],
            )

            (
                span_start,
                span_end,
                span_units,
                intervening_units,
                contiguous,
            ) = _selection_span_metrics(
                selection_id=selection.selection_id,
                positions=positions,
                provenance=provenance,
            )

            outcome = classify_adoption(
                inserted_chars=inserted,
                surviving_chars=surviving,
                survives_contiguously=contiguous,
            )

            rows.append(
                SelectionMetrics(
                    session_id=episode.session_id,
                    request_id=episode.request_id,
                    selection_id=selection.selection_id,

                    request_event_num=(
                        episode.request_event_num
                    ),

                    selection_event_num=(
                        selection.event_num
                    ),

                    insert_event_num=(
                        selection.insert_event_num
                    ),

                    selected_index=(
                        selection.selected_index
                    ),

                    inserted_chars=inserted,
                    surviving_chars=surviving,
                    deleted_chars=deleted,

                    retention_ratio=_safe_ratio(
                        surviving,
                        inserted,
                    ),

                    deletion_ratio=_safe_ratio(
                        deleted,
                        inserted,
                    ),

                    final_span_start=span_start,
                    final_span_end=span_end,
                    final_span_units=span_units,

                    intervening_units=(
                        intervening_units
                    ),

                    survives_contiguously=(
                        contiguous
                    ),

                    adoption_outcome=outcome,

                    request_to_selection_ms=(
                        selection.request_to_selection_ms
                    ),

                    open_to_selection_ms=(
                        selection.open_to_selection_ms
                    ),
                )
            )

    return rows


def compute_session_metrics(
    events: list[Event],
    episodes: list[SuggestionEpisode],
    provenance: ProvenanceResult,
) -> SessionMetrics:
    """
    Derive one session-level behavioral feature vector.
    """

    selection_rows = compute_selection_metrics(
        episodes,
        provenance,
    )

    # ------------------------------------------------------------------
    # Final provenance composition
    # ------------------------------------------------------------------

    final_text_chars = (
        provenance.final_text_chars
    )

    final_ai_chars = (
        provenance.final_ai_chars
    )

    final_human_chars = (
        provenance.final_human_chars
    )

    final_system_chars = 0
    final_other_chars = 0

    for unit in provenance.final_units:
        if unit.is_embed:
            continue

        if unit.selection_id is not None:
            continue

        if unit.origin == HUMAN_ORIGIN:
            continue

        if unit.origin == SYSTEM_ORIGIN:
            final_system_chars += 1
        else:
            final_other_chars += 1

    authored_text_chars = (
        final_ai_chars
        + final_human_chars
    )

    ai_share = _safe_ratio(
        final_ai_chars,
        authored_text_chars,
    )

    document_ai_share = _safe_ratio(
        final_ai_chars,
        final_text_chars,
    )

    # ------------------------------------------------------------------
    # AI provenance
    # ------------------------------------------------------------------

    ai_inserted_chars = sum(
        row.inserted_chars
        for row in selection_rows
    )

    ai_surviving_chars = sum(
        row.surviving_chars
        for row in selection_rows
    )

    ai_deleted_chars = sum(
        row.deleted_chars
        for row in selection_rows
    )

    ai_retention_ratio = _safe_ratio(
        ai_surviving_chars,
        ai_inserted_chars,
    )

    ai_deletion_ratio = _safe_ratio(
        ai_deleted_chars,
        ai_inserted_chars,
    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    suggestion_requests = len(
        episodes
    )

    suggestion_opens = sum(
        episode.open_event_num is not None
        for episode in episodes
    )

    suggestion_reopens = sum(
        len(
            episode.reopen_event_nums
        )
        for episode in episodes
    )

    suggestion_selections = len(
        selection_rows
    )

    suggestion_insertions = sum(
        row.insert_event_num is not None
        for row in selection_rows
    )

    dismissed_episodes = sum(
        episode.was_dismissed
        for episode in episodes
    )

    multi_selection_episodes = sum(
        len(episode.selections) > 1
        for episode in episodes
    )

    selection_rate = _safe_ratio(
        suggestion_selections,
        suggestion_requests,
    )

    # ------------------------------------------------------------------
    # Adoption outcomes
    # ------------------------------------------------------------------

    direct_adoptions = sum(
        row.adoption_outcome
        == DIRECT_ADOPTION
        for row in selection_rows
    )

    modified_adoptions = sum(
        row.adoption_outcome
        == MODIFIED_ADOPTION
        for row in selection_rows
    )

    non_adoptions = sum(
        row.adoption_outcome
        == NON_ADOPTION
        for row in selection_rows
    )

    adoption_total = (
        direct_adoptions
        + modified_adoptions
        + non_adoptions
    )

    direct_adoption_share = (
        _safe_ratio(
            direct_adoptions,
            adoption_total,
        )
    )

    modified_adoption_share = (
        _safe_ratio(
            modified_adoptions,
            adoption_total,
        )
    )

    non_adoption_share = (
        _safe_ratio(
            non_adoptions,
            adoption_total,
        )
    )

    # ------------------------------------------------------------------
    # Human text generation
    # ------------------------------------------------------------------

    human_inserted_chars = sum(
        _text_insert_length(
            event.text_delta
        )
        for event in events
        if (
            event.event_name
            == "text-insert"
            and event.source
            == EventSource.USER
        )
    )

    first_ai_event_num = (
        _first_ai_insert_event_num(
            selection_rows
        )
    )

    if first_ai_event_num is None:
        human_chars_before_first_ai = (
            human_inserted_chars
        )
    else:
        human_chars_before_first_ai = sum(
            _text_insert_length(
                event.text_delta
            )
            for event in events
            if (
                event.event_name
                == "text-insert"
                and event.source
                == EventSource.USER
                and event.event_num
                < first_ai_event_num
            )
        )

    human_generation_before_ai_ratio = (
        _safe_ratio(
            human_chars_before_first_ai,
            human_inserted_chars,
        )
    )

    # ------------------------------------------------------------------
    # Consultation density
    # ------------------------------------------------------------------

    if authored_text_chars > 0:
        consultation_density = (
            suggestion_requests
            / authored_text_chars
            * 1000.0
        )
    else:
        consultation_density = 0.0

    # ------------------------------------------------------------------
    # Selection latency
    # ------------------------------------------------------------------

    request_to_selection = [
        row.request_to_selection_ms
        for row in selection_rows
        if (
            row.request_to_selection_ms
            is not None
            and row.request_to_selection_ms
            >= 0
        )
    ]

    open_to_selection = [
        row.open_to_selection_ms
        for row in selection_rows
        if (
            row.open_to_selection_ms
            is not None
            and row.open_to_selection_ms
            >= 0
        )
    ]

    if request_to_selection:
        median_request_to_selection_ms = (
            float(
                median(
                    request_to_selection
                )
            )
        )

        mean_request_to_selection_ms = (
            sum(
                request_to_selection
            )
            / len(
                request_to_selection
            )
        )
    else:
        median_request_to_selection_ms = None
        mean_request_to_selection_ms = None

    if open_to_selection:
        median_open_to_selection_ms = (
            float(
                median(
                    open_to_selection
                )
            )
        )
    else:
        median_open_to_selection_ms = None

    # ------------------------------------------------------------------
    # Consultation burstiness
    # ------------------------------------------------------------------

    request_timestamps = sorted(
        episode.request_timestamp_ms
        for episode in episodes
    )

    consultation_burstiness = (
        _burstiness(
            request_timestamps
        )
    )

    session_duration_ms = (
        _session_duration_ms(
            events
        )
    )

    return SessionMetrics(
        session_id=(
            provenance.session_id
        ),

        final_text_chars=(
            final_text_chars
        ),

        final_ai_chars=(
            final_ai_chars
        ),

        final_human_chars=(
            final_human_chars
        ),

        final_system_chars=(
            final_system_chars
        ),

        final_other_chars=(
            final_other_chars
        ),

        authored_text_chars=(
            authored_text_chars
        ),

        ai_share=(
            ai_share
        ),

        document_ai_share=(
            document_ai_share
        ),

        ai_inserted_chars=(
            ai_inserted_chars
        ),

        ai_surviving_chars=(
            ai_surviving_chars
        ),

        ai_deleted_chars=(
            ai_deleted_chars
        ),

        ai_retention_ratio=(
            ai_retention_ratio
        ),

        ai_deletion_ratio=(
            ai_deletion_ratio
        ),

        suggestion_requests=(
            suggestion_requests
        ),

        suggestion_opens=(
            suggestion_opens
        ),

        suggestion_reopens=(
            suggestion_reopens
        ),

        suggestion_selections=(
            suggestion_selections
        ),

        suggestion_insertions=(
            suggestion_insertions
        ),

        dismissed_episodes=(
            dismissed_episodes
        ),

        multi_selection_episodes=(
            multi_selection_episodes
        ),

        selection_rate=(
            selection_rate
        ),

        direct_adoptions=(
            direct_adoptions
        ),

        modified_adoptions=(
            modified_adoptions
        ),

        non_adoptions=(
            non_adoptions
        ),

        direct_adoption_share=(
            direct_adoption_share
        ),

        modified_adoption_share=(
            modified_adoption_share
        ),

        non_adoption_share=(
            non_adoption_share
        ),

        human_inserted_chars=(
            human_inserted_chars
        ),

        human_chars_before_first_ai=(
            human_chars_before_first_ai
        ),

        human_generation_before_ai_ratio=(
            human_generation_before_ai_ratio
        ),

        consultation_density_per_1000_authored_chars=(
            consultation_density
        ),

        median_request_to_selection_ms=(
            median_request_to_selection_ms
        ),

        median_open_to_selection_ms=(
            median_open_to_selection_ms
        ),

        mean_request_to_selection_ms=(
            mean_request_to_selection_ms
        ),

        consultation_burstiness=(
            consultation_burstiness
        ),

        session_duration_ms=(
            session_duration_ms
        ),
    )


def classify_adoption(
    *,
    inserted_chars: int,
    surviving_chars: int,
    survives_contiguously: bool,
) -> str:
    """
    Classify one selected AI suggestion.

    Direct adoption requires both complete retention and an uninterrupted
    final selection-specific span.

    Any surviving but structurally altered selection is modified adoption.
    """

    if inserted_chars <= 0:
        return NON_ADOPTION

    if surviving_chars <= 0:
        return NON_ADOPTION

    if (
        surviving_chars
        == inserted_chars
        and survives_contiguously
    ):
        return DIRECT_ADOPTION

    return MODIFIED_ADOPTION


def session_metrics_to_dict(
    metrics: SessionMetrics,
) -> dict[str, object]:
    return asdict(
        metrics
    )


def selection_metrics_to_dict(
    metrics: SelectionMetrics,
) -> dict[str, object]:
    return asdict(
        metrics
    )


# ======================================================================
# Final-layout helpers
# ======================================================================


def _index_final_selection_positions(
    provenance: ProvenanceResult,
) -> dict[
    str,
    list[int],
]:
    """
    Index final logical-unit positions belonging to each AI selection.

    Logical positions include embeds so an embed inserted inside AI text
    correctly breaks the AI span.
    """

    positions: dict[
        str,
        list[int],
    ] = {}

    for index, unit in enumerate(
        provenance.final_units
    ):
        if unit.selection_id is None:
            continue

        positions.setdefault(
            unit.selection_id,
            [],
        ).append(
            index
        )

    return positions


def _selection_span_metrics(
    *,
    selection_id: str,
    positions: list[int],
    provenance: ProvenanceResult,
) -> tuple[
    int | None,
    int | None,
    int,
    int,
    bool,
]:
    """
    Characterize the final span occupied by one AI selection.

    Returns
    -------
    start
        Inclusive logical-unit start position.

    end
        Exclusive logical-unit end position.

    span_units
        Number of logical units from first to last surviving selection
        character.

    intervening_units
        Units inside that span that do not belong to this selection.

    contiguous
        True only when every unit from first to last surviving AI
        character belongs to the same selection.
    """

    if not positions:
        return (
            None,
            None,
            0,
            0,
            False,
        )

    start = positions[0]
    end = positions[-1] + 1

    span = provenance.final_units[
        start:end
    ]

    span_units = len(
        span
    )

    intervening_units = sum(
        unit.selection_id
        != selection_id
        for unit in span
    )

    contiguous = (
        intervening_units == 0
    )

    return (
        start,
        end,
        span_units,
        intervening_units,
        contiguous,
    )


# ======================================================================
# Generic helpers
# ======================================================================


def _safe_ratio(
    numerator: int | float,
    denominator: int | float,
) -> float:
    if denominator <= 0:
        return 0.0

    return float(
        numerator
        / denominator
    )


def _text_insert_length(
    delta: object,
) -> int:
    if not isinstance(
        delta,
        dict,
    ):
        return 0

    ops = delta.get(
        "ops"
    )

    if not isinstance(
        ops,
        list,
    ):
        return 0

    total = 0

    for op in ops:
        if not isinstance(
            op,
            dict,
        ):
            continue

        value = op.get(
            "insert"
        )

        if isinstance(
            value,
            str,
        ):
            total += len(
                value
            )

    return total


def _first_ai_insert_event_num(
    rows: Iterable[
        SelectionMetrics
    ],
) -> int | None:
    event_nums = [
        row.insert_event_num
        for row in rows
        if row.insert_event_num
        is not None
    ]

    if not event_nums:
        return None

    return min(
        event_nums
    )


def _session_duration_ms(
    events: list[Event],
) -> int | None:
    if len(events) < 2:
        return None

    timestamps = [
        event.timestamp_ms
        for event in events
    ]

    start = min(
        timestamps
    )

    end = max(
        timestamps
    )

    duration = (
        end - start
    )

    if duration < 0:
        return None

    return duration


def _burstiness(
    timestamps_ms: list[int],
) -> float | None:
    """
    Consultation burstiness:

        B = (sigma - mu) / (sigma + mu)

    At least two inter-request intervals are required.
    """

    if len(
        timestamps_ms
    ) < 3:
        return None

    ordered = sorted(
        timestamps_ms
    )

    intervals = [
        later - earlier
        for earlier, later
        in zip(
            ordered,
            ordered[1:],
        )
        if later >= earlier
    ]

    if len(
        intervals
    ) < 2:
        return None

    mean_interval = (
        sum(
            intervals
        )
        / len(
            intervals
        )
    )

    variance = (
        sum(
            (
                interval
                - mean_interval
            )
            ** 2
            for interval in intervals
        )
        / len(
            intervals
        )
    )

    sigma = math.sqrt(
        variance
    )

    denominator = (
        sigma
        + mean_interval
    )

    if denominator == 0:
        return 0.0

    return (
        sigma
        - mean_interval
    ) / denominator
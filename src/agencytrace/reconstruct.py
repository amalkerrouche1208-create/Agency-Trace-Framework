from __future__ import annotations

from collections import deque

from agencytrace.models import (
    Event,
    EventSource,
    SuggestionEpisode,
    SuggestionSelection,
)


def reconstruct_suggestion_episodes(
    events: list[Event],
) -> list[SuggestionEpisode]:
    """
    Reconstruct CoAuthor suggestion lifecycles from an event stream.

    CoAuthor suggestion interaction is asynchronous:

    - several suggestion requests may temporarily overlap;
    - a suggestion set can be reopened;
    - one request can therefore produce multiple selections;
    - every selection can subsequently generate its own API insertion.

    Reconstruction consequently tracks:

    1. pending requests waiting for ``suggestion-open``;
    2. the suggestion episode currently displayed;
    3. selections waiting for their corresponding API insertion.

    Invariants
    ----------
    - One ``suggestion-get`` creates exactly one SuggestionEpisode.
    - One ``suggestion-select`` creates exactly one SuggestionSelection.
    - ``suggestion-reopen`` never creates a new request.
    """

    ordered = sorted(
        events,
        key=lambda event: (
            event.event_num,
            event.timestamp_ms,
        ),
    )

    episodes: list[SuggestionEpisode] = []

    # Requests that have been issued but not yet matched to an API open.
    pending_requests: deque[SuggestionEpisode] = deque()

    # Selections waiting for their API text-insert.
    awaiting_insert: deque[
        tuple[
            SuggestionEpisode,
            SuggestionSelection,
        ]
    ] = deque()

    # Suggestion set currently visible to the writer.
    active: SuggestionEpisode | None = None

    # Most recently displayed suggestion set.
    # Required for suggestion-reopen.
    last_displayed: SuggestionEpisode | None = None

    request_number = 0

    for event in ordered:
        name = event.event_name

        # ----------------------------------------------------------
        # REQUEST
        # ----------------------------------------------------------

        if name == "suggestion-get":
            request_number += 1

            episode = SuggestionEpisode(
                session_id=event.session_id,
                request_id=(
                    f"{event.session_id}:request:"
                    f"{request_number:04d}"
                ),
                request_event_num=event.event_num,
                request_timestamp_ms=event.timestamp_ms,
            )

            episodes.append(episode)
            pending_requests.append(episode)

            continue

        # ----------------------------------------------------------
        # OPEN
        #
        # A suggestion-open normally consumes the oldest pending
        # request. This preserves overlapping asynchronous requests:
        #
        #   get A
        #   open A
        #   get B
        #   close A
        #   open B
        # ----------------------------------------------------------

        if name == "suggestion-open":
            if pending_requests:
                active = pending_requests.popleft()

            elif active is None:
                active = _latest_unopened_episode(
                    episodes
                )

            if active is not None:
                active.open_event_num = event.event_num
                active.open_timestamp_ms = event.timestamp_ms

                if event.current_suggestions:
                    active.candidates = (
                        event.current_suggestions
                    )

                active.request_to_open_ms = (
                    event.timestamp_ms
                    - active.request_timestamp_ms
                )

                last_displayed = active

            continue

        # ----------------------------------------------------------
        # REOPEN
        #
        # Reopening returns to an already existing suggestion set.
        # It does not represent another model request.
        # ----------------------------------------------------------

        if name == "suggestion-reopen":
            reopened_episode = last_displayed

            if reopened_episode is None:
                reopened_episode = (
                    _latest_reopenable_episode(
                        episodes
                    )
                )

            if reopened_episode is not None:
                active = reopened_episode

                active.reopen_event_nums.append(
                    event.event_num
                )

                last_displayed = active

            continue

        # ----------------------------------------------------------
        # SELECT
        #
        # Each select is represented independently because one
        # SuggestionEpisode may generate several selections through
        # reopen cycles.
        # ----------------------------------------------------------

        if name == "suggestion-select":
            if active is None:
                active = _latest_selectable_episode(
                    episodes
                )

            if active is None:
                # Do not invent a request if no defensible association
                # can be recovered from the observed event stream.
                continue

            selected_index = event.current_hover_index

            if selected_index is None:
                selected_index = (
                    event.current_suggestion_index
                )

            selected_text: str | None = None

            if selected_index is not None:
                candidate = next(
                    (
                        candidate
                        for candidate in active.candidates
                        if candidate.index
                        == selected_index
                    ),
                    None,
                )

                if candidate is not None:
                    selected_text = candidate.trimmed

            selection_number = (
                len(active.selections) + 1
            )

            selection = SuggestionSelection(
                selection_id=(
                    f"{active.request_id}:selection:"
                    f"{selection_number:02d}"
                ),
                event_num=event.event_num,
                timestamp_ms=event.timestamp_ms,
                selected_index=selected_index,
                selected_text=selected_text,
                request_to_selection_ms=(
                    event.timestamp_ms
                    - active.request_timestamp_ms
                ),
            )

            if active.open_timestamp_ms is not None:
                selection.open_to_selection_ms = (
                    event.timestamp_ms
                    - active.open_timestamp_ms
                )

            active.selections.append(selection)

            awaiting_insert.append(
                (
                    active,
                    selection,
                )
            )

            last_displayed = active

            continue

        # ----------------------------------------------------------
        # CLOSE
        # ----------------------------------------------------------

        if name == "suggestion-close":
            if active is None:
                continue

            active.close_event_nums.append(
                event.event_num
            )

            if active.selections:
                latest_selection = (
                    active.selections[-1]
                )

                if (
                    latest_selection.close_event_num
                    is None
                ):
                    latest_selection.close_event_num = (
                        event.event_num
                    )

                    latest_selection.close_timestamp_ms = (
                        event.timestamp_ms
                    )

            else:
                active.was_dismissed = True

            last_displayed = active
            active = None

            continue

        # ----------------------------------------------------------
        # API INSERTION
        #
        # CoAuthor normally emits:
        #
        #   suggestion-select
        #   suggestion-close
        #   text-insert(api)
        #
        # The selection therefore remains in awaiting_insert after
        # the displayed episode has closed.
        # ----------------------------------------------------------

        if (
            name == "text-insert"
            and event.source == EventSource.API
            and awaiting_insert
        ):
            episode, selection = (
                awaiting_insert.popleft()
            )

            text, start, end = extract_insert(
                event.text_delta
            )

            selection.insert_event_num = (
                event.event_num
            )

            selection.insert_timestamp_ms = (
                event.timestamp_ms
            )

            selection.inserted_text = text
            selection.insertion_start = start
            selection.insertion_end = end

            selection.was_inserted = (
                text is not None
            )

            last_displayed = episode

            continue

    return episodes


def _latest_unopened_episode(
    episodes: list[SuggestionEpisode],
) -> SuggestionEpisode | None:
    """
    Recover the most recent request that has not yet been opened.

    This fallback is used only when an API open cannot be matched
    through the normal pending-request queue.
    """

    for episode in reversed(episodes):
        if episode.open_event_num is None:
            return episode

    return None


def _latest_selectable_episode(
    episodes: list[SuggestionEpisode],
) -> SuggestionEpisode | None:
    """
    Recover the most recent displayed episode eligible for selection.

    Used conservatively when explicit active-display state was lost.
    """

    for episode in reversed(episodes):
        if (
            episode.open_event_num is not None
            and not episode.was_dismissed
        ):
            return episode

    return None


def _latest_reopenable_episode(
    episodes: list[SuggestionEpisode],
) -> SuggestionEpisode | None:
    """
    Recover the most recently displayed suggestion episode.

    A valid reopen target must previously have been opened.
    """

    for episode in reversed(episodes):
        if episode.open_event_num is not None:
            return episode

    return None


def extract_insert(
    delta: object,
) -> tuple[
    str | None,
    int | None,
    int | None,
]:
    """
    Extract inserted text and its [start, end) coordinates
    from a Quill-style Delta.

    Example
    -------
    {
        "ops": [
            {"retain": 272},
            {"insert": "AI-generated text"}
        ]
    }

    Returns
    -------
    tuple
        ``(text, start, end)`` where coordinates follow Python
        half-open interval semantics.
    """

    if not isinstance(delta, dict):
        return None, None, None

    ops = delta.get("ops")

    if not isinstance(ops, list):
        return None, None, None

    position = 0
    start: int | None = None
    pieces: list[str] = []

    for op in ops:
        if not isinstance(op, dict):
            continue

        retain = op.get("retain")

        if (
            isinstance(retain, int)
            and retain >= 0
        ):
            position += retain

        insert = op.get("insert")

        if isinstance(insert, str):
            if start is None:
                start = position

            pieces.append(insert)
            position += len(insert)

    if start is None or not pieces:
        return None, None, None

    text = "".join(pieces)

    return (
        text,
        start,
        start + len(text),
    )
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventSource(StrEnum):
    """Origin of a CoAuthor event."""

    USER = "user"
    API = "api"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SuggestionCandidate:
    """One candidate returned by the language model."""

    index: int
    original: str
    trimmed: str
    probability: float | None = None


@dataclass(frozen=True, slots=True)
class Event:
    """
    Canonical representation of one raw CoAuthor event.

    Downstream AgencyTrace components operate on this normalized form
    rather than directly on the raw JSONL representation.
    """

    session_id: str
    event_num: int
    event_name: str
    timestamp_ms: int

    source: EventSource = EventSource.UNKNOWN

    cursor: int | None = None
    cursor_range: Any | None = None
    text_delta: Any | None = None
    current_doc: str | None = None

    current_suggestions: tuple[SuggestionCandidate, ...] = ()

    current_suggestion_index: int | None = None
    current_hover_index: int | None = None

    raw: dict[str, Any] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )


@dataclass(slots=True)
class SuggestionSelection:
    """
    One concrete selection made from a suggestion episode.

    A single SuggestionEpisode may contain several selections when the
    same suggestion set is reopened through ``suggestion-reopen``.
    """

    selection_id: str

    event_num: int
    timestamp_ms: int

    selected_index: int | None = None
    selected_text: str | None = None

    close_event_num: int | None = None
    close_timestamp_ms: int | None = None

    insert_event_num: int | None = None
    insert_timestamp_ms: int | None = None

    inserted_text: str | None = None
    insertion_start: int | None = None
    insertion_end: int | None = None

    was_inserted: bool = False

    open_to_selection_ms: int | None = None
    request_to_selection_ms: int | None = None


@dataclass(slots=True)
class SuggestionEpisode:
    """
    Reconstructed lifecycle associated with one ``suggestion-get``.

    One request creates exactly one SuggestionEpisode.

    An episode may contain multiple SuggestionSelection objects because
    CoAuthor allows the previously returned suggestion set to be reopened
    and another candidate to be selected.
    """

    session_id: str
    request_id: str

    request_event_num: int
    request_timestamp_ms: int

    open_event_num: int | None = None
    open_timestamp_ms: int | None = None

    candidates: tuple[SuggestionCandidate, ...] = ()

    selections: list[SuggestionSelection] = field(
        default_factory=list
    )

    close_event_nums: list[int] = field(
        default_factory=list
    )

    reopen_event_nums: list[int] = field(
        default_factory=list
    )

    was_dismissed: bool = False

    request_to_open_ms: int | None = None

    @property
    def was_selected(self) -> bool:
        """Whether this request generated at least one selection."""
        return bool(self.selections)

    @property
    def selection_count(self) -> int:
        """Number of selections made from this suggestion set."""
        return len(self.selections)

    @property
    def insertion_count(self) -> int:
        """Number of selections followed by an observed API insertion."""
        return sum(
            selection.was_inserted
            for selection in self.selections
        )
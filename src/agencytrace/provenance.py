from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from agencytrace.models import (
    Event,
    EventSource,
    SuggestionEpisode,
    SuggestionSelection,
)


HUMAN_ORIGIN = "human"
SYSTEM_ORIGIN = "system"
EMBED_PLACEHOLDER = "\uFFFC"


@dataclass(slots=True)
class ProvenanceChar:
    """
    One logical document unit with provenance information.

    Text characters are represented directly.

    Non-text Quill embeds are represented by the Unicode object
    replacement character (U+FFFC), which occupies one logical document
    position but is excluded from text-character metrics.
    """

    value: str
    origin: str
    source_event_num: int | None = None
    selection_id: str | None = None
    is_embed: bool = False


@dataclass(slots=True)
class SelectionProvenance:
    """
    Provenance summary for one reconstructed AI selection.
    """

    selection_id: str

    inserted_chars: int = 0
    surviving_chars: int = 0
    deleted_chars: int = 0

    inserted_event_num: int | None = None

    @property
    def retention_ratio(self) -> float:
        if self.inserted_chars == 0:
            return 0.0

        return (
            self.surviving_chars
            / self.inserted_chars
        )


@dataclass(slots=True)
class ProvenanceResult:
    """
    Final provenance reconstruction for one CoAuthor session.
    """

    session_id: str

    final_units: list[ProvenanceChar]

    selections: dict[
        str,
        SelectionProvenance,
    ]

    deleted_by_origin: dict[
        str,
        int,
    ] = field(
        default_factory=dict
    )

    anomalies: list[str] = field(
        default_factory=list
    )

    @property
    def final_text(self) -> str:
        return "".join(
            unit.value
            for unit in self.final_units
            if not unit.is_embed
        )

    @property
    def final_text_chars(self) -> int:
        return sum(
            not unit.is_embed
            for unit in self.final_units
        )

    @property
    def final_ai_chars(self) -> int:
        return sum(
            (
                not unit.is_embed
                and unit.selection_id is not None
            )
            for unit in self.final_units
        )

    @property
    def final_human_chars(self) -> int:
        return sum(
            (
                not unit.is_embed
                and unit.selection_id is None
                and unit.origin == HUMAN_ORIGIN
            )
            for unit in self.final_units
        )

    @property
    def ai_share(self) -> float:
        if self.final_text_chars == 0:
            return 0.0

        return (
            self.final_ai_chars
            / self.final_text_chars
        )


def reconstruct_provenance(
    events: list[Event],
    episodes: list[SuggestionEpisode],
) -> ProvenanceResult:
    """
    Reconstruct character-level text provenance for one session.

    The function applies all Quill-style text deltas in event order.

    Human text insertions receive HUMAN provenance.

    API text insertions corresponding to reconstructed suggestion
    selections receive the unique selection ID as provenance.

    Retained units preserve their existing provenance.

    Deleted units are removed while deletion statistics are accumulated.
    """

    if not events:
        return ProvenanceResult(
            session_id="",
            final_units=[],
            selections={},
        )

    ordered = sorted(
        events,
        key=lambda event: (
            event.event_num,
            event.timestamp_ms,
        ),
    )

    session_id = ordered[0].session_id

    selection_by_insert_event = (
        _index_selections_by_insert_event(
            episodes
        )
    )

    selection_stats = (
        _initialize_selection_stats(
            episodes
        )
    )

    document: list[ProvenanceChar] = []

    deleted_by_origin: dict[
        str,
        int,
    ] = {}

    anomalies: list[str] = []

    # --------------------------------------------------------------
    # Initialize document from system-initialize currentDoc when
    # available.
    # --------------------------------------------------------------

    initial = next(
        (
            event
            for event in ordered
            if event.event_name
            == "system-initialize"
        ),
        None,
    )

    if (
        initial is not None
        and initial.current_doc
    ):
        document = [
            ProvenanceChar(
                value=char,
                origin=SYSTEM_ORIGIN,
                source_event_num=(
                    initial.event_num
                ),
            )
            for char in initial.current_doc
        ]

    # --------------------------------------------------------------
    # Apply text deltas
    # --------------------------------------------------------------

    for event in ordered:
        if event.event_name not in {
            "text-insert",
            "text-delete",
        }:
            continue

        delta = event.text_delta

        if not isinstance(delta, dict):
            anomalies.append(
                f"event {event.event_num}: "
                "textDelta is not a dict"
            )
            continue

        ops = delta.get("ops")

        if not isinstance(ops, list):
            anomalies.append(
                f"event {event.event_num}: "
                "textDelta.ops is not a list"
            )
            continue

        selection = (
            selection_by_insert_event.get(
                event.event_num
            )
        )

        _apply_delta(
            document=document,
            ops=ops,
            event=event,
            selection=selection,
            selection_stats=selection_stats,
            deleted_by_origin=deleted_by_origin,
            anomalies=anomalies,
        )

    # --------------------------------------------------------------
    # Final survival counts
    # --------------------------------------------------------------

    for unit in document:
        if (
            unit.is_embed
            or unit.selection_id is None
        ):
            continue

        stats = selection_stats.get(
            unit.selection_id
        )

        if stats is not None:
            stats.surviving_chars += 1

    return ProvenanceResult(
        session_id=session_id,
        final_units=document,
        selections=selection_stats,
        deleted_by_origin=deleted_by_origin,
        anomalies=anomalies,
    )


def _apply_delta(
    *,
    document: list[ProvenanceChar],
    ops: list,
    event: Event,
    selection: SuggestionSelection | None,
    selection_stats: dict[
        str,
        SelectionProvenance,
    ],
    deleted_by_origin: dict[
        str,
        int,
    ],
    anomalies: list[str],
) -> None:
    """
    Apply one Quill Delta to the mutable document.

    Quill operations are interpreted sequentially against the evolving
    document cursor:

    - retain(n): advance n logical units
    - insert(x): insert at current cursor
    - delete(n): remove n logical units at current cursor
    """

    cursor = 0

    for op_index, op in enumerate(ops):
        if not isinstance(op, dict):
            anomalies.append(
                f"event {event.event_num}, "
                f"op {op_index}: non-dict op"
            )
            continue

        # ----------------------------------------------------------
        # RETAIN
        # ----------------------------------------------------------

        if "retain" in op:
            retain = op["retain"]

            if not isinstance(retain, int):
                anomalies.append(
                    f"event {event.event_num}, "
                    f"op {op_index}: "
                    "non-integer retain"
                )
                continue

            if retain < 0:
                anomalies.append(
                    f"event {event.event_num}, "
                    f"op {op_index}: "
                    "negative retain"
                )
                continue

            cursor += retain

            if cursor > len(document):
                anomalies.append(
                    f"event {event.event_num}: "
                    f"retain exceeds document "
                    f"({cursor}>{len(document)})"
                )

                cursor = len(document)

        # ----------------------------------------------------------
        # INSERT
        # ----------------------------------------------------------

        if "insert" in op:
            value = op["insert"]

            inserted_units = (
                _make_inserted_units(
                    value=value,
                    event=event,
                    selection=selection,
                )
            )

            if inserted_units:
                document[
                    cursor:cursor
                ] = inserted_units

                inserted_text_chars = sum(
                    not unit.is_embed
                    for unit in inserted_units
                )

                if (
                    selection is not None
                    and inserted_text_chars > 0
                ):
                    stats = (
                        selection_stats[
                            selection.selection_id
                        ]
                    )

                    stats.inserted_chars += (
                        inserted_text_chars
                    )

                    stats.inserted_event_num = (
                        event.event_num
                    )

                cursor += len(
                    inserted_units
                )

        # ----------------------------------------------------------
        # DELETE
        # ----------------------------------------------------------

        if "delete" in op:
            delete = op["delete"]

            if not isinstance(delete, int):
                anomalies.append(
                    f"event {event.event_num}, "
                    f"op {op_index}: "
                    "non-integer delete"
                )
                continue

            if delete < 0:
                anomalies.append(
                    f"event {event.event_num}, "
                    f"op {op_index}: "
                    "negative delete"
                )
                continue

            end = min(
                cursor + delete,
                len(document),
            )

            removed = document[
                cursor:end
            ]

            if len(removed) < delete:
                anomalies.append(
                    f"event {event.event_num}: "
                    f"delete exceeds document "
                    f"({delete} requested, "
                    f"{len(removed)} available)"
                )

            for unit in removed:
                if unit.is_embed:
                    continue

                key = (
                    unit.selection_id
                    if unit.selection_id
                    is not None
                    else unit.origin
                )

                deleted_by_origin[key] = (
                    deleted_by_origin.get(
                        key,
                        0,
                    )
                    + 1
                )

                if (
                    unit.selection_id
                    is not None
                ):
                    stats = (
                        selection_stats.get(
                            unit.selection_id
                        )
                    )

                    if stats is not None:
                        stats.deleted_chars += 1

            del document[
                cursor:end
            ]


def _make_inserted_units(
    *,
    value: object,
    event: Event,
    selection: SuggestionSelection | None,
) -> list[ProvenanceChar]:
    """
    Convert one Quill insert payload into provenance units.

    Text inserts become one unit per character.

    Non-text embeds occupy one logical document position but do not
    contribute to text-character metrics.
    """

    if isinstance(value, str):
        if (
            event.source
            == EventSource.API
            and selection is not None
        ):
            origin = (
                selection.selection_id
            )

            selection_id = (
                selection.selection_id
            )

        elif event.source == EventSource.USER:
            origin = HUMAN_ORIGIN
            selection_id = None

        else:
            origin = event.source.value
            selection_id = None

        return [
            ProvenanceChar(
                value=char,
                origin=origin,
                source_event_num=(
                    event.event_num
                ),
                selection_id=(
                    selection_id
                ),
                is_embed=False,
            )
            for char in value
        ]

    # Quill embeds occupy length 1.
    return [
        ProvenanceChar(
            value=EMBED_PLACEHOLDER,
            origin=event.source.value,
            source_event_num=(
                event.event_num
            ),
            selection_id=None,
            is_embed=True,
        )
    ]


def _index_selections_by_insert_event(
    episodes: Iterable[
        SuggestionEpisode
    ],
) -> dict[
    int,
    SuggestionSelection,
]:
    """
    Map API text-insert event numbers to reconstructed selections.
    """

    result: dict[
        int,
        SuggestionSelection,
    ] = {}

    for episode in episodes:
        for selection in episode.selections:
            if (
                selection.insert_event_num
                is None
            ):
                continue

            result[
                selection.insert_event_num
            ] = selection

    return result


def _initialize_selection_stats(
    episodes: Iterable[
        SuggestionEpisode
    ],
) -> dict[
    str,
    SelectionProvenance,
]:
    result: dict[
        str,
        SelectionProvenance,
    ] = {}

    for episode in episodes:
        for selection in episode.selections:
            result[
                selection.selection_id
            ] = SelectionProvenance(
                selection_id=(
                    selection.selection_id
                ),
                inserted_event_num=(
                    selection.insert_event_num
                ),
            )

    return result
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from agencytrace.models import (
    Event,
    EventSource,
    SuggestionCandidate,
)


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_source(value: Any) -> EventSource:
    try:
        return EventSource(str(value).lower())
    except ValueError:
        return EventSource.UNKNOWN


def _parse_candidate(
    raw: dict[str, Any],
) -> SuggestionCandidate:
    original = str(raw.get("original", ""))

    probability_raw = raw.get("probability")

    try:
        probability = (
            float(probability_raw)
            if probability_raw not in (None, "")
            else None
        )
    except (TypeError, ValueError):
        probability = None

    return SuggestionCandidate(
        index=int(raw["index"]),
        original=original,
        trimmed=str(raw.get("trimmed", original.strip())),
        probability=probability,
    )


def parse_event(
    raw: dict[str, Any],
    *,
    session_id: str,
) -> Event:
    suggestions = raw.get("currentSuggestions") or []

    return Event(
        session_id=session_id,
        event_num=int(raw["eventNum"]),
        event_name=str(raw["eventName"]),
        timestamp_ms=int(raw["eventTimestamp"]),
        source=_parse_source(raw.get("eventSource")),
        cursor=_to_int(raw.get("currentCursor")),
        cursor_range=raw.get("cursorRange"),
        text_delta=raw.get("textDelta"),
        current_doc=raw.get("currentDoc") or None,
        current_suggestions=tuple(
            _parse_candidate(candidate)
            for candidate in suggestions
            if isinstance(candidate, dict)
        ),
        current_suggestion_index=_to_int(
            raw.get("currentSuggestionIndex")
        ),
        current_hover_index=_to_int(
            raw.get("currentHoverIndex")
        ),
        raw=raw,
    )


def read_jsonl_events(
    path: str | Path,
) -> Iterator[Event]:
    path = Path(path)
    session_id = path.stem

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue

            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON"
                ) from exc

            yield parse_event(
                raw,
                session_id=session_id,
            )


def load_jsonl_events(
    path: str | Path,
) -> list[Event]:
    return sorted(
        read_jsonl_events(path),
        key=lambda event: (
            event.event_num,
            event.timestamp_ms,
        ),
    )
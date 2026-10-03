from agencytrace.io import load_jsonl_events


def test_load_minimal_session() -> None:
    events = load_jsonl_events(
        "tests/fixtures/minimal_session.jsonl"
    )

    assert len(events) == 3

    assert events[0].event_name == "system-initialize"
    assert events[1].event_name == "suggestion-get"
    assert events[2].event_name == "suggestion-open"

    assert events[2].event_num == 2
    assert len(events[2].current_suggestions) == 2

    candidate = events[2].current_suggestions[1]

    assert candidate.index == 4
    assert (
        candidate.trimmed
        == "The world is a dangerous place, but it is also filled with wonder."
    )
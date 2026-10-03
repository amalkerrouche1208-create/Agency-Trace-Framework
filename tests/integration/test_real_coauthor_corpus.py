from __future__ import annotations

from pathlib import Path

from agencytrace.episodes import reconstruct_suggestion_episodes
from agencytrace.io import load_jsonl_events


RAW_DATA_DIR = Path("data/raw")


def _raw_sessions() -> list[Path]:
    return sorted(RAW_DATA_DIR.rglob("*.jsonl"))


def test_real_corpus_is_available() -> None:
    files = _raw_sessions()

    assert files, (
        "No CoAuthor JSONL files found under data/raw/"
    )


def test_real_corpus_contains_parseable_sessions() -> None:
    files = _raw_sessions()

    assert files

    # Keep the routine integration test quick.
    sample = files[:10]

    for path in sample:
        events = load_jsonl_events(path)

        assert events
        assert all(event.session_id for event in events)


def test_real_corpus_reconstructs_suggestion_episodes() -> None:
    files = _raw_sessions()

    assert files

    total_episodes = 0

    for path in files[:10]:
        events = load_jsonl_events(path)

        episodes = reconstruct_suggestion_episodes(events)
        total_episodes += len(episodes)

    assert total_episodes > 0
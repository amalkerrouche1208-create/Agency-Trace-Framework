from __future__ import annotations

import csv
from pathlib import Path

from agencytrace.io import load_jsonl_events
from agencytrace.metrics import (
    compute_selection_metrics,
    compute_session_metrics,
    selection_metrics_to_dict,
    session_metrics_to_dict,
)
from agencytrace.provenance import reconstruct_provenance
from agencytrace.reconstruct import reconstruct_suggestion_episodes


RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("data/processed")

SESSION_OUTPUT = OUTPUT_DIR / "session_metrics.csv"
SELECTION_OUTPUT = OUTPUT_DIR / "selection_metrics.csv"


def write_csv(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    """
    Write a list of homogeneous dictionaries to CSV.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        raise ValueError(
            f"No rows available for {path}"
        )

    fieldnames = list(
        rows[0].keys()
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="raise",
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def main() -> None:
    paths = sorted(
        RAW_DIR.rglob("*.jsonl")
    )

    if not paths:
        raise SystemExit(
            "No CoAuthor JSONL files found under data/raw/"
        )

    session_rows: list[
        dict[str, object]
    ] = []

    selection_rows: list[
        dict[str, object]
    ] = []

    for index, path in enumerate(
        paths,
        start=1,
    ):
        events = load_jsonl_events(
            path
        )

        episodes = (
            reconstruct_suggestion_episodes(
                events
            )
        )

        provenance = (
            reconstruct_provenance(
                events,
                episodes,
            )
        )

        session_metrics = (
            compute_session_metrics(
                events,
                episodes,
                provenance,
            )
        )

        selections = (
            compute_selection_metrics(
                episodes,
                provenance,
            )
        )

        session_rows.append(
            session_metrics_to_dict(
                session_metrics
            )
        )

        selection_rows.extend(
            selection_metrics_to_dict(
                row
            )
            for row in selections
        )

        if index % 100 == 0:
            print(
                f"Processed "
                f"{index}/{len(paths)} "
                f"sessions..."
            )

    # ------------------------------------------------------------------
    # Deterministic ordering
    # ------------------------------------------------------------------

    session_rows.sort(
        key=lambda row: str(
            row["session_id"]
        )
    )

    selection_rows.sort(
        key=lambda row: (
            str(
                row["session_id"]
            ),
            int(
                row["selection_event_num"]
            ),
            str(
                row["selection_id"]
            ),
        )
    )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    write_csv(
        SESSION_OUTPUT,
        session_rows,
    )

    write_csv(
        SELECTION_OUTPUT,
        selection_rows,
    )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    expected_sessions = len(
        paths
    )

    expected_selections = sum(
        int(
            row["suggestion_selections"]
        )
        for row in session_rows
    )

    if (
        len(session_rows)
        != expected_sessions
    ):
        raise RuntimeError(
            "Session export row count mismatch: "
            f"{len(session_rows)} "
            f"!= {expected_sessions}"
        )

    if (
        len(selection_rows)
        != expected_selections
    ):
        raise RuntimeError(
            "Selection export row count mismatch: "
            f"{len(selection_rows)} "
            f"!= {expected_selections}"
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    direct = sum(
        row["adoption_outcome"]
        == "direct_adoption"
        for row in selection_rows
    )

    modified = sum(
        row["adoption_outcome"]
        == "modified_adoption"
        for row in selection_rows
    )

    non_adoption = sum(
        row["adoption_outcome"]
        == "non_adoption"
        for row in selection_rows
    )

    print()
    print("=" * 78)
    print(
        "AgencyTrace — Metrics Export"
    )
    print("=" * 78)

    print(
        f"Sessions exported               : "
        f"{len(session_rows)}"
    )

    print(
        f"Selections exported             : "
        f"{len(selection_rows)}"
    )

    print()

    print(
        f"Direct adoption                : "
        f"{direct}"
    )

    print(
        f"Modified adoption              : "
        f"{modified}"
    )

    print(
        f"Non-adoption                   : "
        f"{non_adoption}"
    )

    print()

    print(
        f"Session metrics                : "
        f"{SESSION_OUTPUT}"
    )

    print(
        f"Selection metrics              : "
        f"{SELECTION_OUTPUT}"
    )

    print()
    print("=" * 78)
    print(
        "Metrics export completed."
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
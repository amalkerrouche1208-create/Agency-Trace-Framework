from __future__ import annotations

import csv
from pathlib import Path

from agencytrace.ml.transitions import (
    STATES,
    STATE_LABELS,
    bootstrap_transition_probabilities,
    build_sequences,
    build_session_transition_metrics,
    endpoint_matrix,
    load_selection_records,
    load_session_ids,
    matrix_rows,
    positional_outcome_profile,
    row_probability_matrix,
    transition_count_matrix,
)


SELECTION_METRICS = Path(
    "data/processed/"
    "selection_metrics.csv"
)

SESSION_METRICS = Path(
    "data/processed/"
    "session_metrics.csv"
)

OUTPUT_DIR = Path(
    "data/analysis/ml/"
    "transitions"
)

BOOTSTRAP_REPEATS = 500
RANDOM_STATE = 42


def write_rows(
    path: Path,
    rows: list[dict[str, object]],
) -> None:
    if not rows:
        raise ValueError(
            f"No rows to write: {path}"
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
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

        for row in rows:
            writer.writerow(
                {
                    key: (
                        ""
                        if value is None
                        else value
                    )
                    for key, value
                    in row.items()
                }
            )


def main() -> None:
    records = load_selection_records(
        SELECTION_METRICS
    )

    session_ids = load_session_ids(
        SESSION_METRICS
    )

    sequences = build_sequences(
        records,
        session_ids,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    matrix_output: list[
        dict[str, object]
    ] = []

    bootstrap_output: list[
        dict[str, object]
    ] = []

    matrices = {}

    for scope in (
        "all",
        "cross_request",
    ):
        counts = (
            transition_count_matrix(
                sequences,
                scope=scope,
            )
        )

        probabilities = (
            row_probability_matrix(
                counts
            )
        )

        matrices[
            scope
        ] = (
            counts,
            probabilities,
        )

        matrix_output.extend(
            matrix_rows(
                counts,
                probabilities,
                scope=scope,
            )
        )

        bootstrap_output.extend(
            bootstrap_transition_probabilities(
                sequences,
                scope=scope,
                repeats=(
                    BOOTSTRAP_REPEATS
                ),
                random_state=(
                    RANDOM_STATE
                ),
            )
        )

    session_rows = (
        build_session_transition_metrics(
            sequences
        )
    )

    positional_rows = (
        positional_outcome_profile(
            sequences
        )
    )

    (
        endpoint_counts,
        endpoint_probabilities,
        endpoint_eligible,
    ) = endpoint_matrix(
        sequences
    )

    endpoint_rows = matrix_rows(
        endpoint_counts,
        endpoint_probabilities,
        scope="first_to_last",
    )

    for row in endpoint_rows:
        row[
            "eligible_sessions"
        ] = endpoint_eligible

    paths = {
        "matrix": (
            OUTPUT_DIR
            / "transition_matrix.csv"
        ),
        "bootstrap": (
            OUTPUT_DIR
            / "transition_bootstrap.csv"
        ),
        "session": (
            OUTPUT_DIR
            / "session_transition_metrics.csv"
        ),
        "position": (
            OUTPUT_DIR
            / "positional_outcomes.csv"
        ),
        "endpoint": (
            OUTPUT_DIR
            / "endpoint_matrix.csv"
        ),
    }

    write_rows(
        paths["matrix"],
        matrix_output,
    )

    write_rows(
        paths["bootstrap"],
        bootstrap_output,
    )

    write_rows(
        paths["session"],
        session_rows,
    )

    write_rows(
        paths["position"],
        positional_rows,
    )

    write_rows(
        paths["endpoint"],
        endpoint_rows,
    )

    sessions_with_selection = sum(
        bool(sequence)
        for sequence
        in sequences.values()
    )

    sessions_without_selection = (
        len(sequences)
        - sessions_with_selection
    )

    sessions_with_two_or_more = sum(
        len(sequence) >= 2
        for sequence
        in sequences.values()
    )

    all_counts, _ = matrices[
        "all"
    ]

    (
        cross_counts,
        cross_probabilities,
    ) = matrices[
        "cross_request"
    ]

    print()
    print("=" * 88)
    print(
        "AgencyTrace — Selection Transition Analysis"
    )
    print("=" * 88)

    print(
        f"Sessions                       : "
        f"{len(sequences)}"
    )

    print(
        f"Selection records              : "
        f"{len(records)}"
    )

    print(
        f"Sessions with selection        : "
        f"{sessions_with_selection}"
    )

    print(
        f"Sessions without selection     : "
        f"{sessions_without_selection}"
    )

    print(
        f"Sessions with >=2 selections   : "
        f"{sessions_with_two_or_more}"
    )

    print(
        f"All consecutive transitions    : "
        f"{int(all_counts.sum())}"
    )

    print(
        f"Cross-request transitions      : "
        f"{int(cross_counts.sum())}"
    )

    print(
        f"Intra-request transitions      : "
        f"{int(
            all_counts.sum()
            - cross_counts.sum()
        )}"
    )

    print()
    print(
        "CROSS-REQUEST TRANSITION PROBABILITIES"
    )
    print("-" * 88)

    for i, from_state in enumerate(
        STATES
    ):
        print()
        print(
            STATE_LABELS[
                from_state
            ]
        )

        for j, to_state in enumerate(
            STATES
        ):
            value = (
                cross_probabilities[
                    i,
                    j
                ]
            )

            if value != value:
                text = "NA"
            else:
                text = (
                    f"{float(value):.3f}"
                )

            print(
                f"  -> "
                f"{STATE_LABELS[to_state]:<20} "
                f"{text}"
            )

    print()
    print(
        "Generated:"
    )

    for path in paths.values():
        print(
            f"  {path}"
        )

    print("=" * 88)


if __name__ == "__main__":
    main()
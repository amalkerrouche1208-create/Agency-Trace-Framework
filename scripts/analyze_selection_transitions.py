from __future__ import annotations

import csv
from pathlib import Path

from agencytrace.ml.temporal_inference import (
    early_late_change,
    permutation_transition_test,
    session_weighted_phase_rows,
    summarize_session_weighted_phases,
)
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
    "data/processed/selection_metrics.csv"
)

SESSION_METRICS = Path(
    "data/processed/session_metrics.csv"
)

OUTPUT_DIR = Path(
    "data/analysis/ml/transitions"
)

TRANSITION_BOOTSTRAP_REPEATS = 500
PERMUTATION_REPEATS = 1000
PHASE_BOOTSTRAP_REPEATS = 1000
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

    # =================================================================
    # 1. Consecutive selection transitions
    # =================================================================

    transition_rows: list[
        dict[str, object]
    ] = []

    transition_bootstrap_rows: list[
        dict[str, object]
    ] = []

    matrices = {}

    for scope in (
        "all",
        "cross_request",
    ):
        counts = transition_count_matrix(
            sequences,
            scope=scope,
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

        transition_rows.extend(
            matrix_rows(
                counts,
                probabilities,
                scope=scope,
            )
        )

        transition_bootstrap_rows.extend(
            bootstrap_transition_probabilities(
                sequences,
                scope=scope,
                repeats=(
                    TRANSITION_BOOTSTRAP_REPEATS
                ),
                random_state=(
                    RANDOM_STATE
                ),
            )
        )

    # =================================================================
    # 2. Session-level transition metrics
    # =================================================================

    session_transition_rows = (
        build_session_transition_metrics(
            sequences
        )
    )

    # =================================================================
    # 3. Pooled positional profile
    # =================================================================

    positional_rows = (
        positional_outcome_profile(
            sequences
        )
    )

    # =================================================================
    # 4. First-to-last endpoint matrix
    # =================================================================

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

    # =================================================================
    # 5. Within-session permutation null
    # =================================================================

    (
        permutation_rows,
        persistence_summary,
    ) = permutation_transition_test(
        sequences,
        scope="cross_request",
        repeats=(
            PERMUTATION_REPEATS
        ),
        random_state=(
            RANDOM_STATE
        ),
    )

    persistence_rows = [
        persistence_summary
    ]

    # =================================================================
    # 6. Session-weighted temporal phases
    # =================================================================

    session_phase_rows = (
        session_weighted_phase_rows(
            sequences
        )
    )

    phase_summary_rows = (
        summarize_session_weighted_phases(
            session_phase_rows,
            bootstrap_repeats=(
                PHASE_BOOTSTRAP_REPEATS
            ),
            random_state=(
                RANDOM_STATE
            ),
        )
    )

    early_late_rows = (
        early_late_change(
            session_phase_rows,
            bootstrap_repeats=(
                PHASE_BOOTSTRAP_REPEATS
            ),
            random_state=(
                RANDOM_STATE
            ),
        )
    )

    # =================================================================
    # 7. Write outputs
    # =================================================================

    paths = {
        "transition_matrix": (
            OUTPUT_DIR
            / "transition_matrix.csv"
        ),
        "transition_bootstrap": (
            OUTPUT_DIR
            / "transition_bootstrap.csv"
        ),
        "session_transition_metrics": (
            OUTPUT_DIR
            / "session_transition_metrics.csv"
        ),
        "positional_outcomes": (
            OUTPUT_DIR
            / "positional_outcomes.csv"
        ),
        "endpoint_matrix": (
            OUTPUT_DIR
            / "endpoint_matrix.csv"
        ),
        "permutation_null": (
            OUTPUT_DIR
            / "transition_permutation_null.csv"
        ),
        "persistence_test": (
            OUTPUT_DIR
            / "transition_persistence_test.csv"
        ),
        "session_phase_shares": (
            OUTPUT_DIR
            / "session_phase_shares.csv"
        ),
        "phase_summary": (
            OUTPUT_DIR
            / "session_weighted_phase_summary.csv"
        ),
        "early_late_change": (
            OUTPUT_DIR
            / "early_late_change.csv"
        ),
    }

    write_rows(
        paths[
            "transition_matrix"
        ],
        transition_rows,
    )

    write_rows(
        paths[
            "transition_bootstrap"
        ],
        transition_bootstrap_rows,
    )

    write_rows(
        paths[
            "session_transition_metrics"
        ],
        session_transition_rows,
    )

    write_rows(
        paths[
            "positional_outcomes"
        ],
        positional_rows,
    )

    write_rows(
        paths[
            "endpoint_matrix"
        ],
        endpoint_rows,
    )

    write_rows(
        paths[
            "permutation_null"
        ],
        permutation_rows,
    )

    write_rows(
        paths[
            "persistence_test"
        ],
        persistence_rows,
    )

    write_rows(
        paths[
            "session_phase_shares"
        ],
        session_phase_rows,
    )

    write_rows(
        paths[
            "phase_summary"
        ],
        phase_summary_rows,
    )

    write_rows(
        paths[
            "early_late_change"
        ],
        early_late_rows,
    )

    # =================================================================
    # 8. Corpus summary
    # =================================================================

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

    all_transition_count = int(
        all_counts.sum()
    )

    cross_transition_count = int(
        cross_counts.sum()
    )

    intra_transition_count = (
        all_transition_count
        - cross_transition_count
    )

    print()
    print("=" * 92)
    print(
        "AgencyTrace — Temporal Response-Use Analysis"
    )
    print("=" * 92)

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
        f"{all_transition_count}"
    )

    print(
        f"Cross-request transitions      : "
        f"{cross_transition_count}"
    )

    print(
        f"Intra-request transitions      : "
        f"{intra_transition_count}"
    )

    # =================================================================
    # 9. Transition probabilities
    # =================================================================

    print()
    print(
        "CROSS-REQUEST TRANSITION PROBABILITIES"
    )
    print("-" * 92)

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

            text = (
                "NA"
                if value != value
                else f"{float(value):.3f}"
            )

            print(
                f"  -> "
                f"{STATE_LABELS[to_state]:<20} "
                f"{text}"
            )

    # =================================================================
    # 10. Serial persistence inference
    # =================================================================

    observed_self = float(
        persistence_summary[
            "observed_self_transition_rate"
        ]
    )

    null_self = float(
        persistence_summary[
            "null_mean_self_transition_rate"
        ]
    )

    self_difference = float(
        persistence_summary[
            "difference_from_null"
        ]
    )

    persistence_p = float(
        persistence_summary[
            "permutation_p"
        ]
    )

    print()
    print(
        "SERIAL PERSISTENCE AGAINST "
        "WITHIN-SESSION PERMUTATION NULL"
    )
    print("-" * 92)

    print(
        f"Observed self-transition rate : "
        f"{observed_self:.4f}"
    )

    print(
        f"Null mean                     : "
        f"{null_self:.4f}"
    )

    print(
        f"Difference                    : "
        f"{self_difference:+.4f}"
    )

    print(
        f"Permutation p                 : "
        f"{persistence_p:.6f}"
    )

    # =================================================================
    # 11. Null-adjusted transition cells
    # =================================================================

    print()
    print(
        "NULL-ADJUSTED CROSS-REQUEST TRANSITIONS"
    )
    print("-" * 92)

    ordered_permutation_rows = sorted(
        permutation_rows,
        key=lambda row: (
            -abs(
                float(
                    row[
                        "difference_from_null"
                    ]
                    or 0.0
                )
            ),
            str(
                row[
                    "from_state"
                ]
            ),
            str(
                row[
                    "to_state"
                ]
            ),
        ),
    )

    for row in ordered_permutation_rows:
        from_state = str(
            row[
                "from_state"
            ]
        )

        to_state = str(
            row[
                "to_state"
            ]
        )

        observed = float(
            row[
                "observed_probability"
            ]
        )

        null_mean = float(
            row[
                "null_mean_probability"
            ]
        )

        difference = float(
            row[
                "difference_from_null"
            ]
        )

        q_value = float(
            row[
                "fdr_q"
            ]
        )

        print(
            f"{STATE_LABELS[from_state]:<20} "
            f"-> "
            f"{STATE_LABELS[to_state]:<20} "
            f"obs={observed:.3f}  "
            f"null={null_mean:.3f}  "
            f"diff={difference:+.3f}  "
            f"q={q_value:.4f}"
        )

    # =================================================================
    # 12. Session-weighted early-to-late change
    # =================================================================

    print()
    print(
        "SESSION-WEIGHTED EARLY -> LATE CHANGE"
    )
    print("-" * 92)

    for row in early_late_rows:
        outcome = str(
            row[
                "outcome"
            ]
        )

        mean_change = float(
            row[
                "mean_late_minus_early"
            ]
        )

        lower = float(
            row[
                "ci_2_5"
            ]
        )

        upper = float(
            row[
                "ci_97_5"
            ]
        )

        print(
            f"{STATE_LABELS[outcome]:<20} "
            f"mean change="
            f"{mean_change:+.4f}  "
            f"95% CI=["
            f"{lower:+.4f}, "
            f"{upper:+.4f}]"
        )

    # =================================================================
    # 13. Output inventory
    # =================================================================

    print()
    print(
        "Generated:"
    )

    for path in paths.values():
        print(
            f"  {path}"
        )

    print("=" * 92)
    print(
        "Temporal response-use analysis completed."
    )
    print("=" * 92)


if __name__ == "__main__":
    main()
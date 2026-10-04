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
    STATE_LABELS,
    build_sequences,
    load_selection_records,
    load_session_ids,
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

PERMUTATION_REPEATS = 1000
BOOTSTRAP_REPEATS = 1000
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

    phase_rows = (
        session_weighted_phase_rows(
            sequences
        )
    )

    phase_summary = (
        summarize_session_weighted_phases(
            phase_rows,
            bootstrap_repeats=(
                BOOTSTRAP_REPEATS
            ),
            random_state=(
                RANDOM_STATE
            ),
        )
    )

    change_rows = early_late_change(
        phase_rows,
        bootstrap_repeats=(
            BOOTSTRAP_REPEATS
        ),
        random_state=(
            RANDOM_STATE
        ),
    )

    persistence_rows = [
        persistence_summary
    ]

    paths = {
        "null": (
            OUTPUT_DIR
            / "transition_permutation_null.csv"
        ),
        "persistence": (
            OUTPUT_DIR
            / "transition_persistence_test.csv"
        ),
        "session_phases": (
            OUTPUT_DIR
            / "session_phase_shares.csv"
        ),
        "phase_summary": (
            OUTPUT_DIR
            / "session_weighted_phase_summary.csv"
        ),
        "early_late": (
            OUTPUT_DIR
            / "early_late_change.csv"
        ),
    }

    write_rows(
        paths["null"],
        permutation_rows,
    )

    write_rows(
        paths["persistence"],
        persistence_rows,
    )

    write_rows(
        paths["session_phases"],
        phase_rows,
    )

    write_rows(
        paths["phase_summary"],
        phase_summary,
    )

    write_rows(
        paths["early_late"],
        change_rows,
    )

    print()
    print("=" * 90)
    print(
        "AgencyTrace — Temporal Inference"
    )
    print("=" * 90)

    print()
    print(
        "SERIAL PERSISTENCE AGAINST "
        "WITHIN-SESSION PERMUTATION NULL"
    )
    print("-" * 90)

    print(
        "Observed self-transition rate : "
        f"{float(
            persistence_summary[
                'observed_self_transition_rate'
            ]
        ):.4f}"
    )

    print(
        "Null mean                    : "
        f"{float(
            persistence_summary[
                'null_mean_self_transition_rate'
            ]
        ):.4f}"
    )

    print(
        "Difference                   : "
        f"{float(
            persistence_summary[
                'difference_from_null'
            ]
        ):+.4f}"
    )

    print(
        "Permutation p                : "
        f"{float(
            persistence_summary[
                'permutation_p'
            ]
        ):.6f}"
    )

    print()
    print(
        "NULL-ADJUSTED TRANSITIONS"
    )
    print("-" * 90)

    ordered = sorted(
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

    for row in ordered:
        print(
            f"{STATE_LABELS[
                str(row['from_state'])
            ]:<20} -> "
            f"{STATE_LABELS[
                str(row['to_state'])
            ]:<20} "
            f"obs="
            f"{float(
                row[
                    'observed_probability'
                ]
            ):.3f}  "
            f"null="
            f"{float(
                row[
                    'null_mean_probability'
                ]
            ):.3f}  "
            f"diff="
            f"{float(
                row[
                    'difference_from_null'
                ]
            ):+.3f}  "
            f"q="
            f"{float(
                row[
                    'fdr_q'
                ]
            ):.4f}"
        )

    print()
    print(
        "SESSION-WEIGHTED EARLY -> LATE CHANGE"
    )
    print("-" * 90)

    for row in change_rows:
        print(
            f"{STATE_LABELS[
                str(row['outcome'])
            ]:<20} "
            f"mean change="
            f"{float(
                row[
                    'mean_late_minus_early'
                ]
            ):+.4f}  "
            f"95% CI=["
            f"{float(
                row[
                    'ci_2_5'
                ]
            ):+.4f}, "
            f"{float(
                row[
                    'ci_97_5'
                ]
            ):+.4f}]"
        )

    print()
    print(
        "Generated:"
    )

    for path in paths.values():
        print(
            f"  {path}"
        )

    print("=" * 90)


if __name__ == "__main__":
    main()
from __future__ import annotations

import csv
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping

import numpy as np


# Canonical values stored in selection_metrics.csv.
STATES: tuple[str, ...] = (
    "direct_adoption",
    "modified_adoption",
    "non_adoption",
)

STATE_LABELS = {
    "direct_adoption": "Direct Adoption",
    "modified_adoption": "Modified Adoption",
    "non_adoption": "Non-Adoption",
}

STATE_INDEX = {
    state: index
    for index, state in enumerate(STATES)
}

TransitionScope = Literal[
    "all",
    "cross_request",
]


@dataclass(frozen=True, slots=True)
class SelectionRecord:
    session_id: str
    request_id: str
    selection_id: str

    request_event_num: int
    selection_event_num: int

    adoption_outcome: str


def load_selection_records(
    path: Path,
) -> list[SelectionRecord]:
    if not path.is_file():
        raise FileNotFoundError(path)

    records: list[
        SelectionRecord
    ] = []

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        required = {
            "session_id",
            "request_id",
            "selection_id",
            "request_event_num",
            "selection_event_num",
            "adoption_outcome",
        }

        if reader.fieldnames is None:
            raise ValueError(
                "Selection metrics have no header."
            )

        missing = (
            required
            - set(reader.fieldnames)
        )

        if missing:
            raise ValueError(
                "Selection metrics are missing "
                f"required columns: {sorted(missing)}"
            )

        for raw in reader:
            outcome = (
                raw["adoption_outcome"]
                .strip()
            )

            if outcome not in STATE_INDEX:
                raise ValueError(
                    "Unknown adoption outcome: "
                    f"{outcome!r}. Expected one of "
                    f"{STATES}."
                )

            records.append(
                SelectionRecord(
                    session_id=raw[
                        "session_id"
                    ],
                    request_id=raw[
                        "request_id"
                    ],
                    selection_id=raw[
                        "selection_id"
                    ],
                    request_event_num=int(
                        raw[
                            "request_event_num"
                        ]
                    ),
                    selection_event_num=int(
                        raw[
                            "selection_event_num"
                        ]
                    ),
                    adoption_outcome=outcome,
                )
            )

    identities = [
        (
            record.session_id,
            record.selection_id,
        )
        for record in records
    ]

    if len(identities) != len(
        set(identities)
    ):
        raise ValueError(
            "Duplicate selection identity found."
        )

    return records


def load_session_ids(
    path: Path,
) -> tuple[str, ...]:
    if not path.is_file():
        raise FileNotFoundError(path)

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if (
            reader.fieldnames is None
            or "session_id"
            not in reader.fieldnames
        ):
            raise ValueError(
                "Expected a session_id column."
            )

        session_ids = tuple(
            row["session_id"]
            for row in reader
        )

    if len(session_ids) != len(
        set(session_ids)
    ):
        raise ValueError(
            "Duplicate session IDs found."
        )

    return session_ids


def build_sequences(
    records: Iterable[SelectionRecord],
    session_ids: Iterable[str],
) -> dict[
    str,
    list[SelectionRecord],
]:
    sequences = {
        session_id: []
        for session_id in session_ids
    }

    for record in records:
        if (
            record.session_id
            not in sequences
        ):
            raise ValueError(
                "Selection references unknown "
                f"session: {record.session_id}"
            )

        sequences[
            record.session_id
        ].append(
            record
        )

    for sequence in sequences.values():
        sequence.sort(
            key=lambda record: (
                record.selection_event_num,
                record.request_event_num,
                record.selection_id,
            )
        )

    return sequences


def iter_transitions(
    sequence: list[SelectionRecord],
    *,
    scope: TransitionScope,
):
    for previous, current in zip(
        sequence,
        sequence[1:],
    ):
        same_request = (
            previous.request_id
            == current.request_id
        )

        if (
            scope == "cross_request"
            and same_request
        ):
            continue

        yield (
            previous,
            current,
        )


def transition_count_matrix(
    sequences: Mapping[
        str,
        list[SelectionRecord],
    ],
    *,
    scope: TransitionScope,
) -> np.ndarray:
    matrix = np.zeros(
        (
            len(STATES),
            len(STATES),
        ),
        dtype=int,
    )

    for sequence in sequences.values():
        for previous, current in (
            iter_transitions(
                sequence,
                scope=scope,
            )
        ):
            matrix[
                STATE_INDEX[
                    previous.adoption_outcome
                ],
                STATE_INDEX[
                    current.adoption_outcome
                ],
            ] += 1

    return matrix


def row_probability_matrix(
    counts: np.ndarray,
) -> np.ndarray:
    counts = np.asarray(
        counts,
        dtype=float,
    )

    if counts.shape != (
        len(STATES),
        len(STATES),
    ):
        raise ValueError(
            "Unexpected transition matrix shape."
        )

    probabilities = np.full(
        counts.shape,
        np.nan,
        dtype=float,
    )

    for row_index in range(
        counts.shape[0]
    ):
        total = float(
            np.sum(
                counts[
                    row_index
                ]
            )
        )

        if total <= 0:
            continue

        probabilities[
            row_index
        ] = (
            counts[
                row_index
            ]
            / total
        )

    return probabilities


def _normalized_entropy(
    counts: Iterable[int],
    *,
    category_count: int,
) -> float | None:
    values = np.asarray(
        list(counts),
        dtype=float,
    )

    total = float(
        np.sum(values)
    )

    if total <= 0:
        return None

    if category_count <= 1:
        return 0.0

    probabilities = (
        values[
            values > 0
        ]
        / total
    )

    entropy = -float(
        np.sum(
            probabilities
            * np.log(
                probabilities
            )
        )
    )

    maximum = math.log(
        category_count
    )

    if maximum == 0:
        return 0.0

    return entropy / maximum


def build_session_transition_metrics(
    sequences: Mapping[
        str,
        list[SelectionRecord],
    ],
) -> list[dict[str, object]]:
    rows: list[
        dict[str, object]
    ] = []

    for session_id, sequence in (
        sequences.items()
    ):
        state_counts = Counter(
            record.adoption_outcome
            for record in sequence
        )

        all_pairs = list(
            iter_transitions(
                sequence,
                scope="all",
            )
        )

        cross_pairs = list(
            iter_transitions(
                sequence,
                scope="cross_request",
            )
        )

        intra_count = (
            len(all_pairs)
            - len(cross_pairs)
        )

        all_self = sum(
            previous.adoption_outcome
            == current.adoption_outcome
            for previous, current
            in all_pairs
        )

        cross_self = sum(
            previous.adoption_outcome
            == current.adoption_outcome
            for previous, current
            in cross_pairs
        )

        pair_counts = Counter(
            (
                previous.adoption_outcome,
                current.adoption_outcome,
            )
            for previous, current
            in cross_pairs
        )

        transition_entropy = (
            _normalized_entropy(
                pair_counts.values(),
                category_count=(
                    len(STATES) ** 2
                ),
            )
        )

        state_entropy = (
            _normalized_entropy(
                (
                    state_counts[state]
                    for state in STATES
                ),
                category_count=(
                    len(STATES)
                ),
            )
        )

        selected_requests = {
            record.request_id
            for record in sequence
        }

        rows.append(
            {
                "session_id": session_id,
                "selection_count": (
                    len(sequence)
                ),
                "selected_request_count": (
                    len(
                        selected_requests
                    )
                ),
                "intra_request_transition_count": (
                    intra_count
                ),
                "cross_request_transition_count": (
                    len(
                        cross_pairs
                    )
                ),
                "all_transition_count": (
                    len(
                        all_pairs
                    )
                ),
                "all_self_transition_rate": (
                    all_self
                    / len(all_pairs)
                    if all_pairs
                    else None
                ),
                "cross_request_self_transition_rate": (
                    cross_self
                    / len(cross_pairs)
                    if cross_pairs
                    else None
                ),
                "state_entropy_normalized": (
                    state_entropy
                ),
                "cross_transition_entropy_normalized": (
                    transition_entropy
                ),
                "direct_selection_share": (
                    state_counts[
                        "direct_adoption"
                    ]
                    / len(sequence)
                    if sequence
                    else None
                ),
                "modified_selection_share": (
                    state_counts[
                        "modified_adoption"
                    ]
                    / len(sequence)
                    if sequence
                    else None
                ),
                "non_adoption_selection_share": (
                    state_counts[
                        "non_adoption"
                    ]
                    / len(sequence)
                    if sequence
                    else None
                ),
                "first_outcome": (
                    sequence[
                        0
                    ].adoption_outcome
                    if sequence
                    else ""
                ),
                "last_outcome": (
                    sequence[
                        -1
                    ].adoption_outcome
                    if sequence
                    else ""
                ),
            }
        )

    return rows


def positional_outcome_profile(
    sequences: Mapping[
        str,
        list[SelectionRecord],
    ],
) -> list[dict[str, object]]:
    """
    Describe adoption outcomes across normalized sequence
    position.

    Only sessions with at least two confirmed selections
    contribute because a one-selection session has no
    temporal trajectory.
    """

    phases = (
        "early",
        "middle",
        "late",
    )

    counts = {
        phase: Counter()
        for phase in phases
    }

    contributing_sessions = 0

    for sequence in sequences.values():
        n = len(sequence)

        if n < 2:
            continue

        contributing_sessions += 1

        for index, record in enumerate(
            sequence
        ):
            position = (
                index
                / (n - 1)
            )

            if position <= (
                1.0 / 3.0
            ):
                phase = "early"

            elif position <= (
                2.0 / 3.0
            ):
                phase = "middle"

            else:
                phase = "late"

            counts[
                phase
            ][
                record.adoption_outcome
            ] += 1

    rows: list[
        dict[str, object]
    ] = []

    for phase in phases:
        total = sum(
            counts[
                phase
            ].values()
        )

        for state in STATES:
            count = counts[
                phase
            ][state]

            rows.append(
                {
                    "phase": phase,
                    "outcome": state,
                    "outcome_label": (
                        STATE_LABELS[
                            state
                        ]
                    ),
                    "count": count,
                    "share_within_phase": (
                        count / total
                        if total
                        else None
                    ),
                    "phase_total": total,
                    "contributing_sessions": (
                        contributing_sessions
                    ),
                }
            )

    return rows


def endpoint_matrix(
    sequences: Mapping[
        str,
        list[SelectionRecord],
    ],
) -> tuple[
    np.ndarray,
    np.ndarray,
    int,
]:
    counts = np.zeros(
        (
            len(STATES),
            len(STATES),
        ),
        dtype=int,
    )

    eligible = 0

    for sequence in sequences.values():
        if len(sequence) < 2:
            continue

        eligible += 1

        first = sequence[
            0
        ].adoption_outcome

        last = sequence[
            -1
        ].adoption_outcome

        counts[
            STATE_INDEX[
                first
            ],
            STATE_INDEX[
                last
            ],
        ] += 1

    probabilities = (
        row_probability_matrix(
            counts
        )
    )

    return (
        counts,
        probabilities,
        eligible,
    )


def bootstrap_transition_probabilities(
    sequences: Mapping[
        str,
        list[SelectionRecord],
    ],
    *,
    scope: TransitionScope,
    repeats: int = 500,
    random_state: int = 42,
) -> list[dict[str, object]]:
    """
    Bootstrap transition probabilities by resampling whole
    sessions rather than individual transitions.

    Resampling sessions preserves dependence among
    transitions originating from the same writing session.
    """

    if repeats < 1:
        raise ValueError(
            "repeats must be >= 1."
        )

    session_ids = tuple(
        sequences.keys()
    )

    if not session_ids:
        raise ValueError(
            "No sessions available."
        )

    per_session: list[
        np.ndarray
    ] = []

    for session_id in session_ids:
        matrix = np.zeros(
            (
                len(STATES),
                len(STATES),
            ),
            dtype=int,
        )

        for previous, current in (
            iter_transitions(
                sequences[
                    session_id
                ],
                scope=scope,
            )
        ):
            matrix[
                STATE_INDEX[
                    previous.adoption_outcome
                ],
                STATE_INDEX[
                    current.adoption_outcome
                ],
            ] += 1

        per_session.append(
            matrix
        )

    session_array = np.asarray(
        per_session,
        dtype=int,
    )

    observed_counts = np.sum(
        session_array,
        axis=0,
    )

    observed_probabilities = (
        row_probability_matrix(
            observed_counts
        )
    )

    rng = np.random.default_rng(
        random_state
    )

    draws: dict[
        tuple[int, int],
        list[float],
    ] = {
        (i, j): []
        for i in range(
            len(STATES)
        )
        for j in range(
            len(STATES)
        )
    }

    n_sessions = len(
        session_ids
    )

    for _ in range(
        repeats
    ):
        indices = rng.integers(
            0,
            n_sessions,
            size=n_sessions,
        )

        counts = np.sum(
            session_array[
                indices
            ],
            axis=0,
        )

        probabilities = (
            row_probability_matrix(
                counts
            )
        )

        for i in range(
            len(STATES)
        ):
            for j in range(
                len(STATES)
            ):
                value = probabilities[
                    i,
                    j
                ]

                if np.isfinite(
                    value
                ):
                    draws[
                        (i, j)
                    ].append(
                        float(value)
                    )

    rows: list[
        dict[str, object]
    ] = []

    for i, from_state in enumerate(
        STATES
    ):
        for j, to_state in enumerate(
            STATES
        ):
            values = np.asarray(
                draws[
                    (i, j)
                ],
                dtype=float,
            )

            probability = (
                observed_probabilities[
                    i,
                    j
                ]
            )

            rows.append(
                {
                    "scope": scope,
                    "from_state": (
                        from_state
                    ),
                    "from_label": (
                        STATE_LABELS[
                            from_state
                        ]
                    ),
                    "to_state": (
                        to_state
                    ),
                    "to_label": (
                        STATE_LABELS[
                            to_state
                        ]
                    ),
                    "count": int(
                        observed_counts[
                            i,
                            j
                        ]
                    ),
                    "probability": (
                        float(
                            probability
                        )
                        if np.isfinite(
                            probability
                        )
                        else None
                    ),
                    "bootstrap_mean": (
                        float(
                            np.mean(
                                values
                            )
                        )
                        if len(values)
                        else None
                    ),
                    "ci_2_5": (
                        float(
                            np.quantile(
                                values,
                                0.025,
                            )
                        )
                        if len(values)
                        else None
                    ),
                    "ci_97_5": (
                        float(
                            np.quantile(
                                values,
                                0.975,
                            )
                        )
                        if len(values)
                        else None
                    ),
                    "valid_bootstrap_draws": (
                        len(values)
                    ),
                    "bootstrap_repeats": (
                        repeats
                    ),
                }
            )

    return rows


def matrix_rows(
    counts: np.ndarray,
    probabilities: np.ndarray,
    *,
    scope: str,
) -> list[dict[str, object]]:
    rows: list[
        dict[str, object]
    ] = []

    for i, from_state in enumerate(
        STATES
    ):
        for j, to_state in enumerate(
            STATES
        ):
            probability = (
                probabilities[
                    i,
                    j
                ]
            )

            rows.append(
                {
                    "scope": scope,
                    "from_state": (
                        from_state
                    ),
                    "from_label": (
                        STATE_LABELS[
                            from_state
                        ]
                    ),
                    "to_state": (
                        to_state
                    ),
                    "to_label": (
                        STATE_LABELS[
                            to_state
                        ]
                    ),
                    "count": int(
                        counts[
                            i,
                            j
                        ]
                    ),
                    "probability": (
                        float(
                            probability
                        )
                        if np.isfinite(
                            probability
                        )
                        else None
                    ),
                }
            )

    return rows
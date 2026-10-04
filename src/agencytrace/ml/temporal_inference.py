from __future__ import annotations

from collections import Counter
from typing import Mapping

import numpy as np

from agencytrace.ml.transitions import (
    STATES,
    STATE_INDEX,
    SelectionRecord,
    TransitionScope,
    row_probability_matrix,
    transition_count_matrix,
)


PHASES: tuple[str, ...] = (
    "early",
    "middle",
    "late",
)


def _phase_for_position(
    index: int,
    length: int,
) -> str:
    if length < 2:
        raise ValueError(
            "Temporal phase requires at least "
            "two selections."
        )

    position = index / (
        length - 1
    )

    if position <= (
        1.0 / 3.0
    ):
        return "early"

    if position <= (
        2.0 / 3.0
    ):
        return "middle"

    return "late"


def _benjamini_hochberg(
    p_values: list[float],
) -> list[float]:
    """
    Benjamini-Hochberg false-discovery-rate correction.
    """

    if not p_values:
        return []

    values = np.asarray(
        p_values,
        dtype=float,
    )

    if np.any(
        (
            values < 0
        )
        | (
            values > 1
        )
    ):
        raise ValueError(
            "p-values must lie in [0, 1]."
        )

    order = np.argsort(
        values
    )

    ranked = values[
        order
    ]

    m = len(values)

    adjusted = np.empty(
        m,
        dtype=float,
    )

    running = 1.0

    for reverse_index in range(
        m - 1,
        -1,
        -1,
    ):
        rank = (
            reverse_index
            + 1
        )

        candidate = (
            ranked[
                reverse_index
            ]
            * m
            / rank
        )

        running = min(
            running,
            candidate,
        )

        adjusted[
            reverse_index
        ] = min(
            1.0,
            running,
        )

    output = np.empty(
        m,
        dtype=float,
    )

    output[
        order
    ] = adjusted

    return [
        float(value)
        for value in output
    ]


def _empirical_two_sided_p(
    observed: float,
    null_values: np.ndarray,
) -> float:
    """
    Two-sided empirical permutation p-value.

    The two tails are evaluated relative to the observed
    statistic, with a +1 correction.
    """

    if len(
        null_values
    ) == 0:
        raise ValueError(
            "Null distribution is empty."
        )

    upper = (
        1
        + int(
            np.sum(
                null_values
                >= observed
            )
        )
    ) / (
        len(null_values)
        + 1
    )

    lower = (
        1
        + int(
            np.sum(
                null_values
                <= observed
            )
        )
    ) / (
        len(null_values)
        + 1
    )

    return min(
        1.0,
        2.0
        * min(
            upper,
            lower,
        ),
    )


def permutation_transition_test(
    sequences: Mapping[
        str,
        list[SelectionRecord],
    ],
    *,
    scope: TransitionScope = (
        "cross_request"
    ),
    repeats: int = 1000,
    random_state: int = 42,
) -> tuple[
    list[dict[str, object]],
    dict[str, object],
]:
    """
    Test serial ordering against a within-session
    permutation null.

    Outcomes are shuffled only within their original
    session. This preserves:

    - each session's selection count;
    - each session's outcome composition;
    - request IDs and adjacency structure;
    - the corpus distribution of session lengths.

    The null therefore asks whether observed sequential
    ordering contains information beyond session-level
    response-use composition.
    """

    if repeats < 1:
        raise ValueError(
            "repeats must be >= 1."
        )

    observed_counts = (
        transition_count_matrix(
            sequences,
            scope=scope,
        )
    )

    observed_probabilities = (
        row_probability_matrix(
            observed_counts
        )
    )

    observed_total = int(
        np.sum(
            observed_counts
        )
    )

    if observed_total <= 0:
        raise ValueError(
            "No observed transitions."
        )

    observed_self_rate = float(
        np.trace(
            observed_counts
        )
        / observed_total
    )

    payloads: list[
        tuple[
            tuple[str, ...],
            np.ndarray,
        ]
    ] = []

    for sequence in sequences.values():
        if len(sequence) < 2:
            continue

        request_ids = tuple(
            record.request_id
            for record in sequence
        )

        state_indices = np.asarray(
            [
                STATE_INDEX[
                    record.adoption_outcome
                ]
                for record in sequence
            ],
            dtype=int,
        )

        payloads.append(
            (
                request_ids,
                state_indices,
            )
        )

    rng = np.random.default_rng(
        random_state
    )

    null_probabilities = np.full(
        (
            repeats,
            len(STATES),
            len(STATES),
        ),
        np.nan,
        dtype=float,
    )

    null_self_rates = np.empty(
        repeats,
        dtype=float,
    )

    for repeat in range(
        repeats
    ):
        counts = np.zeros(
            (
                len(STATES),
                len(STATES),
            ),
            dtype=int,
        )

        for (
            request_ids,
            states,
        ) in payloads:
            shuffled = rng.permutation(
                states
            )

            for index in range(
                len(
                    shuffled
                )
                - 1
            ):
                if (
                    scope
                    == "cross_request"
                    and request_ids[
                        index
                    ]
                    == request_ids[
                        index + 1
                    ]
                ):
                    continue

                counts[
                    shuffled[
                        index
                    ],
                    shuffled[
                        index + 1
                    ],
                ] += 1

        probabilities = (
            row_probability_matrix(
                counts
            )
        )

        null_probabilities[
            repeat
        ] = probabilities

        total = int(
            np.sum(
                counts
            )
        )

        null_self_rates[
            repeat
        ] = (
            float(
                np.trace(
                    counts
                )
                / total
            )
            if total
            else np.nan
        )

    rows: list[
        dict[str, object]
    ] = []

    raw_p_values: list[
        float
    ] = []

    for i, from_state in enumerate(
        STATES
    ):
        for j, to_state in enumerate(
            STATES
        ):
            observed = (
                observed_probabilities[
                    i,
                    j
                ]
            )

            null = (
                null_probabilities[
                    :,
                    i,
                    j,
                ]
            )

            null = null[
                np.isfinite(
                    null
                )
            ]

            if (
                not np.isfinite(
                    observed
                )
                or len(null) == 0
            ):
                p_value = 1.0
                null_mean = None
                lower = None
                upper = None
                difference = None
                ratio = None

            else:
                observed_float = float(
                    observed
                )

                null_mean_float = float(
                    np.mean(
                        null
                    )
                )

                p_value = (
                    _empirical_two_sided_p(
                        observed_float,
                        null,
                    )
                )

                null_mean = (
                    null_mean_float
                )

                lower = float(
                    np.quantile(
                        null,
                        0.025,
                    )
                )

                upper = float(
                    np.quantile(
                        null,
                        0.975,
                    )
                )

                difference = (
                    observed_float
                    - null_mean_float
                )

                ratio = (
                    observed_float
                    / null_mean_float
                    if null_mean_float
                    > 0
                    else None
                )

            raw_p_values.append(
                p_value
            )

            rows.append(
                {
                    "scope": scope,
                    "from_state": (
                        from_state
                    ),
                    "to_state": (
                        to_state
                    ),
                    "observed_count": int(
                        observed_counts[
                            i,
                            j
                        ]
                    ),
                    "observed_probability": (
                        float(
                            observed
                        )
                        if np.isfinite(
                            observed
                        )
                        else None
                    ),
                    "null_mean_probability": (
                        null_mean
                    ),
                    "difference_from_null": (
                        difference
                    ),
                    "probability_ratio": (
                        ratio
                    ),
                    "null_ci_2_5": lower,
                    "null_ci_97_5": upper,
                    "permutation_p": (
                        p_value
                    ),
                    "permutation_repeats": (
                        repeats
                    ),
                }
            )

    adjusted = (
        _benjamini_hochberg(
            raw_p_values
        )
    )

    for row, q_value in zip(
        rows,
        adjusted,
        strict=True,
    ):
        row[
            "fdr_q"
        ] = q_value

    valid_self = (
        null_self_rates[
            np.isfinite(
                null_self_rates
            )
        ]
    )

    self_summary = {
        "scope": scope,
        "observed_self_transition_rate": (
            observed_self_rate
        ),
        "null_mean_self_transition_rate": (
            float(
                np.mean(
                    valid_self
                )
            )
        ),
        "difference_from_null": (
            observed_self_rate
            - float(
                np.mean(
                    valid_self
                )
            )
        ),
        "null_ci_2_5": float(
            np.quantile(
                valid_self,
                0.025,
            )
        ),
        "null_ci_97_5": float(
            np.quantile(
                valid_self,
                0.975,
            )
        ),
        "permutation_p": (
            _empirical_two_sided_p(
                observed_self_rate,
                valid_self,
            )
        ),
        "permutation_repeats": repeats,
    }

    return (
        rows,
        self_summary,
    )


def session_weighted_phase_rows(
    sequences: Mapping[
        str,
        list[SelectionRecord],
    ],
) -> list[dict[str, object]]:
    """
    Compute phase-specific outcome shares with one row per
    session and phase.

    Unlike pooled event counts, each contributing session
    receives equal weight in subsequent analyses.
    """

    rows: list[
        dict[str, object]
    ] = []

    for session_id, sequence in (
        sequences.items()
    ):
        n = len(sequence)

        if n < 2:
            continue

        phase_counts = {
            phase: Counter()
            for phase in PHASES
        }

        for index, record in enumerate(
            sequence
        ):
            phase = (
                _phase_for_position(
                    index,
                    n,
                )
            )

            phase_counts[
                phase
            ][
                record.adoption_outcome
            ] += 1

        for phase in PHASES:
            total = sum(
                phase_counts[
                    phase
                ].values()
            )

            if total == 0:
                continue

            row: dict[
                str,
                object,
            ] = {
                "session_id": (
                    session_id
                ),
                "phase": phase,
                "phase_selection_count": (
                    total
                ),
            }

            for state in STATES:
                row[
                    f"{state}_share"
                ] = (
                    phase_counts[
                        phase
                    ][state]
                    / total
                )

            rows.append(
                row
            )

    return rows


def summarize_session_weighted_phases(
    phase_rows: list[
        dict[str, object]
    ],
    *,
    bootstrap_repeats: int = 1000,
    random_state: int = 42,
) -> list[dict[str, object]]:
    if bootstrap_repeats < 1:
        raise ValueError(
            "bootstrap_repeats must be >= 1."
        )

    rng = np.random.default_rng(
        random_state
    )

    output: list[
        dict[str, object]
    ] = []

    for phase in PHASES:
        members = [
            row
            for row in phase_rows
            if row[
                "phase"
            ] == phase
        ]

        if not members:
            continue

        for state in STATES:
            field = (
                f"{state}_share"
            )

            values = np.asarray(
                [
                    float(
                        row[field]
                    )
                    for row in members
                ],
                dtype=float,
            )

            bootstrap_means = np.empty(
                bootstrap_repeats,
                dtype=float,
            )

            for repeat in range(
                bootstrap_repeats
            ):
                sample = rng.choice(
                    values,
                    size=len(values),
                    replace=True,
                )

                bootstrap_means[
                    repeat
                ] = float(
                    np.mean(
                        sample
                    )
                )

            output.append(
                {
                    "phase": phase,
                    "outcome": state,
                    "sessions": (
                        len(values)
                    ),
                    "mean_session_share": (
                        float(
                            np.mean(
                                values
                            )
                        )
                    ),
                    "median_session_share": (
                        float(
                            np.median(
                                values
                            )
                        )
                    ),
                    "ci_2_5": float(
                        np.quantile(
                            bootstrap_means,
                            0.025,
                        )
                    ),
                    "ci_97_5": float(
                        np.quantile(
                            bootstrap_means,
                            0.975,
                        )
                    ),
                    "bootstrap_repeats": (
                        bootstrap_repeats
                    ),
                }
            )

    return output


def early_late_change(
    phase_rows: list[
        dict[str, object]
    ],
    *,
    bootstrap_repeats: int = 1000,
    random_state: int = 42,
) -> list[dict[str, object]]:
    """
    Estimate within-session late-minus-early change.

    Only sessions containing both early and late phases are
    used, which gives each session equal weight.
    """

    by_session: dict[
        str,
        dict[
            str,
            dict[str, object],
        ],
    ] = {}

    for row in phase_rows:
        session_id = str(
            row[
                "session_id"
            ]
        )

        phase = str(
            row[
                "phase"
            ]
        )

        by_session.setdefault(
            session_id,
            {},
        )[
            phase
        ] = row

    eligible = [
        (
            session_id,
            phases[
                "early"
            ],
            phases[
                "late"
            ],
        )
        for session_id, phases
        in by_session.items()
        if (
            "early"
            in phases
            and "late"
            in phases
        )
    ]

    if not eligible:
        raise ValueError(
            "No sessions contain both early "
            "and late phases."
        )

    rng = np.random.default_rng(
        random_state
    )

    output: list[
        dict[str, object]
    ] = []

    for state in STATES:
        field = (
            f"{state}_share"
        )

        differences = np.asarray(
            [
                float(
                    late[field]
                )
                - float(
                    early[field]
                )
                for (
                    _,
                    early,
                    late,
                )
                in eligible
            ],
            dtype=float,
        )

        bootstrap_means = np.empty(
            bootstrap_repeats,
            dtype=float,
        )

        for repeat in range(
            bootstrap_repeats
        ):
            sample = rng.choice(
                differences,
                size=len(
                    differences
                ),
                replace=True,
            )

            bootstrap_means[
                repeat
            ] = float(
                np.mean(
                    sample
                )
            )

        output.append(
            {
                "outcome": state,
                "sessions": (
                    len(
                        differences
                    )
                ),
                "mean_late_minus_early": (
                    float(
                        np.mean(
                            differences
                        )
                    )
                ),
                "median_late_minus_early": (
                    float(
                        np.median(
                            differences
                        )
                    )
                ),
                "ci_2_5": float(
                    np.quantile(
                        bootstrap_means,
                        0.025,
                    )
                ),
                "ci_97_5": float(
                    np.quantile(
                        bootstrap_means,
                        0.975,
                    )
                ),
                "bootstrap_repeats": (
                    bootstrap_repeats
                ),
            }
        )

    return output
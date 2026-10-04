from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    roc_auc_score,
)


HIGHER_IS_BETTER: tuple[str, ...] = (
    "roc_auc",
    "average_precision",
    "balanced_accuracy",
    "macro_f1",
)

LOWER_IS_BETTER: tuple[str, ...] = (
    "brier_score",
)

INFERENCE_METRICS: tuple[str, ...] = (
    *HIGHER_IS_BETTER,
    *LOWER_IS_BETTER,
)


@dataclass(frozen=True, slots=True)
class PredictionRecord:
    task: str
    model: str
    session_id: str
    selection_id: str

    actual: int
    predicted: int

    positive_probability: float


def load_binary_predictions(
    path: Path,
) -> list[PredictionRecord]:
    if not path.is_file():
        raise FileNotFoundError(path)

    required = {
        "task",
        "model",
        "session_id",
        "selection_id",
        "actual",
        "predicted",
        "positive_probability",
    }

    rows: list[
        PredictionRecord
    ] = []

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(
            handle
        )

        if reader.fieldnames is None:
            raise ValueError(
                "Prediction file has no header."
            )

        missing = (
            required
            - set(
                reader.fieldnames
            )
        )

        if missing:
            raise ValueError(
                "Prediction file is missing "
                f"required columns: "
                f"{sorted(missing)}"
            )

        for raw in reader:
            actual = int(
                raw["actual"]
            )

            predicted = int(
                raw["predicted"]
            )

            probability = float(
                raw[
                    "positive_probability"
                ]
            )

            if actual not in (
                0,
                1,
            ):
                raise ValueError(
                    "Actual labels must be "
                    "binary."
                )

            if predicted not in (
                0,
                1,
            ):
                raise ValueError(
                    "Predicted labels must be "
                    "binary."
                )

            if not (
                0.0
                <= probability
                <= 1.0
            ):
                raise ValueError(
                    "Prediction probability "
                    "must lie in [0, 1]."
                )

            rows.append(
                PredictionRecord(
                    task=raw[
                        "task"
                    ],
                    model=raw[
                        "model"
                    ],
                    session_id=raw[
                        "session_id"
                    ],
                    selection_id=raw[
                        "selection_id"
                    ],
                    actual=actual,
                    predicted=predicted,
                    positive_probability=(
                        probability
                    ),
                )
            )

    identities = [
        (
            row.task,
            row.model,
            row.session_id,
            row.selection_id,
        )
        for row in rows
    ]

    if len(identities) != len(
        set(identities)
    ):
        raise ValueError(
            "Duplicate out-of-fold "
            "prediction identity."
        )

    return rows


def binary_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    probability: np.ndarray,
) -> dict[str, float] | None:
    actual = np.asarray(
        actual,
        dtype=int,
    )

    predicted = np.asarray(
        predicted,
        dtype=int,
    )

    probability = np.asarray(
        probability,
        dtype=float,
    )

    if not (
        len(actual)
        == len(predicted)
        == len(probability)
    ):
        raise ValueError(
            "Metric arrays have "
            "different lengths."
        )

    if len(actual) == 0:
        raise ValueError(
            "Metric arrays are empty."
        )

    if len(
        np.unique(
            actual
        )
    ) < 2:
        return None

    return {
        "roc_auc": float(
            roc_auc_score(
                actual,
                probability,
            )
        ),
        "average_precision": float(
            average_precision_score(
                actual,
                probability,
            )
        ),
        "balanced_accuracy": float(
            balanced_accuracy_score(
                actual,
                predicted,
            )
        ),
        "macro_f1": float(
            f1_score(
                actual,
                predicted,
                average="macro",
                zero_division=0,
            )
        ),
        "brier_score": float(
            brier_score_loss(
                actual,
                probability,
            )
        ),
    }


def _improvement(
    *,
    metric: str,
    candidate: float,
    reference: float,
) -> float:
    if metric in HIGHER_IS_BETTER:
        return (
            candidate
            - reference
        )

    if metric in LOWER_IS_BETTER:
        return (
            reference
            - candidate
        )

    raise ValueError(
        f"Unknown metric: {metric}"
    )


def _empirical_two_sided_p(
    values: np.ndarray,
) -> float:
    if len(values) == 0:
        raise ValueError(
            "Bootstrap distribution "
            "is empty."
        )

    lower = (
        1
        + int(
            np.sum(
                values <= 0.0
            )
        )
    ) / (
        len(values)
        + 1
    )

    upper = (
        1
        + int(
            np.sum(
                values >= 0.0
            )
        )
    ) / (
        len(values)
        + 1
    )

    return min(
        1.0,
        2.0
        * min(
            lower,
            upper,
        ),
    )


def _task_arrays(
    rows: list[
        PredictionRecord
    ],
    *,
    task: str,
    candidate_model: str,
    reference_model: str,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    candidate = {
        (
            row.session_id,
            row.selection_id,
        ): row
        for row in rows
        if (
            row.task == task
            and row.model
            == candidate_model
        )
    }

    reference = {
        (
            row.session_id,
            row.selection_id,
        ): row
        for row in rows
        if (
            row.task == task
            and row.model
            == reference_model
        )
    }

    if not candidate:
        raise ValueError(
            f"No rows for task={task}, "
            f"model={candidate_model}."
        )

    if not reference:
        raise ValueError(
            f"No rows for reference model "
            f"{reference_model}."
        )

    if set(candidate) != set(
        reference
    ):
        raise ValueError(
            "Candidate and reference "
            "predictions are not aligned."
        )

    keys = sorted(
        candidate
    )

    actual = np.asarray(
        [
            candidate[key].actual
            for key in keys
        ],
        dtype=int,
    )

    reference_actual = (
        np.asarray(
            [
                reference[key].actual
                for key in keys
            ],
            dtype=int,
        )
    )

    if not np.array_equal(
        actual,
        reference_actual,
    ):
        raise ValueError(
            "Actual labels differ across "
            "model predictions."
        )

    sessions = np.asarray(
        [
            key[0]
            for key in keys
        ],
        dtype=object,
    )

    candidate_predicted = np.asarray(
        [
            candidate[
                key
            ].predicted
            for key in keys
        ],
        dtype=int,
    )

    candidate_probability = (
        np.asarray(
            [
                candidate[
                    key
                ].positive_probability
                for key in keys
            ],
            dtype=float,
        )
    )

    reference_predicted = (
        np.asarray(
            [
                reference[
                    key
                ].predicted
                for key in keys
            ],
            dtype=int,
        )
    )

    reference_probability = (
        np.asarray(
            [
                reference[
                    key
                ].positive_probability
                for key in keys
            ],
            dtype=float,
        )
    )

    return (
        actual,
        sessions,
        candidate_predicted,
        candidate_probability,
        reference_predicted,
        reference_probability,
    )


def bootstrap_model_improvement(
    rows: list[
        PredictionRecord
    ],
    *,
    task: str,
    candidate_model: str,
    reference_model: str = (
        "prior_baseline"
    ),
    repeats: int = 1000,
    random_state: int = 42,
) -> list[dict[str, object]]:
    """
    Compare an OOF model against a reference using
    session-cluster bootstrap resampling.

    Whole sessions are sampled with replacement so all
    selections from a session remain together.
    """

    if repeats < 1:
        raise ValueError(
            "repeats must be >= 1."
        )

    (
        actual,
        sessions,
        candidate_predicted,
        candidate_probability,
        reference_predicted,
        reference_probability,
    ) = _task_arrays(
        rows,
        task=task,
        candidate_model=(
            candidate_model
        ),
        reference_model=(
            reference_model
        ),
    )

    observed_candidate = (
        binary_metrics(
            actual,
            candidate_predicted,
            candidate_probability,
        )
    )

    observed_reference = (
        binary_metrics(
            actual,
            reference_predicted,
            reference_probability,
        )
    )

    if (
        observed_candidate is None
        or observed_reference is None
    ):
        raise RuntimeError(
            "Observed data do not contain "
            "both classes."
        )

    unique_sessions = np.asarray(
        sorted(
            set(
                sessions.tolist()
            )
        ),
        dtype=object,
    )

    session_indices = {
        session_id: np.flatnonzero(
            sessions
            == session_id
        )
        for session_id
        in unique_sessions
    }

    rng = np.random.default_rng(
        random_state
    )

    bootstrap_values = {
        metric: []
        for metric in (
            INFERENCE_METRICS
        )
    }

    valid_draws = 0

    for _ in range(
        repeats
    ):
        sampled_sessions = rng.choice(
            unique_sessions,
            size=len(
                unique_sessions
            ),
            replace=True,
        )

        indices = np.concatenate(
            [
                session_indices[
                    session_id
                ]
                for session_id
                in sampled_sessions
            ]
        )

        candidate_metrics = (
            binary_metrics(
                actual[
                    indices
                ],
                candidate_predicted[
                    indices
                ],
                candidate_probability[
                    indices
                ],
            )
        )

        reference_metrics = (
            binary_metrics(
                actual[
                    indices
                ],
                reference_predicted[
                    indices
                ],
                reference_probability[
                    indices
                ],
            )
        )

        if (
            candidate_metrics is None
            or reference_metrics
            is None
        ):
            continue

        valid_draws += 1

        for metric in (
            INFERENCE_METRICS
        ):
            bootstrap_values[
                metric
            ].append(
                _improvement(
                    metric=metric,
                    candidate=(
                        candidate_metrics[
                            metric
                        ]
                    ),
                    reference=(
                        reference_metrics[
                            metric
                        ]
                    ),
                )
            )

    if valid_draws == 0:
        raise RuntimeError(
            "No valid bootstrap draws."
        )

    output: list[
        dict[str, object]
    ] = []

    for metric in (
        INFERENCE_METRICS
    ):
        values = np.asarray(
            bootstrap_values[
                metric
            ],
            dtype=float,
        )

        observed_improvement = (
            _improvement(
                metric=metric,
                candidate=(
                    observed_candidate[
                        metric
                    ]
                ),
                reference=(
                    observed_reference[
                        metric
                    ]
                ),
            )
        )

        output.append(
            {
                "task": task,
                "candidate_model": (
                    candidate_model
                ),
                "reference_model": (
                    reference_model
                ),
                "metric": metric,
                "direction": (
                    "higher_is_better"
                    if metric
                    in HIGHER_IS_BETTER
                    else "lower_is_better"
                ),
                "candidate_value": (
                    observed_candidate[
                        metric
                    ]
                ),
                "reference_value": (
                    observed_reference[
                        metric
                    ]
                ),
                "observed_improvement": (
                    observed_improvement
                ),
                "bootstrap_mean_improvement": (
                    float(
                        np.mean(
                            values
                        )
                    )
                ),
                "ci_2_5": float(
                    np.quantile(
                        values,
                        0.025,
                    )
                ),
                "ci_97_5": float(
                    np.quantile(
                        values,
                        0.975,
                    )
                ),
                "bootstrap_p": (
                    _empirical_two_sided_p(
                        values
                    )
                ),
                "valid_bootstrap_draws": (
                    len(values)
                ),
                "bootstrap_repeats": (
                    repeats
                ),
                "sessions": (
                    len(
                        unique_sessions
                    )
                ),
                "rows": (
                    len(
                        actual
                    )
                ),
            }
        )

    return output
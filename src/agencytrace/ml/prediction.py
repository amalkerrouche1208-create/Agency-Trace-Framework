from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import (
    LogisticRegression,
)
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    log_loss,
)
from sklearn.model_selection import (
    StratifiedGroupKFold,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    StandardScaler,
)

from agencytrace.ml.transitions import (
    STATES,
)


OUTCOME_INDEX = {
    outcome: index
    for index, outcome in enumerate(
        STATES
    )
}


# Leakage-controlled predictors available at or before
# the selected AI text is inserted.
#
# Deliberately excluded:
# - final AI retention;
# - final AI share;
# - deletion ratio;
# - surviving characters;
# - final session duration;
# - adoption outcomes;
# - log_prior_selection_count because it is deterministically
#   redundant with log_selection_ordinal;
# - open_latency_missing because open_to_selection_ms is complete
#   for the validated corpus.
FEATURE_NAMES: tuple[str, ...] = (
    "log_inserted_chars",
    "selected_index",
    "log_request_to_selection_ms",
    "log_open_to_selection_ms",
    "log_selection_ordinal",
    "log_prior_mean_inserted_chars",
    "log_prior_mean_request_latency_ms",
    "log_event_index",
    "log_event_gap_from_previous_selection",
)


@dataclass(frozen=True, slots=True)
class InsertionRecord:
    session_id: str
    request_id: str
    selection_id: str

    request_event_num: int
    selection_event_num: int

    selected_index: int

    inserted_chars: int

    request_to_selection_ms: float
    open_to_selection_ms: (
        float | None
    )

    adoption_outcome: str


@dataclass(frozen=True, slots=True)
class PredictionRow:
    session_id: str
    selection_id: str
    outcome: str
    features: tuple[
        float,
        ...,
    ]


def _optional_float(
    value: str,
) -> float | None:
    value = value.strip()

    if value == "":
        return None

    parsed = float(
        value
    )

    if not math.isfinite(
        parsed
    ):
        return None

    return parsed


def load_insertion_records(
    path: Path,
) -> list[InsertionRecord]:
    if not path.is_file():
        raise FileNotFoundError(path)

    required = {
        "session_id",
        "request_id",
        "selection_id",
        "request_event_num",
        "selection_event_num",
        "selected_index",
        "inserted_chars",
        "request_to_selection_ms",
        "open_to_selection_ms",
        "adoption_outcome",
    }

    records: list[
        InsertionRecord
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
                "Selection metrics have no header."
            )

        missing = (
            required
            - set(
                reader.fieldnames
            )
        )

        if missing:
            raise ValueError(
                "Selection metrics are missing "
                f"required columns: "
                f"{sorted(missing)}"
            )

        for raw in reader:
            outcome = (
                raw[
                    "adoption_outcome"
                ]
                .strip()
            )

            if outcome not in (
                OUTCOME_INDEX
            ):
                raise ValueError(
                    "Unknown adoption outcome: "
                    f"{outcome!r}"
                )

            request_latency = float(
                raw[
                    "request_to_selection_ms"
                ]
            )

            if (
                not math.isfinite(
                    request_latency
                )
                or request_latency < 0
            ):
                raise ValueError(
                    "Invalid request-to-selection "
                    "latency."
                )

            inserted_chars = int(
                raw[
                    "inserted_chars"
                ]
            )

            if inserted_chars < 0:
                raise ValueError(
                    "inserted_chars cannot "
                    "be negative."
                )

            records.append(
                InsertionRecord(
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
                    selected_index=int(
                        raw[
                            "selected_index"
                        ]
                    ),
                    inserted_chars=(
                        inserted_chars
                    ),
                    request_to_selection_ms=(
                        request_latency
                    ),
                    open_to_selection_ms=(
                        _optional_float(
                            raw[
                                "open_to_selection_ms"
                            ]
                        )
                    ),
                    adoption_outcome=(
                        outcome
                    ),
                )
            )

    identities = {
        (
            record.session_id,
            record.selection_id,
        )
        for record in records
    }

    if len(identities) != len(
        records
    ):
        raise ValueError(
            "Duplicate selection identity."
        )

    return records


def build_prediction_rows(
    records: list[
        InsertionRecord
    ],
) -> list[PredictionRow]:
    """
    Build leakage-controlled predictors available by the
    time the selected AI text is inserted.

    The eventual adoption outcome is used only as the
    retrospective prediction target.

    Features derived from final document state or later
    editing are deliberately excluded.
    """

    by_session: dict[
        str,
        list[InsertionRecord],
    ] = {}

    for record in records:
        by_session.setdefault(
            record.session_id,
            [],
        ).append(
            record
        )

    rows: list[
        PredictionRow
    ] = []

    for session_id, sequence in (
        by_session.items()
    ):
        sequence.sort(
            key=lambda record: (
                record.selection_event_num,
                record.request_event_num,
                record.selection_id,
            )
        )

        cumulative_inserted = 0.0
        cumulative_request_latency = (
            0.0
        )

        previous_event: int | None = (
            None
        )

        for index, record in enumerate(
            sequence
        ):
            prior_count = index

            if prior_count:
                prior_mean_inserted = (
                    cumulative_inserted
                    / prior_count
                )

                prior_mean_latency = (
                    cumulative_request_latency
                    / prior_count
                )

            else:
                prior_mean_inserted = (
                    0.0
                )

                prior_mean_latency = (
                    0.0
                )

            open_latency = (
                record.open_to_selection_ms
            )

            if previous_event is None:
                event_gap = 0
            else:
                event_gap = max(
                    0,
                    (
                        record.selection_event_num
                        - previous_event
                    ),
                )

            features = (
                math.log1p(
                    record.inserted_chars
                ),
                float(
                    record.selected_index
                ),
                math.log1p(
                    record.request_to_selection_ms
                ),
                (
                    math.log1p(
                        open_latency
                    )
                    if (
                        open_latency
                        is not None
                        and open_latency >= 0
                    )
                    else float(
                        "nan"
                    )
                ),
                math.log1p(
                    index + 1
                ),
                math.log1p(
                    prior_mean_inserted
                ),
                math.log1p(
                    prior_mean_latency
                ),
                math.log1p(
                    max(
                        0,
                        record.selection_event_num,
                    )
                ),
                math.log1p(
                    event_gap
                ),
            )

            rows.append(
                PredictionRow(
                    session_id=(
                        session_id
                    ),
                    selection_id=(
                        record.selection_id
                    ),
                    outcome=(
                        record.adoption_outcome
                    ),
                    features=features,
                )
            )

            cumulative_inserted += (
                record.inserted_chars
            )

            cumulative_request_latency += (
                record.request_to_selection_ms
            )

            previous_event = (
                record.selection_event_num
            )

    return rows


def rows_to_arrays(
    rows: list[
        PredictionRow
    ],
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    if not rows:
        raise ValueError(
            "Prediction dataset is empty."
        )

    x = np.asarray(
        [
            row.features
            for row in rows
        ],
        dtype=float,
    )

    y = np.asarray(
        [
            OUTCOME_INDEX[
                row.outcome
            ]
            for row in rows
        ],
        dtype=int,
    )

    groups = np.asarray(
        [
            row.session_id
            for row in rows
        ],
        dtype=object,
    )

    if x.shape[1] != len(
        FEATURE_NAMES
    ):
        raise RuntimeError(
            "Feature matrix width does not "
            "match FEATURE_NAMES."
        )

    return (
        x,
        y,
        groups,
    )


def build_models(
    *,
    random_state: int = 42,
) -> dict[
    str,
    object,
]:
    return {
        "prior_baseline": Pipeline(
            [
                (
                    "imputer",
                    SimpleImputer(
                        strategy="median",
                    ),
                ),
                (
                    "model",
                    DummyClassifier(
                        strategy="prior",
                    ),
                ),
            ]
        ),
        "logistic": Pipeline(
            [
                (
                    "imputer",
                    SimpleImputer(
                        strategy="median",
                    ),
                ),
                (
                    "scale",
                    StandardScaler(),
                ),
                (
                    "model",
                    LogisticRegression(
                        max_iter=2000,
                        solver="lbfgs",
                        random_state=(
                            random_state
                        ),
                    ),
                ),
            ]
        ),
        "logistic_balanced": (
            Pipeline(
                [
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median",
                        ),
                    ),
                    (
                        "scale",
                        StandardScaler(),
                    ),
                    (
                        "model",
                        LogisticRegression(
                            max_iter=2000,
                            solver="lbfgs",
                            class_weight=(
                                "balanced"
                            ),
                            random_state=(
                                random_state
                            ),
                        ),
                    ),
                ]
            )
        ),
        "hist_gradient_boosting": (
            Pipeline(
                [
                    (
                        "imputer",
                        SimpleImputer(
                            strategy="median",
                        ),
                    ),
                    (
                        "model",
                        HistGradientBoostingClassifier(
                            learning_rate=0.05,
                            max_iter=250,
                            max_leaf_nodes=15,
                            l2_regularization=1.0,
                            class_weight=(
                                "balanced"
                            ),
                            random_state=(
                                random_state
                            ),
                        ),
                    ),
                ]
            )
        ),
    }


def evaluate_models(
    rows: list[
        PredictionRow
    ],
    *,
    n_splits: int = 5,
    random_state: int = 42,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
]:
    x, y, groups = (
        rows_to_arrays(
            rows
        )
    )

    splitter = (
        StratifiedGroupKFold(
            n_splits=n_splits,
            shuffle=True,
            random_state=(
                random_state
            ),
        )
    )

    models = build_models(
        random_state=random_state
    )

    metric_rows: list[
        dict[str, object]
    ] = []

    prediction_rows: list[
        dict[str, object]
    ] = []

    labels = np.arange(
        len(
            STATES
        )
    )

    for model_name, model in (
        models.items()
    ):
        fold_metrics: list[
            dict[str, float]
        ] = []

        for fold, (
            train_index,
            test_index,
        ) in enumerate(
            splitter.split(
                x,
                y,
                groups,
            ),
            start=1,
        ):
            train_groups = set(
                groups[
                    train_index
                ]
            )

            test_groups = set(
                groups[
                    test_index
                ]
            )

            if (
                train_groups
                & test_groups
            ):
                raise RuntimeError(
                    "Session leakage across "
                    "train/test folds."
                )

            model.fit(
                x[
                    train_index
                ],
                y[
                    train_index
                ],
            )

            predicted = model.predict(
                x[
                    test_index
                ]
            )

            probabilities = (
                model.predict_proba(
                    x[
                        test_index
                    ]
                )
            )

            macro_f1 = f1_score(
                y[
                    test_index
                ],
                predicted,
                labels=labels,
                average="macro",
                zero_division=0,
            )

            balanced = (
                balanced_accuracy_score(
                    y[
                        test_index
                    ],
                    predicted,
                )
            )

            accuracy = accuracy_score(
                y[
                    test_index
                ],
                predicted,
            )

            loss = log_loss(
                y[
                    test_index
                ],
                probabilities,
                labels=labels,
            )

            class_f1 = f1_score(
                y[
                    test_index
                ],
                predicted,
                labels=labels,
                average=None,
                zero_division=0,
            )

            fold_metrics.append(
                {
                    "macro_f1": float(
                        macro_f1
                    ),
                    "balanced_accuracy": (
                        float(
                            balanced
                        )
                    ),
                    "accuracy": float(
                        accuracy
                    ),
                    "log_loss": float(
                        loss
                    ),
                    "direct_f1": float(
                        class_f1[0]
                    ),
                    "modified_f1": float(
                        class_f1[1]
                    ),
                    "non_adoption_f1": (
                        float(
                            class_f1[2]
                        )
                    ),
                }
            )

            for (
                local_index,
                row_index,
            ) in enumerate(
                test_index
            ):
                source = rows[
                    int(
                        row_index
                    )
                ]

                prediction_rows.append(
                    {
                        "model": (
                            model_name
                        ),
                        "fold": fold,
                        "session_id": (
                            source.session_id
                        ),
                        "selection_id": (
                            source.selection_id
                        ),
                        "actual": (
                            STATES[
                                int(
                                    y[
                                        row_index
                                    ]
                                )
                            ]
                        ),
                        "predicted": (
                            STATES[
                                int(
                                    predicted[
                                        local_index
                                    ]
                                )
                            ]
                        ),
                        "p_direct_adoption": (
                            float(
                                probabilities[
                                    local_index,
                                    0,
                                ]
                            )
                        ),
                        "p_modified_adoption": (
                            float(
                                probabilities[
                                    local_index,
                                    1,
                                ]
                            )
                        ),
                        "p_non_adoption": (
                            float(
                                probabilities[
                                    local_index,
                                    2,
                                ]
                            )
                        ),
                    }
                )

        for metric_name in (
            "macro_f1",
            "balanced_accuracy",
            "accuracy",
            "log_loss",
            "direct_f1",
            "modified_f1",
            "non_adoption_f1",
        ):
            values = np.asarray(
                [
                    row[
                        metric_name
                    ]
                    for row
                    in fold_metrics
                ],
                dtype=float,
            )

            metric_rows.append(
                {
                    "model": model_name,
                    "metric": (
                        metric_name
                    ),
                    "mean": float(
                        np.mean(
                            values
                        )
                    ),
                    "std": float(
                        np.std(
                            values,
                            ddof=1,
                        )
                    ),
                    "min": float(
                        np.min(
                            values
                        )
                    ),
                    "max": float(
                        np.max(
                            values
                        )
                    ),
                    "folds": (
                        n_splits
                    ),
                }
            )

    return (
        metric_rows,
        prediction_rows,
    )


def grouped_split_audit(
    rows: list[
        PredictionRow
    ],
    *,
    n_splits: int = 5,
    random_state: int = 42,
) -> list[dict[str, object]]:
    x, y, groups = (
        rows_to_arrays(
            rows
        )
    )

    splitter = (
        StratifiedGroupKFold(
            n_splits=n_splits,
            shuffle=True,
            random_state=(
                random_state
            ),
        )
    )

    output: list[
        dict[str, object]
    ] = []

    for fold, (
        train_index,
        test_index,
    ) in enumerate(
        splitter.split(
            x,
            y,
            groups,
        ),
        start=1,
    ):
        train_sessions = set(
            groups[
                train_index
            ]
        )

        test_sessions = set(
            groups[
                test_index
            ]
        )

        overlap = (
            train_sessions
            & test_sessions
        )

        output.append(
            {
                "fold": fold,
                "train_rows": (
                    len(
                        train_index
                    )
                ),
                "test_rows": (
                    len(
                        test_index
                    )
                ),
                "train_sessions": (
                    len(
                        train_sessions
                    )
                ),
                "test_sessions": (
                    len(
                        test_sessions
                    )
                ),
                "session_overlap": (
                    len(
                        overlap
                    )
                ),
                "test_direct": int(
                    np.sum(
                        y[
                            test_index
                        ]
                        == 0
                    )
                ),
                "test_modified": int(
                    np.sum(
                        y[
                            test_index
                        ]
                        == 1
                    )
                ),
                "test_non_adoption": int(
                    np.sum(
                        y[
                            test_index
                        ]
                        == 2
                    )
                ),
            }
        )

    return output
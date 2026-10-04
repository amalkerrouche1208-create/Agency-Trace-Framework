from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

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
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    StratifiedGroupKFold,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    StandardScaler,
)

from agencytrace.ml.prediction import (
    FEATURE_NAMES,
    PredictionRow,
)


@dataclass(
    frozen=True,
    slots=True,
)
class BinaryTask:
    name: str
    negative_outcome: str
    positive_outcome: str


DIRECT_VS_MODIFIED = BinaryTask(
    name="direct_vs_modified",
    negative_outcome=(
        "modified_adoption"
    ),
    positive_outcome=(
        "direct_adoption"
    ),
)

NON_ADOPTION_DETECTION = BinaryTask(
    name="non_adoption_detection",
    negative_outcome=(
        "any_adoption"
    ),
    positive_outcome=(
        "non_adoption"
    ),
)


IMPORTANCE_METRICS: tuple[
    str,
    ...,
] = (
    "roc_auc",
    "average_precision",
)


# =====================================================================
# Dataset construction
# =====================================================================


def build_binary_dataset(
    rows: list[PredictionRow],
    *,
    task: BinaryTask,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    list[PredictionRow],
]:
    """
    Convert leakage-controlled multiclass prediction rows
    into one binary analytical task.
    """

    selected_rows: list[
        PredictionRow
    ] = []

    labels: list[int] = []

    if (
        task.name
        == "direct_vs_modified"
    ):
        allowed = {
            "direct_adoption",
            "modified_adoption",
        }

        for row in rows:
            if (
                row.outcome
                not in allowed
            ):
                continue

            selected_rows.append(
                row
            )

            labels.append(
                int(
                    row.outcome
                    == task.positive_outcome
                )
            )

    elif (
        task.name
        == "non_adoption_detection"
    ):
        for row in rows:
            selected_rows.append(
                row
            )

            labels.append(
                int(
                    row.outcome
                    == "non_adoption"
                )
            )

    else:
        raise ValueError(
            f"Unknown binary task: "
            f"{task.name}"
        )

    if not selected_rows:
        raise ValueError(
            "Binary dataset is empty."
        )

    x = np.asarray(
        [
            row.features
            for row in selected_rows
        ],
        dtype=float,
    )

    y = np.asarray(
        labels,
        dtype=int,
    )

    groups = np.asarray(
        [
            row.session_id
            for row
            in selected_rows
        ],
        dtype=object,
    )

    if len(
        np.unique(y)
    ) != 2:
        raise ValueError(
            "Binary task does not "
            "contain both classes."
        )

    return (
        x,
        y,
        groups,
        selected_rows,
    )


# =====================================================================
# Models
# =====================================================================


def build_binary_models(
    *,
    random_state: int = 42,
) -> dict[str, object]:
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
        "logistic_balanced": Pipeline(
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


def _positive_probability(
    model: object,
    x: np.ndarray,
) -> np.ndarray:
    probabilities = (
        model.predict_proba(
            x
        )
    )

    classes = np.asarray(
        model.classes_
    )

    matches = np.where(
        classes == 1
    )[0]

    if len(matches) != 1:
        raise RuntimeError(
            "Unable to locate "
            "positive class."
        )

    return probabilities[
        :,
        int(matches[0]),
    ]


# =====================================================================
# Binary prediction evaluation
# =====================================================================


def evaluate_binary_task(
    rows: list[PredictionRow],
    *,
    task: BinaryTask,
    n_splits: int = 5,
    random_state: int = 42,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
]:
    (
        x,
        y,
        groups,
        selected_rows,
    ) = build_binary_dataset(
        rows,
        task=task,
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

    models = build_binary_models(
        random_state=random_state
    )

    metric_rows: list[
        dict[str, object]
    ] = []

    prediction_rows: list[
        dict[str, object]
    ] = []

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

            if (
                train_sessions
                & test_sessions
            ):
                raise RuntimeError(
                    "Session leakage "
                    "detected."
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

            positive_probability = (
                _positive_probability(
                    model,
                    x[
                        test_index
                    ],
                )
            )

            actual = y[
                test_index
            ]

            fold_metrics.append(
                {
                    "accuracy": float(
                        accuracy_score(
                            actual,
                            predicted,
                        )
                    ),
                    "balanced_accuracy": (
                        float(
                            balanced_accuracy_score(
                                actual,
                                predicted,
                            )
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
                    "positive_precision": (
                        float(
                            precision_score(
                                actual,
                                predicted,
                                pos_label=1,
                                zero_division=0,
                            )
                        )
                    ),
                    "positive_recall": (
                        float(
                            recall_score(
                                actual,
                                predicted,
                                pos_label=1,
                                zero_division=0,
                            )
                        )
                    ),
                    "positive_f1": float(
                        f1_score(
                            actual,
                            predicted,
                            pos_label=1,
                            zero_division=0,
                        )
                    ),
                    "roc_auc": float(
                        roc_auc_score(
                            actual,
                            positive_probability,
                        )
                    ),
                    "average_precision": (
                        float(
                            average_precision_score(
                                actual,
                                positive_probability,
                            )
                        )
                    ),
                    "brier_score": float(
                        brier_score_loss(
                            actual,
                            positive_probability,
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
                source = (
                    selected_rows[
                        int(
                            row_index
                        )
                    ]
                )

                prediction_rows.append(
                    {
                        "task": (
                            task.name
                        ),
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
                        "actual": int(
                            actual[
                                local_index
                            ]
                        ),
                        "predicted": int(
                            predicted[
                                local_index
                            ]
                        ),
                        "positive_probability": (
                            float(
                                positive_probability[
                                    local_index
                                ]
                            )
                        ),
                    }
                )

        for metric in (
            "accuracy",
            "balanced_accuracy",
            "macro_f1",
            "positive_precision",
            "positive_recall",
            "positive_f1",
            "roc_auc",
            "average_precision",
            "brier_score",
        ):
            values = np.asarray(
                [
                    row[
                        metric
                    ]
                    for row
                    in fold_metrics
                ],
                dtype=float,
            )

            metric_rows.append(
                {
                    "task": (
                        task.name
                    ),
                    "model": (
                        model_name
                    ),
                    "metric": metric,
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


def task_split_audit(
    rows: list[PredictionRow],
    *,
    task: BinaryTask,
    n_splits: int = 5,
    random_state: int = 42,
) -> list[dict[str, object]]:
    (
        x,
        y,
        groups,
        _,
    ) = build_binary_dataset(
        rows,
        task=task,
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

        output.append(
            {
                "task": task.name,
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
                        train_sessions
                        & test_sessions
                    )
                ),
                "test_negative": int(
                    np.sum(
                        y[
                            test_index
                        ]
                        == 0
                    )
                ),
                "test_positive": int(
                    np.sum(
                        y[
                            test_index
                        ]
                        == 1
                    )
                ),
                "test_positive_prevalence": (
                    float(
                        np.mean(
                            y[
                                test_index
                            ]
                        )
                    )
                ),
            }
        )

    return output


# =====================================================================
# Predictive signal explanation
# =====================================================================


def _score_probability(
    metric: str,
    actual: np.ndarray,
    probability: np.ndarray,
) -> float:
    if metric == "roc_auc":
        return float(
            roc_auc_score(
                actual,
                probability,
            )
        )

    if (
        metric
        == "average_precision"
    ):
        return float(
            average_precision_score(
                actual,
                probability,
            )
        )

    raise ValueError(
        f"Unknown metric: {metric}"
    )


def grouped_cv_permutation_importance(
    rows: list[PredictionRow],
    *,
    task: BinaryTask,
    model_name: str,
    n_splits: int = 5,
    permutation_repeats: int = 20,
    random_state: int = 42,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """
    Held-out permutation importance under session-grouped
    cross-validation.

    Importance is the decrease in held-out discrimination
    after permuting one feature:

        baseline score - permuted score

    Positive values indicate useful predictive information.

    This is predictive importance, not a causal effect.
    """

    if permutation_repeats < 1:
        raise ValueError(
            "permutation_repeats "
            "must be >= 1."
        )

    (
        x,
        y,
        groups,
        _,
    ) = build_binary_dataset(
        rows,
        task=task,
    )

    if (
        model_name
        not in build_binary_models(
            random_state=random_state
        )
    ):
        raise ValueError(
            f"Unknown model: "
            f"{model_name}"
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

    rng = np.random.default_rng(
        random_state
    )

    fold_rows: list[
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

        if (
            train_sessions
            & test_sessions
        ):
            raise RuntimeError(
                "Session leakage detected."
            )

        model = build_binary_models(
            random_state=random_state
        )[
            model_name
        ]

        model.fit(
            x[
                train_index
            ],
            y[
                train_index
            ],
        )

        x_test = x[
            test_index
        ]

        y_test = y[
            test_index
        ]

        baseline_probability = (
            _positive_probability(
                model,
                x_test,
            )
        )

        baseline_scores = {
            metric: (
                _score_probability(
                    metric,
                    y_test,
                    baseline_probability,
                )
            )
            for metric
            in IMPORTANCE_METRICS
        }

        for (
            feature_index,
            feature,
        ) in enumerate(
            FEATURE_NAMES
        ):
            repeated = {
                metric: []
                for metric
                in IMPORTANCE_METRICS
            }

            for _ in range(
                permutation_repeats
            ):
                permuted = (
                    x_test.copy()
                )

                order = rng.permutation(
                    len(
                        x_test
                    )
                )

                permuted[
                    :,
                    feature_index,
                ] = permuted[
                    order,
                    feature_index,
                ]

                probability = (
                    _positive_probability(
                        model,
                        permuted,
                    )
                )

                for metric in (
                    IMPORTANCE_METRICS
                ):
                    score = (
                        _score_probability(
                            metric,
                            y_test,
                            probability,
                        )
                    )

                    repeated[
                        metric
                    ].append(
                        baseline_scores[
                            metric
                        ]
                        - score
                    )

            for metric in (
                IMPORTANCE_METRICS
            ):
                values = np.asarray(
                    repeated[
                        metric
                    ],
                    dtype=float,
                )

                fold_rows.append(
                    {
                        "task": (
                            task.name
                        ),
                        "model": (
                            model_name
                        ),
                        "metric": metric,
                        "fold": fold,
                        "feature": feature,
                        "baseline_score": (
                            baseline_scores[
                                metric
                            ]
                        ),
                        "mean_importance": (
                            float(
                                np.mean(
                                    values
                                )
                            )
                        ),
                        "std_permutation": (
                            float(
                                np.std(
                                    values,
                                    ddof=1,
                                )
                            )
                            if len(
                                values
                            ) > 1
                            else 0.0
                        ),
                        "min_importance": (
                            float(
                                np.min(
                                    values
                                )
                            )
                        ),
                        "max_importance": (
                            float(
                                np.max(
                                    values
                                )
                            )
                        ),
                        "permutation_repeats": (
                            permutation_repeats
                        ),
                    }
                )

    grouped: dict[
        tuple[str, str],
        list[
            dict[str, object]
        ],
    ] = defaultdict(list)

    for row in fold_rows:
        grouped[
            (
                str(
                    row[
                        "metric"
                    ]
                ),
                str(
                    row[
                        "feature"
                    ]
                ),
            )
        ].append(
            row
        )

    summary_rows: list[
        dict[str, object]
    ] = []

    for (
        metric,
        feature,
    ), members in (
        grouped.items()
    ):
        values = np.asarray(
            [
                float(
                    row[
                        "mean_importance"
                    ]
                )
                for row in members
            ],
            dtype=float,
        )

        baselines = np.asarray(
            [
                float(
                    row[
                        "baseline_score"
                    ]
                )
                for row in members
            ],
            dtype=float,
        )

        summary_rows.append(
            {
                "task": (
                    task.name
                ),
                "model": (
                    model_name
                ),
                "metric": metric,
                "feature": feature,
                "mean_baseline_score": (
                    float(
                        np.mean(
                            baselines
                        )
                    )
                ),
                "mean_importance": (
                    float(
                        np.mean(
                            values
                        )
                    )
                ),
                "std_across_folds": (
                    float(
                        np.std(
                            values,
                            ddof=1,
                        )
                    )
                    if len(
                        values
                    ) > 1
                    else 0.0
                ),
                "median_importance": (
                    float(
                        np.median(
                            values
                        )
                    )
                ),
                "min_fold_importance": (
                    float(
                        np.min(
                            values
                        )
                    )
                ),
                "max_fold_importance": (
                    float(
                        np.max(
                            values
                        )
                    )
                ),
                "positive_fold_fraction": (
                    float(
                        np.mean(
                            values > 0
                        )
                    )
                ),
                "folds": (
                    len(
                        values
                    )
                ),
                "permutation_repeats_per_fold": (
                    permutation_repeats
                ),
            }
        )

    summary_rows.sort(
        key=lambda row: (
            str(
                row[
                    "metric"
                ]
            ),
            -float(
                row[
                    "mean_importance"
                ]
            ),
        )
    )

    return (
        summary_rows,
        fold_rows,
    )


def logistic_coefficient_stability(
    rows: list[PredictionRow],
    *,
    task: BinaryTask,
    model_names: tuple[
        str,
        ...,
    ] = (
        "logistic",
        "logistic_balanced",
    ),
    n_splits: int = 5,
    random_state: int = 42,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
]:
    """
    Summarize standardized logistic coefficients across
    session-grouped CV folds.

    Positive coefficients point toward the positive task
    outcome. Negative coefficients point toward the
    negative task outcome.

    Coefficients describe associations, not causal effects.
    """

    (
        x,
        y,
        groups,
        _,
    ) = build_binary_dataset(
        rows,
        task=task,
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

    splits = list(
        splitter.split(
            x,
            y,
            groups,
        )
    )

    fold_rows: list[
        dict[str, object]
    ] = []

    for model_name in (
        model_names
    ):
        if model_name not in (
            "logistic",
            "logistic_balanced",
        ):
            raise ValueError(
                "Coefficient stability "
                "requires a logistic model."
            )

        for fold, (
            train_index,
            test_index,
        ) in enumerate(
            splits,
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

            if (
                train_sessions
                & test_sessions
            ):
                raise RuntimeError(
                    "Session leakage detected."
                )

            model = build_binary_models(
                random_state=(
                    random_state
                )
            )[
                model_name
            ]

            model.fit(
                x[
                    train_index
                ],
                y[
                    train_index
                ],
            )

            estimator = (
                model.named_steps[
                    "model"
                ]
            )

            coefficients = np.asarray(
                estimator.coef_,
                dtype=float,
            )

            if coefficients.shape != (
                1,
                len(
                    FEATURE_NAMES
                ),
            ):
                raise RuntimeError(
                    "Unexpected logistic "
                    "coefficient shape."
                )

            for (
                feature_index,
                feature,
            ) in enumerate(
                FEATURE_NAMES
            ):
                coefficient = float(
                    coefficients[
                        0,
                        feature_index,
                    ]
                )

                fold_rows.append(
                    {
                        "task": (
                            task.name
                        ),
                        "model": (
                            model_name
                        ),
                        "fold": fold,
                        "feature": feature,
                        "standardized_coefficient": (
                            coefficient
                        ),
                    }
                )

    grouped: dict[
        tuple[str, str],
        list[float],
    ] = defaultdict(list)

    for row in fold_rows:
        grouped[
            (
                str(
                    row[
                        "model"
                    ]
                ),
                str(
                    row[
                        "feature"
                    ]
                ),
            )
        ].append(
            float(
                row[
                    "standardized_coefficient"
                ]
            )
        )

    summary_rows: list[
        dict[str, object]
    ] = []

    for (
        model_name,
        feature,
    ), raw_values in (
        grouped.items()
    ):
        values = np.asarray(
            raw_values,
            dtype=float,
        )

        mean_coefficient = float(
            np.mean(
                values
            )
        )

        if mean_coefficient > 0:
            direction = (
                task.positive_outcome
            )

            sign_consistency = float(
                np.mean(
                    values > 0
                )
            )

        elif mean_coefficient < 0:
            direction = (
                task.negative_outcome
            )

            sign_consistency = float(
                np.mean(
                    values < 0
                )
            )

        else:
            direction = "neutral"

            sign_consistency = float(
                np.mean(
                    values == 0
                )
            )

        summary_rows.append(
            {
                "task": (
                    task.name
                ),
                "model": (
                    model_name
                ),
                "feature": feature,
                "mean_standardized_coefficient": (
                    mean_coefficient
                ),
                "mean_absolute_coefficient": (
                    float(
                        np.mean(
                            np.abs(
                                values
                            )
                        )
                    )
                ),
                "std_across_folds": (
                    float(
                        np.std(
                            values,
                            ddof=1,
                        )
                    )
                    if len(
                        values
                    ) > 1
                    else 0.0
                ),
                "median_coefficient": (
                    float(
                        np.median(
                            values
                        )
                    )
                ),
                "min_coefficient": (
                    float(
                        np.min(
                            values
                        )
                    )
                ),
                "max_coefficient": (
                    float(
                        np.max(
                            values
                        )
                    )
                ),
                "direction": (
                    direction
                ),
                "sign_consistency": (
                    sign_consistency
                ),
                "folds": (
                    len(
                        values
                    )
                ),
            }
        )

    summary_rows.sort(
        key=lambda row: (
            str(
                row[
                    "model"
                ]
            ),
            -float(
                row[
                    "mean_absolute_coefficient"
                ]
            ),
        )
    )

    return (
        summary_rows,
        fold_rows,
    )
from __future__ import annotations

import csv
from pathlib import Path

from agencytrace.ml.prediction import (
    FEATURE_NAMES,
    build_prediction_rows,
    evaluate_models,
    grouped_split_audit,
    load_insertion_records,
)
from agencytrace.ml.prediction_inference import (
    bootstrap_model_improvement,
    load_binary_predictions,
)
from agencytrace.ml.prediction_tasks import (
    DIRECT_VS_MODIFIED,
    NON_ADOPTION_DETECTION,
    build_binary_dataset,
    evaluate_binary_task,
    grouped_cv_permutation_importance,
    logistic_coefficient_stability,
    task_split_audit,
)


INPUT = Path(
    "data/processed/"
    "selection_metrics.csv"
)

OUTPUT_DIR = Path(
    "data/analysis/ml/"
    "prediction"
)

TASKS = (
    DIRECT_VS_MODIFIED,
    NON_ADOPTION_DETECTION,
)

EXPLANATION_TARGETS = (
    (
        DIRECT_VS_MODIFIED,
        "hist_gradient_boosting",
    ),
    (
        NON_ADOPTION_DETECTION,
        "logistic",
    ),
)

INFERENCE_MODELS = (
    "logistic",
    "logistic_balanced",
    "hist_gradient_boosting",
)

REFERENCE_MODEL = (
    "prior_baseline"
)

N_SPLITS = 5
PERMUTATION_REPEATS = 20
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


def print_multiclass_results(
    metric_rows: list[
        dict[str, object]
    ],
) -> None:
    print()
    print(
        "MULTICLASS EVENTUAL ADOPTION"
    )
    print("-" * 96)

    models = sorted(
        {
            str(
                row[
                    "model"
                ]
            )
            for row in metric_rows
        }
    )

    for model in models:
        selected = {
            str(
                row[
                    "metric"
                ]
            ): row
            for row in metric_rows
            if row[
                "model"
            ] == model
        }

        print()
        print(
            model
        )

        for metric in (
            "macro_f1",
            "balanced_accuracy",
            "accuracy",
            "log_loss",
            "direct_f1",
            "modified_f1",
            "non_adoption_f1",
        ):
            result = selected[
                metric
            ]

            print(
                f"  {metric:<24} "
                f"{float(
                    result['mean']
                ):.4f} "
                f"± "
                f"{float(
                    result['std']
                ):.4f}"
            )


def print_binary_results(
    *,
    task_name: str,
    metric_rows: list[
        dict[str, object]
    ],
) -> None:
    print()
    print(
        task_name.upper()
    )
    print("-" * 96)

    models = sorted(
        {
            str(
                row[
                    "model"
                ]
            )
            for row in metric_rows
        }
    )

    for model in models:
        selected = {
            str(
                row[
                    "metric"
                ]
            ): row
            for row in metric_rows
            if row[
                "model"
            ] == model
        }

        print()
        print(
            model
        )

        for metric in (
            "balanced_accuracy",
            "macro_f1",
            "roc_auc",
            "average_precision",
            "positive_precision",
            "positive_recall",
            "positive_f1",
            "brier_score",
        ):
            result = selected[
                metric
            ]

            print(
                f"  {metric:<22} "
                f"{float(
                    result['mean']
                ):.4f} "
                f"± "
                f"{float(
                    result['std']
                ):.4f}"
            )


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = (
        load_insertion_records(
            INPUT
        )
    )

    rows = (
        build_prediction_rows(
            records
        )
    )

    sessions = {
        row.session_id
        for row in rows
    }

    print()
    print("=" * 96)
    print(
        "AgencyTrace — Prediction Analysis"
    )
    print("=" * 96)

    print(
        f"Selections                    : "
        f"{len(rows)}"
    )

    print(
        f"Sessions                      : "
        f"{len(sessions)}"
    )

    print(
        f"Insertion-time predictors     : "
        f"{len(FEATURE_NAMES)}"
    )

    print(
        f"Grouped CV folds              : "
        f"{N_SPLITS}"
    )

    # =================================================================
    # 1. Multiclass prediction
    # =================================================================

    multiclass_split_rows = (
        grouped_split_audit(
            rows,
            n_splits=N_SPLITS,
            random_state=(
                RANDOM_STATE
            ),
        )
    )

    (
        multiclass_metrics,
        multiclass_predictions,
    ) = evaluate_models(
        rows,
        n_splits=N_SPLITS,
        random_state=(
            RANDOM_STATE
        ),
    )

    print_multiclass_results(
        multiclass_metrics
    )

    # =================================================================
    # 2. Binary prediction tasks
    # =================================================================

    binary_metrics: list[
        dict[str, object]
    ] = []

    binary_predictions: list[
        dict[str, object]
    ] = []

    binary_splits: list[
        dict[str, object]
    ] = []

    print()
    print("=" * 96)
    print(
        "BINARY PREDICTION TASKS"
    )
    print("=" * 96)

    for task in TASKS:
        (
            _,
            y,
            groups,
            _,
        ) = build_binary_dataset(
            rows,
            task=task,
        )

        print()
        print(
            f"{task.name}"
        )

        print(
            f"  Rows                       : "
            f"{len(y)}"
        )

        print(
            f"  Sessions                   : "
            f"{len(set(groups))}"
        )

        print(
            f"  Positive cases             : "
            f"{int(y.sum())}"
        )

        print(
            f"  Positive prevalence        : "
            f"{float(y.mean()):.4f}"
        )

        split_rows = (
            task_split_audit(
                rows,
                task=task,
                n_splits=N_SPLITS,
                random_state=(
                    RANDOM_STATE
                ),
            )
        )

        (
            metric_rows,
            prediction_rows,
        ) = evaluate_binary_task(
            rows,
            task=task,
            n_splits=N_SPLITS,
            random_state=(
                RANDOM_STATE
            ),
        )

        binary_splits.extend(
            split_rows
        )

        binary_metrics.extend(
            metric_rows
        )

        binary_predictions.extend(
            prediction_rows
        )

        print_binary_results(
            task_name=task.name,
            metric_rows=metric_rows,
        )

    # =================================================================
    # 3. Predictive-signal explanation
    # =================================================================

    importance_summary: list[
        dict[str, object]
    ] = []

    importance_folds: list[
        dict[str, object]
    ] = []

    coefficient_summary: list[
        dict[str, object]
    ] = []

    coefficient_folds: list[
        dict[str, object]
    ] = []

    print()
    print("=" * 96)
    print(
        "PREDICTIVE SIGNAL EXPLANATION"
    )
    print("=" * 96)

    for (
        task,
        model_name,
    ) in EXPLANATION_TARGETS:
        (
            summary,
            folds,
        ) = (
            grouped_cv_permutation_importance(
                rows,
                task=task,
                model_name=model_name,
                n_splits=N_SPLITS,
                permutation_repeats=(
                    PERMUTATION_REPEATS
                ),
                random_state=(
                    RANDOM_STATE
                ),
            )
        )

        importance_summary.extend(
            summary
        )

        importance_folds.extend(
            folds
        )

        print()
        print(
            f"{task.name.upper()} "
            f"— {model_name}"
        )
        print("-" * 96)

        ranked = [
            row
            for row in summary
            if row[
                "metric"
            ] == "roc_auc"
        ]

        ranked.sort(
            key=lambda row:
            -float(
                row[
                    "mean_importance"
                ]
            )
        )

        for result in ranked[
            :6
        ]:
            print(
                f"  "
                f"{str(
                    result['feature']
                ):<42} "
                f"importance="
                f"{float(
                    result[
                        'mean_importance'
                    ]
                ):+.4f}  "
                f"positive folds="
                f"{float(
                    result[
                        'positive_fold_fraction'
                    ]
                ):.0%}"
            )

    for task in TASKS:
        (
            summary,
            folds,
        ) = (
            logistic_coefficient_stability(
                rows,
                task=task,
                n_splits=N_SPLITS,
                random_state=(
                    RANDOM_STATE
                ),
            )
        )

        coefficient_summary.extend(
            summary
        )

        coefficient_folds.extend(
            folds
        )

        print()
        print(
            f"{task.name.upper()} "
            "— LOGISTIC ASSOCIATIONS"
        )
        print("-" * 96)

        ranked = [
            row
            for row in summary
            if row[
                "model"
            ] == "logistic"
        ]

        ranked.sort(
            key=lambda row:
            -float(
                row[
                    "mean_absolute_coefficient"
                ]
            )
        )

        for result in ranked[
            :6
        ]:
            print(
                f"  "
                f"{str(
                    result['feature']
                ):<42} "
                f"coef="
                f"{float(
                    result[
                        'mean_standardized_coefficient'
                    ]
                ):+.3f}  "
                f"sign="
                f"{float(
                    result[
                        'sign_consistency'
                    ]
                ):.0%}  "
                f"toward="
                f"{result['direction']}"
            )

    # =================================================================
    # 4. Write prediction outputs
    # =================================================================

    paths = {
        "multiclass_metrics": (
            OUTPUT_DIR
            / "model_metrics.csv"
        ),
        "multiclass_predictions": (
            OUTPUT_DIR
            / "oof_predictions.csv"
        ),
        "multiclass_cv": (
            OUTPUT_DIR
            / "grouped_cv_audit.csv"
        ),
        "feature_manifest": (
            OUTPUT_DIR
            / "feature_manifest.csv"
        ),
        "binary_metrics": (
            OUTPUT_DIR
            / "binary_task_metrics.csv"
        ),
        "binary_predictions": (
            OUTPUT_DIR
            / "binary_task_oof_predictions.csv"
        ),
        "binary_cv": (
            OUTPUT_DIR
            / "binary_task_cv_audit.csv"
        ),
        "importance_summary": (
            OUTPUT_DIR
            / "permutation_importance_summary.csv"
        ),
        "importance_folds": (
            OUTPUT_DIR
            / "permutation_importance_folds.csv"
        ),
        "coefficient_summary": (
            OUTPUT_DIR
            / "logistic_coefficient_summary.csv"
        ),
        "coefficient_folds": (
            OUTPUT_DIR
            / "logistic_coefficient_folds.csv"
        ),
        "inference": (
            OUTPUT_DIR
            / "model_improvement_bootstrap.csv"
        ),
    }

    write_rows(
        paths[
            "multiclass_metrics"
        ],
        multiclass_metrics,
    )

    write_rows(
        paths[
            "multiclass_predictions"
        ],
        multiclass_predictions,
    )

    write_rows(
        paths[
            "multiclass_cv"
        ],
        multiclass_split_rows,
    )

    write_rows(
        paths[
            "feature_manifest"
        ],
        [
            {
                "feature": feature,
                "availability": (
                    "at_or_before_AI_insertion"
                ),
                "future_derived": False,
            }
            for feature in (
                FEATURE_NAMES
            )
        ],
    )

    write_rows(
        paths[
            "binary_metrics"
        ],
        binary_metrics,
    )

    write_rows(
        paths[
            "binary_predictions"
        ],
        binary_predictions,
    )

    write_rows(
        paths[
            "binary_cv"
        ],
        binary_splits,
    )

    write_rows(
        paths[
            "importance_summary"
        ],
        importance_summary,
    )

    write_rows(
        paths[
            "importance_folds"
        ],
        importance_folds,
    )

    write_rows(
        paths[
            "coefficient_summary"
        ],
        coefficient_summary,
    )

    write_rows(
        paths[
            "coefficient_folds"
        ],
        coefficient_folds,
    )

    # =================================================================
    # 5. Session-cluster bootstrap inference
    # =================================================================

    prediction_records = (
        load_binary_predictions(
            paths[
                "binary_predictions"
            ]
        )
    )

    inference_rows: list[
        dict[str, object]
    ] = []

    print()
    print("=" * 96)
    print(
        "MODEL IMPROVEMENT INFERENCE"
    )
    print("=" * 96)

    print(
        f"Session-bootstrap repeats     : "
        f"{BOOTSTRAP_REPEATS}"
    )

    for task in TASKS:
        print()
        print(
            task.name.upper()
        )
        print("-" * 96)

        for model_name in (
            INFERENCE_MODELS
        ):
            results = (
                bootstrap_model_improvement(
                    prediction_records,
                    task=(
                        task.name
                    ),
                    candidate_model=(
                        model_name
                    ),
                    reference_model=(
                        REFERENCE_MODEL
                    ),
                    repeats=(
                        BOOTSTRAP_REPEATS
                    ),
                    random_state=(
                        RANDOM_STATE
                    ),
                )
            )

            inference_rows.extend(
                results
            )

            selected = {
                str(
                    row[
                        "metric"
                    ]
                ): row
                for row in results
            }

            print()
            print(
                model_name
            )

            for metric in (
                "roc_auc",
                "average_precision",
                "balanced_accuracy",
                "macro_f1",
                "brier_score",
            ):
                result = selected[
                    metric
                ]

                print(
                    f"  "
                    f"{metric:<20} "
                    f"improvement="
                    f"{float(
                        result[
                            'observed_improvement'
                        ]
                    ):+.4f}  "
                    f"95% CI=["
                    f"{float(
                        result[
                            'ci_2_5'
                        ]
                    ):+.4f}, "
                    f"{float(
                        result[
                            'ci_97_5'
                        ]
                    ):+.4f}]  "
                    f"p="
                    f"{float(
                        result[
                            'bootstrap_p'
                        ]
                    ):.4f}"
                )

    write_rows(
        paths[
            "inference"
        ],
        inference_rows,
    )

    # =================================================================
    # Final output inventory
    # =================================================================

    print()
    print("=" * 96)
    print(
        "Generated:"
    )

    for path in paths.values():
        print(
            f"  {path}"
        )

    print("=" * 96)
    print(
        "Prediction analysis completed."
    )
    print("=" * 96)


if __name__ == "__main__":
    main()
from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = (
    ROOT
    / "data"
    / "raw"
)

PROCESSED_DIR = (
    ROOT
    / "data"
    / "processed"
)

ANALYSIS_DIR = (
    ROOT
    / "data"
    / "analysis"
)

ML_ANALYSIS_DIR = (
    ANALYSIS_DIR
    / "ml"
)

FIGURE_DIR = (
    ROOT
    / "figures"
)


EXPECTED_SESSIONS = 1447
EXPECTED_SELECTIONS = 12812
EXPECTED_REQUESTS = 18103

EXPECTED_ANALYTICAL_OUTCOMES = {
    "direct_adoption": 7833,
    "modified_adoption": 4754,
    "non_adoption": 225,
}

EXPECTED_OUTCOMES = {
    "accept_unchanged": 12427,
    "accepted_modified": 364,
    "non_adoption": 3205,
    "presented_no_selection": 878,
    "request_without_suggestion": 1229,
}

EXPECTED_GROUP_COUNTS = {
    "Low": {
        "direct_adoption": 1437,
        "modified_adoption": 82,
        "non_adoption": 712,
        "no_selection": 153,
        "no_suggestion": 406,
    },
    "Moderate": {
        "direct_adoption": 3514,
        "modified_adoption": 195,
        "non_adoption": 955,
        "no_selection": 321,
        "no_suggestion": 385,
    },
    "High": {
        "direct_adoption": 7476,
        "modified_adoption": 87,
        "non_adoption": 1538,
        "no_selection": 404,
        "no_suggestion": 438,
    },
}

OUTCOME_COLUMNS = (
    "direct_adoption",
    "modified_adoption",
    "non_adoption",
    "no_selection",
    "no_suggestion",
)

EXPECTED_CROSS_REQUEST_TRANSITIONS = {
    (
        "direct_adoption",
        "direct_adoption",
    ): 4897,
    (
        "direct_adoption",
        "modified_adoption",
    ): 2090,
    (
        "direct_adoption",
        "non_adoption",
    ): 63,
    (
        "modified_adoption",
        "direct_adoption",
    ): 2126,
    (
        "modified_adoption",
        "modified_adoption",
    ): 1938,
    (
        "modified_adoption",
        "non_adoption",
    ): 87,
    (
        "non_adoption",
        "direct_adoption",
    ): 72,
    (
        "non_adoption",
        "modified_adoption",
    ): 92,
    (
        "non_adoption",
        "non_adoption",
    ): 35,
}

EXPECTED_ALL_TRANSITIONS = 11421
EXPECTED_CROSS_REQUEST_TRANSITIONS_TOTAL = 11400
EXPECTED_ENDPOINT_SESSIONS = 1332

EXPECTED_PREDICTION_FEATURES = {
    "log_inserted_chars",
    "selected_index",
    "log_request_to_selection_ms",
    "log_open_to_selection_ms",
    "log_selection_ordinal",
    "log_prior_mean_inserted_chars",
    "log_prior_mean_request_latency_ms",
    "log_event_index",
    "log_event_gap_from_previous_selection",
}

EXPECTED_PREDICTION_MODELS = {
    "prior_baseline",
    "logistic",
    "logistic_balanced",
    "hist_gradient_boosting",
}

EXPECTED_BINARY_TASKS = {
    "direct_vs_modified",
    "non_adoption_detection",
}


def _read_csv(
    path: Path,
) -> list[dict[str, str]]:
    if not path.is_file():
        raise AssertionError(
            "Missing required file: "
            f"{path.relative_to(ROOT)}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(
                handle
            )
        )


def _require_file(
    path: Path,
) -> None:
    if not path.is_file():
        raise AssertionError(
            "Missing required file: "
            f"{path.relative_to(ROOT)}"
        )

    if path.stat().st_size == 0:
        raise AssertionError(
            "Empty required file: "
            f"{path.relative_to(ROOT)}"
        )


def _as_int(
    value: str,
) -> int:
    return int(
        float(
            value
        )
    )


def _as_float(
    value: str,
) -> float:
    result = float(
        value
    )

    if not math.isfinite(
        result
    ):
        raise AssertionError(
            f"Non-finite numeric value: {value!r}"
        )

    return result


def _check_raw_corpus() -> None:
    files = sorted(
        RAW_DIR.rglob(
            "*.jsonl"
        )
    )

    assert (
        len(files)
        == EXPECTED_SESSIONS
    ), (
        "Raw corpus session count mismatch: "
        f"{len(files)} != "
        f"{EXPECTED_SESSIONS}"
    )

    print(
        f"PASS  Raw sessions: "
        f"{len(files)}"
    )


def _check_analytical_metrics() -> None:
    sessions = _read_csv(
        PROCESSED_DIR
        / "session_metrics.csv"
    )

    selections = _read_csv(
        PROCESSED_DIR
        / "selection_metrics.csv"
    )

    assert (
        len(sessions)
        == EXPECTED_SESSIONS
    ), (
        "Session metric row count mismatch."
    )

    assert (
        len(selections)
        == EXPECTED_SELECTIONS
    ), (
        "Selection metric row count mismatch."
    )

    session_ids = {
        row[
            "session_id"
        ]
        for row in sessions
    }

    assert (
        len(session_ids)
        == EXPECTED_SESSIONS
    ), (
        "Session metrics contain duplicate "
        "session identifiers."
    )

    selection_ids = {
        (
            row[
                "session_id"
            ],
            row[
                "selection_id"
            ],
        )
        for row in selections
    }

    assert (
        len(selection_ids)
        == EXPECTED_SELECTIONS
    ), (
        "Selection metrics contain duplicate "
        "selection identifiers."
    )

    outcome_counts = Counter(
        row[
            "adoption_outcome"
        ]
        for row in selections
    )

    assert (
        outcome_counts
        == Counter(
            EXPECTED_ANALYTICAL_OUTCOMES
        )
    ), (
        "Analytical adoption outcome mismatch: "
        f"{dict(outcome_counts)}"
    )

    request_total = sum(
        _as_int(
            row[
                "suggestion_requests"
            ]
        )
        for row in sessions
    )

    selection_total = sum(
        _as_int(
            row[
                "suggestion_selections"
            ]
        )
        for row in sessions
    )

    assert (
        request_total
        == EXPECTED_REQUESTS
    ), (
        "Analytical request total mismatch: "
        f"{request_total}"
    )

    assert (
        selection_total
        == EXPECTED_SELECTIONS
    ), (
        "Analytical selection total mismatch: "
        f"{selection_total}"
    )

    print(
        f"PASS  Session metrics: "
        f"{len(sessions)}"
    )

    print(
        f"PASS  Selection metrics: "
        f"{len(selections)}"
    )

    print(
        "PASS  Analytical adoption "
        "outcome accounting"
    )


def _check_target_replication() -> None:
    sessions = _read_csv(
        PROCESSED_DIR
        / "target_behavior_metrics.csv"
    )

    outcomes = _read_csv(
        PROCESSED_DIR
        / "request_outcomes.csv"
    )

    assert (
        len(sessions)
        == EXPECTED_SESSIONS
    ), (
        "Target behavior session count mismatch."
    )

    assert (
        len(outcomes)
        == EXPECTED_REQUESTS
    ), (
        "Target request count mismatch."
    )

    counts = Counter(
        row[
            "outcome"
        ]
        for row in outcomes
    )

    assert (
        counts
        == Counter(
            EXPECTED_OUTCOMES
        )
    ), (
        "Historical five-way outcome "
        "replication mismatch: "
        f"{dict(counts)}"
    )

    print(
        "PASS  Historical five-way "
        "outcome replication"
    )


def _check_analysis() -> None:
    correlations = _read_csv(
        ANALYSIS_DIR
        / "target_behavior_correlations.csv"
    )

    sample_sizes = _read_csv(
        ANALYSIS_DIR
        / "target_behavior_sample_sizes.csv"
    )

    grouped = _read_csv(
        ANALYSIS_DIR
        / "target_outcomes_by_ai_share.csv"
    )

    assert (
        len(correlations)
        == 10
    ), (
        "Expected 10 rows in "
        "correlation matrix."
    )

    assert (
        len(sample_sizes)
        == 10
    ), (
        "Expected 10 rows in "
        "sample-size matrix."
    )

    assert (
        len(grouped)
        == 3
    ), (
        "Expected exactly three "
        "AI-share groups."
    )

    rows_by_group = {
        row[
            "group"
        ]: row
        for row in grouped
    }

    assert set(
        rows_by_group
    ) == {
        "Low",
        "Moderate",
        "High",
    }, (
        "Unexpected AI-share groups: "
        f"{sorted(rows_by_group)}"
    )

    for (
        group,
        expected_counts,
    ) in (
        EXPECTED_GROUP_COUNTS.items()
    ):
        row = rows_by_group[
            group
        ]

        expected_total = sum(
            expected_counts.values()
        )

        observed_sum = 0.0

        for outcome in (
            OUTCOME_COLUMNS
        ):
            if outcome not in row:
                raise AssertionError(
                    "Missing outcome column "
                    f"{outcome!r} for "
                    f"group {group}."
                )

            observed = float(
                row[
                    outcome
                ]
            )

            expected = (
                expected_counts[
                    outcome
                ]
                / expected_total
            )

            if not math.isclose(
                observed,
                expected,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise AssertionError(
                    f"{group}/{outcome} "
                    f"mismatch: "
                    f"{observed} != "
                    f"{expected}"
                )

            observed_sum += (
                observed
            )

        if not math.isclose(
            observed_sum,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise AssertionError(
                f"{group} outcome shares "
                f"sum to {observed_sum}, "
                "not 1."
            )

    print(
        "PASS  10 x 10 target "
        "correlation matrix"
    )

    print(
        "PASS  Exact AI-share "
        "outcome composition"
    )


def _check_figures() -> None:
    required = (
        FIGURE_DIR
        / "ai_share_response_outcomes.png",
        FIGURE_DIR
        / "ai_share_response_outcomes.pdf",
        FIGURE_DIR
        / "trace_indicator_correlations.png",
        FIGURE_DIR
        / "trace_indicator_correlations.pdf",
    )

    for path in required:
        _require_file(
            path
        )

    print(
        "PASS  Historical target "
        "PNG/PDF figures"
    )


def _check_ml_outputs() -> None:
    feature_path = (
        PROCESSED_DIR
        / "ml_session_features.csv"
    )

    manifest_path = (
        PROCESSED_DIR
        / "ml_session_features_manifest.json"
    )

    features = _read_csv(
        feature_path
    )

    _require_file(
        manifest_path
    )

    assert (
        len(features)
        == EXPECTED_SESSIONS
    ), (
        "ML feature row count mismatch."
    )

    feature_sessions = {
        row[
            "session_id"
        ]
        for row in features
    }

    assert (
        len(feature_sessions)
        == EXPECTED_SESSIONS
    ), (
        "ML feature table contains "
        "duplicate session identifiers."
    )

    required_root_outputs = (
        "feature_diagnostics.csv",
        "feature_pairwise_n.csv",
        "feature_spearman.csv",
        "missingness_patterns.csv",
        "strong_correlations.csv",
        "primary_cluster_manifest.json",
        "primary_cluster_raw.csv",
        "primary_cluster_scaled.csv",
    )

    for name in (
        required_root_outputs
    ):
        _require_file(
            ML_ANALYSIS_DIR
            / name
        )

    clustering_dir = (
        ML_ANALYSIS_DIR
        / "clustering"
    )

    clustering_outputs = (
        "algorithm_agreement.csv",
        "candidate_assignments.csv",
        "cluster_evaluation.csv",
        "cluster_profiles.csv",
        "feature_drop_robustness.csv",
        "feature_set_sensitivity.csv",
        "pca_explained_variance.csv",
        "pca_loadings.csv",
        "pca_scores.csv",
        "scaling_sensitivity.csv",
    )

    for name in (
        clustering_outputs
    ):
        _require_file(
            clustering_dir
            / name
        )

    dimensionality_dir = (
        ML_ANALYSIS_DIR
        / "dimensionality"
    )

    dimensionality_outputs = (
        "pca_bootstrap_component_stability.csv",
        "pca_bootstrap_subspace_stability.csv",
        "pca_loadings_by_scaling.csv",
        "pca_scaling_component_alignment.csv",
        "pca_scaling_subspace_similarity.csv",
        "pca_scores_by_scaling.csv",
        "pca_variance_by_scaling.csv",
    )

    for name in (
        dimensionality_outputs
    ):
        _require_file(
            dimensionality_dir
            / name
        )

    print(
        f"PASS  ML session features: "
        f"{len(features)}"
    )

    print(
        "PASS  Exploratory clustering "
        "and dimensionality outputs"
    )


def _check_temporal_outputs() -> None:
    transition_dir = (
        ML_ANALYSIS_DIR
        / "transitions"
    )

    required = (
        "transition_matrix.csv",
        "transition_bootstrap.csv",
        "session_transition_metrics.csv",
        "positional_outcomes.csv",
        "endpoint_matrix.csv",
        "transition_permutation_null.csv",
        "transition_persistence_test.csv",
        "session_phase_shares.csv",
        "session_weighted_phase_summary.csv",
        "early_late_change.csv",
    )

    for name in required:
        _require_file(
            transition_dir
            / name
        )

    selections = _read_csv(
        PROCESSED_DIR
        / "selection_metrics.csv"
    )

    sequences: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(
        list
    )

    for row in selections:
        sequences[
            row[
                "session_id"
            ]
        ].append(
            row
        )

    for sequence in (
        sequences.values()
    ):
        sequence.sort(
            key=lambda row: (
                _as_int(
                    row[
                        "selection_event_num"
                    ]
                ),
                _as_int(
                    row[
                        "request_event_num"
                    ]
                ),
                row[
                    "selection_id"
                ],
            )
        )

    all_transition_count = 0
    cross_transition_count = 0

    cross_counts: Counter[
        tuple[str, str]
    ] = Counter()

    endpoint_sessions = 0

    for sequence in (
        sequences.values()
    ):
        if len(sequence) >= 2:
            endpoint_sessions += 1

        for previous, current in zip(
            sequence,
            sequence[
                1:
            ],
        ):
            all_transition_count += 1

            if (
                previous[
                    "request_id"
                ]
                == current[
                    "request_id"
                ]
            ):
                continue

            cross_transition_count += 1

            cross_counts[
                (
                    previous[
                        "adoption_outcome"
                    ],
                    current[
                        "adoption_outcome"
                    ],
                )
            ] += 1

    assert (
        all_transition_count
        == EXPECTED_ALL_TRANSITIONS
    ), (
        "All-transition count mismatch: "
        f"{all_transition_count}"
    )

    assert (
        cross_transition_count
        == EXPECTED_CROSS_REQUEST_TRANSITIONS_TOTAL
    ), (
        "Cross-request transition "
        "count mismatch: "
        f"{cross_transition_count}"
    )

    assert (
        cross_counts
        == Counter(
            EXPECTED_CROSS_REQUEST_TRANSITIONS
        )
    ), (
        "Cross-request transition matrix "
        f"mismatch: {dict(cross_counts)}"
    )

    assert (
        endpoint_sessions
        == EXPECTED_ENDPOINT_SESSIONS
    ), (
        "Endpoint-eligible session "
        "count mismatch: "
        f"{endpoint_sessions}"
    )

    persistence = _read_csv(
        transition_dir
        / "transition_persistence_test.csv"
    )

    assert (
        len(persistence)
        == 1
    ), (
        "Expected one persistence "
        "summary row."
    )

    expected_self_rate = (
        (
            EXPECTED_CROSS_REQUEST_TRANSITIONS[
                (
                    "direct_adoption",
                    "direct_adoption",
                )
            ]
            + EXPECTED_CROSS_REQUEST_TRANSITIONS[
                (
                    "modified_adoption",
                    "modified_adoption",
                )
            ]
            + EXPECTED_CROSS_REQUEST_TRANSITIONS[
                (
                    "non_adoption",
                    "non_adoption",
                )
            ]
        )
        / EXPECTED_CROSS_REQUEST_TRANSITIONS_TOTAL
    )

    observed_self_rate = (
        _as_float(
            persistence[
                0
            ][
                "observed_self_transition_rate"
            ]
        )
    )

    assert math.isclose(
        observed_self_rate,
        expected_self_rate,
        rel_tol=0.0,
        abs_tol=1e-12,
    ), (
        "Observed self-transition rate "
        "does not match the exact "
        "transition matrix."
    )

    early_late = _read_csv(
        transition_dir
        / "early_late_change.csv"
    )

    assert (
        len(early_late)
        == 3
    ), (
        "Expected three early-to-late "
        "outcome rows."
    )

    changes = {
        row[
            "outcome"
        ]: row
        for row in early_late
    }

    assert set(
        changes
    ) == {
        "direct_adoption",
        "modified_adoption",
        "non_adoption",
    }, (
        "Unexpected early-to-late "
        "outcome labels."
    )

    direct = changes[
        "direct_adoption"
    ]

    modified = changes[
        "modified_adoption"
    ]

    non_adoption = changes[
        "non_adoption"
    ]

    assert (
        _as_float(
            direct[
                "mean_late_minus_early"
            ]
        )
        > 0.0
    )

    assert (
        _as_float(
            direct[
                "ci_2_5"
            ]
        )
        > 0.0
    )

    assert (
        _as_float(
            modified[
                "mean_late_minus_early"
            ]
        )
        < 0.0
    )

    assert (
        _as_float(
            modified[
                "ci_97_5"
            ]
        )
        < 0.0
    )

    non_lower = _as_float(
        non_adoption[
            "ci_2_5"
        ]
    )

    non_upper = _as_float(
        non_adoption[
            "ci_97_5"
        ]
    )

    assert (
        non_lower
        <= 0.0
        <= non_upper
    ), (
        "Non-Adoption early-to-late "
        "interval no longer contains zero."
    )

    print(
        "PASS  Exact cross-request "
        "transition accounting"
    )

    print(
        "PASS  Session-weighted temporal "
        "direction checks"
    )


def _binary_metric(
    rows: list[
        dict[str, str]
    ],
    *,
    task: str,
    model: str,
    metric: str,
) -> float:
    matches = [
        row
        for row in rows
        if (
            row[
                "task"
            ]
            == task
            and row[
                "model"
            ]
            == model
            and row[
                "metric"
            ]
            == metric
        )
    ]

    if len(matches) != 1:
        raise AssertionError(
            "Expected exactly one binary "
            "metric row for "
            f"{task}/{model}/{metric}; "
            f"found {len(matches)}."
        )

    return _as_float(
        matches[
            0
        ][
            "mean"
        ]
    )


def _check_prediction_outputs() -> None:
    prediction_dir = (
        ML_ANALYSIS_DIR
        / "prediction"
    )

    required = (
        "model_metrics.csv",
        "oof_predictions.csv",
        "grouped_cv_audit.csv",
        "feature_manifest.csv",
        "binary_task_metrics.csv",
        "binary_task_oof_predictions.csv",
        "binary_task_cv_audit.csv",
        "permutation_importance_summary.csv",
        "permutation_importance_folds.csv",
        "logistic_coefficient_summary.csv",
        "logistic_coefficient_folds.csv",
        "model_improvement_bootstrap.csv",
    )

    for name in required:
        _require_file(
            prediction_dir
            / name
        )

    manifest = _read_csv(
        prediction_dir
        / "feature_manifest.csv"
    )

    observed_features = {
        row[
            "feature"
        ]
        for row in manifest
    }

    assert (
        observed_features
        == EXPECTED_PREDICTION_FEATURES
    ), (
        "Prediction feature manifest "
        "mismatch: "
        f"{sorted(observed_features)}"
    )

    assert (
        len(manifest)
        == len(
            EXPECTED_PREDICTION_FEATURES
        )
    ), (
        "Unexpected number of prediction "
        "features."
    )

    for row in manifest:
        assert (
            row[
                "availability"
            ]
            == "at_or_before_AI_insertion"
        ), (
            "Prediction feature availability "
            "is not insertion-time safe."
        )

        assert (
            row[
                "future_derived"
            ]
            .strip()
            .lower()
            in {
                "false",
                "0",
            }
        ), (
            "Prediction feature is marked "
            "as future-derived."
        )

    grouped_cv = _read_csv(
        prediction_dir
        / "grouped_cv_audit.csv"
    )

    assert (
        len(grouped_cv)
        == 5
    ), (
        "Expected five grouped CV folds."
    )

    assert all(
        _as_int(
            row[
                "session_overlap"
            ]
        )
        == 0
        for row in grouped_cv
    ), (
        "Session leakage detected in "
        "multiclass grouped CV."
    )

    binary_cv = _read_csv(
        prediction_dir
        / "binary_task_cv_audit.csv"
    )

    assert (
        len(binary_cv)
        == 10
    ), (
        "Expected ten binary grouped "
        "CV audit rows."
    )

    assert all(
        _as_int(
            row[
                "session_overlap"
            ]
        )
        == 0
        for row in binary_cv
    ), (
        "Session leakage detected in "
        "binary grouped CV."
    )

    binary_metrics = _read_csv(
        prediction_dir
        / "binary_task_metrics.csv"
    )

    assert (
        len(binary_metrics)
        == 72
    ), (
        "Binary metric row count mismatch."
    )

    tasks = {
        row[
            "task"
        ]
        for row in binary_metrics
    }

    models = {
        row[
            "model"
        ]
        for row in binary_metrics
    }

    assert (
        tasks
        == EXPECTED_BINARY_TASKS
    ), (
        "Unexpected binary prediction "
        f"tasks: {sorted(tasks)}"
    )

    assert (
        models
        == EXPECTED_PREDICTION_MODELS
    ), (
        "Unexpected prediction models: "
        f"{sorted(models)}"
    )

    direct_baseline_auc = (
        _binary_metric(
            binary_metrics,
            task="direct_vs_modified",
            model="prior_baseline",
            metric="roc_auc",
        )
    )

    direct_hgb_auc = (
        _binary_metric(
            binary_metrics,
            task="direct_vs_modified",
            model=(
                "hist_gradient_boosting"
            ),
            metric="roc_auc",
        )
    )

    non_baseline_auc = (
        _binary_metric(
            binary_metrics,
            task="non_adoption_detection",
            model="prior_baseline",
            metric="roc_auc",
        )
    )

    non_logistic_auc = (
        _binary_metric(
            binary_metrics,
            task="non_adoption_detection",
            model="logistic",
            metric="roc_auc",
        )
    )

    assert math.isclose(
        direct_baseline_auc,
        0.5,
        rel_tol=0.0,
        abs_tol=1e-12,
    )

    assert math.isclose(
        non_baseline_auc,
        0.5,
        rel_tol=0.0,
        abs_tol=1e-12,
    )

    assert (
        direct_hgb_auc
        > direct_baseline_auc
    ), (
        "Direct-vs-Modified HGB "
        "discrimination no longer "
        "exceeds the prior baseline."
    )

    assert (
        non_logistic_auc
        > non_baseline_auc
    ), (
        "Non-Adoption logistic ranking "
        "no longer exceeds the prior "
        "baseline."
    )

    multiclass_metrics = _read_csv(
        prediction_dir
        / "model_metrics.csv"
    )

    assert (
        len(multiclass_metrics)
        == 28
    ), (
        "Multiclass metric row "
        "count mismatch."
    )

    improvement = _read_csv(
        prediction_dir
        / "model_improvement_bootstrap.csv"
    )

    assert (
        len(improvement)
        == 30
    ), (
        "Prediction-improvement bootstrap "
        "row count mismatch."
    )

    print(
        "PASS  Prediction feature "
        "leakage guard"
    )

    print(
        "PASS  Grouped CV session "
        "isolation"
    )

    print(
        "PASS  Prediction output "
        "structure and baseline checks"
    )


def main() -> None:
    print()
    print("=" * 78)
    print(
        "AgencyTrace — Release Validation"
    )
    print("=" * 78)

    checks = (
        _check_raw_corpus,
        _check_analytical_metrics,
        _check_target_replication,
        _check_analysis,
        _check_figures,
        _check_ml_outputs,
        _check_temporal_outputs,
        _check_prediction_outputs,
    )

    try:
        for check in checks:
            check()

    except (
        AssertionError,
        KeyError,
        ValueError,
    ) as exc:
        print()
        print(
            f"FAIL  {exc}"
        )
        print("=" * 78)

        raise SystemExit(
            1
        ) from exc

    print()
    print("=" * 78)
    print(
        "AgencyTrace release "
        "validation PASSED."
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
ANALYSIS_DIR = ROOT / "data" / "analysis"
FIGURE_DIR = ROOT / "figures"


EXPECTED_SESSIONS = 1447
EXPECTED_SELECTIONS = 12812
EXPECTED_REQUESTS = 18103

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


def _read_csv(
    path: Path,
) -> list[dict[str, str]]:
    if not path.is_file():
        raise AssertionError(
            f"Missing required file: "
            f"{path.relative_to(ROOT)}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(handle)
        )


def _require_file(
    path: Path,
) -> None:
    if not path.is_file():
        raise AssertionError(
            f"Missing required file: "
            f"{path.relative_to(ROOT)}"
        )

    if path.stat().st_size == 0:
        raise AssertionError(
            f"Empty required file: "
            f"{path.relative_to(ROOT)}"
        )


def _check_raw_corpus() -> None:
    files = sorted(
        RAW_DIR.rglob("*.jsonl")
    )

    assert len(files) == EXPECTED_SESSIONS, (
        "Raw corpus session count mismatch: "
        f"{len(files)} != {EXPECTED_SESSIONS}"
    )

    print(
        f"PASS  Raw sessions: {len(files)}"
    )


def _check_modern_metrics() -> None:
    sessions = _read_csv(
        PROCESSED_DIR
        / "session_metrics.csv"
    )

    selections = _read_csv(
        PROCESSED_DIR
        / "selection_metrics.csv"
    )

    assert len(sessions) == EXPECTED_SESSIONS, (
        "Session metric row count mismatch."
    )

    assert len(selections) == EXPECTED_SELECTIONS, (
        "Selection metric row count mismatch."
    )

    print(
        f"PASS  Session metrics: "
        f"{len(sessions)}"
    )

    print(
        f"PASS  Selection metrics: "
        f"{len(selections)}"
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

    assert len(sessions) == EXPECTED_SESSIONS, (
        "Target behavior session count mismatch."
    )

    assert len(outcomes) == EXPECTED_REQUESTS, (
        "Target request count mismatch."
    )

    counts = Counter(
        row["outcome"]
        for row in outcomes
    )

    assert counts == Counter(EXPECTED_OUTCOMES), (
        "Historical five-way outcome "
        f"replication mismatch: {dict(counts)}"
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

    assert len(correlations) == 10, (
        "Expected 10 rows in correlation matrix."
    )

    assert len(sample_sizes) == 10, (
        "Expected 10 rows in sample-size matrix."
    )

    assert len(grouped) == 3, (
        "Expected exactly three AI-share groups."
    )

    rows_by_group = {
        row["group"]: row
        for row in grouped
    }

    assert set(rows_by_group) == {
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
    ) in EXPECTED_GROUP_COUNTS.items():
        row = rows_by_group[group]

        expected_total = sum(
            expected_counts.values()
        )

        observed_sum = 0.0

        for outcome in OUTCOME_COLUMNS:
            if outcome not in row:
                raise AssertionError(
                    "Missing outcome column "
                    f"{outcome!r} for group {group}."
                )

            observed = float(
                row[outcome]
            )

            expected = (
                expected_counts[outcome]
                / expected_total
            )

            if not math.isclose(
                observed,
                expected,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise AssertionError(
                    f"{group}/{outcome} mismatch: "
                    f"{observed} != {expected}"
                )

            observed_sum += observed

        if not math.isclose(
            observed_sum,
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise AssertionError(
                f"{group} outcome shares "
                f"sum to {observed_sum}, not 1."
            )

    print(
        "PASS  10 x 10 target "
        "correlation matrix"
    )

    print(
        "PASS  Exact AI-share outcome composition"
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
        _require_file(path)

    print(
        "PASS  Target PNG/PDF figures"
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
        _check_modern_metrics,
        _check_target_replication,
        _check_analysis,
        _check_figures,
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

        raise SystemExit(1) from exc

    print()
    print("=" * 78)
    print(
        "AgencyTrace release validation PASSED."
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


AUDIT_STAGES = {
    "Text-delta audit",
    "Suggestion lifecycle audit",
    "Provenance audit",
    "Metric audit",
    "ML feature audit",
}


STAGES = (
    # ================================================================
    # Core reconstruction and analytical metrics
    # ================================================================
    (
        "Text-delta audit",
        (
            "scripts/audit_text_deltas.py",
        ),
    ),
    (
        "Suggestion lifecycle audit",
        (
            "scripts/audit_suggestion_episodes.py",
        ),
    ),
    (
        "Provenance audit",
        (
            "scripts/audit_provenance.py",
        ),
    ),
    (
        "Analytical metric export",
        (
            "scripts/export_metrics.py",
        ),
    ),
    (
        "Metric audit",
        (
            "scripts/audit_metrics.py",
        ),
    ),

    # ================================================================
    # Historical reproduction layer
    # ================================================================
    (
        "Historical target reproduction",
        (
            "scripts/export_target_behavior.py",
        ),
    ),
    (
        "Historical target analysis",
        (
            "-m",
            "agencytrace.analysis",
        ),
    ),
    (
        "Historical figure reproduction",
        (
            "-m",
            "agencytrace.figures",
        ),
    ),

    # ================================================================
    # AgencyTrace behavioral feature layer
    # ================================================================
    (
        "ML feature export",
        (
            "scripts/export_ml_dataset.py",
        ),
    ),
    (
        "ML feature audit",
        (
            "scripts/audit_ml_features.py",
        ),
    ),
    (
        "ML feature diagnostics",
        (
            "scripts/analyze_ml_features.py",
        ),
    ),
    (
        "ML matrix preparation",
        (
            "scripts/prepare_ml_matrix.py",
        ),
    ),

    # ================================================================
    # Exploratory behavioral structure
    # ================================================================
    (
        "Exploratory clustering",
        (
            "scripts/evaluate_ml_clusters.py",
        ),
    ),
    (
        "Cluster profiling",
        (
            "scripts/profile_ml_clusters.py",
        ),
    ),
    (
        "Cluster robustness",
        (
            "scripts/evaluate_cluster_robustness.py",
        ),
    ),
    (
        "Cluster sensitivity",
        (
            "scripts/evaluate_cluster_sensitivity.py",
        ),
    ),
    (
        "Dimensionality robustness",
        (
            "scripts/evaluate_dimension_robustness.py",
        ),
    ),

    # ================================================================
    # Temporal and prospective analyses
    # ================================================================
    (
        "Temporal response-use analysis",
        (
            "scripts/analyze_selection_transitions.py",
        ),
    ),
    (
        "Prediction analysis",
        (
            "scripts/evaluate_prediction_tasks.py",
        ),
    ),

    # ================================================================
    # Repository verification
    # ================================================================
    (
        "Test suite",
        (
            "-m",
            "pytest",
            "-q",
        ),
    ),
    (
        "Release validation",
        (
            "scripts/validate_release.py",
        ),
    ),
)


def _run_stage(
    name: str,
    args: tuple[str, ...],
) -> None:
    command = [
        sys.executable,
        *args,
    ]

    print()
    print("=" * 78)
    print(
        f"AgencyTrace — {name}"
    )
    print("=" * 78)
    print(
        "Command:",
        " ".join(
            command
        ),
    )
    print()

    started = (
        time.perf_counter()
    )

    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    if completed.returncode != 0:
        raise SystemExit(
            f"\nStage FAILED: {name}\n"
            f"Exit code: "
            f"{completed.returncode}"
        )

    print()
    print(
        f"Stage completed in "
        f"{elapsed:.1f} s."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reproduce the complete AgencyTrace "
            "analysis from the CoAuthor raw corpus."
        )
    )

    parser.add_argument(
        "--skip-audits",
        action="store_true",
        help=(
            "Skip corpus and feature audit stages "
            "while retaining exports, analytical "
            "stages, tests, and release validation."
        ),
    )

    args = parser.parse_args()

    started = (
        time.perf_counter()
    )

    print()
    print("=" * 78)
    print(
        "AgencyTrace — Full Reproduction Pipeline"
    )
    print("=" * 78)
    print(
        f"Repository : {ROOT}"
    )
    print(
        f"Python     : {sys.executable}"
    )

    for name, command in STAGES:
        if (
            args.skip_audits
            and name
            in AUDIT_STAGES
        ):
            print()
            print(
                f"SKIP: {name}"
            )
            continue

        _run_stage(
            name,
            command,
        )

    elapsed = (
        time.perf_counter()
        - started
    )

    print()
    print("=" * 78)
    print(
        "AgencyTrace reproduction "
        "completed successfully."
    )
    print(
        f"Total elapsed time: "
        f"{elapsed / 60.0:.1f} min"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
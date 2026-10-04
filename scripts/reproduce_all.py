from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


STAGES = (
    (
        "Text-delta audit",
        ("scripts/audit_text_deltas.py",),
    ),
    (
        "Suggestion lifecycle audit",
        ("scripts/audit_suggestion_episodes.py",),
    ),
    (
        "Provenance audit",
        ("scripts/audit_provenance.py",),
    ),
    (
        "Modern metric export",
        ("scripts/export_metrics.py",),
    ),
    (
        "Metric audit",
        ("scripts/audit_metrics.py",),
    ),
    (
        "Historical target reproduction",
        ("scripts/export_target_behavior.py",),
    ),
    (
        "Target analysis",
        ("-m", "agencytrace.analysis"),
    ),
    (
        "Figure generation",
        ("-m", "agencytrace.figures"),
    ),
    (
        "Release validation",
        ("scripts/validate_release.py",),
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
    print(f"AgencyTrace — {name}")
    print("=" * 78)
    print(
        "Command:",
        " ".join(command),
    )
    print()

    started = time.perf_counter()

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
            f"Exit code: {completed.returncode}"
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
            "Skip corpus audit stages and run "
            "exports, analysis, figures, and "
            "release validation only."
        ),
    )

    args = parser.parse_args()

    started = time.perf_counter()

    print()
    print("=" * 78)
    print(
        "AgencyTrace — Full Reproduction Pipeline"
    )
    print("=" * 78)
    print(f"Repository : {ROOT}")
    print(f"Python     : {sys.executable}")

    for name, command in STAGES:
        if (
            args.skip_audits
            and name
            in {
                "Text-delta audit",
                "Suggestion lifecycle audit",
                "Provenance audit",
                "Metric audit",
            }
        ):
            print(
                f"\nSKIP: {name}"
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
        "AgencyTrace reproduction completed successfully."
    )
    print(
        f"Total elapsed time: "
        f"{elapsed / 60.0:.1f} min"
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
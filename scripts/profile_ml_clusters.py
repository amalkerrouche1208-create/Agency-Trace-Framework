from __future__ import annotations

import csv
from pathlib import Path

from agencytrace.ml.profiling import (
    export_cluster_profiles,
)


RAW_MATRIX = Path(
    "data/analysis/ml/"
    "primary_cluster_raw.csv"
)

ASSIGNMENTS = Path(
    "data/analysis/ml/clustering/"
    "candidate_assignments.csv"
)

OUTPUT = Path(
    "data/analysis/ml/clustering/"
    "cluster_profiles.csv"
)

CANDIDATES = (
    "kmeans_k2",
    "kmeans_k4",
)


def main() -> None:
    export_cluster_profiles(
        raw_matrix=RAW_MATRIX,
        assignments=ASSIGNMENTS,
        output=OUTPUT,
        assignment_columns=(
            CANDIDATES
        ),
    )

    with OUTPUT.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(
            csv.DictReader(handle)
        )

    print()
    print("=" * 86)
    print(
        "AgencyTrace — Candidate Cluster Profiles"
    )
    print("=" * 86)

    for solution in CANDIDATES:
        print()
        print(solution)
        print("-" * 86)

        solution_rows = [
            row
            for row in rows
            if row["solution"]
            == solution
        ]

        clusters = sorted(
            {
                int(
                    row["cluster"]
                )
                for row
                in solution_rows
            }
        )

        for cluster in clusters:
            members = [
                row
                for row
                in solution_rows
                if int(
                    row["cluster"]
                )
                == cluster
            ]

            n = int(
                members[0]["n"]
            )

            fraction = float(
                members[0][
                    "cluster_fraction"
                ]
            )

            print()
            print(
                f"Cluster {cluster}: "
                f"n={n} "
                f"({fraction:.1%})"
            )

            for row in members:
                print(
                    f"  "
                    f"{row['feature']:<42} "
                    f"median="
                    f"{float(row['median']):.4f}"
                )

    print()
    print(
        f"Profiles written to: {OUTPUT}"
    )
    print("=" * 86)


if __name__ == "__main__":
    main()
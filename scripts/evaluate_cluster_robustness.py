from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from agencytrace.ml.clustering import (
    load_scaled_matrix,
)
from agencytrace.ml.robustness import (
    evaluate_feature_drop_robustness,
)


INPUT = Path(
    "data/analysis/ml/"
    "primary_cluster_scaled.csv"
)

OUTPUT = Path(
    "data/analysis/ml/clustering/"
    "feature_drop_robustness.csv"
)


def main() -> None:
    data = load_scaled_matrix(
        INPUT
    )

    rows = []

    for k in (2, 4):
        results = (
            evaluate_feature_drop_robustness(
                data.values,
                data.feature_names,
                k=k,
            )
        )

        rows.extend(
            asdict(result)
            for result in results
        )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT.open(
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
        writer.writerows(rows)

    print()
    print("=" * 82)
    print(
        "AgencyTrace — Feature-Drop Cluster Robustness"
    )
    print("=" * 82)

    for k in (2, 4):
        print()
        print(f"K-means k={k}")
        print("-" * 82)

        subset = [
            row
            for row in rows
            if row["k"] == k
        ]

        subset.sort(
            key=lambda row:
            row["ari_vs_primary"]
        )

        for row in subset:
            print(
                f"{row['removed_feature']:<42} "
                f"ARI={row['ari_vs_primary']:.3f}"
            )

    print()
    print(
        f"Written to: {OUTPUT}"
    )
    print("=" * 82)


if __name__ == "__main__":
    main()